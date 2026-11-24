"""UX plan U1, part A: a bare ``inventag`` prints the help page and starts no
scan (exit code 2). Every test asserts the exit code."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.e2e.conftest import restored_process_state

BARE_LINE = (
    "inventag: error: no option was given, so no scan was started. For the scan "
    "that a bare 'inventag' ran before v1.5.0, run: inventag --create-excel\n"
)


def _main(argv, capsys, monkeypatch):
    from inventag.cli.main import main

    monkeypatch.setattr(sys, "argv", ["inventag", *argv])
    code = 0
    with restored_process_state():
        try:
            main()
        except SystemExit as stop:
            code = 0 if stop.code is None else stop.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_bare_inventag_prints_the_help_and_exits_2(capsys, monkeypatch, tmp_path):
    import boto3

    def refuse(*args, **kwargs):
        raise AssertionError("a bare inventag must not open an AWS session")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(boto3, "Session", refuse)
    monkeypatch.setattr(boto3, "client", refuse)
    code, out, err = _main([], capsys, monkeypatch)
    assert code == 2
    assert err == BARE_LINE
    help_code, help_out, help_err = _main(["--help"], capsys, monkeypatch)
    assert help_code == 0 and help_err == ""
    assert out == help_out
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("stdin", ["pipe", "closed"])
def test_bare_inventag_in_a_child_process_ignores_the_environment(tmp_path, stdin):
    env = dict(os.environ)
    env.update(
        AWS_PROFILE="someone",
        AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE",
        AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        AWS_DEFAULT_REGION="us-east-1",
        INVENTAG_ANYTHING="1",
    )
    root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [root, env.get("PYTHONPATH")]))
    stdin_kwargs = {"input": ""} if stdin == "pipe" else {"stdin": subprocess.DEVNULL}
    result = subprocess.run(
        [sys.executable, "-m", "inventag"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=120,
        **stdin_kwargs,
    )
    assert result.returncode == 2
    assert result.stderr == BARE_LINE
    assert result.stdout.startswith("usage: inventag")
    assert list(tmp_path.iterdir()) == []


def test_help_still_exits_0(capsys, monkeypatch):
    code, out, err = _main(["--help"], capsys, monkeypatch)
    assert code == 0 and out.startswith("usage: inventag")


def test_bare_policy_still_exits_2(capsys, monkeypatch):
    code, out, err = _main(["policy"], capsys, monkeypatch)
    assert code == 2
    assert "no option was given" not in err


def test_the_exit_code_list_names_the_bare_run():
    from inventag import exit_codes

    assert "or no option at all" in " ".join(exit_codes.__doc__.split())


# ------------------------------------------------- unchanged neighbours (moto)
@pytest.mark.e2e
def test_any_option_still_scans_and_defaults_to_excel(tmp_path):
    from tests.unit.finops.conftest import run_scan

    scan = run_scan(tmp_path)
    assert scan.code == 0, scan.stdout + scan.stderr
    assert "No output formats specified. Defaulting to Excel format." in (
        scan.stdout + scan.stderr
    )
    assert sorted(scan.out.glob("*.xlsx"))


@pytest.mark.e2e
def test_create_excel_gives_the_old_run_without_the_default_line(tmp_path):
    from tests.unit.finops.conftest import run_scan

    scan = run_scan(tmp_path, "--create-excel")
    assert scan.code == 0, scan.stdout + scan.stderr
    assert "Defaulting to Excel" not in scan.stdout + scan.stderr
    (xlsx,) = sorted(scan.out.glob("*.xlsx"))
    assert xlsx.name.startswith("multi_account_bom_")
