"""The JSON, CSV and YAML files the reporting package writes are written whole or not at all.

A write that fails part-way must leave the file that was there as it was, and
no temporary file in the folder. (Workbooks and Word documents already go
through ``save_atomically``.)
"""

import os

import pytest

from inventag.reporting import configuration_manager as configuration_module
from inventag.reporting import csv_builder as csv_module
from inventag.reporting import document_generator as generator_module
from inventag.reporting import template_framework as template_module
from inventag.reporting.bom_processor import BOMData
from inventag.reporting.configuration_manager import (
    ConfigurationManager,
    ConfigurationSet,
)
from inventag.reporting.document_generator import (
    DocumentConfig,
    DocumentGenerationResult,
    DocumentGenerationSummary,
    DocumentGenerator,
)
from inventag.reporting.template_framework import DocumentTemplate, TemplateManager

OLD = "the previous complete file\n"


def _half_dump(obj, fileobj, *args, **kwargs):
    fileobj.write('{"half": ')
    raise RuntimeError("write failed")


def _folder_after(tmp_path, target):
    return sorted(p.name for p in tmp_path.iterdir()), target.read_text()


def test_the_generation_report_keeps_the_old_file_when_the_write_fails(
    tmp_path, monkeypatch
):
    target = tmp_path / "report.json"
    target.write_text(OLD)
    monkeypatch.setattr(generator_module.json, "dump", _half_dump)
    generator = DocumentGenerator(
        DocumentConfig(output_formats=["csv"], output_directory=str(tmp_path))
    )
    summary = DocumentGenerationSummary(
        total_formats=1,
        successful_formats=1,
        failed_formats=0,
        results=[
            DocumentGenerationResult(format_type="csv", filename="a", success=True)
        ],
        total_generation_time=0.1,
    )
    generator.save_generation_report(summary, str(target))
    assert _folder_after(tmp_path, target) == (["report.json"], OLD)


def test_a_csv_keeps_the_old_file_when_the_write_fails(tmp_path, monkeypatch):
    target = tmp_path / "out.csv"
    target.write_text(OLD)

    def half_csv(fileobj, headers, rows):
        fileobj.write("id,")
        raise RuntimeError("write failed")

    monkeypatch.setattr(csv_module, "write_safe_csv", half_csv)
    builder = csv_module.CSVBuilder(DocumentConfig(output_formats=["csv"]))
    result = builder.generate_document(
        BOMData(resources=[{"id": "i-1", "service": "EC2"}]), str(target)
    )
    assert result.success is False
    assert _folder_after(tmp_path, target) == (["out.csv"], OLD)


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_a_saved_configuration_keeps_the_old_file_when_the_write_fails(
    tmp_path, monkeypatch, suffix
):
    target = tmp_path / f"config{suffix}"
    target.write_text(OLD)
    monkeypatch.setattr(configuration_module.json, "dump", _half_dump)
    monkeypatch.setattr(configuration_module.yaml, "dump", _half_dump)
    with pytest.raises(RuntimeError, match="write failed"):
        ConfigurationManager(str(tmp_path)).save_configuration(
            ConfigurationSet(name="c"), str(target)
        )
    assert _folder_after(tmp_path, target) == ([f"config{suffix}"], OLD)


def test_a_saved_configuration_in_an_unsupported_format_keeps_the_old_file(tmp_path):
    target = tmp_path / "config.txt"
    target.write_text(OLD)
    with pytest.raises(ValueError, match="Unsupported output format"):
        ConfigurationManager(str(tmp_path)).save_configuration(
            ConfigurationSet(name="c"), str(target)
        )
    assert _folder_after(tmp_path, target) == (["config.txt"], OLD)


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_a_saved_template_keeps_the_old_file_when_the_write_fails(
    tmp_path, monkeypatch, suffix
):
    target = tmp_path / f"template{suffix}"
    target.write_text(OLD)
    monkeypatch.setattr(template_module.json, "dump", _half_dump)
    monkeypatch.setattr(template_module.yaml, "dump", _half_dump)
    with pytest.raises(RuntimeError, match="write failed"):
        TemplateManager().save_template(DocumentTemplate(name="t"), str(target))
    assert _folder_after(tmp_path, target) == ([f"template{suffix}"], OLD)


def test_a_saved_template_in_an_unsupported_format_keeps_the_old_file(tmp_path):
    target = tmp_path / "template.txt"
    target.write_text(OLD)
    with pytest.raises(ValueError, match="Unsupported output format"):
        TemplateManager().save_template(DocumentTemplate(name="t"), str(target))
    assert _folder_after(tmp_path, target) == (["template.txt"], OLD)


def test_a_complete_write_replaces_the_file_and_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "template.json"
    target.write_text(OLD)
    TemplateManager().save_template(DocumentTemplate(name="t"), str(target))
    assert [p.name for p in tmp_path.iterdir()] == ["template.json"]
    assert '"name": "t"' in target.read_text()
    assert os.stat(target).st_size > len(OLD)


def _write_each_kind(tmp_path):
    """Write one file of each kind; return {kind: path}."""
    generator = DocumentGenerator(
        DocumentConfig(output_formats=["csv"], output_directory=str(tmp_path))
    )
    summary = DocumentGenerationSummary(
        total_formats=1,
        successful_formats=1,
        failed_formats=0,
        results=[],
        total_generation_time=0.1,
    )
    paths = {
        "report": tmp_path / "report.json",
        "csv": tmp_path / "out.csv",
        "config": tmp_path / "config.json",
        "template": tmp_path / "template.yaml",
    }
    generator.save_generation_report(summary, str(paths["report"]))
    csv_module.CSVBuilder(DocumentConfig(output_formats=["csv"])).generate_document(
        BOMData(resources=[{"id": "i-1"}]), str(paths["csv"])
    )
    ConfigurationManager(str(tmp_path)).save_configuration(
        ConfigurationSet(name="c"), str(paths["config"])
    )
    TemplateManager().save_template(DocumentTemplate(name="t"), str(paths["template"]))
    return paths


# What v1.2.1 gave: the report and the CSV were opened with open_private (0600);
# the saved configuration and template with a plain open (0666 minus the umask).
@pytest.mark.parametrize(
    "umask,expected",
    [
        (0o022, {"report": 0o600, "csv": 0o600, "config": 0o644, "template": 0o644}),
        (0o077, {"report": 0o600, "csv": 0o600, "config": 0o600, "template": 0o600}),
    ],
)
def test_file_modes_are_what_they_were_before_the_atomic_write(
    tmp_path, umask, expected
):
    previous = os.umask(umask)
    try:
        paths = _write_each_kind(tmp_path)
    finally:
        os.umask(previous)
    modes = {kind: os.stat(path).st_mode & 0o777 for kind, path in paths.items()}
    assert modes == expected


# ------------------------------------------------- the HTML report (v1.5.1)
def test_the_html_report_keeps_the_old_file_when_the_write_fails(tmp_path, monkeypatch):
    from inventag.reporting import html_report

    target = tmp_path / "multi_account_bom_20261112_090000.html"
    target.write_text(OLD)
    real_open = open

    class _Half:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()
            return False

        def write(self, data):
            self.handle.write(data[:10])
            raise RuntimeError("write failed")

    monkeypatch.setattr(
        html_report,
        "open",
        lambda path, *a, **k: _Half(real_open(path, *a, **k)),
        raising=False,
    )
    with pytest.raises(RuntimeError, match="write failed"):
        html_report.write_html_report(
            BOMData(resources=[{"id": "i-1", "service": "EC2"}]), target
        )
    assert _folder_after(tmp_path, target) == ([target.name], OLD)


def test_a_complete_html_report_replaces_the_file_and_leaves_no_temporary_file(
    tmp_path,
):
    from inventag.reporting.html_report import write_html_report

    target = tmp_path / "r.html"
    target.write_text(OLD)
    write_html_report(BOMData(resources=[{"id": "i-1", "service": "EC2"}]), target)
    assert [p.name for p in tmp_path.iterdir()] == ["r.html"]
    assert target.read_text().startswith("<!DOCTYPE html>")
