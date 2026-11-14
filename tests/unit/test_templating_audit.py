"""Fixes found while auditing inventag/templating."""

import argparse
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from docx import Document
from openpyxl import load_workbook

from inventag.core.cloud_bom_generator import MultiAccountConfig
from inventag.reporting.bom_processor import BOMProcessingConfig
from inventag.templating import cli as templates_cli
from inventag.templating.errors import TemplateError
from inventag.templating.loader import safe_relative_path
from inventag.templating.registry import (
    BUILTIN_DIR,
    SearchDir,
    TemplateRegistry,
    looks_like_path,
)
from inventag.templating.render_excel import render_excel
from inventag.templating.render_word import render_word
from inventag.templating.runner import (
    EXIT_NO_RESOURCES,
    TemplatedCloudBOMGenerator,
    TemplateRun,
    bom_result_is_empty,
    load_templates,
    unused_option_warnings,
)
from inventag.templating.tag_policy import evaluate


@pytest.fixture
def registry(tmp_path):
    return TemplateRegistry(
        [SearchDir("user", tmp_path / "none"), SearchDir("builtin", BUILTIN_DIR)]
    )


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------ tag policy


def test_invalid_counts_belong_to_the_full_tag_key(registry, tmp_path):
    policy = write(
        tmp_path / "p.yaml",
        "kind: tag-policy\nname: p\nspec:\n  required_tags:\n"
        "    - {key: 'team:owner', allowed_values: [a]}\n"
        "    - {key: team, allowed_values: [x]}\n",
    )
    resources = [
        {
            "service": "S3",
            "resource_type": "Bucket",
            "tags": {"team:owner": "zzz", "team": "x"},
        }
    ]
    report = evaluate(resources, registry.resolve(str(policy)))
    assert report.invalid_by_key() == {"team:owner": 1, "team": 0}


# ------------------------------------------------------------ rendering


def test_control_characters_and_huge_values_do_not_break_files(registry, tmp_path):
    resources = [
        {
            "service": "S3",
            "resource_type": "Bucket",
            "resource_name": "a\x07b",
            "tags": {"Owner": "x\x00y"},
            "notes": "z" * 40000,
        }
    ]
    template = registry.resolve("finops-cost-report")
    compliance = evaluate(resources, registry.resolve("finops-cost-allocation"))
    path = render_excel(str(tmp_path / "a.xlsx"), resources, template, compliance)
    wb = load_workbook(path)
    assert wb["S3"]["E2"].value == "a\ufffdb"
    path = render_word(str(tmp_path / "a.docx"), resources, template, compliance)
    assert Document(path)

    wide = registry.resolve("standard-bom")
    wide.spec["excel"]["include_all_fields"] = True
    wb = load_workbook(render_excel(str(tmp_path / "b.xlsx"), resources, wide))
    values = [c.value for c in wb["S3"][2] if c.value and len(c.value) > 1000]
    assert values and len(values[0]) == 32767


# ------------------------------------------------------------ loading


def test_json_file_is_a_path_not_a_name(tmp_path, registry, capsys):
    f = write(
        tmp_path / "t.json",
        '{"format_version": 1, "kind": "report", "name": "t", "spec": {"title": "J"}}',
    )
    assert looks_like_path("t.json") and looks_like_path("a.b")
    assert not looks_like_path("standard-bom")
    assert registry.resolve(str(f)).spec["title"] == "J"
    assert templates_cli.main(["validate", str(f)]) == 0


@pytest.mark.parametrize(
    "reference, message",
    [
        ("..\\outside.png", "must stay inside"),
        ("sub\\..\\..\\outside.png", "must stay inside"),
        ("C:\\img\\a.png", "drive letter"),
        ("C:/img/a.png", "drive letter"),
        ("\\\\server\\share\\a.png", "relative path"),
        ("/etc/passwd", "relative path"),
    ],
)
def test_windows_style_paths_are_refused_everywhere(tmp_path, reference, message):
    with pytest.raises(ValueError, match=message):
        safe_relative_path(tmp_path, reference)


def test_backslash_separator_works_inside_the_folder(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"x")
    assert (
        safe_relative_path(tmp_path, "assets\\logo.png")
        == (tmp_path / "assets" / "logo.png").resolve()
    )


def test_schema_patterns_match_the_whole_value(tmp_path):
    bad_name = write(tmp_path / "n.yaml", 'kind: report\nname: "abc\\n"\nspec: {}\n')
    with pytest.raises(TemplateError, match="lower-case"):
        TemplateRegistry([]).resolve(str(bad_name))
    arabic = write(
        tmp_path / "c.yaml",
        "kind: config\nname: c\nspec:\n  accounts:\n"
        '    - {account_id: "١٢٣٤٥٦٧٨٩٠١٢", profile_name: p}\n',
    )
    with pytest.raises(TemplateError, match="12-digit"):
        TemplateRegistry([]).resolve(str(arabic))


def test_empty_tag_key_is_an_error(tmp_path):
    f = write(
        tmp_path / "p.yaml",
        "kind: tag-policy\nname: p\nspec:\n  required_tags:\n    - {key: ' '}\n",
    )
    with pytest.raises(TemplateError, match="must not be empty"):
        TemplateRegistry([]).resolve(str(f))


@pytest.mark.parametrize(
    "text, message",
    [
        ("kind: report\nname: x\nspec: {}\nbogus: 1\n", "bogus"),
        ("kind: report\nname: x\nspec:\n  titel: a\n", "did you mean 'title'"),
        ("kind: report\nname: x\nspec:\n  title: 5\n", "must be text"),
        ("kind: report\nname: x\nspec:\n  title: a\n  title: b\n", "duplicate key"),
        ("\ufeffkind: report\nname: x\nspec:\n  titel: a\n", "titel"),
        ("", "empty"),
        ("kind: report\nname: x\nspec:\n\ttitle: a\n", "invalid YAML"),
    ],
)
def test_bad_templates_name_the_key_and_the_file(tmp_path, text, message):
    f = write(tmp_path / "bad.yaml", text)
    with pytest.raises(TemplateError) as error:
        TemplateRegistry([]).resolve(str(f))
    shown = str(error.value)
    assert message in shown and "bad.yaml" in shown


def test_bom_and_crlf_and_anchors_load(tmp_path):
    f = tmp_path / "ok.yaml"
    f.write_bytes(
        b"\xef\xbb\xbfkind: report\r\nname: ok\r\nspec:\r\n  colors: &c\r\n"
        b"    header_fill: '112233'\r\n  word: {orientation: landscape}\r\n"
    )
    assert TemplateRegistry([]).resolve(str(f)).spec["colors"]["header_fill"] == (
        "112233"
    )


# ------------------------------------------------ options that are not shown


def make_run(registry, text=None, tmp_path=None):
    if text:
        path = write(tmp_path / "r.yaml", text)
        return load_templates([str(path)], registry)
    return load_templates(["standard-bom"], registry)


def test_tag_mappings_warning_names_the_column(tmp_path, registry):
    tags = write(
        tmp_path / "tags.yaml",
        "tag_mappings:\n  - {tag: CostCenter, name: Cost Center}\n",
    )
    args = argparse.Namespace(tag_mappings=str(tags), service_descriptions=None)
    (message,) = unused_option_warnings(args, make_run(registry))
    assert "'Cost Center'" in message and "--tag-mappings" in message
    listed = make_run(
        registry,
        "kind: report\nname: r\nextends: standard-bom\nspec:\n  columns:\n"
        "    - {field: resource_id}\n    - {field: Cost Center}\n",
        tmp_path,
    )
    assert unused_option_warnings(args, listed) == []


def test_service_descriptions_warning(tmp_path, registry):
    args = argparse.Namespace(tag_mappings=None, service_descriptions="d.yaml")
    (message,) = unused_option_warnings(args, make_run(registry))
    assert "service_description" in message
    assert unused_option_warnings(argparse.Namespace(), make_run(registry)) == []


# ------------------------------------------------------ empty results


def result(success=True, generation=0, stats=0):
    out = {"success": success}
    if generation is not None:
        out["bom_generation"] = {"total_resources": generation, "generated_files": []}
    if stats is not None:
        out["processing_statistics"] = {"total_resources": stats}
    return out


def test_bom_result_is_empty():
    assert bom_result_is_empty(result())
    assert not bom_result_is_empty(result(generation=3, stats=3))
    assert not bom_result_is_empty(result(success=False))
    assert not bom_result_is_empty({"success": True})  # unknown is not "empty"
    assert bom_result_is_empty(result(generation=None, stats=0))
    assert not bom_result_is_empty(None)


def test_finish_exit_code_for_empty_results(registry, capsys):
    run = TemplateRun(registry.resolve("standard-bom"), None, None)
    log = logging.getLogger("t")
    assert run.finish(result(), log) == 0  # default: unchanged
    assert run.finish(result(), log, fail_if_empty=True) == EXIT_NO_RESOURCES == 6
    assert run.finish(result(generation=2, stats=2), log, fail_if_empty=True) == 0
    assert "--fail-if-empty" in capsys.readouterr().err


def test_templated_generator_reports_empty_result(registry, tmp_path, caplog):
    config = MultiAccountConfig(
        output_directory=str(tmp_path / "out"),
        bom_processing_config=BOMProcessingConfig(
            enable_network_analysis=False,
            enable_security_analysis=False,
            enable_service_enrichment=False,
            enable_service_descriptions=False,
            enable_tag_mapping=False,
        ),
    )
    run = TemplateRun(registry.resolve("standard-bom"), None, None)
    generator = TemplatedCloudBOMGenerator(config, run)
    generator.account_contexts = {
        "1": SimpleNamespace(session=MagicMock(), processing_errors=[])
    }
    with caplog.at_level(logging.WARNING):
        out = generator._generate_bom_documents([], {}, ["excel"])
    assert out["empty"] is True and out["total_resources"] == 0
    assert len(out["generated_files"]) == 1  # the template path still writes a file
    assert "No resources to report" in caplog.text
    full = {"success": True, "bom_generation": out}
    assert bom_result_is_empty(full)


# ------------------------------------------------------ JSON templates


def test_json_template_with_tabs_and_surrogate_escapes(tmp_path, registry):
    f = tmp_path / "t.json"
    f.write_text(
        '{\n\t"format_version": 1,\n\t"kind": "report",\n\t"name": "t",\n'
        '\t"spec": {"title": "T\\u00e9 \\ud83d\\ude00"}\n}\n',
        encoding="utf-8",
    )
    resolved = registry.resolve(str(f))
    assert resolved.spec["title"] == "Té 😀"
    assert templates_cli.main(["validate", str(f)]) == 0


def test_json_errors_name_the_file_and_key(tmp_path, registry):
    f = write(tmp_path / "d.json", '{"kind": "report", "kind": "config"}')
    with pytest.raises(TemplateError, match="duplicate key 'kind'"):
        registry.resolve(str(f))
    f = write(tmp_path / "s.json", "{")
    with pytest.raises(TemplateError, match="invalid JSON") as error:
        registry.resolve(str(f))
    assert "s.json" in str(error.value)
    f = write(
        tmp_path / "u.json",
        '{"kind": "report", "name": "u", "spec": {"titel": "x"}}',
    )
    with pytest.raises(TemplateError, match="did you mean 'title'") as error:
        registry.resolve(str(f))
    assert "u.json" in str(error.value)
    f = write(tmp_path / "deep.json", "[" * 5000 + "]" * 5000)
    with pytest.raises(TemplateError):
        registry.resolve(str(f))


def test_deeply_nested_yaml_is_an_error_not_a_crash(tmp_path, registry):
    f = write(tmp_path / "deep.yaml", "kind: report\nname: d\nspec: " + "[" * 5000)
    with pytest.raises(TemplateError):
        registry.resolve(str(f))
    f = write(
        tmp_path / "deep2.yaml", "kind: report\nname: d\nspec: " + "[" * 40 + "]" * 40
    )
    with pytest.raises(TemplateError, match="nested too deeply"):
        registry.resolve(str(f))
