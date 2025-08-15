#!/usr/bin/env python3
"""
Unit tests for CICDIntegration - CI/CD Integration Components

Tests for the CI/CD integration system for automated BOM generation and compliance checking.
"""

import pytest
import json
import tempfile
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
        assert config.lifecycle_days == 90
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

    def test_cicd_result_success(self):
        """Test CICDResult for successful execution."""
        result = CICDResult(
            success=True,
            message="BOM generation completed successfully",
            bom_data={"resources": []},
            compliance_report={"compliance_percentage": 95.0},
            document_paths={"excel": "/path/to/bom.xlsx"},
            s3_urls={"excel": "https://s3.amazonaws.com/bucket/bom.xlsx"},
            execution_time=120.5,
            resource_count=150,
            compliance_percentage=95.0,
        )

        assert result.success is True
        assert result.message == "BOM generation completed successfully"
        assert result.bom_data == {"resources": []}
        assert result.compliance_report == {"compliance_percentage": 95.0}
        assert result.document_paths == {"excel": "/path/to/bom.xlsx"}
        assert result.s3_urls == {"excel": "https://s3.amazonaws.com/bucket/bom.xlsx"}
        assert result.execution_time == 120.5
        assert result.resource_count == 150
        assert result.compliance_percentage == 95.0

    def test_cicd_result_failure(self):
        """Test CICDResult for failed execution."""
        result = CICDResult(
            success=False,
            message="Authentication failed",
            error_details={
                "error_type": "CredentialError",
                "details": "Invalid AWS credentials",
            },
        )

        assert result.success is False
        assert result.message == "Authentication failed"
        assert result.error_details == {
            "error_type": "CredentialError",
            "details": "Invalid AWS credentials",
        }
        assert result.bom_data is None
        assert result.compliance_report is None
        assert result.document_paths is None
        assert result.s3_urls is None
        assert result.execution_time is None
        assert result.resource_count is None
        assert result.compliance_percentage is None


class TestCICDIntegration:
    """Test CICDIntegration main class."""

    @pytest.fixture
    def mock_bom_generator(self):
        """Mock BOM generator."""
        mock = Mock()
        mock.generate_bom.return_value = {
            "resources": [{"service": "EC2", "resource_id": "i-123", "region": "us-east-1"}],
            "metadata": {"total_resources": 1},
        }
        return mock

    @pytest.fixture
    def mock_document_generator(self):
        """Mock document generator."""
        mock = Mock()
        mock.generate_excel_report.return_value = "/tmp/test_bom.xlsx"
        mock.generate_word_report.return_value = "/tmp/test_bom.docx"
        return mock

    @pytest.fixture
    def mock_credential_manager(self):
        """Mock credential manager."""
        mock = Mock()
        mock.get_aws_credentials.return_value = {
            "aws_access_key_id": "test_key",
            "aws_secret_access_key": "test_secret",
        }
        return mock

    @pytest.fixture
    def cicd_integration(self):
        """Create CICDIntegration instance with default configuration."""
        return CICDIntegration()

    def test_init_default(self, cicd_integration):
        """Test CICDIntegration initialization with defaults."""
        assert cicd_integration.s3_config is None
        assert cicd_integration.compliance_gate_config is not None
        assert cicd_integration.notification_config is not None
        assert cicd_integration.prometheus_config is not None
        assert cicd_integration.s3_client is None

    def test_init_with_configs(self):
        """Test CICDIntegration initialization with custom configs."""
        s3_config = S3UploadConfig(bucket_name="test-bucket")
        compliance_config = ComplianceGateConfig(minimum_compliance_percentage=90.0)
        notification_config = NotificationConfig(slack_webhook_url="https://hooks.slack.com/test")
        prometheus_config = PrometheusConfig(push_gateway_url="http://prometheus:9091")

        cicd = CICDIntegration(
            s3_config=s3_config,
            compliance_config=compliance_config,
            notification_config=notification_config,
            prometheus_config=prometheus_config,
        )

        assert cicd.s3_config == s3_config
        assert cicd.compliance_gate_config == compliance_config
        assert cicd.notification_config == notification_config
        assert cicd.prometheus_config == prometheus_config

    @patch("inventag.core.cicd_integration.boto3")
    def test_upload_to_s3_success(self, mock_boto3, cicd_integration):
        """Test successful S3 upload."""
        # Setup
        mock_s3_client = Mock()
        mock_boto3.client.return_value = mock_s3_client

        s3_config = S3UploadConfig(bucket_name="test-bucket")
        cicd_integration.s3_config = s3_config

        with tempfile.NamedTemporaryFile(suffix=".xlsx") as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()

            # Execute
            result = cicd_integration._upload_to_s3(temp_file.name, "test.xlsx")

            # Verify
            assert result.startswith("https://test-bucket.s3.us-east-1.amazonaws.com/")
            mock_s3_client.upload_file.assert_called_once()

    @patch("inventag.core.cicd_integration.boto3")
    def test_upload_to_s3_failure(self, mock_boto3, cicd_integration):
        """Test S3 upload failure."""
        # Setup
        mock_s3_client = Mock()
        mock_s3_client.upload_file.side_effect = Exception("Upload failed")
        mock_boto3.client.return_value = mock_s3_client

        s3_config = S3UploadConfig(bucket_name="test-bucket")
        cicd_integration.s3_config = s3_config

        with tempfile.NamedTemporaryFile(suffix=".xlsx") as temp_file:
            # Execute & Verify
            with pytest.raises(Exception, match="Upload failed"):
                cicd_integration._upload_to_s3(temp_file.name, "test.xlsx")

    def test_check_compliance_gate_pass(self, cicd_integration):
        """Test compliance gate check that passes."""
        compliance_report = {
            "compliance_percentage": 85.0,
            "critical_violations": 0,
            "security_issues": [],
            "network_issues": ["minor-issue"],
        }

        result = cicd_integration._check_compliance_gate(compliance_report)

        assert result is True

    def test_check_compliance_gate_fail_percentage(self, cicd_integration):
        """Test compliance gate check that fails on percentage."""
        compliance_report = {
            "compliance_percentage": 75.0,
            "critical_violations": 0,
            "security_issues": [],
            "network_issues": [],
        }

        result = cicd_integration._check_compliance_gate(compliance_report)

        assert result is False

    def test_check_compliance_gate_fail_critical_violations(self, cicd_integration):
        """Test compliance gate check that fails on critical violations."""
        compliance_report = {
            "compliance_percentage": 85.0,
            "critical_violations": 1,
            "security_issues": [],
            "network_issues": [],
        }

        result = cicd_integration._check_compliance_gate(compliance_report)

        assert result is False

    def test_check_compliance_gate_fail_security_issues(self, cicd_integration):
        """Test compliance gate check that fails on security issues."""
        compliance_report = {
            "compliance_percentage": 85.0,
            "critical_violations": 0,
            "security_issues": ["high-severity-issue"],
            "network_issues": [],
        }

        result = cicd_integration._check_compliance_gate(compliance_report)

        assert result is False

    @patch("inventag.core.cicd_integration.requests.post")
    def test_send_slack_notification_success(self, mock_post, cicd_integration):
        """Test successful Slack notification."""
        # Setup
        mock_post.return_value.status_code = 200
        cicd_integration.notification_config.slack_webhook_url = "https://hooks.slack.com/test"

        result = CICDResult(
            success=True,
            message="BOM generation completed",
            execution_time=120.5,
            resource_count=150,
            compliance_percentage=95.0,
        )

        # Execute
        cicd_integration._send_slack_notification(result)

        # Verify
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "BOM generation completed" in call_args[1]["json"]["text"]

    @patch("inventag.core.cicd_integration.requests.post")
    def test_send_slack_notification_failure(self, mock_post, cicd_integration):
        """Test Slack notification failure."""
        # Setup
        mock_post.side_effect = Exception("Network error")
        cicd_integration.notification_config.slack_webhook_url = "https://hooks.slack.com/test"

        result = CICDResult(success=False, message="BOM generation failed")

        # Execute (should not raise exception)
        cicd_integration._send_slack_notification(result)

        # Verify
        mock_post.assert_called_once()

    @patch("inventag.core.cicd_integration.requests.post")
    def test_push_prometheus_gateway_success(self, mock_post, cicd_integration):
        """Test successful Prometheus push gateway."""
        # Setup
        mock_post.return_value.status_code = 200
        metrics_content = "inventag_total_resources 150"
        gateway_url = "http://prometheus:9091"

        # Execute
        cicd_integration._push_to_prometheus_gateway(metrics_content, gateway_url)

        # Verify
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "prometheus:9091" in call_args[0][0]
        assert "inventag_total_resources 150" in call_args[1]["data"]
        assert call_args[1]["headers"]["Content-Type"] == "text/plain"

    @patch("inventag.core.cicd_integration.requests.post")
    def test_push_prometheus_gateway_failure(self, mock_post, cicd_integration):
        """Test Prometheus push gateway failure."""
        # Setup
        mock_post.side_effect = Exception("Connection error")
        metrics_content = "inventag_total_resources 150"
        gateway_url = "http://prometheus:9091"

        # Execute (should not raise exception)
        cicd_integration._push_to_prometheus_gateway(metrics_content, gateway_url)

        # Verify
        mock_post.assert_called_once()

    @patch("inventag.core.cicd_integration.os.environ.get")
    @patch("inventag.core.cicd_integration.requests.post")
    def test_export_prometheus_metrics_with_gateway(
        self, mock_post, mock_env_get, cicd_integration
    ):
        """Test Prometheus metrics export with push gateway."""
        # Setup
        mock_post.return_value.status_code = 200
        mock_env_get.side_effect = lambda key, default=None: {
            "PROMETHEUS_PUSH_GATEWAY_URL": "http://prometheus:9091",
            "PROMETHEUS_JOB_NAME": "test-job",
            "PROMETHEUS_INSTANCE_NAME": "test-instance",
        }.get(key, default)

        metrics = PrometheusMetrics(
            total_resources=150, compliant_resources=120, compliance_percentage=80.0
        )

        # Execute
        cicd_integration._export_prometheus_metrics(metrics)

        # Verify
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "prometheus:9091" in call_args[0][0]
        assert "test-job" in call_args[0][0]
        assert "test-instance" in call_args[0][0]

    @patch("inventag.core.cicd_integration.time.time")
    def test_run_pipeline_success(
        self, mock_time, cicd_integration, mock_bom_generator, mock_document_generator
    ):
        """Test successful pipeline execution."""
        # Setup
        mock_time.side_effect = [1000.0, 1120.5]  # Start and end times

        mock_bom_generator.generate_compliance_report.return_value = {
            "compliance_percentage": 85.0,
            "critical_violations": 0,
            "security_issues": [],
            "network_issues": [],
        }

        # Execute
        result = cicd_integration.run_pipeline()

        # Verify
        assert result.success is True
        assert result.execution_time == 120.5
        assert result.resource_count == 1
        assert result.compliance_percentage == 85.0
        assert "BOM generation completed successfully" in result.message

        mock_bom_generator.generate_bom.assert_called_once()
        mock_bom_generator.generate_compliance_report.assert_called_once()
        mock_document_generator.generate_excel_report.assert_called_once()

    def test_run_pipeline_bom_generation_failure(self, cicd_integration, mock_bom_generator):
        """Test pipeline failure during BOM generation."""
        # Setup
        mock_bom_generator.generate_bom.side_effect = Exception("AWS API error")

        # Execute
        result = cicd_integration.run_pipeline()

        # Verify
        assert result.success is False
        assert "BOM generation failed" in result.message
        assert "AWS API error" in result.error_details["details"]

    def test_run_pipeline_compliance_gate_failure(
        self, cicd_integration, mock_bom_generator, mock_document_generator
    ):
        """Test pipeline failure due to compliance gate."""
        # Setup
        mock_bom_generator.generate_compliance_report.return_value = {
            "compliance_percentage": 70.0,  # Below threshold
            "critical_violations": 0,
            "security_issues": [],
            "network_issues": [],
        }

        # Execute
        result = cicd_integration.run_pipeline()

        # Verify
        assert result.success is False
        assert "Compliance gate failed" in result.message
        assert result.compliance_percentage == 70.0

    @patch("inventag.core.cicd_integration.boto3")
    def test_run_pipeline_with_s3_upload(
        self, mock_boto3, cicd_integration, mock_bom_generator, mock_document_generator
    ):
        """Test pipeline with S3 upload enabled."""
        # Setup
        mock_s3_client = Mock()
        mock_boto3.client.return_value = mock_s3_client

        cicd_integration.s3_config = S3UploadConfig(bucket_name="test-bucket")

        mock_bom_generator.generate_compliance_report.return_value = {
            "compliance_percentage": 85.0,
            "critical_violations": 0,
            "security_issues": [],
            "network_issues": [],
        }

        # Execute
        result = cicd_integration.run_pipeline()

        # Verify
        assert result.success is True
        assert result.s3_urls is not None
        assert "excel" in result.s3_urls
        mock_s3_client.upload_file.assert_called()

    @patch("inventag.core.cicd_integration.requests.post")
    def test_run_pipeline_with_notifications(
        self, mock_post, cicd_integration, mock_bom_generator, mock_document_generator
    ):
        """Test pipeline with notifications enabled."""
        # Setup
        mock_post.return_value.status_code = 200
        cicd_integration.notification_config.slack_webhook_url = "https://hooks.slack.com/test"
        cicd_integration.prometheus_config.gateway_url = "http://prometheus:9091"

        mock_bom_generator.generate_compliance_report.return_value = {
            "compliance_percentage": 85.0,
            "critical_violations": 0,
            "security_issues": [],
            "network_issues": [],
        }

        # Execute
        result = cicd_integration.run_pipeline()

        # Verify
        assert result.success is True
        assert mock_post.call_count == 2  # Slack + Prometheus

    def test_run_pipeline_document_generation_failure(
        self, cicd_integration, mock_bom_generator, mock_document_generator
    ):
        """Test pipeline failure during document generation."""
        # Setup
        mock_bom_generator.generate_compliance_report.return_value = {
            "compliance_percentage": 85.0,
            "critical_violations": 0,
            "security_issues": [],
            "network_issues": [],
        }
        mock_document_generator.generate_excel_report.side_effect = Exception(
            "Document generation error"
        )

        # Execute
        result = cicd_integration.run_pipeline()

        # Verify
        assert result.success is False
        assert "Document generation failed" in result.message
        assert "Document generation error" in result.error_details["details"]


if __name__ == "__main__":
    pytest.main([__file__])
