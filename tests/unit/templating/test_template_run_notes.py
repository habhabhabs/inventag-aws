"""A template report names what was not scanned (register row A-07).

The default report prints the run notes (accounts that failed and why). A report
made with ``--template`` must say the same, in the Summary of the workbook and
in the Summary of the Word document, and must stay unchanged when there is
nothing to say.
"""

import logging
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from docx import Document
from openpyxl import load_workbook

from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    BOMProcessingConfig,
    MultiAccountConfig,
)
from inventag.templating.runner import TemplatedCloudBOMGenerator, TemplateRun

FAILED_ID = "222222222222"
REASON = "AccessDenied: not authorized to perform sts:AssumeRole"

RESOURCE = {
    "service": "S3",
    "resource_type": "Bucket",
    "resource_id": "bucket-one",
    "arn": "arn:aws:s3:::bucket-one",
    "region": "us-east-1",
    "source_account_id": "111111111111",
    "tags": {},
}


def _generator(registry, tmp_path, failed):
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
    contexts = {
        "111111111111": AccountContext(
            credentials=AccountCredentials(
                account_id="111111111111", account_name="good"
            ),
            session=MagicMock(),
            caller_identity={},
        )
    }
    if failed:
        contexts[FAILED_ID] = AccountContext(
            credentials=AccountCredentials(account_id=FAILED_ID, account_name="bad"),
            session=None,
            caller_identity={},
            processing_errors=[REASON],
        )
    generator.account_contexts = contexts
    return generator


def _generate(generator):
    out = generator._generate_bom_documents([dict(RESOURCE)], {}, ["excel", "word"])
    assert out["success"], out
    files = {path.rsplit(".", 1)[1]: path for path in out["generated_files"]}
    return files["xlsx"], files["docx"]


def _workbook_text(path):
    wb = load_workbook(path)
    return {
        ws.title: [str(c.value) for row in ws.iter_rows() for c in row if c.value]
        for ws in wb.worksheets
    }


def _word_text(path):
    return [p.text for p in Document(path).paragraphs]


def test_failed_account_and_reason_are_in_the_workbook_and_the_document(
    registry, tmp_path
):
    xlsx, docx = _generate(_generator(registry, tmp_path, failed=True))

    cells = _workbook_text(xlsx)["Summary"]
    assert any(FAILED_ID in c and REASON in c for c in cells), cells
    paragraphs = _word_text(docx)
    assert any(FAILED_ID in p and REASON in p for p in paragraphs), paragraphs


def test_notes_add_no_sheet_and_the_default_report_wording_is_used(registry, tmp_path):
    clean_x, _ = _generate(_generator(registry, tmp_path / "a", failed=False))
    noted_x, _ = _generate(_generator(registry, tmp_path / "b", failed=True))
    assert list(_workbook_text(noted_x)) == list(_workbook_text(clean_x))
    assert "Run notes" in _workbook_text(noted_x)["Summary"]
    assert "Run notes" not in _workbook_text(clean_x)["Summary"]


def test_notes_from_the_generator_pass_through_unchanged(registry, tmp_path):
    """Whatever list ``_run_notes`` returns (lead A adds lines) is shown."""
    generator = _generator(registry, tmp_path, failed=False)
    generator._run_notes = lambda: ["Not read: sqs in us-east-1 (throttled)"]
    xlsx, docx = _generate(generator)
    assert "Not read: sqs in us-east-1 (throttled)" in _workbook_text(xlsx)["Summary"]
    assert "Not read: sqs in us-east-1 (throttled)" in _word_text(docx)


def test_no_notes_means_no_run_notes_heading_in_the_document(registry, tmp_path):
    _, docx = _generate(_generator(registry, tmp_path, failed=False))
    assert "Run notes" not in _word_text(docx)
