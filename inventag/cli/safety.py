"""
CLI-level safety wiring: process hardening, the read-only guard, flags that
are not implemented, ``--validate-operations`` and ``--audit-output``.

Kept separate from :mod:`inventag.cli.main` so the argument parser and the BOM
flow stay readable.
"""

import json
import logging
import os
import re
from typing import List, Optional, Tuple

from ..security.read_only_guard import ReadOnlyGuard, install_global_guard
from ..security.redaction import install_log_record_redaction
from ..security.safe_output import ensure_private_dir, open_private
from pathlib import Path

from .errors import UsageError

# Exit code for flags that are recognised but refused (argparse also uses 2
# for usage errors).
EXIT_NOT_IMPLEMENTED = 2

_BUILTIN_TEMPLATES = Path(__file__).resolve().parent.parent / "templating" / "builtin"

# --compliance-standard value -> (label for the message, template name).
# InvenTag does not assess or certify any framework: the template named here
# only checks tag evidence.
_STANDARD_TEMPLATES = {
    "soc2": ("SOC 2", "evidence-soc2"),
    "pci": ("PCI DSS", "evidence-pci-dss"),
    "hipaa": ("HIPAA", "evidence-hipaa"),
    "gdpr": ("GDPR", "evidence-gdpr"),
    "pdpa": ("PDPA", "evidence-pdpa"),
    "general": (None, "security-baseline"),
}
_FALLBACK_TEMPLATE = "security-baseline"


def _compliance_standard_error(args) -> UsageError:
    value = str(args.compliance_standard)
    label, template = _STANDARD_TEMPLATES.get(
        value.lower(), (value, _FALLBACK_TEMPLATE)
    )
    if not (_BUILTIN_TEMPLATES / f"{template}.yaml").is_file():
        template = _FALLBACK_TEMPLATE
    if label:
        what = (
            f"InvenTag does not assess or certify {label} compliance, and this "
            "option never changed what it does"
        )
        purpose = f"check the tags that support a {label} scoping conversation"
    else:
        what = (
            "InvenTag does not assess compliance, and this option never "
            "changed what it does"
        )
        purpose = "check your tags against the built-in baseline"
    return UsageError(
        f"--compliance-standard {value}",
        what,
        f"to {purpose} (tag evidence only), run: inventag --template "
        f"{template} --create-excel. Read what it checks with: inventag "
        f"templates show {template}",
        "templates/catalogue",
    )


def _disable_production_safety_error(args) -> UsageError:
    return UsageError(
        "--disable-production-safety",
        "InvenTag has no mode without the read-only guard",
        "remove this option and run the command again. To see whether a call is "
        "allowed, run: inventag --validate-operations ec2:DescribeInstances",
        "guides/read-only-access",
        why="InvenTag needs only read access and never changes your account, so "
        "there is nothing to turn off.",
    )


# (flag, predicate on args, builder of the UsageError)
REFUSED = (
    (
        "--compliance-standard",
        lambda a: getattr(a, "compliance_standard", None) is not None,
        _compliance_standard_error,
    ),
    (
        "--disable-production-safety",
        lambda a: getattr(a, "disable_production_safety", False),
        _disable_production_safety_error,
    ),
)


def unimplemented_flag_errors(args) -> List[UsageError]:
    """One error for each refused flag on the command line."""
    return [build(args) for _flag, used, build in REFUSED if used(args)]


def harden_process() -> None:
    """Owner-only default permissions and log redaction for this process.

    Reports, state snapshots and logs describe the scanned accounts, so every
    file the CLI creates is 0600 and every directory 0700 by default.
    """
    os.umask(0o077)
    install_log_record_redaction()


def enable_read_only_guard() -> ReadOnlyGuard:
    """Install the read-only guard for every AWS client created from now on."""
    guard = install_global_guard()
    logging.getLogger(__name__).info(
        "Read-only guard enabled: non-read AWS API calls will be blocked"
    )
    return guard


_OPERATION_RE = re.compile(r"^([a-z0-9-]+):([A-Za-z0-9_]+)$")


def _to_operation_name(name: str) -> str:
    """Accept PascalCase (DescribeInstances) or snake_case (describe_instances)."""
    if "_" in name or name[:1].islower():
        return "".join(part[:1].upper() + part[1:] for part in name.split("_"))
    return name


def validate_operations(
    operations: List[str], guard: Optional[ReadOnlyGuard] = None
) -> Tuple[bool, List[str]]:
    """Check ``service:Operation`` strings against the read-only policy.

    Returns ``(all_allowed, report_lines)``. Malformed entries count as not
    allowed.
    """
    guard = guard or ReadOnlyGuard()
    lines = []
    all_allowed = True
    for entry in operations:
        match = _OPERATION_RE.match(entry.strip())
        if not match:
            lines.append(
                f"INVALID  {entry}: expected service:Operation, for example "
                "ec2:DescribeInstances"
            )
            all_allowed = False
            continue
        service, operation = match.group(1), _to_operation_name(match.group(2))
        allowed, reason = guard.evaluate(service, operation)
        all_allowed = all_allowed and allowed
        status = "ALLOWED" if allowed else "BLOCKED"
        lines.append(f"{status}  {service}:{operation} ({reason})")
    return all_allowed, lines


def write_audit_output(guard: Optional[ReadOnlyGuard], path: str) -> str:
    """Write the guard's audit summary as JSON (owner-only file)."""
    report = (
        guard.audit_report()
        if guard is not None
        else {"read_only_enforced": False, "operations": []}
    )
    output_path = Path(path)
    ensure_private_dir(output_path.parent)
    with open_private(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return str(output_path)
