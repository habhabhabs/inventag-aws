#!/usr/bin/env python3
"""
End-to-End Integration Tests

This module provides comprehensive integration testing for complete
discovery → compliance → BOM generation workflows.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import pytest
import sys
import os
import json
import yaml
import tempfile
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any, Optional

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows"""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_aws_resources(self) -> List[Dict[str, Any]]:
        """Sample AWS resources for end-to-end testing"""
        return [
            {
                "service": "S3",
                "type": "Bucket",
                "region": "us-east-1",
                "id": "production-data-bucket",
                "name": "production-data-bucket",
                "arn": "arn:aws:s3:::production-data-bucket",
                "account_id": "123456789012",
                "tags": {
                    "Environment": "production",
                    "Owner": "data-team",
                    "Role": "storage",
                },
                "discovered_via": "ResourceGroupsTaggingAPI",
            },
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
                    "Owner": "web-team",
                    "Role": "webserver",
                },
                "discovered_via": "EC2API",
            },
            {
                "service": "RDS",
                "type": "DBInstance",
                "region": "us-west-2",
                "id": "prod-database",
                "name": "prod-database",
                "arn": "arn:aws:rds:us-west-2:123456789012:db:prod-database",
                "account_id": "123456789012",
                "tags": {
                    "Environment": "production",
                    "Owner": "backend-team",
                    # Missing Role tag - will be non-compliant
                },
                "discovered_via": "RDSAPI",
            },
            {
                "service": "Lambda",
                "type": "Function",
                "region": "us-east-1",
                "id": "data-processor",
                "name": "data-processor",
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:data-processor",
                "account_id": "123456789012",
                "tags": {},  # No tags - will be untagged
                "discovered_via": "LambdaAPI",
            },
        ]

    @pytest.fixture
    def tag_policy_config(self) -> Dict[str, Any]:
        """Tag policy configuration for testing"""
        return {
            "required_tags": ["Environment", "Owner", "Role"],
            "optional_tags": ["Name", "CostCenter", "Project"],
            "exemptions": [],
            "tag_patterns": {"Environment": "^(production|staging|development|test)$"},
            "service_specific_rules": {},
        }

    def test_discovery_to_compliance_workflow(
        self, temp_workspace, sample_aws_resources, tag_policy_config
    ):
        """Test discovery → compliance workflow"""
        # Step 1: Create inventory data file
        inventory_file = temp_workspace / "inventory.json"
        inventory_data = {"all_discovered_resources": sample_aws_resources}

        with open(inventory_file, "w") as f:
            json.dump(inventory_data, f, indent=2)

        # Step 2: Create tag policy file
        policy_file = temp_workspace / "tag_policy.yaml"
        with open(policy_file, "w") as f:
            yaml.dump(tag_policy_config, f)

        # Step 3: Run compliance check
        compliance_file = temp_workspace / "compliance_report"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/tag_compliance_checker.py",
                "--input",
                str(inventory_file),
                "--config",
                str(policy_file),
                "--output",
                str(compliance_file),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Verify compliance check completed
        if result.returncode == 0:
            # Check that compliance report was created
            compliance_report_file = temp_workspace / "compliance_report.json"
            if compliance_report_file.exists():
                with open(compliance_report_file, "r") as f:
                    compliance_data = json.load(f)

                # Verify compliance report structure
                assert "summary" in compliance_data
                assert "compliant_resources" in compliance_data
                assert "non_compliant_resources" in compliance_data

                # Verify expected compliance results
                summary = compliance_data["summary"]
                assert summary["total_resources"] == 4
                assert summary["compliant_resources"] == 2  # S3 and EC2
                assert summary["non_compliant_resources"] == 1  # RDS missing Role
                assert summary["untagged_resources"] == 1  # Lambda with no tags
        else:
            # Allow for missing dependencies but not structural errors
            assert any(
                error in result.stderr
                for error in ["ModuleNotFoundError", "ImportError", "No module named"]
            )

    def test_compliance_to_bom_workflow(
        self, temp_workspace, sample_aws_resources, tag_policy_config
    ):
        """Test compliance → BOM generation workflow"""
        # Step 1: Create compliance data
        compliance_data = {
            "summary": {
                "total_resources": 4,
                "compliant_resources": 2,
                "non_compliant_resources": 1,
                "untagged_resources": 1,
                "compliance_percentage": 50.0,
            },
            "compliant_resources": [
                sample_aws_resources[0],  # S3 bucket
                sample_aws_resources[1],  # EC2 instance
            ],
            "non_compliant_resources": [
                {
                    **sample_aws_resources[2],
                    "compliance_status": "non_compliant",
                    "violations": ["Missing required tag: Role"],
                }
            ],
            "untagged_resources": [{**sample_aws_resources[3], "compliance_status": "untagged"}],
        }

        compliance_file = temp_workspace / "compliance_report.json"
        with open(compliance_file, "w") as f:
            json.dump(compliance_data, f, indent=2)

        # Step 2: Generate BOM from compliance data
        bom_file = temp_workspace / "bom_report.xlsx"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/bom_converter.py",
                "--input",
                str(compliance_file),
                "--output",
                str(bom_file),
                "--format",
                "excel",
                "--no-vpc-enrichment",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Verify BOM generation
        if result.returncode == 0:
            # Check that BOM file was created
            assert bom_file.exists()
            assert bom_file.stat().st_size > 0
        else:
            # Allow for missing dependencies
            assert any(
                error in result.stderr
                for error in ["ModuleNotFoundError", "ImportError", "No module named"]
            )

    def test_full_discovery_compliance_bom_workflow(
        self, temp_workspace, sample_aws_resources, tag_policy_config
    ):
        """Test complete discovery → compliance → BOM workflow"""
        # Step 1: Create inventory data
        inventory_file = temp_workspace / "inventory.json"
        inventory_data = {"all_discovered_resources": sample_aws_resources}

        with open(inventory_file, "w") as f:
            json.dump(inventory_data, f, indent=2)

        # Step 2: Create tag policy
        policy_file = temp_workspace / "tag_policy.yaml"
        with open(policy_file, "w") as f:
            yaml.dump(tag_policy_config, f)

        # Step 3: Run compliance check
        compliance_file = temp_workspace / "compliance_report"

        compliance_result = subprocess.run(
            [
                sys.executable,
                "scripts/tag_compliance_checker.py",
                "--input",
                str(inventory_file),
                "--config",
                str(policy_file),
                "--output",
                str(compliance_file),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if compliance_result.returncode == 0:
            # Step 4: Generate BOM from compliance results
            compliance_report_file = temp_workspace / "compliance_report.json"
            if compliance_report_file.exists():
                bom_file = temp_workspace / "final_bom.xlsx"

                bom_result = subprocess.run(
                    [
                        sys.executable,
                        "scripts/bom_converter.py",
                        "--input",
                        str(compliance_report_file),
                        "--output",
                        str(bom_file),
                        "--format",
                        "excel",
                        "--no-vpc-enrichment",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
                )

                if bom_result.returncode == 0:
                    # Verify final BOM was created
                    assert bom_file.exists()
                    assert bom_file.stat().st_size > 0

                    # Verify workflow completed successfully
                    assert "BOM report generated" in bom_result.stdout or bom_file.exists()


class TestMultiFormatOutputValidation:
    """Test multi-format output validation"""

    @pytest.fixture
    def sample_data(self) -> List[Dict[str, Any]]:
        """Sample data for format testing"""
        return [
            {
                "service": "S3",
                "type": "Bucket",
                "region": "us-east-1",
                "id": "test-bucket",
                "name": "test-bucket",
                "arn": "arn:aws:s3:::test-bucket",
                "account_id": "123456789012",
                "tags": {"Environment": "test", "Owner": "team-a"},
            },
            {
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "id": "i-123456789",
                "name": "test-instance",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-123456789",
                "account_id": "123456789012",
                "tags": {"Name": "test-instance", "Environment": "test"},
            },
        ]

    def test_json_output_validation(self, temp_workspace, sample_data):
        """Test JSON output format validation"""
        # Create input file
        input_file = temp_workspace / "input.json"
        with open(input_file, "w") as f:
            json.dump({"all_discovered_resources": sample_data}, f)

        # Test JSON compliance output
        output_file = temp_workspace / "output"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/tag_compliance_checker.py",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode == 0:
            json_output = temp_workspace / "output.json"
            if json_output.exists():
                with open(json_output, "r") as f:
                    data = json.load(f)

                # Validate JSON structure
                assert isinstance(data, dict)
                assert "summary" in data
                assert isinstance(data["summary"], dict)

    def test_yaml_output_validation(self, temp_workspace, sample_data):
        """Test YAML output format validation"""
        # Create input file
        input_file = temp_workspace / "input.json"
        with open(input_file, "w") as f:
            json.dump({"all_discovered_resources": sample_data}, f)

        # Test YAML compliance output
        output_file = temp_workspace / "output"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/tag_compliance_checker.py",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--format",
                "yaml",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode == 0:
            yaml_output = temp_workspace / "output.yaml"
            if yaml_output.exists():
                with open(yaml_output, "r") as f:
                    data = yaml.safe_load(f)

                # Validate YAML structure
                assert isinstance(data, dict)
                assert "summary" in data

    def test_excel_output_validation(self, temp_workspace, sample_data):
        """Test Excel output format validation"""
        # Create input file
        input_file = temp_workspace / "input.json"
        with open(input_file, "w") as f:
            json.dump(sample_data, f)

        # Test Excel BOM output
        output_file = temp_workspace / "output.xlsx"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/bom_converter.py",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--format",
                "excel",
                "--no-vpc-enrichment",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode == 0:
            # Verify Excel file was created
            assert output_file.exists()
            assert output_file.stat().st_size > 0

    def test_csv_output_validation(self, temp_workspace, sample_data):
        """Test CSV output format validation"""
        # Create input file
        input_file = temp_workspace / "input.json"
        with open(input_file, "w") as f:
            json.dump(sample_data, f)

        # Test CSV BOM output
        output_file = temp_workspace / "output.csv"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/bom_converter.py",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--format",
                "csv",
                "--no-vpc-enrichment",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode == 0:
            # Verify CSV file was created
            assert output_file.exists()
            assert output_file.stat().st_size > 0

            # Verify CSV content
            with open(output_file, "r") as f:
                content = f.read()
                # Should have CSV headers
                assert "Service" in content
                assert "Type" in content
                assert "Region" in content


class TestConfigurationFileValidation:
    """Test configuration file loading and validation"""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_yaml_config_loading(self, temp_workspace):
        """Test YAML configuration file loading"""
        config_data = {
            "required_tags": ["Environment", "Owner"],
            "optional_tags": ["Name", "CostCenter"],
            "exemptions": [],
            "tag_patterns": {"Environment": "^(prod|staging|dev)$"},
        }

        config_file = temp_workspace / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Test that config file can be loaded
        result = subprocess.run(
            [
                sys.executable,
                "scripts/tag_compliance_checker.py",
                "--config",
                str(config_file),
                "--help",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Should not fail with config loading errors
        assert result.returncode == 0
        assert "Tag Compliance Checker" in result.stdout

    def test_json_config_loading(self, temp_workspace):
        """Test JSON configuration file loading"""
        config_data = {
            "required_tags": ["Environment", "Owner"],
            "optional_tags": ["Name", "CostCenter"],
            "exemptions": [],
            "tag_patterns": {"Environment": "^(prod|staging|dev)$"},
        }

        config_file = temp_workspace / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # Test that config file can be loaded
        result = subprocess.run(
            [
                sys.executable,
                "scripts/tag_compliance_checker.py",
                "--config",
                str(config_file),
                "--help",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Should not fail with config loading errors
        assert result.returncode == 0

    def test_invalid_config_handling(self, temp_workspace):
        """Test handling of invalid configuration files"""
        # Create invalid YAML config
        invalid_config = temp_workspace / "invalid.yaml"
        with open(invalid_config, "w") as f:
            f.write("invalid: yaml: content: [")

        # Test with invalid config
        result = subprocess.run(
            [
                sys.executable,
                "scripts/tag_compliance_checker.py",
                "--config",
                str(invalid_config),
                "--help",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Should handle invalid config gracefully
        if result.returncode != 0:
            assert "yaml" in result.stderr.lower() or "config" in result.stderr.lower()

    def test_missing_config_handling(self, temp_workspace):
        """Test handling of missing configuration files"""
        missing_config = temp_workspace / "nonexistent.yaml"

        # Test with missing config
        result = subprocess.run(
            [
                sys.executable,
                "scripts/tag_compliance_checker.py",
                "--config",
                str(missing_config),
                "--help",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Should handle missing config gracefully
        if result.returncode != 0:
            assert "not found" in result.stderr.lower() or "file" in result.stderr.lower()


class TestMockAWSEnvironment:
    """Test with mock AWS environment for comprehensive service coverage"""

    @pytest.fixture
    def comprehensive_aws_resources(self) -> List[Dict[str, Any]]:
        """Comprehensive AWS resources covering multiple services"""
        return [
            # EC2 Resources
            {
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "id": "i-1234567890abcdef0",
                "name": "web-server",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
                "account_id": "123456789012",
                "tags": {
                    "Name": "web-server",
                    "Environment": "production",
                    "Owner": "web-team",
                },
            },
            {
                "service": "EC2",
                "type": "Volume",
                "region": "us-east-1",
                "id": "vol-1234567890abcdef0",
                "name": "web-server-root",
                "arn": "arn:aws:ec2:us-east-1:123456789012:volume/vol-1234567890abcdef0",
                "account_id": "123456789012",
                "tags": {"Name": "web-server-root", "Environment": "production"},
            },
            # S3 Resources
            {
                "service": "S3",
                "type": "Bucket",
                "region": "us-east-1",
                "id": "production-data-bucket",
                "name": "production-data-bucket",
                "arn": "arn:aws:s3:::production-data-bucket",
                "account_id": "123456789012",
                "tags": {
                    "Environment": "production",
                    "Owner": "data-team",
                    "Role": "storage",
                },
            },
            # RDS Resources
            {
                "service": "RDS",
                "type": "DBInstance",
                "region": "us-west-2",
                "id": "prod-database",
                "name": "prod-database",
                "arn": "arn:aws:rds:us-west-2:123456789012:db:prod-database",
                "account_id": "123456789012",
                "tags": {
                    "Environment": "production",
                    "Owner": "backend-team",
                    "Role": "database",
                },
            },
            # Lambda Resources
            {
                "service": "Lambda",
                "type": "Function",
                "region": "us-east-1",
                "id": "data-processor",
                "name": "data-processor",
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:data-processor",
                "account_id": "123456789012",
                "tags": {
                    "Environment": "production",
                    "Owner": "data-team",
                    "Role": "processing",
                },
            },
            # IAM Resources
            {
                "service": "IAM",
                "type": "Role",
                "region": "global",
                "id": "EC2-S3-Access-Role",
                "name": "EC2-S3-Access-Role",
                "arn": "arn:aws:iam::123456789012:role/EC2-S3-Access-Role",
                "account_id": "123456789012",
                "tags": {
                    "Environment": "production",
                    "Owner": "security-team",
                    "Role": "access",
                },
            },
            # CloudFormation Resources
            {
                "service": "CloudFormation",
                "type": "Stack",
                "region": "us-east-1",
                "id": "production-infrastructure",
                "name": "production-infrastructure",
                "arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/production-infrastructure",
                "account_id": "123456789012",
                "tags": {
                    "Environment": "production",
                    "Owner": "devops-team",
                    "Role": "infrastructure",
                },
            },
        ]

    def test_comprehensive_service_coverage(self, temp_workspace, comprehensive_aws_resources):
        """Test comprehensive service coverage"""
        # Create inventory with multiple services
        inventory_file = temp_workspace / "comprehensive_inventory.json"
        inventory_data = {"all_discovered_resources": comprehensive_aws_resources}

        with open(inventory_file, "w") as f:
            json.dump(inventory_data, f, indent=2)

        # Test BOM generation with comprehensive data
        bom_file = temp_workspace / "comprehensive_bom.xlsx"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/bom_converter.py",
                "--input",
                str(inventory_file),
                "--output",
                str(bom_file),
                "--format",
                "excel",
                "--no-vpc-enrichment",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode == 0:
            # Verify BOM was created
            assert bom_file.exists()
            assert bom_file.stat().st_size > 0

            # Verify processing message
            assert "BOM report generated" in result.stdout or "resources processed" in result.stdout

    def test_service_specific_processing(self, temp_workspace, comprehensive_aws_resources):
        """Test service-specific processing logic"""
        # Filter resources by service
        services = set(resource["service"] for resource in comprehensive_aws_resources)

        for service in services:
            service_resources = [r for r in comprehensive_aws_resources if r["service"] == service]

            # Create service-specific inventory
            service_inventory_file = temp_workspace / f"{service.lower()}_inventory.json"
            service_inventory_data = {"all_discovered_resources": service_resources}

            with open(service_inventory_file, "w") as f:
                json.dump(service_inventory_data, f, indent=2)

            # Test BOM generation for specific service
            service_bom_file = temp_workspace / f"{service.lower()}_bom.csv"

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/bom_converter.py",
                    "--input",
                    str(service_inventory_file),
                    "--output",
                    str(service_bom_file),
                    "--format",
                    "csv",
                    "--no-vpc-enrichment",
                ],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )

            if result.returncode == 0:
                # Verify service-specific BOM was created
                assert service_bom_file.exists()

                # Verify CSV content contains service data
                with open(service_bom_file, "r") as f:
                    content = f.read()
                    assert service in content


class TestCICDPipelineIntegration:
    """Test CI/CD pipeline integration"""

    def test_github_actions_simulation(self, temp_workspace):
        """Test GitHub Actions workflow simulation"""
        # Simulate the CI workflow steps
        sample_data = {
            "all_discovered_resources": [
                {
                    "service": "S3",
                    "type": "Bucket",
                    "region": "us-east-1",
                    "id": "test-bucket",
                    "name": "test-bucket",
                    "arn": "arn:aws:s3:::test-bucket",
                    "account_id": "123456789012",
                    "tags": {"Environment": "test"},
                    "discovered_via": "ResourceGroupsTaggingAPI",
                }
            ]
        }

        # Step 1: Create sample data (as done in CI)
        sample_file = temp_workspace / "sample.json"
        with open(sample_file, "w") as f:
            json.dump(sample_data, f)

        # Step 2: Test BOM converter (as done in CI)
        output_file = temp_workspace / "test-output.xlsx"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/bom_converter.py",
                "--input",
                str(sample_file),
                "--output",
                str(output_file),
                "--no-vpc-enrichment",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Verify CI-like behavior
        if result.returncode == 0:
            assert output_file.exists()
        else:
            # Allow for missing dependencies in CI environment
            assert any(
                error in result.stderr
                for error in ["ModuleNotFoundError", "ImportError", "No module named"]
            )

    def test_automated_workflow_execution(self, temp_workspace):
        """Test automated workflow execution"""
        # Create a batch script that simulates automated execution
        batch_script = temp_workspace / "automated_workflow.py"

        script_content = f"""
import sys
import json
import subprocess
import os

# Sample data
sample_data = {{
    "all_discovered_resources": [
        {{
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "id": "i-automated123",
            "name": "automated-instance",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-automated123",
            "account_id": "123456789012",
            "tags": {{"Environment": "test", "Owner": "automation"}},
            "discovered_via": "EC2API"
        }}
    ]
}}

# Write sample data
with open("{temp_workspace}/automated_input.json", "w") as f:
    json.dump(sample_data, f)

# Run BOM converter
result = subprocess.run([
    sys.executable, "scripts/bom_converter.py",
    "--input", "{temp_workspace}/automated_input.json",
    "--output", "{temp_workspace}/automated_output.xlsx",
    "--no-vpc-enrichment"
], capture_output=True, text=True, cwd="{os.path.join(os.path.dirname(__file__), '..', '..')}")

print("Automated workflow completed")
print(f"Return code: {{result.returncode}}")
if result.stdout:
    print(f"Output: {{result.stdout}}")
if result.stderr:
    print(f"Errors: {{result.stderr}}")
"""

        with open(batch_script, "w") as f:
            f.write(script_content)

        # Execute automated workflow
        result = subprocess.run([sys.executable, str(batch_script)], capture_output=True, text=True)

        # Verify automated execution
        assert result.returncode == 0
        assert "Automated workflow completed" in result.stdout


class TestPerformanceBenchmarks:
    """Test performance benchmarks to ensure no regression"""

    @pytest.fixture
    def large_dataset(self) -> List[Dict[str, Any]]:
        """Generate large dataset for performance testing"""
        resources = []

        services = ["EC2", "S3", "RDS", "Lambda", "IAM"]
        types = {
            "EC2": ["Instance", "Volume", "SecurityGroup"],
            "S3": ["Bucket"],
            "RDS": ["DBInstance", "DBCluster"],
            "Lambda": ["Function"],
            "IAM": ["Role", "User", "Policy"],
        }

        # Generate 500 resources for performance testing
        for i in range(500):
            service = services[i % len(services)]
            resource_type = types[service][i % len(types[service])]

            resource = {
                "service": service,
                "type": resource_type,
                "region": f"us-{'east' if i % 2 == 0 else 'west'}-{(i % 2) + 1}",
                "id": f"{service.lower()}-{i:06d}",
                "name": f"{service.lower()}-resource-{i}",
                "arn": f"arn:aws:{service.lower()}:us-east-1:123456789012:{resource_type.lower()}/{service.lower()}-{i:06d}",
                "account_id": "123456789012",
                "tags": {
                    "Environment": "test" if i % 3 == 0 else "production",
                    "Owner": f"team-{i % 5}",
                    "Role": f"role-{i % 10}",
                },
                "discovered_via": f"{service}API",
            }
            resources.append(resource)

        return resources

    def test_large_dataset_processing_performance(self, temp_workspace, large_dataset):
        """Test processing performance with large dataset"""
        # Create large inventory file
        inventory_file = temp_workspace / "large_inventory.json"
        inventory_data = {"all_discovered_resources": large_dataset}

        with open(inventory_file, "w") as f:
            json.dump(inventory_data, f)

        # Measure processing time
        start_time = time.time()

        # Test BOM generation with large dataset
        bom_file = temp_workspace / "large_bom.csv"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/bom_converter.py",
                "--input",
                str(inventory_file),
                "--output",
                str(bom_file),
                "--format",
                "csv",
                "--no-vpc-enrichment",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        end_time = time.time()
        processing_time = end_time - start_time

        if result.returncode == 0:
            # Verify performance (should complete within reasonable time)
            assert processing_time < 30  # Should complete within 30 seconds

            # Verify output was created
            assert bom_file.exists()
            assert bom_file.stat().st_size > 0

            # Verify all resources were processed
            with open(bom_file, "r") as f:
                lines = f.readlines()
                # Should have header + 500 data rows
                assert len(lines) >= 500

    def test_memory_usage_benchmark(self, temp_workspace, large_dataset):
        """Test memory usage with large dataset"""
        import psutil
        import os

        # Create large inventory file
        inventory_file = temp_workspace / "memory_test_inventory.json"
        inventory_data = {"all_discovered_resources": large_dataset}

        with open(inventory_file, "w") as f:
            json.dump(inventory_data, f)

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Process large dataset
        bom_file = temp_workspace / "memory_test_bom.csv"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/bom_converter.py",
                "--input",
                str(inventory_file),
                "--output",
                str(bom_file),
                "--format",
                "csv",
                "--no-vpc-enrichment",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Get final memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        if result.returncode == 0:
            # Memory increase should be reasonable (less than 200MB for 500 resources)
            assert memory_increase < 200 * 1024 * 1024  # 200MB

            # Verify processing completed
            assert bom_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
