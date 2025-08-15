#!/usr/bin/env python3
"""
Unit Tests for inventag.compliance Module

This module provides comprehensive unit testing for the compliance module
with various policy scenarios and error handling.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import pytest
import sys
import os
import json
import yaml
import tempfile
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    from inventag.compliance import ComprehensiveTagComplianceChecker
except ImportError:
    pytest.skip("Compliance module not available", allow_module_level=True)


class TestComplianceCheckerCore:
    """Test core functionality of ComprehensiveTagComplianceChecker"""

    @pytest.fixture
    def sample_resources(self) -> List[Dict[str, Any]]:
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
    def basic_policy(self) -> Dict[str, Any]:
        """Basic tag policy for testing"""
        return {
            "required_tags": ["Environment", "Owner", "Role"],
            "optional_tags": ["Name", "CostCenter", "Project"],
            "exemptions": [],
            "tag_patterns": {},
            "service_specific_rules": {},
        }

    @pytest.fixture
    def advanced_policy(self) -> Dict[str, Any]:
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
                assert checker.policy == basic_policy
        finally:
            os.unlink(config_file)

    def test_initialization_without_config(self):
        """Test initialization without config file uses defaults"""
        with patch("boto3.Session"):
            checker = ComprehensiveTagComplianceChecker(regions=["us-east-1"])
            assert isinstance(checker.policy, dict)
            assert "required_tags" in checker.policy

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
                checker = ComprehensiveTagComplianceChecker(regions=["us-east-1"])
                loaded_policy = checker._load_policy(config_file)
                assert loaded_policy == basic_policy
        finally:
            os.unlink(config_file)

    def test_load_policy_json(self, basic_policy):
        """Test loading policy from JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(basic_policy, f)
            config_file = f.name

        try:
            with patch("boto3.Session"):
                checker = ComprehensiveTagComplianceChecker(regions=["us-east-1"])
                loaded_policy = checker._load_policy(config_file)
                assert loaded_policy == basic_policy
        finally:
            os.unlink(config_file)

    def test_load_policy_invalid_file(self):
        """Test loading policy from non-existent file"""
        with patch("boto3.Session"):
            checker = ComprehensiveTagComplianceChecker(regions=["us-east-1"])
            with pytest.raises(FileNotFoundError):
                checker._load_policy("nonexistent.yaml")


class TestComplianceValidation:
    """Test compliance validation logic"""

    @pytest.fixture
    def checker(self, basic_policy):
        """Create compliance checker with basic policy"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(basic_policy, f)
            config_file = f.name

        try:
            with patch("boto3.Session"):
                return ComprehensiveTagComplianceChecker(
                    regions=["us-east-1"], config_file=config_file
                )
        finally:
            os.unlink(config_file)

    def test_check_resource_compliance_compliant(self, checker, sample_resources):
        """Test compliance check for compliant resource"""
        compliant_resource = sample_resources[0]  # Has all required tags

        is_compliant, violations = checker._check_resource_compliance(compliant_resource)

        assert is_compliant is True
        assert len(violations) == 0

    def test_check_resource_compliance_missing_tags(self, checker, sample_resources):
        """Test compliance check for resource with missing tags"""
        non_compliant_resource = sample_resources[1]  # Missing Role tag

        is_compliant, violations = checker._check_resource_compliance(non_compliant_resource)

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
        assert "summary" in results
        assert "compliant_resources" in results
        assert "non_compliant_resources" in results
        assert "untagged_resources" in results

        # Validate summary
        summary = results["summary"]
        assert summary["total_resources"] == 3
        assert summary["compliant_resources"] == 1
        assert summary["non_compliant_resources"] == 2
        assert summary["untagged_resources"] == 0  # RDS has empty tags but not None
        assert summary["compliance_percentage"] == 33.33

    def test_check_compliance_empty_resources(self, checker):
        """Test compliance check with empty resource list"""
        results = checker.check_compliance([])

        summary = results["summary"]
        assert summary["total_resources"] == 0
        assert summary["compliant_resources"] == 0
        assert summary["non_compliant_resources"] == 0
        assert summary["compliance_percentage"] == 0.0


class TestAdvancedPolicyFeatures:
    """Test advanced policy features like exemptions and patterns"""

    @pytest.fixture
    def advanced_checker(self, advanced_policy):
        """Create compliance checker with advanced policy"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(advanced_policy, f)
            config_file = f.name

        try:
            with patch("boto3.Session"):
                return ComprehensiveTagComplianceChecker(
                    regions=["us-east-1"], config_file=config_file
                )
        finally:
            os.unlink(config_file)

    def test_exemption_handling(self, advanced_checker):
        """Test that exemptions are properly applied"""
        # Create S3 bucket that matches exemption pattern
        exempt_resource = {
            "service": "S3",
            "type": "Bucket",
            "id": "access-logs",  # Matches .*-logs$ pattern
            "name": "access-logs",
            "tags": {
                "Environment": "production",
                "Owner": "ops-team",
                # Missing Role tag but should be exempt
            },
        }

        is_compliant, violations = advanced_checker._check_resource_compliance(exempt_resource)

        # Should be compliant due to exemption
        assert is_compliant is True
        assert len(violations) == 0

    def test_tag_pattern_validation(self, advanced_checker):
        """Test tag pattern validation"""
        # Resource with invalid Environment tag
        invalid_resource = {
            "service": "EC2",
            "type": "Instance",
            "id": "i-123",
            "name": "test-instance",
            "tags": {
                "Environment": "invalid-env",  # Doesn't match pattern
                "Owner": "team-a",
                "Role": "webserver",
            },
        }

        is_compliant, violations = advanced_checker._check_resource_compliance(invalid_resource)

        assert is_compliant is False
        assert any(
            "Environment" in violation and "pattern" in violation for violation in violations
        )

    def test_service_specific_rules(self, advanced_checker):
        """Test service-specific rules"""
        # Lambda function with service-specific rules
        lambda_resource = {
            "service": "Lambda",
            "type": "Function",
            "id": "test-function",
            "name": "test-function",
            "tags": {
                "Environment": "production",
                "Owner": "dev-team",
                # Only needs Environment and Owner for Lambda
            },
        }

        is_compliant, violations = advanced_checker._check_resource_compliance(lambda_resource)

        # Should be compliant with Lambda-specific rules
        assert is_compliant is True
        assert len(violations) == 0

    def test_pattern_matching_case_sensitivity(self, advanced_checker):
        """Test pattern matching case sensitivity"""
        # Test case-sensitive pattern matching
        resource_upper = {
            "service": "EC2",
            "type": "Instance",
            "id": "i-123",
            "name": "test-instance",
            "tags": {
                "Environment": "PRODUCTION",  # Uppercase
                "Owner": "TEAM-A",  # Uppercase
                "Role": "webserver",
            },
        }

        is_compliant, violations = advanced_checker._check_resource_compliance(resource_upper)

        # Should fail pattern validation (patterns are case-sensitive)
        assert is_compliant is False


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

        # Should handle malformed resources gracefully
        results = checker.check_compliance(malformed_resources)

        assert isinstance(results, dict)
        assert "summary" in results

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

    def test_save_results_json(self, checker_with_results):
        """Test saving results to JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_file = f.name

        try:
            checker_with_results.save_results(output_file, "json")

            # Verify file was created and contains valid JSON
            assert os.path.exists(output_file + ".json")

            with open(output_file + ".json", "r") as f:
                loaded_results = json.load(f)

            assert "summary" in loaded_results
            assert "compliant_resources" in loaded_results

        finally:
            try:
                os.unlink(output_file + ".json")
            except FileNotFoundError:
                pass

    def test_save_results_yaml(self, checker_with_results):
        """Test saving results to YAML file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            output_file = f.name

        try:
            checker_with_results.save_results(output_file, "yaml")

            # Verify file was created and contains valid YAML
            assert os.path.exists(output_file + ".yaml")

            with open(output_file + ".yaml", "r") as f:
                loaded_results = yaml.safe_load(f)

            assert "summary" in loaded_results
            assert "compliant_resources" in loaded_results

        finally:
            try:
                os.unlink(output_file + ".yaml")
            except FileNotFoundError:
                pass

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
        assert summary["compliant_resources"] + summary["non_compliant_resources"] == 1000

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
        is_compliant, violations = checker._check_resource_compliance(malicious_resource)

        # Should complete without hanging
        assert isinstance(is_compliant, bool)
        assert isinstance(violations, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
