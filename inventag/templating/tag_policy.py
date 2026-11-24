"""Check resources against a tag-policy template."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .columns import normalize_tags, resource_sort_key


@dataclass
class TagFinding:
    """Result for one in-scope resource."""

    resource: Dict[str, Any]
    missing: List[str] = field(default_factory=list)
    invalid: List[str] = field(default_factory=list)  # human-readable reasons

    @property
    def compliant(self) -> bool:
        return not self.missing and not self.invalid

    @property
    def status(self) -> str:
        return "Compliant" if self.compliant else "Non-compliant"


@dataclass
class ComplianceReport:
    policy_name: str
    policy_description: str
    rules: List[Dict[str, Any]]
    findings: List[TagFinding]
    out_of_scope: int
    # v1.5.0 scope.filters: (row, reason) of each row the filters could not
    # decide; counted, never checked. ``uses_filters`` keeps the v1.4.3 shape
    # of a policy without filters.
    not_evaluated: List[Tuple[Dict[str, Any], str]] = field(default_factory=list)
    uses_filters: bool = False

    @property
    def checked(self) -> int:
        return len(self.findings)

    @property
    def compliant(self) -> int:
        return sum(1 for f in self.findings if f.compliant)

    @property
    def non_compliant(self) -> int:
        return self.checked - self.compliant

    @property
    def percent_compliant(self) -> float:
        return round(self.compliant / self.checked * 100, 1) if self.checked else 100.0

    def missing_by_key(self) -> Dict[str, int]:
        counts = {rule["key"]: 0 for rule in self.rules}
        for finding in self.findings:
            for key in finding.missing:
                counts[key] = counts.get(key, 0) + 1
        return counts

    def invalid_by_key(self) -> Dict[str, int]:
        counts = {rule["key"]: 0 for rule in self.rules}
        # Tag keys can hold colons ("team:owner"), so match the rule keys
        # instead of cutting the text at the first colon. Longest key first.
        keys = sorted(counts, key=len, reverse=True)
        for finding in self.findings:
            for reason in finding.invalid:
                key = next(
                    (k for k in keys if reason.startswith(f"{k}: ")),
                    reason.split(":", 1)[0],
                )
                counts[key] = counts.get(key, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        data = self._to_dict()
        if self.uses_filters:
            data["summary"]["not_evaluated"] = len(self.not_evaluated)
            data["not_evaluated_resources"] = [
                {
                    "account": r.get("source_account_id") or r.get("account_id"),
                    "service": r.get("service"),
                    "resource_type": r.get("resource_type"),
                    "resource_id": r.get("resource_id") or r.get("id"),
                    "arn": r.get("arn"),
                    "region": r.get("region"),
                    "reason": reason,
                }
                for r, reason in sorted(
                    self.not_evaluated, key=lambda e: resource_sort_key(e[0])
                )
            ]
        return data

    def _to_dict(self) -> Dict[str, Any]:
        return {
            "policy": self.policy_name,
            "description": self.policy_description,
            "summary": {
                "checked": self.checked,
                "compliant": self.compliant,
                "non_compliant": self.non_compliant,
                "out_of_scope": self.out_of_scope,
                "percent_compliant": self.percent_compliant,
                "missing_by_key": self.missing_by_key(),
                "invalid_by_key": self.invalid_by_key(),
            },
            "non_compliant_resources": [
                {
                    "account": f.resource.get("source_account_id")
                    or f.resource.get("account_id"),
                    "service": f.resource.get("service"),
                    "resource_type": f.resource.get("resource_type"),
                    "resource_id": f.resource.get("resource_id")
                    or f.resource.get("id"),
                    "arn": f.resource.get("arn"),
                    "region": f.resource.get("region"),
                    "missing": f.missing,
                    "invalid": f.invalid,
                }
                for f in sorted(
                    self.findings, key=lambda f: resource_sort_key(f.resource)
                )
                if not f.compliant
            ],
        }


def rule_summary(rule: Dict[str, Any]) -> str:
    if rule.get("allowed_values"):
        case = "" if rule.get("case_sensitive") else " (any case)"
        return "One of: " + ", ".join(rule["allowed_values"]) + case
    if rule.get("pattern"):
        return f"Matches: {rule['pattern']}"
    return "Any value"


def _in_scope(resource: Dict[str, Any], scope: Dict[str, Any]) -> bool:
    service = str(resource.get("service") or "").lower()
    rtype = str(resource.get("resource_type") or "").lower()
    services = [s.lower() for s in scope.get("services") or []]
    types = [t.lower() for t in scope.get("resource_types") or []]
    excluded = [t.lower() for t in scope.get("exclude_resource_types") or []]
    if services and service not in services:
        return False
    if types and rtype not in types:
        return False
    return rtype not in excluded


def check_value(rule: Dict[str, Any], value: str) -> Optional[str]:
    """Return a reason if ``value`` breaks ``rule``, else None."""
    allowed = rule.get("allowed_values")
    if allowed:
        if rule.get("case_sensitive"):
            ok = value in allowed
        else:
            ok = value.lower() in {a.lower() for a in allowed}
        if not ok:
            return f"{rule['key']}: '{value}' is not one of {', '.join(allowed)}"
    pattern = rule.get("pattern")
    if pattern and not re.fullmatch(pattern, value):
        return f"{rule['key']}: '{value}' does not match {pattern}"
    return None


class _ScopeFilters:
    """``scope.filters``: the policy language's filters (``type: value``)."""

    def __init__(self, entries, resources, now, units_not_read):
        # imported here: inventag.policy imports this module
        from ..policy import engine, filters

        self.filters = filters
        self.nodes = [filters.compile_entry(e) for e in entries]
        snap = engine._Snapshot(
            {
                "resources": resources,
                "metadata": {"tags": {"units_not_read": units_not_read}},
            }
        )
        self.ctx = filters.Context(
            now=now or dt.datetime.now(dt.timezone.utc),
            tags_unknown=snap.tags_unknown,
            unit_unread=snap.unit_unread,
            related_rows=snap.related_rows,
        )

    def decide(self, resource: Dict[str, Any]) -> Tuple[Optional[bool], str]:
        """True (in scope), False (out of scope) or None with the reason."""
        found = self.filters.evaluate_all(self.nodes, resource, self.ctx)
        if found.value is self.filters.TRUE:
            return True, ""
        if found.value is self.filters.FALSE:
            return False, ""
        return None, found.reason or "not_comparable"


def evaluate(
    resources: List[Dict[str, Any]],
    policy,
    now: Optional[dt.datetime] = None,
    units_not_read: Any = None,
) -> ComplianceReport:
    """Check ``resources`` against a resolved tag-policy template.

    ``now`` and ``units_not_read`` (the snapshot's ``metadata.tags`` list of
    listings this run did not read) are used only by ``scope.filters``: an
    age is counted from ``now``, and a tag filter on a row whose tags were not
    read cannot be decided.
    """
    spec = policy.spec
    rules = spec["required_tags"]
    scope = spec.get("scope") or {}
    entries = scope.get("filters") or []
    chooser = (
        _ScopeFilters(entries, resources, now, units_not_read) if entries else None
    )
    findings: List[TagFinding] = []
    not_evaluated: List[Tuple[Dict[str, Any], str]] = []
    out_of_scope = 0
    for resource in resources:
        if not _in_scope(resource, scope):
            out_of_scope += 1
            continue
        if chooser is not None:
            chosen, reason = chooser.decide(resource)
            if chosen is False:
                out_of_scope += 1
                continue
            if chosen is None:
                not_evaluated.append((resource, reason))
                continue
        tags = normalize_tags(resource.get("tags"))
        lowered = {k.lower(): k for k in tags}
        finding = TagFinding(resource)
        for rule in rules:
            key = rule["key"]
            if key not in tags:
                near = lowered.get(key.lower())
                finding.missing.append(key)
                if near:
                    finding.invalid.append(
                        f"{key}: found '{near}' instead (tag keys are case-sensitive)"
                    )
                continue
            reason = check_value(rule, str(tags[key]))
            if reason:
                finding.invalid.append(reason)
        findings.append(finding)
    return ComplianceReport(
        policy_name=policy.name,
        policy_description=policy.description,
        rules=rules,
        findings=findings,
        out_of_scope=out_of_scope,
        not_evaluated=not_evaluated,
        uses_filters=bool(entries),
    )
