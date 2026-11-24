"""Shared words, limits and objects of the policy engine (v15-policy-spec.md).

Every policy module imports from here: the loader builds :class:`Policy`,
:class:`PolicySet` and :class:`Waiver`; the engine evaluates them; waivers,
baseline and the outputs read the result the engine returns.

Interfaces other packages provide (the engine calls them when present):

* ``inventag.policy.waivers.apply(findings, waivers, now, known_policies)
  -> (findings, unused)``: spec 2.5 and 10.1. ``known_policies`` are the ids
  of every loaded, enabled policy (a waiver for another id is "unknown
  policy"). ``findings`` are the engine's finding dicts (sorted);
  ``waivers`` a list of :class:`Waiver`; ``now`` an aware ``datetime``. It
  returns the findings with ``fail`` turned into ``waived`` (with ``waiver``)
  or carrying ``waiver_expired``, and the ``unused_waivers`` entries.
* ``inventag.policy.baseline.evaluate(policy, entry_index, selected_rows,
  snapshot, baseline, units) -> BaselineOutcome``: spec 2.3.1. ``row_results``
  maps ``resource(row)`` to ``(value, problem)`` for the selected rows of the
  snapshot (value: ``True``, ``False``); ``removed`` lists the baseline rows
  that fail as ``removed`` (each a row dict).

Nothing here reads a clock, a file or the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Optional, Tuple

SEVERITIES: Tuple[str, ...] = ("info", "low", "medium", "high", "critical")
RESULTS: Tuple[str, ...] = ("pass", "fail", "waived", "not_evaluated")
# Reasons of a not-evaluated row, in the order of spec 9.1: when several apply
# to one row, the first of this list is the finding's reason.
REASONS: Tuple[str, ...] = (
    "identity_only",
    "listing_not_read",
    "field_missing",
    "tags_not_read",
    "not_comparable",
    "not_convertible",
    "value_too_long",
)
UNIT_REASON = "listing_not_read"
# Why a waiver changed no finding (spec 2.5, 3.3; "superseded": amendment 2).
UNUSED_WHY: Tuple[str, ...] = ("no match", "expired", "unknown policy", "superseded")
CHECK_TYPES: Tuple[str, ...] = (
    "value",
    "required-tags",
    "allowed-regions",
    "name-pattern",
    "baseline",
    "related",
    "require",
)
OPERATORS: Tuple[str, ...] = (
    "eq",
    "ne",
    "gt",
    "ge",
    "lt",
    "le",
    "in",
    "not-in",
    "contains",
    "glob",
    "regex",
    "regex-case",
)
VALUE_TYPES: Tuple[str, ...] = (
    "integer",
    "size",
    "normalize",
    "age",
    "expiration",
    "text",
)
SPECIAL_VALUES: Tuple[str, ...] = ("absent", "present", "empty", "not-null")
KINDS: Tuple[str, ...] = ("policy", "policy-set", "waivers")
FORBIDDEN_FIELDS: Tuple[str, ...] = ("actions", "mode", "notify", "remediate")
NO_ACTIONS = "InvenTag never changes resources; a policy has no actions."
PLACEHOLDERS: Tuple[str, ...] = (
    "name",
    "resource",
    "account",
    "region",
    "service",
    "resource_type",
    "policy",
)
ID_PATTERN = r"[A-Z][A-Z0-9]{1,7}-[0-9]{3,5}"
SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class Limits:
    file_bytes: int = 256 * 1024
    policies_per_run: int = 500
    checks_per_policy: int = 20
    entries_per_group: int = 20
    nesting_depth: int = 5
    key_length: int = 200
    pattern_length: int = 200
    found_string_length: int = 4096
    message_length: int = 300
    references: int = 10
    related_rows_per_place: int = 50_000
    waiver_days_ahead: int = 366


LIMITS = Limits()


@dataclass(frozen=True)
class Policy:
    """One ``kind: policy`` document, validated."""

    id: str
    name: str
    severity: str
    check: Tuple[Dict[str, Any], ...]
    version: int = 1
    resource: Dict[str, Any] = field(default_factory=dict)
    require: Tuple[str, ...] = ()
    message: Optional[str] = None
    references: Tuple[str, ...] = ()
    enabled: bool = True
    description: str = ""
    file: str = ""  # as given, relative to the policy directory, with "/"
    sha256: str = ""  # of the file bytes
    id_line: Optional[int] = None  # line of spec.id (SARIF region)
    severity_overridden_by: Optional[str] = None  # set name


@dataclass(frozen=True)
class PolicySet:
    """One ``kind: policy-set`` document, validated (not yet resolved)."""

    name: str
    policies: Tuple[str, ...] = ()
    include: Tuple[str, ...] = ()
    severity_overrides: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    file: str = ""


@dataclass(frozen=True)
class Waiver:
    """One entry of ``spec.waivers`` of a ``kind: waivers`` document."""

    policy: str
    resource: str
    reason: str
    approved_by: str
    expires: date
    account: Optional[str] = None
    file: str = ""


# ------------------------------------------------------------ row helpers
def account(row: Dict[str, Any]) -> str:
    """``source_account_id``, else ``account_id``, else ``""`` (spec 1)."""
    return str(row.get("source_account_id") or row.get("account_id") or "")


def resource(row: Dict[str, Any]) -> str:
    """``arn`` if not empty, else ``<service>/<resource_type>/<resource_id>``."""
    arn = row.get("arn")
    if arn:
        return str(arn)
    return "/".join(
        str(row.get(k) or "") for k in ("service", "resource_type", "resource_id")
    )


def name(row: Dict[str, Any]) -> str:
    """``resource_name``, else ``resource_id`` (spec 1). ``get_field`` falls
    back to the ID only for some resource types, so it is not used here."""
    value = row.get("resource_name") or row.get("resource_id")
    return "" if value is None else str(value)


def identity_only(row: Dict[str, Any]) -> bool:
    """``detail_level == "identity"`` or ``raw_data`` missing or not a mapping."""
    return row.get("detail_level") == "identity" or not isinstance(
        row.get("raw_data"), dict
    )
