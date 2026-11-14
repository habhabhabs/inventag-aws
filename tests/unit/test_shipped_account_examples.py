"""Every accounts-file example that ships in examples/ loads through the real
loader with no error and no warning. A copy is made with mode 0600, as the
file-mode warning asks of a file with keys; the examples are meant to be copied."""

import logging
import shutil
from pathlib import Path

import pytest

from inventag.cli.main import load_configuration_file

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FILES = sorted(
    [
        *EXAMPLES.glob("accounts_*.json"),
        *EXAMPLES.glob("accounts_*.yaml"),
        *EXAMPLES.glob("accounts-*.json"),
        *EXAMPLES.glob("cicd_accounts_*.yaml"),
    ]
)


def test_the_examples_are_found():
    assert len(FILES) >= 12


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_example_loads_with_no_warning_and_no_error(path, tmp_path, caplog):
    copy = tmp_path / path.name
    shutil.copy(path, copy)
    copy.chmod(0o600)
    with caplog.at_level(logging.INFO):
        config = load_configuration_file(str(copy), "accounts")
    assert config["accounts"]
    problems = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert problems == []
