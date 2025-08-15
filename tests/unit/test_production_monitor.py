#!/usr/bin/env python3
"""
Unit tests for InvenTag Production Safety Monitor
Tests the production safety, error handling, and monitoring functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import time
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError, NoCredentialsError

from inventag.compliance.production_monitor import (
    ProductionSafetyMonitor,
    ErrorSeverity,
    MonitoringMetric,
    ErrorContext,
    PerformanceMetric,
    CloudTrailEvent,
    SecurityValidationReport,
)


class TestProductionSafetyMonitor(unittest.TestCase):
    """Test cases for ProductionSafetyMonitor."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("boto3.Session"), patch("psutil.cpu_percent"), patch(
            "psutil.virtual_memory"
        ), patch("psutil.disk_usage"):
            self.monitor = ProductionSafetyMonitor(
                enable_cloudtrail=False,  # Disable for testing
                enable_performance_monitoring=False,  # Disable for testing
            )
            self.monitor.account_id = "123456789012"

    def test_assess_error_severity_critical(self):
        """Test critical error severity assessment."""
        error = NoCredentialsError()
        severity = self.monitor._assess_error_severity(error, "describe_instances", "ec2")
        self.assertEqual(severity, ErrorSeverity.CRITICAL)

    def test_assess_error_severity_high(self):
        """Test high error severity assessment."""
        error = ClientError(
            error_response={"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            operation_name="DescribeInstances",
        )
        severity = self.monitor._assess_error_severity(error, "describe_instances", "ec2")
        self.assertEqual(severity, ErrorSeverity.HIGH)

    def test_assess_error_severity_medium(self):
        """Test medium error severity assessment."""
        error = ClientError(
            error_response={"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
            operation_name="DescribeInstances",
        )
        severity = self.monitor._assess_error_severity(error, "describe_instances", "ec2")
        self.assertEqual(severity, ErrorSeverity.MEDIUM)

    def test_assess_user_impact(self):
        """Test user impact assessment."""
        # Critical impact
        impact = self.monitor._assess_user_impact(ErrorSeverity.CRITICAL, "describe_instances")
        self.assertIn("High", impact)
        self.assertIn("user intervention required", impact)

        # High impact
        impact = self.monitor._assess_user_impact(ErrorSeverity.HIGH, "describe_instances")
        self.assertIn("Medium", impact)

        # Medium impact
        impact = self.monitor._assess_user_impact(ErrorSeverity.MEDIUM, "describe_instances")
        self.assertIn("Low", impact)

        # Low impact
        impact = self.monitor._assess_user_impact(ErrorSeverity.LOW, "describe_instances")
        self.assertIn("Minimal", impact)

    def test_handle_error_creates_context(self):
        """Test that error handling creates proper error context."""
        error = ValueError("Test error")

        error_context = self.monitor.handle_error(
            error,
            "test_operation",
            "test_service",
            resource_arn="arn:aws:test:us-east-1:123456789012:resource/test",
        )

        self.assertIsInstance(error_context, ErrorContext)
        self.assertEqual(error_context.error_type, "ValueError")
        self.assertEqual(error_context.error_message, "Test error")
        self.assertEqual(error_context.operation, "test_operation")
        self.assertEqual(error_context.service, "test_service")
        self.assertIsNotNone(error_context.correlation_id)
        self.assertIsNotNone(error_context.timestamp)

    def test_handle_error_updates_history(self):
        """Test that error handling updates error history."""
        initial_count = len(self.monitor.error_history)

        error = ValueError("Test error")
        self.monitor.handle_error(error, "test_operation", "test_service")

        self.assertEqual(len(self.monitor.error_history), initial_count + 1)
        self.assertEqual(self.monitor.error_counts["test_service:test_operation"], 1)

    def test_circuit_breaker_opens_after_failures(self):
        """Test that circuit breaker opens after repeated failures."""
        error = ValueError("Test error")

        # Generate multiple failures
        for i in range(6):
            self.monitor.handle_error(error, "test_operation", "test_service")

        breaker_state = self.monitor.circuit_breaker_state["test_service:test_operation"]
        self.assertEqual(breaker_state["state"], "open")
        self.assertEqual(breaker_state["failures"], 6)

    def test_record_operation(self):
        """Test operation recording."""
        initial_count = self.monitor.operation_counts["test_service:test_operation"]
        initial_metrics = len(self.monitor.performance_metrics)

        self.monitor.record_operation("test_operation", "test_service", 1.5, True)

        self.assertEqual(
            self.monitor.operation_counts["test_service:test_operation"],
            initial_count + 1,
        )
        self.assertEqual(len(self.monitor.performance_metrics), initial_metrics + 1)

        # Check the recorded metric
        metric = self.monitor.performance_metrics[-1]
        self.assertEqual(metric.metric_type, MonitoringMetric.PERFORMANCE)
        self.assertEqual(metric.metric_name, "operation_duration")
        self.assertEqual(metric.value, 1.5)
        self.assertEqual(metric.unit, "seconds")

    @patch("boto3.Session")
    def test_integrate_cloudtrail_events_success(self, mock_session):
        """Test successful CloudTrail integration."""
        # Setup mock CloudTrail client
        mock_cloudtrail = Mock()
        mock_paginator = Mock()
        mock_page_iterator = Mock()

        # Mock CloudTrail event data
        mock_events = [
            {
                "EventTime": datetime.now(timezone.utc),
                "EventName": "DescribeInstances",
                "EventSource": "ec2.amazonaws.com",
                "CloudTrailEvent": json.dumps(
                    {
                        "userIdentity": {"type": "IAMUser", "userName": "test-user"},
                        "sourceIPAddress": "192.168.1.1",
                        "userAgent": "aws-cli/2.0.0",
                        "requestParameters": {"instancesSet": {}},
                        "responseElements": None,
                    }
                ),
                "Resources": [],
                "ReadOnly": True,
            }
        ]

        mock_page_iterator.__iter__ = Mock(return_value=iter([{"Events": mock_events}]))
        mock_paginator.paginate.return_value = mock_page_iterator
        mock_cloudtrail.get_paginator.return_value = mock_paginator

        mock_session.return_value.client.return_value = mock_cloudtrail

        # Enable CloudTrail for this test
        self.monitor.cloudtrail_client = mock_cloudtrail

        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        end_time = datetime.now(timezone.utc)

        events = self.monitor.integrate_cloudtrail_events(start_time, end_time)

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], CloudTrailEvent)
        self.assertEqual(events[0].event_name, "DescribeInstances")
        self.assertTrue(events[0].read_only)

    def test_integrate_cloudtrail_events_no_client(self):
        """Test CloudTrail integration when client is not available."""
        self.monitor.cloudtrail_client = None

        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        end_time = datetime.now(timezone.utc)

        events = self.monitor.integrate_cloudtrail_events(start_time, end_time)

        self.assertEqual(len(events), 0)

    def test_generate_security_findings(self):
        """Test security findings generation."""
        # Add some test errors
        error = ValueError("Test error")
        for i in range(15):  # More than threshold
            self.monitor.handle_error(error, "test_operation", "test_service")

        # Add a critical error
        critical_error = NoCredentialsError()
        self.monitor.handle_error(critical_error, "critical_operation", "test_service")

        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        end_time = datetime.now(timezone.utc)

        findings = self.monitor._generate_security_findings(start_time, end_time)

        # Should have findings for high error rate and critical errors
        self.assertTrue(len(findings) >= 2)

        finding_ids = [f["finding_id"] for f in findings]
        self.assertIn("SEC-HIGH-ERROR-RATE", finding_ids)
        self.assertIn("SEC-CRITICAL-ERRORS", finding_ids)

    def test_calculate_risk_score(self):
        """Test risk score calculation."""
        # Test with no issues
        risk_score = self.monitor._calculate_risk_score(100, 0, 0, [])
        self.assertEqual(risk_score, 0.0)

        # Test with some failures
        risk_score = self.monitor._calculate_risk_score(100, 10, 2, [])
        self.assertGreater(risk_score, 0)

        # Test with high severity findings
        findings = [{"severity": "HIGH"}, {"severity": "MEDIUM"}, {"severity": "LOW"}]
        risk_score = self.monitor._calculate_risk_score(100, 5, 1, findings)
        self.assertGreater(risk_score, 30)  # Should be significant

    def test_generate_security_validation_report(self):
        """Test security validation report generation."""
        # Add some test data
        error = ValueError("Test error")
        self.monitor.handle_error(error, "test_operation", "test_service")
        self.monitor.record_operation("test_operation", "test_service", 1.0, True)

        report = self.monitor.generate_security_validation_report(validation_period_hours=1)

        self.assertIsInstance(report, SecurityValidationReport)
        self.assertIsNotNone(report.report_id)
        self.assertEqual(report.account_id, "123456789012")
        self.assertGreaterEqual(report.total_operations, 0)
        self.assertIsInstance(report.security_findings, list)
        self.assertIsInstance(report.recommendations, list)
        self.assertGreaterEqual(report.risk_score, 0)
        self.assertLessEqual(report.risk_score, 100)

    def test_generate_security_recommendations(self):
        """Test security recommendations generation."""
        findings = [{"severity": "HIGH"}]
        violations = [{"severity": "MEDIUM"}]

        recommendations = self.monitor._generate_security_recommendations(
            findings, violations, 75.0
        )

        self.assertIsInstance(recommendations, list)
        self.assertTrue(len(recommendations) > 0)

        # Should include base recommendations
        rec_text = " ".join(recommendations)
        self.assertIn("audit logging", rec_text)
        self.assertIn("IAM permissions", rec_text)

        # Should include high risk score recommendation
        self.assertTrue(any("High risk score" in rec for rec in recommendations))

    def test_get_monitoring_summary(self):
        """Test monitoring summary generation."""
        # Add some test data
        self.monitor.record_operation("test_operation", "test_service", 1.0, True)
        error = ValueError("Test error")
        self.monitor.handle_error(error, "test_operation", "test_service")

        summary = self.monitor.get_monitoring_summary()

        self.assertIn("monitoring_status", summary)
        self.assertIn("total_operations", summary)
        self.assertIn("total_errors", summary)
        self.assertIn("circuit_breakers", summary)
        self.assertIn("error_threshold", summary)
        self.assertIn("performance_thresholds", summary)
        self.assertEqual(summary["account_id"], "123456789012")

    def test_graceful_degradation_s3_upload(self):
        """Test graceful degradation for S3 upload failures."""
        error = ClientError(
            error_response={"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
            operation_name="PutObject",
        )

        error_context = self.monitor.handle_error(error, "s3_upload", "s3")

        # Should suggest local save as recovery action
        self.assertIsNotNone(error_context.recovery_action)
        self.assertIn("locally", error_context.recovery_action)

    @patch("logging.FileHandler")
    def test_logging_setup(self, mock_file_handler):
        """Test that logging is properly set up."""
        # The logger should be created during initialization
        self.assertIsNotNone(self.monitor.logger)
        self.assertEqual(
            self.monitor.logger.name,
            f"{self.monitor.__class__.__module__}.production_monitor",
        )

    def test_error_threshold_alert(self):
        """Test error threshold alerting."""
        # Generate errors to exceed threshold
        error = ValueError("Test error")
        for i in range(self.monitor.error_threshold + 1):
            self.monitor.handle_error(error, f"operation_{i}", "test_service")

        # Should have triggered threshold alert (logged as critical)
        # This is tested indirectly through the error history length
        self.assertGreaterEqual(len(self.monitor.error_history), self.monitor.error_threshold)

    def test_performance_metric_creation(self):
        """Test performance metric creation."""
        timestamp = datetime.now(timezone.utc)

        metric = PerformanceMetric(
            timestamp=timestamp,
            metric_type=MonitoringMetric.RESOURCE_USAGE,
            metric_name="cpu_usage_percent",
            value=75.5,
            unit="percent",
            tags={"resource": "cpu"},
            threshold_breached=False,
        )

        self.assertEqual(metric.metric_type, MonitoringMetric.RESOURCE_USAGE)
        self.assertEqual(metric.metric_name, "cpu_usage_percent")
        self.assertEqual(metric.value, 75.5)
        self.assertEqual(metric.unit, "percent")
        self.assertFalse(metric.threshold_breached)

    def test_cloudtrail_event_creation(self):
        """Test CloudTrail event creation."""
        timestamp = datetime.now(timezone.utc)

        event = CloudTrailEvent(
            event_time=timestamp,
            event_name="DescribeInstances",
            event_source="ec2.amazonaws.com",
            user_identity={"type": "IAMUser"},
            source_ip_address="192.168.1.1",
            user_agent="aws-cli/2.0.0",
            request_parameters={},
            response_elements=None,
            error_code=None,
            error_message=None,
            resources=[],
            read_only=True,
        )

        self.assertEqual(event.event_name, "DescribeInstances")
        self.assertEqual(event.event_source, "ec2.amazonaws.com")
        self.assertTrue(event.read_only)


if __name__ == "__main__":
    unittest.main()
