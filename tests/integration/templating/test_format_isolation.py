"""One failing report format does not stop the others (register row A-13).

With ``--template``, Word and Excel are written one by one. A format that
fails is named in one ERROR line, the formats that could be written are kept,
and the exit code is the one v1.2.1 gives (1 for every failed format).
"""

import glob
import logging

from openpyxl import load_workbook
from docx import Document

from inventag.templating import runner

from .test_report_templates import aws, run_inventag  # noqa: F401

ARGS = (
    "--template",
    "standard-bom",
    "--create-excel",
    "--create-word",
    "--account-regions",
    "us-east-1",
)


def _boom(name):
    def fail(*args, **kwargs):
        raise RuntimeError(f"{name} writer broke")

    return fail


def _files(tmp_path, ext):
    return glob.glob(str(tmp_path / "bom_output" / f"multi_account_bom_*.{ext}"))


def _summary_text(path):
    return [
        str(c.value) for row in load_workbook(path)["Summary"].iter_rows() for c in row
    ]


def _errors(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


def test_word_fails_excel_is_still_written(aws, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(runner, "render_word", _boom("word"))
    code = run_inventag(monkeypatch, tmp_path, *ARGS)
    assert code == 1
    assert len(_files(tmp_path, "xlsx")) == 1
    assert _files(tmp_path, "docx") == []
    text = _summary_text(_files(tmp_path, "xlsx")[0])
    assert any("Word" in c and "not written" in c for c in text), text
    assert any("Could not write the Word report" in m for m in _errors(caplog))


def test_excel_fails_word_is_still_written(aws, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(runner, "render_excel", _boom("excel"))
    code = run_inventag(monkeypatch, tmp_path, *ARGS)
    assert code == 1
    assert len(_files(tmp_path, "docx")) == 1
    assert _files(tmp_path, "xlsx") == []
    paragraphs = [p.text for p in Document(_files(tmp_path, "docx")[0]).paragraphs]
    assert any("Excel" in p and "not written" in p for p in paragraphs), paragraphs
    assert any("Could not write the Excel report" in m for m in _errors(caplog))


def test_both_fail_exit_code_and_no_files(aws, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(runner, "render_excel", _boom("excel"))
    monkeypatch.setattr(runner, "render_word", _boom("word"))
    code = run_inventag(monkeypatch, tmp_path, *ARGS)
    assert code == 1
    assert _files(tmp_path, "xlsx") == [] and _files(tmp_path, "docx") == []
    errors = _errors(caplog)
    assert any("Could not write the Excel report" in m for m in errors)
    assert any("Could not write the Word report" in m for m in errors)
