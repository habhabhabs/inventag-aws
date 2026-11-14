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

from ..security.read_only_guard import (
    DENIED_PARAMETERS,
    ReadOnlyGuard,
    install_global_guard,
)
from ..security.redaction import install_log_record_redaction
from ..security.safe_output import ensure_private_dir, open_private
from pathlib import Path

# Exit code for flags that are recognised but not implemented (argparse also
# uses 2 for usage errors).
EXIT_NOT_IMPLEMENTED = 2

# flag -> (predicate on args, message)
_NOT_IMPLEMENTED = (
    (
        "--compliance-standard",
        lambda a: getattr(a, "compliance_standard", None) is not None,
        "Compliance-standard enforcement is not implemented yet; the option "
        "has never changed InvenTag's behaviour.",
    ),
    (
        "--disable-production-safety",
        lambda a: getattr(a, "disable_production_safety", False),
        "The read-only guard cannot be disabled from the CLI: InvenTag only "
        "needs read access, so non-read AWS calls are always blocked.",
    ),
)


def unimplemented_flag_errors(args) -> List[str]:
    """Messages for each flag on the command line that does nothing yet."""
    return [
        f"{flag}: {message}" for flag, used, message in _NOT_IMPLEMENTED if used(args)
    ]


def unusable_path_error(option: str, path: str, folder: bool) -> Optional[str]:
    """A message when ``path`` cannot be written, else None.

    Looks only: nothing is created. ``folder`` is True for an output folder
    and False for a file (its parent folder is checked). The nearest existing
    parent must be a folder that the user may write to.
    """
    target = Path(path) if folder else Path(path).parent
    if not folder and Path(path).is_dir():
        return f"{option}: '{path}' is a folder; give a file name."
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not probe.exists():
        return None  # cannot tell; the later write reports it
    if not probe.is_dir():
        return (
            f"{option}: cannot write to '{path}', because '{probe}' is a file, "
            "not a folder. Give a path in a folder that exists or can be created."
        )
    if not os.access(probe, os.W_OK | os.X_OK):
        return (
            f"{option}: cannot write to '{path}', because you may not write in "
            f"'{probe}'. Give a path in a folder you can write to."
        )
    return None


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
            lines.append(f"INVALID  {entry}: expected service:Operation")
            all_allowed = False
            continue
        service, operation = match.group(1), _to_operation_name(match.group(2))
        allowed, reason = guard.evaluate(service, operation)
        all_allowed = all_allowed and allowed
        status = "ALLOWED" if allowed else "BLOCKED"
        line = f"{status}  {service}:{operation} ({reason})"
        if allowed:
            # Allowed by name, but blocked with a parameter that returns secrets.
            rules = DENIED_PARAMETERS.get((service, operation), {})
            blocked = [
                f"{parameter}={value}"
                for parameter, values in rules.items()
                for value in sorted(values)
            ]
            if blocked:
                line += "; BLOCKED when " + ", ".join(blocked)
        lines.append(line)
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
