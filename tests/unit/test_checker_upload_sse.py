"""The checker's S3 upload asks for SSE-S3, which the published read-only
policy's optional PutObject statement requires (security review B2)."""

import boto3
from moto import mock_aws

from inventag.compliance.checker import ComprehensiveTagComplianceChecker


def test_upload_is_server_side_encrypted(monkeypatch):
    for k, v in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(k, v)
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="reports")
        checker = ComprehensiveTagComplianceChecker(
            regions=["us-east-1"], policy={"required_tags": ["Owner"]}
        )
        checker.compliance_results["summary"] = {"total_resources": 0}
        checker.upload_to_s3("reports", "out.json", allow_write=True)
        head = s3.head_object(Bucket="reports", Key="out.json")
        assert head["ServerSideEncryption"] == "AES256"
