"""``python -m inventag`` in a child process, against moto, one test per exit code.

The child is started by ``tests/e2e/_moto_runner.py``, which seeds moto and then
runs the package through ``runpy`` exactly as ``python -m inventag`` does. These
tests prove what the in-process tests cannot: the real entry point, the real
``sys.exit`` codes, and what goes to stdout and what to stderr.
"""

import json

import pytest

from .conftest import FAST_SCAN

pytestmark = pytest.mark.e2e


def test_exit_0_default_run_writes_a_report_and_state(run_cli_subprocess):
    result = run_cli_subprocess(*FAST_SCAN, "--output-directory", "out")
    assert result.code == 0, result.text
    out = result.output_dir
    reports = list(out.glob("multi_account_bom_*.xlsx"))
    assert len(reports) == 1 and reports[0].stat().st_size > 5000
    assert len(list((out / "state").glob("state_*.json"))) == 1
    assert "Data exported to" in result.stdout


def test_exit_1_for_a_missing_accounts_file(run_cli_subprocess):
    result = run_cli_subprocess(
        "--accounts-file",
        "does-not-exist.json",
        *FAST_SCAN,
        "--output-directory",
        "out",
    )
    assert result.code == 1
    assert "does-not-exist.json" in result.text


def test_exit_2_for_compliance_standard_and_the_message_goes_to_stderr(
    run_cli_subprocess,
):
    result = run_cli_subprocess("--compliance-standard", "soc2")
    assert result.code == 2
    assert "inventag: error: --compliance-standard:" in result.stderr
    assert result.stdout == ""


def test_exit_2_for_an_unknown_option(run_cli_subprocess):
    result = run_cli_subprocess("--not-a-real-flag")
    assert result.code == 2
    assert "unrecognized arguments" in result.stderr


def test_exit_3_when_fail_on_tag_violations_finds_violations(run_cli_subprocess):
    result = run_cli_subprocess(
        "--template", "ci-pipeline", *FAST_SCAN, "--output-directory", "out"
    )
    assert result.code == 3, result.text
    assert list(result.output_dir.glob("*.xlsx")), "reports are written before exit 3"


def test_exit_4_when_a_security_group_rule_reaches_the_threshold(run_cli_subprocess):
    result = run_cli_subprocess(
        "--enable-security-analysis",
        "--risk-threshold",
        "CRITICAL",
        *FAST_SCAN,
        "--output-directory",
        "out",
    )
    assert result.code == 4, result.text
    assert "0.0.0.0/0" in result.text and "(critical)" in result.text
    assert list(result.output_dir.glob("*.xlsx"))


def test_audit_file_from_a_child_process_shows_no_blocked_call(
    run_cli_subprocess, tmp_path
):
    audit = tmp_path / "audit.json"
    result = run_cli_subprocess(
        *FAST_SCAN, "--output-directory", "out", "--audit-output", str(audit)
    )
    assert result.code == 0, result.text
    data = json.loads(audit.read_text())
    assert data["blocked_calls"] == 0 and data["allowed_calls"] > 20
