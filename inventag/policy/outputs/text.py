"""Plain text: one summary line per policy, the findings grouped by policy, and
the sentence the exit code stands for as the last line (spec 3.4)."""

from typing import Any, List, Mapping

from . import _common
from ._common import clean


def _detail(detail: Mapping[str, Any], show_values: bool) -> str:
    line = clean(detail.get("problem", ""))
    if detail.get("key"):
        line = f"{line}: {clean(detail['key'])}"
    if show_values and "value" in detail:
        line += f" (value: {_common.shown_value(detail['value'])})"
    return line


def _why(w: Mapping[str, Any]) -> str:
    if w.get("by"):
        return f"{w['why']} by {clean(w['by'])}"
    return str(w["why"])


def render(data: Mapping[str, Any], show_values: bool = False, gate=None) -> str:
    summary = data.get("summary") or {}
    by = summary.get("by_result") or {}
    snap = data.get("snapshot") or {}
    lines: List[str] = [
        "InvenTag policy findings",
        f"Snapshot: {clean(snap.get('file', ''))}  now: {clean(data.get('now', ''))}",
        "Rows: {rows}  fail: {fail}  waived: {waived}  not evaluated: {ne}  "
        "pass: {ok}".format(
            rows=summary.get("rows", 0),
            fail=by.get("fail", 0),
            waived=by.get("waived", 0),
            ne=by.get("not_evaluated", 0),
            ok=by.get("pass", 0),
        ),
        "",
    ]
    policies = data.get("policies") or []
    for policy in policies:
        c = _common.counts(policy)
        lines.append(
            "{id} [{sev}] fail={fail} waived={waived} not_evaluated={ne} "
            "pass={ok} out_of_scope={oos}".format(
                id=clean(policy["id"]),
                sev=policy.get("severity", ""),
                fail=c.get("fail", 0),
                waived=c.get("waived", 0),
                ne=c.get("not_evaluated", 0),
                ok=c.get("pass", 0),
                oos=c.get("out_of_scope", 0),
            )
        )
    grouped = _common.findings_by_policy(data)
    for policy in policies:
        items = grouped.get(policy["id"], [])
        if not items:
            continue
        lines += ["", f"{clean(policy['id'])} ({clean(policy.get('file', ''))})"]
        for f in items:
            tag = {
                "fail": "FAIL",
                "waived": "WAIVED",
                "not_evaluated": "NOT EVALUATED",
            }[f["result"]]
            lines.append(f"  {tag} {clean(f['resource'])}")
            lines.append(f"    {clean(f['message'])}")
            if f.get("reason") and f["reason"] not in f["message"]:
                lines.append(f"    reason: {f['reason']}")
            if f.get("waiver"):
                w = f["waiver"]
                lines.append(
                    f"    waiver: {clean(w['reason'])} (approved by "
                    f"{clean(w['approved_by'])}, expires {w['expires']})"
                )
            for d in f.get("details") or []:
                lines.append(f"    - {_detail(d, show_values)}")
    units = data.get("not_evaluated_units") or []
    if units:
        lines += ["", "Units not read:"]
        for u in units:
            lines.append(
                f"  {clean(u['policy'])} {clean(u['account'])} {clean(u['service'])} "
                f"{clean(u['region'])}: {clean(u['outcome'])}"
                + (" (baseline)" if u.get("from") == "baseline" else "")
            )
    nep = data.get("not_evaluated_policies") or []
    if nep:
        lines += ["", "Policies not evaluated:"]
        for p in nep:
            lines.append(f"  {clean(p['policy'])}: {p['reason']}")
    unused = data.get("unused_waivers") or []
    if unused:
        lines += ["", "Unused waivers:"]
        for w in unused:
            lines.append(
                f"  {clean(w['policy'])} {clean(w['resource'])} expires "
                f"{w['expires']}: {_why(w)} ({clean(w['file'])})"
            )
    sentence = _common.exit_sentence(data, gate)
    if sentence is not None:
        lines += ["", sentence]
    return "\n".join(lines) + "\n"
