"""Six fixed FinOps checks (FIN-001 to FIN-006) on the rows of a scan.

Since v1.5.0 the checks are the policy set ``finops-checks``
(``inventag/policy/builtin/finops-checks``) and this module is its caller:
it hands the rows to the policy engine and writes the engine's result in the
shape of v1.4.x, byte for byte (the sheet and the ``finops_checks`` key did not
change). Pure: rows, the listings not read (``units_not_read``) and the run's
start time in; sorted findings out. No AWS call, no clock, no file write, and
the rows are not changed.

What is done here and not by the engine (each point has a case in
``tests/unit/finops/golden/checks-v143.json``, made by the v1.4.3 code):

* The engine is given copies of the rows. A copy gets a canonical label when
  v1.4.x recognised the row (by label, or by ARN for a row known by identity
  only) and a neutral label when it did not; a field v1.4.x read as "not on the
  row" (an empty string, a wrong type, a date it could not parse) is left out of
  the copy; a target group known by identity only is hidden from the related
  rows (v1.4.x ignored it). The copy's name is the row's number, which is how
  a finding finds its row again.
* The words of the sheet: ``Observed`` texts and the ``not_evaluated`` messages.
* FIN-006 and the Tagging API: v1.4.x decided "tags not read" after it had found
  a missing key, and counted a global row as unread when any Tagging API
  listing of its account failed. The engine is given no ``tagging-api`` unit,
  and the rule is applied here to the failed rows.
* The engine is given only the ``elbv2`` listing units: it reads "elb" and
  "elbv2" as one service, v1.4.x did not.
* The unit lines, one per unread listing, from the units as given (FIN-006 has
  one per unit of any source).
* Without a start time FIN-003 is ``not_evaluated`` (the clock is never read).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..discovery.arn_utils import parse_arn

SCHEMA_VERSION = 1
# FIN-003: a snapshot that started more than this many days before the run
# (the number is in the policy file finops-checks/fin-003.yaml).
SNAPSHOT_AGE_DAYS = 90
GLOBAL_REGION = "global"
POLICY_NAME = "finops-cost-allocation"
SET_NAME = "finops-checks"

CHECKS: Dict[str, str] = {
    "FIN-001": "EBS volume with no attachment",
    "FIN-002": "Elastic IP with no association",
    "FIN-003": f"EBS snapshot older than {SNAPSHOT_AGE_DAYS} days",
    "FIN-004": "EC2 instance in the stopped state",
    "FIN-005": "Load balancer with no target group or instance",
    "FIN-006": "Cost allocation tag key missing",
}

FAIL = "fail"
NOT_EVALUATED = "not_evaluated"
PASS = "pass"

IDENTITY_ONLY = "identity_only"
FIELD_MISSING = "field_missing"
TAGS_NOT_READ = "tags_not_read"
LISTING_NOT_READ = "listing_not_read"

# The discovery services whose listings give the rows of each check.
_LISTINGS = {
    "FIN-001": ("ec2",),
    "FIN-002": ("vpc",),
    "FIN-003": ("ec2",),
    "FIN-004": ("ec2",),
    "FIN-005": ("elb", "elbv2"),
}

# (service, resource type) of a full row, per kind.
_ROW_KINDS = {
    ("ec2", "volume"): "volume",
    ("vpc", "elasticip"): "address",
    ("ec2", "snapshot"): "snapshot",
    ("ec2", "instance"): "instance",
    ("elbv2", "loadbalancerv2"): "lb_v2",
    ("elb", "loadbalancer"): "lb_classic",
    ("elbv2", "targetgroup"): "target_group",
}
# The labels the policy files select (the engine compares them exactly).
_LABELS = {
    "volume": ("EC2", "Volume"),
    "address": ("VPC", "ElasticIP"),
    "snapshot": ("EC2", "Snapshot"),
    "instance": ("EC2", "Instance"),
    "lb_v2": ("ELBV2", "LoadBalancerV2"),
    "lb_classic": ("ELB", "LoadBalancer"),
    "target_group": ("ELBV2", "TargetGroup"),
}
_KIND_CHECK = {
    "volume": "FIN-001",
    "address": "FIN-002",
    "snapshot": "FIN-003",
    "instance": "FIN-004",
    "lb_v2": "FIN-005",
    "lb_classic": "FIN-005",
}
# "<field> is not on the row" of a not_evaluated row, per kind.
_FIELD = {
    "volume": "State",
    "address": "PublicIp",
    "snapshot": "StartTime",
    "instance": "State",
    "lb_v2": "LoadBalancerArn",
    "lb_classic": "Instances",
}
_NEUTRAL = "(not checked)"

_policy_cache: List[Any] = []


def builtin_policy():
    """The built-in ``finops-cost-allocation`` tag policy (never a user copy)."""
    if not _policy_cache:
        from ..templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry

        registry = TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])
        _policy_cache.append(registry.resolve(POLICY_NAME))
    return _policy_cache[0]


def parse_time(value: Any) -> Optional[dt.datetime]:
    """A time as AWS listings give it (datetime or ISO text), in UTC; else None."""
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _account(row: Dict[str, Any]) -> str:
    return _text(row.get("source_account_id") or row.get("account_id"))


def _identity_kind(row: Dict[str, Any]) -> Optional[str]:
    """The kind of a row known by identity only, read from its ARN."""
    parts = parse_arn(_text(row.get("arn")))
    if not parts:
        return None
    resource = parts["resource"]
    if parts["service"] == "ec2":
        for prefix, kind in (
            ("volume/", "volume"),
            ("elastic-ip/", "address"),
            ("snapshot/", "snapshot"),
            ("instance/", "instance"),
        ):
            if resource.startswith(prefix):
                return kind
    if parts["service"] == "elasticloadbalancing" and resource.startswith(
        "loadbalancer/"
    ):
        rest = resource[len("loadbalancer/") :]
        return "lb_v2" if "/" in rest else "lb_classic"
    return None


def _labels(row: Dict[str, Any]) -> Tuple[str, str]:
    return (
        _text(row.get("service")).lower(),
        _text(row.get("resource_type")).lower(),
    )


def _kind(row: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    """(kind, known by identity only) of a row."""
    if _text(row.get("detail_level")) == "identity":
        return _identity_kind(row), True
    return _ROW_KINDS.get(_labels(row)), False


# ------------------------------------------------------- rows for the engine
def _usable(raw: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """A copy of ``raw_data`` without the fields v1.4.x read as not on the row."""
    raw = dict(raw)

    def drop_unless(key: str, good: bool) -> None:
        if not good:
            raw.pop(key, None)

    if kind == "volume":
        drop_unless("State", bool(raw.get("State")))
    elif kind == "address":
        drop_unless("PublicIp", bool(raw.get("PublicIp")))
        drop_unless("AssociationId", bool(raw.get("AssociationId")))
    elif kind == "snapshot":
        started = parse_time(raw.get("StartTime"))
        if started is None:
            raw.pop("StartTime", None)
        else:
            raw["StartTime"] = started.isoformat()
    elif kind == "instance":
        state = raw.get("State")
        drop_unless("State", isinstance(state, dict) and bool(state.get("Name")))
    elif kind == "lb_v2":
        drop_unless("LoadBalancerArn", bool(raw.get("LoadBalancerArn")))
    elif kind == "lb_classic":
        drop_unless("Instances", isinstance(raw.get("Instances"), list))
    elif kind == "target_group":
        drop_unless("LoadBalancerArns", isinstance(raw.get("LoadBalancerArns"), list))
    return raw


def _engine_row(number: int, row: Dict[str, Any]) -> Dict[str, Any]:
    """The copy of ``row`` the engine evaluates (see the module docstring)."""
    copy = dict(row)
    copy["resource_name"] = str(number)  # the finding's name: which row it is
    kind, identity = _kind(row)
    if kind is not None:
        copy["service"], copy["resource_type"] = _LABELS[kind]
        if not identity:
            raw = row.get("raw_data")
            copy["raw_data"] = _usable(raw if isinstance(raw, dict) else {}, kind)
    elif _labels(row) in _ROW_KINDS:
        # recognised by label but not by what it is: v1.4.x did not check it
        # (an identity-only row with an unreadable ARN, or a target group known
        # by identity only, which names no load balancer).
        copy["resource_type"] = _NEUTRAL
    return copy


def _engine_snapshot(rows: List[Dict[str, Any]], units: List[Dict[str, Any]]):
    # Only the elbv2 listing changes a verdict (FIN-005's related rows). The
    # engine reads "elb" and "elbv2" as one service (``canonical_service``),
    # v1.4.x did not, so an "elb" unit is not given to it; the unit lines of
    # the sheet are written below, not by the engine.
    shown = [
        u
        for u in units
        if u.get("source") == "service-api" and u.get("service") == "elbv2"
    ]
    return {
        "metadata": {"tags": {"units_not_read": shown}},
        "resources": [_engine_row(i, row) for i, row in enumerate(rows)],
    }


# ------------------------------------------------------------ the sheet's words
def _finding(policy, result, reason, row, message) -> Dict[str, str]:
    return {
        "policy": policy,
        "result": result,
        "reason": reason,
        "account": _account(row),
        "region": _text(row.get("region")),
        "service": _text(row.get("service")),
        "resource_type": _text(row.get("resource_type")),
        "resource": _text(row.get("resource_id") or row.get("id")),
        "name": _text(row.get("resource_name")),
        "message": message,
    }


def _unit_finding(policy: str, unit: Dict[str, Any]) -> Dict[str, str]:
    service, region = _text(unit.get("service")), _text(unit.get("region"))
    return {
        "policy": policy,
        "result": NOT_EVALUATED,
        "reason": LISTING_NOT_READ,
        "account": _text(unit.get("account")),
        "region": region,
        "service": service,
        "resource_type": "",
        "resource": "",
        "name": "",
        "message": (
            f"{service} listing in {region} not read ({_text(unit.get('outcome'))})"
        ),
    }


def _missing_message(kind: str, copy: Dict[str, Any]) -> str:
    if kind == "lb_v2" and (copy.get("raw_data") or {}).get("LoadBalancerArn"):
        return "LoadBalancerArns is not on a target group row"
    return f"{_FIELD[kind]} is not on the row"


def _observed(fail: Dict[str, Any], kind: Optional[str], row) -> str:
    policy = fail["policy"]
    if policy == "FIN-006":
        keys = [
            d["key"]
            for d in fail.get("details", [])
            if d.get("problem") == "missing tag"
        ]
        return "missing: " + ", ".join(keys)
    if policy == "FIN-003":
        started = parse_time((row.get("raw_data") or {}).get("StartTime"))
        return f"started {started:%Y-%m-%d}"
    return {
        "volume": "no attachment",
        "address": "no association",
        "instance": "state stopped",
        "lb_v2": "no target group names it",
        "lb_classic": "lists no instance",
    }[kind or ""]


def _tags_read(row: Dict[str, Any], tags_failed) -> bool:
    account, region = _account(row), _text(row.get("region"))
    if region == GLOBAL_REGION:
        return not any(a == account for a, _ in tags_failed)
    return (account, region) not in tags_failed


def _row_finding(found, row, copy, kind, ctx) -> Optional[Dict[str, str]]:
    """The v1.4.x finding of one engine finding (None for a pass)."""
    policy, result, reason = found["policy"], found["result"], found.get("reason", "")
    if policy == "FIN-003" and reason != IDENTITY_ONLY and ctx["run_started"] is None:
        return _finding(
            policy,
            NOT_EVALUATED,
            FIELD_MISSING,
            row,
            "the run has no start time",
        )
    if result == PASS:
        return None
    if result == FAIL:
        if policy == "FIN-006" and not _tags_read(row, ctx["tags_failed"]):
            return _finding(
                policy,
                NOT_EVALUATED,
                TAGS_NOT_READ,
                row,
                f"tags of {_text(row.get('region'))} not read in this run",
            )
        return _finding(policy, FAIL, "", row, _observed(found, kind, row))
    if reason == IDENTITY_ONLY:
        message = "known by identity only (Tagging API)"
    elif reason == LISTING_NOT_READ:
        message = "elbv2 listing not read in this region"
    else:
        reason = FIELD_MISSING
        place = (_account(row), _text(row.get("region")))
        if kind == "lb_v2" and place in ctx["failed_elbv2"]:
            # v1.4.x asked first whether the listing was read
            reason, message = LISTING_NOT_READ, "elbv2 listing not read in this region"
        else:
            message = _missing_message(kind, copy)
    return _finding(policy, NOT_EVALUATED, reason, row, message)


def _sort_key(finding: Dict[str, str]) -> tuple:
    return (
        finding["policy"],
        finding["account"],
        finding["region"],
        finding["resource"],
        finding["service"],
        finding["reason"],
        finding["message"],
    )


def run_checks(
    rows: Iterable[Dict[str, Any]],
    units_not_read: Iterable[Dict[str, Any]],
    run_started: Optional[dt.datetime],
    policy=None,
) -> Dict[str, Any]:
    """Run FIN-001 to FIN-006. ``run_started`` must carry a time zone; with
    None, FIN-003 is ``not_evaluated`` (the clock is never read).

    ``policy`` is accepted for callers of v1.4.x and ignored: the keys of
    FIN-006 are those of the built-in tag policy ``finops-cost-allocation``."""
    from ..policy import builtin, engine

    if run_started is not None and (
        not isinstance(run_started, dt.datetime) or run_started.tzinfo is None
    ):
        raise ValueError("run_started must be a datetime with a time zone")
    rows = [r for r in rows if isinstance(r, dict)]
    units = sorted(
        (u for u in units_not_read if isinstance(u, dict)),
        key=lambda u: tuple(_text(u.get(k)) for k in ("account", "region", "service")),
    )
    ctx = {
        "run_started": run_started,
        "failed_elbv2": {
            (_text(u.get("account")), _text(u.get("region")))
            for u in units
            if u.get("source") == "service-api" and u.get("service") == "elbv2"
        },
        "tags_failed": {
            (_text(u.get("account")), _text(u.get("region")))
            for u in units
            if u.get("source") == "tagging-api"
        },
    }
    snapshot = _engine_snapshot(rows, units)
    result = engine.evaluate(
        snapshot,
        builtin.load_set(SET_NAME),
        now=run_started or dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc),
        include_pass=True,
        inventag_version="",
    )
    findings: List[Dict[str, str]] = []
    passed = {policy_id: 0 for policy_id in CHECKS}
    for found in result["findings"]:
        number = int(found["name"])
        row, copy = rows[number], snapshot["resources"][number]
        kind = _kind(row)[0]
        mine = _row_finding(found, row, copy, kind, ctx)
        if mine is None:
            passed[found["policy"]] += 1
        else:
            findings.append(mine)

    for unit in units:
        if unit.get("source") == "service-api":
            for policy_id, services in _LISTINGS.items():
                if unit.get("service") in services:
                    findings.append(_unit_finding(policy_id, unit))
        findings.append(_unit_finding("FIN-006", unit))
    findings.sort(key=_sort_key)

    summary = []
    for policy_id, title in CHECKS.items():
        mine = [f for f in findings if f["policy"] == policy_id]
        summary.append(
            {
                "policy": policy_id,
                "check": title,
                "fail": sum(1 for f in mine if f["result"] == FAIL),
                "not_evaluated": sum(1 for f in mine if f["result"] == NOT_EVALUATED),
                PASS: passed[policy_id],
            }
        )
    return {"schema_version": SCHEMA_VERSION, "summary": summary, "findings": findings}
