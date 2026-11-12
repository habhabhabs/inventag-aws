"""Connects templates to the main ``inventag`` command.

``inventag/cli/main.py`` calls three functions from here:

* :func:`add_template_arguments` adds ``--template`` to the parser;
* :func:`prepare_template_run` loads the templates, applies a config template
  to the parsed arguments (flags you type always win) and returns a
  :class:`TemplateRun`, or ``None`` when no ``--template`` was given;
* :meth:`TemplateRun.create_generator` and :meth:`TemplateRun.finish` wrap the
  BOM generator and decide the exit code.
"""

from __future__ import annotations

import argparse
import atexit
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml

from ..core import CloudBOMGenerator
from ..reporting import BOMDataProcessor
from .errors import TemplateError, TemplateIssue
from .loader import safe_relative_path
from .registry import ResolvedTemplate, TemplateRegistry
from .schema import LOGO_SUFFIXES
from .render_excel import render_excel
from .render_word import render_word
from .tag_policy import ComplianceReport, evaluate

EXIT_TAG_VIOLATIONS = 3
DEFAULT_REPORT = "standard-bom"


def add_template_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group(
        "Templates",
        "Reusable report layouts, tag policies and run settings. "
        "See 'inventag templates --help'.",
    )
    group.add_argument(
        "--template",
        action="append",
        metavar="NAME|PATH",
        help=(
            "Use a template by name or file path. Repeat to combine one report, "
            "one tag-policy and one config template, e.g. "
            "--template standard-bom --template finops-cost-allocation"
        ),
    )


def explicit_dests(parser_factory, argv: List[str]) -> set:
    """Names of the options that were actually typed on the command line."""
    parser = parser_factory()
    for action in parser._actions:
        action.default = argparse.SUPPRESS
    namespace, _ = parser.parse_known_args(argv)
    return set(vars(namespace))


class TemplateRun:
    """Templates chosen for one run of ``inventag``."""

    def __init__(
        self,
        report: ResolvedTemplate,
        policy: Optional[ResolvedTemplate],
        config: Optional[ResolvedTemplate],
    ):
        self.report = report
        self.policy = policy
        self.config = config
        self.compliance: Optional[ComplianceReport] = None
        self._temp_files: List[str] = []

    @property
    def fail_on_violations(self) -> bool:
        return bool(self.config and self.config.spec.get("fail_on_tag_violations"))

    def describe(self) -> str:
        parts = [f"report={self.report.name}"]
        if self.policy:
            parts.append(f"tag-policy={self.policy.name}")
        if self.config:
            parts.append(f"config={self.config.name}")
        return ", ".join(parts)

    def create_generator(self, config) -> "TemplatedCloudBOMGenerator":
        return TemplatedCloudBOMGenerator(config, self)

    def finish(self, results: Dict[str, Any], logger: logging.Logger) -> int:
        """Print a short summary and return the exit code (0 or 3)."""
        files = results.get("bom_generation", {}).get("generated_files", [])
        for path in files:
            print(f"Wrote {path}")
        if self.compliance is None:
            return 0
        c = self.compliance
        print(
            f"Tag policy '{c.policy_name}': {c.compliant} of {c.checked} resources "
            f"compliant ({c.percent_compliant:.1f}%), {c.non_compliant} non-compliant, "
            f"{c.out_of_scope} out of scope."
        )
        if c.non_compliant and self.fail_on_violations:
            print(
                "Tag policy violations found and fail_on_tag_violations is true "
                f"(exit code {EXIT_TAG_VIOLATIONS}).",
                file=sys.stderr,
            )
            return EXIT_TAG_VIOLATIONS
        return 0

    def write_accounts_file(self, accounts: List[Dict[str, Any]]) -> str:
        """Write the config template's accounts to a private temporary file."""
        fd, path = tempfile.mkstemp(prefix="inventag-accounts-", suffix=".yaml")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump({"accounts": accounts}, handle, sort_keys=False)
        self._temp_files.append(path)
        atexit.register(self.cleanup)
        return path

    def cleanup(self) -> None:
        for path in self._temp_files:
            try:
                os.remove(path)
            except OSError:
                pass
        self._temp_files = []


def _account_entry(account: Dict[str, Any], default_regions) -> Dict[str, Any]:
    entry = {k: v for k, v in account.items() if v not in (None, "", [])}
    if "regions" not in entry and default_regions:
        entry["regions"] = list(default_regions)
    return entry


def apply_config(run: TemplateRun, args, explicit: set, logger) -> None:
    """Copy config-template settings onto ``args`` unless typed on the CLI."""
    spec = run.config.spec

    def unset(dest: str) -> bool:
        return dest not in explicit

    account_flags = {"accounts_file", "accounts_prompt", "cross_account_role"}
    if spec.get("accounts"):
        if explicit & account_flags:
            logger.warning(
                f"Config template '{run.config.name}' lists accounts, but an account "
                "option was given on the command line; using the command line"
            )
        else:
            accounts = [
                _account_entry(a, spec.get("regions")) for a in spec["accounts"]
            ]
            args.accounts_file = run.write_accounts_file(accounts)
    if spec.get("regions") and unset("account_regions"):
        args.account_regions = ",".join(spec["regions"])
    if spec.get("services") and unset("account_services"):
        args.account_services = ",".join(spec["services"])
    if unset("create_excel") and unset("create_word"):
        outputs = spec.get("outputs") or ["excel"]
        args.create_excel = "excel" in outputs
        args.create_word = "word" in outputs
    if unset("output_directory"):
        args.output_directory = spec["output_directory"]
    if unset("max_concurrent_accounts"):
        args.max_concurrent_accounts = spec["max_concurrent_accounts"]
    if unset("account_processing_timeout"):
        args.account_processing_timeout = spec["account_processing_timeout"]
    if unset("disable_parallel_processing") and spec["parallel_processing"] is False:
        args.disable_parallel_processing = True


def load_templates(
    references: List[str], registry: Optional[TemplateRegistry] = None
) -> TemplateRun:
    """Resolve ``--template`` values into a :class:`TemplateRun`."""
    registry = registry or TemplateRegistry()
    by_kind: Dict[str, ResolvedTemplate] = {}
    for reference in references:
        template = registry.resolve(reference)
        if template.kind in by_kind:
            raise TemplateError(
                f"--template given two {template.kind} templates "
                f"('{by_kind[template.kind].name}' and '{template.name}'); "
                "use at most one of each kind"
            )
        by_kind[template.kind] = template

    config = by_kind.get("config")
    report = by_kind.get("report")
    policy = by_kind.get("tag-policy")
    if report is None:
        ref = config.spec["report_template"] if config else DEFAULT_REPORT
        base = config.directory if config else None
        report = _resolve_ref(registry, ref, base, "report", config)
    if policy is None:
        if config and config.spec.get("tag_policy"):
            policy = _resolve_ref(
                registry,
                config.spec["tag_policy"],
                config.directory,
                "tag-policy",
                config,
            )
        elif report.spec.get("tag_policy"):
            policy = _resolve_ref(
                registry,
                report.spec["tag_policy"],
                report.directory,
                "tag-policy",
                report,
            )
    _check_logo(report)
    return TemplateRun(report=report, policy=policy, config=config)


def _check_logo(report: ResolvedTemplate) -> None:
    logo = report.spec.get("logo")
    if not logo:
        return
    file = report.file
    line = file.line_of(("spec", "logo"))
    try:
        path = safe_relative_path(report.directory, logo)
    except ValueError as error:
        raise TemplateError(
            [TemplateIssue(str(error), file.source, line, "spec.logo")]
        ) from None
    if path.suffix.lower() not in LOGO_SUFFIXES:
        raise TemplateError(
            [
                TemplateIssue(
                    "logo must be a PNG, JPEG, GIF or BMP image (Word cannot embed "
                    f"'{path.suffix}' files)",
                    file.source,
                    line,
                    "spec.logo",
                )
            ]
        )
    if not path.is_file():
        raise TemplateError(
            [
                TemplateIssue(
                    f"logo file not found: {path}", file.source, line, "spec.logo"
                )
            ]
        )


def _resolve_ref(registry, reference, base_dir, kind, owner) -> ResolvedTemplate:
    try:
        template = registry.resolve(reference, base_dir=base_dir)
    except TemplateError as error:
        where = f" (referenced by '{owner.name}')" if owner else ""
        raise TemplateError(
            [
                type(i)(f"{i.message}{where}", i.source, i.line, i.field)
                for i in error.issues
            ]
        ) from None
    if template.kind != kind:
        raise TemplateError(
            f"'{reference}' is a {template.kind} template, but a {kind} template is "
            f"needed here" + (f" (referenced by '{owner.name}')" if owner else "")
        )
    return template


def prepare_template_run(
    args, argv: List[str], parser_factory, logger
) -> Optional[TemplateRun]:
    """Load ``--template`` values and apply a config template to ``args``.

    Exits with status 1 and a clear message if a template is invalid.
    """
    if not getattr(args, "template", None):
        return None
    try:
        run = load_templates(args.template)
    except TemplateError as error:
        logger.error("Template problem:")
        for issue in error.issues:
            logger.error(f"  {issue}")
        sys.exit(1)
    if run.config:
        apply_config(run, args, explicit_dests(parser_factory, argv), logger)
    logger.info(f"Using templates: {run.describe()}")
    return run


class TemplatedCloudBOMGenerator(CloudBOMGenerator):
    """``CloudBOMGenerator`` that writes Excel and Word files from templates."""

    def __init__(self, config, run: TemplateRun):
        super().__init__(config)
        self.template_run = run

    def _generate_bom_documents(
        self,
        resources: List[Dict[str, Any]],
        compliance_results: Dict[str, Any],
        output_formats: List[str],
    ) -> Dict[str, Any]:
        run = self.template_run
        generated: List[str] = []
        try:
            session = next(
                (c.session for c in self.account_contexts.values() if c.session), None
            )
            if session is None:
                raise RuntimeError("No valid session available for BOM generation")
            processor = BOMDataProcessor(
                config=self.config.bom_processing_config, session=session
            )
            bom_data = processor.process_inventory_data(resources)
            processed = bom_data.resources
            now = datetime.now(timezone.utc)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            metadata = {"generated_at": now.strftime("%Y-%m-%d %H:%M UTC")}

            if run.policy is not None:
                run.compliance = evaluate(processed, run.policy)
                path = self.output_dir / f"tag_compliance_{stamp}.json"
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(run.compliance.to_dict(), handle, indent=2, default=str)
                generated.append(str(path))

            for fmt in output_formats:
                fmt = fmt.lower()
                if fmt == "excel":
                    path = self.output_dir / f"multi_account_bom_{stamp}.xlsx"
                    render_excel(
                        str(path), processed, run.report, run.compliance, metadata
                    )
                elif fmt == "word":
                    path = self.output_dir / f"multi_account_bom_{stamp}.docx"
                    render_word(
                        str(path), processed, run.report, run.compliance, metadata
                    )
                else:
                    self.logger.warning(
                        f"Output format '{fmt}' is not supported with "
                        "--template; skipped"
                    )
                    continue
                generated.append(str(path))

            return {
                "success": True,
                "generated_files": generated,
                "total_resources": len(processed),
                "processing_statistics": bom_data.processing_statistics,
                "generation_timestamp": now.isoformat(),
                "templates": run.describe(),
            }
        except Exception as error:  # report, like the base class does
            self.logger.error(f"BOM document generation failed: {error}")
            raise
