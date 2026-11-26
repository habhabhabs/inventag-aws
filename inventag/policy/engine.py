"""Evaluate policies on a saved snapshot (v15-policy-spec.md sections 1 to 3.2, 9).

``evaluate(snapshot, policies, waivers, baseline, now)`` is pure: no AWS call,
no network, no clock (``now`` comes in), no file. The result is the mapping of
spec 3.3; ``dumps`` writes it with sorted keys, two-space indent and a final
newline, so the same input gives the same bytes.

The rules about listings and tags that were not read are the change report's
(``state.delta_detector._PreviousUnread``, spec 8.1); they are not written a
second time here.
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
import string
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..discovery.service_filter import canonical_service
from ..state.delta_detector import _PreviousUnread
from ..templating.tag_policy import _in_scope
from . import filters, model
from .filters import FALSE, TRUE, UNKNOWN

_SEVERITY_RANK = {s: i for i, s in enumerate(model.SEVERITIES)}

# Discovery keys whose row label ``canonical_service`` does not reach by itself
# (``ComprehensiveAWSDiscovery._label_for``); a test checks the whole table.
_UNIT_LABELS = {"wafv2-cloudfront": "WAFV2"}


def unit_service(name: Any) -> str:
    """Comparison key of a unit's discovery key or a row's service label."""
    text = str(name or "")
    return canonical_service(_UNIT_LABELS.get(text, text))


# ----------------------------------------------------------------- inputs
def parse_now(value: Any) -> dt.datetime:
    """``YYYY-MM-DD`` (00:00 UTC of that day) or an ISO 8601 instant (spec 9.2)."""
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            raise ValueError("now must carry a time zone")
        return value.astimezone(dt.timezone.utc)
    return filters.parse_instant(value)


def _units(snapshot: Dict[str, Any]) -> Any:
    tags = (snapshot.get("metadata") or {}).get("tags") or {}
    return tags.get("units_not_read")


def _plain(row: Dict[str, Any], block: Dict[str, Any]) -> bool:
    """The five plain tests of spec 2.1.1."""

    def lower(items):
        return {str(i).lower() for i in items or []}

    services, types = lower(block.get("services")), lower(block.get("resource_types"))
    if services and str(row.get("service") or "").lower() not in services:
        return False
    rtype = str(row.get("resource_type") or "").lower()
    if types and rtype not in types:
        return False
    if rtype in lower(block.get("exclude_resource_types")):
        return False
    regions = block.get("regions")
    if regions and str(row.get("region") or "") not in regions:
        return False
    accounts = block.get("accounts")
    if accounts and model.account(row) not in accounts:
        return False
    return True


class _Snapshot:
    """The lookups every policy shares."""

    def __init__(self, snapshot: Dict[str, Any]):
        resources = snapshot.get("resources") or []
        self.rows: List[Dict[str, Any]] = [r for r in resources if isinstance(r, dict)]
        self.unread = _PreviousUnread(_units(snapshot), {})
        self.units: List[Dict[str, str]] = []
        for unit in _units(snapshot) or []:
            if not isinstance(unit, dict) or unit.get("source") != "service-api":
                continue
            key = (
                str(unit.get("account") or ""),
                canonical_service(unit.get("service")),
                str(unit.get("region") or ""),
            )
            if key in self.unread.service:
                self.units.append(
                    {
                        "account": key[0],
                        "service": str(unit.get("service")),
                        "region": key[2],
                        "outcome": self.unread.service[key],
                    }
                )
        self.by_place: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for row in self.rows:
            place = (model.account(row), str(row.get("region") or ""))
            self.by_place.setdefault(place, []).append(row)
        self._related: Dict[Tuple[str, str, int], Optional[List[Dict]]] = {}

    def tags_unknown(self, row: Dict[str, Any]) -> bool:
        return bool(self.unread.tags_reason(row, model.resource(row)))

    def unit_unread(self, account: str, listing: str, region: str) -> bool:
        return (account, canonical_service(listing), region) in self.unread.service

    def related_rows(self, account: str, region: str, block: Dict) -> Optional[List]:
        key = (account, region, id(block))
        if key not in self._related:
            rows = [
                r for r in self.by_place.get((account, region), []) if _plain(r, block)
            ]
            limit = model.LIMITS.related_rows_per_place
            self._related[key] = rows if len(rows) <= limit else None
        return self._related[key]


# ----------------------------------------------------------------- messages
def _describe(failure: Dict[str, Any]) -> str:
    problem = failure.get("problem", "")
    key = failure.get("key")
    if key and not problem.startswith(f"{key}:"):
        return f"{problem}: {key}"
    return problem


def _message(policy: model.Policy, row, result: str, reason, failures) -> str:
    if policy.message:
        values = {
            "name": model.name(row),
            "resource": model.resource(row),
            "account": model.account(row),
            "region": str(row.get("region") or ""),
            "service": str(row.get("service") or ""),
            "resource_type": str(row.get("resource_type") or ""),
            "policy": policy.id,
        }
        # Placeholders only: a format spec or conversion is refused at
        # validation and ignored here, so a value can never act as one.
        return "".join(
            literal + (values.get(field, "") if field is not None else "")
            for literal, field, _, _ in string.Formatter().parse(policy.message)
        )
    if result in ("fail", "waived"):
        return f"{policy.id}: " + "; ".join(_describe(f) for f in failures)
    if result == "not_evaluated":
        return f"{policy.id}: not evaluated ({reason})"
    if result == "out_of_scope":
        return f"{policy.id}: out of scope"
    return f"{policy.id}: pass"


def _finding(policy, row, result, reason=None, failures=None) -> Dict[str, Any]:
    finding = {
        "policy": policy.id,
        "result": result,
        "severity": policy.severity,
        "account": model.account(row),
        "region": str(row.get("region") or ""),
        "service": str(row.get("service") or ""),
        "resource_type": str(row.get("resource_type") or ""),
        "resource": model.resource(row),
        "name": model.name(row),
        "message": _message(policy, row, result, reason, failures or []),
    }
    if reason:
        finding["reason"] = reason
    if failures:
        finding["details"] = failures
    return finding


def _sort_key(finding: Dict[str, Any]) -> Tuple:
    return (
        finding["policy"],
        finding["account"],
        finding["region"],
        finding["resource"],
        finding.get("from", ""),
    )


def _zero() -> Dict[str, int]:
    return {"pass": 0, "fail": 0, "waived": 0, "not_evaluated": 0, "out_of_scope": 0}


def _tag_scopes(entries) -> List[Dict]:
    return [e["_scope"] for e in entries if isinstance(e, dict) and "_scope" in e]


# ----------------------------------------------------------------- policies
def _plain_trace(row: Dict[str, Any], block: Dict[str, Any]) -> List[Dict]:
    """The plain tests of ``resource`` as trace nodes (spec 11.5)."""
    nodes = []
    for kind, keys in (
        ("services", ("services",)),
        ("resource_types", ("resource_types", "exclude_resource_types")),
        ("regions", ("regions",)),
        ("accounts", ("accounts",)),
    ):
        part = {k: block[k] for k in keys if block.get(k)}
        if part:
            ok = filters.TRUE if _plain(row, part) else filters.FALSE
            nodes.append(filters.verdict_node("resource", kind, ok))
    return nodes


def _trace(policy, row, ctx, filter_nodes, require, check_nodes, result, reason=None):
    """One trace tree for one row (spec 11.5): a root "and" over every test."""
    found = _plain_trace(row, policy.resource)
    found += [filters.trace(n, row, ctx, "resource") for n in filter_nodes]
    if result == "out_of_scope":
        # the row was never checked: the resource nodes only (review F5)
        return {
            "part": "resource",
            "kind": "and",
            "verdict": "out_of_scope",
            "children": found,
        }
    if require.keys:
        found.append(filters.trace(require, row, ctx, "check"))
    found += [filters.trace(n, row, ctx, "check") for n in check_nodes]
    verdict = {"pass": "true", "not_evaluated": "unknown"}.get(result, "false")
    root: Dict[str, Any] = {"part": "check", "kind": "and", "verdict": verdict}
    if verdict == "unknown" and reason:
        root["reason"] = reason
    root["children"] = found
    return root


def _evaluate_policy(policy: model.Policy, snap: _Snapshot, ctx: filters.Context):
    """(findings including passes, counts, unit lines) of one policy."""
    block = policy.resource
    filter_nodes = [filters.compile_entry(e) for e in block.get("filters") or []]
    check_nodes = [filters.compile_entry(e) for e in policy.check]
    require = filters.RequireNode([filters.compile_key(k) for k in policy.require])
    scopes = _tag_scopes(policy.check)
    counts = _zero()
    findings: List[Dict[str, Any]] = []
    tracing = getattr(ctx, "trace", None)

    def out_of_scope(row):
        counts["out_of_scope"] += 1
        if tracing is not None and model.resource(row) in tracing["wanted"]:
            entry = _finding(policy, row, "out_of_scope")
            entry["trace"] = _trace(
                policy, row, ctx, filter_nodes, require, check_nodes, "out_of_scope"
            )
            tracing["out_of_scope"].append(entry)

    rows_of: List[Dict[str, Any]] = []

    def add(row, finding):
        findings.append(finding)
        rows_of.append(row)

    for row in snap.rows:
        if not _plain(row, block) or not all(_in_scope(row, s) for s in scopes):
            out_of_scope(row)
            continue
        selected = filters.evaluate_all(filter_nodes, row, ctx)
        if selected.value is FALSE:
            out_of_scope(row)
            continue
        if selected.value is UNKNOWN:
            add(row, _finding(policy, row, "not_evaluated", selected.reason))
            continue
        if require.keys:
            needed = filters.evaluate_outcome(require, row, ctx)
            if needed.value is UNKNOWN:
                add(row, _finding(policy, row, "not_evaluated", needed.reason))
                continue
        verdict = filters.evaluate_all(check_nodes, row, ctx)
        if verdict.value is TRUE:
            add(row, _finding(policy, row, "pass"))
        elif verdict.value is FALSE:
            add(row, _finding(policy, row, "fail", failures=verdict.failures))
        else:
            add(row, _finding(policy, row, "not_evaluated", verdict.reason))
    if tracing is not None:
        for f, row in zip(findings, rows_of):
            f["trace"] = _trace(
                policy,
                row,
                ctx,
                filter_nodes,
                require,
                check_nodes,
                f["result"],
                f.get("reason"),
            )
    for f in findings:
        counts[f["result"]] += 1
    return findings, counts, _unit_lines(policy, snap)


def _unit_lines(policy: model.Policy, snap: _Snapshot) -> List[Dict[str, str]]:
    """Spec 3.2 and 9.4: the unread listings the policy could select."""
    block = policy.resource
    listings = {unit_service(s) for s in block.get("listings") or []}
    services = {unit_service(s) for s in block.get("services") or []}
    lines = []
    for unit in snap.units:
        if block.get("accounts") and unit["account"] not in block["accounts"]:
            continue
        if block.get("regions") and unit["region"] not in block["regions"]:
            continue
        wanted = listings or services
        if wanted and unit_service(unit["service"]) not in wanted:
            continue
        lines.append(
            {
                "policy": policy.id,
                "account": unit["account"],
                "service": unit["service"],
                "region": unit["region"],
                "reason": model.UNIT_REASON,
                "outcome": unit["outcome"],
            }
        )
    return lines


def _has_baseline_check(policy: model.Policy) -> bool:
    def walk(entries):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") == "baseline":
                return True
            for group in ("and", "or", "not"):
                if group in entry and walk(entry[group]):
                    return True
        return False

    return walk(policy.check)


def _package(name: str):
    """A module of package P2 (``waivers``, ``baseline``)."""
    try:
        return importlib.import_module(f"{__package__}.{name}")
    except ModuleNotFoundError as error:
        if error.name != f"{__package__}.{name}":
            raise
        raise NotImplementedError(
            f"inventag.policy.{name} is not installed (package P2)"
        ) from None


# ----------------------------------------------------------------- result
def exit_code(
    result: Dict[str, Any],
    fail_on: Optional[str] = None,
    fail_on_not_evaluated: bool = False,
) -> int:
    """Spec 4: 8 wins over 7; waived and pass never change the code."""
    if fail_on_not_evaluated and (
        any(f["result"] == "not_evaluated" for f in result["findings"])
        or result["not_evaluated_units"]
        or result["not_evaluated_policies"]
    ):
        return 8
    if fail_on is not None:
        floor = _SEVERITY_RANK[fail_on]
        counted = result.get("_fails") or [
            f["severity"] for f in result["findings"] if f["result"] == "fail"
        ]
        if any(_SEVERITY_RANK[s] >= floor for s in counted):
            return 7
    return 0


def _snapshot_entry(snapshot, file, sha256) -> Dict[str, Any]:
    metadata = snapshot.get("metadata") or {}
    entry = {
        "file": file,
        "sha256": sha256,
        "timestamp": str(metadata.get("timestamp") or ""),
    }
    version = (metadata.get("tags") or {}).get("inventag_version")
    if version:
        entry["inventag_version"] = str(version)
    return entry


def evaluate(
    snapshot: Dict[str, Any],
    policies: Sequence[model.Policy],
    waivers: Sequence[model.Waiver] = (),
    baseline: Optional[Dict[str, Any]] = None,
    now: Any = None,
    *,
    fail_on: Optional[str] = None,
    fail_on_not_evaluated: bool = False,
    include_pass: bool = False,
    show_values: bool = False,
    snapshot_file: str = "",
    snapshot_sha256: str = "",
    baseline_file: str = "",
    baseline_sha256: str = "",
    inventag_version: Optional[str] = None,
    trace: bool = False,
    trace_resources: Sequence[str] = (),
    trace_resource: Optional[str] = None,
) -> Dict[str, Any]:
    """The result of spec 3.3 for ``policies`` on ``snapshot``."""
    if now is None:
        raise ValueError("now is required (the engine reads no clock)")
    now = parse_now(now)
    snap = _Snapshot(snapshot)
    ctx = filters.Context(
        now=now,
        tags_unknown=snap.tags_unknown,
        unit_unread=snap.unit_unread,
        related_rows=snap.related_rows,
        show_values=show_values,
    )
    # spec 11.5: with trace, each finding carries its tree, and the
    # out-of-scope rows asked for come back with theirs
    wanted = set(trace_resources) | ({trace_resource} if trace_resource else set())
    ctx.trace = {"wanted": wanted, "out_of_scope": []} if trace else None
    findings: List[Dict[str, Any]] = []
    units: List[Dict[str, str]] = []
    not_evaluated_policies: List[Dict[str, str]] = []
    policy_entries: List[Dict[str, Any]] = []
    for policy in sorted(policies, key=lambda p: p.id):
        entry: Dict[str, Any] = {
            "id": policy.id,
            "name": policy.name,
            "severity": policy.severity,
            "version": policy.version,
            "file": policy.file,
            "sha256": policy.sha256,
            "counts": _zero(),
        }
        if policy.id_line:
            entry["line"] = policy.id_line
        if policy.description:
            entry["description"] = policy.description
        if policy.references:
            entry["references"] = list(policy.references)
        if policy.severity_overridden_by:
            entry["severity_overridden_by"] = policy.severity_overridden_by
        policy_entries.append(entry)
        if not policy.enabled:
            continue
        if _has_baseline_check(policy):
            if baseline is None:
                not_evaluated_policies.append(
                    {"policy": policy.id, "reason": "no_baseline"}
                )
                continue
            found, counts, lines = _package("baseline").evaluate_policy(
                policy, snapshot, baseline, ctx, _evaluate_policy, snap
            )
        else:
            found, counts, lines = _evaluate_policy(policy, snap, ctx)
        entry["counts"] = counts
        findings.extend(found)
        units.extend(lines)

    findings.sort(key=_sort_key)
    unused: List[Dict[str, Any]] = []
    if waivers:
        known = sorted(p.id for p in policies if p.enabled)
        findings, unused = _package("waivers").apply(
            findings, list(waivers), now, known_policies=known
        )
        counts_by_policy: Dict[str, Dict[str, int]] = {}
        for f in findings:
            counts_by_policy.setdefault(f["policy"], {"fail": 0, "waived": 0})
            if f["result"] in ("fail", "waived"):
                counts_by_policy[f["policy"]][f["result"]] += 1
        for entry in policy_entries:
            if entry["id"] in counts_by_policy:
                entry["counts"].update(counts_by_policy[entry["id"]])

    by_result = _zero()
    for entry in policy_entries:
        for name, n in entry["counts"].items():
            by_result[name] += n
    fail_by_severity = {s: 0 for s in model.SEVERITIES}
    for f in findings:
        if f["result"] == "fail":
            fail_by_severity[f["severity"]] += 1
    listed = [f for f in findings if include_pass or f["result"] != "pass"]
    if trace and ctx.trace["out_of_scope"]:
        # spec 11.5: the rows asked for that no policy selected; never counted
        listed = sorted(listed + ctx.trace["out_of_scope"], key=_sort_key)
    units.sort(key=lambda u: (u["policy"], u["account"], u["service"], u["region"]))
    result = {
        "schema_version": model.SCHEMA_VERSION,
        "inventag_version": inventag_version or _running_version(),
        "now": now.date().isoformat(),
        "snapshot": _snapshot_entry(snapshot, snapshot_file, snapshot_sha256),
        "baseline": (
            _snapshot_entry(baseline, baseline_file, baseline_sha256)
            if baseline is not None
            else None
        ),
        "policies": policy_entries,
        "summary": {
            "rows": len(snap.rows),
            "by_result": by_result,
            "fail_by_severity": fail_by_severity,
            "exit_code": 0,
        },
        "findings": listed,
        "not_evaluated_units": units,
        "not_evaluated_policies": sorted(
            not_evaluated_policies, key=lambda p: p["policy"]
        ),
        "unused_waivers": sorted(
            unused, key=lambda w: (w["policy"], w["resource"], w["expires"])
        ),
    }
    fails = [f["severity"] for f in findings if f["result"] == "fail"]
    result["summary"]["exit_code"] = exit_code(
        dict(result, findings=findings, _fails=fails), fail_on, fail_on_not_evaluated
    )
    return result


def _running_version() -> str:
    from .._version import __version__

    return __version__


def dumps(result: Dict[str, Any]) -> str:
    """The result file's text: sorted keys, two-space indent, final newline."""
    return json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
