"""Template outputs: a failed format is named and does not stop the others
(A-13), and the files the templating code writes are written whole or not at
all (A-14)."""

import json
import logging
import os
from unittest.mock import MagicMock

from docx import Document
from openpyxl import load_workbook

from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    BOMProcessingConfig,
    MultiAccountConfig,
)
from inventag.templating import runner
from inventag.templating.runner import (
    TemplatedCloudBOMGenerator,
    TemplateRun,
)

RESOURCE = {
    "service": "S3",
    "resource_type": "Bucket",
    "resource_id": "bucket-one",
    "arn": "arn:aws:s3:::bucket-one",
    "region": "us-east-1",
    "source_account_id": "111111111111",
    "tags": {},
}


def _generator(registry, tmp_path, policy=None):
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
    run = TemplateRun(
        registry.resolve("standard-bom"),
        registry.resolve(policy) if policy else None,
        None,
    )
    generator = TemplatedCloudBOMGenerator(config, run)
    generator.account_contexts = {
        "111111111111": AccountContext(
            credentials=AccountCredentials(account_id="111111111111", account_name="a"),
            session=MagicMock(),
            caller_identity={},
        )
    }
    return generator


def _boom(*args, **kwargs):
    raise RuntimeError("secret-looking detail")


def _generate(generator, formats=("excel", "word")):
    return generator._generate_bom_documents([dict(RESOURCE)], {}, list(formats))


def _summary(path):
    return [
        str(c.value) for row in load_workbook(path)["Summary"].iter_rows() for c in row
    ]


def test_word_fails_excel_written_and_notes_the_missing_report(
    registry, tmp_path, monkeypatch, caplog
):
    monkeypatch.setattr(runner, "render_word", _boom)
    out = _generate(_generator(registry, tmp_path))
    assert out["success"] is False
    assert out["error"] == "Could not write: Word report (RuntimeError)"
    assert [p.rsplit(".", 1)[1] for p in out["generated_files"]] == ["xlsx"]
    assert any(
        "The Word report was not written (RuntimeError)" in c
        for c in _summary(out["generated_files"][0])
    )
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors == [
        "Could not write the Word report (RuntimeError). Run again with --debug "
        "to log the traceback."
    ]
    assert "secret-looking detail" not in " ".join(errors)


def test_excel_fails_word_written_and_notes_the_missing_report(
    registry, tmp_path, monkeypatch
):
    monkeypatch.setattr(runner, "render_excel", _boom)
    out = _generate(_generator(registry, tmp_path))
    assert out["success"] is False
    (docx,) = out["generated_files"]
    assert docx.endswith(".docx")
    assert any(
        "The Excel report was not written (RuntimeError)" in p.text
        for p in Document(docx).paragraphs
    )


def test_both_fail_writes_nothing_and_names_both(registry, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "render_excel", _boom)
    monkeypatch.setattr(runner, "render_word", _boom)
    out = _generate(_generator(registry, tmp_path))
    assert out["success"] is False
    assert out["generated_files"] == []
    assert out["error"] == (
        "Could not write: Excel report (RuntimeError); Word report (RuntimeError)"
    )


def test_file_error_names_the_system_reason(registry, tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError(13, "Permission denied", "/secret/path")

    monkeypatch.setattr(runner, "render_word", denied)
    out = _generate(_generator(registry, tmp_path))
    assert (
        out["error"]
        == "Could not write: Word report (PermissionError: Permission denied)"
    )
    assert "/secret/path" not in out["error"]


def test_clean_run_is_unchanged(registry, tmp_path):
    out = _generate(_generator(registry, tmp_path))
    assert out["success"] is True and len(out["generated_files"]) == 2
    assert not any("not written" in c for c in _summary(out["generated_files"][0]))


def test_tag_compliance_failure_does_not_stop_the_reports(
    registry, tmp_path, monkeypatch
):
    def fail(path, data):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(runner, "_write_json_atomically", fail, raising=False)
    out = _generate(_generator(registry, tmp_path, policy="finops-cost-allocation"))
    assert out["success"] is False
    assert out["error"] == (
        "Could not write: tag compliance file (OSError: No space left on device)"
    )
    assert len(out["generated_files"]) == 2


def test_half_written_compliance_json_leaves_no_file(registry, tmp_path, monkeypatch):
    """A write that breaks half way leaves no tag_compliance file (A-14)."""
    real_dump = json.dump

    def broken_dump(data, handle, **kwargs):
        handle.write('{"half": ')
        handle.flush()
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(runner.json, "dump", broken_dump)
    out = _generate(_generator(registry, tmp_path, policy="finops-cost-allocation"))
    monkeypatch.setattr(runner.json, "dump", real_dump)
    assert out["success"] is False
    leftovers = [f for f in os.listdir(tmp_path / "out") if "tag_compliance" in f]
    assert leftovers == []
