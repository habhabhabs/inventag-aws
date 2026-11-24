"""Filter entries and checks on one row, with three values (spec 2.2, 2.3, 9).

Pure: the row and a :class:`Context` (the run's ``now`` and the lookups the
engine builds from the snapshot) come in; a value, a reason and the failed
entries come out. No AWS call, no clock, no file.

Every entry is ``TRUE``, ``FALSE`` or ``UNKNOWN``. ``and``, ``or`` and
``not`` follow Kleene's rules. An unknown entry carries one of
``model.REASONS``; where several unknown entries meet, the reason that comes
first in that list is kept (spec 9.1).
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import jmespath

from ..templating.columns import normalize_tags
from ..templating.tag_policy import check_value
from . import model


class Tri:
    """One of the three values."""

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return self.name


TRUE = Tri("TRUE")
FALSE = Tri("FALSE")
UNKNOWN = Tri("UNKNOWN")

_RANK = {reason: i for i, reason in enumerate(model.REASONS)}


def first_reason(reasons) -> Optional[str]:
    """The reason that comes first in spec 9.1's order."""
    found = [r for r in reasons if r]
    return min(found, key=lambda r: _RANK.get(r, len(_RANK))) if found else None


@dataclass
class Context:
    """What an entry may read besides the row."""

    now: dt.datetime
    tags_unknown: Callable[[Dict[str, Any]], bool] = lambda row: False
    # (account, listing, region) -> True when that listing was not read
    unit_unread: Callable[[str, str, str], bool] = lambda a, s, r: False
    # (account, region, rows block) -> the related rows of that place
    related_rows: Callable[[str, str, Dict[str, Any]], Sequence[Dict]] = (
        lambda a, r, block: ()
    )
    show_values: bool = False


@dataclass
class Outcome:
    value: Tri
    reason: Optional[str] = None
    failures: List[Dict[str, Any]] = field(default_factory=list)
    progress: int = 0  # entries that were true before the false one (and)


# ----------------------------------------------------------------- nodes
@dataclass
class Key:
    text: str  # as written
    tag: Optional[str] = None  # tag key, when the key reads a tag
    expression: Any = None  # compiled JMESPath otherwise

    @property
    def is_raw(self) -> bool:
        return self.text.startswith("raw_data")

    def get(self, row: Dict[str, Any]) -> Any:
        if self.tag is not None:
            return normalize_tags(row.get("tags")).get(self.tag)
        return self.expression.search(row)


def compile_key(text: str) -> Key:
    """A key as in spec 2.2.1. ``tags.<Key>`` and ``tag:<Key>`` read a tag;
    anything else is JMESPath (``jmespath.exceptions.ParseError`` if not)."""
    if text.startswith("tags."):
        return Key(text, tag=text[len("tags.") :])
    if text.startswith("tag:"):
        return Key(text, tag=text[len("tag:") :])
    return Key(text, expression=jmespath.compile(text))


@dataclass
class ValueNode:
    key: Key
    op: str = "eq"
    value: Any = None
    value_type: Optional[str] = None
    pattern: Any = None  # compiled for regex and regex-case


@dataclass
class GroupNode:
    op: str  # and, or, not
    children: List[Any]


@dataclass
class RequireNode:
    keys: List[Key]


@dataclass
class CheckNode:
    """required-tags, allowed-regions, name-pattern, related, baseline."""

    type: str
    spec: Dict[str, Any]
    key: Optional[Key] = None
    my_key: Optional[Key] = None
    their_key: Optional[Key] = None
    pattern: Any = None


def _shorthand(entry: Dict[str, Any]) -> Optional[Tuple[str, Any]]:
    if len(entry) == 1:
        ((key, value),) = entry.items()
        if isinstance(key, str) and key.startswith("tag:"):
            return key, value
    return None


def compile_entry(entry: Dict[str, Any]) -> Any:
    """Compile one validated entry (``schema`` has checked it)."""
    short = _shorthand(entry)
    if short is not None:
        return ValueNode(compile_key(short[0]), "eq", short[1])
    for op in ("and", "or", "not"):
        if op in entry:
            return GroupNode(op, [compile_entry(e) for e in entry[op]])
    kind = entry.get("type", "value")
    if kind == "value":
        op = entry.get("op", "eq")
        node = ValueNode(
            compile_key(entry["key"]),
            op,
            entry.get("value"),
            entry.get("value_type"),
        )
        if op == "regex":
            node.pattern = re.compile(entry["value"], re.IGNORECASE)
        elif op == "regex-case":
            node.pattern = re.compile(entry["value"])
        return node
    if kind == "require":
        return RequireNode([compile_key(k) for k in entry["keys"]])
    node = CheckNode(kind, dict(entry))
    if kind == "name-pattern":
        node.key = compile_key(entry["field"]) if entry.get("field") else None
        node.pattern = re.compile(entry["pattern"])
    elif kind == "related":
        node.my_key = compile_key(entry["my_key"])
        node.their_key = compile_key(entry["their_key"])
    return node


# ----------------------------------------------------------------- values
def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _is_number(a) and _is_number(b):
        return a == b
    if isinstance(a, str) or isinstance(b, str):
        return isinstance(a, str) and isinstance(b, str) and a == b
    return type(a) is type(b) and a == b


class _NotConvertible(Exception):
    pass


def parse_instant(value: Any) -> dt.datetime:
    """An ISO 8601 date or instant (no zone = UTC), or epoch seconds."""
    if _is_number(value):
        return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, dt.date):
        parsed = dt.datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        text = value.strip()
        try:
            if re.fullmatch(r"\d{4}-\d\d-\d\d", text):
                parsed = dt.datetime.fromisoformat(text)
            else:
                parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            raise _NotConvertible() from None
    else:
        raise _NotConvertible()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _convert(found: Any, value_type: Optional[str], now: dt.datetime) -> Any:
    if value_type is None:
        return found
    if value_type == "integer":
        if _is_number(found):
            return int(found)
        if isinstance(found, str) and re.fullmatch(r"\s*-?\d+\s*", found):
            return int(found)
        raise _NotConvertible()
    if value_type == "size":
        if isinstance(found, (list, dict, str)):
            return len(found)
        raise _NotConvertible()
    if value_type == "normalize":
        return str(found).strip().lower()
    if value_type in ("age", "expiration"):
        instant = parse_instant(found)
        days = (now - instant).total_seconds() / 86400
        return days if value_type == "age" else -days
    if value_type == "text":
        return found if isinstance(found, str) else str(found)
    raise _NotConvertible()  # pragma: no cover - schema refuses other types


def _wanted(node: ValueNode) -> Any:
    if node.value_type == "normalize":
        if isinstance(node.value, list):
            return [str(v).strip().lower() for v in node.value]
        return str(node.value).strip().lower()
    return node.value


def _special(found: Any, word: str) -> bool:
    if word == "absent":
        return found is None
    if word in ("present", "not-null"):
        return found is not None
    # empty
    return found is None or (isinstance(found, (str, list, dict)) and len(found) == 0)


def _leaf_failure(node, problem: str, found: Any, ctx: Context) -> Dict[str, Any]:
    failure = {"type": "value", "key": node.key.text, "problem": problem}
    if ctx.show_values:
        failure["value"] = found
    return failure


def _value(node: ValueNode, row: Dict[str, Any], ctx: Context) -> Outcome:
    if node.key.is_raw and model.identity_only(row):
        return Outcome(UNKNOWN, "identity_only")
    if node.key.tag is not None and ctx.tags_unknown(row):
        return Outcome(UNKNOWN, "tags_not_read")
    found = node.key.get(row)

    def result(ok: bool) -> Outcome:
        if ok:
            return Outcome(TRUE)
        return Outcome(
            FALSE, failures=[_leaf_failure(node, "condition not met", found, ctx)]
        )

    if (
        node.op == "eq"
        and node.value_type != "text"
        and isinstance(node.value, str)
        and node.value in model.SPECIAL_VALUES
    ):
        return result(_special(found, node.value))
    if found is None:
        return result(node.op in ("ne", "not-in"))
    try:
        found = _convert(found, node.value_type, ctx.now)
    except _NotConvertible:
        return Outcome(UNKNOWN, "not_convertible")
    wanted = _wanted(node)
    op = node.op
    if op == "eq":
        return result(_equal(found, wanted))
    if op == "ne":
        return result(not _equal(found, wanted))
    if op in ("gt", "ge", "lt", "le"):
        if not (_is_number(found) and _is_number(wanted)):
            return Outcome(UNKNOWN, "not_comparable")
        return result(
            {
                "gt": found > wanted,
                "ge": found >= wanted,
                "lt": found < wanted,
                "le": found <= wanted,
            }[op]
        )
    if op in ("in", "not-in"):
        member = any(_equal(found, item) for item in wanted)
        return result(member if op == "in" else not member)
    if op == "contains":
        if isinstance(found, list):
            return result(any(_equal(item, wanted) for item in found))
        if isinstance(found, str) and isinstance(wanted, str):
            return result(wanted in found)
        return result(False)
    # glob, regex, regex-case
    if not isinstance(found, str):
        return result(False)
    if len(found) > model.LIMITS.found_string_length:
        return Outcome(UNKNOWN, "value_too_long")
    if op == "glob":
        return result(fnmatch.fnmatchcase(found, wanted))
    return result(node.pattern.match(found) is not None)


# ----------------------------------------------------------------- checks
def _required_tags(node: CheckNode, row: Dict[str, Any], ctx: Context) -> Outcome:
    if ctx.tags_unknown(row):
        return Outcome(UNKNOWN, "tags_not_read")
    tags = normalize_tags(row.get("tags"))
    missing_only = bool(node.spec.get("missing_only"))
    failures = []
    for rule in node.spec["_rules"]:
        key = rule["key"]
        if key not in tags:
            failures.append(
                {"type": "required-tags", "key": key, "problem": "missing tag"}
            )
            continue
        if missing_only:
            continue
        reason = check_value(rule, str(tags[key]))
        if reason:
            failures.append({"type": "required-tags", "key": key, "problem": reason})
    return Outcome(FALSE, failures=failures) if failures else Outcome(TRUE)


def _allowed_regions(node: CheckNode, row: Dict[str, Any], ctx: Context) -> Outcome:
    region = str(row.get("region") or "")
    allowed = region in node.spec["regions"] or (
        region == "global" and node.spec.get("allow_global", True)
    )
    if allowed:
        return Outcome(TRUE)
    return Outcome(
        FALSE, failures=[{"type": "allowed-regions", "problem": "region not allowed"}]
    )


def _name_pattern(node: CheckNode, row: Dict[str, Any], ctx: Context) -> Outcome:
    if node.key is None:
        found: Any = model.name(row) or None
        key_text = None
    else:
        if node.key.is_raw and model.identity_only(row):
            return Outcome(UNKNOWN, "identity_only")
        if node.key.tag is not None and ctx.tags_unknown(row):
            return Outcome(UNKNOWN, "tags_not_read")
        found = node.key.get(row)
        key_text = node.key.text
    if isinstance(found, str) and node.pattern.fullmatch(found):
        return Outcome(TRUE)
    failure = {"type": "name-pattern", "problem": "pattern not matched"}
    if key_text:
        failure = {
            "type": "name-pattern",
            "key": key_text,
            "problem": "pattern not matched",
        }
    if ctx.show_values:
        failure["value"] = found
    return Outcome(FALSE, failures=[failure])


def _names(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _related(node: CheckNode, row: Dict[str, Any], ctx: Context) -> Outcome:
    spec = node.spec
    # 1. this row's own key
    if node.my_key.is_raw and model.identity_only(row):
        return Outcome(UNKNOWN, "identity_only")
    mine = node.my_key.get(row)
    if mine is None:
        return Outcome(UNKNOWN, "field_missing")
    account, region = model.account(row), str(row.get("region") or "")
    # 2. the listing of the related rows was not read here
    if ctx.unit_unread(account, spec["listing"], region):
        return Outcome(UNKNOWN, "listing_not_read")
    expect = spec.get("expect", "any")
    rows = ctx.related_rows(account, region, spec["rows"])
    if rows is None:  # more related rows than the limit
        return Outcome(UNKNOWN, "field_missing")
    named = False
    lacking = False
    for other in rows:
        if node.their_key.is_raw and model.identity_only(other):
            lacking = True
            continue
        theirs = node.their_key.get(other)
        if theirs is None:
            lacking = True
            continue
        if mine in _names(theirs):
            named = True
            break
    # 3. a related row names it
    if named:
        if expect == "any":
            return Outcome(TRUE)
        return Outcome(
            FALSE,
            failures=[{"type": "related", "problem": "a related row names it"}],
        )
    # 4. nothing names it, and a related row lacks its key
    if lacking:
        return Outcome(UNKNOWN, "field_missing")
    # 5.
    if expect == "none":
        return Outcome(TRUE)
    return Outcome(
        FALSE, failures=[{"type": "related", "problem": "no related row names it"}]
    )


def _require(node: RequireNode, row: Dict[str, Any], ctx: Context) -> Outcome:
    reasons = []
    for key in node.keys:
        if key.is_raw and model.identity_only(row):
            reasons.append("identity_only")
        elif key.tag is not None and ctx.tags_unknown(row):
            reasons.append("tags_not_read")
        elif key.get(row) is None:
            reasons.append("field_missing")
    if reasons:
        return Outcome(UNKNOWN, first_reason(reasons))
    return Outcome(TRUE)


_CHECKS = {
    "required-tags": _required_tags,
    "allowed-regions": _allowed_regions,
    "name-pattern": _name_pattern,
    "related": _related,
}


# ----------------------------------------------------------------- groups
def _group(node: GroupNode, row: Dict[str, Any], ctx: Context) -> Outcome:
    if node.op == "or":
        outcomes = [evaluate_outcome(child, row, ctx) for child in node.children]
        if any(o.value is TRUE for o in outcomes):
            return Outcome(TRUE)
        unknown = [o.reason for o in outcomes if o.value is UNKNOWN]
        if unknown:
            return Outcome(UNKNOWN, first_reason(unknown))
        best = max(outcomes, key=lambda o: o.progress)  # first of the ties
        return Outcome(FALSE, failures=best.failures, progress=best.progress)
    inner = _and(node.children, row, ctx)
    if node.op == "and":
        return inner
    # not: true when the "and" of its entries is false
    if inner.value is UNKNOWN:
        return inner
    if inner.value is FALSE:
        return Outcome(TRUE)
    return Outcome(FALSE, failures=[{"type": "not", "problem": "condition not met"}])


def _and(children, row: Dict[str, Any], ctx: Context) -> Outcome:
    unknown: List[str] = []
    required: set = set()
    true_count = 0
    for child in children:
        if isinstance(child, RequireNode):
            # evaluated only when the entries before it are true (spec 9.4)
            if unknown:
                continue
            outcome = _require(child, row, ctx)
            if outcome.value is UNKNOWN:
                # the fact could not be read: the rest of the "and" is not
                # evaluated (spec 9.2, 9.4)
                return outcome
            required.update(k.text for k in child.keys)
        else:
            outcome = evaluate_outcome(child, row, ctx)
            if (
                outcome.value is UNKNOWN
                and outcome.reason == "not_convertible"
                and isinstance(child, ValueNode)
                and child.key.text in required
            ):
                # a required value that cannot be read as needed (spec 9.4)
                outcome = Outcome(UNKNOWN, "field_missing")
        if outcome.value is FALSE:
            return Outcome(
                FALSE,
                failures=outcome.failures,
                progress=true_count + outcome.progress,
            )
        if outcome.value is UNKNOWN:
            unknown.append(outcome.reason)
        else:
            true_count += 1
    if unknown:
        return Outcome(UNKNOWN, first_reason(unknown))
    return Outcome(TRUE, progress=true_count)


# ----------------------------------------------------------------- entry
def evaluate_outcome(node: Any, row: Dict[str, Any], ctx: Context) -> Outcome:
    if isinstance(node, ValueNode):
        return _value(node, row, ctx)
    if isinstance(node, GroupNode):
        return _group(node, row, ctx)
    if isinstance(node, RequireNode):
        return _require(node, row, ctx)
    return _CHECKS[node.type](node, row, ctx)


def evaluate(node: Any, row: Dict[str, Any], ctx: Context) -> Tuple[Tri, Optional[str]]:
    """(value, reason) of one compiled entry on one row."""
    outcome = evaluate_outcome(node, row, ctx)
    return outcome.value, outcome.reason


def evaluate_all(nodes, row: Dict[str, Any], ctx: Context) -> Outcome:
    """The Kleene ``and`` of a list of entries (``check``, ``filters``), with
    the index of each failed top-level entry in its failures."""
    unknown: List[str] = []
    failures: List[Dict[str, Any]] = []
    any_false = False
    for index, node in enumerate(nodes):
        outcome = evaluate_outcome(node, row, ctx)
        if outcome.value is FALSE:
            any_false = True
            failures.extend({"check": index, **f} for f in outcome.failures)
        elif outcome.value is UNKNOWN:
            unknown.append(outcome.reason)
    if any_false:
        return Outcome(FALSE, failures=failures)
    if unknown:
        return Outcome(UNKNOWN, first_reason(unknown))
    return Outcome(TRUE)


# ----------------------------------------------------------------- trace
_VERDICT = {"TRUE": "true", "FALSE": "false", "UNKNOWN": "unknown"}


def verdict_node(part: str, kind: str, outcome_value, reason=None, key=None):
    """One node of a trace (spec 11.5): kind, key (never a value), verdict."""
    node: Dict[str, Any] = {"part": part, "kind": kind}
    if key is not None:
        node["key"] = key
    node["verdict"] = _VERDICT[outcome_value.name]
    if outcome_value is UNKNOWN and reason:
        node["reason"] = reason
    return node


def trace(node: Any, row: Dict[str, Any], ctx: Context, part: str) -> Dict[str, Any]:
    """The trace of one compiled entry on one row (every child evaluated)."""
    outcome = evaluate_outcome(node, row, ctx)
    if isinstance(node, ValueNode):
        return verdict_node(part, "value", outcome.value, outcome.reason, node.key.text)
    if isinstance(node, RequireNode):
        key = node.keys[0].text if len(node.keys) == 1 else None
        return verdict_node(part, "require", outcome.value, outcome.reason, key)
    if isinstance(node, GroupNode):
        found = verdict_node(part, node.op, outcome.value, outcome.reason)
        found["children"] = [trace(child, row, ctx, part) for child in node.children]
        return found
    key = None
    if node.type == "name-pattern" and node.key is not None:
        key = node.key.text
    elif node.type == "related":
        key = node.my_key.text
    return verdict_node(part, node.type, outcome.value, outcome.reason, key)
