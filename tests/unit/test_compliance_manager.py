#!/usr/bin/env python3
"""
Unit tests for InvenTag Compliance Manager
Tests the unified compliance management functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime, timezone, timedelta

from inventag.compliance.compliance_manager import (
    ComplianceManager,
    ComplianceConfiguration,
    ComplianceStatus,
    ComplianceStandard,
)


class TestComplianceManager(unittest.TestCase):
    """Test cases for ComplianceManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = ComplianceConfiguration(
            compliance_standard=ComplianceStandard.GENERAL,
            enable_security_validation=True,
            enable_production_monitoring=True,
            enable_cloudtrail_integration=False,  # Disable for testing
            error_threshold=5,
        )

        with patch("boto3.Session"), patch("psutil.cpu_percent"), patch(
            "psutil.virtual_memory"
        ), patch("psutil.disk_usage"):
            self.manager = ComplianceManager(self.config)

    def test_initialization(self):
        """Test compliance manager initialization."""
        self.assertIsNotNone(self.manager.security_validator)
        self.assertIsNotNone(self.manager.production_monitor)
        self.assertEqual(
            self.manager.config.compliance_standard, ComplianceStandard.GENERAL
        )

    def test_initialization_with_disabled_components(self):
        """Test initialization with disabled components."""
        config = ComplianceConfiguration(
            compliance_standard=ComplianceStandard.GENERAL,
            enable_security_validation=False,
            enable_production_monitoring=False,
        )

        with patch("boto3.Session"):
            manager = ComplianceManager(config)
            self.assertIsNone(manager.security_validator)
            self.assertIsNone(manager.production_monitor)

    def test_validate_and_monitor_operation_success(self):
        """Test successful operation validation and monitoring."""
        # Mock operation function
        mock_operation = Mock(return_value={"result": "success"})

        result = self.manager.validate_and_monitor_operation(
            service="ec2", operation="describe_instances", operation_func=mock_operation
        )

        self.assertTrue(result["validation_passed"])
        self.assertTrue(result["operation_executed"])
        self.assertTrue(result["operation_successful"])
        self.assertIsNotNone(result["security_validation"])
        self.assertGreater(result["duration_seconds"], 0)

    def test_validate_and_monitor_operation_blocked(self):
        """Test operation blocked by security validation."""
        result = self.manager.validate_and_monitor_operation(
            service="ec2", operation="create_instance"  # This should be blocked
        )

        self.assertFalse(result["validation_passed"])
        self.assertFalse(result["operation_executed"])
        self.assertIsNotNone(result["security_validation"])

    def test_validate_and_monitor_operation_with_error(self):
        """Test operation that throws an error."""

        # Mock operation function that raises an exception
        def failing_operation():
            raise ValueError("Test error")

        result = self.manager.validate_and_monitor_operation(
            service="ec2",
            operation="describe_instances",
            operation_func=failing_operation,
        )

        self.assertTrue(result["validation_passed"])
        self.assertTrue(result["operation_executed"])
        self.assertFalse(result["operation_successful"])
        self.assertIsNotNone(result["error_context"])

    def test_assess_compliance_status_compliant(self):
        """Test compliance status assessment when compliant."""
        # Perform some valid operations
        self.manager.validate_and_monitor_operation("ec2", "describe_instances")
        self.manager.validate_and_monitor_operation("s3", "list_buckets")

        status = self.manager.assess_compliance_status()

        self.assertIsInstance(status, ComplianceStatus)
        self.assertTrue(status.is_compliant)
        self.assertGreater(status.compliance_score, 90)
        self.assertTrue(status.security_validation_passed)
        self.assertGreater(status.total_operations, 0)

    def test_assess_compliance_status_non_compliant(self):
        """Test compliance status assessment when non-compliant."""
        # Perform some blocked operations
        self.manager.validate_and_monitor_operation("ec2", "create_instance")
        self.manager.validate_and_monitor_operation("s3", "delete_bucket")

        status = self.manager.assess_compliance_status()

        self.assertFalse(status.is_compliant)
        self.assertFalse(status.security_validation_passed)
        self.assertGreater(status.blocked_operations, 0)
        self.assertIn("blocked operations", " ".join(status.recommendations).lower())

    def test_generate_comprehensive_compliance_report(self):
        """Test comprehensive compliance report generation."""
        # Perform some operations
        self.manager.validate_and_monitor_operation("ec2", "describe_instances")
        self.manager.validate_and_monitor_operation("ec2", "create_instance")  # Blocked

        report = self.manager.generate_comprehensive_compliance_report()

        self.assertIn("report_id", report)
        self.assertIn("generation_timestamp", report)
        self.assertIn("compliance_status", report)
        self.assertIn("executive_summary", report)
        self.assertIn("recommendations", report)

        # Check executive summary
        exec_summary = report["executive_summary"]
        self.assertIn("overall_compliance", exec_summary)
        self.assertIn("compliance_score", exec_summary)
        self.assertIn("risk_level", exec_summary)

    def test_save_compliance_report(self):
        """Test saving compliance report to file."""
        report = self.manager.generate_comprehensive_compliance_report()

        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            self.manager.save_compliance_report(report, "test_report.json")

            mock_open.assert_called_once_with("test_report.json", "w")
            mock_file.write.assert_called()

    def test_cleanup_audit_logs(self):
        """Test audit log cleanup functionality."""
        # Add some old audit entries
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=100)

        # Mock some old entries
        if self.manager.security_validator:
            # Add a mock old entry
            old_entry = Mock()
            old_entry.timestamp = old_timestamp
            self.manager.security_validator.audit_entries.append(old_entry)

            initial_count = len(self.manager.security_validator.audit_entries)

            self.manager.cleanup_audit_logs(retention_days=30)

            # Should have fewer entries after cleanup
            self.assertLessEqual(
                len(self.manager.security_validator.audit_entries), initial_count
            )

    def test_get_compliance_dashboard_data(self):
        """Test compliance dashboard data generation."""
        # Perform some operations
        self.manager.validate_and_monitor_operation("ec2", "describe_instances")

        dashboard_data = self.manager.get_compliance_dashboard_data()

        self.assertIn("timestamp", dashboard_data)
        self.assertIn("overall_status", dashboard_data)
        self.assertIn("compliance_score", dashboard_data)
        self.assertIn("risk_score", dashboard_data)
        self.assertIn("metrics", dashboard_data)
        self.assertIn("status_indicators", dashboard_data)
        self.assertIn("recent_activity", dashboard_data)
        self.assertIn("recommendations", dashboard_data)

        # Check metrics structure
        metrics = dashboard_data["metrics"]
        self.assertIn("total_operations", metrics)
        self.assertIn("blocked_operations", metrics)
        self.assertIn("error_count", metrics)
        self.assertIn("success_rate", metrics)

    def test_extract_key_findings(self):
        """Test key findings extraction."""
        # Create a mock report with compliance issues
        mock_report = {
            "compliance_status": {
                "is_compliant": False,
                "blocked_operations": 5,
                "risk_score": 75,
                "error_count": 15,
            }
        }

        findings = self.manager._extract_key_findings(mock_report)

        self.assertIsInstance(findings, list)
        self.assertTrue(len(findings) > 0)

        findings_text = " ".join(findings).lower()
        self.assertIn("not fully compliant", findings_text)
        self.assertIn("blocked", findings_text)
        self.assertIn("high risk", findings_text)

    def test_extract_immediate_actions(self):
        """Test immediate actions extraction."""
        # Create a mock report with issues requiring immediate action
        mock_report = {
            "compliance_status": {
                "security_validation_passed": False,
                "risk_score": 85,
                "production_monitoring_active": False,
            }
        }

        actions = self.manager._extract_immediate_actions(mock_report)

        self.assertIsInstance(actions, list)
        self.assertTrue(len(actions) > 0)

        actions_text = " ".join(actions).lower()
        self.assertIn("security", actions_text)
        self.assertIn("monitoring", actions_text)

    def test_get_recent_activity_summary(self):
        """Test recent activity summary generation."""
        # Perform some operations
        self.manager.validate_and_monitor_operation("ec2", "describe_instances")

        summary = self.manager._get_recent_activity_summary()

        self.assertIn("last_24h", summary)
        self.assertIn("last_hour", summary)

        for period in ["last_24h", "last_hour"]:
            self.assertIn("operations", summary[period])
            self.assertIn("errors", summary[period])
            self.assertIn("blocked", summary[period])

    def test_validate_and_monitor_without_security_validator(self):
        """Test operation validation when security validator is disabled."""
        config = ComplianceConfiguration(
            compliance_standard=ComplianceStandard.GENERAL,
            enable_security_validation=False,
            enable_production_monitoring=True,
            enable_cloudtrail_integration=False,
        )

        with patch("boto3.Session"), patch("psutil.cpu_percent"), patch(
            "psutil.virtual_memory"
        ), patch("psutil.disk_usage"):
            manager = ComplianceManager(config)

        mock_operation = Mock(return_value={"result": "success"})

        result = manager.validate_and_monitor_operation(
            service="ec2", operation="describe_instances", operation_func=mock_operation
        )

        self.assertTrue(result["validation_passed"])
        self.assertTrue(result["operation_executed"])
        self.assertIsNone(result["security_validation"])

    def test_validate_and_monitor_without_production_monitor(self):
        """Test operation validation when production monitor is disabled."""
        config = ComplianceConfiguration(
            compliance_standard=ComplianceStandard.GENERAL,
            enable_security_validation=True,
            enable_production_monitoring=False,
        )

        with patch("boto3.Session"):
            manager = ComplianceManager(config)

        mock_operation = Mock(return_value={"result": "success"})

        result = manager.validate_and_monitor_operation(
            service="ec2", operation="describe_instances", operation_func=mock_operation
        )

        self.assertTrue(result["validation_passed"])
        self.assertTrue(result["operation_executed"])
        self.assertEqual(result["monitoring_data"], {})

    def test_compliance_configuration_defaults(self):
        """Test compliance configuration default values."""
        config = ComplianceConfiguration(compliance_standard=ComplianceStandard.GENERAL)

        self.assertTrue(config.enable_security_validation)
        self.assertTrue(config.enable_production_monitoring)
        self.assertTrue(config.enable_cloudtrail_integration)
        self.assertEqual(config.error_threshold, 10)
        self.assertEqual(config.performance_threshold_cpu, 80.0)
        self.assertEqual(config.performance_threshold_memory, 80.0)
        self.assertEqual(config.audit_log_retention_days, 90)

    def test_compliance_status_dataclass(self):
        """Test ComplianceStatus dataclass functionality."""
        status = ComplianceStatus(
            is_compliant=True,
            compliance_score=95.5,
            security_validation_passed=True,
            production_monitoring_active=True,
            total_operations=100,
            blocked_operations=0,
            error_count=2,
            risk_score=15.0,
            last_assessment=datetime.now(timezone.utc),
            recommendations=["Maintain current practices"],
        )

        self.assertTrue(status.is_compliant)
        self.assertEqual(status.compliance_score, 95.5)
        self.assertEqual(status.total_operations, 100)
        self.assertEqual(len(status.recommendations), 1)


if __name__ == "__main__":
    unittest.main()
