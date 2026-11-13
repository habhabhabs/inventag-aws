"""The legacy tag compliance script still uploads with --s3-bucket.

ComprehensiveTagComplianceChecker.upload_to_s3 refuses to write unless the
caller passes allow_write=True. The legacy script's --s3-bucket option is the
user's explicit request for that one write, so the script must pass it.
"""

import json
import runpy
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "legacy"
    / "tag_compliance_checker.py"
)


@pytest.fixture
def aws_env(monkeypatch):
    for k, v in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AWS_PROFILE", raising=False)


def test_s3_bucket_option_uploads_the_results(tmp_path, monkeypatch, aws_env):
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps(
            [
                {
                    "service": "S3",
                    "type": "Bucket",
                    "id": "b1",
                    "arn": "arn:aws:s3:::b1",
                    "region": "us-east-1",
                    "tags": {"Owner": "a"},
                }
            ]
        )
    )
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="reports")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                str(SCRIPT),
                "--input",
                str(inventory),
                "--format",
                "json",
                "--s3-bucket",
                "reports",
                "--s3-key",
                "out/compliance.json",
                "--no-color",
            ],
        )
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as exc:  # the script may exit 0 at the end
            assert exc.code in (0, None)
        body = (
            boto3.client("s3", region_name="us-east-1")
            .get_object(Bucket="reports", Key="out/compliance.json")["Body"]
            .read()
        )
    assert "summary" in json.loads(body)
