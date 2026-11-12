"""Check resources against a tag-policy template."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .columns import normalize_tags


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
        for finding in self.findings:
            for reason in finding.invalid:
                key = reason.split(":", 1)[0]
                counts[key] = counts.get(key, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
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
                for f in self.findings
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


def evaluate(resources: List[Dict[str, Any]], policy) -> ComplianceReport:
    """Check ``resources`` against a resolved tag-policy template."""
    spec = policy.spec
    rules = spec["required_tags"]
    scope = spec.get("scope") or {}
    findings: List[TagFinding] = []
    out_of_scope = 0
    for resource in resources:
        if not _in_scope(resource, scope):
            out_of_scope += 1
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
    )
