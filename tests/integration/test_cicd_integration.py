#!/usr/bin/env python3
"""
End-to-end CI/CD integration test against moto (no real AWS).

Runs the real CloudBOMGenerator (discovery -> Excel/JSON) through
CICDIntegration.execute_pipeline_integration (gate, encrypted S3 upload,
artifacts, Prometheus metrics) under the read-only guard.
"""

import json

import boto3
import pytest
from moto import mock_aws

from inventag.core.cicd_integration import (
    CICDIntegration,
    ComplianceGateConfig,
    S3UploadConfig,
)
from inventag.core.cloud_bom_generator import (
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    install_global_guard,
    uninstall_global_guard,
)


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="reports")
        s3.create_bucket(Bucket="data")
        s3.put_bucket_tagging(
            Bucket="data",
            Tagging={"TagSet": [{"Key": "Environment", "Value": "prod"}]},
        )
        yield s3


def _generator(tmp_path):
    config = MultiAccountConfig(
        accounts=[AccountCredentials(account_id="123456789012", regions=["us-east-1"])],
        cross_account_role_name="",
        output_directory=str(tmp_path / "out"),
        enable_state_management=False,
    )
    return CloudBOMGenerator(config)


def test_pipeline_end_to_end(aws, tmp_path):
    uninstall_global_guard()
    guard = install_global_guard(ReadOnlyGuard())
    try:
        integration = CICDIntegration(
            s3_config=S3UploadConfig(bucket_name="reports", key_prefix="ci"),
            compliance_gate_config=ComplianceGateConfig(minimum_compliance_percentage=0),
            artifacts_dir=str(tmp_path / "artifacts"),
        )
        result = integration.execute_pipeline_integration(
            _generator(tmp_path),
            output_formats=["excel", "json"],
            send_notifications=False,
        )
    finally:
        uninstall_global_guard()

    assert result.success, result.error_message
    assert sorted(p.rsplit(".", 1)[1] for p in result.generated_documents) == [
        "json",
        "xlsx",
    ]
    assert sorted(result.s3_uploads) == ["json", "xlsx"]

    keys = [o["Key"] for o in aws.list_objects_v2(Bucket="reports")["Contents"]]
    assert len(keys) == 2 and all(k.startswith("ci/") for k in keys)
    for key in keys:
        assert aws.head_object(Bucket="reports", Key=key)["ServerSideEncryption"] == "AES256"

    summary = json.loads((tmp_path / "artifacts" / "pipeline_summary.json").read_text())
    assert summary["success"] is True and summary["s3_uploads"] == 2
    assert result.metrics.total_resources >= 1

    # Discovery and upload made no write calls other than the uploads themselves.
    audit = guard.audit_report()
    assert audit["blocked_calls"] == 0
    writes = {o["operation"] for o in audit["operations"]} - {
        o["operation"]
        for o in audit["operations"]
        if o["operation"].startswith(("List", "Describe", "Get", "Head", "Lookup"))
    }
    assert writes <= {"PutObject", "AssumeRole"}


def test_pipeline_reports_bom_failure(aws, tmp_path, monkeypatch):
    generator = _generator(tmp_path)
    monkeypatch.setattr(
        generator,
        "generate_multi_account_bom",
        lambda **kwargs: {"success": False, "error": "no accounts reachable"},
    )
    result = CICDIntegration(artifacts_dir=str(tmp_path)).execute_pipeline_integration(
        generator, send_notifications=False
    )
    assert result.success is False
    assert result.error_message == "BOM generation failed: no accounts reachable"
