"""``--version``, ``python -m inventag`` and shipped templates."""

import subprocess
import sys
from pathlib import Path

import pytest

from inventag._version import __version__


def _run(*args):
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, timeout=120
    )


def test_version_flag_prints_the_package_version():
    result = _run("-m", "inventag", "--version")
    assert result.returncode == 0
    assert result.stdout.strip() == f"inventag {__version__}"


def test_module_entry_point_lists_templates():
    result = _run("-m", "inventag", "templates", "list")
    assert result.returncode == 0
    assert "standard-bom" in result.stdout


def test_builtin_templates_live_inside_the_package():
    import inventag

    builtin = Path(inventag.__file__).parent / "templating" / "builtin"
    assert (builtin / "standard-bom.yaml").is_file()


def test_version_sources_agree():
    import json

    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / "version.json").read_text(encoding="utf-8"))
    assert data["version"] == __version__
