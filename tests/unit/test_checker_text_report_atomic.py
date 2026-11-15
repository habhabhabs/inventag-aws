"""The checker's plain-text report fallback never leaves a half-written file:
a write that fails keeps the old file and leaves no temporary file behind."""

from types import SimpleNamespace

import pytest

import inventag.reporting as reporting
from inventag.compliance.checker import ComprehensiveTagComplianceChecker


class NoWordSupport:
    def __init__(self, *args, **kwargs):
        pass

    def generate_word_document(self, *args, **kwargs):
        raise ImportError("python-docx is not installed")


@pytest.fixture
def checker(monkeypatch):
    monkeypatch.setattr(reporting, "DocumentGenerator", NoWordSupport)
    return ComprehensiveTagComplianceChecker(regions=["us-east-1"])


def test_text_report_is_written_when_word_support_is_missing(checker, tmp_path):
    bom = SimpleNamespace(
        resources=[{"service": "S3"}],
        compliance_details={"compliance_percentage": 50},
    )
    target = tmp_path / "bom.docx"
    checker._generate_word_bom(bom, str(target))
    text = (tmp_path / "bom.txt").read_text()
    assert "Total Resources: 1" in text and "S3: 1" in text
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bom.txt"]


def test_failed_text_report_keeps_the_old_file_and_leaves_no_temp_file(
    checker, tmp_path
):
    old = tmp_path / "bom.txt"
    old.write_text("old report")
    bom = SimpleNamespace(resources=[], compliance_details={})  # no percentage
    with pytest.raises(KeyError):
        checker._generate_word_bom(bom, str(tmp_path / "bom.docx"))
    assert old.read_text() == "old report"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bom.txt"]
