"""ExcelWorkbookBuilder and WordDocumentBuilder: odd data, limits and failed saves.

Every test writes a real file and opens it again with openpyxl or python-docx.
"""

import os

import pytest
from docx import Document
from openpyxl import load_workbook

from inventag.reporting import document_generator as dg
from inventag.reporting.bom_processor import BOMData
from inventag.reporting.document_generator import (
    DocumentConfig,
    clean_bom_data,
    limit_text,
    safe_sheet_name,
    save_atomically,
)
from inventag.reporting.excel_builder import ExcelWorkbookBuilder
from inventag.reporting.word_builder import WordDocumentBuilder

BASE = {
    "type": "Instance",
    "id": "i-1",
    "name": "n",
    "region": "us-east-1",
    "compliance_status": "non_compliant",
}


def make_bom(resources):
    total = len(resources)
    return BOMData(
        resources=resources,
        generation_metadata={"generated_at": "now", "total_resources": total},
        compliance_summary={
            "total_resources": total,
            "compliant_resources": 0,
            "non_compliant_resources": total,
            "compliance_percentage": 0.0,
        },
    )


def build_excel(tmp_path, resources, config=None):
    path = str(tmp_path / "out.xlsx")
    result = ExcelWorkbookBuilder(config or DocumentConfig()).generate_document(
        make_bom(resources), path
    )
    assert result.success, result.error_message
    return result, load_workbook(path)


def build_word(tmp_path, resources, config=None):
    path = str(tmp_path / "out.docx")
    result = WordDocumentBuilder(config or DocumentConfig()).generate_document(
        make_bom(resources), path
    )
    assert result.success, result.error_message
    return result, Document(path)


# ---------------------------------------------------------------- sheet names
def test_safe_sheet_name_rules():
    taken = set()
    long_a = safe_sheet_name("A" * 40 + "1", taken)
    long_b = safe_sheet_name("A" * 40 + "2", taken)
    assert len(long_a) == len(long_b) == 31
    assert long_a != long_b and long_b.endswith(" (2)")
    assert safe_sheet_name("a/b:c?*[x]\\", taken) == "a_b_c___x__"
    # Excel compares sheet names without regard to case
    assert safe_sheet_name("ec2", taken) == "ec2"
    assert safe_sheet_name("EC2", taken) == "EC2 (2)"
    assert safe_sheet_name("", taken) == "Sheet"
    assert safe_sheet_name(None, taken) == "Sheet (2)"
    assert safe_sheet_name("'quoted'", taken) == "quoted"
    assert safe_sheet_name("History", taken) == "History (2)"
    for name in taken:
        assert len(name) <= 31


def test_service_sheets_are_valid_unique_and_show_the_full_name(tmp_path):
    long1, long2 = "S" * 40 + "-one", "S" * 40 + "-two"
    resources = [
        dict(BASE, service=long1),
        dict(BASE, service=long2),
        dict(BASE, service="a/b:c"),
        dict(BASE, service="Network Analysis"),  # same name as a fixed sheet
        dict(BASE, service="ec2"),
        dict(BASE, service="EC2"),
        dict(BASE, service=None),
        dict(BASE, service=""),
    ]
    result, wb = build_excel(tmp_path, resources)
    names = wb.sheetnames
    assert len({n.lower() for n in names}) == len(names)
    assert all(len(n) <= 31 for n in names)
    assert not any(set("[]:*?/\\") & set(n) for n in names)
    for fixed in (
        "Executive Summary",
        "Network Analysis",
        "Security Analysis",
        "Compliance Details",
    ):
        assert fixed in names
    # The fixed "Network Analysis" sheet is the real one, not the service's
    assert wb["Network Analysis"]["A1"].value == "Network Analysis & Capacity Planning"
    # Every service sheet carries the full service name in its title row
    titles = {
        ws["A1"].value for ws in wb.worksheets if ws["A1"].value.endswith(" Resources")
    }
    assert f"{long1} Resources" in titles and f"{long2} Resources" in titles
    assert "a/b:c Resources" in titles
    assert "Unknown Resources" in titles
    assert any("Network Analysis" in w and "limited" in w for w in result.warnings)


# ------------------------------------------------------------ odd cell values
def test_illegal_xml_characters_do_not_stop_the_report(tmp_path):
    resources = [
        dict(
            BASE,
            service="EC2",
            name="bad\x00\x01name",
            tags={"k\x08ey": "v\x0balue"},
        )
    ]
    _, wb = build_excel(tmp_path, resources)
    ws = wb["EC2"]
    values = [c.value for row in ws.iter_rows() for c in row if c.value]
    assert "bad��name" in values
    assert "tags.k�ey" in values and "v�alue" in values
    _, doc = build_word(tmp_path, resources)
    text = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "bad��name" in text


def test_formula_like_tag_values_are_text(tmp_path):
    values = ['=HYPERLINK("http://x","y")', "+1+1", "-2+3", "@SUM(A1)", "=1+1"]
    resources = [
        dict(BASE, service="EC2", name=v, tags={"Owner": v, f"={i}": v})
        for i, v in enumerate(values)
    ]
    _, wb = build_excel(tmp_path, resources)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                assert cell.data_type != "f", (ws.title, cell.coordinate, cell.value)
    written = {c.value for row in wb["EC2"].iter_rows() for c in row}
    assert set(values) <= written  # the text is kept as discovered


def test_cell_over_excel_limit_is_cut_with_a_visible_note(tmp_path):
    resources = [dict(BASE, service="EC2", name="x" * 40000)]
    _, wb = build_excel(tmp_path, resources)
    longest = max(
        (c.value for row in wb["EC2"].iter_rows() for c in row if c.value),
        key=lambda v: len(str(v)),
    )
    assert len(longest) == 32767
    assert longest.endswith("[truncated, 40000 characters in total]")
    assert limit_text("short") == "short"


def test_numbers_stay_numbers_and_dates_keep_their_offset(tmp_path):
    from datetime import datetime, timezone

    resources = [
        dict(
            BASE,
            service="EC2",
            size_gb=100,
            ratio=0.5,
            big=10**20,
            nan=float("nan"),
            flag=True,
            created=datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )
    ]
    _, wb = build_excel(tmp_path, resources)
    ws = wb["EC2"]
    header = {c.value: c.column for c in ws[8] if c.value}
    row = {name: ws.cell(row=9, column=col) for name, col in header.items()}
    assert row["size_gb"].value == 100 and row["size_gb"].data_type == "n"
    assert row["ratio"].value == 0.5
    assert row["big"].value == str(10**20)
    assert row["nan"].value == "nan"
    assert row["flag"].value == "True"
    assert row["created"].value == "2024-01-02 03:04:05+00:00"


def test_header_is_frozen_and_filtered(tmp_path):
    resources = [dict(BASE, service="EC2", id=f"i-{i}") for i in range(5)]
    _, wb = build_excel(tmp_path, resources)
    ws = wb["EC2"]
    assert ws.freeze_panes == "A9"
    ref = ws.auto_filter.ref
    first, last = ref.split(":")
    assert first == "A8"
    assert last.endswith("13")  # header row 8 + 5 data rows
    # the filter ends at the last header column
    header_cells = [c for c in ws[8] if c.value is not None]
    assert last.rstrip("0123456789") == header_cells[-1].column_letter


def test_very_wide_tag_set_is_capped_and_reported(tmp_path):
    tags = {f"tag{i:05d}": "v" for i in range(17000)}
    result, wb = build_excel(tmp_path, [dict(BASE, service="EC2", tags=tags)])
    ws = wb["EC2"]
    assert ws.max_column == 16384
    assert "columns do not fit" in ws["A2"].value
    assert any("columns do not fit" in w for w in result.warnings)


# -------------------------------------------------------------- failed writes
@pytest.mark.parametrize(
    "builder_class,ext",
    [
        (ExcelWorkbookBuilder, "xlsx"),
        (WordDocumentBuilder, "docx"),
    ],
)
def test_failed_save_leaves_no_file_and_keeps_the_old_one(
    tmp_path, monkeypatch, builder_class, ext
):
    path = tmp_path / f"report.{ext}"
    path.write_bytes(b"previous report")

    def failing_save(temporary):
        with open(temporary, "wb") as f:
            f.write(b"half")
        raise OSError("disk full")

    monkeypatch.setattr(
        dg,
        "save_atomically",
        lambda output, save: save_atomically(output, failing_save),
    )
    import inventag.reporting.excel_builder as eb
    import inventag.reporting.word_builder as wbld

    monkeypatch.setattr(eb, "save_atomically", dg.save_atomically)
    monkeypatch.setattr(wbld, "save_atomically", dg.save_atomically)
    result = builder_class(DocumentConfig()).generate_document(
        make_bom([dict(BASE, service="EC2")]), str(path)
    )
    assert not result.success
    assert "OSError" in result.error_message and "disk full" in result.error_message
    assert path.read_bytes() == b"previous report"
    assert os.listdir(tmp_path) == [path.name]  # no temporary file left


def test_save_atomically_success_is_private_and_replaces(tmp_path):
    target = tmp_path / "a.bin"
    seen = {}

    def save(temporary):
        seen["temporary"] = temporary
        with open(temporary, "wb") as f:
            f.write(b"done")

    save_atomically(str(target), save)
    assert target.read_bytes() == b"done"
    assert not os.path.exists(seen["temporary"])
    assert (target.stat().st_mode & 0o777) == 0o600


def test_unwritable_directory_gives_a_clear_error(tmp_path):
    result = ExcelWorkbookBuilder(DocumentConfig()).generate_document(
        make_bom([dict(BASE, service="EC2")]), str(tmp_path / "missing" / "x.xlsx")
    )
    assert not result.success
    assert "FileNotFoundError" in result.error_message


def test_clean_bom_data_copies_only_when_needed():
    clean = make_bom([dict(BASE, service="EC2", tags={"a": ["b"]})])
    assert clean_bom_data(clean) is clean
    dirty = make_bom([dict(BASE, service="EC2", tags={"a": ["b\x00"]})])
    cleaned = clean_bom_data(dirty)
    assert cleaned is not dirty
    assert cleaned.resources[0]["tags"]["a"] == ["b�"]
    assert dirty.resources[0]["tags"]["a"] == ["b\x00"]  # input is not changed


# ------------------------------------------------------------------ Word rows
def word_service_note_paragraphs(doc):
    return [p.text for p in doc.paragraphs if p.text.startswith("Showing ")]


def service_table_rows(doc, header="Id"):
    for table in doc.tables:
        if table.rows[0].cells[0].text == header:
            yield table


def test_word_shows_all_rows_by_default_and_says_nothing_is_cut(tmp_path):
    resources = [dict(BASE, service="EC2", id=f"i-{i:03d}") for i in range(120)]
    result, doc = build_word(tmp_path, resources)
    assert word_service_note_paragraphs(doc) == []
    table = next(service_table_rows(doc))
    assert len(table.rows) == 121


def test_word_row_limit_says_how_many_are_shown_and_where_the_rest_is(tmp_path):
    resources = [dict(BASE, service="EC2", id=f"i-{i:03d}") for i in range(120)]
    resources += [
        dict(BASE, service="S3", id=f"b-{i}", compliance_status="compliant")
        for i in range(3)
    ]
    config = DocumentConfig(max_rows_per_service=50)
    result, doc = build_word(tmp_path, resources, config)
    table = next(service_table_rows(doc))
    assert len(table.rows) == 51  # header + 50
    notes = word_service_note_paragraphs(doc)
    assert any(
        n.startswith("Showing 50 of 120 EC2 resources; 70 are not listed here.")
        and "Excel report" in n
        for n in notes
    ), notes
    # a service under the limit gets no row note
    assert not any("S3 resources;" in n for n in notes)
    # the non-compliant list is cut the same way and says so
    assert any(
        n.startswith("Showing 50 of 120 non-compliant resources") for n in notes
    ), notes
    assert any("Showing 50 of 120 EC2" in w for w in result.warnings)


def test_word_says_when_fields_were_left_out_of_a_table(tmp_path):
    resource = dict(BASE, service="EC2", **{f"extra{i}": i for i in range(10)})
    _, doc = build_word(tmp_path, [resource])
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "The table shows 8 of " in text


def test_word_cell_text_over_the_limit_is_cut_with_a_note(tmp_path):
    _, doc = build_word(tmp_path, [dict(BASE, service="EC2", name="y" * 50000)])
    cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    longest = max(cells, key=len)
    assert len(longest) == 32767 and "truncated, 50000 characters" in longest


def test_word_service_headings_survive_odd_service_names(tmp_path):
    resources = [dict(BASE, service=None), dict(BASE, service="a/b\x00c")]
    _, doc = build_word(tmp_path, resources)
    headings = [p.text for p in doc.paragraphs if p.style.name == "Heading 2"]
    assert "Unknown Resources" in headings and "a/b�c Resources" in headings
