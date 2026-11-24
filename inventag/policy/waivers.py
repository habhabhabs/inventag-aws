"""Waivers (v15-policy-spec.md 2.5): a fail with a valid waiver becomes waived.

``apply`` is pure: it reads no clock (``now`` comes in), no file, and does not
change its input. A waiver never touches ``pass`` or ``not_evaluated``.
"""

from __future__ import annotations

import datetime as dt
from fnmatch import fnmatchcase
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import model


def _is_glob(pattern: str) -> bool:
    return "*" in pattern or "?" in pattern


def _matches(waiver: model.Waiver, finding: Dict[str, Any]) -> bool:
    if waiver.policy != finding["policy"]:
        return False
    if waiver.account is not None and waiver.account != finding["account"]:
        return False
    if _is_glob(waiver.resource):
        return fnmatchcase(finding["resource"], waiver.resource)
    return waiver.resource == finding["resource"]


def _unused(waiver: model.Waiver, why: str) -> Dict[str, Any]:
    entry = {
        "policy": waiver.policy,
        "resource": waiver.resource,
        "expires": waiver.expires.isoformat(),
        "why": why,
        "file": waiver.file,
    }
    if waiver.account is not None:
        entry["account"] = waiver.account
    return entry


def apply(
    findings: Sequence[Dict[str, Any]],
    waivers: Sequence[model.Waiver],
    now: dt.datetime,
    known_policies: Optional[Iterable[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """``(findings, unused_waivers)`` (spec 2.5).

    A waiver is valid through the end of its ``expires`` day in UTC. Of several
    waivers that match a failing finding the one with the latest ``expires``
    is used (ties: first in ``waivers``); if that one is expired the finding
    stays ``fail`` and carries ``waiver_expired``. ``known_policies`` are the
    ids of the loaded policies; without it only the policies that have a
    finding count as known (a waiver for any other is ``unknown policy``).
    """
    today = now.astimezone(dt.timezone.utc).date()
    known = (
        {f["policy"] for f in findings}
        if known_policies is None
        else set(known_policies)
    )
    used = set()
    out: List[Dict[str, Any]] = []
    for finding in findings:
        finding = dict(finding)
        if finding["result"] == "fail":
            matching = [(i, w) for i, w in enumerate(waivers) if _matches(w, finding)]
            if matching:
                index, best = max(matching, key=lambda m: (m[1].expires, -m[0]))
                if best.expires >= today:
                    finding["result"] = "waived"
                    finding["waiver"] = {
                        "reason": best.reason,
                        "approved_by": best.approved_by,
                        "expires": best.expires.isoformat(),
                        "file": best.file,
                    }
                    used.add(index)
                else:
                    finding["waiver_expired"] = best.expires.isoformat()
        out.append(finding)
    unused = []
    for index, waiver in enumerate(waivers):
        if index in used:
            continue
        if waiver.policy not in known:
            why = "unknown policy"
        elif waiver.expires < today:
            why = "expired"
        else:
            why = "no match"
        unused.append(_unused(waiver, why))
    return out, unused
