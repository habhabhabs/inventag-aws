"""Re-saving a file keeps the mode the existing file had (review M1).

v1.2.1 wrote these four files with a plain ``open(path, "w")``: an existing
file kept its mode (a file the user had restricted to 0640 stayed 0640); a new
file got 0666 minus the umask. The atomic writes of A-14 replace the file, so
the mode must be carried over from the file that is replaced.
"""

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

import inventag.reporting as reporting
from inventag.compliance.checker import ComprehensiveTagComplianceChecker
from inventag.reporting.configuration_manager import (
    ConfigurationManager,
    ConfigurationSet,
)
from inventag.reporting.template_framework import DocumentTemplate, TemplateManager
from inventag.templating.runner import _write_json_atomically


class _NoWordSupport:
    def __init__(self, *args, **kwargs):
        pass

    def generate_word_document(self, *args, **kwargs):
        raise ImportError("python-docx is not installed")


def _write(kind, folder, monkeypatch):
    """Write one file of ``kind`` in ``folder``; return its path."""
    if kind == "configuration":
        path = folder / "config.json"
        ConfigurationManager(str(folder)).save_configuration(
            ConfigurationSet(name="c"), str(path)
        )
    elif kind == "template":
        path = folder / "template.yaml"
        TemplateManager().save_template(DocumentTemplate(name="t"), str(path))
    elif kind == "checker text report":
        monkeypatch.setattr(reporting, "DocumentGenerator", _NoWordSupport)
        checker = ComprehensiveTagComplianceChecker(regions=["us-east-1"])
        checker._generate_word_bom(
            SimpleNamespace(
                resources=[], compliance_details={"compliance_percentage": 1}
            ),
            str(folder / "bom.docx"),
        )
        path = folder / "bom.txt"
    else:  # the tag compliance JSON of a template run
        path = folder / "tag_compliance_20261117_000000.json"
        _write_json_atomically(str(path), {"summary": {}})
    return path


KINDS = ["configuration", "template", "checker text report", "tag compliance JSON"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("mask", [0o022, 0o077])
def test_an_existing_file_keeps_its_mode(kind, mask, tmp_path, monkeypatch):
    first = _write(kind, tmp_path, monkeypatch)
    os.chmod(first, 0o640)
    previous = os.umask(mask)
    try:
        path = _write(kind, tmp_path, monkeypatch)
    finally:
        os.umask(previous)
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("mask,mode", [(0o022, 0o644), (0o077, 0o600)])
def test_a_new_file_gets_the_mode_of_a_plain_open(
    kind, mask, mode, tmp_path, monkeypatch
):
    previous = os.umask(mask)
    try:
        path = _write(kind, tmp_path, monkeypatch)
    finally:
        os.umask(previous)
    assert stat.S_IMODE(path.stat().st_mode) == mode


# The HTML report (--create-html, v1.5.1) does not keep the mode of the file it
# replaces: it follows the rule of the other reports (Excel, Word), which are
# written with save_atomically and are private to the user (0600).
def _report(kind, folder):
    from inventag.reporting.bom_processor import BOMData
    from inventag.reporting.converter import BOMConverter
    from inventag.reporting.html_report import write_html_report

    data = BOMData(resources=[{"service": "S3", "id": "b", "region": "us-east-1"}])
    if kind == "html":
        return Path(write_html_report(data, folder / "r.html"))
    path = folder / "r.xlsx"
    BOMConverter(enrich_vpc_info=False).generate_excel_bom(data, str(path))
    return path


@pytest.mark.parametrize("existing", [None, 0o640, 0o644])
@pytest.mark.parametrize("mask", [0o022, 0o077])
def test_the_html_report_gets_the_mode_of_the_excel_report(tmp_path, existing, mask):
    modes = {}
    for kind in ("excel", "html"):
        folder = tmp_path / kind
        folder.mkdir()
        if existing is not None:
            first = _report(kind, folder)
            os.chmod(first, existing)
        previous = os.umask(mask)
        try:
            path = _report(kind, folder)
        finally:
            os.umask(previous)
        modes[kind] = stat.S_IMODE(path.stat().st_mode)
    assert modes == {"excel": 0o600, "html": 0o600}
