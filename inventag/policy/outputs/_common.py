"""Shared helpers: masking, text cleaning, the exit-code sentences."""

import copy
import json
import re
import unicodedata
from typing import Any, Dict, List, Mapping

from ...security import secret_values

MASK = secret_values.MASK

EXIT_SENTENCE = {
    0: "Exit code 0: no gate was triggered.",
    7: "Exit code 7: at least one fail has the --fail-on severity or a higher one.",
    8: "Exit code 8: something was not evaluated and --fail-on-not-evaluated is set.",
}

_BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A)) | {0x200E, 0x200F}
_WORD = re.compile(r"[A-Za-z0-9_-]+")


def exit_sentence(result: Mapping[str, Any]) -> str:
    code = (result.get("summary") or {}).get("exit_code", 0)
    return EXIT_SENTENCE.get(code, f"Exit code {code}.")


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
