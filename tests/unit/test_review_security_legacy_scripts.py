"""Release-gate review: the legacy scripts run under the read-only guard.

Before v1.2.0 these scripts installed no guard, and
``scripts/legacy/aws_resource_inventory.py --s3-bucket`` wrote through an
unguarded, unencrypted ``put_object``. Now each script installs the guard;
the inventory script's upload is the one allowed write.
"""

import os
import runpy
import stat
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import (
    ReadOnlyViolationError,
    get_installed_guard,
    uninstall_global_guard,
)

LEGACY = Path(__file__).resolve().parents[2] / "scripts" / "legacy"


@pytest.fixture
def aws_env(monkeypatch, tmp_path):
    for k, v in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_EC2_METADATA_DISABLED": "true",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    old_umask = os.umask(0o022)
    os.umask(old_umask)
    uninstall_global_guard()
    yield
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    os.umask(old_umask)


def _run(script, argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(script), *argv])
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        assert exc.code in (0, None), exc.code


def test_inventory_script_uploads_encrypted_under_the_guard(aws_env, monkeypatch):
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="reports")
        s3.create_bucket(Bucket="other")
        _run(
            LEGACY / "aws_resource_inventory.py",
            [
                "--regions",
                "us-east-1",
                "--s3-bucket",
                "reports",
                "--s3-key",
                "inv/x.json",
            ],
            monkeypatch,
        )
        guard = get_installed_guard()
        assert guard is not None, "the script ran without the read-only guard"
        head = boto3.client("s3", region_name="us-east-1").head_object(
            Bucket="reports", Key="inv/x.json"
        )
        assert head["ServerSideEncryption"] == "AES256"
        allowed_writes = {
            (op["service"], op["operation"])
            for op in guard.audit_report()["operations"]
            if op["allowed"]
            and not op["operation"].startswith(("List", "Describe", "Get", "Head"))
        }
        assert allowed_writes <= {("s3", "PutObject")}, allowed_writes
        # Any other client created after the script is still read-only.
        with pytest.raises(ReadOnlyViolationError):
            boto3.client("s3", region_name="us-east-1").put_object(
                Bucket="other", Key="k", Body=b"x"
            )
    written = [p for p in Path.cwd().glob("aws_resources_*.json")]
    assert written and stat.S_IMODE(written[0].stat().st_mode) == 0o600


def test_inventory_script_refuses_an_invalid_bucket_name(aws_env, monkeypatch):
    with mock_aws():
        monkeypatch.setattr(
            sys,
            "argv",
            ["x", "--regions", "us-east-1", "--s3-bucket", "../evil", "--s3-key", "k"],
        )
        with pytest.raises(SystemExit) as exc:
            runpy.run_path(
                str(LEGACY / "aws_resource_inventory.py"), run_name="__main__"
            )
        assert exc.value.code == 1
