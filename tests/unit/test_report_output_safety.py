"""What the CLI's report writers (converter.py, templating) do with odd data."""

import logging
import os
import stat
import zipfile

import pytest
from docx import Document
from openpyxl import load_workbook

from inventag.reporting.converter import BOMConverter
from inventag.reporting.masking import (
    MASK,
    count_masked,
    mask_resource,
    mask_resources,
)
from inventag.reporting.safe_save import save_atomically
from inventag.templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry
from inventag.templating.render_excel import render_excel
from inventag.templating.render_word import render_word

SECRET = "S3CR3T-PLANTED-VALUE-123"


def converter(rows):
    c = BOMConverter(enrich_vpc_info=False)
    c.data = rows
    return c


def row(service, name="n", **extra):
    return dict(
        service=service,
        type="T",
        id=f"id-{name}",
        name=name,
        region="us-east-1",
        arn=f"arn:aws:x:us-east-1:111111111111:t/{name}",
        **extra,
    )


# ------------------------------------------------------------ sheet names


def test_long_and_odd_service_names_give_unique_valid_sheets(tmp_path, caplog):
    long_a = "A" * 40 + "one"
    long_b = "A" * 40 + "two"
    rows = [
        row(long_a, "1"),
        row(long_b, "2"),
        row("ec2", "3"),
        row("EC2", "4"),
        row("Bad/Name[1]:x?*", "5"),
        row("History", "6"),
        row("Summary", "7"),
    ]
    out = tmp_path / "a.xlsx"
    with caplog.at_level(logging.WARNING):
        converter(rows).export_to_excel(str(out))
    names = load_workbook(out).sheetnames
    assert len(names) == len({n.lower() for n in names}), names
    assert all(len(n) <= 31 and not set("[]:*?/\\") & set(n) for n in names)
    assert "history" not in [n.lower() for n in names]
    assert "sheet name" in caplog.text and "Bad/Name" in caplog.text


def test_templated_sheet_names_are_unique_and_warn(tmp_path, caplog):
    registry = TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])
    rows = [
        dict(row("History", "1"), resource_type="T"),
        dict(row("A" * 40 + "x", "2"), resource_type="T"),
        dict(row("A" * 40 + "y", "3"), resource_type="T"),
    ]
    with caplog.at_level(logging.WARNING):
        path = render_excel(
            str(tmp_path / "t.xlsx"), rows, registry.resolve("standard-bom")
        )
    names = load_workbook(path).sheetnames
    assert len(names) == len({n.lower() for n in names})
    assert "history" not in [n.lower() for n in names]
    assert all(len(n) <= 31 for n in names)
    assert "sheet name" in caplog.text


# ------------------------------------------------ missing and odd fields


ODD = [
    row(None, "none-service"),
    row("EC2", "ctl\x07\x00name", tags={"Owner": "a\x0bb\x1f"}),
    row("EC2", "plain", description="x" * 40000),
]


def test_converter_excel_and_word_survive_odd_data(tmp_path):
    out = tmp_path / "c.xlsx"
    converter(ODD).export_to_excel(str(out))
    wb = load_workbook(out)
    assert "Unknown" in wb.sheetnames
    text = " ".join(
        str(c.value) for ws in wb for r in ws.iter_rows() for c in r if c.value
    )
    assert "ctl��name" in text and "\x07" not in text

    word = tmp_path / "c.docx"
    converter(ODD).export_to_word(str(word))
    doc = Document(word)
    cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    assert any("Unknown" in c for c in cells) or any(
        "Unknown" in p.text for p in doc.paragraphs
    )


def test_templated_excel_and_word_survive_odd_data(tmp_path):
    registry = TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])
    template = registry.resolve("standard-bom")
    rows = [dict(r, resource_name=r["name"], resource_type="T") for r in ODD]
    assert load_workbook(render_excel(str(tmp_path / "t.xlsx"), rows, template))
    assert Document(render_word(str(tmp_path / "t.docx"), rows, template))


# ------------------------------------------------------- atomic writing


def test_failed_save_leaves_no_partial_file_and_keeps_the_old_one(tmp_path):
    target = tmp_path / "report.xlsx"
    target.write_bytes(b"old report")

    def boom(path):
        with open(path, "wb") as handle:
            handle.write(b"half")
        raise RuntimeError("disk full")

    with pytest.raises(RuntimeError):
        save_atomically(target, boom)
    assert target.read_bytes() == b"old report"
    assert os.listdir(tmp_path) == ["report.xlsx"]


def test_successful_save_replaces_and_is_owner_only(tmp_path):
    target = tmp_path / "r.bin"
    save_atomically(target, lambda p: open(p, "wb").write(b"new"))
    assert target.read_bytes() == b"new"
    assert os.listdir(tmp_path) == ["r.bin"]
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_converter_failure_does_not_create_the_report(tmp_path, monkeypatch):
    c = converter([row("EC2")])
    out = tmp_path / "x.xlsx"

    def fail(self, filename):
        raise OSError("no space")

    monkeypatch.setattr("openpyxl.workbook.workbook.Workbook.save", fail)
    with pytest.raises(OSError):
        c.export_to_excel(str(out))
    assert os.listdir(tmp_path) == []


# --------------------------------------------------- Word row limit note


def test_word_note_says_how_many_are_missing_and_where_they_are(tmp_path):
    rows = [row("EC2", f"n{i:03d}") for i in range(60)]
    out = tmp_path / "w.docx"
    converter(rows).export_to_word(str(out))
    text = "\n".join(p.text for p in Document(out).paragraphs)
    assert "Showing first 50 of 60 EC2" in text
    assert "10 EC2 resources are not listed here" in text
    assert "Excel report lists all of them" in text


def test_templated_word_note(tmp_path):
    registry = TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])
    rows = [
        dict(row("EC2", f"n{i}"), resource_name=f"n{i}", resource_type="T")
        for i in range(60)
    ]
    path = render_word(str(tmp_path / "t.docx"), rows, registry.resolve("standard-bom"))
    text = "\n".join(p.text for p in Document(path).paragraphs)
    assert "Showing 50 of 60 EC2 resources; 10 are not listed here" in text


# ---------------------------------------------------- formula injection


@pytest.mark.parametrize("lead", ["=", "+", "-", "@"])
def test_leading_formula_characters_are_stored_as_text(tmp_path, lead):
    value = f"{lead}1+1"
    rows = [row("EC2", value, tags={"Owner": value})]
    out = tmp_path / "f.xlsx"
    converter(rows).export_to_excel(str(out))
    for ws in load_workbook(out):
        for r in ws.iter_rows():
            for cell in r:
                assert cell.data_type != "f"
    # templating
    registry = TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])
    t = dict(rows[0], resource_name=value, resource_type="T")
    wb = load_workbook(
        render_excel(str(tmp_path / "t.xlsx"), [t], registry.resolve("standard-bom"))
    )
    cells = [c for ws in wb for r in ws.iter_rows() for c in r if c.value == value]
    assert cells and all(c.data_type == "s" for c in cells)


# ------------------------------------------------------------- masking


def lambda_like():
    return {
        "service": "LAMBDA",
        "id": "fn",
        "tags": {"Password": "tag-value-stays"},
        "raw_data": {
            "Environment": {"Variables": {"DB_PASSWORD": SECRET, "EMPTY": ""}},
            "boto3_config": {"Environment": {"Variables": {"K": SECRET}}},
        },
    }


def test_masking_hides_values_and_keeps_names():
    r, n = mask_resource(lambda_like())
    assert n == 2
    assert r["raw_data"]["Environment"]["Variables"] == {
        "DB_PASSWORD": MASK,
        "EMPTY": "",
    }
    assert r["raw_data"]["boto3_config"]["Environment"]["Variables"]["K"] == MASK
    assert r["tags"] == {"Password": "tag-value-stays"}  # tags are left alone
    assert SECRET not in repr(r)
    assert SECRET in repr(lambda_like())  # the input was not changed


@pytest.mark.parametrize(
    "resource",
    [
        {"UserData": SECRET},
        {"raw_data": {"user_data": SECRET}},
        {"containerDefinitions": [{"environment": [{"name": "K", "value": SECRET}]}]},
        {
            "environment": {
                "environmentVariables": [
                    {"name": "K", "value": SECRET, "type": "PLAINTEXT"}
                ]
            }
        },
        {"Parameters": [{"ParameterKey": "P", "ParameterValue": SECRET}]},
        {"ConnectionProperties": {"PASSWORD": SECRET, "JDBC_CONNECTION_URL": SECRET}},
        {"ClientSecret": SECRET},
        {"MasterUserPassword": SECRET},
        {"environment_variables": {"A": SECRET}},
    ],
)
def test_deny_list_paths(resource):
    out, n = mask_resource(resource)
    assert n >= 1 and SECRET not in repr(out)


def test_masking_leaves_clean_data_alone():
    clean = {"service": "S3", "id": "b", "raw_data": {"Size": 3, "Public": False}}
    out, n = mask_resource(clean)
    assert n == 0 and out is clean
    assert count_masked([clean]) == 0
    assert mask_resources([clean, lambda_like()])[0] is clean
    again = mask_resources(mask_resources([lambda_like()]))
    assert SECRET not in repr(again)


def test_every_writer_masks_even_if_the_caller_did_not(tmp_path):
    rows = [lambda_like()]
    c = BOMConverter(enrich_vpc_info=False)
    c.generate_excel_bom(rows, str(tmp_path / "a.xlsx"))
    c.generate_word_bom(rows, str(tmp_path / "a.docx"))
    c.generate_csv_bom(rows, str(tmp_path / "a.csv"))
    registry = TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])
    template = registry.resolve("standard-bom")
    template.spec["excel"]["include_all_fields"] = True
    t = [dict(rows[0], resource_name="fn", resource_type="F")]
    render_excel(str(tmp_path / "t.xlsx"), t, template)
    render_word(str(tmp_path / "t.docx"), t, template)
    for name in os.listdir(tmp_path):
        path = tmp_path / name
        if name.endswith((".xlsx", ".docx")):
            with zipfile.ZipFile(path) as z:
                blob = b"".join(z.read(n) for n in z.namelist())
        else:
            blob = path.read_bytes()
        assert SECRET.encode() not in blob, name
    # and the names of the variables are still there
    with zipfile.ZipFile(tmp_path / "t.xlsx") as z:
        assert b"DB_PASSWORD" in b"".join(z.read(n) for n in z.namelist())
