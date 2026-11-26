"""Validation of policy, policy-set and waiver documents (spec 2, 9.2, 9.3, 9.6).

Each problem is a :class:`TemplateIssue` (``file:line: field: problem``), the
form the template loader uses. Every pattern and key is compiled here, so the
engine meets only valid entries.
"""

from __future__ import annotations

import datetime as dt
import difflib
import re
import string
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import re._constants as _sre
import jmespath
from re._parser import parse as _sre_parse
from jmespath.exceptions import JMESPathError

from ..templating.errors import TemplateError, TemplateIssue
from ..templating.schema import NAME_PATTERN
from . import model

BACKTRACK_PROBLEM = (
    "pattern can take very long to match: a repeated group varies in length, "
    "or two repeats have nothing fixed between them; rewrite it"
)
_REPEATS = (_sre.MAX_REPEAT, _sre.MIN_REPEAT)
_WILDCARD_PARTS = re.compile(r"\[[^\]]*\]?|[*?]")


_FIXED = (
    _sre.LITERAL,
    _sre.NOT_LITERAL,
    _sre.IN,
    _sre.ANY,
    _sre.CATEGORY,
)


def _risky(items) -> bool:
    """True when a part of a parsed pattern varies in length: a repeat whose
    minimum and maximum differ, or a ``|`` (atomic groups and possessive
    repeats are left out: they do not backtrack)."""
    for op, av in items:
        if op in _REPEATS:
            if av[0] != av[1] or _risky(av[2]):
                return True
        elif op is _sre.BRANCH:
            return True
        elif op is _sre.SUBPATTERN:
            if _risky(av[3]):
                return True
        elif op in (_sre.ASSERT, _sre.ASSERT_NOT):
            if _risky(av[1]):
                return True
    return False


def _fixed(items) -> bool:
    """True when the items always match at least one character."""
    for op, av in items:
        if op in _FIXED:
            return True
        if op in _REPEATS and av[0] > 0 and _fixed(av[2]):
            return True
        if op is _sre.SUBPATTERN and _fixed(av[3]):
            return True
    return False


def _adjacent(items) -> bool:
    """True when two unbounded repeats follow each other in one sequence with
    nothing fixed between them (``a*a*``, ``.*b?.*``): the match tries every
    split of the text between them."""
    open_repeat = False
    for op, av in _flat(items):
        if op in _REPEATS and av[1] == _sre.MAXREPEAT:
            if open_repeat:
                return True
            open_repeat = True
        elif op in _FIXED or (op in _REPEATS and av[0] == av[1] and _fixed(av[2])):
            open_repeat = False
    return False


def _flat(items):
    """The items of a sequence, with the contents of plain groups inlined."""
    for op, av in items:
        if op is _sre.SUBPATTERN:
            yield from _flat(av[3])
        else:
            yield op, av


def _nested(items) -> bool:
    if _adjacent(items):
        return True
    for op, av in items:
        if op in _REPEATS:
            if av[1] > 1 and _risky(av[2]):
                return True
            if _nested(av[2]):
                return True
        elif op is _sre.SUBPATTERN:
            if _nested(av[3]):
                return True
        elif op is _sre.BRANCH:
            if any(_nested(b) for b in av[1]):
                return True
        elif op in (_sre.ASSERT, _sre.ASSERT_NOT):
            if _nested(av[1]):
                return True
    return False


def backtracks(pattern: str, flags: int = 0) -> bool:
    """True when ``pattern`` repeats a group whose length varies (``(a+)+``,
    ``(a|a)+``, ``(a{1,50}){1,50}``, ``(a?){30}``) or has two unbounded repeats
    with nothing fixed between them (``a*a*``, ``.*.*``): such a pattern can
    take exponential or high polynomial time on a value from the scanned
    account. Not complete: repeats with a fixed character between them pass."""
    try:
        return _nested(_sre_parse(pattern, flags).data)
    except (re.error, RecursionError):  # compiled and checked elsewhere
        return False


def only_wildcards(resource: str) -> bool:
    """True when a waiver ``resource`` has no literal character: every
    character is part of ``*``, ``?`` or a ``[...]`` class."""
    text = resource.strip()
    return bool(text) and not _WILDCARD_PARTS.sub("", text)


Path_ = Tuple[Any, ...]
LineOf = Callable[[Path_], Optional[int]]

_ACCOUNT = re.compile(r"[0-9]{12}")
_ID = re.compile(model.ID_PATTERN)
OPERATOR_LIST = ", ".join(model.OPERATORS)
PLACEHOLDER_LIST = ", ".join("{" + p + "}" for p in model.PLACEHOLDERS)
CHANGES = ("added", "removed", "modified")


class PolicyError(TemplateError):
    """A policy, set or waiver file is not valid (exit code 1)."""


def _type_name(value: Any) -> str:
    if value is None:
        return "nothing"
    if isinstance(value, bool):
        return "true/false"
    return {
        str: "text",
        int: "a number",
        float: "a number",
        list: "a list",
        dict: "a mapping",
    }.get(type(value), type(value).__name__)


class Validator:
    """Collects the issues of one document."""

    def __init__(self, source: str, line_of: LineOf):
        self.source = source
        self.line_of = line_of
        self.issues: List[TemplateIssue] = []

    # ------------------------------------------------------------ basics
    def add(self, path: Path_, message: str) -> None:
        self.issues.append(
            TemplateIssue(
                message,
                self.source,
                self.line_of(path),
                ".".join(str(p) for p in path) or None,
            )
        )

    def fields(
        self, value: Any, path: Path_, allowed: Sequence[str], required=()
    ) -> bool:
        """A mapping with only ``allowed`` keys; False when it is not a mapping."""
        if not isinstance(value, dict):
            self.add(
                path, f"must be a mapping (key: value pairs), got {_type_name(value)}"
            )
            return False
        for key in value:
            if key in model.FORBIDDEN_FIELDS:
                self.add(path + (key,), model.NO_ACTIONS)
            elif key not in allowed:
                hint = difflib.get_close_matches(str(key), list(allowed), n=1)
                suggestion = f"; did you mean '{hint[0]}'?" if hint else ""
                self.add(
                    path + (key,),
                    f"unknown field '{key}'{suggestion} Allowed here: "
                    f"{', '.join(sorted(allowed))}",
                )
        for key in required:
            if value.get(key) is None:
                self.add(path + (key,), "is required")
        return True

    def text(self, value: Any, path: Path_, limit: Optional[int] = None) -> bool:
        if not isinstance(value, str):
            self.add(path, f"must be text, got {_type_name(value)}")
            return False
        if limit is not None and len(value) > limit:
            self.add(path, f"must be at most {limit} characters")
            return False
        return True

    def texts(self, value: Any, path: Path_, limit: Optional[int] = None) -> bool:
        if not isinstance(value, list):
            self.add(path, f"must be a list, got {_type_name(value)}")
            return False
        ok = True
        for i, item in enumerate(value):
            ok = self.text(item, path + (i,)) and ok
        if limit is not None and len(value) > limit:
            self.add(path, f"must have at most {limit} entries")
            ok = False
        return ok

    def boolean(self, value: Any, path: Path_) -> None:
        if not isinstance(value, bool):
            self.add(path, f"must be true or false, got {_type_name(value)}")

    def key(self, value: Any, path: Path_) -> None:
        if not self.text(value, path, model.LIMITS.key_length):
            return
        if value.startswith(("tags.", "tag:")):
            if (
                len(value.split(".", 1)[-1] if value.startswith("tags.") else value[4:])
                == 0
            ):
                self.add(path, "names no tag key")
            return
        try:
            jmespath.compile(value)
        except JMESPathError as error:
            self.add(path, f"not a valid key: {error}".splitlines()[0])

    def pattern(self, value: Any, path: Path_, flags: int = 0) -> None:
        if not self.text(value, path, model.LIMITS.pattern_length):
            return
        try:
            re.compile(value, flags)
        except re.error as error:
            self.add(path, f"not a valid regular expression: {error}")
            return
        if backtracks(value, flags):
            self.add(path, BACKTRACK_PROBLEM)

    # ------------------------------------------------------------ blocks
    def resource(self, value: Any, path: Path_, related: bool = False) -> None:
        allowed = [
            "services",
            "resource_types",
            "exclude_resource_types",
            "regions",
            "accounts",
        ]
        if not related:
            allowed += ["filters", "listings"]
        elif isinstance(value, dict) and "filters" in value:
            self.add(path + ("filters",), "rows of a related check take no filters")
            value = {k: v for k, v in value.items() if k != "filters"}
        if not self.fields(value, path, allowed):
            return
        for name in (
            "services",
            "resource_types",
            "exclude_resource_types",
            "regions",
            "listings",
        ):
            if name in value:
                self.texts(value[name], path + (name,))
        if "accounts" in value and self.texts(value["accounts"], path + ("accounts",)):
            for i, account in enumerate(value["accounts"]):
                if not _ACCOUNT.fullmatch(account):
                    self.add(path + ("accounts", i), "must be a 12-digit account ID")
        if "filters" in value:
            self.entries(value["filters"], path + ("filters",), filters_only=True)

    def entries(
        self, value: Any, path: Path_, filters_only: bool = False, depth: int = 0
    ):
        if not isinstance(value, list):
            self.add(path, f"must be a list, got {_type_name(value)}")
            return
        limit = model.LIMITS.entries_per_group
        if len(value) > limit:
            self.add(path, f"must have at most {limit} entries")
        for i, entry in enumerate(value):
            self.entry(entry, path + (i,), filters_only, depth)

    def entry(self, entry: Any, path: Path_, filters_only: bool, depth: int) -> None:
        if not isinstance(entry, dict):
            self.add(path, f"must be a mapping, got {_type_name(entry)}")
            return
        if len(entry) == 1 and str(next(iter(entry))).startswith("tag:"):
            ((key, wanted),) = entry.items()
            self.key(key, path + (key,))
            if isinstance(wanted, (dict, list)):
                self.add(path + (key,), "must be a single value")
            return
        groups = [g for g in ("and", "or", "not") if g in entry]
        if groups:
            group = groups[0]
            if len(entry) > 1:
                self.add(path, f"'{group}' must be the only field of its entry")
            if depth + 1 > model.LIMITS.nesting_depth:
                self.add(
                    path,
                    f"and/or/not are nested more than {model.LIMITS.nesting_depth} levels",
                )
                return
            items = entry[group]
            if isinstance(items, list) and not items:
                self.add(path + (group,), f"'{group}' needs at least one entry")
            self.entries(items, path + (group,), filters_only, depth + 1)
            return
        kind = entry.get("type", "value")
        if kind == "baseline" and depth > 0:
            self.add(
                path + ("type",), "a baseline check must be a top-level entry of check"
            )
            return
        if filters_only and kind != "value":
            self.add(path + ("type",), "filters take only type: value")
            return
        handler = {
            "value": self.value_entry,
            "required-tags": self.required_tags,
            "allowed-regions": self.allowed_regions,
            "name-pattern": self.name_pattern,
            "baseline": self.baseline,
            "related": self.related,
            "require": self.require_entry,
        }.get(kind)
        if handler is None:
            self.add(
                path + ("type",),
                f"unknown check type '{kind}'; use one of {', '.join(model.CHECK_TYPES)}",
            )
            return
        handler(entry, path)

    # ------------------------------------------------------------ checks
    def value_entry(self, entry: Dict, path: Path_) -> None:
        if not self.fields(
            entry, path, ["type", "key", "op", "value", "value_type"], ["key"]
        ):
            return
        if "key" in entry:
            self.key(entry["key"], path + ("key",))
        op = entry.get("op", "eq")
        if op not in model.OPERATORS:
            self.add(
                path + ("op",), f"unknown operator '{op}'; use one of {OPERATOR_LIST}"
            )
            return
        value_type = entry.get("value_type")
        if value_type is not None and value_type not in model.VALUE_TYPES:
            self.add(
                path + ("value_type",),
                f"unknown value_type '{value_type}'; use one of {', '.join(model.VALUE_TYPES)}",
            )
        wanted = entry.get("value")
        if op in ("in", "not-in") and not isinstance(wanted, list):
            self.add(path + ("value",), f"'{op}' needs a list")
        if op in ("regex", "regex-case"):
            self.pattern(
                wanted, path + ("value",), re.IGNORECASE if op == "regex" else 0
            )
        if op == "glob":
            self.text(wanted, path + ("value",), model.LIMITS.pattern_length)

    def required_tags(self, entry: Dict, path: Path_) -> None:
        allowed = ["type", "keys", "policy", "use_scope", "missing_only"]
        if not self.fields(entry, path, allowed):
            return
        if ("keys" in entry) == ("policy" in entry):
            self.add(path, "give either keys or policy")
            return
        for option in ("use_scope", "missing_only"):
            if option in entry:
                self.boolean(entry[option], path + (option,))
                if "policy" not in entry:
                    self.add(path + (option,), f"{option} needs policy")
        if "policy" in entry:
            self.text(entry["policy"], path + ("policy",))
            return
        keys = entry["keys"]
        if not isinstance(keys, list) or not keys:
            self.add(path + ("keys",), "needs at least one key")
            return
        for i, rule in enumerate(keys):
            rpath = path + ("keys", i)
            if not self.fields(
                rule,
                rpath,
                ["key", "allowed_values", "case_sensitive", "pattern"],
                ["key"],
            ):
                continue
            self.text(rule.get("key"), rpath + ("key",))
            if "allowed_values" in rule:
                self.texts(rule["allowed_values"], rpath + ("allowed_values",))
            if "case_sensitive" in rule:
                self.boolean(rule["case_sensitive"], rpath + ("case_sensitive",))
            if "pattern" in rule:
                self.pattern(rule["pattern"], rpath + ("pattern",))

    def allowed_regions(self, entry: Dict, path: Path_) -> None:
        if not self.fields(
            entry, path, ["type", "regions", "allow_global"], ["regions"]
        ):
            return
        if "regions" in entry:
            self.texts(entry["regions"], path + ("regions",))
        if "allow_global" in entry:
            self.boolean(entry["allow_global"], path + ("allow_global",))

    def name_pattern(self, entry: Dict, path: Path_) -> None:
        if not self.fields(entry, path, ["type", "pattern", "field"], ["pattern"]):
            return
        if "pattern" in entry:
            self.pattern(entry["pattern"], path + ("pattern",))
        if "field" in entry:
            self.key(entry["field"], path + ("field",))

    def baseline(self, entry: Dict, path: Path_) -> None:
        if not self.fields(entry, path, ["type", "change", "attributes"]):
            return
        change = entry.get("change")
        if (
            not isinstance(change, list)
            or not change
            or any(c not in CHANGES for c in change)
        ):
            self.add(
                path + ("change",),
                "change needs at least one of added, removed, modified",
            )
            return
        if "attributes" in entry:
            if "modified" not in change:
                self.add(path + ("attributes",), "attributes go only with modified")
            elif self.texts(entry["attributes"], path + ("attributes",)):
                for i, key in enumerate(entry["attributes"]):
                    self.key(key, path + ("attributes", i))

    def related(self, entry: Dict, path: Path_) -> None:
        allowed = ["type", "rows", "their_key", "my_key", "listing", "expect"]
        if any(entry.get(k) is None for k in ("rows", "their_key", "my_key")):
            self.add(path, "related needs rows, their_key and my_key")
        if not self.fields(entry, path, allowed):
            return
        if entry.get("rows") is not None:
            self.resource(entry["rows"], path + ("rows",), related=True)
        for name in ("their_key", "my_key"):
            if entry.get(name) is not None:
                self.key(entry[name], path + (name,))
        if "listing" in entry:
            self.text(entry["listing"], path + ("listing",))
        if entry.get("expect", "any") not in ("any", "none"):
            self.add(path + ("expect",), "expect must be any or none")

    def require_entry(self, entry: Dict, path: Path_) -> None:
        if not self.fields(entry, path, ["type", "keys"]):
            return
        self.require(entry.get("keys"), path + ("keys",))

    def require(self, keys: Any, path: Path_) -> None:
        if not isinstance(keys, list) or not keys:
            self.add(path, "require needs at least one key")
            return
        for i, key in enumerate(keys):
            self.key(key, path + (i,))

    # ------------------------------------------------------------ documents
    def message(self, value: Any, path: Path_) -> None:
        if not self.text(value, path, model.LIMITS.message_length):
            return
        try:
            parts = [
                (f, spec, conversion)
                for _, f, spec, conversion in string.Formatter().parse(value)
                if f is not None
            ]
        except ValueError as error:
            self.add(path, f"not a valid message: {error}")
            return
        names = [f for f, _, _ in parts]
        if any(spec or conversion for _, spec, conversion in parts):
            self.add(
                path,
                "a message placeholder takes no format spec or conversion; "
                "write it as {name}",
            )
            return
        unknown = [n for n in names if n not in model.PLACEHOLDERS]
        if unknown:
            self.add(
                path,
                f"unknown placeholder '{{{unknown[0]}}}'; use one of {PLACEHOLDER_LIST}",
            )

    def policy_spec(self, spec: Any) -> None:
        path = ("spec",)
        allowed = [
            "id",
            "severity",
            "version",
            "resource",
            "require",
            "check",
            "message",
            "references",
            "enabled",
        ]
        if not self.fields(spec, path, allowed, ["id", "severity"]):
            return
        if "id" in spec and not (
            isinstance(spec["id"], str) and _ID.fullmatch(spec["id"])
        ):
            self.add(path + ("id",), "id must look like ABC-001")
        if "severity" in spec and spec["severity"] not in model.SEVERITIES:
            self.add(
                path + ("severity",),
                f"must be one of {', '.join(model.SEVERITIES)}",
            )
        if "version" in spec and not (
            isinstance(spec["version"], int)
            and not isinstance(spec["version"], bool)
            and spec["version"] >= 1
        ):
            self.add(path + ("version",), "must be a whole number of 1 or more")
        if "resource" in spec:
            self.resource(spec["resource"], path + ("resource",))
        if "require" in spec:
            self.require(spec["require"], path + ("require",))
        check = spec.get("check")
        if check is None or (isinstance(check, list) and not check):
            self.add(path + ("check",), "at least one check is needed")
        elif isinstance(check, list) and len(check) > model.LIMITS.checks_per_policy:
            self.add(
                path + ("check",), f"at most {model.LIMITS.checks_per_policy} checks"
            )
        else:
            self.entries(check, path + ("check",))
        if "message" in spec:
            self.message(spec["message"], path + ("message",))
        if "references" in spec:
            self.texts(
                spec["references"], path + ("references",), model.LIMITS.references
            )
        if "enabled" in spec:
            self.boolean(spec["enabled"], path + ("enabled",))

    def set_spec(self, spec: Any) -> None:
        path = ("spec",)
        if not self.fields(spec, path, ["policies", "include", "severity_overrides"]):
            return
        for name in ("policies", "include"):
            if name in spec:
                self.texts(spec[name], path + (name,))
        overrides = spec.get("severity_overrides")
        if overrides is not None:
            if not isinstance(overrides, dict):
                self.add(
                    path + ("severity_overrides",),
                    "must be a mapping of id to severity",
                )
                return
            for pid, severity in overrides.items():
                if severity not in model.SEVERITIES:
                    self.add(
                        path + ("severity_overrides", pid),
                        f"must be one of {', '.join(model.SEVERITIES)}",
                    )

    def waivers_spec(self, spec: Any, now: dt.datetime) -> None:
        path = ("spec",)
        if not self.fields(spec, path, ["waivers"], ["waivers"]):
            return
        waivers = spec.get("waivers")
        if not isinstance(waivers, list):
            return
        allowed = ["policy", "resource", "account", "reason", "approved_by", "expires"]
        today = now.astimezone(dt.timezone.utc).date()
        for i, waiver in enumerate(waivers):
            wpath = path + ("waivers", i)
            if not isinstance(waiver, dict):
                self.add(wpath, f"must be a mapping, got {_type_name(waiver)}")
                continue
            for key in waiver:
                if key not in allowed:
                    self.fields({key: None}, wpath, allowed)
            for key in ("policy", "resource", "reason", "approved_by"):
                if waiver.get(key) is None:
                    self.add(wpath + (key,), f"{key} is required")
            if waiver.get("expires") is None:
                self.add(wpath + ("expires",), "expires is required")
            resource = waiver.get("resource")
            if isinstance(resource, str):
                if resource.strip() == "*" or only_wildcards(resource):
                    self.add(
                        wpath + ("resource",), "a waiver cannot match every resource"
                    )
                elif any(c in resource for c in "*?") and not waiver.get("account"):
                    self.add(
                        wpath + ("account",),
                        "account is required when resource has a wildcard",
                    )
            elif resource is not None:
                self.text(resource, wpath + ("resource",))
            account = waiver.get("account")
            if account is not None and not (
                isinstance(account, str) and _ACCOUNT.fullmatch(account)
            ):
                self.add(
                    wpath + ("account",), "must be a 12-digit account ID, in quotes"
                )
            reason = waiver.get("reason")
            if reason is not None and not (
                isinstance(reason, str) and 10 <= len(reason) <= 300
            ):
                self.add(wpath + ("reason",), "reason must be 10 to 300 characters")
            if waiver.get("approved_by") is not None:
                self.text(waiver["approved_by"], wpath + ("approved_by",))
            if waiver.get("policy") is not None:
                self.text(waiver["policy"], wpath + ("policy",))
            expires = parse_date(waiver.get("expires"))
            if waiver.get("expires") is not None and expires is None:
                self.add(wpath + ("expires",), "expires must be a date YYYY-MM-DD")
            elif expires is not None:
                limit = model.LIMITS.waiver_days_ahead
                if (expires - today).days > limit:
                    self.add(
                        wpath + ("expires",),
                        f"expires must be at most {limit} days after now",
                    )

    def header(self, data: Dict[str, Any]) -> Optional[str]:
        allowed = ["format_version", "kind", "name", "description", "spec"]
        if not self.fields(
            data, (), allowed, ["format_version", "kind", "name", "spec"]
        ):
            return None
        if data.get("format_version") not in (None, 1) or isinstance(
            data.get("format_version"), bool
        ):
            self.add(("format_version",), "must be 1")
        kind = data.get("kind")
        if kind is not None and kind not in model.KINDS:
            self.add(("kind",), f"must be one of {', '.join(model.KINDS)}")
            kind = None
        name = data.get("name")
        if name is not None and not (
            isinstance(name, str) and NAME_PATTERN.fullmatch(name)
        ):
            self.add(
                ("name",),
                "must use lower-case letters, digits and hyphens (at most 63 characters)",
            )
        if "description" in data:
            self.text(data["description"], ("description",))
        return kind


def parse_date(value: Any) -> Optional[dt.date]:
    if isinstance(value, dt.datetime):
        return None
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", value):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def validate_document(
    data: Dict[str, Any], source: str, line_of: LineOf, now: Optional[dt.datetime]
) -> Tuple[Optional[str], List[TemplateIssue]]:
    """(kind, issues) of one document."""
    validator = Validator(source, line_of)
    kind = validator.header(data)
    spec = data.get("spec") if isinstance(data, dict) else None
    if kind == "policy" and spec is not None:
        validator.policy_spec(spec)
    elif kind == "policy-set" and spec is not None:
        validator.set_spec(spec)
    elif kind == "waivers" and spec is not None:
        validator.waivers_spec(
            spec, now or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        )
    return kind, validator.issues
