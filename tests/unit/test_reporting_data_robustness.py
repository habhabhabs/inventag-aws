"""Layout-file loading, legacy converter input and Excel cell safety."""

import json

import pytest
from openpyxl import load_workbook

from inventag.reporting.converter import BOMConverter
from inventag.reporting.report_template import (
    MAX_TEMPLATE_BYTES,
    TemplateValidationError,
    default_template_text,
    load_report_template,
)


@pytest.fixture
def word_template_text():
    return default_template_text("word")


def test_default_word_template_loads(tmp_path, word_template_text):
    f = tmp_path / "t.yaml"
    f.write_text(word_template_text, encoding="utf-8")
    assert load_report_template(f, "word").format_type == "word"


def test_bom_in_front_of_yaml_is_accepted(tmp_path, word_template_text):
    f = tmp_path / "t.yaml"
    f.write_bytes(b"\xef\xbb\xbf" + word_template_text.encode("utf-8"))
    assert load_report_template(f, "word")


def test_duplicate_yaml_key_is_an_error_with_a_line(tmp_path, word_template_text):
    f = tmp_path / "t.yaml"
    f.write_text("name: first\n" + word_template_text + "\nname: second\n")
    with pytest.raises(TemplateValidationError, match="duplicate key 'name'") as e:
        load_report_template(f, "word")
    assert "line" in str(e.value) and "t.yaml" in str(e.value)


def test_duplicate_json_key_is_an_error(tmp_path):
    f = tmp_path / "t.json"
    f.write_text('{"name": "a", "name": "b"}')
    with pytest.raises(TemplateValidationError, match="duplicate key 'name'"):
        load_report_template(f, "excel")


def test_unknown_key_names_the_key_and_file(tmp_path, word_template_text):
    f = tmp_path / "t.yaml"
    f.write_text(word_template_text + "\nfooter_colour: red\n")
    with pytest.raises(TemplateValidationError, match="footer_colour") as e:
        load_report_template(f, "word")
    assert "t.yaml" in str(e.value)


def test_tabs_empty_and_huge_files(tmp_path):
    f = tmp_path / "t.yaml"
    f.write_text("a:\n\tb: 1\n")
    with pytest.raises(TemplateValidationError, match="YAML syntax error"):
        load_report_template(f)
    f.write_text("")
    with pytest.raises(TemplateValidationError):
        load_report_template(f)
    f.write_text("a: " + "x" * (MAX_TEMPLATE_BYTES + 10))
    with pytest.raises(TemplateValidationError, match="maximum"):
        load_report_template(f)


def test_load_data_reads_utf8_with_bom(tmp_path):
    f = tmp_path / "inv.json"
    rows = [{"service": "S3", "type": "Bucket", "id": "café", "name": "ü✓"}]
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps(rows, ensure_ascii=False).encode())
    c = BOMConverter(enrich_vpc_info=False)
    assert c.load_data(str(f))[0]["name"] == "ü✓"


def test_excel_survives_control_characters_and_odd_service_names(tmp_path):
    c = BOMConverter(enrich_vpc_info=False)
    c.data = [
        {"service": "S3", "type": "Bucket", "id": "a", "name": "x\x07y"},
        {"service": "Bad/Name[1]", "type": "T", "id": "b", "big": "z" * 40000},
        {"service": None, "type": "T", "id": "c"},
    ]
    out = tmp_path / "o.xlsx"
    c.export_to_excel(str(out))
    wb = load_workbook(out)
    assert "Bad-Name-1-" in wb.sheetnames
    assert wb["S3"]["D2"].value == "x\ufffdy" or "x\ufffdy" in [
        x.value for x in wb["S3"][2]
    ]
    big = [x.value for x in wb["Bad-Name-1-"][2] if x.value and len(x.value) > 100]
    assert len(big[0]) == 32767 and "cut" in big[0]
