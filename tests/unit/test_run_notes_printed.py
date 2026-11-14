"""The run notes of a result reach the console, once, as warnings.

Moto only; the generator is replaced by a fake that returns a ready result,
so the test is fast. The console logger of InvenTag writes to stdout (see
``cli/logging_setup.py``), so the lines are looked for in stdout and stderr
together.
"""

import importlib
import logging
import re
import sys

import boto3
import pytest
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")

NOTE_1 = "Account 111111111111: every listing was denied; nothing was read."
NOTE_2 = "Not read: sqs in us-east-1 (throttled)."


@pytest.fixture
def aws(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-creds"))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1")
        yield
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def run_cli(*args):
    old_argv = sys.argv
    sys.argv = ["inventag", *args]
    try:
        cli_main.main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old_argv


def fake_generator(result):
    class FakeGenerator:
        def __init__(self, config):
            pass

        def generate_comprehensive_bom(self, **kwargs):
            return result

    return FakeGenerator


def base_result(**extra):
    result = {
        "success": True,
        "bom_generation": {"generated_files": []},
        "failed_accounts": [],
        "processing_statistics": {
            "total_accounts": 1,
            "total_resources": 3,
            "processing_time_seconds": 1.0,
        },
    }
    result.update(extra)
    return result


def run_with(monkeypatch, capsys, result, *extra):
    monkeypatch.setattr(cli_main, "CloudBOMGenerator", fake_generator(result))
    code = run_cli("--create-excel", "--no-billing-validation", *extra)
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_every_run_note_is_printed_once_as_a_warning_after_the_summary(
    aws, monkeypatch, capsys
):
    code, text = run_with(monkeypatch, capsys, base_result(run_notes=[NOTE_1, NOTE_2]))
    assert code == 0
    for note in (NOTE_1, NOTE_2):
        lines = [line for line in text.splitlines() if note in line]
        assert len(lines) == 1, f"{note!r} printed {len(lines)} times:\n{text}"
        assert " - WARNING - " in lines[0]
    assert text.index(NOTE_1) < text.index(NOTE_2)


def test_run_notes_come_after_the_processing_summary(aws, monkeypatch, capsys):
    code, text = run_with(
        monkeypatch, capsys, base_result(run_notes=[NOTE_1]), "--verbose"
    )
    assert code == 0
    assert text.index("Processing summary") < text.index(NOTE_1)


def test_a_result_without_notes_prints_nothing_new(aws, monkeypatch, capsys):
    code, text = run_with(monkeypatch, capsys, base_result(run_notes=[]))
    assert code == 0
    assert "note" not in text.lower()
    _, text_missing = run_with(monkeypatch, capsys, base_result())
    assert re.sub(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+", "T", text) == re.sub(
        r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+", "T", text_missing
    )


def test_failed_account_block_is_unchanged_and_not_repeated(aws, monkeypatch, capsys):
    failed = [
        {
            "account_id": "222222222222",
            "account_name": "prod",
            "errors": ["The AWS session could not be created."],
        }
    ]
    notes = [
        "1 of 1 account(s) were not scanned, so this report does not include them:",
        "222222222222 (prod): The AWS session could not be created.",
        NOTE_2,
    ]
    code, text = run_with(
        monkeypatch, capsys, base_result(failed_accounts=failed, run_notes=notes)
    )
    assert code == 0  # exit code stays as in v1.2.0 (5 only with the opt-in flag)
    assert "1 account(s) were not scanned, or only partly." in text
    assert text.count("222222222222 (prod)") == 1
    assert text.count(NOTE_2) == 1
    code, _ = run_with(
        monkeypatch,
        capsys,
        base_result(failed_accounts=failed, run_notes=notes),
        "--fail-on-account-error",
    )
    assert code == 5
