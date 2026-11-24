"""Markdown: the same content as tables, at most 50 rows per policy, then
"and N more" (spec 3.4). Untrusted text is escaped so a resource name cannot
make a link, a tag or a table row."""

import re
from typing import Any, List, Mapping

from . import _common
from ._common import clean

MAX_ROWS = 50


def esc(value: Any) -> str:
    text = clean(value).replace("&", "&amp;")
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_\[\]|~])", r"\\\1", text)


def _table(header: List[str], rows: List[List[str]]) -> List[str]:
    out = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(" --- " for _ in header) + "|",
    ]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def _row(f: Mapping[str, Any], show_values: bool) -> List[str]:
    note = esc(f["message"])
    if f.get("reason") and f["reason"] not in f["message"]:
        note += f" ({esc(f['reason'])})"
    if f.get("waiver"):
        note += f" waived: {esc(f['waiver']['reason'])}, expires {esc(f['waiver']['expires'])}"
    if show_values:
        values = [
            f"{esc(d.get('key', ''))} = {esc(_common.shown_value(d['value']))}"
            for d in f.get("details") or []
            if "value" in d
        ]
        if values:
            note += " [" + "; ".join(values) + "]"
    return [
        esc(f["result"]),
        esc(f["account"]),
        esc(f["region"]),
        esc(f["resource"]),
        note,
    ]


def _why(w: Mapping[str, Any]) -> str:
    if w.get("by"):
        return f"{w['why']} by {clean(w['by'])}"
    return str(w["why"])


def _outcome(u: Mapping[str, Any]) -> str:
    suffix = " (baseline)" if u.get("from") == "baseline" else ""
    return f"{u['outcome']}{suffix}"


def render(data: Mapping[str, Any], show_values: bool = False, gate=None) -> str:
    summary = data.get("summary") or {}
    by = summary.get("by_result") or {}
    snap = data.get("snapshot") or {}
    lines = [
        "# InvenTag policy findings",
        "",
        f"Snapshot `{esc(snap.get('file', ''))}`, evaluated on {esc(data.get('now', ''))}.",
        "",
    ]
    lines += _table(
        ["Rows", "Fail", "Waived", "Not evaluated", "Pass"],
        [
            [
                str(summary.get("rows", 0)),
                str(by.get("fail", 0)),
                str(by.get("waived", 0)),
                str(by.get("not_evaluated", 0)),
                str(by.get("pass", 0)),
            ]
        ],
    )
    grouped = _common.findings_by_policy(data)
    for policy in data.get("policies") or []:
        c = _common.counts(policy)
        lines += [
            "",
            f"## {esc(policy['id'])} ({esc(policy.get('severity', ''))})",
            "",
            f"File {esc(policy.get('file', ''))}: fail {c.get('fail', 0)}, waived "
            f"{c.get('waived', 0)}, not evaluated {c.get('not_evaluated', 0)}, "
            f"pass {c.get('pass', 0)}, out of scope {c.get('out_of_scope', 0)}.",
        ]
        items = grouped.get(policy["id"], [])
        if items:
            lines.append("")
            shown = items[:MAX_ROWS]
            lines += _table(
                ["Result", "Account", "Region", "Resource", "Detail"],
                [_row(f, show_values) for f in shown],
            )
            if len(items) > MAX_ROWS:
                lines += ["", f"and {len(items) - MAX_ROWS} more"]
    units = data.get("not_evaluated_units") or []
    if units:
        lines += ["", "## Units not read", ""]
        lines += _table(
            ["Policy", "Account", "Service", "Region", "Outcome"],
            [
                [
                    esc(u["policy"]),
                    esc(u["account"]),
                    esc(u["service"]),
                    esc(u["region"]),
                    esc(_outcome(u)),
                ]
                for u in units[:MAX_ROWS]
            ],
        )
        if len(units) > MAX_ROWS:
            lines += ["", f"and {len(units) - MAX_ROWS} more"]
    nep = data.get("not_evaluated_policies") or []
    if nep:
        lines += ["", "## Policies not evaluated", ""]
        lines += _table(
            ["Policy", "Reason"], [[esc(p["policy"]), esc(p["reason"])] for p in nep]
        )
    unused = data.get("unused_waivers") or []
    if unused:
        lines += ["", "## Unused waivers", ""]
        lines += _table(
            ["Policy", "Resource", "Expires", "Why", "File"],
            [
                [
                    esc(w["policy"]),
                    esc(w["resource"]),
                    esc(w["expires"]),
                    esc(_why(w)),
                    esc(w["file"]),
                ]
                for w in unused[:MAX_ROWS]
            ],
        )
        if len(unused) > MAX_ROWS:
            lines += ["", f"and {len(unused) - MAX_ROWS} more"]
    sentence = _common.exit_sentence(data, gate)
    if sentence is not None:
        lines += ["", sentence]
    return "\n".join(lines) + "\n"
