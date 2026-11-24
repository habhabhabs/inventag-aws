"""Shared helpers of the policy command tests (P4): run the command in process,
copy the golden policies, and stand in for the modules of P2 and P3."""

import io
import shutil
import sys
import types
from pathlib import Path

GOLDEN = Path(__file__).resolve().parent / "golden"
NOW = "2026-11-20"


def run(argv):
    """(exit code, stdout, stderr) of ``inventag policy <argv>``."""
    from inventag.policy import cli

    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(map(str, argv)), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def policies_dir(tmp_path, *names):
    """A policy folder holding the named golden policy files."""
    folder = tmp_path / "policies"
    folder.mkdir(exist_ok=True)
    for name in names:
        shutil.copy(GOLDEN / "policies" / name, folder / name)
    return folder


def snapshot_file(tmp_path, name="s1.json"):
    target = tmp_path / name
    shutil.copy(GOLDEN / name, target)
    return target


def stub(monkeypatch, name, **attrs):
    """Install ``inventag.policy.<name>`` as a module with ``attrs``."""
    module = types.ModuleType(f"inventag.policy.{name}")
    module.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, f"inventag.policy.{name}", module)
    return module
