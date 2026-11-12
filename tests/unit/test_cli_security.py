"""End-to-end CLI security behaviour against moto (no real AWS)."""

import json
import os
import stat
import sys
import zipfile

import boto3
import pytest
from moto import mock_aws

import importlib
from inventag.core.cloud_bom_generator import (
    AccountCredentials,
    AccountSessionError,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")

FORMULA = '=HYPERLINK("http://evil.example","x")'


@pytest.fixture
def aws(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    old_umask = os.umask(0o022)
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="reports-bucket")
        s3.create_bucket(Bucket="data-bucket")
        s3.put_bucket_tagging(
            Bucket="data-bucket",
            Tagging={"TagSet": [{"Key": "Owner", "Value": FORMULA}]},
        )
        yield s3
    os.umask(old_umask)
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    import logging

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


@pytest.mark.parametrize(
    "flag",
    [
        ["--create-google-docs"],
        ["--per-account-reports"],
        ["--compliance-standard", "soc2"],
        ["--compliance-standard", "general"],
        ["--risk-threshold", "HIGH"],
        ["--disable-production-safety"],
        ["--cross-account-role", "bad role name!"],
        ["--cross-account-role", "arn:aws:iam::cross-account:role/X"],
    ],
)
def test_unimplemented_or_invalid_flags_fail_loudly(aws, flag, capsys):
    assert run_cli("--account-regions", "us-east-1", *flag) == 2
    assert "error" in capsys.readouterr().err
    assert not os.path.exists("bom_output")


def test_role_name_without_accounts_file_is_rejected(aws):
    assert (
        run_cli(
            "--account-regions", "us-east-1", "--cross-account-role", "InvenTagReadOnly"
        )
        == 2
    )


def test_full_run_private_files_formula_safe_upload_and_audit(aws, tmp_path):
    code = run_cli(
        "--account-regions",
        "us-east-1",
        "--create-excel",
        "--s3-bucket",
        "reports-bucket",
        "--s3-key-prefix",
        "bom/",
        "--audit-output",
        "audit/api-audit.json",
        "--log-file",
        "logs/run.log",
    )
    assert code == 0
    reports = list((tmp_path / "bom_output").glob("*.xlsx"))
    assert len(reports) == 1
    created = [
        reports[0],
        tmp_path / "audit" / "api-audit.json",
        tmp_path / "logs" / "run.log",
    ]
    created += list((tmp_path / "bom_output" / "state").glob("*.json"))
    for path in created:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, path
    assert stat.S_IMODE((tmp_path / "bom_output").stat().st_mode) == 0o700

    with zipfile.ZipFile(reports[0]) as z:
        sheets = [n for n in z.namelist() if n.startswith("xl/worksheets/")]
        xml = "".join(z.read(n).decode() for n in sheets)
        strings = (
            z.read("xl/sharedStrings.xml").decode()
            if "xl/sharedStrings.xml" in z.namelist()
            else ""
        )
    assert "<f>" not in xml and "<f " not in xml
    assert "HYPERLINK" in xml + strings  # the tag value is still in the report, as text

    keys = [o["Key"] for o in aws.list_objects_v2(Bucket="reports-bucket")["Contents"]]
    assert len(keys) == 1 and keys[0].startswith("bom/") and keys[0].endswith(".xlsx")
    assert (
        aws.head_object(Bucket="reports-bucket", Key=keys[0])["ServerSideEncryption"]
        == "AES256"
    )

    audit = json.loads((tmp_path / "audit" / "api-audit.json").read_text())
    assert audit["read_only_enforced"] is True
    assert audit["blocked_calls"] == 0
    assert audit["allowed_calls"] > 0
    put = [o for o in audit["operations"] if o["operation"] == "PutObject"]
    assert put and all(o["allowed"] for o in put)


def test_s3_upload_failure_fails_the_run(aws):
    code = run_cli(
        "--account-regions",
        "us-east-1",
        "--create-excel",
        "--s3-bucket",
        "no-such-bucket-inventag",
    )
    assert code == 1


def test_validate_operations_exit_codes(aws, capsys):
    assert run_cli("--validate-operations", "ec2:DescribeInstances") == 0
    assert (
        run_cli("--validate-operations", "ec2:DescribeInstances", "iam:CreateUser") == 1
    )
    assert "BLOCKED  iam:CreateUser" in capsys.readouterr().out


def test_validate_credentials_works(aws):
    """Used to fail always: it passed timeout= to a method without that parameter."""
    assert run_cli("--validate-credentials", "--account-regions", "us-east-1") == 0


def test_cross_account_role_arn_is_assumed(aws):
    iam = boto3.client("iam")
    iam.create_role(RoleName="InvenTagReadOnly", AssumeRolePolicyDocument="{}")
    code = run_cli(
        "--account-regions",
        "us-east-1",
        "--create-excel",
        "--cross-account-role",
        "arn:aws:iam::123456789012:role/InvenTagReadOnly",
    )
    assert code == 0


def test_role_name_with_accounts_file_builds_arn_per_account(
    aws, tmp_path, monkeypatch
):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "123456789012",
                        "account_name": "Moto",
                        "regions": ["us-east-1"],
                    }
                ]
            }
        )
    )
    assumed = []
    original = CloudBOMGenerator._assume_role_session

    def spy(self, role_arn, account_id, external_id=None):
        assumed.append(role_arn)
        return original(self, role_arn, account_id, external_id)

    monkeypatch.setattr(CloudBOMGenerator, "_assume_role_session", spy)
    code = run_cli(
        "--accounts-file",
        str(accounts),
        "--create-excel",
        "--cross-account-role",
        "InvenTagReadOnly",
    )
    assert code == 0
    assert assumed == ["arn:aws:iam::123456789012:role/InvenTagReadOnly"]


def test_account_mismatch_is_fatal_not_mislabelled(aws, tmp_path):
    """If credentials resolve to another account, do not scan it under this label."""
    config = MultiAccountConfig(
        accounts=[AccountCredentials(account_id="999999999999", regions=["us-east-1"])],
        cross_account_role_name="",
        output_directory=str(tmp_path / "out"),
        enable_state_management=False,
    )
    generator = CloudBOMGenerator(config)
    contexts = generator._establish_account_contexts()
    ctx = contexts["999999999999"]
    assert ctx.session is None
    assert "refusing to scan the wrong account" in ctx.processing_errors[0]


def test_explicit_bad_role_arn_does_not_fall_back_to_default(aws):
    config = MultiAccountConfig(accounts=[])
    generator = CloudBOMGenerator.__new__(CloudBOMGenerator)
    generator.config = config
    generator.logger = __import__("logging").getLogger("t")
    generator._default_identity = None
    with pytest.raises(AccountSessionError):
        generator._create_account_session(
            AccountCredentials(account_id="123456789012", role_arn="InvenTagReadOnly")
        )
