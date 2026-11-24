"""``inventag policy``: validate, list, schema, test, check, explain, lock.

Like ``inventag templates`` the group is a word before the flags, handled by
:func:`main`, which takes the arguments after the word and returns the exit
code. Everything works offline on a saved snapshot (no AWS call). The
evaluation is :mod:`inventag.policy.engine`; fixtures run through
:mod:`inventag.policy.testing`.

Exit codes (v15-policy-spec.md section 4): 0; 1 a policy, set, waiver, lock or
snapshot file is not valid or cannot be read; 2 invalid options; 7 a ``fail``
at or above ``--fail-on``; 8 ``--fail-on-not-evaluated`` and something could
not be evaluated (8 wins over 7). ``validate``, ``list``, ``schema``,
``explain``: 0 or 1. ``test``, ``lock``: 0 or 1.

Interfaces of other packages, called only when the command needs them and
looked up by name (a missing module is an exit code 1 with a clear text):

* ``inventag.policy.waivers.apply`` (P2), through the engine;
* ``inventag.policy.baseline.evaluate_policy`` (P2), through the engine;
* ``inventag.policy.lock.write(root) -> Path`` and ``verify(root) -> [problem]``
  (P2);
* ``inventag.policy.outputs.render(result, fmt, show_values=, fail_on=,
  thresholds=) -> str`` for ``text``, ``sarif``, ``junit`` (P3's ``xml``)
  and ``markdown`` (P3's ``md``). The JSON file is written here
  with :func:`inventag.policy.engine.dumps`.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TextIO, Tuple

from ..exit_codes import EXIT_ERROR, EXIT_OK, EXIT_USAGE
from ..security import safe_output
from ..templating.errors import TemplateIssue
from . import engine, loader, model, testing
from .schema import PolicyError, parse_date

DEFAULT_FOLDER = ".inventag/policies"
FORMATS = ("text", "json", "sarif", "junit", "markdown")
EXTENSIONS = {"json": "json", "sarif": "sarif", "junit": "xml", "markdown": "md"}
TRIM = 12  # hex digits of a digest in ``list``
DEFAULT_FORMATS = "text"

EPILOG = f"""\
Exit codes of 'check': 0 evaluated; 1 a file is not valid or cannot be read;
2 invalid options; 7 a fail at or above --fail-on; 8 --fail-on-not-evaluated
and something could not be evaluated (8 wins over 7).

Examples:
  inventag policy validate {DEFAULT_FOLDER}
  inventag policy test {DEFAULT_FOLDER}
  inventag policy check --snapshot state/state_20261120_000000.json --fail-on high
  inventag policy explain TAG-002 --snapshot state/state_20261120_000000.json
  inventag policy lock
"""


class CliError(Exception):
    """A problem to print as ``error: ...`` lines, with the exit code."""

    def __init__(self, code: int, *lines: str):
        super().__init__("\n".join(lines))
        self.code = code
        self.lines = lines


# --------------------------------------------------------------- field help
# (where, text) per field name; the wording follows v15-policy-spec.md 2 and 9.
FIELD_HELP: Dict[str, Tuple[str, str]] = {
    "format_version": ("file header", "Always 1. Required."),
    "kind": (
        "file header",
        f"What the file holds: {', '.join(model.KINDS)}. Required.",
    ),
    "name": (
        "file header",
        "Lower-case letters, digits and hyphens, at most 63 characters. Required.",
    ),
    "description": ("file header", "Free text. Optional."),
    "id": (
        "spec.id",
        "Stable identity of a policy, for example RDS-001: capital letters, a "
        "hyphen, 3 to 5 digits. Unique in a run. Required.",
    ),
    "severity": (
        "spec.severity",
        f"One of: {', '.join(model.SEVERITIES)} (info is the lowest). Required.",
    ),
    "version": (
        "spec.version",
        "Integer, 1 or more, default 1. Raise it when the meaning changes; it "
        "is written into every finding.",
    ),
    "resource": (
        "spec.resource",
        "Which rows the policy looks at: services, resource_types, "
        "exclude_resource_types, regions, accounts, filters, listings. Default: all rows.",
    ),
    "check": (
        "spec.check",
        "A list of 1 to 20 entries; every entry must hold. An entry is a check "
        f"type ({', '.join(model.CHECK_TYPES)}), a tag shorthand such as "
        '"tag:Owner": present, or and/or/not. Required.',
    ),
    "require": (
        "spec.require",
        "Keys (JMESPath) that must exist on a selected row; an absent key "
        "gives not evaluated (field_missing) instead of a verdict.",
    ),
    "message": (
        "spec.message",
        "Text of a finding, at most 300 characters. Placeholders: {name} "
        "{resource} {account} {region} {service} {resource_type} {policy}.",
    ),
    "references": (
        "spec.references",
        "Up to 10 URLs or texts; the first URL is the SARIF help address.",
    ),
    "enabled": (
        "spec.enabled",
        "true or false, default true. false: listed, not evaluated, not counted.",
    ),
    "services": ("spec.resource", "Row service labels, case-insensitive."),
    "resource_types": ("spec.resource", "Row resource types, case-insensitive."),
    "exclude_resource_types": (
        "spec.resource",
        "Resource types removed after services and resource_types.",
    ),
    "regions": (
        "spec.resource; check type allowed-regions",
        "Row regions. 'global' must be named to select global rows.",
    ),
    "accounts": ("spec.resource", "12-digit account IDs."),
    "listings": (
        "spec.resource",
        "Discovery service keys of the listings whose failure makes the policy "
        "report a unit not read; where given, they replace the service label "
        "mapping for the unit lines of this policy.",
    ),
    "filters": (
        "spec.resource",
        "Filter entries that must all hold; a filter that cannot be decided "
        "gives not evaluated.",
    ),
    "type": (
        "check entry",
        f"The check type: {', '.join(model.CHECK_TYPES)}.",
    ),
    "key": (
        "check entry (type value)",
        "A JMESPath expression over the row, at most 200 characters; "
        "tags.<Key> and tag:<Key> read tags. A key with no result is absent.",
    ),
    "op": (
        "check entry (type value)",
        f"One of: {', '.join(model.OPERATORS)}. Default eq.",
    ),
    "value": (
        "check entry (type value)",
        "What to compare with. Special words with eq: "
        f"{', '.join(model.SPECIAL_VALUES)}.",
    ),
    "value_type": (
        "check entry (type value)",
        f"Conversion before comparing: {', '.join(model.VALUE_TYPES)}.",
    ),
    "keys": (
        "check type required-tags",
        "List of {key, allowed_values, case_sensitive, pattern}; every key "
        "must be present and pass.",
    ),
    "policy": (
        "check type required-tags",
        "Name of a tag policy whose required_tags are used.",
    ),
    "use_scope": (
        "check type required-tags",
        "true: also apply the tag policy's own scope. Default false.",
    ),
    "missing_only": (
        "check type required-tags",
        "true: fail a row only for missing keys. Default false.",
    ),
    "allow_global": (
        "check type allowed-regions",
        "true or false, default true: a global row passes.",
    ),
    "pattern": (
        "check type name-pattern",
        "Python regular expression, full match, case-sensitive.",
    ),
    "field": (
        "check type name-pattern",
        "The name (default) or a JMESPath key of the field to match.",
    ),
    "change": (
        "check type baseline",
        "A non-empty subset of added, removed, modified. Needs --baseline.",
    ),
    "attributes": (
        "check type baseline",
        "Keys that count for modified; only with modified.",
    ),
    "rows": (
        "check type related",
        "Which other rows are looked at; the fields of resource, no filters.",
    ),
    "their_key": (
        "check type related",
        "On the other row: a string or a list of strings that names this row.",
    ),
    "my_key": ("check type related", "On this row: the string the other rows name."),
    "listing": (
        "check type related",
        "Discovery service key of the listing that gives the related rows.",
    ),
    "expect": (
        "check type related",
        "any (at least one row names this row) or none (no row names it).",
    ),
    "policies": (
        "kind policy-set",
        "A policy name, or a path relative to the file that stays inside the "
        "policy folder.",
    ),
    "include": ("kind policy-set", "Names of other sets."),
    "severity_overrides": (
        "kind policy-set",
        "Mapping of policy id to severity; recorded as severity_overridden_by.",
    ),
    "waivers": (
        "kind waivers",
        "List of {policy, resource, account, reason, approved_by, expires}. "
        "A waiver turns a fail into waived until the end of the UTC day of "
        "expires (at most 366 days ahead).",
    ),
}


def json_schema() -> Dict[str, Any]:
    """A JSON Schema (draft 2020-12) for editors: the file headers and the
    fields of the three kinds. It is looser than the validator (the validator
    is the authority); check entries are only typed by ``type``."""
    text = {"type": "string"}
    entry = {
        "type": "object",
        "properties": {"type": {"enum": list(model.CHECK_TYPES)}},
    }
    resource = {
        "type": "object",
        "properties": {
            "services": {"type": "array", "items": text},
            "resource_types": {"type": "array", "items": text},
            "exclude_resource_types": {"type": "array", "items": text},
            "regions": {"type": "array", "items": text},
            "accounts": {"type": "array", "items": {"type": "string"}},
            "filters": {"type": "array", "items": entry},
            "listings": {"type": "array", "items": text},
        },
        "additionalProperties": False,
    }
    policy_spec = {
        "type": "object",
        "required": ["id", "severity", "check"],
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string", "pattern": "^[A-Z][A-Z0-9]{1,7}-[0-9]{3,5}$"},
            "severity": {"enum": list(model.SEVERITIES)},
            "version": {"type": "integer", "minimum": 1},
            "resource": resource,
            "check": {
                "type": "array",
                "minItems": 1,
                "maxItems": model.LIMITS.checks_per_policy,
                "items": entry,
            },
            "require": {"type": "array", "minItems": 1, "items": text},
            "message": {"type": "string", "maxLength": model.LIMITS.message_length},
            "references": {
                "type": "array",
                "maxItems": model.LIMITS.references,
                "items": text,
            },
            "enabled": {"type": "boolean"},
        },
    }
    set_spec = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "policies": {"type": "array", "items": text},
            "include": {"type": "array", "items": text},
            "severity_overrides": {
                "type": "object",
                "additionalProperties": {"enum": list(model.SEVERITIES)},
            },
        },
    }
    waivers_spec = {
        "type": "object",
        "required": ["waivers"],
        "additionalProperties": False,
        "properties": {
            "waivers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "policy",
                        "resource",
                        "reason",
                        "approved_by",
                        "expires",
                    ],
                    "additionalProperties": False,
                    "properties": {
                        "policy": text,
                        "resource": text,
                        "account": text,
                        "reason": {"type": "string", "minLength": 10, "maxLength": 300},
                        "approved_by": text,
                        "expires": {"type": ["string", "null"]},
                    },
                },
            }
        },
    }
    kinds = {"policy": policy_spec, "policy-set": set_spec, "waivers": waivers_spec}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:inventag:policy-file:1",
        "title": "InvenTag policy, policy set or waivers file",
        "type": "object",
        "required": ["format_version", "kind", "name", "spec"],
        "properties": {
            "format_version": {"const": 1},
            "kind": {"enum": list(model.KINDS)},
            "name": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{0,62}$"},
            "description": text,
            "spec": {"type": "object"},
        },
        "additionalProperties": False,
        "allOf": [
            {
                "if": {"properties": {"kind": {"const": kind}}, "required": ["kind"]},
                "then": {"properties": {"spec": spec}},
            }
            for kind, spec in kinds.items()
        ],
    }


# ------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inventag policy",
        description="Governance as code: check a saved snapshot against "
        "policies. InvenTag reads; a policy has no actions. No AWS call is made.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    def policies_option(p):
        p.add_argument(
            "--policies",
            nargs="+",
            metavar="PATH",
            help=f"Policy files or folders (default: {DEFAULT_FOLDER})",
        )

    def set_option(p):
        p.add_argument(
            "--set",
            metavar="NAME",
            help="Only the policies of this set: a set in the given paths, "
            "else a shipped set",
        )

    def now_option(p):
        p.add_argument(
            "--now",
            metavar="DATE",
            help="The date to use, YYYY-MM-DD (default: today, UTC)",
        )

    p = sub.add_parser(
        "validate", help="Check policy, set and waiver files for problems"
    )
    p.add_argument("paths", nargs="+", metavar="PATH", help="Files or folders")
    now_option(p)

    p = sub.add_parser("list", help="List policies: id, severity, version, digest")
    policies_option(p)
    set_option(p)
    p.add_argument(
        "--shipped",
        action="store_true",
        help="List the policy sets shipped with InvenTag",
    )

    p = sub.add_parser(
        "schema", help="Describe the fields of the files, or print a JSON Schema"
    )
    p.add_argument("field", nargs="?", metavar="FIELD", help="A field name")
    p.add_argument(
        "--json", action="store_true", help="Print a JSON Schema for editors"
    )

    p = sub.add_parser("test", help="Run the fixtures under tests/<policy>/")
    p.add_argument(
        "dir",
        nargs="?",
        metavar="DIR",
        default=DEFAULT_FOLDER,
        help=f"Policy folder (default: {DEFAULT_FOLDER})",
    )

    p = sub.add_parser(
        "check",
        help="Evaluate policies on a snapshot and write the result",
        description="Evaluate policies on a saved snapshot and write the "
        "result files. The command reports and exits 0 unless --fail-on or "
        "--fail-on-not-evaluated is given.",
    )
    p.add_argument("--snapshot", required=True, metavar="FILE", help="State file")
    policies_option(p)
    set_option(p)
    p.add_argument("--waivers", metavar="FILE", help="A waivers file")
    p.add_argument(
        "--baseline", metavar="FILE", help="An older state file, for baseline checks"
    )
    p.add_argument(
        "--fail-on",
        choices=model.SEVERITIES,
        metavar="SEVERITY",
        help="Exit 7 when a fail has this severity or a higher one "
        f"({', '.join(model.SEVERITIES)})",
    )
    p.add_argument(
        "--fail-on-not-evaluated",
        action="store_true",
        help="Exit 8 when something could not be evaluated",
    )
    p.add_argument(
        "--format",
        default=DEFAULT_FORMATS,
        metavar="LIST",
        help=f"Comma-separated: {', '.join(FORMATS)} (default: {DEFAULT_FORMATS}). "
        "text goes to the screen, the others to files",
    )
    p.add_argument(
        "--output-directory",
        default=".",
        metavar="DIR",
        help="Folder for the result files (default: the current folder)",
    )
    now_option(p)
    p.add_argument(
        "--locked",
        action="store_true",
        help="Refuse a policy file that differs from policy.lock",
    )
    p.add_argument(
        "--show-values",
        action="store_true",
        help="Show the values that failed a check (masked values stay masked)",
    )

    p = sub.add_parser("explain", help="Show how one policy decided each row")
    p.add_argument("policy", metavar="POLICY", help="Policy id or name")
    p.add_argument("--snapshot", required=True, metavar="FILE", help="State file")
    policies_option(p)
    set_option(p)
    p.add_argument(
        "--baseline", metavar="FILE", help="An older state file, for baseline checks"
    )
    p.add_argument("--resource", metavar="ARN", help="Only this resource")
    now_option(p)
    p.add_argument(
        "--show-values",
        action="store_true",
        help="Show the values that failed a check (masked values stay masked)",
    )

    p = sub.add_parser("lock", help="Write or check policy.lock")
    p.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        default=DEFAULT_FOLDER,
        help=f"Policy folder (default: {DEFAULT_FOLDER})",
    )
    p.add_argument(
        "--check", action="store_true", help="Only check that policy.lock is current"
    )
    return parser


# ----------------------------------------------------------------- helpers
# the command's format names -> P3's writer names
WRITER_FORMATS = {"text": "text", "sarif": "sarif", "junit": "xml", "markdown": "md"}


def _thresholds(args) -> List[str]:
    """The thresholds set on the command line, for the exit sentence (11.3)."""
    names = []
    if args.fail_on:
        names.append("fail_on")
    if args.fail_on_not_evaluated:
        names.append("fail_on_not_evaluated")
    return names


def _module(name: str, message: str):
    """``inventag.policy.<name>``, or a clear error when it is not installed."""
    full = f"inventag.policy.{name}"
    try:
        return importlib.import_module(full)
    except ModuleNotFoundError as error:
        if error.name != full:
            raise
        raise CliError(EXIT_ERROR, message) from None


def _lock_module(what: str):
    return _module(
        "lock", f"{what}: inventag.policy.lock is not installed in this build."
    )


def _issue_lines(error: PolicyError) -> List[str]:
    return [str(i) for i in error.issues]


def _now(args) -> dt.datetime:
    text = getattr(args, "now", None)
    if text is None:
        today = dt.datetime.now(dt.timezone.utc).date()
    else:
        today = parse_date(text)
        if today is None:
            raise CliError(
                EXIT_USAGE, f"--now: '{text}' is not a date; write YYYY-MM-DD."
            )
    return dt.datetime(today.year, today.month, today.day, tzinfo=dt.timezone.utc)


def _policy_paths(args, hint: str) -> List[Path]:
    if args.policies:
        return [Path(p) for p in args.policies]
    folder = Path(DEFAULT_FOLDER)
    if not folder.is_dir():
        raise CliError(
            EXIT_ERROR, f"policy folder {DEFAULT_FOLDER} does not exist; {hint}."
        )
    return [folder]


def _load(args, hint: str = "give --policies PATH") -> loader.Loaded:
    try:
        return loader.load(_policy_paths(args, hint))
    except PolicyError as error:
        raise CliError(EXIT_ERROR, *_issue_lines(error)) from None


def _shipped():
    """The shipped-sets module (P5), or None when this build has none."""
    try:
        return importlib.import_module("inventag.policy.builtin")
    except ModuleNotFoundError as error:
        if error.name != "inventag.policy.builtin":
            raise
        return None


def _shipped_names() -> Tuple[str, ...]:
    module = _shipped()
    return tuple(module.SET_NAMES) if module else ()


def _select(args, err: TextIO) -> List[model.Policy]:
    """The policies to use: all loaded ones, or those of ``--set``.

    A set is looked up in the given paths first, then among the shipped sets;
    a local set with a shipped set's name wins and one note says so (spec 11.7).
    """
    wanted = getattr(args, "set", None)
    folder = Path(DEFAULT_FOLDER)
    if not args.policies and not folder.is_dir() and wanted:
        loaded = None
    else:
        loaded = _load(args)
    if not wanted:
        return list(loaded.policies)
    local = {s.name for s in loaded.sets} if loaded else set()
    shipped = _shipped_names()
    if wanted in local:
        if wanted in shipped:
            err.write(
                f"note: the policy set '{wanted}' in your files hides the "
                "shipped set of the same name.\n"
            )
        ids = {p.id for p in _set_members(loaded, wanted)}
        return [p for p in loaded.policies if p.id in ids]
    if wanted in shipped:
        try:
            return list(_shipped().load_set(wanted))
        except PolicyError as error:
            raise CliError(EXIT_ERROR, *_issue_lines(error)) from None
    raise CliError(
        EXIT_ERROR,
        f"no policy set named '{wanted}'; run 'inventag policy list' and "
        "'inventag policy list --shipped' to see the sets.",
    )


def _read_snapshot(option: str, path: str) -> Tuple[Dict[str, Any], str]:
    name = Path(path).name

    def fail(problem: str) -> CliError:
        return CliError(
            EXIT_ERROR,
            f"{option} {name}: {problem}; give a state file that InvenTag wrote.",
        )

    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise fail(f"cannot read the file ({error.strerror})") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise fail(
            f"is not valid JSON (line {error.lineno}, column {error.colno})"
        ) from None
    except (ValueError, RecursionError):
        raise fail("is not valid JSON") from None
    if not isinstance(data, dict) or not isinstance(data.get("resources"), list):
        raise fail("is not a state file (no 'resources' list)")
    return data, hashlib.sha256(raw).hexdigest()


def _stamp(snapshot: Dict[str, Any], now: dt.datetime) -> str:
    """``<ts>`` of the file names: the snapshot's timestamp, not the clock."""
    text = str((snapshot.get("metadata") or {}).get("timestamp") or "")
    try:
        moment = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=dt.timezone.utc)
        moment = moment.astimezone(dt.timezone.utc)
    except ValueError:
        moment = now
    return moment.strftime("%Y%m%d_%H%M%S")


def _lock_lines(problems: Sequence[str]) -> List[str]:
    return [
        f"{p}; run 'inventag policy lock' to record the change, or restore the file."
        for p in problems
    ]


# ---------------------------------------------------------------- commands
def _cmd_validate(args, out: TextIO, err: TextIO) -> int:
    now = _now(args)
    files = loader.expand_paths([Path(p) for p in args.paths])
    root = Path(args.paths[0]) if Path(args.paths[0]).is_dir() else None
    issues: List[TemplateIssue] = []
    rest: List[Path] = []
    waiver_files: List[Path] = []
    for path in files:
        try:
            docs = loader.read_documents(path, root or Path(path).parent)
        except PolicyError as error:
            issues.extend(error.issues)
            continue
        kinds = {d.data.get("kind") for d in docs}
        (waiver_files if kinds == {"waivers"} else rest).append(path)
    loaded = None
    waivers: List[model.Waiver] = []
    if rest:
        try:
            loaded = loader.load(rest, root=root)
        except PolicyError as error:
            issues.extend(error.issues)
    if waiver_files:
        try:
            waivers = loader.load_waivers(waiver_files, now, root=root)
        except PolicyError as error:
            issues.extend(error.issues)
    if issues:
        for issue in issues:
            err.write(f"error: {issue}\n")
        count = len(issues)
        err.write(
            f"{count} problem{'s' if count != 1 else ''} found; "
            "nothing was evaluated.\n"
        )
        return EXIT_ERROR
    policies = loaded.policies if loaded else ()
    sets = loaded.sets if loaded else ()
    for policy in policies:
        out.write(f"OK    {policy.file} (policy {policy.id})\n")
    for policy_set in sets:
        out.write(f"OK    {policy_set.file} (policy-set {policy_set.name})\n")
    for file in sorted({w.file for w in waivers}):
        n = sum(1 for w in waivers if w.file == file)
        out.write(f"OK    {file} ({n} waivers)\n")
    out.write(
        f"{len(policies)} policies, {len(sets)} sets, {len(waivers)} waivers: "
        "no problems.\n"
    )
    return EXIT_OK


def _set_members(
    loaded: loader.Loaded, name: str, seen: Optional[set] = None
) -> List[model.Policy]:
    seen = seen if seen is not None else set()
    by_set = {s.name: s for s in loaded.sets}
    by_name = {p.name: p for p in loaded.policies}
    found: List[model.Policy] = []
    if name in seen:
        return found
    seen.add(name)
    policy_set = by_set[name]
    for included in policy_set.include:
        found.extend(_set_members(loaded, included, seen))
    root = loaded.root
    for reference in policy_set.policies:
        if reference in by_name:
            found.append(by_name[reference])
        elif root is not None:
            from ..templating.loader import safe_relative_path

            base = (root / policy_set.file).parent
            path = safe_relative_path(base, reference)
            found.extend(loader.load([path], root=root).policies)
    return found


def _cmd_list(args, out: TextIO, err: TextIO) -> int:
    if args.shipped:
        if args.set:
            raise CliError(
                EXIT_USAGE, "--shipped cannot be used with --set; use one of them."
            )
        module = _shipped()
        if module is None:
            raise CliError(
                EXIT_ERROR,
                "the shipped sets (inventag.policy.builtin) are not installed "
                "in this build.",
            )
        names = sorted(module.SET_NAMES)
        counts = [str(len(module.load_set(n))) for n in names]
        width = max(len(n) for n in names + ["NAME"])
        out.write(f"{'NAME':<{width}}  POLICIES\n")
        for name, count in zip(names, counts):
            out.write(f"{name:<{width}}  {count}\n")
        return EXIT_OK
    policies = _select(args, err)
    rows = [
        (p.id, p.severity, str(p.version), p.sha256[:TRIM], p.file)
        for p in sorted(policies, key=lambda p: p.id)
    ]
    head = ("ID", "SEVERITY", "VERSION", "SHA256", "FILE")
    widths = [max(len(r[i]) for r in rows + [head]) for i in range(4)]
    for row in [head] + rows:
        cells = [f"{row[i]:<{widths[i]}}" for i in range(4)] + [row[4]]
        out.write("  ".join(cells) + "\n")
    return EXIT_OK


def _cmd_schema(args, out: TextIO, err: TextIO) -> int:
    if args.json:
        out.write(json.dumps(json_schema(), sort_keys=True, indent=2) + "\n")
        return EXIT_OK
    if args.field is None:
        width = max(len(n) for n in FIELD_HELP)
        for field, (where, _) in FIELD_HELP.items():
            out.write(f"{field:<{width}}  {where}\n")
        return EXIT_OK
    if args.field not in FIELD_HELP:
        raise CliError(
            EXIT_ERROR,
            f"no field named '{args.field}'; run 'inventag policy schema' to "
            "list the fields.",
        )
    where, text = FIELD_HELP[args.field]
    out.write(f"{args.field}  ({where})\n  {text}\n")
    return EXIT_OK


def _cmd_test(args, out: TextIO, err: TextIO) -> int:
    folder = Path(args.dir)
    if not folder.is_dir():
        shown = args.dir
        raise CliError(
            EXIT_ERROR,
            f"policy folder {shown} does not exist; give the folder as DIR.",
        )
    try:
        report = testing.run(folder)
    except PolicyError as error:
        raise CliError(EXIT_ERROR, *_issue_lines(error)) from None
    for warning in report.warnings:
        err.write(f"WARNING {warning}\n")
    for result in report.results:
        out.write(f"{'PASS' if result.ok else 'FAIL'}  {result.name}\n")
        for problem in result.problems:
            out.write(f"      {problem}\n")
    out.write(f"{len(report.results)} fixtures, {report.failed} failed.\n")
    return EXIT_OK if report.ok else EXIT_ERROR


def _formats(text: str) -> List[str]:
    words = [w.strip() for w in text.split(",") if w.strip()]
    for word in words:
        if word not in FORMATS:
            raise CliError(
                EXIT_USAGE,
                f"--format: unknown format '{word}'; use {', '.join(FORMATS)}.",
            )
    if not words:
        raise CliError(
            EXIT_USAGE, f"--format: no format given; use {', '.join(FORMATS)}."
        )
    return list(dict.fromkeys(words))


def _cmd_check(args, out: TextIO, err: TextIO) -> int:
    formats = _formats(args.format)
    now = _now(args)
    if args.locked and not (
        args.policies and len(args.policies) == 1 and Path(args.policies[0]).is_dir()
    ):
        raise CliError(
            EXIT_USAGE,
            "--locked: --policies must be one folder that holds policy.lock; "
            "give the folder.",
        )
    if args.locked:
        lock = _lock_module("--locked")
        root = Path(args.policies[0])
        try:
            problems = lock.verify(root)
            if not problems and args.waivers:
                # spec 10.3: the waivers file must be in the folder and the lock
                lock.require_listed(root, [Path(args.waivers)])
        except PolicyError as error:
            raise CliError(EXIT_ERROR, *_issue_lines(error)) from None
        if problems:
            raise CliError(EXIT_ERROR, *_lock_lines(problems))
    policies = _select(args, err)
    waivers: List[model.Waiver] = []
    if args.waivers:
        try:
            waivers = loader.load_waivers([Path(args.waivers)], now)
        except PolicyError as error:
            raise CliError(EXIT_ERROR, *_issue_lines(error)) from None
    snapshot, sha = _read_snapshot("--snapshot", args.snapshot)
    baseline = baseline_sha = None
    if args.baseline:
        baseline, baseline_sha = _read_snapshot("--baseline", args.baseline)
    try:
        result = engine.evaluate(
            snapshot,
            policies,
            waivers,
            baseline,
            now,
            fail_on=args.fail_on,
            fail_on_not_evaluated=args.fail_on_not_evaluated,
            show_values=args.show_values,
            snapshot_file=Path(args.snapshot).name,
            snapshot_sha256=sha,
            baseline_file=Path(args.baseline).name if args.baseline else "",
            baseline_sha256=baseline_sha or "",
        )
    except NotImplementedError as error:
        raise CliError(EXIT_ERROR, str(error)) from None

    texts: Dict[str, str] = {}
    for fmt in formats:
        if fmt == "json":
            texts[fmt] = engine.dumps(result)
        else:
            writers = _module(
                "outputs",
                f"--format {fmt}: the output writers (inventag.policy.outputs) "
                "are not installed in this build.",
            )
            texts[fmt] = writers.render(
                result,
                WRITER_FORMATS[fmt],
                show_values=args.show_values,
                fail_on=args.fail_on,
                thresholds=_thresholds(args),
            )
    if args.show_values and {"sarif", "junit"} & set(formats):
        err.write(
            "note: --show-values does not apply to sarif and junit; those "
            "files never carry a value.\n"
        )
    stamp = _stamp(snapshot, now)
    folder = Path(args.output_directory)
    written: List[Path] = []
    for fmt in formats:
        if fmt == "text":
            continue
        target = folder / f"policy_findings_{stamp}.{EXTENSIONS[fmt]}"
        try:
            # owner-only, as the scan's findings files (lead decision 4)
            safe_output.ensure_private_dir(folder)
            with safe_output.open_private(
                target, "w", encoding="utf-8", newline="\n"
            ) as handle:
                handle.write(texts[fmt])
        except OSError as error:
            raise CliError(
                EXIT_ERROR,
                f"cannot write {target}: {error.strerror}; check the folder "
                "and its permissions.",
            ) from None
        written.append(target)
    if "text" in texts:
        out.write(texts["text"])
    for target in written:
        err.write(f"Wrote {target}\n")
    return int(result["summary"]["exit_code"])


def _trace_lines(trace: Any, depth: int = 0) -> List[str]:
    """The lines of an engine trace (spec 11.5): kind, key, verdict, reason."""
    nodes = trace if isinstance(trace, list) else [trace]
    lines: List[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        label = f"{node.get('part')} {node.get('kind')}"
        if node.get("key"):
            label += f" {node['key']}"
        text = f"{label}: {node.get('verdict')}"
        if node.get("reason"):
            text += f" ({node['reason']})"
        lines.append("  " * depth + text)
        lines.extend(_trace_lines(node.get("children") or [], depth + 1))
    return lines


def _evaluate_with_trace(*args, resource: Optional[str], **kwargs):
    """``engine.evaluate`` with ``trace=True`` (spec 11.5, engine order P1c).

    Until the engine has the argument the call runs without it and the
    findings carry no ``trace``.
    """
    accepted = inspect.signature(engine.evaluate).parameters
    if "trace" in accepted:
        kwargs["trace"] = True
        if resource and "trace_resource" in accepted:
            kwargs["trace_resource"] = resource
    return engine.evaluate(*args, **kwargs)


def _cmd_explain(args, out: TextIO, err: TextIO) -> int:
    now = _now(args)
    policies = _select(args, err)
    found = [p for p in policies if args.policy in (p.id, p.name)]
    if not found:
        raise CliError(
            EXIT_ERROR,
            f"no policy with id or name '{args.policy}'; run 'inventag policy "
            "list' to see the loaded policies.",
        )
    policy = found[0]
    snapshot, sha = _read_snapshot("--snapshot", args.snapshot)
    baseline = None
    if args.baseline:
        baseline, _ = _read_snapshot("--baseline", args.baseline)
    try:
        result = _evaluate_with_trace(
            snapshot,
            [policy],
            (),
            baseline,
            now,
            resource=args.resource,
            include_pass=True,
            show_values=args.show_values,
            snapshot_file=Path(args.snapshot).name,
            snapshot_sha256=sha,
        )
    except NotImplementedError as error:
        raise CliError(EXIT_ERROR, str(error)) from None
    findings = result["findings"]
    if args.resource:
        findings = [f for f in findings if f["resource"] == args.resource]
        if not findings:
            raise CliError(
                EXIT_ERROR,
                f"--resource {args.resource}: the policy does not select a row "
                "with this ARN; check the ARN or run without --resource.",
            )
    out.write(
        f"{policy.id} ({policy.name}, {policy.severity}, version {policy.version})\n"
    )
    if result["not_evaluated_policies"]:
        out.write(
            "This policy needs a baseline; pass --baseline FILE. No row was "
            "evaluated.\n"
        )
    for finding in findings:
        out.write(f"{finding['result']}  {finding['resource']}\n")
        for detail in finding.get("details") or ():
            text = detail.get("problem", "")
            if detail.get("key"):
                text = f"{text}: {detail['key']}"
            line = f"      check {detail.get('check')} ({detail.get('type')}): {text}"
            if "value" in detail:
                line += f" (value: {json.dumps(detail['value'], sort_keys=True)})"
            out.write(line + "\n")
        if finding.get("reason"):
            out.write(f"      reason: {finding['reason']}\n")
        if finding.get("trace"):
            out.write("      trace:\n")
            for line in _trace_lines(finding["trace"]):
                out.write(f"        {line}\n")
    if not result["not_evaluated_policies"]:
        selected = sum(1 for f in findings if f["result"] != "out_of_scope")
        if args.resource:
            skipped = len(findings) - selected
        else:
            skipped = result["summary"]["by_result"]["out_of_scope"]
        out.write(f"Rows: {selected} selected, {skipped} not selected.\n")
    return EXIT_OK


def _cmd_lock(args, out: TextIO, err: TextIO) -> int:
    folder = Path(args.path)
    if not folder.is_dir():
        raise CliError(
            EXIT_ERROR,
            f"policy folder {args.path} does not exist; give the folder.",
        )
    lock = _lock_module("policy lock")
    if args.check:
        try:
            problems = lock.verify(folder)
        except PolicyError as error:
            raise CliError(EXIT_ERROR, *_issue_lines(error)) from None
        if problems:
            raise CliError(EXIT_ERROR, *_lock_lines(problems))
        out.write("policy.lock is current.\n")
        return EXIT_OK
    try:
        written = lock.write(folder)
    except PolicyError as error:
        raise CliError(EXIT_ERROR, *_issue_lines(error)) from None
    except OSError as error:
        raise CliError(
            EXIT_ERROR,
            f"cannot write policy.lock: {error.strerror}; check the folder and "
            "its permissions.",
        ) from None
    out.write(f"Wrote {written}\n")
    return EXIT_OK


COMMANDS = {
    "validate": _cmd_validate,
    "list": _cmd_list,
    "schema": _cmd_schema,
    "test": _cmd_test,
    "check": _cmd_check,
    "explain": _cmd_explain,
    "lock": _cmd_lock,
}


def main(
    argv: Optional[Sequence[str]] = None,
    out: Optional[TextIO] = None,
    err: Optional[TextIO] = None,
) -> int:
    """Run ``inventag policy`` with the arguments after the word ``policy``."""
    out = out or sys.stdout
    err = err or sys.stderr
    parser = build_parser()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as stop:
        return int(stop.code or 0) if isinstance(stop.code, int) else EXIT_USAGE
    try:
        return COMMANDS[args.command](args, out, err)
    except CliError as error:
        for line in error.lines:
            err.write(f"error: {line}\n")
        return error.code
