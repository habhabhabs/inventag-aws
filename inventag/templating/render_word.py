"""Write a Word BOM from a report template."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, RGBColor

from ..reporting.masking import mask_resources
from ..reporting.safe_save import save_atomically
from .columns import (
    build_columns,
    clean_text,
    format_value,
    get_field,
    group_by_service,
    resource_sort_key,
)
from .loader import safe_relative_path
from .tag_policy import ComplianceReport, rule_summary

DISCLAIMER = (
    "InvenTag is an independent open-source project. It is not affiliated with, "
    "endorsed by or sponsored by Amazon Web Services. This report lists what "
    "InvenTag could discover with the permissions it was given; it is not a "
    "compliance assessment or certification."
)


def _hex(value: str) -> str:
    return value.lstrip("#").upper()


def _style_header_row(table, spec: Dict[str, Any]) -> None:
    fill = _hex(spec["colors"]["header_fill"])
    text = _hex(spec["colors"]["header_text"])
    row = table.rows[0]
    # Repeat the header row on every page and mark it as a header for
    # screen readers.
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)
    for cell in row.cells:
        shading = OxmlElement("w:shd")
        shading.set(qn("w:val"), "clear")
        shading.set(qn("w:color"), "auto")
        shading.set(qn("w:fill"), fill)
        cell._tc.get_or_add_tcPr().append(shading)
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.color.rgb = RGBColor.from_string(text)


def _table(doc, spec, headers: List[str], rows: List[List[str]]):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, text in enumerate(headers):
        table.rows[0].cells[i].text = clean_text(text)
    for values in rows:
        cells = table.add_row().cells
        for i, value in enumerate(values):
            cells[i].text = clean_text(value)
    _style_header_row(table, spec)
    return table


def _set_alt_text(inline_shape, text: str) -> None:
    doc_pr = inline_shape._inline.docPr
    doc_pr.set("descr", text)
    doc_pr.set("title", text)


def _cover(doc, spec, template, resources, metadata) -> None:
    logo = spec.get("logo")
    if logo:
        path = safe_relative_path(template.directory, logo)
        alt = spec.get("logo_alt_text") or (
            f"{spec['company_name']} logo" if spec.get("company_name") else "Logo"
        )
        shape = doc.add_picture(str(path), width=Inches(1.5))
        _set_alt_text(shape, alt)
    doc.add_heading(spec["title"], level=0)
    if spec.get("subtitle"):
        doc.add_paragraph(spec["subtitle"])
    if spec.get("company_name"):
        doc.add_paragraph(f"Prepared for {spec['company_name']}")
    doc.add_paragraph(f"Generated: {metadata['generated_at']}")


def _summary(doc, spec, resources) -> None:
    doc.add_heading("Summary", level=1)
    accounts = {str(r.get("source_account_id") or "") for r in resources} - {""}
    regions = {str(r.get("region") or "") for r in resources} - {""}
    services = group_by_service(resources)
    for line in (
        f"Resources: {len(resources)}",
        f"Services: {len(services)}",
        f"Accounts: {len(accounts)}",
        f"Regions: {len(regions)}",
    ):
        doc.add_paragraph(line, style="List Bullet")


def _service_summary(doc, spec, resources) -> None:
    doc.add_heading("Resources by service", level=1)
    groups = group_by_service(resources)
    total = len(resources)
    if not groups:
        doc.add_paragraph("No resources were found.")
        return
    rows = [
        [service, str(len(items)), f"{len(items) / total * 100:.1f}%"]
        for service, items in groups.items()
    ]
    rows.append(["Total", str(total), "100.0%"])
    _table(doc, spec, ["Service", "Resources", "Share"], rows)


def _tag_compliance(doc, spec, compliance: Optional[ComplianceReport]) -> None:
    if compliance is None:
        return
    doc.add_heading("Tag compliance", level=1)
    intro = f"Policy: {compliance.policy_name}."
    if compliance.policy_description:
        intro += f" {compliance.policy_description}"
    doc.add_paragraph(intro)
    doc.add_paragraph(
        f"{compliance.compliant} of {compliance.checked} resources checked meet the "
        f"policy ({compliance.percent_compliant:.1f}%). "
        f"{compliance.out_of_scope} resources were out of scope."
    )
    doc.add_heading("Required tags", level=2)
    missing = compliance.missing_by_key()
    invalid = compliance.invalid_by_key()
    _table(
        doc,
        spec,
        ["Tag key", "Rule", "Missing", "Invalid value"],
        [
            [
                rule["key"],
                rule_summary(rule),
                str(missing.get(rule["key"], 0)),
                str(invalid.get(rule["key"], 0)),
            ]
            for rule in compliance.rules
        ],
    )
    bad = sorted(
        (f for f in compliance.findings if not f.compliant),
        key=lambda f: resource_sort_key(f.resource),
    )
    if not bad:
        return
    doc.add_heading("Non-compliant resources", level=2)
    limit = spec["word"]["max_noncompliant_rows"]
    _table(
        doc,
        spec,
        ["Service", "Resource", "Missing tags", "Problems"],
        [
            [
                str(f.resource.get("service") or ""),
                str(
                    f.resource.get("resource_name")
                    or f.resource.get("resource_id")
                    or f.resource.get("arn")
                    or ""
                ),
                ", ".join(f.missing),
                "; ".join(f.invalid),
            ]
            for f in bad[:limit]
        ],
    )
    if len(bad) > limit:
        doc.add_paragraph(
            f"Showing {limit} of {len(bad)} non-compliant resources. The Excel "
            "report and the JSON file list all of them."
        )


def _service_tables(doc, spec, resources) -> None:
    word = spec["word"]
    columns_spec = word["columns"]
    if columns_spec is None:
        columns_spec = spec["columns"][: word["max_columns"]]
    doc.add_heading("Resource details", level=1)
    groups = group_by_service(resources)
    if not groups:
        doc.add_paragraph("No resources were found.")
        return
    limit = word["max_rows_per_service"]
    for service, items in groups.items():
        doc.add_heading(clean_text(f"{service} ({len(items)})"), level=2)
        columns = build_columns(spec, items, columns=columns_spec, with_tags=False)
        rows = [
            [format_value(get_field(r, c[0]), c[0]) for c in columns]
            for r in items[:limit]
        ]
        _table(doc, spec, [c[1] for c in columns], rows)
        if len(items) > limit:
            doc.add_paragraph(
                f"Showing {limit} of {len(items)} {service} resources; "
                f"{len(items) - limit} are not listed here. The Excel report "
                "lists all of them (use --create-excel)."
            )


def _about(doc, spec, template, metadata) -> None:
    doc.add_heading("About this report", level=1)
    doc.add_paragraph(
        f"Generated by InvenTag on {metadata['generated_at']} using the "
        f"'{template.name}' report template."
    )
    doc.add_paragraph(DISCLAIMER)


def render_word(
    path: str,
    resources: List[Dict[str, Any]],
    template,
    compliance: Optional[ComplianceReport] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Write the document to ``path`` and return the path."""
    resources = mask_resources(resources)  # no secret value goes into a file
    spec = template.spec
    metadata = dict(metadata or {})
    metadata.setdefault(
        "generated_at", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )
    doc = Document()
    doc.core_properties.title = spec["title"]
    doc.core_properties.author = "InvenTag"
    if spec["word"]["orientation"] == "landscape":
        section = doc.sections[0]
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = (
            section.page_height,
            section.page_width,
        )
    renderers = {
        "cover": lambda: _cover(doc, spec, template, resources, metadata),
        "summary": lambda: _summary(doc, spec, resources),
        "service-summary": lambda: _service_summary(doc, spec, resources),
        "tag-compliance": lambda: _tag_compliance(doc, spec, compliance),
        "service-tables": lambda: _service_tables(doc, spec, resources),
        "about": lambda: _about(doc, spec, template, metadata),
    }
    for section_name in spec["word"]["sections"]:
        renderers[section_name]()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    save_atomically(path, doc.save)
    return path
