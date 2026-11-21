"""Six fixed FinOps checks (FIN-001 to FIN-006) on the rows of a scan.

Pure: rows, the listings not read (``units_not_read``) and the run's start
time in; sorted findings out. No AWS call, no clock, no file write, and the
rows are not changed. The result words follow the v1.5.0 policy spec:
``fail`` and ``not_evaluated`` are listed, ``pass`` is counted. A gap in the
data is ``not_evaluated`` with a reason, never a pass.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..discovery.arn_utils import parse_arn
from ..templating.tag_policy import _in_scope, evaluate

SCHEMA_VERSION = 1
# FIN-003: a snapshot that started more than this many days before the run.
SNAPSHOT_AGE_DAYS = 90
GLOBAL_REGION = "global"
POLICY_NAME = "finops-cost-allocation"

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
UNITS_NOT_READ = "units_not_read"

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
_KIND_CHECK = {
    "volume": "FIN-001",
    "address": "FIN-002",
    "snapshot": "FIN-003",
    "instance": "FIN-004",
    "lb_v2": "FIN-005",
    "lb_classic": "FIN-005",
}

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


def _kind(row: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    """(kind, known by identity only) of a row."""
    if _text(row.get("detail_level")) == "identity":
        return _identity_kind(row), True
    key = (
        _text(row.get("service")).lower(),
        _text(row.get("resource_type")).lower(),
    )
    return _ROW_KINDS.get(key), False


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
        "reason": UNITS_NOT_READ,
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


def _missing(field: str) -> Tuple[str, str, str]:
    return NOT_EVALUATED, FIELD_MISSING, f"{field} is not on the row"


def _volume(raw, _row, _ctx):
    state = raw.get("State")
    if not state:
        return _missing("State")
    return (FAIL, "", "no attachment") if state == "available" else None


def _address(raw, _row, _ctx):
    # A listed address always has PublicIp; AssociationId is absent (or empty)
    # when the address is not associated, so its absence is the fact itself.
    if not raw.get("PublicIp"):
        return _missing("PublicIp")
    return None if raw.get("AssociationId") else (FAIL, "", "no association")


def _snapshot(raw, _row, ctx):
    started = parse_time(raw.get("StartTime"))
    if started is None:
        return _missing("StartTime")
    if ctx["run_started"] - started > dt.timedelta(days=SNAPSHOT_AGE_DAYS):
        return FAIL, "", f"started {started:%Y-%m-%d}"
    return None


def _instance(raw, _row, _ctx):
    state = raw.get("State")
    name = state.get("Name") if isinstance(state, dict) else None
    if not name:
        return _missing("State")
    return (FAIL, "", "state stopped") if name == "stopped" else None


def _lb_v2(raw, row, ctx):
    place = (_account(row), _text(row.get("region")))
    if place in ctx["failed_elbv2"]:
        return NOT_EVALUATED, UNITS_NOT_READ, "elbv2 listing not read in this region"
    arn = raw.get("LoadBalancerArn")
    if not arn:
        return _missing("LoadBalancerArn")
    if arn in ctx["named"].get(place, set()):
        return None
    if place in ctx["groups_without_list"]:
        return (
            NOT_EVALUATED,
            FIELD_MISSING,
            "LoadBalancerArns is not on a target group row",
        )
    return FAIL, "", "no target group names it"


def _lb_classic(raw, _row, _ctx):
    if "Instances" not in raw or not isinstance(raw.get("Instances"), list):
        return _missing("Instances")
    return None if raw["Instances"] else (FAIL, "", "lists no instance")


_JUDGES = {
    "volume": _volume,
    "address": _address,
    "snapshot": _snapshot,
    "instance": _instance,
    "lb_v2": _lb_v2,
    "lb_classic": _lb_classic,
}


def _context(rows: List[Dict[str, Any]], units, run_started) -> Dict[str, Any]:
    named: Dict[tuple, set] = {}
    groups_without_list = set()
    for row in rows:
        kind, identity = _kind(row)
        if kind != "target_group" or identity:
            continue
        place = (_account(row), _text(row.get("region")))
        arns = (row.get("raw_data") or {}).get("LoadBalancerArns")
        if not isinstance(arns, list):
            groups_without_list.add(place)
            continue
        named.setdefault(place, set()).update(_text(a) for a in arns)
    failed_elbv2 = {
        (_text(u.get("account")), _text(u.get("region")))
        for u in units
        if u.get("source") == "service-api" and u.get("service") == "elbv2"
    }
    tags_failed = {
        (_text(u.get("account")), _text(u.get("region")))
        for u in units
        if u.get("source") == "tagging-api"
    }
    return {
        "run_started": run_started,
        "named": named,
        "groups_without_list": groups_without_list,
        "failed_elbv2": failed_elbv2,
        "tags_failed": tags_failed,
    }


def _tags_read(row: Dict[str, Any], ctx) -> bool:
    account, region = _account(row), _text(row.get("region"))
    if region == GLOBAL_REGION:
        return not any(a == account for a, _ in ctx["tags_failed"])
    return (account, region) not in ctx["tags_failed"]


def _allocation_findings(rows, ctx, policy) -> Tuple[List[Dict[str, str]], int]:
    """FIN-006 through the tag-policy check of ``inventag templates``."""
    taggable = [
        row
        for row in rows
        if _text(row.get("source")) != "billing"
        and _in_scope(row, policy.spec.get("scope") or {})
    ]
    report = evaluate(taggable, policy)
    found, passed = [], 0
    for result in report.findings:
        if not result.missing:
            passed += 1
            continue
        row = result.resource
        if not _tags_read(row, ctx):
            found.append(
                _finding(
                    "FIN-006",
                    NOT_EVALUATED,
                    TAGS_NOT_READ,
                    row,
                    f"tags of {_text(row.get('region'))} not read in this run",
                )
            )
            continue
        found.append(
            _finding("FIN-006", FAIL, "", row, "missing: " + ", ".join(result.missing))
        )
    return found, passed


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
    run_started: dt.datetime,
    policy=None,
) -> Dict[str, Any]:
    """Run FIN-001 to FIN-006. ``run_started`` must carry a time zone."""
    if not isinstance(run_started, dt.datetime) or run_started.tzinfo is None:
        raise ValueError("run_started must be a datetime with a time zone")
    rows = [r for r in rows if isinstance(r, dict)]
    units = sorted(
        (u for u in units_not_read if isinstance(u, dict)),
        key=lambda u: tuple(_text(u.get(k)) for k in ("account", "region", "service")),
    )
    ctx = _context(rows, units, run_started.astimezone(dt.timezone.utc))
    findings: List[Dict[str, str]] = []
    passed = {policy_id: 0 for policy_id in CHECKS}

    for row in rows:
        kind, identity = _kind(row)
        policy_id = _KIND_CHECK.get(kind or "")
        if policy_id is None:
            continue
        if identity:
            findings.append(
                _finding(
                    policy_id,
                    NOT_EVALUATED,
                    IDENTITY_ONLY,
                    row,
                    "known by identity only (Tagging API)",
                )
            )
            continue
        raw = row.get("raw_data")
        verdict = _JUDGES[kind](raw if isinstance(raw, dict) else {}, row, ctx)
        if verdict is None:
            passed[policy_id] += 1
        else:
            findings.append(_finding(policy_id, *verdict[:2], row, verdict[2]))

    for unit in units:
        if unit.get("source") == "service-api":
            for policy_id, services in _LISTINGS.items():
                if unit.get("service") in services:
                    findings.append(_unit_finding(policy_id, unit))
        findings.append(_unit_finding("FIN-006", unit))

    allocation, passed["FIN-006"] = _allocation_findings(
        rows, ctx, policy or builtin_policy()
    )
    findings.extend(allocation)
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
