"""The moto session setup must not break a run where moto is not installed.

The job "Tests of the workflow code" installs pytest and PyYAML only. A listed
test file that only mentions the word in its text (a test of a workflow that
installs it) must not make conftest import it.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RUNNER = """
import sys
import pytest


class BlockMoto:
    def find_spec(self, name, path=None, target=None):
        if name == "moto" or name.startswith("moto."):
            raise ModuleNotFoundError("blocked: moto is not installed")
        return None


sys.meta_path.insert(0, BlockMoto())
sys.exit(pytest.main(["-q", "-p", "no:cacheprovider", sys.argv[1]]))
"""


def test_a_run_without_moto_installed_does_not_fail_at_setup(tmp_path):
    # The file below says "moto" in its text but imports nothing from it.
    mentions = ROOT / "tests" / "unit" / "test_conftest_moto_probe_tmp.py"
    mentions.write_text(
        'def test_it():\n    assert "moto" in "a workflow installs moto"\n',
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", RUNNER, str(mentions)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        mentions.unlink()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
