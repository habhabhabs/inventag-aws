#!/usr/bin/env python3
"""
Unit tests for CICDIntegration - CI/CD Integration Components

Tests for the CI/CD integration system for automated BOM generation and compliance checking.
"""

import pytest
import json
import tempfile

import boto3
from moto import mock_aws
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from pathlib import Path

from inventag.core.cicd_integration import (
    CICDIntegration,
    S3UploadConfig,
    ComplianceGateConfig,
    NotificationConfig,
    PrometheusConfig,
    PrometheusMetrics,
    CICDResult,
)


class TestS3UploadConfig:
    """Test S3UploadConfig data class."""

    def test_s3_upload_config_defaults(self):
        """Test S3UploadConfig with default values."""
        config = S3UploadConfig(bucket_name="test-bucket")

        assert config.bucket_name == "test-bucket"
        assert config.key_prefix == "inventag-bom"
        assert config.region == "us-east-1"
        assert config.encryption == "AES256"
        assert config.kms_key_id is None
        assert config.public_read is False
        # Lifecycle management is opt-in (it used to replace the bucket's rules).
        assert config.lifecycle_days == 0
        assert config.storage_class == "STANDARD"

    def test_s3_upload_config_custom(self):
        """Test S3UploadConfig with custom values."""
        config = S3UploadConfig(
            bucket_name="custom-bucket",
            key_prefix="custom-prefix",
            region="us-west-2",
            encryption="aws:kms",
            kms_key_id="arn:aws:kms:us-west-2:123456789012:key/12345678-1234-1234-1234-123456789012",
            public_read=True,
            lifecycle_days=30,
            storage_class="STANDARD_IA",
        )

        assert config.bucket_name == "custom-bucket"
        assert config.key_prefix == "custom-prefix"
        assert config.region == "us-west-2"
        assert config.encryption == "aws:kms"
        assert (
            config.kms_key_id
            == "arn:aws:kms:us-west-2:123456789012:key/12345678-1234-1234-1234-123456789012"
        )
        assert config.public_read is True
        assert config.lifecycle_days == 30
        assert config.storage_class == "STANDARD_IA"


class TestComplianceGateConfig:
    """Test ComplianceGateConfig data class."""

    def test_compliance_gate_config_defaults(self):
        """Test ComplianceGateConfig with default values."""
        config = ComplianceGateConfig()

        assert config.minimum_compliance_percentage == 80.0
        assert config.critical_violations_threshold == 0
        assert config.required_tags == []
        assert config.allowed_non_compliant_services == []
        assert config.fail_on_security_issues is True
        assert config.fail_on_network_issues is False

    def test_compliance_gate_config_custom(self):
        """Test ComplianceGateConfig with custom values."""
        config = ComplianceGateConfig(
            minimum_compliance_percentage=90.0,
            critical_violations_threshold=5,
            required_tags=["Environment", "Owner"],
            allowed_non_compliant_services=["S3", "CloudTrail"],
            fail_on_security_issues=False,
            fail_on_network_issues=True,
        )

        assert config.minimum_compliance_percentage == 90.0
        assert config.critical_violations_threshold == 5
        assert config.required_tags == ["Environment", "Owner"]
        assert config.allowed_non_compliant_services == ["S3", "CloudTrail"]
        assert config.fail_on_security_issues is False
        assert config.fail_on_network_issues is True


class TestNotificationConfig:
    """Test NotificationConfig data class."""

    def test_notification_config_defaults(self):
        """Test NotificationConfig with default values."""
        config = NotificationConfig()

        assert config.slack_webhook_url is None
        assert config.teams_webhook_url is None
        assert config.email_recipients == []
        assert config.include_summary is True
        assert config.include_document_links is True
        assert config.notify_on_success is True
        assert config.notify_on_failure is True

    def test_notification_config_custom(self):
        """Test NotificationConfig with custom values."""
        config = NotificationConfig(
            slack_webhook_url="https://hooks.slack.com/test",
            teams_webhook_url="https://outlook.office.com/webhook/test",
            email_recipients=["admin@example.com", "team@example.com"],
            include_summary=False,
            include_document_links=False,
            notify_on_success=False,
            notify_on_failure=True,
        )

        assert config.slack_webhook_url == "https://hooks.slack.com/test"
        assert config.teams_webhook_url == "https://outlook.office.com/webhook/test"
        assert config.email_recipients == ["admin@example.com", "team@example.com"]
        assert config.include_summary is False
        assert config.include_document_links is False
        assert config.notify_on_success is False
        assert config.notify_on_failure is True


class TestPrometheusConfig:
    """Test PrometheusConfig data class."""

    def test_prometheus_config_defaults(self):
        """Test PrometheusConfig with default values."""
        config = PrometheusConfig()

        assert config.push_gateway_url is None
        assert config.job_name == "inventag-bom"
        assert config.instance_name == "default"
        assert config.push_on_success is True
        assert config.push_on_failure is True
        assert config.include_resource_counts is True
        assert config.include_compliance_metrics is True
        assert config.include_timing_metrics is True

    def test_prometheus_config_custom(self):
        """Test PrometheusConfig with custom values."""
        config = PrometheusConfig(
            push_gateway_url="http://prometheus-gateway:9091",
            job_name="custom-job",
            instance_name="prod-instance",
            push_on_success=False,
            push_on_failure=True,
            include_resource_counts=False,
            include_compliance_metrics=False,
            include_timing_metrics=False,
        )

        assert config.push_gateway_url == "http://prometheus-gateway:9091"
        assert config.job_name == "custom-job"
        assert config.instance_name == "prod-instance"
        assert config.push_on_success is False
        assert config.push_on_failure is True
        assert config.include_resource_counts is False
        assert config.include_compliance_metrics is False
        assert config.include_timing_metrics is False


class TestPrometheusMetrics:
    """Test PrometheusMetrics data class."""

    def test_prometheus_metrics_defaults(self):
        """Test PrometheusMetrics with default values."""
        metrics = PrometheusMetrics()

        assert metrics.total_resources == 0
        assert metrics.compliant_resources == 0
        assert metrics.non_compliant_resources == 0
        assert metrics.compliance_percentage == 0.0
        assert metrics.processing_time_seconds == 0.0
        assert metrics.successful_accounts == 0
        assert metrics.failed_accounts == 0
        assert metrics.total_accounts == 0
        assert metrics.security_issues == 0
        assert metrics.network_issues == 0
        assert metrics.document_generation_time == 0.0
        assert metrics.s3_upload_time == 0.0

    def test_prometheus_metrics_custom(self):
        """Test PrometheusMetrics with custom values."""
        metrics = PrometheusMetrics(
            total_resources=1000,
            compliant_resources=800,
            non_compliant_resources=200,
            compliance_percentage=80.0,
            processing_time_seconds=120.5,
            successful_accounts=3,
            failed_accounts=1,
            total_accounts=4,
            security_issues=5,
            network_issues=2,
            document_generation_time=30.2,
            s3_upload_time=5.8,
        )

        assert metrics.total_resources == 1000
        assert metrics.compliant_resources == 800
        assert metrics.non_compliant_resources == 200
        assert metrics.compliance_percentage == 80.0
        assert metrics.processing_time_seconds == 120.5
        assert metrics.successful_accounts == 3
        assert metrics.failed_accounts == 1
        assert metrics.total_accounts == 4
        assert metrics.security_issues == 5
        assert metrics.network_issues == 2
        assert metrics.document_generation_time == 30.2
        assert metrics.s3_upload_time == 5.8


class TestCICDResult:
    """Test CICDResult data class."""

    def test_cicd_result_defaults(self):
        result = CICDResult(success=True)
        assert result.compliance_gate_passed is False
        assert result.generated_documents == [] and result.s3_uploads == {}
        assert result.notifications_sent == [] and result.artifacts == {}
        assert result.metrics is None and result.error_message == ""

    def test_cicd_result_values(self):
        result = CICDResult(
            success=False,
            error_message="Authentication failed",
            generated_documents=["/out/bom.xlsx"],
            s3_uploads={"xlsx": "https://reports.s3.us-east-1.amazonaws.com/x"},
            execution_time_seconds=1.5,
        )
        assert result.success is False
        assert result.error_message == "Authentication failed"
        assert result.generated_documents == ["/out/bom.xlsx"]


def _bom_results(success=True, compliance=None, files=None):
    return {
        "success": success,
        "error": None if success else "discovery exploded",
        "processing_statistics": {
            "total_accounts": 2,
            "successful_accounts": 2,
            "failed_accounts": 0,
            "total_resources": 10,
        },
        "account_contexts": {
            "123456789012": {"account_name": "a", "resource_count": 10}
        },
        "bom_generation": {"generated_files": files or []},
        "compliance_analysis": (
            compliance
            if compliance is not None
            else {"total_resources": 10, "compliant_resources": 9}
        ),
    }


class TestCICDIntegration:
    """Test CICDIntegration against its real API."""

    @pytest.fixture
    def cicd_integration(self, tmp_path):
        return CICDIntegration(artifacts_dir=str(tmp_path / "artifacts"))

    @pytest.fixture
    def s3(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        with mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            client.create_bucket(Bucket="reports")
            yield client

    def test_init_default(self, cicd_integration):
        assert cicd_integration.s3_config is None
        assert isinstance(cicd_integration.compliance_gate_config, ComplianceGateConfig)
        assert isinstance(cicd_integration.notification_config, NotificationConfig)
        assert isinstance(cicd_integration.prometheus_config, PrometheusConfig)

    def test_init_with_configs(self, tmp_path):
        s3_config = S3UploadConfig(bucket_name="reports")
        gate = ComplianceGateConfig(minimum_compliance_percentage=90.0)
        integration = CICDIntegration(
            s3_config=s3_config,
            compliance_gate_config=gate,
            artifacts_dir=str(tmp_path),
        )
        assert integration.s3_config is s3_config
        assert integration.compliance_gate_config is gate
        assert str(integration.artifacts_dir) == str(tmp_path)

    def test_upload_to_s3_success(self, s3, tmp_path):
        report = tmp_path / "bom.xlsx"
        report.write_bytes(b"x")
        integration = CICDIntegration(s3_config=S3UploadConfig(bucket_name="reports"))
        uploads = integration._upload_documents_to_s3([str(report)])
        assert list(uploads) == ["xlsx"]
        assert uploads["xlsx"].startswith(
            "https://reports.s3.us-east-1.amazonaws.com/inventag-bom/"
        )
        assert integration.last_upload_errors == []

    def test_upload_to_s3_failure_is_reported(self, s3, tmp_path):
        report = tmp_path / "bom.xlsx"
        report.write_bytes(b"x")
        integration = CICDIntegration(
            s3_config=S3UploadConfig(bucket_name="missing-bucket")
        )
        assert integration._upload_documents_to_s3([str(report)]) == {}
        assert len(integration.last_upload_errors) == 1

    def test_upload_without_config(self, cicd_integration):
        assert cicd_integration._upload_documents_to_s3(["x"]) == {}

    @pytest.mark.parametrize(
        "results, expected",
        [
            ({"total_resources": 10, "compliant_resources": 9}, True),
            ({"total_resources": 10, "compliant_resources": 7}, False),
            (
                {
                    "total_resources": 10,
                    "compliant_resources": 10,
                    "critical_violations": 1,
                },
                False,
            ),
            (
                {
                    "total_resources": 10,
                    "compliant_resources": 10,
                    "security_issues": 2,
                },
                False,
            ),
            ({"total_resources": 0, "compliant_resources": 0}, False),
            ({}, False),
        ],
    )
    def test_check_compliance_gate(self, cicd_integration, results, expected):
        assert cicd_integration._check_compliance_gate(results) is expected

    def test_network_issues_only_fail_when_configured(self):
        results = {
            "total_resources": 10,
            "compliant_resources": 10,
            "network_issues": 3,
        }
        assert CICDIntegration()._check_compliance_gate(results) is True
        strict = CICDIntegration(
            compliance_gate_config=ComplianceGateConfig(fail_on_network_issues=True)
        )
        assert strict._check_compliance_gate(results) is False

    @patch("inventag.core.cicd_integration.requests.post")
    def test_send_slack_notification_success(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        integration = CICDIntegration(
            notification_config=NotificationConfig(
                slack_webhook_url="https://hooks.slack.com/services/T0/B0/x"
            )
        )
        sent = integration._send_notifications(_bom_results(), CICDResult(success=True))
        assert sent == ["slack"]
        payload = mock_post.call_args.kwargs["json"]
        assert "InvenTag" in payload["text"] or payload.get("attachments")
        assert mock_post.call_args.kwargs["allow_redirects"] is False
        assert mock_post.call_args.kwargs["timeout"] == 30

    @patch("inventag.core.cicd_integration.requests.post")
    def test_send_slack_notification_failure(self, mock_post):
        mock_post.return_value.raise_for_status.side_effect = RuntimeError("500")
        integration = CICDIntegration(
            notification_config=NotificationConfig(
                slack_webhook_url="https://hooks.slack.com/services/T0/B0/x"
            )
        )
        assert (
            integration._send_notifications(_bom_results(), CICDResult(success=True))
            == []
        )

    @patch("inventag.core.cicd_integration.requests.post")
    def test_failure_notification_is_delivered(self, mock_post):
        """Used to raise KeyError (partial summary) so nothing was sent."""
        mock_post.return_value.raise_for_status.return_value = None
        integration = CICDIntegration(
            notification_config=NotificationConfig(
                slack_webhook_url="https://hooks.slack.com/services/T0/B0/x"
            )
        )
        integration._send_failure_notification(
            CICDResult(success=False, error_message="boom")
        )
        assert mock_post.call_count == 1
        assert "boom" in json.dumps(mock_post.call_args.kwargs["json"])

    @patch("inventag.core.cicd_integration.requests.post")
    def test_push_prometheus_gateway_success(self, mock_post, cicd_integration):
        mock_post.return_value.raise_for_status.return_value = None
        cicd_integration._push_to_prometheus_gateway("metric 1\n", "http://gw:9091/")
        url = mock_post.call_args.args[0]
        assert url == "http://gw:9091/metrics/job/inventag-bom/instance/default"

    @patch("inventag.core.cicd_integration.requests.post")
    def test_push_prometheus_gateway_escapes_labels(
        self, mock_post, cicd_integration, monkeypatch
    ):
        monkeypatch.setenv("PROMETHEUS_JOB_NAME", "../admin?x=1")
        cicd_integration._push_to_prometheus_gateway("m 1\n", "http://gw:9091")
        assert mock_post.call_args.args[0] == (
            "http://gw:9091/metrics/job/..%2Fadmin%3Fx%3D1/instance/default"
        )

    @patch("inventag.core.cicd_integration.requests.post")
    def test_push_prometheus_gateway_rejects_bad_scheme(
        self, mock_post, cicd_integration
    ):
        cicd_integration._push_to_prometheus_gateway("m 1\n", "file:///etc/passwd")
        mock_post.assert_not_called()

    def test_export_prometheus_metrics_writes_private_file(self, cicd_integration):
        metrics = PrometheusMetrics(total_resources=10, compliant_resources=9)
        cicd_integration._export_prometheus_metrics(metrics)
        prom = cicd_integration.artifacts_dir / "inventag_metrics.prom"
        assert "inventag_total_resources 10" in prom.read_text()
        assert prom.stat().st_mode & 0o777 == 0o600

    def _generator(self, results):
        generator = Mock()
        generator.generate_multi_account_bom.return_value = results
        return generator

    def test_run_pipeline_success(self, cicd_integration):
        result = cicd_integration.execute_pipeline_integration(
            self._generator(_bom_results()), send_notifications=False
        )
        assert result.success is True
        assert result.compliance_gate_passed is True
        assert result.metrics.total_resources == 10
        assert "pipeline_summary.json" in result.artifacts
        assert (cicd_integration.artifacts_dir / "pipeline_summary.json").exists()

    def test_run_pipeline_bom_generation_failure(self, cicd_integration):
        result = cicd_integration.execute_pipeline_integration(
            self._generator(_bom_results(success=False))
        )
        assert result.success is False
        assert "discovery exploded" in result.error_message

    def test_run_pipeline_compliance_gate_failure(self, cicd_integration):
        results = _bom_results(
            compliance={"total_resources": 10, "compliant_resources": 1}
        )
        result = cicd_integration.execute_pipeline_integration(
            self._generator(results), send_notifications=False
        )
        assert result.success is True
        assert result.compliance_gate_passed is False

    def test_run_pipeline_with_s3_upload(self, s3, tmp_path):
        report = tmp_path / "bom.xlsx"
        report.write_bytes(b"x")
        integration = CICDIntegration(
            s3_config=S3UploadConfig(bucket_name="reports"),
            artifacts_dir=str(tmp_path / "a"),
        )
        result = integration.execute_pipeline_integration(
            self._generator(_bom_results(files=[str(report)])), send_notifications=False
        )
        assert result.success is True
        assert list(result.s3_uploads) == ["xlsx"]

    def test_run_pipeline_s3_upload_failure_fails_pipeline(self, s3, tmp_path):
        report = tmp_path / "bom.xlsx"
        report.write_bytes(b"x")
        integration = CICDIntegration(
            s3_config=S3UploadConfig(bucket_name="missing-bucket"),
            artifacts_dir=str(tmp_path / "a"),
        )
        result = integration.execute_pipeline_integration(
            self._generator(_bom_results(files=[str(report)])), send_notifications=False
        )
        assert result.success is False
        assert "S3 upload failed for 1 file(s)" in result.error_message

    @patch("inventag.core.cicd_integration.requests.post")
    def test_run_pipeline_with_notifications(self, mock_post, tmp_path):
        mock_post.return_value.raise_for_status.return_value = None
        integration = CICDIntegration(
            notification_config=NotificationConfig(
                slack_webhook_url="https://hooks.slack.com/services/T0/B0/x",
                teams_webhook_url="https://example.webhook.office.com/webhookb2/x",
            ),
            artifacts_dir=str(tmp_path),
        )
        result = integration.execute_pipeline_integration(
            self._generator(_bom_results())
        )
        assert sorted(result.notifications_sent) == ["slack", "teams"]

    @patch("inventag.core.cicd_integration.requests.post")
    def test_success_status_reported_in_artifacts_and_notifications(
        self, mock_post, tmp_path
    ):
        """Artifacts and notifications used to be produced before success was set."""
        mock_post.return_value.raise_for_status.return_value = None
        integration = CICDIntegration(
            notification_config=NotificationConfig(
                slack_webhook_url="https://hooks.slack.com/services/T0/B0/x"
            ),
            artifacts_dir=str(tmp_path),
        )
        generator = Mock()
        generator.generate_multi_account_bom.return_value = _bom_results()
        result = integration.execute_pipeline_integration(generator)
        assert result.success is True
        summary = json.loads((tmp_path / "pipeline_summary.json").read_text())
        assert summary["success"] is True
        assert "SUCCESS" in json.dumps(mock_post.call_args.kwargs["json"])
