#!/usr/bin/env python3
"""
Unit tests for InvenTag Security Validator
Tests the read-only access validation and compliance audit logging functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime, timezone
from inventag.compliance.security_validator import (
    ReadOnlyAccessValidator,
    OperationType,
    ComplianceStandard,
    SecurityValidationResult,
    AuditLogEntry,
    ComplianceReport,
)


class TestReadOnlyAccessValidator(unittest.TestCase):
    """Test cases for ReadOnlyAccessValidator."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("boto3.Session"):
            self.validator = ReadOnlyAccessValidator(ComplianceStandard.GENERAL)
            self.validator.user_identity = {
                "user_id": "test_user",
                "account": "123456789012",
                "arn": "arn:aws:iam::123456789012:user/test-user",
                "type": "IAM_USER",
            }

    def test_classify_read_only_operation(self):
        """Test classification of read-only operations."""
        # Test explicit read-only operations
        result = self.validator._classify_operation("ec2", "describe_instances")
        self.assertEqual(result, OperationType.READ_ONLY)

        result = self.validator._classify_operation("s3", "list_buckets")
        self.assertEqual(result, OperationType.READ_ONLY)

        # Test pattern-based read-only operations
        result = self.validator._classify_operation("unknown_service", "describe_something")
        self.assertEqual(result, OperationType.READ_ONLY)

        result = self.validator._classify_operation("unknown_service", "get_configuration")
        self.assertEqual(result, OperationType.READ_ONLY)

    def test_classify_mutating_operation(self):
        """Test classification of mutating operations."""
        # Test explicit mutating patterns
        result = self.validator._classify_operation("ec2", "create_instance")
        self.assertEqual(result, OperationType.MUTATING)

        result = self.validator._classify_operation("s3", "delete_bucket")
        self.assertEqual(result, OperationType.MUTATING)

        result = self.validator._classify_operation("rds", "modify_db_instance")
        self.assertEqual(result, OperationType.MUTATING)

    def test_classify_unknown_operation(self):
        """Test classification of unknown operations."""
        result = self.validator._classify_operation("unknown_service", "unknown_operation")
        self.assertEqual(result, OperationType.UNKNOWN)

    def test_validate_read_only_operation(self):
        """Test validation of read-only operations."""
        result = self.validator.validate_operation("ec2", "describe_instances")

        self.assertTrue(result.is_valid)
        self.assertEqual(result.operation, "describe_instances")
        self.assertEqual(result.operation_type, OperationType.READ_ONLY)
        self.assertEqual(result.risk_level, "LOW")
        self.assertIn("read-only", result.validation_message)

    def test_validate_mutating_operation(self):
        """Test validation blocks mutating operations."""
        result = self.validator.validate_operation("ec2", "create_instance")

        self.assertFalse(result.is_valid)
        self.assertEqual(result.operation, "create_instance")
        self.assertEqual(result.operation_type, OperationType.MUTATING)
        self.assertEqual(result.risk_level, "HIGH")
        self.assertIn("BLOCKED", result.validation_message)

    def test_validate_unknown_operation(self):
        """Test validation blocks unknown operations."""
        result = self.validator.validate_operation("unknown", "unknown_operation")

        self.assertFalse(result.is_valid)
        self.assertEqual(result.operation_type, OperationType.UNKNOWN)
        self.assertEqual(result.risk_level, "MEDIUM")

    def test_assess_risk_level(self):
        """Test risk level assessment."""
        # High risk for mutating operations
        risk = self.validator._assess_risk_level(OperationType.MUTATING, "ec2", "create_instance")
        self.assertEqual(risk, "HIGH")

        # Medium risk for unknown operations
        risk = self.validator._assess_risk_level(OperationType.UNKNOWN, "unknown", "unknown_op")
        self.assertEqual(risk, "MEDIUM")

        # Medium risk for IAM/STS even if read-only
        risk = self.validator._assess_risk_level(OperationType.READ_ONLY, "iam", "list_users")
        self.assertEqual(risk, "MEDIUM")

        # Low risk for normal read-only operations
        risk = self.validator._assess_risk_level(
            OperationType.READ_ONLY, "ec2", "describe_instances"
        )
        self.assertEqual(risk, "LOW")

    def test_general_compliance_notes(self):
        """Test general compliance notes generation."""
        notes = self.validator._generate_compliance_notes(
            OperationType.READ_ONLY, "ec2", "describe_instances"
        )

        self.assertTrue(any("read-only" in note.lower() for note in notes))
        self.assertTrue(any("audit trail" in note.lower() for note in notes))

    def test_audit_entry_creation(self):
        """Test audit entry creation."""
        initial_count = len(self.validator.audit_entries)

        self.validator.validate_operation(
            "ec2",
            "describe_instances",
            resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
        )

        self.assertEqual(len(self.validator.audit_entries), initial_count + 1)

        audit_entry = self.validator.audit_entries[-1]
        self.assertEqual(audit_entry.operation, "describe_instances")
        self.assertEqual(audit_entry.service, "ec2")
        self.assertEqual(audit_entry.operation_type, OperationType.READ_ONLY)
        self.assertEqual(audit_entry.compliance_standard, ComplianceStandard.GENERAL)

    @patch("boto3.Session")
    def test_validate_aws_permissions(self, mock_session):
        """Test AWS permissions validation."""
        # Mock successful operations
        mock_client = Mock()
        mock_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_client.describe_regions.return_value = {"Regions": []}
        mock_client.list_buckets.return_value = {"Buckets": []}

        mock_session.return_value.client.return_value = mock_client

        result = self.validator.validate_aws_permissions()

        self.assertIn("permission_checks", result)
        self.assertIn("overall_status", result)
        self.assertEqual(result["overall_status"], "VALID")

    def test_generate_compliance_report(self):
        """Test general compliance report generation."""
        # Add some test audit entries
        self.validator.validate_operation("ec2", "describe_instances")
        self.validator.validate_operation("s3", "list_buckets")
        self.validator.validate_operation("ec2", "create_instance")  # This should be blocked

        report = self.validator.generate_compliance_report()

        self.assertIsInstance(report, ComplianceReport)
        self.assertEqual(report.total_operations, 3)
        self.assertEqual(report.read_only_operations, 2)
        self.assertEqual(report.mutating_operations_blocked, 1)
        self.assertEqual(report.compliance_standard, "general")
        self.assertLess(
            report.compliance_score, 100
        )  # Should be less than 100% due to blocked operation
        self.assertTrue(len(report.security_findings) > 0)
        self.assertTrue(len(report.recommendations) > 0)

    def test_audit_summary(self):
        """Test audit summary generation."""
        # Add some operations
        self.validator.validate_operation("ec2", "describe_instances")
        self.validator.validate_operation("s3", "create_bucket")  # Should be blocked

        summary = self.validator.get_audit_summary()

        self.assertEqual(summary["total_operations"], 2)
        self.assertEqual(summary["read_only_operations"], 1)
        self.assertEqual(summary["blocked_operations"], 1)
        self.assertEqual(summary["compliance_standard"], "general")
        self.assertIn("user_identity", summary)

    def test_determine_identity_type(self):
        """Test AWS identity type determination."""
        # Test IAM user
        identity_type = self.validator._determine_identity_type(
            "arn:aws:iam::123456789012:user/test-user"
        )
        self.assertEqual(identity_type, "IAM_USER")

        # Test IAM role
        identity_type = self.validator._determine_identity_type(
            "arn:aws:iam::123456789012:role/test-role"
        )
        self.assertEqual(identity_type, "IAM_ROLE")

        # Test assumed role
        identity_type = self.validator._determine_identity_type(
            "arn:aws:sts::123456789012:assumed-role/test-role/session"
        )
        self.assertEqual(identity_type, "ASSUMED_ROLE")

        # Test root user
        identity_type = self.validator._determine_identity_type("arn:aws:iam::123456789012:root")
        self.assertEqual(identity_type, "ROOT_USER")

    def test_blocked_operations_tracking(self):
        """Test that blocked operations are properly tracked."""
        initial_blocked = len(self.validator.blocked_operations)

        # This should be blocked
        self.validator.validate_operation("ec2", "create_instance")
        self.assertEqual(len(self.validator.blocked_operations), initial_blocked + 1)
        self.assertIn("ec2:create_instance", self.validator.blocked_operations)

        # This should not be blocked
        self.validator.validate_operation("ec2", "describe_instances")
        self.assertEqual(len(self.validator.blocked_operations), initial_blocked + 1)

    def test_compliance_report_serialization(self):
        """Test that compliance reports can be serialized to JSON."""
        self.validator.validate_operation("ec2", "describe_instances")
        report = self.validator.generate_compliance_report()

        # Test that the report can be converted to dict and serialized
        report_dict = report.__dict__.copy()

        # Convert datetime objects to strings for JSON serialization
        report_dict["generation_timestamp"] = report_dict["generation_timestamp"].isoformat()
        for entry in report_dict["audit_entries"]:
            entry.timestamp = entry.timestamp.isoformat()

        # Should not raise an exception
        json_str = json.dumps(report_dict, default=str)
        self.assertIsInstance(json_str, str)
        self.assertIn("report_id", json_str)


if __name__ == "__main__":
    unittest.main()
