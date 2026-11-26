"""Shared helpers: masking, text cleaning, the exit-code sentences."""

import copy
import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ...security import secret_values

MASK = secret_values.MASK

SEVERITIES = ("info", "low", "medium", "high", "critical")
THRESHOLDS = ("fail_on", "fail_on_not_evaluated")

_BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A)) | {0x200E, 0x200F}
_WORD = re.compile(r"[A-Za-z0-9_-]+")


def gates(
    fail_on: Optional[str], thresholds: Optional[Iterable[str]]
) -> Optional[Tuple[Optional[str], bool]]:
    """``(fail_on, fail_on_not_evaluated)`` as the caller set them, or None.

    None means the caller gave neither: the exit sentence is then left out.
    """
    if fail_on is None and thresholds is None:
        return None
    names = set(thresholds or ())
    unknown = sorted(names - set(THRESHOLDS))
    if unknown:
        raise ValueError(f"unknown threshold: {', '.join(unknown)}")
    if fail_on is not None and fail_on not in SEVERITIES:
        raise ValueError(f"unknown severity for fail_on: {fail_on}")
    if "fail_on" in names and fail_on is None:
        raise ValueError("the fail_on threshold needs the fail_on severity")
    return fail_on, "fail_on_not_evaluated" in names


# On a scan, 5, 6, 3 and 4 come before the policy check's code (spec 4); the
# last line then gives the code the scan exits with (behaviour review F2).
_SCAN_CODES = {
    3: "the template's tag policy found violations (fail_on_tag_violations)",
    4: "a security group rule is at or above --risk-threshold",
    5: "an account could not be scanned (--fail-on-account-error)",
    6: "no resources were found (--fail-if-empty)",
}
_BEFORE = "this code comes before the policy check's code"


def exit_sentence(result: Mapping[str, Any], gate) -> Optional[str]:
    """The last line of the text and Markdown forms (spec 11.3), or None."""
    if gate is None:
        return None
    fail_on, not_evaluated = gate
    code = (result.get("summary") or {}).get("exit_code", 0)
    if code == 7:
        if fail_on is None:
            raise ValueError("exit code 7 needs fail_on to name the severity")
        return (
            f"Exit code 7: at least one finding failed at severity {fail_on} or higher."
        )
    if code == 8:
        return "Exit code 8: some checks could not be evaluated."
    if code in _SCAN_CODES:
        return f"Exit code {code}: {_SCAN_CODES[code]}; {_BEFORE}."
    if code != 0:
        return f"Exit code {code}."
    parts = []
    if fail_on is not None:
        parts.append(f"Exit code 0: nothing failed at severity {fail_on} or higher.")
    if not_evaluated:
        parts.append("Exit code 0: everything could be evaluated.")
    if not parts:
        return "Exit code 0: findings are reported; no threshold was set."
    return " ".join(parts)


_TAG_VALUE_MARKERS = ("' does not match ", "' is not one of ")


def _value_free_problem(problem: str, key: Any) -> str:
    """``KEY: 'value' does not match P`` -> ``KEY: value does not match P``
    (the same for ``is not one of``); other problems are unchanged."""
    prefix = f"{key}: '"
    if not problem.startswith(prefix):
        return problem
    for marker in _TAG_VALUE_MARKERS:
        at = problem.rfind(marker)
        if at >= len(prefix) - 1:
            return f"{key}: value {marker[2:]}{problem[at + len(marker):]}"
    return problem


def value_free_message(finding: Mapping[str, Any]) -> str:
    """The finding's message without the tag values that a required-tags
    problem quotes (SARIF and JUnit never carry a value, spec 11.4)."""
    message = str(finding.get("message") or "")
    for detail in finding.get("details") or []:
        if detail.get("type") != "required-tags":
            continue
        problem = str(detail.get("problem") or "")
        free = _value_free_problem(problem, detail.get("key"))
        if free != problem:
            message = message.replace(problem, free)
    return message


def clean(value: Any) -> str:
    """One line of plain text: no control, escape or direction characters.

    Resource names and tags come from the scanned accounts, so they are
    untrusted. Line breaks and tabs become one space.
    """
    out = []
    for ch in str(value):
        if ch in "\n\r\t":
            out.append(" ")
        elif unicodedata.category(ch) in ("Cc", "Cs") or ord(ch) in _BIDI:
            continue
        else:
            out.append(ch)
    return "".join(out)


def dumps(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _secret_key(key: Any) -> bool:
    words = _WORD.findall(str(key or ""))
    return bool(words) and secret_values.is_secret_key(words[-1])


def prepared(result: Mapping[str, Any], show_values: bool) -> Dict[str, Any]:
    """A copy of ``result`` that is safe to write.

    Without ``show_values`` every ``value`` of a detail is removed, whatever the
    engine did. With it, a value stays unless its key names a secret, and a
    nested secret is masked. A masked value stays masked.
    """
    data = copy.deepcopy(dict(result))
    for finding in data.get("findings") or []:
        for detail in finding.get("details") or []:
            if "value" not in detail:
                continue
            if not show_values:
                del detail["value"]
            elif _secret_key(detail.get("key")):
                detail["value"] = MASK
            else:
                detail["value"] = secret_values.mask_secret_values(detail["value"])
    return data


def findings_by_policy(data: Mapping[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Listed findings (never ``pass``) by policy id, in the result's order."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for finding in data.get("findings") or []:
        if finding.get("result") != "pass":
            out.setdefault(finding["policy"], []).append(finding)
    return out


def counts(policy: Mapping[str, Any]) -> Mapping[str, int]:
    return policy.get("counts") or {}


def shown_value(value: Any) -> str:
    if isinstance(value, str):
        return clean(value)
    return clean(json.dumps(value, sort_keys=True, ensure_ascii=False))
