#!/usr/bin/env python3
"""
Unit Tests for inventag.compliance Module

This module provides comprehensive unit testing for the compliance module
with various policy scenarios and error handling.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import pytest
import os
import json
import yaml
import tempfile
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from inventag.compliance import ComprehensiveTagComplianceChecker


@pytest.fixture
def sample_resources() -> List[Dict[str, Any]]:
    """Sample resources for testing"""
    return [
        {
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "id": "i-1234567890abcdef0",
            "name": "web-server-01",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "account_id": "123456789012",
            "tags": {
                "Name": "web-server-01",
                "Environment": "production",
                "Owner": "team-a",
                "Role": "webserver",
            },
        },
        {
            "service": "S3",
            "type": "Bucket",
            "region": "us-east-1",
            "id": "example-bucket",
            "name": "example-bucket",
            "arn": "arn:aws:s3:::example-bucket",
            "account_id": "123456789012",
            "tags": {
                "Environment": "production",
                "Owner": "data-team",
                # Missing Role tag
            },
        },
        {
            "service": "RDS",
            "type": "DBInstance",
            "region": "us-west-2",
            "id": "prod-database",
            "name": "prod-database",
            "arn": "arn:aws:rds:us-west-2:123456789012:db:prod-database",
            "account_id": "123456789012",
            "tags": {},  # No tags
        },
    ]


@pytest.fixture
def basic_policy() -> Dict[str, Any]:
    """Basic tag policy for testing"""
    return {
        "required_tags": ["Environment", "Owner", "Role"],
        "optional_tags": ["Name", "CostCenter", "Project"],
        "exemptions": [],
        "tag_patterns": {},
        "service_specific_rules": {},
    }


@pytest.fixture
def advanced_policy() -> Dict[str, Any]:
    """Advanced tag policy with patterns and exemptions"""
    return {
        "required_tags": ["Environment", "Owner", "Role"],
        "optional_tags": ["Name", "CostCenter", "Project"],
        "exemptions": [
            {
                "service": "S3",
                "type": "Bucket",
                "pattern": ".*-logs$",
                "exempt_tags": ["Role"],
            }
        ],
        "tag_patterns": {
            "Environment": "^(production|staging|development|test)$",
            "Owner": "^[a-z-]+$",
        },
        "service_specific_rules": {
            "Lambda": {
                "required_tags": ["Environment", "Owner"],
                "optional_tags": ["Runtime", "Timeout"],
            }
        },
    }


def _write_policy(tmp_path, policy, suffix=".yaml"):
    path = tmp_path / f"policy{suffix}"
    if suffix == ".json":
        path.write_text(json.dumps(policy))
    else:
        path.write_text(yaml.safe_dump(policy))
    return str(path)


@pytest.fixture
def checker(basic_policy, tmp_path):
    """Compliance checker with the basic policy (no AWS calls)."""
    with patch("boto3.Session"):
        return ComprehensiveTagComplianceChecker(
            regions=["us-east-1"], config_file=_write_policy(tmp_path, basic_policy)
        )


class TestComplianceCheckerCore:
    """Test core functionality of ComprehensiveTagComplianceChecker"""

    def test_initialization_with_config_file(self, basic_policy):
        """Test initialization with config file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(basic_policy, f)
            config_file = f.name

        try:
            with patch("boto3.Session"):
                checker = ComprehensiveTagComplianceChecker(
                    regions=["us-east-1"], config_file=config_file
                )
                assert checker.tag_policy == basic_policy
        finally:
            os.unlink(config_file)

    def test_initialization_without_config(self):
        """Test initialization without config file uses defaults"""
        with patch("boto3.Session"):
            checker = ComprehensiveTagComplianceChecker(regions=["us-east-1"])
            assert checker.tag_policy == {"required_tags": []}

    def test_initialization_with_regions(self):
        """Test initialization with specific regions"""
        regions = ["us-east-1", "us-west-2"]
        with patch("boto3.Session"):
            checker = ComprehensiveTagComplianceChecker(regions=regions)
            assert checker.regions == regions

    def test_load_policy_yaml(self, basic_policy):
        """Test loading policy from YAML file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(basic_policy, f)
            config_file = f.name

        try:
            with patch("boto3.Session"):
                checker = ComprehensiveTagComplianceChecker(
                    regions=["us-east-1"], config_file=config_file
                )
                assert checker._load_tag_policy() == basic_policy
        finally:
            os.unlink(config_file)

    def test_load_policy_json(self, basic_policy):
        """Test loading policy from JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(basic_policy, f)
            config_file = f.name

        try:
            with patch("boto3.Session"):
                checker = ComprehensiveTagComplianceChecker(
                    regions=["us-east-1"], config_file=config_file
                )
                assert checker._load_tag_policy() == basic_policy
        finally:
            os.unlink(config_file)

    def test_load_policy_invalid_file(self):
        """Test loading policy from non-existent file"""
        with patch("boto3.Session"):
            with pytest.raises(FileNotFoundError):
                ComprehensiveTagComplianceChecker(
                    regions=["us-east-1"], config_file="nonexistent.yaml"
                )


class TestComplianceValidation:
    """Test compliance validation logic"""

    def test_check_resource_compliance_compliant(self, checker, sample_resources):
        """Test compliance check for compliant resource"""
        compliant_resource = sample_resources[0]  # Has all required tags

        is_compliant, violations = checker._check_resource_compliance(
            compliant_resource
        )

        assert is_compliant is True
        assert len(violations) == 0

    def test_check_resource_compliance_missing_tags(self, checker, sample_resources):
        """Test compliance check for resource with missing tags"""
        non_compliant_resource = sample_resources[1]  # Missing Role tag

        is_compliant, violations = checker._check_resource_compliance(
            non_compliant_resource
        )

        assert is_compliant is False
        assert len(violations) > 0
        assert any("Role" in violation for violation in violations)

    def test_check_resource_compliance_no_tags(self, checker, sample_resources):
        """Test compliance check for resource with no tags"""
        untagged_resource = sample_resources[2]  # No tags

        is_compliant, violations = checker._check_resource_compliance(untagged_resource)

        assert is_compliant is False
        assert len(violations) == 3  # Missing all 3 required tags

    def test_check_compliance_with_resources(self, checker, sample_resources):
        """Test full compliance check with provided resources"""
        results = checker.check_compliance(sample_resources)

        # Validate results structure
        assert {"summary", "compliant", "non_compliant", "untagged"} <= set(results)

        # Validate summary: EC2 compliant, S3 missing Role, RDS has no tags at all
        summary = results["summary"]
        assert summary["total_resources"] == 3
        assert summary["compliant_resources"] == 1
        assert summary["non_compliant_resources"] == 1
        assert summary["untagged_resources"] == 1
        assert summary["compliance_percentage"] == 33.33
        assert results["non_compliant"][0]["missing_tags"] == ["Role"]
        assert results["untagged"][0]["id"] == "prod-database"

    def test_check_compliance_empty_resources(self, checker):
        """Test compliance check with empty resource list"""
        results = checker.check_compliance([])

        summary = results["summary"]
        assert summary["total_resources"] == 0
        assert summary["compliant_resources"] == 0
        assert summary["non_compliant_resources"] == 0
        assert summary["compliance_percentage"] == 0.0


class TestErrorHandling:
    """Test error handling scenarios"""

    def test_invalid_yaml_config(self):
        """Test handling of invalid YAML config"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")  # Invalid YAML
            config_file = f.name

        try:
            with patch("boto3.Session"):
                with pytest.raises(yaml.YAMLError):
                    ComprehensiveTagComplianceChecker(
                        regions=["us-east-1"], config_file=config_file
                    )
        finally:
            os.unlink(config_file)

    def test_invalid_json_config(self):
        """Test handling of invalid JSON config"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"invalid": json content}')  # Invalid JSON
            config_file = f.name

        try:
            with patch("boto3.Session"):
                with pytest.raises(json.JSONDecodeError):
                    ComprehensiveTagComplianceChecker(
                        regions=["us-east-1"], config_file=config_file
                    )
        finally:
            os.unlink(config_file)

    def test_malformed_resource_handling(self, checker):
        """Test handling of malformed resource data"""
        malformed_resources = [
            {"service": "EC2"},  # Missing required fields
            {"id": "i-123"},  # Missing service
            {},  # Empty resource
            None,  # None resource
        ]

        # Non-dict entries are skipped; dicts without tags count as untagged
        results = checker.check_compliance(malformed_resources)

        assert results["summary"]["total_resources"] == 3
        assert results["summary"]["untagged_resources"] == 3

    def test_missing_tags_field_handling(self, checker):
        """Test handling of resources without tags field"""
        resource_no_tags = {
            "service": "EC2",
            "type": "Instance",
            "id": "i-123",
            "name": "test-instance",
            # Missing tags field entirely
        }

        is_compliant, violations = checker._check_resource_compliance(resource_no_tags)

        # Should treat as non-compliant
        assert is_compliant is False
        assert len(violations) > 0


class TestOutputGeneration:
    """Test output generation and formatting"""

    @pytest.fixture
    def checker_with_results(self, checker, sample_resources):
        """Checker with compliance results"""
        results = checker.check_compliance(sample_resources)
        checker.results = results
        return checker

    @pytest.mark.parametrize("fmt", ["json", "yaml"])
    def test_save_results(self, checker_with_results, tmp_path, fmt):
        """Results are written to the given path, owner-only."""
        output_file = tmp_path / f"results.{fmt}"
        checker_with_results.save_results(str(output_file), fmt)
        loaded = (json.loads if fmt == "json" else yaml.safe_load)(
            output_file.read_text()
        )
        assert loaded["summary"]["total_resources"] == 3
        assert {"compliant", "non_compliant", "untagged"} <= set(loaded)
        if os.name == "posix":
            assert output_file.stat().st_mode & 0o777 == 0o600

    def test_save_results_invalid_format(self, checker_with_results):
        """Test saving results with invalid format"""
        with pytest.raises(ValueError, match="Format must be 'json' or 'yaml'"):
            checker_with_results.save_results("test", "txt")


class TestPerformanceScenarios:
    """Test performance with large datasets"""

    @pytest.fixture
    def large_resource_dataset(self):
        """Generate large dataset for performance testing"""
        resources = []

        # Generate 1000+ resources
        for i in range(1000):
            resource = {
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "id": f"i-{i:010d}abcdef",
                "name": f"instance-{i}",
                "arn": f"arn:aws:ec2:us-east-1:123456789012:instance/i-{i:010d}abcdef",
                "account_id": "123456789012",
                "tags": {
                    "Name": f"instance-{i}",
                    "Environment": "test" if i % 2 == 0 else "production",
                    "Owner": f"team-{i % 5}",
                    "Role": "webserver" if i % 3 == 0 else None,  # Some missing Role
                },
            }

            # Remove Role tag for some resources to create non-compliant ones
            if resource["tags"]["Role"] is None:
                del resource["tags"]["Role"]

            resources.append(resource)

        return resources

    def test_large_dataset_compliance_check(self, checker, large_resource_dataset):
        """Test compliance checking with large dataset (1000+ resources)"""
        results = checker.check_compliance(large_resource_dataset)

        # Verify results structure
        assert "summary" in results
        summary = results["summary"]
        assert summary["total_resources"] == 1000

        # Verify performance - should complete without timeout
        assert (
            summary["compliant_resources"] + summary["non_compliant_resources"] == 1000
        )

    def test_memory_efficiency_large_dataset(self, checker, large_resource_dataset):
        """Test memory efficiency with large dataset"""
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Process large dataset
        results = checker.check_compliance(large_resource_dataset)

        # Get final memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for 1000 resources)
        assert memory_increase < 100 * 1024 * 1024  # 100MB

        # Results should be complete
        assert results["summary"]["total_resources"] == 1000


class TestSecurityValidation:
    """Test security aspects of compliance checking"""

    def test_no_sensitive_data_in_logs(self, checker, sample_resources):
        """Test that sensitive data is not logged"""
        with patch("logging.Logger.info") as mock_log:
            checker.check_compliance(sample_resources)

            # Check that no sensitive data appears in log calls
            for call in mock_log.call_args_list:
                log_message = str(call)
                # Should not contain AWS account IDs or ARNs
                assert "123456789012" not in log_message
                assert "arn:aws:" not in log_message

    def test_policy_validation_security(self, checker):
        """Test that policy validation prevents injection attacks"""
        # Test with potentially malicious regex patterns
        malicious_resource = {
            "service": "EC2",
            "type": "Instance",
            "id": "i-123",
            "name": "test-instance",
            "tags": {
                "Environment": "production",
                "Owner": "team-a",
                "Role": "webserver",
                "MaliciousTag": ".*" * 1000,  # Potentially expensive regex
            },
        }

        # Should handle without causing ReDoS
        is_compliant, violations = checker._check_resource_compliance(
            malicious_resource
        )

        # Should complete without hanging
        assert isinstance(is_compliant, bool)
        assert isinstance(violations, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
