"""No writer touches the process umask (register row A-14).

InvenTag runs worker threads. Setting the umask to 0 for a moment to learn it
would let a file that another thread creates in that moment be 0666.
"""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import inventag
import inventag.reporting as reporting
from inventag.compliance.checker import ComprehensiveTagComplianceChecker
from inventag.reporting.configuration_manager import (
    ConfigurationManager,
    ConfigurationSet,
)
from inventag.reporting.template_framework import DocumentTemplate, TemplateManager
from inventag.templating.runner import _write_json_atomically

# cli/safety.py sets the CLI's umask (077) once at start-up, before any thread.
ALLOWED = {"cli/safety.py"}


@pytest.fixture
def umask_calls(monkeypatch):
    import os

    calls = []
    real = os.umask

    def recording(mask):
        calls.append(mask)
        return real(mask)

    monkeypatch.setattr(os, "umask", recording)
    return calls


def _checker_text(tmp_path, monkeypatch):
    class NoWord:
        def __init__(self, *args, **kwargs):
            pass

        def generate_word_document(self, *args, **kwargs):
            raise ImportError("python-docx is not installed")

    monkeypatch.setattr(reporting, "DocumentGenerator", NoWord)
    checker = ComprehensiveTagComplianceChecker(regions=["us-east-1"])
    bom = SimpleNamespace(resources=[], compliance_details={"compliance_percentage": 1})
    checker._generate_word_bom(bom, str(tmp_path / "bom.docx"))
    return tmp_path / "bom.txt"


def _runner_json(tmp_path, monkeypatch):
    _write_json_atomically(str(tmp_path / "c.json"), {"a": 1})
    return tmp_path / "c.json"


def _saved_configuration(tmp_path, monkeypatch):
    ConfigurationManager(str(tmp_path)).save_configuration(
        ConfigurationSet(name="c"), str(tmp_path / "config.json")
    )
    return tmp_path / "config.json"


def _saved_template(tmp_path, monkeypatch):
    TemplateManager().save_template(
        DocumentTemplate(name="t"), str(tmp_path / "template.yaml")
    )
    return tmp_path / "template.yaml"


WRITERS = [
    pytest.param(_checker_text, id="checker-text-report"),
    pytest.param(_runner_json, id="tag-compliance-json"),
    pytest.param(_saved_configuration, id="saved-configuration"),
    pytest.param(_saved_template, id="saved-template"),
]


@pytest.mark.parametrize("write", WRITERS)
def test_writer_never_calls_os_umask(write, umask_calls, tmp_path, monkeypatch):
    path = write(tmp_path, monkeypatch)
    assert path.exists()
    assert umask_calls == [], f"os.umask was called with {umask_calls}"


def test_no_module_under_inventag_calls_os_umask():
    root = Path(inventag.__file__).parent
    pattern = re.compile(r"\bos\.umask\s*\(")
    found = []
    for module in sorted(root.rglob("*.py")):
        relative = module.relative_to(root).as_posix()
        if relative in ALLOWED:
            continue
        for number, line in enumerate(module.read_text("utf-8").splitlines(), 1):
            if pattern.search(line):
                found.append(f"{relative}:{number}")
    assert found == []
