"""Report templates: schema validation, substitution, file handling, defaults,
real Word/Excel output and the CLI flags. No AWS access."""

import copy
import importlib
import json
import os
import re
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from docx import Document
from openpyxl import load_workbook

from inventag.reporting import report_template as rt
from inventag.reporting.converter import BOMConverter
from inventag.reporting.report_template import (
    DEFAULT_EXCEL_TEMPLATE,
    DEFAULT_WORD_TEMPLATE,
    GLOBAL_VARIABLES,
    MAX_TEMPLATE_BYTES,
    MAX_TEXT_LENGTH,
    SERVICE_VARIABLES,
    TemplateValidationError,
    build_context,
    default_template,
    default_template_text,
    load_report_template,
    placeholder_errors,
    schema_reference,
    shipped_template_path,
    substitute,
    validate_template_data,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
cli_main = importlib.import_module("inventag.cli.main")

RESOURCES = [
    {
        "service": "EC2",
        "type": "Instance",
        "id": "i-1",
        "name": "web-1",
        "arn": "arn:aws:ec2:us-east-1:111111111111:instance/i-1",
        "region": "us-east-1",
        "account_id": "111111111111",
        "source_account_id": "111111111111",
        "tags": {"env": "prod", "Owner": "team-a"},
        "state": "running",
        "cost_center": "CC-42",
    },
    {
        "service": "EC2",
        "type": "Volume",
        "id": "vol-1",
        "name": "data",
        "region": "us-east-1",
        "account_id": "111111111111",
        "tags": {},
    },
    {
        "service": "S3",
        "type": "Bucket",
        "id": "bucket-a",
        "name": '=HYPERLINK("http://evil.example")',
        "region": "eu-west-1",
        "account_id": "222222222222",
        "source_account_id": "222222222222",
        "tags": {"env": "dev"},
    },
    {
        "service": "Lambda",
        "type": "Function",
        "id": "fn",
        "name": "{{ company_name }}",
        "region": "us-east-1",
    },
]


def word_data(**overrides):
    data = copy.deepcopy(DEFAULT_WORD_TEMPLATE)
    data.update(overrides)
    return data


def excel_data(**overrides):
    data = copy.deepcopy(DEFAULT_EXCEL_TEMPLATE)
    data.update(overrides)
    return data


def issues_of(data, expected_format=None):
    with pytest.raises(TemplateValidationError) as excinfo:
        validate_template_data(data, expected_format, source="tpl.yaml")
    return excinfo.value


def write_png(path, width=60, height=30):
    """Write a small valid PNG file with the standard library only."""
    import struct
    import zlib

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\x00" + b"\x1f\x4e\x78" * width for _ in range(height))
    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def write(tmp_path, name, content):
    path = tmp_path / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    elif isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    elif name.endswith(".json"):
        path.write_text(json.dumps(content), encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")
    return path


# ------------------------------------------------------------ default templates
class TestDefaultTemplates:
    @pytest.mark.parametrize("fmt", ["word", "excel"])
    def test_built_in_default_is_valid(self, fmt):
        template = default_template(fmt)
        assert template.format_type == fmt
        assert template.sections

    @pytest.mark.parametrize("fmt", ["word", "excel"])
    def test_shipped_file_loads_and_equals_built_in(self, fmt):
        path = shipped_template_path(fmt)
        assert path.is_file(), path
        shipped = load_report_template(path, fmt)
        assert shipped.data == default_template(fmt).data

    @pytest.mark.parametrize("fmt", ["word", "excel"])
    def test_docs_copy_equals_shipped_file(self, fmt):
        shipped = shipped_template_path(fmt)
        docs_copy = REPO_ROOT / "docs" / "assets" / "files" / shipped.name
        assert docs_copy.read_text() == shipped.read_text()

    @pytest.mark.parametrize("fmt", ["word", "excel"])
    def test_default_text_is_a_valid_template(self, fmt, tmp_path):
        suffix = ".yaml" if fmt == "word" else ".json"
        path = write(tmp_path, f"copy{suffix}", default_template_text(fmt))
        assert load_report_template(path, fmt).data == default_template(fmt).data

    def test_default_text_without_shipped_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rt, "shipped_template_path", lambda fmt: tmp_path / "none")
        for fmt, suffix in (("word", ".yaml"), ("excel", ".json")):
            path = write(tmp_path, f"gen{suffix}", default_template_text(fmt))
            assert load_report_template(path, fmt).data == default_template(fmt).data

    def test_default_word_structure_is_the_legacy_report(self):
        sections = default_template("word").sections
        assert [s["id"] for s in sections] == [
            "title",
            "generated_on",
            "executive_summary",
            "service_summary",
            "resource_inventory",
            "report_information",
        ]
        inventory = sections[4]
        assert inventory["columns"] == "auto"
        assert inventory["max_rows"] == 50 and inventory["max_columns"] == 6

    def test_legacy_loader_reads_shipped_files(self):
        from inventag.reporting.template_framework import TemplateLoader

        for fmt in ("word", "excel"):
            loaded = TemplateLoader().load_from_file(str(shipped_template_path(fmt)))
            assert loaded.format_type == fmt


# ------------------------------------------------------------ schema validation
class TestSchemaValidation:
    def test_minimal_word_template(self):
        template = validate_template_data(
            {
                "template_version": "2.0",
                "format_type": "word",
                "sections": [{"id": "title", "content_type": "title"}],
            }
        )
        assert template.data["document"]["title"] == ""
        assert template.data["header_footer"]["include_page_numbers"] is False

    def test_minimal_excel_template_fills_defaults(self):
        template = validate_template_data(
            {
                "template_version": "2.0",
                "format_type": "excel",
                "sections": [{"id": "s", "content_type": "service_summary"}],
            }
        )
        section = template.sections[0]
        assert section["sheet_name"] == "Summary"
        assert [c["field"] for c in section["columns"]] == [
            "service",
            "resource_count",
            "percentage",
        ]
        assert template.data["branding"]["header_color"] == "366092"

    def test_columns_accept_names_and_mappings(self):
        data = excel_data(
            extra_fields=["cost_center"],
            sections=[
                {
                    "id": "r",
                    "content_type": "resources",
                    "columns": [
                        "name",
                        {"field": "tags.Owner", "heading": "Owner", "width": 20},
                        "cost_center",
                        "raw_data.InstanceId",
                    ],
                }
            ],
        )
        columns = validate_template_data(data).sections[0]["columns"]
        assert columns[0] == {"field": "name", "heading": None, "width": None}
        assert columns[1] == {"field": "tags.Owner", "heading": "Owner", "width": 20.0}
        assert [c["field"] for c in columns][2:] == [
            "cost_center",
            "raw_data.InstanceId",
        ]

    def test_disabled_section_is_not_rendered(self):
        data = word_data()
        data["sections"][1]["enabled"] = False
        ids = [s["id"] for s in validate_template_data(data).sections]
        assert "generated_on" not in ids and len(ids) == 5

    @pytest.mark.parametrize(
        "mutate, key_path, reason",
        [
            (lambda d: d.update(colour="red"), "colour", "unknown key"),
            (lambda d: d.update(sections="all"), "sections", "must be a list"),
            (lambda d: d.update(sections=[]), "sections", "empty"),
            (lambda d: d.pop("sections"), "sections", "missing key"),
            (lambda d: d.pop("template_version"), "template_version", "missing key"),
            (
                lambda d: d.update(template_version="1.0"),
                "template_version",
                "unsupported version '1.0'",
            ),
            (lambda d: d.update(format_type="pdf"), "format_type", "'word' or 'excel'"),
            (lambda d: d.update(document=[1]), "document", "must be a mapping"),
            (
                lambda d: d["document"].update(title=5),
                "document.title",
                "must be a string, but the value is integer",
            ),
            (
                lambda d: d["document"].update(author="x"),
                "document.author",
                "unknown key",
            ),
            (
                lambda d: d["branding"].update(header_color="366092"),
                "branding.header_color",
                "not valid in a Word template",
            ),
            (
                lambda d: d["header_footer"].update(include_page_numbers="yes"),
                "header_footer.include_page_numbers",
                "must be true or false",
            ),
            (
                lambda d: d["sections"][0].update(content_type="cover_page"),
                "sections[0].content_type",
                "unknown section type 'cover_page'",
            ),
            (
                lambda d: d["sections"][0].update(content_type="network_analysis"),
                "sections[0].content_type",
                "unknown section type 'network_analysis' for a Word template",
            ),
            (
                lambda d: d["sections"][1].update(id="title"),
                "sections[1].id",
                "duplicate id 'title'",
            ),
            (lambda d: d["sections"][1].pop("id"), "sections[1].id", "missing key"),
            (
                lambda d: d["sections"][1].update(id="Bad Id"),
                "sections[1].id",
                "lowercase",
            ),
            (
                lambda d: d["sections"][0].update(paragraphs=["x"]),
                "sections[0].paragraphs",
                "not valid in a 'title' section",
            ),
            (
                lambda d: d["sections"][2].update(level=9),
                "sections[2].level",
                "must be 1, 2 or 3",
            ),
            (
                lambda d: d["sections"][2].update(paragraphs=["ok", 3]),
                "sections[2].paragraphs[1]",
                "must be a string",
            ),
            (
                lambda d: d["sections"][3].update(table_style="Fancy Style"),
                "sections[3].table_style",
                "unknown table style",
            ),
            (
                lambda d: d["sections"][3].update(columns=[{"field": "cost"}]),
                "sections[3].columns[0].field",
                "unknown column 'cost'",
            ),
            (
                lambda d: d["sections"][4].update(columns=["name", "favourite_colour"]),
                "sections[4].columns[1].field",
                "unknown column 'favourite_colour'",
            ),
            (
                lambda d: d["sections"][4].update(columns=["name", "name"]),
                "sections[4].columns[1].field",
                "duplicate column",
            ),
            (
                lambda d: d["sections"][4].update(
                    columns=[{"field": "name", "width": 99}]
                ),
                "sections[4].columns[0].width",
                "0.2 to 10 inches",
            ),
            (
                lambda d: d["sections"][4].update(
                    columns=[{"field": "name", "colour": "red"}]
                ),
                "sections[4].columns[0].colour",
                "unknown key",
            ),
            (
                lambda d: d["sections"][4].update(columns={"name": "Name"}),
                "sections[4].columns",
                "'auto' or a list",
            ),
            (
                lambda d: d["sections"][4].update(max_rows=0),
                "sections[4].max_rows",
                "from 1 to",
            ),
            (
                lambda d: d["sections"][4].update(services=[]),
                "sections[4].services",
                "empty",
            ),
            (
                lambda d: d["sections"][4].update(sheet_name="All"),
                "sections[4].sheet_name",
                "not valid in a 'resources' section of a Word template",
            ),
            (
                lambda d: d.update(variables={"total_resources": "9"}),
                "variables.total_resources",
                "built-in variable",
            ),
            (
                lambda d: d.update(variables={"Bad-Name": "x"}),
                "variables.Bad-Name",
                "lowercase",
            ),
            (
                lambda d: d.update(variables={"a": "{{ b }}"}),
                "variables.a",
                "must not contain {{",
            ),
            (
                lambda d: d.update(variables={"a": ["x"]}),
                "variables.a",
                "must be a string or a number",
            ),
            (
                lambda d: d.update(extra_fields="cost_center"),
                "extra_fields",
                "must be a list",
            ),
        ],
    )
    def test_bad_word_templates(self, mutate, key_path, reason):
        data = word_data()
        mutate(data)
        error = issues_of(data, "word")
        matching = [i for i in error.issues if i.key_path == key_path]
        assert matching, [str(i) for i in error.issues]
        assert any(reason in i.reason for i in matching), [str(i) for i in matching]
        assert all(m.startswith("tpl.yaml: ") for m in error.messages())

    @pytest.mark.parametrize(
        "mutate, key_path, reason",
        [
            (
                lambda d: d["branding"].update(header_color="blue"),
                "branding.header_color",
                "six hexadecimal digits",
            ),
            (
                lambda d: d["branding"].update(logo_path="logo.png"),
                "branding.logo_path",
                "not valid in an Excel template",
            ),
            (
                lambda d: d["header_footer"].update(include_page_numbers=True),
                "header_footer.include_page_numbers",
                "not valid in an Excel template",
            ),
            (
                lambda d: d["sections"][0].update(content_type="title"),
                "sections[0].content_type",
                "unknown section type 'title' for an Excel template",
            ),
            (
                lambda d: d["sections"][0].update(sheet_name="a/b"),
                "sections[0].sheet_name",
                "must not contain",
            ),
            (
                lambda d: d["sections"][0].update(sheet_name="x" * 32),
                "sections[0].sheet_name",
                "1 to 31 characters",
            ),
            (
                lambda d: d["sections"][1].update(sheet_name="All"),
                "sections[1].sheet_name",
                "only valid with group_by_service: false",
            ),
            (
                lambda d: d["sections"][1].update(group_by_service=False),
                "sections[1].sheet_name",
                "must have a sheet_name",
            ),
            (
                lambda d: d["sections"][1].update(
                    group_by_service=False, sheet_name="summary"
                ),
                "sections[1].sheet_name",
                "duplicate sheet name",
            ),
            (
                lambda d: d["sections"][1].update(max_rows=5),
                "sections[1].max_rows",
                "not valid in a 'resources' section of an Excel template",
            ),
            (
                lambda d: d["sections"][1].update(
                    columns=[{"field": "name", "width": 0}]
                ),
                "sections[1].columns[0].width",
                "1 to 255 characters",
            ),
            (
                lambda d: [s.update(enabled=False) for s in d["sections"]],
                "sections",
                "all sections are disabled",
            ),
        ],
    )
    def test_bad_excel_templates(self, mutate, key_path, reason):
        data = excel_data()
        mutate(data)
        error = issues_of(data, "excel")
        matching = [i for i in error.issues if i.key_path == key_path]
        assert matching, [str(i) for i in error.issues]
        assert any(reason in i.reason for i in matching), [str(i) for i in matching]

    def test_format_mismatch(self):
        error = issues_of(excel_data(), "word")
        assert "template for Excel reports" in str(error)
        assert "needs a template for Word reports" in str(error)

    @pytest.mark.parametrize("raw", [None, [], "text", 3])
    def test_template_must_be_a_mapping(self, raw):
        assert "the template must be a mapping" in str(issues_of(raw, "word"))

    def test_every_problem_is_reported(self):
        data = word_data(colour="red")
        data["document"]["title"] = "{{ nope }}"
        data["sections"][4]["columns"] = ["favourite_colour"]
        error = issues_of(data, "word")
        assert {i.key_path for i in error.issues} >= {
            "colour",
            "document.title",
            "sections[4].columns[0].field",
        }

    def test_schema_tables_are_consistent(self):
        reference = schema_reference()
        assert set(reference) == {
            "top level",
            "document",
            "branding",
            "header_footer",
            "sections",
            "columns",
        }
        for keys in reference.values():
            names = [k.name for k in keys]
            assert len(names) == len(set(names))
            for key in keys:
                assert key.description and set(key.formats) <= {"word", "excel"}
        # Every key of the default templates is in the schema.
        top = {k.name for k in rt.TOP_LEVEL_KEYS}
        section_keys = {k.name for k in rt.SECTION_KEYS}
        for data in (DEFAULT_WORD_TEMPLATE, DEFAULT_EXCEL_TEMPLATE):
            assert set(data) <= top
            for section in data["sections"]:
                assert set(section) <= section_keys


# ------------------------------------------------------------------ variables
class TestVariables:
    def test_unknown_variable_in_each_text_key(self):
        cases = {
            "document.title": lambda d: d["document"].update(title="{{ nope }}"),
            "document.subtitle": lambda d: d["document"].update(subtitle="{{ nope }}"),
            "header_footer.header_text": lambda d: d["header_footer"].update(
                header_text="{{ nope }}"
            ),
            "header_footer.footer_text": lambda d: d["header_footer"].update(
                footer_text="{{ nope }}"
            ),
            "sections[2].title": lambda d: d["sections"][2].update(title="{{ nope }}"),
            "sections[2].paragraphs[0]": lambda d: d["sections"][2].update(
                paragraphs=["{{ nope }}"]
            ),
            "sections[4].service_title": lambda d: d["sections"][4].update(
                service_title="{{ nope }}"
            ),
            "sections[4].truncation_note": lambda d: d["sections"][4].update(
                truncation_note="{{ nope }}"
            ),
        }
        for key_path, mutate in cases.items():
            data = word_data()
            mutate(data)
            error = issues_of(data, "word")
            assert [i.key_path for i in error.issues] == [key_path]
            assert "unknown variable 'nope'" in error.issues[0].reason
            assert "total_resources" in error.issues[0].reason  # lists allowed names

    def test_service_variables_only_in_service_texts(self):
        data = word_data()
        data["sections"][2]["paragraphs"] = ["{{ service }}"]
        assert "unknown variable 'service'" in str(issues_of(data, "word"))
        data = word_data()
        data["sections"][4]["service_title"] = "{{ service }} / {{ company_name }}"
        validate_template_data(data, "word")

    def test_title_cannot_refer_to_itself(self):
        data = word_data()
        data["document"]["title"] = "{{ document_title }}"
        assert "unknown variable 'document_title'" in str(issues_of(data, "word"))

    def test_user_variables(self):
        data = word_data(variables={"classification": "Internal", "revision": 3})
        data["header_footer"]["header_text"] = "{{ classification }} r{{ revision }}"
        template = validate_template_data(data, "word")
        context = build_context(template, RESOURCES)
        assert substitute(template.data["header_footer"]["header_text"], context) == (
            "Internal r3"
        )

    def test_context_values(self):
        data = word_data()
        data["branding"]["company_name"] = "Example Corp"
        data["document"] = {
            "title": "{{ company_name }} BOM",
            "subtitle": "{{ account_count }} accounts: {{ account_ids }}",
        }
        from datetime import datetime, timezone

        now = datetime(2026, 11, 12, 8, 9, 10, tzinfo=timezone.utc)
        context = build_context(validate_template_data(data, "word"), RESOURCES, now)
        assert context["document_title"] == "Example Corp BOM"
        assert context["document_subtitle"] == (
            "2 accounts: 111111111111, 222222222222"
        )
        assert context["generated_at"] == "2026-11-12 08:09:10"
        assert context["generated_date"] == "2026-11-12"
        assert context["total_resources"] == "4"
        assert context["service_count"] == "3"
        assert context["region_count"] == "2"
        assert set(GLOBAL_VARIABLES) <= set(context)

    def test_substitute_basic(self):
        values = {"a": "1", "b_2": "two"}
        assert substitute("{{a}}-{{ b_2 }}-{{   a   }}", values) == "1-two-1"
        assert substitute("no placeholders", values) == "no placeholders"
        assert substitute("", values) == ""

    @pytest.mark.parametrize(
        "text",
        [
            "{{ __class__ }}",
            "{{ __class__.__mro__ }}",
            "{{ ''.__class__ }}",
            "{{ company_name.__class__ }}",
            "{{ config['SECRET'] }}",
            "{{ 7*7 }}",
            "{{ company_name | upper }}",
            "{{ company_name|date:%Y }}",
            "{% include '/etc/passwd' %} {{ x }}",
            "{{ self }}",
            "{{ os.environ }}",
            "{{{{ company_name }}}}",
            "{{ {{ company_name }} }}",
            "{{ company_name",
            "company_name }}",
            "{{}}",
            "{{ company name }}",
            "${{ secrets.TOKEN }}",
        ],
    )
    def test_hostile_placeholders_are_rejected(self, text):
        assert placeholder_errors(text, GLOBAL_VARIABLES), text
        data = word_data()
        data["sections"][2]["paragraphs"] = [text]
        error = issues_of(data, "word")
        assert error.issues[0].key_path == "sections[2].paragraphs[0]"

    def test_literal_text_without_braces_is_allowed(self):
        text = "{% include '/etc/passwd' %} $(rm -rf /) `id` ${HOME} <script>"
        assert placeholder_errors(text, GLOBAL_VARIABLES) == []
        assert substitute(text, {}) == text

    def test_value_is_not_expanded_again(self):
        values = {"a": "{{ b }}", "b": "SECRET"}
        assert substitute("{{ a }}", values) == "{{ b }}"

    def test_unknown_name_at_render_time_raises(self):
        with pytest.raises(KeyError):
            substitute("{{ __class__ }}", {"a": "1"})

    def test_substitute_does_no_attribute_access(self):
        class Explosive:
            def __getattr__(self, name):
                raise AssertionError("attribute access")

            def __str__(self):
                return "safe"

        assert substitute("{{ a }}", {"a": Explosive()}) == "safe"

    def test_very_long_text_is_rejected_fast(self):
        data = word_data()
        data["sections"][2]["paragraphs"] = ["{{ " + " " * 2_000_000]
        start = time.monotonic()
        error = issues_of(data, "word")
        assert time.monotonic() - start < 5
        assert f"The maximum is {MAX_TEXT_LENGTH}" in str(error)

    def test_text_at_the_limit_is_accepted(self):
        data = word_data()
        data["sections"][2]["paragraphs"] = ["x" * MAX_TEXT_LENGTH]
        validate_template_data(data, "word")

    def test_long_user_variable_value_is_rejected(self):
        data = word_data(variables={"a": "x" * (MAX_TEXT_LENGTH + 1)})
        assert "variables.a" in str(issues_of(data, "word"))

    def test_company_name_cannot_contain_placeholders(self):
        data = word_data()
        data["branding"]["company_name"] = "{{ total_resources }}"
        assert "branding.company_name" in str(issues_of(data, "word"))

    def test_service_variable_names_are_reserved(self):
        for name in SERVICE_VARIABLES:
            data = word_data(variables={name: "x"})
            assert f"variables.{name}" in str(issues_of(data, "word"))


# --------------------------------------------------------------- file handling
class TestFileHandling:
    def test_yaml_and_json_are_accepted(self, tmp_path):
        for name in ("t.yaml", "t.yml", "t.json"):
            path = write(tmp_path, name, word_data())
            assert load_report_template(path, "word").format_type == "word"

    def test_error_has_file_path_key_path_and_reason(self, tmp_path):
        data = word_data()
        data["sections"][4]["columns"] = ["favourite_colour"]
        path = write(tmp_path, "bad.yaml", data)
        with pytest.raises(TemplateValidationError) as excinfo:
            load_report_template(path, "word")
        (message,) = excinfo.value.messages()
        assert message.startswith(
            f"{path}: sections[4].columns[0].field: unknown column 'favourite_colour'"
        )

    @pytest.mark.parametrize("name", ["t.txt", "t.py", "t", "t.yaml.exe", "t.docx"])
    def test_wrong_suffix(self, tmp_path, name):
        path = write(tmp_path, name, word_data())
        with pytest.raises(TemplateValidationError, match="unsupported file type"):
            load_report_template(path, "word")

    def test_missing_file_and_directory(self, tmp_path):
        with pytest.raises(TemplateValidationError, match="file not found"):
            load_report_template(tmp_path / "none.yaml", "word")
        (tmp_path / "dir.yaml").mkdir()
        with pytest.raises(TemplateValidationError, match="not a regular file"):
            load_report_template(tmp_path / "dir.yaml", "word")

    def test_size_limit(self, tmp_path):
        path = write(tmp_path, "big.yaml", "# " + "x" * MAX_TEMPLATE_BYTES + "\n")
        with pytest.raises(
            TemplateValidationError, match="The maximum is 262144 bytes"
        ):
            load_report_template(path, "word")

    def test_yaml_python_tags_are_not_executed(self, tmp_path):
        marker = tmp_path / "pwned"
        path = write(
            tmp_path,
            "evil.yaml",
            f"name: !!python/object/apply:os.system ['touch {marker}']\n",
        )
        with pytest.raises(TemplateValidationError, match="YAML syntax error"):
            load_report_template(path, "word")
        assert not marker.exists()

    def test_syntax_errors(self, tmp_path):
        path = write(tmp_path, "bad.json", '{"template_version": "2.0",')
        with pytest.raises(
            TemplateValidationError, match="JSON syntax error at line 1"
        ):
            load_report_template(path, "word")
        path = write(tmp_path, "bad.yaml", "sections: [unclosed\n")
        with pytest.raises(TemplateValidationError, match="YAML syntax error at line"):
            load_report_template(path, "word")

    def test_not_utf8(self, tmp_path):
        path = write(tmp_path, "latin.yaml", b"name: \xff\xfe\n")
        with pytest.raises(TemplateValidationError, match="not UTF-8"):
            load_report_template(path, "word")

    def test_deeply_nested_yaml_gives_an_error_not_a_crash(self, tmp_path):
        path = write(tmp_path, "deep.json", "[" * 50000 + "]" * 50000)
        with pytest.raises(TemplateValidationError):
            load_report_template(path, "word")

    def test_yaml_alias_expansion_is_bounded_by_validation(self, tmp_path):
        text = "a: &a [x, x, x, x, x, x, x, x, x]\n"
        for prev, name in zip("abcdefg", "bcdefgh"):
            text += f"{name}: &{name} [*{prev}, *{prev}, *{prev}, *{prev}, *{prev}, *{prev}, *{prev}, *{prev}, *{prev}]\n"
        text += 'template_version: "2.0"\nformat_type: word\nsections: *h\n'
        path = write(tmp_path, "bomb.yaml", text)
        start = time.monotonic()
        with pytest.raises(TemplateValidationError):
            load_report_template(path, "word")
        assert time.monotonic() - start < 5

    def _logo_template(self, tmp_path, logo_path):
        data = word_data()
        data["branding"]["logo_path"] = logo_path
        return write(tmp_path, "tpl.yaml", data)

    def test_logo_inside_template_directory(self, tmp_path):
        (tmp_path / "img").mkdir()
        write_png(tmp_path / "img" / "logo.png")
        template = load_report_template(
            self._logo_template(tmp_path, "img/logo.png"), "word"
        )
        assert template.logo_file == (tmp_path / "img" / "logo.png").resolve()

    @pytest.mark.parametrize(
        "logo_path, reason",
        [
            ("../secret.png", "must stay in the directory"),
            ("img/../../secret.png", "must stay in the directory"),
            ("/etc/passwd", "relative path"),
            ("C:\\Windows\\logo.png", "relative path"),
            ("notes.txt", ".png, .jpg or .jpeg"),
            ("missing.png", "file not found"),
            ("", "1 to 255 characters"),
        ],
    )
    def test_logo_path_rules(self, tmp_path, logo_path, reason):
        work = tmp_path / "work"
        work.mkdir()
        (tmp_path / "secret.png").write_bytes(b"x")
        (work / "notes.txt").write_text("x")
        with pytest.raises(TemplateValidationError) as excinfo:
            load_report_template(self._logo_template(work, logo_path), "word")
        assert "branding.logo_path" in str(excinfo.value)
        assert reason in str(excinfo.value)

    def test_logo_symlink_out_of_directory_is_refused(self, tmp_path):
        work = tmp_path / "work"
        work.mkdir()
        (tmp_path / "outside.png").write_bytes(b"x")
        try:
            os.symlink(tmp_path / "outside.png", work / "logo.png")
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not available")
        with pytest.raises(TemplateValidationError, match="must stay in the directory"):
            load_report_template(self._logo_template(work, "logo.png"), "word")

    def test_logo_not_allowed_without_a_file(self):
        data = word_data()
        data["branding"]["logo_path"] = "logo.png"
        assert "only possible in a template file" in str(issues_of(data, "word"))

    def test_legacy_loader_has_the_same_size_limit(self, tmp_path):
        from inventag.reporting.template_framework import TemplateLoader

        path = write(tmp_path, "big.yaml", "# " + "x" * MAX_TEMPLATE_BYTES + "\n")
        with pytest.raises(ValueError, match="larger than"):
            TemplateLoader().load_from_file(str(path))


# ------------------------------------------------------------- real documents
def body_items(doc):
    """Paragraphs and tables of a document, in order."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    items = []
    for element in doc.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(element, doc)
            items.append(("p", paragraph.style.name, paragraph.text))
        elif tag == "tbl":
            table = Table(element, doc)
            items.append(
                (
                    "tbl",
                    table.style.name,
                    [[c.text for c in r.cells] for r in table.rows],
                )
            )
    return items


def headings(doc):
    return [
        (style, text)
        for kind, style, text in body_items(doc)
        if kind == "p" and style.startswith(("Title", "Heading", "Subtitle"))
    ]


CUSTOM_WORD = """
template_version: "2.0"
format_type: word
document:
  title: "{{ company_name }} Cloud Inventory"
  subtitle: "Accounts: {{ account_ids }}"
branding:
  company_name: Example Corp
variables:
  classification: Internal
extra_fields: [cost_center]
header_footer:
  header_text: "{{ company_name }} - {{ classification }}"
  footer_text: "{{ total_resources }} resources"
  include_page_numbers: true
sections:
  - id: title
    content_type: title
  - id: inventory
    content_type: resources
    title: Resources of {{ account_count }} accounts
    level: 1
    services: [Amazon S3, ec2]
    service_title: "{{ service }}: {{ shown_resource_count }} of {{ service_resource_count }}"
    max_rows: 1
    truncation_note: "{{ service }} list is not complete."
    page_break_after_service: false
    table_style: Table Grid
    columns:
      - field: name
        heading: Resource name
        width: 2.5
      - region
      - field: tags.env
        heading: Environment
      - field: cost_center
        heading: Cost center
  - id: summary
    content_type: service_summary
    title: Summary
    level: 1
    columns:
      - field: resource_count
        heading: Count
      - field: service
        heading: AWS service
  - id: notice
    content_type: text
    paragraphs:
      - "Classification: {{ classification }}. Generated {{ generated_date }}."
"""

CUSTOM_EXCEL = {
    "template_version": "2.0",
    "format_type": "excel",
    "document": {
        "title": "{{ company_name }} inventory",
        "subtitle": "{{ total_resources }} resources in {{ account_count }} accounts",
    },
    "branding": {"company_name": "Example Corp", "header_color": "#1f4e78"},
    "extra_fields": ["cost_center"],
    "header_footer": {
        "header_text": "{{ document_title }}",
        "footer_text": "R&D {{ classification }}",
    },
    "variables": {"classification": "Internal"},
    "sections": [
        {
            "id": "all",
            "content_type": "resources",
            "group_by_service": False,
            "sheet_name": "All resources",
            "columns": [
                {"field": "service", "heading": "Service", "width": 14},
                {"field": "name", "heading": "Name"},
                "region",
                {"field": "tags", "heading": "Tags"},
                {"field": "tags.env", "heading": "Environment"},
                {"field": "cost_center", "heading": "Cost center"},
            ],
        },
        {
            "id": "overview",
            "content_type": "service_summary",
            "sheet_name": "Overview",
            "show_title": True,
            "columns": [
                {"field": "service", "heading": "AWS service"},
                {"field": "resource_count", "heading": "Count", "width": 9},
            ],
        },
        {"id": "s3_only", "content_type": "resources", "services": ["Amazon S3"]},
        {"id": "net", "content_type": "network_analysis"},
        {"id": "hidden", "content_type": "security_analysis", "enabled": False},
    ],
}


class TestWordOutput:
    def test_default_template_gives_the_legacy_report(self, tmp_path):
        out = tmp_path / "default.docx"
        BOMConverter(enrich_vpc_info=False).generate_word_bom(
            copy.deepcopy(RESOURCES), str(out)
        )
        doc = Document(str(out))
        items = body_items(doc)
        assert items[0] == ("p", "Title", "AWS Resource Inventory - BOM Report")
        assert re.fullmatch(
            r"Generated on: \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC", items[1][2]
        )
        assert headings(doc) == [
            ("Title", "AWS Resource Inventory - BOM Report"),
            ("Heading 1", "Executive Summary"),
            ("Heading 2", "Service Summary"),
            ("Heading 1", "Detailed Resource Inventory"),
            ("Heading 2", "EC2 Resources (2)"),
            ("Heading 2", "Lambda Resources (1)"),
            ("Heading 2", "S3 Resources (1)"),
            ("Heading 1", "Report Information"),
        ]
        texts = [text for kind, _, text in items if kind == "p"]
        assert "Total Resources: 4" in texts
        assert "Services Covered: 3" in texts
        assert "AWS Regions: 2" in texts
        tables = [item for item in items if item[0] == "tbl"]
        assert tables[0][1] == "Light Grid Accent 1"
        assert tables[0][2][0] == ["Service", "Resource Count", "Percentage"]
        assert tables[0][2][1] == ["EC2", "2", "50.0%"]
        assert tables[1][1] == "Light List Accent 1"
        assert tables[1][2][0] == ["Name", "Id", "Type", "Region", "Tags", "Service"]
        assert doc.sections[0].header.paragraphs[0].text == ""
        assert doc.sections[0].footer.paragraphs[0].text == ""
        assert (os.stat(out).st_mode & 0o777) == 0o600

    def test_custom_template(self, tmp_path):
        template = load_report_template(
            write(tmp_path, "word.yaml", CUSTOM_WORD), "word"
        )
        out = tmp_path / "custom.docx"
        BOMConverter(enrich_vpc_info=False).generate_word_bom(
            copy.deepcopy(RESOURCES), str(out), template=template
        )
        doc = Document(str(out))

        # Title, subtitle and section order
        assert headings(doc) == [
            ("Title", "Example Corp Cloud Inventory"),
            ("Subtitle", "Accounts: 111111111111, 222222222222"),
            ("Heading 1", "Resources of 2 accounts"),
            ("Heading 2", "S3: 1 of 1"),
            ("Heading 2", "EC2: 1 of 2"),
            ("Heading 1", "Summary"),
        ]
        items = body_items(doc)
        tables = [item for item in items if item[0] == "tbl"]

        # Column headings, order and values; the services filter and its order
        assert tables[0][1] == "Table Grid"
        assert tables[0][2] == [
            ["Resource name", "Region", "Environment", "Cost center"],
            ['=HYPERLINK("http://evil.example")', "eu-west-1", "dev", ""],
        ]
        assert tables[1][2] == [
            ["Resource name", "Region", "Environment", "Cost center"],
            ["web-1", "us-east-1", "prod", "CC-42"],
        ]
        assert tables[2][2][0] == ["Count", "AWS service"]
        assert ["2", "EC2"] in tables[2][2]
        assert len(tables) == 3

        # max_rows and the truncation note
        texts = [text for kind, _, text in items if kind == "p"]
        assert "EC2 list is not complete." in texts
        assert "S3 list is not complete." not in texts
        assert any(
            re.fullmatch(r"Classification: Internal\. Generated \d{4}-\d\d-\d\d\.", t)
            for t in texts
        )
        # Sections that the template does not list are absent
        assert "Executive Summary" not in texts and "Report Information" not in texts

        # Header, footer and page number field
        section = doc.sections[0]
        assert section.header.paragraphs[0].text == "Example Corp - Internal"
        footer = section.footer.paragraphs[0]
        assert footer.text == "4 resources  Page "
        assert 'w:instr="PAGE"' in footer._p.xml

        # Column width from the template (2.5 inches)
        first_table = doc.tables[0]
        assert abs(first_table.columns[0].cells[0].width.inches - 2.5) < 0.01

    def test_resource_data_is_never_substituted(self, tmp_path):
        data = word_data()
        data["branding"]["company_name"] = "SECRET-COMPANY"
        template = validate_template_data(data, "word")
        out = tmp_path / "data.docx"
        BOMConverter(enrich_vpc_info=False).generate_word_bom(
            copy.deepcopy(RESOURCES), str(out), template=template
        )
        doc = Document(str(out))
        cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
        assert "{{ company_name }}" in cells
        assert "SECRET-COMPANY" not in cells

    def test_logo_is_embedded(self, tmp_path):
        write_png(tmp_path / "logo.png")
        data = word_data()
        data["branding"].update(logo_path="logo.png", logo_width_inches=2)
        template = load_report_template(write(tmp_path, "t.yaml", data), "word")
        out = tmp_path / "logo.docx"
        BOMConverter(enrich_vpc_info=False).generate_word_bom(
            copy.deepcopy(RESOURCES), str(out), template=template
        )
        doc = Document(str(out))
        assert len(doc.inline_shapes) == 1
        assert abs(doc.inline_shapes[0].width.inches - 2) < 0.01

    def test_wrong_format_template_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="format_type"):
            BOMConverter(enrich_vpc_info=False).generate_word_bom(
                copy.deepcopy(RESOURCES),
                str(tmp_path / "x.docx"),
                template=default_template("excel"),
            )


class TestExcelOutput:
    def test_default_template_gives_the_legacy_workbook(self, tmp_path):
        out = tmp_path / "default.xlsx"
        BOMConverter(enrich_vpc_info=False).generate_excel_bom(
            copy.deepcopy(RESOURCES), str(out)
        )
        wb = load_workbook(str(out))
        assert wb.sheetnames == ["Summary", "EC2", "S3", "Lambda"]
        summary = [[c.value for c in row] for row in wb["Summary"].iter_rows()]
        assert summary == [
            ["Service", "Resource Count", "Percentage"],
            ["EC2", 2, "50.0%"],
            ["Lambda", 1, "25.0%"],
            ["S3", 1, "25.0%"],
            ["TOTAL", 4, "100.0%"],
        ]
        ec2_header = [c.value for c in wb["EC2"][1]]
        assert ec2_header == [
            "service",
            "type",
            "id",
            "name",
            "arn",
            "account_id",
            "source_account_id",
            "region",
            "state",
            "cost_center",
            "tags.Owner",
            "tags.env",
        ]
        assert wb["EC2"]["A1"].fill.start_color.rgb == "00366092"
        assert wb.properties.title is None
        assert wb["Summary"].oddHeader.center.text is None
        assert (os.stat(out).st_mode & 0o777) == 0o600

    def test_custom_template(self, tmp_path):
        template = load_report_template(
            write(tmp_path, "excel.json", CUSTOM_EXCEL), "excel"
        )
        out = tmp_path / "custom.xlsx"
        BOMConverter(enrich_vpc_info=False).generate_excel_bom(
            copy.deepcopy(RESOURCES), str(out), template=template
        )
        wb = load_workbook(str(out))

        # Sheet order follows the template; disabled and data-less sheets are absent
        assert wb.sheetnames == ["All resources", "Overview", "S3"]

        # Column headings, order and width
        ws = wb["All resources"]
        rows = [[c.value for c in row] for row in ws.iter_rows()]
        assert rows[0] == [
            "Service",
            "Name",
            "region",
            "Tags",
            "Environment",
            "Cost center",
        ]
        assert rows[1] == [
            "EC2",
            "web-1",
            "us-east-1",
            "env=prod, Owner=team-a",
            "prod",
            "CC-42",
        ]
        assert len(rows) == 1 + len(RESOURCES)
        assert ws.column_dimensions["A"].width == 14
        assert ws["A1"].fill.start_color.rgb == "001F4E78"

        # A formula from discovered data stays text
        s3_row = next(row for row in ws.iter_rows() if row[0].value == "S3")
        assert s3_row[1].value == '=HYPERLINK("http://evil.example")'
        assert s3_row[1].data_type == "s"

        # Title block, then the summary table with the template headings
        overview = [[c.value for c in row] for row in wb["Overview"].iter_rows()]
        assert overview[0][0] == "Example Corp inventory"
        assert overview[1][0] == "4 resources in 2 accounts"
        assert overview[3] == ["AWS service", "Count"]
        assert overview[-1] == ["TOTAL", 4]
        assert wb["Overview"].column_dimensions["B"].width == 9

        # The services filter matches "Amazon S3" to the S3 service
        assert [c.value for c in wb["S3"][1]][:3] == ["service", "type", "id"]

        # Workbook properties and the print header/footer of each sheet
        assert wb.properties.title == "Example Corp inventory"
        assert wb.properties.subject == "4 resources in 2 accounts"
        assert wb.properties.creator == "Example Corp"
        for sheet in wb.worksheets:
            assert sheet.oddHeader.center.text == "Example Corp inventory"
            assert sheet.oddFooter.center.text == "R&&D Internal"

    def test_services_filter_with_no_match_gives_a_clear_error(self, tmp_path):
        data = excel_data(
            sections=[{"id": "r", "content_type": "resources", "services": ["RDS"]}]
        )
        with pytest.raises(ValueError, match="workbook with no sheets"):
            BOMConverter(enrich_vpc_info=False).generate_excel_bom(
                copy.deepcopy(RESOURCES),
                str(tmp_path / "x.xlsx"),
                template=validate_template_data(data, "excel"),
            )


# ------------------------------------------------------------------------ CLI
def run_cli(*args):
    old_argv = sys.argv
    sys.argv = ["inventag", *args]
    try:
        cli_main.main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old_argv


@pytest.fixture
def no_aws(monkeypatch):
    """Fail the test if the CLI gets as far as AWS setup."""

    def forbidden(*args, **kwargs):
        raise AssertionError("the CLI went past template validation")

    monkeypatch.setattr(cli_main.safety, "harden_process", forbidden)
    monkeypatch.setattr(cli_main.safety, "enable_read_only_guard", forbidden)
    monkeypatch.setattr(cli_main.boto3, "Session", forbidden)


class TestCli:
    def test_invalid_template_stops_before_any_aws_call(self, tmp_path, capsys, no_aws):
        data = word_data(colour="red")
        data["sections"][4]["columns"] = ["favourite_colour"]
        path = write(tmp_path, "bad.yaml", data)
        code = run_cli("--create-word", "--word-template", str(path))
        assert code == 1
        err = capsys.readouterr().err.splitlines()
        assert f"inventag: error: {path}: colour: unknown key. Allowed keys: " in err[0]
        assert (
            f"inventag: error: {path}: sections[4].columns[0].field: "
            "unknown column 'favourite_colour'" in err[1]
        )

    def test_errors_of_both_files_are_reported(self, tmp_path, capsys, no_aws):
        word = write(tmp_path, "w.yaml", excel_data())
        excel = write(tmp_path, "e.txt", "x")
        code = run_cli(
            "--create-word",
            "--create-excel",
            "--word-template",
            str(word),
            "--excel-template",
            str(excel),
        )
        assert code == 1
        err = capsys.readouterr().err
        assert f"{word}: format_type:" in err
        assert f"{excel}: unsupported file type" in err

    def test_validate_templates(self, tmp_path, capsys, no_aws):
        word = write(tmp_path, "w.yaml", CUSTOM_WORD)
        excel = write(tmp_path, "e.json", CUSTOM_EXCEL)
        code = run_cli(
            "--validate-templates",
            "--word-template",
            str(word),
            "--excel-template",
            str(excel),
        )
        assert code == 0
        out = capsys.readouterr().out.splitlines()
        assert out == [
            f"OK  {word} (word template, 4 sections)",
            f"OK  {excel} (excel template, 4 sections)",
        ]

    def test_validate_templates_needs_a_file(self, capsys, no_aws):
        assert run_cli("--validate-templates") == 2
        assert "--validate-templates" in capsys.readouterr().err

    @pytest.mark.parametrize("fmt, suffix", [("word", ".yaml"), ("excel", ".json")])
    def test_print_default_template(self, fmt, suffix, tmp_path, capsys, no_aws):
        assert run_cli("--print-default-template", fmt) == 0
        text = capsys.readouterr().out
        path = write(tmp_path, f"printed{suffix}", text)
        assert load_report_template(path, fmt).data == default_template(fmt).data

    def test_word_template_needs_create_word(self, capsys, no_aws):
        path = str(shipped_template_path("word"))
        assert run_cli("--word-template", path) == 2
        assert "--word-template: this flag needs --create-word" in (
            capsys.readouterr().err
        )

    def test_excel_template_needs_an_excel_report(self, capsys, no_aws):
        path = str(shipped_template_path("excel"))
        assert run_cli("--create-word", "--excel-template", path) == 2
        assert "--excel-template: this flag needs --create-excel" in (
            capsys.readouterr().err
        )

    def test_help_lists_the_template_flags(self, capsys):
        with pytest.raises(SystemExit):
            cli_main.create_parser().parse_args(["--help"])
        text = capsys.readouterr().out
        for flag in (
            "--word-template",
            "--excel-template",
            "--print-default-template",
            "--validate-templates",
        ):
            assert flag in text

    def test_generator_passes_the_templates_to_the_builders(self, tmp_path):
        from inventag.core import cloud_bom_generator as module

        word, excel = default_template("word"), default_template("excel")
        config = module.MultiAccountConfig(
            accounts=[],
            output_directory=str(tmp_path / "out"),
            word_template=word,
            excel_template=excel,
        )
        generator = module.CloudBOMGenerator(config)
        context = Mock()
        context.credentials.account_name = "test"
        context.resource_count = 0
        context.processing_time_seconds = 0.0
        context.processing_errors = []
        generator.account_contexts = {"111111111111": context}
        with patch.object(module, "BOMDataProcessor") as processor, patch.object(
            module, "BOMConverter"
        ) as converter:
            bom_data = Mock()
            bom_data.generation_metadata = {}
            bom_data.processing_statistics = {}
            processor.return_value.process_inventory_data.return_value = bom_data
            result = generator._generate_bom_documents([], {}, ["excel", "word"])
        assert result["success"] is True
        built = converter.return_value
        assert built.generate_excel_bom.call_args.kwargs["template"] is excel
        assert built.generate_word_bom.call_args.kwargs["template"] is word


# ----------------------------------------------------------------------- docs
class TestDocs:
    GUIDE = REPO_ROOT / "docs" / "templates" / "layout-flags.md"

    def test_guide_documents_every_key_variable_and_section_type(self):
        text = self.GUIDE.read_text()
        for group, keys in schema_reference().items():
            for key in keys:
                assert f"`{key.name}`" in text, f"{group}: {key.name}"
        for name in list(GLOBAL_VARIABLES) + list(SERVICE_VARIABLES):
            assert f"`{{{{ {name} }}}}`" in text, name
        for fmt, content_types in rt.CONTENT_TYPES.items():
            for content_type in content_types:
                assert f"`{content_type}`" in text, content_type
        for field in rt.KNOWN_RESOURCE_FIELDS:
            assert f"`{field}`" in text, field

    def test_guide_states_the_real_limits(self):
        text = self.GUIDE.read_text()
        for value in (
            rt.MAX_TEMPLATE_BYTES,
            rt.MAX_TEXT_LENGTH,
            rt.MAX_SECTIONS,
            rt.MAX_COLUMNS,
            rt.MAX_PARAGRAPHS,
            rt.MAX_VARIABLES,
            rt.MAX_LOGO_BYTES,
        ):
            assert str(value) in text.replace(",", ""), value

    def test_examples_in_the_guide_are_valid_templates(self, tmp_path):
        text = self.GUIDE.read_text()
        blocks = re.findall(r"```(yaml|json) title=\"([^\"]+)\"\n(.*?)```", text, re.S)
        assert len(blocks) >= 2
        for language, title, body in blocks:
            path = write(tmp_path, Path(title).name, body)
            fmt = "excel" if "excel" in title else "word"
            load_report_template(path, fmt)
