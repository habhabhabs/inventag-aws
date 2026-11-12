"""S3 report upload: encryption, no public ACLs, lifecycle merge (not clobber)."""

import boto3
import pytest
from moto import mock_aws

from inventag.core.cicd_integration import CICDIntegration, S3UploadConfig
from inventag.core.s3_upload import (
    LIFECYCLE_RULE_ID,
    S3UploadError,
    build_object_key,
    ensure_lifecycle_rule,
    merge_lifecycle_rule,
    upload_files,
)
from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    install_global_guard,
    uninstall_global_guard,
)

EXISTING_RULE = {
    "ID": "keep-me",
    "Status": "Enabled",
    "Filter": {"Prefix": "logs/"},
    "Expiration": {"Days": 7},
}


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="reports")
        client.put_bucket_lifecycle_configuration(
            Bucket="reports", LifecycleConfiguration={"Rules": [EXISTING_RULE]}
        )
        yield client


def test_merge_keeps_other_rules_and_replaces_own():
    rules = merge_lifecycle_rule([EXISTING_RULE], "bom/", 30)
    assert [r["ID"] for r in rules] == ["keep-me", LIFECYCLE_RULE_ID]
    rules = merge_lifecycle_rule(rules, "bom/", 60)
    assert [r["ID"] for r in rules] == ["keep-me", LIFECYCLE_RULE_ID]
    assert rules[-1]["Expiration"] == {"Days": 60}
    assert rules[-1]["Filter"] == {"Prefix": "bom/"}


def test_ensure_lifecycle_rule_does_not_clobber_existing_rules(s3):
    assert ensure_lifecycle_rule(s3, "reports", "bom", 30) is True
    ids = [
        r["ID"]
        for r in s3.get_bucket_lifecycle_configuration(Bucket="reports")["Rules"]
    ]
    assert sorted(ids) == sorted(["keep-me", LIFECYCLE_RULE_ID])


def test_upload_is_encrypted_and_private_under_guard(s3, tmp_path):
    report = tmp_path / "bom.xlsx"
    report.write_bytes(b"report")
    uninstall_global_guard()
    install_global_guard(ReadOnlyGuard())
    try:
        uploader = boto3.client("s3", region_name="us-east-1")
        result = upload_files(
            uploader, [str(report)], "reports", "bom/", timestamp="t1"
        )
    finally:
        uninstall_global_guard()
    assert result["errors"] == []
    key = result["uploaded"][0]["key"]
    assert key == "bom/t1/bom.xlsx"
    head = s3.head_object(Bucket="reports", Key=key)
    assert head["ServerSideEncryption"] == "AES256"
    grants = s3.get_object_acl(Bucket="reports", Key=key)["Grants"]
    assert not any("AllUsers" in str(g.get("Grantee", {})) for g in grants)
    # Uploading never touched the lifecycle configuration.
    rules = s3.get_bucket_lifecycle_configuration(Bucket="reports")["Rules"]
    assert [r["ID"] for r in rules] == ["keep-me"]


def test_public_read_is_refused(s3, tmp_path):
    report = tmp_path / "bom.xlsx"
    report.write_bytes(b"x")
    with pytest.raises(S3UploadError):
        upload_files(s3, [str(report)], "reports", public_read=True)


def test_invalid_bucket_and_missing_file(s3, tmp_path):
    with pytest.raises(S3UploadError):
        upload_files(s3, [], "Not_A_Bucket")
    result = upload_files(s3, [str(tmp_path / "missing.xlsx")], "reports")
    assert result["uploaded"] == [] and len(result["errors"]) == 1


def test_object_key_cannot_traverse():
    assert build_object_key("../a/./b/", "t", "../../x.xlsx") == "a/b/t/x.xlsx"


def test_cicd_integration_lifecycle_is_opt_in_and_merged(s3, tmp_path):
    report = tmp_path / "bom.docx"
    report.write_bytes(b"x")
    assert S3UploadConfig(bucket_name="reports").lifecycle_days == 0
    default = CICDIntegration(s3_config=S3UploadConfig(bucket_name="reports"))
    assert default._upload_documents_to_s3([str(report)])
    assert [
        r["ID"]
        for r in s3.get_bucket_lifecycle_configuration(Bucket="reports")["Rules"]
    ] == ["keep-me"]

    opted_in = CICDIntegration(
        s3_config=S3UploadConfig(
            bucket_name="reports", key_prefix="bom", lifecycle_days=30
        )
    )
    opted_in._upload_documents_to_s3([str(report)])
    ids = [
        r["ID"]
        for r in s3.get_bucket_lifecycle_configuration(Bucket="reports")["Rules"]
    ]
    assert sorted(ids) == sorted(["keep-me", LIFECYCLE_RULE_ID])


def test_cicd_artifacts_written_private(tmp_path, monkeypatch):
    from inventag.core.cicd_integration import CICDResult

    integration = CICDIntegration(artifacts_dir=str(tmp_path / "artifacts"))
    integration._generate_cicd_artifacts({}, CICDResult(success=True))
    summary = tmp_path / "artifacts" / "pipeline_summary.json"
    assert summary.exists()
    assert oct(summary.stat().st_mode & 0o777) == "0o600"


def test_webhooks_require_https():
    from inventag.core.cicd_integration import NotificationConfig

    integration = CICDIntegration(
        notification_config=NotificationConfig(
            slack_webhook_url="http://hooks.example/x"
        )
    )
    content = {
        "title": "t",
        "status": "SUCCESS",
        "compliance_gate": "PASSED",
        "summary": {},
        "document_links": {},
    }
    with pytest.raises(ValueError):
        integration._send_slack_notification(content)
