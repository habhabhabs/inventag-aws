"""``inventag templates`` - list, show, init and validate templates.

The main ``inventag`` command is flag-based, so ``templates`` is handled as a
word before the flags: ``inventag templates list``. Everything else on the
command line keeps working as before.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, TextIO

import yaml

from ..cli.config_validator import ConfigValidator
from ..cli.errors import InventagArgumentParser, UsageError, emit
from .errors import TemplateError
from .loader import load_template_file
from .registry import TemplateRegistry, search_dirs
from .runner import detect_old_layout, load_templates, usage_errors_for
from .schema import KINDS, NAME_PATTERN

TEMPLATES_PAGE = "reference/cli#templates-subcommands"


class _TemplatesParser(InventagArgumentParser):
    """Parser of ``inventag templates``; its errors point at its docs."""

    docs_page = TEMPLATES_PAGE


EPILOG = """\
Search order (first match wins):
  1. folders in $INVENTAG_TEMPLATE_PATH
  2. ./.inventag/templates/
  3. $XDG_CONFIG_HOME/inventag/templates/ (default ~/.config/inventag/templates/)
  4. built-in templates

Examples:
  inventag templates list
  inventag templates show executive-summary
  inventag templates init standard-bom --output .inventag/templates/acme-bom.yaml
  inventag templates validate .inventag/templates/acme-bom.yaml
  inventag --template acme-bom --create-excel --create-word
"""


def build_parser() -> argparse.ArgumentParser:
    parser = _TemplatesParser(
        prog="inventag templates",
        description="Work with InvenTag templates: report layouts, tag policies "
        "and run settings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    p = sub.add_parser("list", help="List the templates you can use")
    p.add_argument("--kind", choices=KINDS, help="Only show one kind")
    p.add_argument(
        "--all",
        action="store_true",
        help="Also show templates hidden by another of the same name",
    )

    p = sub.add_parser("show", help="Print a template")
    p.add_argument("template", metavar="NAME|PATH")
    p.add_argument(
        "--resolved",
        action="store_true",
        help="Print the result after 'extends' is applied and defaults are filled in",
    )

    p = sub.add_parser(
        "init",
        help="Copy a template into your project so you can adapt it",
        description="Copy a template into your project so you can adapt it. "
        "By default the file is a full copy. With --extend it is a short file "
        "that inherits everything and lets you override only what you change.",
    )
    p.add_argument("template", metavar="NAME|PATH")
    p.add_argument(
        "--output",
        "-o",
        help="File to write, or a folder (the file is then <name>.yaml). "
        "Default: ./<name>.yaml in the current folder",
    )
    p.add_argument(
        "--name", help="Name for the new template (default: from the file name)"
    )
    p.add_argument(
        "--extend",
        action="store_true",
        help="Write a short file that extends the template",
    )
    p.add_argument("--force", action="store_true", help="Overwrite an existing file")

    p = sub.add_parser("validate", help="Check template files and report problems")
    p.add_argument("templates", nargs="+", metavar="NAME|PATH")
    return parser


def _cmd_list(args, registry: TemplateRegistry, out: TextIO) -> int:
    rows = []
    for entry in registry.entries():
        if entry.shadowed_by and not args.all:
            continue
        try:
            data = load_template_file(entry.path, entry.origin).data
            kind = str(data.get("kind", "?"))
            description = str(data.get("description", "")).strip()
        except TemplateError:
            kind, description = (
                "?",
                "(cannot be read; run 'inventag templates validate')",
            )
        if args.kind and kind != args.kind:
            continue
        note = f" (hidden by {entry.shadowed_by.path})" if entry.shadowed_by else ""
        rows.append((entry.name, kind, entry.origin, description + note))
    if not rows:
        out.write("No templates found.\n")
        return 0
    rows.sort(key=lambda r: (KINDS.index(r[1]) if r[1] in KINDS else 9, r[0]))
    widths = [
        max(len(r[i]) for r in rows + [("NAME", "KIND", "SOURCE", "")])
        for i in range(3)
    ]
    out.write(
        f"{'NAME':<{widths[0]}}  {'KIND':<{widths[1]}}  "
        f"{'SOURCE':<{widths[2]}}  DESCRIPTION\n"
    )
    for name, kind, origin, description in rows:
        out.write(
            f"{name:<{widths[0]}}  {kind:<{widths[1]}}  "
            f"{origin:<{widths[2]}}  {description}\n"
        )
    out.write("\nSearch order (first match wins):\n")
    for index, directory in enumerate(registry.dirs, 1):
        exists = "" if directory.path.is_dir() else "  (not created)"
        out.write(f"  {index}. {directory.origin:<8} {directory.path}{exists}\n")
    return 0


def _cmd_show(args, registry: TemplateRegistry, out: TextIO) -> int:
    if args.resolved:
        template = registry.resolve(args.template)
        chain = " -> ".join(t.source for t in template.chain)
        out.write(f"# Resolved from: {chain}\n")
        data = {
            "format_version": 1,
            "kind": template.kind,
            "name": template.name,
            "description": template.description,
            "spec": _drop_nulls(template.spec),
        }
        out.write(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88))
        return 0
    template = registry.load(args.template)
    out.write(f"# Source: {template.source}\n")
    out.write(template.text if template.text.endswith("\n") else template.text + "\n")
    return 0


def _drop_nulls(value):
    if isinstance(value, dict):
        return {k: _drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_nulls(v) for v in value]
    return value


def _derive_name(output: Path, explicit: Optional[str]) -> str:
    return explicit or output.stem


def _cmd_init(args, registry: TemplateRegistry, out: TextIO, err: TextIO) -> int:
    source = registry.load(args.template)
    resolved = registry.resolve_file(source)
    target = args.output or "."
    output = Path(target).expanduser()
    if output.is_dir() or target.endswith(("/", "\\")):
        name = args.name or f"my-{resolved.name}"
        output = output / f"{name}.yaml"
    name = _derive_name(output, args.name)
    if not NAME_PATTERN.fullmatch(name):
        return _stop(
            err,
            UsageError(
                None,
                f"'{name}' is not a valid template name: use lower-case letters, "
                "digits and hyphens",
                "choose a file name such as acme-bom.yaml, or pass --name acme-bom.",
                "templates/reference#fields-in-every-template",
            ),
        )
    if output.suffix not in (".yaml", ".yml"):
        return _stop(
            err,
            UsageError(
                "--output",
                "must end in .yaml or .yml, or be a folder",
                "for example --output .inventag/templates/acme-bom.yaml",
                TEMPLATES_PAGE,
            ),
        )
    if output.exists() and not args.force:
        return _stop(
            err,
            UsageError(
                str(output),
                "already exists",
                "add --force to overwrite it, or choose another file with --output.",
                TEMPLATES_PAGE,
                code=1,
            ),
        )

    reference = resolved.name if source.origin != "file" else source.source
    if args.extend:
        text = (
            "# Inherits everything from '{ref}'. Add only what you want to change.\n"
            "# See: inventag templates show {ref} --resolved\n"
            "format_version: 1\n"
            "kind: {kind}\n"
            "name: {name}\n"
            'description: "Adapted from {parent}"\n'
            "extends: {ref}\n"
            "spec: {{}}\n"
        ).format(ref=reference, kind=resolved.kind, name=name, parent=resolved.name)
    elif not source.data.get("extends"):
        # Keep the comments: copy the text and change only the name.
        text, count = re.subn(
            r"^name:.*$", f"name: {name}", source.text, count=1, flags=re.MULTILINE
        )
        if count == 0:
            text = f"name: {name}\n" + source.text
    else:
        data = dict(resolved.data)
        data.pop("extends", None)
        data["name"] = name
        text = (
            f"# Copied from '{resolved.name}' with 'extends' applied.\n"
            + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88)
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    # Prove the new file is valid before telling the user it is.
    registry.resolve_file(load_template_file(output))
    out.write(f"Created {output} (kind: {resolved.kind}, name: {name}).\n")
    out.write(f"Next: edit it, then run 'inventag templates validate {output}'.\n")
    return 0


def _stop(err: TextIO, *errors: UsageError) -> int:
    """Print the errors on ``err`` and return their exit code (2 beats 1)."""
    emit(errors, err)
    return max(e.code for e in errors)


def _validate_one(reference: str, registry: TemplateRegistry, out: TextIO) -> bool:
    try:
        template = registry.resolve(reference)
        warnings = []
        file = template.file
        if file.path is not None and file.path.stem != template.name:
            warnings.append(
                f"{file.source}: name '{template.name}' does not match the file name "
                f"'{file.path.stem}'; 'inventag --template {file.path.stem}' will find "
                "the file, but listings show the file name"
            )
        # Check references (report_template, tag_policy) resolve and fit.
        load_templates([str(file.path) if file.path else reference], registry)
        if template.kind == "config" and template.spec.get("accounts"):
            _check_accounts(template, warnings)
    except TemplateError as error:
        for issue in detect_old_layout(error).issues:
            out.write(f"ERROR {issue}\n")
        return False
    for warning in warnings:
        out.write(f"WARNING {warning}\n")
    out.write(f"OK    {template.source} ({template.kind} '{template.name}')\n")
    return True


def _check_accounts(template, warnings: List[str]) -> None:
    """Run the same account checks the main CLI uses for --accounts-file."""
    validator = ConfigValidator()
    for index, account in enumerate(template.spec["accounts"]):
        for problem in validator._validate_account_config(
            {k: v for k, v in account.items() if v is not None}, index
        ):
            raise TemplateError(f"{template.source}: spec.accounts: {problem}")
    placeholders = [
        a["account_id"]
        for a in template.spec["accounts"]
        if len(set(a["account_id"])) == 1
    ]
    if placeholders:
        warnings.append(
            f"{template.source}: account IDs {', '.join(placeholders)} look like "
            "placeholders; replace them with your own"
        )


def main(
    argv: Optional[List[str]] = None, out: TextIO = None, err: TextIO = None
) -> int:
    out = out or sys.stdout
    err = err or sys.stderr
    args = build_parser().parse_args(argv)
    registry = TemplateRegistry(search_dirs())
    try:
        if args.command == "list":
            return _cmd_list(args, registry, out)
        if args.command == "show":
            return _cmd_show(args, registry, out)
        if args.command == "init":
            return _cmd_init(args, registry, out, err)
        if args.command == "validate":
            results = [_validate_one(ref, registry, out) for ref in args.templates]
            if all(results):
                return 0
            bad = results.count(False)
            return _stop(
                err,
                UsageError(
                    None,
                    f"{bad} of {len(results)} template(s) are not valid; the ERROR "
                    "lines above say where",
                    "fix the lines named, then run the same command again.",
                    "templates/reference#validation-messages",
                    code=1,
                ),
            )
    except TemplateError as error:
        return _stop(err, *usage_errors_for(detect_old_layout(error)))
    return 2
