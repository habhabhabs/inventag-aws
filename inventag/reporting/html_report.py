"""The HTML report (``--create-html``): one self-contained, static file.

The file holds the same rows as the default Excel report (secret values
masked the same way), as plain HTML tables:

* a summary (resources by service, resources by region, run notes);
* one closed ``<details>`` section of resources for each service;
* the compliance summary, the network and security tables, the FinOps
  findings and the FinOps costs, when the run made them;
* coverage: the accounts, how the listings ended, the permissions denied.

Safety rules (architect plan, part C):

* Every value is escaped with :func:`html.escape`; values from AWS accounts
  can hold markup.
* No JavaScript, no external resource (no CDN, font, remote image or link to
  another site). A Content-Security-Policy meta tag (:data:`CSP`) blocks
  anything else a browser could load.
* The only links are links to sections of the same file (``#...``). The only
  image is the template logo, PNG or JPEG only, embedded as a ``data:`` URI.
* Standard library only. The file is written with ``save_atomically`` and is
  private to the user (0600), as the other reports are.
* Nothing from a scanned resource is written to the log.
"""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .safe_save import save_atomically

CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
    "base-uri 'none'; form-action 'none'"
)
DEFAULT_TITLE = "AWS Resource Inventory - BOM Report"
PRIVACY_NOTE = (
    "This file holds data from your AWS accounts (resource names, IDs, tags "
    "and settings). Keep it private, as you keep the Excel report."
)
NO_RESOURCES = "No resources to report."
# The coverage outcomes, in the order of the Output files page.
OUTCOMES = ("ok", "empty", "denied", "throttled", "error", "timeout", "out_of_scope")
_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
# Characters that HTML must not carry (C0 controls except tab, line feed and
# carriage return; lone surrogates; the two non-characters).
_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff\ufffe\uffff]")
# Text-direction marks, embeddings, overrides and isolates (the set the policy
# outputs remove), and the C1 controls: removed, so a name from a scanned
# account cannot show reversed or reordered (security review v1.5.1, 1).
_BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A)) | {0x200E, 0x200F}
_REMOVED = re.compile("[" + "".join(chr(c) for c in sorted(_BIDI)) + "\x80-\x9f]")

_STYLE = """
:root { color-scheme: light; }
body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  color: #1a1a1a; background: #ffffff; margin: 0 auto; padding: 1rem 1.5rem;
  max-width: 100rem; line-height: 1.45; }
header { border-bottom: 3px solid #1f3b5c; margin-bottom: 1rem; }
header img { max-height: 4rem; max-width: 16rem; }
h1 { color: #1f3b5c; font-size: 1.6rem; margin: 0.4rem 0; }
h2 { color: #1f3b5c; font-size: 1.3rem; margin-top: 2rem;
  border-bottom: 1px solid #c4ccd6; }
h3 { font-size: 1.05rem; }
summary h3 { display: inline; }
nav ul { padding-left: 1.2rem; }
a { color: #0b4f8a; }
a:focus, summary:focus { outline: 3px solid #0b4f8a; outline-offset: 2px; }
.note { background: #f3f5f8; border-left: 4px solid #1f3b5c; padding: 0.5rem 0.8rem; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; margin: 0.5rem 0 1rem; font-size: 0.85rem; }
caption { text-align: left; font-weight: 600; padding: 0.3rem 0; }
th, td { border: 1px solid #9aa5b1; padding: 0.25rem 0.5rem; text-align: left;
  vertical-align: top; overflow-wrap: anywhere; max-width: 40rem; }
th { background: #e3e9f0; color: #1a1a1a; }
tfoot td { font-weight: 600; }
details { margin: 0.4rem 0; }
summary { cursor: pointer; padding: 0.2rem 0; }
footer { margin-top: 2rem; border-top: 1px solid #c4ccd6; font-size: 0.85rem; }
@media print {
  nav { display: none; }
  body { max-width: none; padding: 0; }
  details > summary { list-style: none; }
  details::details-content { content-visibility: visible; display: block; }
  table { page-break-inside: auto; }
  tr { page-break-inside: avoid; }
  th { background: #ffffff; }
}
""".strip()


def text(value: Any) -> str:
    """Escaped text for HTML: ``None`` is empty, text-direction and C1 control
    characters are removed, characters HTML cannot carry
    become U+FFFD, and ``& < > " '`` are escaped."""
    raw = "" if value is None else str(value)
    return escape(_ILLEGAL.sub("\ufffd", _REMOVED.sub("", raw)), quote=True)


def safe_href(target: Any) -> Optional[str]:
    """``target`` when it is a link to a section of this file (``#name``,
    letters, digits, ``-`` and ``_`` only), else None. No other link, and
    so no other URL scheme, is ever written."""
    value = "" if target is None else str(target)
    if re.fullmatch(r"#[A-Za-z][A-Za-z0-9_-]{0,63}", value):
        return value
    return None


def logo_data_uri(path: Optional[Path]) -> Optional[str]:
    """The logo as a ``data:`` URI, or None when there is no logo.

    Only PNG and JPEG files are embedded; the file content decides, not the
    name. Anything else (SVG can carry script) raises ValueError.
    """
    if path is None:
        return None
    data = Path(path).read_bytes()
    if data.startswith(_PNG):
        kind = "image/png"
    elif data.startswith(_JPEG):
        kind = "image/jpeg"
    else:
        raise ValueError("the logo is not a PNG or JPEG file")
    return f"data:{kind};base64,{base64.b64encode(data).decode('ascii')}"


def branding_of(*templates) -> Dict[str, Any]:
    """Branding for the HTML report from the first report template given
    (``--word-template``, then ``--excel-template``): its document title
    (placeholders filled in as for that report), company name and logo. The
    logo was checked when the template was loaded (PNG or JPEG, in the
    template's own folder). Empty when no template was given."""
    for template in templates:
        if template is not None:
            return {"template": template}
    return {}


def _resolve_branding(branding: Dict[str, Any], rows: List[Dict]) -> Dict[str, Any]:
    template = branding.get("template")
    if template is None:
        return branding
    from .report_template import build_context

    context = build_context(template, rows)
    return {
        "title": context.get("document_title") or "",
        "company_name": context.get("company_name") or "",
        "logo_file": getattr(template, "logo_file", None),
    }


def generated_now() -> str:
    """The time shown in the report header (UTC, to the minute)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _cell(value: Any) -> str:
    if isinstance(value, dict):
        value = ", ".join(f"{k}={v}" for k, v in value.items())
    elif isinstance(value, (list, tuple, set)):
        value = ", ".join(str(v) for v in value)
    return text(value)


def _table(
    caption: str,
    headings: Sequence[Any],
    rows: Iterable[Sequence[Any]],
    footer: Optional[Sequence[Any]] = None,
) -> str:
    parts = ['<div class="scroll"><table>', f"<caption>{text(caption)}</caption>"]
    parts.append("<thead><tr>")
    parts.extend(f'<th scope="col">{text(h)}</th>' for h in headings)
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{_cell(v)}</td>" for v in row) + "</tr>")
    parts.append("</tbody>")
    if footer is not None:
        parts.append(
            "<tfoot><tr>"
            + "".join(f"<td>{_cell(v)}</td>" for v in footer)
            + "</tr></tfoot>"
        )
    parts.append("</table></div>")
    return "".join(parts)


def _records_table(caption: str, records: Any) -> str:
    """A table of a list of mappings: one column per key, in first-seen order."""
    rows = [r for r in (records or []) if isinstance(r, dict)]
    keys: List[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    return _table(caption, keys, ([row.get(k, "") for k in keys] for row in rows))


def _section(anchor: str, heading: str, body: str) -> str:
    return (
        f'<section id="{anchor}" aria-labelledby="{anchor}-h">'
        f'<h2 id="{anchor}-h">{text(heading)}</h2>{body}</section>'
    )


def _service_rows(converter, rows: List[Dict[str, Any]]):
    """Headings and cells of one service, as the default Excel sheet has them."""
    flattened = [converter._flatten_dict(row) for row in rows]
    headers = set()
    for flat in flattened:
        headers.update(flat.keys())
    fields = converter._get_logical_column_order(headers)
    cells = (
        [
            (
                flat[f]
                if f in flat
                else converter._format_structured_value(row.get(f, ""))
            )
            for f in fields
        ]
        for row, flat in zip(rows, flattened)
    )
    return fields, cells


def _summary(services: Dict[str, List], rows: List[Dict], notes: Sequence[str]):
    total = sum(len(group) for group in services.values())
    by_service = [
        (name, len(group), f"{(len(group) / total * 100) if total else 0:.1f}%")
        for name, group in services.items()
    ]
    regions: Dict[str, int] = {}
    for row in rows:
        region = str(row.get("region") or "Unknown")
        regions[region] = regions.get(region, 0) + 1
    body = [
        _table(
            "Resources by service",
            ["Service", "Resource Count", "Percentage"],
            by_service,
            footer=["TOTAL", total, "100.0%"],
        ),
        _table(
            "Resources by region",
            ["Region", "Resource Count"],
            sorted(regions.items(), key=lambda kv: kv[0].lower()),
        ),
    ]
    if notes:
        body.append('<h3 id="run-notes">Run notes</h3><ul>')
        body.extend(f"<li>{text(note)}</li>" for note in notes)
        body.append("</ul>")
    return "".join(body)


def _resources(converter, services: Dict[str, List]) -> str:
    if not services:
        return f"<p>{text(NO_RESOURCES)}</p>"
    parts = []
    for number, (service, rows) in enumerate(services.items(), 1):
        fields, cells = _service_rows(converter, rows)
        parts.append(
            f'<details id="service-{number}"><summary><h3>{text(service)} '
            f"({len(rows)})</h3></summary>"
            + _table(f"{service} resources", fields, cells)
            + "</details>"
        )
    return "".join(parts)


def _policy_summary(compliance: Any) -> Optional[Dict[str, Any]]:
    """The ``summary`` of a tag policy result (the compliance checker's, or a
    template run's tag compliance), else None. The processor's own counts of
    ``compliance_status`` (``unknown`` without a policy) are not shown."""
    if isinstance(compliance, dict) and isinstance(compliance.get("summary"), dict):
        return compliance["summary"]
    return None


def _compliance(summary: Dict[str, Any]) -> str:
    rows = [
        (key, value)
        for key, value in summary.items()
        if not (isinstance(value, list) and value and isinstance(value[0], dict))
    ]
    return _table("Tag compliance summary", ["Item", "Value"], rows)


def _network(analysis: Dict[str, Any]) -> str:
    rows = [
        (
            vpc_id,
            getattr(a, "vpc_name", ""),
            getattr(a, "cidr_block", ""),
            getattr(a, "total_ips", ""),
            getattr(a, "available_ips", ""),
            f"{getattr(a, 'utilization_percentage', 0):.1f}%",
            len(getattr(a, "subnets", []) or []),
            len(getattr(a, "associated_resources", []) or []),
        )
        for vpc_id, a in analysis.items()
    ]
    return _table(
        "VPCs",
        [
            "VPC ID",
            "VPC Name",
            "CIDR Block",
            "Total IPs",
            "Available IPs",
            "Utilization %",
            "Subnet Count",
            "Associated Resources",
        ],
        rows,
    )


def _security(analysis: Dict[str, Any]) -> str:
    rows = []
    for sg_id, a in analysis.items():
        permissive = [
            f"{r.protocol}:{r.port_range}"
            for r in getattr(a, "inbound_rules", []) or []
            if "0.0.0.0/0" in str(getattr(r, "source_destination", ""))
        ]
        rows.append(
            (
                sg_id,
                getattr(a, "group_name", ""),
                getattr(a, "vpc_id", ""),
                getattr(a, "risk_level", ""),
                len(getattr(a, "inbound_rules", []) or []),
                len(getattr(a, "outbound_rules", []) or []),
                len(getattr(a, "associated_resources", []) or []),
                "Yes" if permissive else "No",
                ", ".join(permissive),
            )
        )
    return _table(
        "Security groups",
        [
            "Security Group ID",
            "Group Name",
            "VPC ID",
            "Risk Level",
            "Inbound Rules",
            "Outbound Rules",
            "Associated Resources",
            "Has Permissive Rules",
            "Permissive Rule Details",
        ],
        rows,
    )


def _finops(finops: Dict[str, Any]) -> str:
    from .finops_sheet import COLUMNS, NOTE, SUMMARY_COLUMNS, _FIELDS

    titles = {s["policy"]: s["check"] for s in finops.get("summary", [])}
    findings = (
        [
            titles.get(f["policy"]) if field is None else f.get(field)
            for field in _FIELDS
        ]
        for f in finops.get("findings", [])
    )
    counts = (
        [e["policy"], e["check"], e["fail"], e["not_evaluated"], e["pass"]]
        for e in finops.get("summary", [])
    )
    return (
        f'<p class="note">{text(NOTE)}</p>'
        + _table("FinOps findings", COLUMNS, findings)
        + _table("FinOps checks: counts", SUMMARY_COLUMNS, counts)
    )


def _finops_costs(costs: Dict[str, Any]) -> str:
    from ..finops.cost_allocation import NO_VALUE, status_text, table_label
    from .finops_costs_sheet import COLUMNS, NOTE

    rows = []
    metric = costs.get("metric", "")
    for account in costs.get("accounts", []):
        period = account.get("period", {})
        for name, table in account.get("tables", {}).items():
            base = [account.get("account"), table_label(name)]
            tail = [metric, period.get("start"), period.get("end")]
            items = table.get("rows", [])
            if not items:
                rows.append(
                    base
                    + ["", "", table.get("currency")]
                    + tail
                    + [status_text(table.get("status")) or "no spend returned"]
                )
                continue
            for item in items:
                rows.append(
                    base
                    + [item.get("name"), item.get("amount"), item.get("unit")]
                    + tail
                    + [status_text(table.get("status"))]
                )
    return (
        f'<p class="note">{text(NOTE)}</p>'
        f"<p>{text(NO_VALUE)}: spend without that tag key.</p>"
        + _table("FinOps costs", COLUMNS, rows)
    )


def _coverage(metadata: Dict[str, Any], not_read: frozenset = frozenset()) -> str:
    parts = []
    accounts = metadata.get("account_summary")
    if accounts:
        parts.append(
            _table(
                "Accounts",
                [
                    "Account ID",
                    "Account Name",
                    "Resources",
                    "Errors",
                    "Read in part",
                ],
                (
                    (
                        a.get("account_id"),
                        a.get("account_name"),
                        a.get("resource_count"),
                        a.get("error_count"),
                        (
                            "Yes"
                            if a.get("partial") or str(a.get("account_id")) in not_read
                            else "No"
                        ),
                    )
                    for a in accounts
                    if isinstance(a, dict)
                ),
            )
        )
    summary = metadata.get("coverage_summary")
    if isinstance(summary, dict) and summary:
        extra = sorted(
            {k for counts in summary.values() for k in counts} - set(OUTCOMES)
        )
        outcomes = list(OUTCOMES) + extra
        parts.append(
            _table(
                "Listings by outcome",
                ["Account ID", *outcomes],
                (
                    [account, *(counts.get(o, 0) for o in outcomes)]
                    for account, counts in sorted(summary.items())
                ),
            )
        )
    denied = metadata.get("permissions_denied")
    if denied:
        parts.append(_records_table("Permissions denied", denied))
    if not parts:
        parts.append("<p>No coverage data in this run.</p>")
    return "".join(parts)


def render_html_report(
    scope_data,
    converter=None,
    branding: Optional[Dict[str, Any]] = None,
    notes: Sequence[str] = (),
    generated_at: str = "",
    accounts_not_read: Iterable[str] = (),
) -> str:
    """The report as text. ``scope_data`` is a BOMData (or anything with the
    same attributes). ``converter`` is the BOMConverter of the report scope:
    its ``prepare_data`` masks the rows as for Excel. ``branding`` may have
    ``company_name``, ``title`` and ``logo_file`` (a Path).
    ``accounts_not_read``: the accounts with a listing that was not read (the
    accounts the "Not read in account" run notes name); their row in the
    accounts table says ``Read in part: Yes``, as for an account that
    stopped early."""
    from .converter import BOMConverter, _group_by_service

    if converter is None:
        converter = BOMConverter(enrich_vpc_info=False)
    rows = [r for r in converter.prepare_data(scope_data) if isinstance(r, dict)]
    services = _group_by_service(rows)
    metadata = getattr(scope_data, "generation_metadata", None) or {}
    compliance = getattr(scope_data, "compliance_summary", None) or {}
    branding = _resolve_branding(branding or {}, rows)
    title = branding.get("title") or DEFAULT_TITLE
    company = branding.get("company_name") or ""
    logo = logo_data_uri(branding.get("logo_file"))

    sections = [("summary", "Summary", _summary(services, rows, notes))]
    sections.append(
        ("resources", "Resources by service", _resources(converter, services))
    )
    policy = _policy_summary(compliance)
    if policy is not None:
        sections.append(("compliance", "Tag compliance", _compliance(policy)))
    network = getattr(converter, "network_analysis", None)
    if (converter.enable_advanced_analysis or converter.analyze_network) and network:
        sections.append(("network", "Network analysis", _network(network)))
    security = getattr(converter, "security_analysis", None)
    if (converter.enable_advanced_analysis or converter.analyze_security) and security:
        sections.append(("security", "Security analysis", _security(security)))
    if converter.finops_checks is not None:
        sections.append(("finops", "FinOps", _finops(converter.finops_checks)))
    if converter.finops_costs is not None:
        sections.append(
            ("finops-costs", "FinOps costs", _finops_costs(converter.finops_costs))
        )
    sections.append(
        (
            "coverage",
            "Coverage and errors",
            _coverage(metadata, frozenset(str(a) for a in accounts_not_read)),
        )
    )

    nav = "".join(
        f'<li><a href="{safe_href("#" + anchor)}">{text(heading)}</a></li>'
        for anchor, heading, _ in sections
    )
    head = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f'<meta http-equiv="Content-Security-Policy" content="{text(CSP)}">',
        '<meta name="referrer" content="no-referrer">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{text(title)}</title>",
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body>",
        "<header>",
    ]
    if logo:
        alt = f"{company} logo" if company else "Logo"
        head.append(f'<img src="{text(logo)}" alt="{text(alt)}">')
    head.append(f"<h1>{text(title)}</h1>")
    if company:
        head.append(f"<p>{text(company)}</p>")
    if generated_at:
        head.append(f"<p>Generated: {text(generated_at)}</p>")
    head.append(f'<p class="note">{text(PRIVACY_NOTE)}</p>')
    head.append("</header>")
    head.append(f'<nav aria-label="Contents"><h2>Contents</h2><ul>{nav}</ul></nav>')
    body = ["<main>"]
    body.extend(_section(anchor, heading, html) for anchor, heading, html in sections)
    body.append("</main>")
    body.append(
        "<footer><p>Written by InvenTag. A static file: no script, no external "
        "resource.</p></footer>"
    )
    body.append("</body>")
    body.append("</html>")
    return "\n".join(head + body) + "\n"


def write_html_report(
    scope_data,
    path,
    converter=None,
    branding: Optional[Dict[str, Any]] = None,
    notes: Sequence[str] = (),
    generated_at: str = "",
    accounts_not_read: Iterable[str] = (),
) -> str:
    """Write the report to ``path`` whole or not at all (owner-only file).
    Returns ``path`` as text."""
    document = render_html_report(
        scope_data,
        converter=converter,
        branding=branding,
        notes=notes,
        generated_at=generated_at,
        accounts_not_read=accounts_not_read,
    )

    def write(temp_path: str) -> None:
        with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(document)

    return save_atomically(path, write)
