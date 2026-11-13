"""CLI: opt-in exit codes, conflicting flags, value checks, calls made by
validation-only modes. Moto only."""

import importlib
import json
import logging
import os
import sys

import boto3
import pytest
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")


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
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="a-bucket")
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


def accounts_file(tmp_path, accounts):
    path = tmp_path / "accounts.json"
    path.write_text(json.dumps({"accounts": accounts}))
    return str(path)


GOOD = {"account_id": "123456789012", "regions": ["us-east-1"]}
BROKEN = {
    "account_id": "999999999999",
    "profile_name": "no-such-profile",
    "regions": ["us-east-1"],
}
BASE = ["--create-excel", "--no-billing-validation"]


# ------------------------------------------------------------------ exit codes
def test_failed_account_exit_code_is_opt_in(aws, tmp_path):
    path = accounts_file(tmp_path, [GOOD, BROKEN])
    assert run_cli("--accounts-file", path, *BASE) == 0
    assert run_cli("--accounts-file", path, *BASE, "--fail-on-account-error") == 5
    # The report is written all the same.
    assert list((tmp_path / "bom_output").glob("*.xlsx"))


def test_fail_on_account_error_passes_when_all_accounts_work(aws, tmp_path):
    path = accounts_file(tmp_path, [GOOD])
    assert run_cli("--accounts-file", path, *BASE, "--fail-on-account-error") == 0


def test_every_account_failing_is_still_exit_1(aws, tmp_path):
    path = accounts_file(tmp_path, [BROKEN])
    assert run_cli("--accounts-file", path, *BASE, "--fail-on-account-error") == 1


def test_empty_result_exit_code_is_opt_in(aws, tmp_path, monkeypatch):
    from inventag.core import cloud_bom_generator as cbg

    monkeypatch.setattr(
        cbg.CloudBOMGenerator,
        "_discover_account_resources_inner",
        lambda self, account_id, context: [],
    )
    path = accounts_file(tmp_path, [GOOD])
    assert run_cli("--accounts-file", path, *BASE) == 0
    assert run_cli("--accounts-file", path, *BASE, "--fail-if-empty") == 6


def test_opt_in_exit_code(aws):
    from types import SimpleNamespace

    log = logging.getLogger("test")
    args = SimpleNamespace(fail_on_account_error=True, fail_if_empty=True)
    failed = {"failed_accounts": [{"account_id": "1"}]}
    empty = {"bom_generation": {"total_resources": 0}}
    assert cli_main._opt_in_exit_code(args, {**failed, **empty}, log) == 5
    assert cli_main._opt_in_exit_code(args, empty, log) == 6
    assert (
        cli_main._opt_in_exit_code(
            args, {"bom_generation": {"total_resources": 3}}, log
        )
        == 0
    )
    off = SimpleNamespace(fail_on_account_error=False, fail_if_empty=False)
    assert cli_main._opt_in_exit_code(off, {**failed, **empty}, log) == 0


# ------------------------------------------------------------ conflicting flags
@pytest.mark.parametrize(
    "flags",
    [
        ["--accounts-file", "a.json", "--accounts-prompt"],
        [
            "--accounts-file",
            "a.json",
            "--cross-account-role",
            "arn:aws:iam::123456789012:role/R",
        ],
        ["--s3-bucket", "a-bucket", "--s3-kms-key-id", "alias/k"],
        ["--resume", "--disable-state-management"],
    ],
)
def test_conflicting_flags_stop_with_exit_2(aws, flags, capsys):
    assert run_cli(*flags) == 2
    assert "error" in capsys.readouterr().err
    assert not os.path.exists("bom_output")


@pytest.mark.parametrize(
    "flags",
    [
        ["--max-concurrent-accounts", "0"],
        ["--account-processing-timeout", "0"],
        ["--account-processing-timeout", "59"],
        ["--credential-timeout", "0"],
        ["--resume-max-age-hours", "0"],
        ["--resume-max-age-hours", "200"],
        ["--account-tags", "[1, 2]"],
        ["--account-tags", "{not json"],
    ],
)
def test_out_of_range_values_stop_with_exit_1(aws, flags):
    assert run_cli("--account-regions", "us-east-1", *flags) == 1
    assert not os.path.exists("bom_output")


@pytest.mark.parametrize("value", ["abc", "-1"])
def test_retention_values_are_checked_by_argparse(aws, value):
    assert run_cli("--state-retention-days", value) == 2


def test_new_options_reach_the_config(aws, tmp_path):
    parser = cli_main.create_parser()
    args = parser.parse_args(
        [
            "--accounts-file",
            accounts_file(tmp_path, [{"account_id": "123456789012"}]),
            "--resume",
            "--resume-max-age-hours",
            "6",
            "--state-retention-days",
            "none",
            "--state-max-snapshots",
            "0",
            "--max-concurrent-accounts",
            "2",
            "--account-processing-timeout",
            "120",
        ]
    )
    config = cli_main.create_multi_account_config(args)
    assert config.resume is True and config.resume_max_age_hours == 6
    assert config.state_retention_days is None
    assert config.state_max_snapshots is None
    assert config.max_concurrent_accounts == 2
    assert config.account_processing_timeout == 120
    # Without regions in the file, each account's regions are looked up with
    # that account's own credentials during the scan, not here.
    assert config.accounts[0].regions == []
    defaults = cli_main.create_multi_account_config(
        parser.parse_args(["--accounts-file", str(tmp_path / "accounts.json")])
    )
    assert defaults.resume is False
    assert (defaults.state_retention_days, defaults.state_max_snapshots) == (30, 100)


def test_google_output_alone_gives_no_missing_format_warning():
    from types import SimpleNamespace

    from inventag.cli.config_validator import ConfigValidator

    args = cli_main.create_parser().parse_args(["--create-google-sheets"])
    result = ConfigValidator().validate_cli_arguments(args)
    assert not any("No output format" in w for w in result.warnings)
    args = SimpleNamespace(**{**vars(args), "create_google_sheets": False})
    result = ConfigValidator().validate_cli_arguments(args)
    assert any("No output format" in w for w in result.warnings)


# --------------------------------------------- AWS calls of validation modes
def _audit(tmp_path):
    return json.loads((tmp_path / "audit.json").read_text())


def test_validate_config_only_makes_no_aws_call(aws, tmp_path):
    path = accounts_file(tmp_path, [GOOD])
    code = run_cli(
        "--validate-config-only",
        "--accounts-file",
        path,
        "--audit-output",
        "audit.json",
    )
    assert code == 0
    assert _audit(tmp_path)["total_calls"] == 0


def test_validate_config_with_accounts_file_makes_no_aws_call(aws, tmp_path):
    path = accounts_file(tmp_path, [{"account_id": "123456789012"}])
    code = run_cli(
        "--validate-config", "--accounts-file", path, "--audit-output", "audit.json"
    )
    assert code == 0
    assert _audit(tmp_path)["total_calls"] == 0


def test_validate_credentials_makes_only_read_calls(aws, tmp_path):
    code = run_cli(
        "--validate-credentials",
        "--account-regions",
        "us-east-1",
        "--audit-output",
        "audit.json",
    )
    assert code == 0
    audit = _audit(tmp_path)
    assert audit["blocked_calls"] == 0
    assert not os.path.exists("bom_output/state")
    assert {o["service"] for o in audit["operations"]} <= {
        "sts",
        "ec2",
        "iam",
        "s3",
        "config",
        "resource-groups",
    }


@pytest.mark.parametrize(
    "flags",
    [
        ["--enable-production-safety"],
        ["--security-validation"],
        ["--enforce-read-only"],
        ["--hide-fallback-resources"],
        ["--enable-state-management"],
        ["--enable-delta-detection"],
    ],
)
def test_legacy_flags_are_still_accepted(flags):
    cli_main.create_parser().parse_args(flags)
