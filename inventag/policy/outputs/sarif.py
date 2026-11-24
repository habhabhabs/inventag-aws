"""SARIF 2.1.0 (spec 3.4): one run, ``rules[]`` = policies, one result per
``fail``, ``waived`` (with an external suppression) and ``not_evaluated``
(kind ``review``, level ``none``). ``pass`` is not written. No raw value and no
clock time is written."""

import hashlib
from typing import Any, Dict, List, Mapping

from . import _common

SCHEMA_URL = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}


def _rule(policy: Mapping[str, Any]) -> Dict[str, Any]:
    rule: Dict[str, Any] = {
        "id": policy["id"],
        "name": policy.get("name", policy["id"]),
        "shortDescription": {"text": _common.clean(policy.get("name", policy["id"]))},
        "properties": {
            "severity": policy.get("severity", ""),
            "version": policy.get("version", 1),
            "sha256": policy.get("sha256", ""),
        },
    }
    if policy.get("description"):
        rule["fullDescription"] = {"text": _common.clean(policy["description"])}
    for ref in policy.get("references") or []:
        if str(ref).startswith(("https://", "http://")):
            rule["helpUri"] = ref
            break
    return rule


def _line(value: Any) -> int:
    return value if isinstance(value, int) and value >= 1 else 1


def _result(
    f: Mapping[str, Any],
    index: Mapping[str, int],
    files: Mapping[str, str],
    lines: Mapping[str, Any],
) -> Dict[str, Any]:
    kind = {"fail": "fail", "waived": "fail", "not_evaluated": "review"}[f["result"]]
    out: Dict[str, Any] = {
        "ruleId": f["policy"],
        "kind": kind,
        "level": "none" if kind == "review" else LEVEL.get(f["severity"], "note"),
        "message": {"text": _common.clean(f["message"])},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": files.get(f["policy"], "")},
                    "region": {"startLine": _line(lines.get(f["policy"]))},
                },
                "logicalLocations": [{"fullyQualifiedName": f["resource"]}],
            }
        ],
        "partialFingerprints": {
            "inventag/v1": hashlib.sha256(
                f"{f['policy']}|{f['account']}|{f['resource']}".encode("utf-8")
            ).hexdigest()
        },
        "properties": {
            k: f[k] for k in ("account", "region", "service", "resource_type") if k in f
        },
    }
    if f["policy"] in index:
        out["ruleIndex"] = index[f["policy"]]
    if f.get("reason"):
        out["properties"]["reason"] = f["reason"]
    if f["result"] == "waived":
        out["suppressions"] = [
            {
                "kind": "external",
                "justification": _common.clean(
                    (f.get("waiver") or {}).get("reason", "")
                ),
            }
        ]
    return out


def _notes(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    notes = []
    for u in data.get("not_evaluated_units") or []:
        text = (
            f"{u['policy']}: {u['service']} in {u['region']} of account "
            f"{u['account']} was not read ({u['outcome']})"
        )
        if u.get("from") == "baseline":
            text += " in the baseline"
        notes.append({"level": "note", "message": {"text": _common.clean(text)}})
    for p in data.get("not_evaluated_policies") or []:
        text = f"{p['policy']}: not evaluated ({p['reason']})"
        notes.append({"level": "note", "message": {"text": _common.clean(text)}})
    for w in data.get("unused_waivers") or []:
        text = f"{w['policy']}: unused waiver for {w['resource']} ({w['why']}"
        if w.get("by"):
            text += f" by {w['by']}"
        text += ")"
        notes.append({"level": "note", "message": {"text": _common.clean(text)}})
    return notes


def render(data: Mapping[str, Any], policy_lines: Mapping[str, int]) -> str:
    policies = data.get("policies") or []
    index = {p["id"]: i for i, p in enumerate(policies)}
    files = {p["id"]: p.get("file", "") for p in policies}
    lines = {p["id"]: p["line"] for p in policies if "line" in p}
    lines.update(policy_lines)
    results = [
        _result(f, index, files, lines)
        for f in data.get("findings") or []
        if f.get("result") != "pass"
    ]
    driver: Dict[str, Any] = {
        "name": "InvenTag",
        "rules": [_rule(p) for p in policies],
    }
    if data.get("inventag_version"):
        driver["version"] = data["inventag_version"]
    run: Dict[str, Any] = {
        "tool": {"driver": driver},
        "results": results,
        "properties": {
            "snapshotSha256": (data.get("snapshot") or {}).get("sha256", "")
        },
    }
    notes = _notes(data)
    if notes:
        run["invocations"] = [
            {"executionSuccessful": True, "toolExecutionNotifications": notes}
        ]
    log = {"$schema": SCHEMA_URL, "version": "2.1.0", "runs": [run]}
    return _common.dumps(log)
