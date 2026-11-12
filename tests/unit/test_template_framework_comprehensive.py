#!/usr/bin/env python3
"""
Unit tests for the document template framework (real API).

Covers template loading (YAML/JSON) and caching, validation, listing,
save/load round-trips, variable resolution and formatting, document structure
building and table-of-contents generation.
"""

import json

import pytest
import yaml

from inventag.reporting.template_framework import (
    DocumentSection,
    DocumentStructureBuilder,
    DocumentTemplate,
    TableOfContentsConfig,
    TemplateLoader,
    TemplateManager,
    TemplateVariable,
    TemplateVariableResolver,
    create_template_manager,
)

TEMPLATE_DATA = {
    "name": "Test Template",
    "format_type": "word",
    "description": "unit test template",
    "variables": {
        "company_name": "Test Corp",
        "document_title": {"value": None, "default_value": "BOM Report"},
    },
    "sections": [
        {"id": "summary", "title": "Summary", "level": 1},
        {
            "id": "resources",
            "title": "Resources",
            "level": 1,
            "content_type": "table",
            "subsections": [
                {"id": "ec2", "title": "EC2", "level": 2},
                {
                    "id": "hidden",
                    "title": "Hidden",
                    "level": 2,
                    "include_in_toc": False,
                },
            ],
        },
    ],
    "table_of_contents": {"enabled": True, "max_depth": 2},
    "page_orientation": "landscape",
}


@pytest.fixture
def manager(tmp_path):
    (tmp_path / "test_template.yaml").write_text(yaml.safe_dump(TEMPLATE_DATA))
    excel = dict(TEMPLATE_DATA, name="Excel Template", format_type="excel")
    (tmp_path / "excel_template.json").write_text(json.dumps(excel))
    (tmp_path / "notes.txt").write_text("not a template")
    return TemplateManager(template_directory=str(tmp_path))


class TestTemplateManager:
    def test_init(self, tmp_path):
        manager = TemplateManager(template_directory=str(tmp_path))
        assert manager.template_directory == str(tmp_path)
        assert manager._template_cache == {}
        assert isinstance(manager.loader, TemplateLoader)
        assert isinstance(manager.variable_resolver, TemplateVariableResolver)
        assert TemplateManager().template_directory == "templates"

    def test_load_template_yaml_success(self, manager):
        template = manager.load_template("test_template")
        assert template.name == "Test Template"
        assert template.format_type == "word"
        assert [s.id for s in template.sections] == ["summary", "resources"]
        assert template.variables["company_name"].value == "Test Corp"
        assert template.page_orientation == "landscape"
        assert template.template_path.endswith("test_template.yaml")

    def test_load_template_json_success(self, manager):
        template = manager.load_template("excel_template")
        assert template.name == "Excel Template"
        assert template.format_type == "excel"

    def test_load_template_is_cached(self, manager, tmp_path):
        first = manager.load_template("test_template")
        (tmp_path / "test_template.yaml").unlink()
        assert manager.load_template("test_template") is first

    def test_load_missing_template(self, manager):
        with pytest.raises(FileNotFoundError):
            manager.load_template("does_not_exist")

    @pytest.mark.parametrize("name", ["../secret", "a/b", "..", "", "x\\y", "a\x00b"])
    def test_template_name_cannot_escape_directory(self, manager, tmp_path, name):
        (tmp_path.parent / "secret.yaml").write_text(yaml.safe_dump(TEMPLATE_DATA))
        with pytest.raises(ValueError):
            manager.load_template(name)

    def test_list_available_templates(self, manager):
        assert manager.list_available_templates() == ["excel_template", "test_template"]

    def test_list_available_templates_missing_dir(self, tmp_path):
        assert TemplateManager(str(tmp_path / "nope")).list_available_templates() == []

    def test_validate_template_success(self, manager):
        assert manager.validate_template(manager.load_template("test_template")) == []

    def test_validate_template_reports_problems(self, manager):
        template = DocumentTemplate(
            name="",
            format_type="",
            sections=[
                DocumentSection(id="a", title="A"),
                DocumentSection(id="a", title=""),
                DocumentSection(id="", title="B"),
            ],
            variables={"v": TemplateVariable(name="", value=1)},
        )
        issues = manager.validate_template(template)
        assert "Template name is required" in issues
        assert "Template format_type is required" in issues
        assert "Duplicate section ID: a" in issues
        assert "Section a must have a title" in issues
        assert "All sections must have an ID" in issues
        assert "Variable v must have a name" in issues

    def test_validate_template_requires_sections(self, manager):
        issues = manager.validate_template(DocumentTemplate(name="x"))
        assert "Template must have at least one section" in issues

    @pytest.mark.parametrize("suffix", [".json", ".yaml"])
    def test_save_and_reload_round_trip(self, manager, tmp_path, suffix):
        original = manager.create_default_template("excel")
        path = tmp_path / f"saved{suffix}"
        manager.save_template(original, str(path))
        reloaded = TemplateLoader().load_from_file(str(path))
        assert reloaded.name == original.name
        assert reloaded.format_type == "excel"
        assert [s.id for s in reloaded.sections] == [s.id for s in original.sections]
        assert reloaded.table_of_contents.max_depth == 3
        assert reloaded.header_footer.header_text == original.header_footer.header_text
        assert reloaded.branding.company_name == original.branding.company_name

    def test_save_unsupported_format(self, manager, tmp_path):
        with pytest.raises(ValueError):
            manager.save_template(DocumentTemplate(name="x"), str(tmp_path / "t.txt"))

    def test_create_default_template(self, manager):
        template = manager.create_default_template("word")
        assert template.name == "Default Word Template"
        assert manager.validate_template(template) == []
        assert {"title_page", "executive_summary", "compliance_details"} <= {
            s.id for s in template.sections
        }

    def test_factory(self, tmp_path):
        assert create_template_manager(str(tmp_path)).template_directory == str(
            tmp_path
        )


class TestTemplateLoader:
    def test_unsupported_extension(self, tmp_path):
        path = tmp_path / "t.txt"
        path.write_text("name: x")
        with pytest.raises(ValueError):
            TemplateLoader().load_from_file(str(path))

    def test_yaml_is_loaded_safely(self, tmp_path):
        path = tmp_path / "evil.yaml"
        path.write_text("name: !!python/object/apply:os.system ['echo pwned']\n")
        with pytest.raises(yaml.YAMLError):
            TemplateLoader().load_from_file(str(path))

    def test_load_from_dict_defaults(self):
        template = TemplateLoader().load_from_dict({})
        assert template.name == "Untitled Template"
        assert template.format_type == "word"
        assert template.sections == []
        assert template.page_size == "letter"

    def test_variables_parsed(self):
        template = TemplateLoader().load_from_dict(TEMPLATE_DATA)
        var = template.variables["document_title"]
        assert var.value is None and var.default_value == "BOM Report"


class TestDocumentTemplate:
    def test_defaults(self):
        template = DocumentTemplate(name="T")
        assert template.format_type == "word"
        assert template.sections == [] and template.variables == {}
        assert template.page_margins == {
            "top": 1.0,
            "bottom": 1.0,
            "left": 1.0,
            "right": 1.0,
        }
        assert template.page_orientation == "portrait"

    def test_mutable_defaults_not_shared(self):
        a, b = DocumentTemplate(name="a"), DocumentTemplate(name="b")
        a.sections.append(DocumentSection(id="x", title="X"))
        a.page_margins["top"] = 2.0
        assert b.sections == [] and b.page_margins["top"] == 1.0


class TestTemplateVariableResolver:
    def test_builtins_template_and_context_precedence(self):
        resolver = TemplateVariableResolver()
        template = TemplateLoader().load_from_dict(TEMPLATE_DATA)
        resolved = resolver.resolve_variables(template, {"company_name": "Override"})
        assert {"current_date", "current_year", "generation_timestamp"} <= set(resolved)
        assert resolved["company_name"] == "Override"
        assert resolved["document_title"] == "BOM Report"  # default_value used

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("Hello {{name}}", "Hello acme"),
            ("{{name|upper}}", "ACME"),
            ("{{name|title}}", "Acme"),
            ("{{shout|lower}}", "loud"),
            ("{{count|number:.2f}}", "3.14"),
            ("{{when|date:%d/%m/%Y}}", "01/02/2026"),
            ("{{missing}} stays", "{{missing}} stays"),
            ("{{empty}}", ""),
            ("", ""),
        ],
    )
    def test_substitute_text(self, text, expected):
        variables = {
            "name": "acme",
            "shout": "LOUD",
            "count": 3.14159,
            "when": "2026-02-01T00:00:00Z",
            "empty": None,
        }
        assert TemplateVariableResolver().substitute_text(text, variables) == expected

    def test_bad_format_falls_back_to_plain_value(self):
        assert (
            TemplateVariableResolver().substitute_text("{{x|number:.2f}}", {"x": "abc"})
            == "abc"
        )


class TestDocumentStructureBuilder:
    def test_build_structure_copies_sections(self):
        template = TemplateLoader().load_from_dict(TEMPLATE_DATA)
        structure = DocumentStructureBuilder().build_structure(template)
        assert [s.id for s in structure] == ["summary", "resources"]
        assert [s.id for s in structure[1].subsections] == ["ec2", "hidden"]
        structure[0].variables["changed"] = True
        assert "changed" not in template.sections[0].variables

    def test_table_of_contents(self):
        template = TemplateLoader().load_from_dict(TEMPLATE_DATA)
        builder = DocumentStructureBuilder()
        toc = builder.generate_table_of_contents(
            template.sections, template.table_of_contents
        )
        assert [(e["id"], e["level"]) for e in toc] == [
            ("summary", 1),
            ("resources", 1),
            ("ec2", 2),
        ]

    def test_table_of_contents_depth_and_disabled(self):
        template = TemplateLoader().load_from_dict(TEMPLATE_DATA)
        builder = DocumentStructureBuilder()
        shallow = builder.generate_table_of_contents(
            template.sections, TableOfContentsConfig(max_depth=1)
        )
        assert [e["id"] for e in shallow] == ["summary", "resources"]
        assert (
            builder.generate_table_of_contents(
                template.sections, TableOfContentsConfig(enabled=False)
            )
            == []
        )
        assert builder.generate_table_of_contents(template.sections, None) == []
