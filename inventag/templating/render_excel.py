"""Write an Excel BOM from a report template."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ..security.secret_values import mask_resources
from ..reporting.safe_save import save_atomically
from .columns import (
    EXCEL_CELL_LIMIT,
    build_columns,
    clean_text,
    format_value,
    get_field,
    group_by_service,
    resource_sort_key,
    unique_sheet_name,
)
from .tag_policy import ComplianceReport, rule_summary


def _color(value: str) -> str:
    return value.lstrip("#").upper()


class _Styler:
    def __init__(self, spec: Dict[str, Any]):
        colors = spec["colors"]
        self.fill = PatternFill(
            start_color=_color(colors["header_fill"]),
            end_color=_color(colors["header_fill"]),
            fill_type="solid",
        )
        self.font = Font(bold=True, color=_color(colors["header_text"]))
        self.max_width = spec["excel"]["max_column_width"]

    def header(self, ws, row: int, headers: List[str]) -> None:
        for col, text in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=clean_text(str(text)))
            cell.font = self.font
            cell.fill = self.fill
            cell.alignment = Alignment(vertical="center")


def _write(ws, row: int, col: int, value: Any):
    if isinstance(value, str):
        # Control characters make openpyxl refuse the cell; a cell holds at most
        # 32,767 characters.
        value = clean_text(value)[:EXCEL_CELL_LIMIT]
    cell = ws.cell(row=row, column=col, value=value)
    # Never let data from AWS become a formula (CSV/formula injection): a text
    # that starts with = + - or @ is stored as text.
    if isinstance(value, str) and value:
        cell.data_type = "s"
    return cell


def _fit_columns(ws, max_width: int, fixed: Optional[Dict[int, int]] = None) -> None:
    fixed = fixed or {}
    for column in ws.columns:
        index = column[0].column
        letter = get_column_letter(index)
        if index in fixed and fixed[index]:
            ws.column_dimensions[letter].width = fixed[index]
            continue
        longest = max(
            (len(str(c.value)) for c in column if c.value is not None), default=8
        )
        ws.column_dimensions[letter].width = min(max(longest + 2, 8), max_width)


def _table_sheet(ws, styler, columns, resources, excel_spec) -> None:
    styler.header(ws, 1, [c[1] for c in columns])
    for row, resource in enumerate(resources, 2):
        for col, (field_name, _, _) in enumerate(columns, 1):
            _write(
                ws, row, col, format_value(get_field(resource, field_name), field_name)
            )
    if excel_spec["freeze_header"]:
        ws.freeze_panes = "A2"
    if excel_spec["autofilter"] and columns:
        ws.auto_filter.ref = (
            f"A1:{get_column_letter(len(columns))}{max(len(resources) + 1, 1)}"
        )
    _fit_columns(
        ws, styler.max_width, {i: c[2] for i, c in enumerate(columns, 1) if c[2]}
    )


def _summary_sheet(
    wb, styler, spec, resources, metadata, compliance, run_notes=None
) -> None:
    ws = wb.create_sheet("Summary", 0)
    ws.cell(row=1, column=1, value=spec["title"]).font = Font(bold=True, size=14)
    row = 2
    if spec.get("subtitle"):
        _write(ws, row, 1, spec["subtitle"])
        row += 1
    if spec.get("company_name"):
        _write(ws, row, 1, spec["company_name"])
        row += 1
    _write(ws, row, 1, f"Generated: {metadata['generated_at']}")
    row += 1
    accounts = sorted({str(r.get("source_account_id") or "") for r in resources} - {""})
    regions = sorted({str(r.get("region") or "") for r in resources} - {""})
    _write(ws, row, 1, f"Accounts: {len(accounts)}   Regions: {len(regions)}")
    row += 2

    groups = group_by_service(resources)
    total = len(resources)
    header_row = row
    styler.header(ws, header_row, ["Service", "Resources", "Share"])
    row += 1
    for service, items in groups.items():
        _write(ws, row, 1, service)
        _write(ws, row, 2, len(items))
        _write(ws, row, 3, f"{(len(items) / total * 100) if total else 0:.1f}%")
        row += 1
    for col, value in enumerate(["Total", total, "100.0%" if total else "0.0%"], 1):
        _write(ws, row, col, value).font = Font(bold=True)
    row += 2

    if compliance is not None:
        ws.cell(row=row, column=1, value="Tag policy").font = Font(bold=True)
        _write(ws, row, 2, compliance.policy_name)
        row += 1
        for label, value in (
            ("Resources checked", compliance.checked),
            ("Compliant", compliance.compliant),
            ("Non-compliant", compliance.non_compliant),
            ("Out of scope", compliance.out_of_scope),
            ("Compliant (%)", f"{compliance.percent_compliant:.1f}%"),
        ):
            _write(ws, row, 1, label)
            _write(ws, row, 2, value)
            row += 1
    if run_notes:
        # What the reader must know (for example, accounts that were not
        # scanned): the same lines the default report shows.
        if compliance is not None:
            row += 1
        ws.cell(row=row, column=1, value="Run notes").font = Font(bold=True)
        for note in run_notes:
            row += 1
            _write(ws, row, 1, note)
    _fit_columns(ws, styler.max_width)
    ws.column_dimensions["A"].width = max(ws.column_dimensions["A"].width, 22)


def _compliance_sheet(wb, styler, compliance: ComplianceReport, used: set) -> None:
    ws = wb.create_sheet(unique_sheet_name("Tag Compliance", used))
    headers = [
        "Account",
        "Region",
        "Service",
        "Type",
        "Resource",
        "ARN",
        "Status",
        "Missing tags",
        "Problems",
    ]
    styler.header(ws, 1, headers)
    ordered = sorted(
        compliance.findings,
        key=lambda f: (f.compliant, resource_sort_key(f.resource)),
    )
    for row, finding in enumerate(ordered, 2):
        r = finding.resource
        values = [
            r.get("source_account_id") or r.get("account_id") or "",
            r.get("region") or "",
            r.get("service") or "",
            r.get("resource_type") or "",
            r.get("resource_name") or r.get("resource_id") or r.get("id") or "",
            r.get("arn") or "",
            finding.status,
            ", ".join(finding.missing),
            "; ".join(finding.invalid),
        ]
        for col, value in enumerate(values, 1):
            _write(ws, row, col, format_value(value))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(ordered) + 1}"
    start = len(ordered) + 3
    ws.cell(row=start, column=1, value="Policy rules").font = Font(bold=True)
    styler.header(ws, start + 1, ["Tag key", "Rule", "Missing", "Invalid value"])
    missing = compliance.missing_by_key()
    invalid = compliance.invalid_by_key()
    for offset, rule in enumerate(compliance.rules, start + 2):
        _write(ws, offset, 1, rule["key"])
        _write(ws, offset, 2, rule_summary(rule))
        _write(ws, offset, 3, missing.get(rule["key"], 0))
        _write(ws, offset, 4, invalid.get(rule["key"], 0))
    _fit_columns(ws, styler.max_width)


def render_excel(
    path: str,
    resources: List[Dict[str, Any]],
    template,
    compliance: Optional[ComplianceReport] = None,
    metadata: Optional[Dict[str, Any]] = None,
    run_notes: Optional[List[str]] = None,
) -> str:
    """Write the workbook to ``path`` and return the path.

    ``run_notes`` are lines the reader must know (accounts that were not
    scanned and why). They go into the Summary sheet, and only when there are
    some; the sheet is then written even if the template turns it off.
    """
    resources = mask_resources(resources)  # no secret value goes into a file
    spec = template.spec
    excel = spec["excel"]
    metadata = dict(metadata or {})
    metadata.setdefault(
        "generated_at", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )
    styler = _Styler(spec)
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.title = spec["title"]
    wb.properties.creator = "InvenTag"
    if spec.get("company_name"):
        wb.properties.company = spec["company_name"]
    wb.properties.description = f"Generated by InvenTag with template '{template.name}'"

    show_summary = bool(excel["summary_sheet"] or run_notes)
    used = {"summary"} if show_summary else set()
    if excel["layout"] == "single-sheet":
        ws = wb.create_sheet(unique_sheet_name(excel["single_sheet_name"], used))
        columns = build_columns(spec, resources, excel["include_all_fields"])
        if not any(c[0] == "service" for c in columns):
            columns.insert(0, ("service", "Service", None))
        ordered = sorted(resources, key=resource_sort_key)
        _table_sheet(ws, styler, columns, ordered, excel)
    else:
        for service, items in group_by_service(resources).items():
            ws = wb.create_sheet(unique_sheet_name(service, used))
            columns = build_columns(spec, items, excel["include_all_fields"])
            _table_sheet(ws, styler, columns, items, excel)

    if compliance is not None and excel["tag_compliance_sheet"]:
        _compliance_sheet(wb, styler, compliance, used)
    if show_summary:
        _summary_sheet(wb, styler, spec, resources, metadata, compliance, run_notes)
    if not wb.sheetnames:
        wb.create_sheet("Resources")
    wb.active = 0
    save_atomically(path, wb.save)
    return path
