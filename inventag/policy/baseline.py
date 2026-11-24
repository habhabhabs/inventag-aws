"""Baseline checks (v15-policy-spec.md 2.3.1).

Rows of the snapshot and of the baseline are paired by the change report's
rule (``state.delta_detector.DeltaDetector``: same keys, same alignment, same
meaning of "modified"); no rule about identity or modification is written here.

``evaluate_policy`` is what ``engine.evaluate`` calls for a policy that has a
``baseline`` entry. The entry must stand at the top level of ``check``: the
other entries are evaluated by the engine's own function and the verdicts are
joined per row (a false entry makes the row fail; a row the engine could not
decide stays ``not_evaluated`` unless an entry is false).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Tuple

from ..state.delta_detector import DeltaDetector
from ..templating.errors import TemplateIssue
from ..templating.tag_policy import _in_scope
from . import engine, filters, model
from .filters import FALSE, UNKNOWN
from .schema import PolicyError


def _is_baseline(entry: Any) -> bool:
    return isinstance(entry, dict) and entry.get("type") == "baseline"


def _nested(entries) -> bool:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for group in ("and", "or", "not"):
            if group in entry and (
                any(_is_baseline(e) for e in entry[group]) or _nested(entry[group])
            ):
                return True
    return False


def _pairing(old_rows, new_rows):
    """(detector report, aligned key of each snapshot row by ``id(row)``,
    baseline row of each key)."""
    detector = DeltaDetector()
    report = detector.detect_changes(old_rows, new_rows, "baseline", "snapshot")
    old_map = detector._create_resource_map(old_rows)
    new_map = detector._create_resource_map(new_rows)
    aligned, _ = detector._align_keys(old_map, new_map)
    key_of = {id(row): key for key, row in aligned.items()}
    return detector, report, key_of, old_map


def _differs(detector, key, old_row, new_row) -> List[str]:
    """The ``attributes`` keys whose value differs between the two rows (the
    rows compared after the change report's canonical form)."""
    ignored = detector._ignored_names()
    old = detector._canonical(old_row, ignored)
    new = detector._canonical(new_row, ignored)
    return [
        text
        for text in key
        if filters.compile_key(text).get(old) != filters.compile_key(text).get(new)
    ]


def evaluate_policy(
    policy: model.Policy,
    snapshot: Dict[str, Any],
    baseline: Dict[str, Any],
    ctx: filters.Context,
    evaluate_rows,
    snap,
) -> Tuple[List[Dict[str, Any]], Dict[str, int], List[Dict[str, str]]]:
    """``(findings including passes, counts, unit lines)`` of one policy that
    has a ``baseline`` entry, with a baseline given."""
    if _nested(policy.check):
        raise PolicyError(
            [
                TemplateIssue(
                    "a baseline check must be a top-level entry of check, "
                    "not inside and, or or not",
                    policy.file or None,
                    policy.id_line,
                    "check",
                )
            ]
        )
    entries = list(policy.check)
    baseline_at = [i for i, e in enumerate(entries) if _is_baseline(e)]
    other_at = [i for i, e in enumerate(entries) if not _is_baseline(e)]
    others = replace(policy, check=tuple(entries[i] for i in other_at))
    findings, counts, lines = evaluate_rows(others, snap, ctx)
    for finding in findings:  # details name the entry's place in ``check``
        for detail in finding.get("details") or ():
            detail["check"] = other_at[detail["check"]]

    old_rows = [r for r in (baseline.get("resources") or []) if isinstance(r, dict)]
    detector, report, key_of, old_map = _pairing(old_rows, snap.rows)
    added = {c.resource_arn for c in report.added_resources}
    modified = {c.resource_arn for c in report.modified_resources}
    by_resource = {}
    for row in snap.rows:
        by_resource.setdefault(model.resource(row), []).append(row)

    wanted = [(i, entries[i]) for i in baseline_at]

    def verdict(row) -> List[Dict[str, Any]]:
        """The failures of the baseline entries on one snapshot row."""
        key = key_of.get(id(row))
        failures = []
        for index, entry in wanted:
            changes = entry["change"]
            if key in added and "added" in changes:
                failures.append(
                    {"check": index, "type": "baseline", "problem": "added"}
                )
            elif key in modified and "modified" in changes:
                keys = entry.get("attributes")
                if not keys:
                    failures.append(
                        {"check": index, "type": "baseline", "problem": "modified"}
                    )
                else:
                    for text in _differs(detector, keys, old_map[key], row):
                        failures.append(
                            {
                                "check": index,
                                "type": "baseline",
                                "key": text,
                                "problem": "modified",
                            }
                        )
        return failures

    result: List[Dict[str, Any]] = []
    for finding in findings:
        rows = by_resource.get(finding["resource"], [])
        failures = verdict(rows[0]) if rows else []
        if failures and finding["result"] in ("pass", "fail"):
            policy_failures = list(finding.get("details") or []) + failures
            policy_failures.sort(key=lambda d: d["check"])
            finding = engine._finding(policy, rows[0], "fail", failures=policy_failures)
        result.append(finding)

    result.extend(_removed(policy, snapshot, ctx, snap, report, old_map, wanted))
    counts = dict(counts)
    for name in ("pass", "fail", "not_evaluated"):
        counts[name] = sum(1 for f in result if f["result"] == name)
    return result, counts, lines


def _removed(policy, snapshot, ctx, snap, report, old_map, wanted):
    """Findings of the baseline rows that the snapshot lacks (spec 2.3.1)."""
    at = [i for i, e in wanted if "removed" in e["change"]]
    if not at:
        return []
    block = policy.resource
    filter_nodes = [filters.compile_entry(e) for e in block.get("filters") or []]
    scopes = engine._tag_scopes(policy.check)
    found = []
    for change in report.removed_resources:
        row = old_map[change.resource_arn]
        if not engine._plain(row, block) or not all(_in_scope(row, s) for s in scopes):
            continue
        account, service = model.account(row), str(row.get("service") or "")
        region = str(row.get("region") or "")
        if any(ctx.unit_unread(account, service, r) for r in {region, "global"}):
            continue  # the unit was not read: not "removed" (change report, A-05)
        selected = filters.evaluate_all(filter_nodes, row, ctx)
        if selected.value is FALSE:
            continue
        if selected.value is UNKNOWN:
            finding = engine._finding(policy, row, "not_evaluated", selected.reason)
        else:
            failure = {"check": at[0], "type": "baseline", "problem": "removed"}
            finding = engine._finding(policy, row, "fail", failures=[failure])
        finding["from"] = "baseline"
        found.append(finding)
    return found
