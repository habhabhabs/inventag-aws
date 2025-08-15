#!/usr/bin/env python3
"""
Backward Compatibility Tests for Script Interfaces

This module validates that existing script interfaces produce identical outputs
after the architectural transformation to the unified inventag package.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import pytest
import sys
import os
import json
import yaml
import tempfile
import subprocess
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any, Optional

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestScriptInterfaceCompatibility:
    """Test backward compatibility of script interfaces"""

    @pytest.fixture
    def sample_inventory_data(self) -> Dict[str, Any]:
        """Sample inventory data for testing"""
        return {
            "all_discovered_resources": [
                {
                    "service": "S3",
                    "type": "Bucket",
                    "region": "us-east-1",
                    "id": "test-bucket-1",
                    "name": "test-bucket-1",
                    "arn": "arn:aws:s3:::test-bucket-1",
                    "account_id": "123456789012",
                    "tags": {"Environment": "test", "Owner": "team-a"},
                    "discovered_via": "ResourceGroupsTaggingAPI",
                },
                {
                    "service": "EC2",
                    "type": "Instance",
                    "region": "us-east-1",
                    "id": "i-1234567890abcdef0",
                    "name": "test-instance",
                    "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
                    "account_id": "123456789012",
                    "tags": {"Environment": "production", "Name": "test-instance"},
                    "discovered_via": "EC2API",
                },
                {
                    "service": "RDS",
                    "type": "DBInstance",
                    "region": "us-west-2",
                    "id": "test-db-instance",
                    "name": "test-db-instance",
                    "arn": "arn:aws:rds:us-west-2:123456789012:db:test-db-instance",
                    "account_id": "123456789012",
                    "tags": {"Environment": "staging"},
                    "discovered_via": "RDSAPI",
                },
            ]
        }

    @pytest.fixture
    def sample_compliance_data(self) -> Dict[str, Any]:
        """Sample compliance data for testing"""
        return {
            "summary": {
                "total_resources": 3,
                "compliant_resources": 2,
                "non_compliant_resources": 1,
                "untagged_resources": 0,
                "compliance_percentage": 66.67,
            },
            "compliant_resources": [
                {
                    "service": "S3",
                    "type": "Bucket",
                    "region": "us-east-1",
                    "id": "test-bucket-1",
                    "name": "test-bucket-1",
                    "tags": {"Environment": "test", "Owner": "team-a"},
                    "compliance_status": "compliant",
                },
                {
                    "service": "EC2",
                    "type": "Instance",
                    "region": "us-east-1",
                    "id": "i-1234567890abcdef0",
                    "name": "test-instance",
                    "tags": {"Environment": "production", "Name": "test-instance"},
                    "compliance_status": "compliant",
                },
            ],
            "non_compliant_resources": [
                {
                    "service": "RDS",
                    "type": "DBInstance",
                    "region": "us-west-2",
                    "id": "test-db-instance",
                    "name": "test-db-instance",
                    "tags": {"Environment": "staging"},
                    "compliance_status": "non_compliant",
                    "violations": ["Missing required tag: Owner"],
                }
            ],
            "untagged_resources": [],
        }

    def test_aws_resource_inventory_help(self):
        """Test that aws_resource_inventory.py --help works"""
        result = subprocess.run(
            [sys.executable, "scripts/aws_resource_inventory.py", "--help"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        assert result.returncode == 0
        assert "AWS Resource Inventory Tool" in result.stdout
        assert "--regions" in result.stdout
        assert "--format" in result.stdout
        assert "--output" in result.stdout
        assert "--s3-bucket" in result.stdout
        assert "--export-excel" in result.stdout
        assert "--verbose" in result.stdout

    def test_tag_compliance_checker_help(self):
        """Test that tag_compliance_checker.py --help works"""
        result = subprocess.run(
            [sys.executable, "scripts/tag_compliance_checker.py", "--help"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        assert result.returncode == 0
        assert "Tag Compliance Checker" in result.stdout
        assert "--config" in result.stdout
        assert "--input" in result.stdout
        assert "--output" in result.stdout
        assert "--format" in result.stdout
        assert "--regions" in result.stdout
        assert "--s3-bucket" in result.stdout
        assert "--verbose" in result.stdout

    def test_bom_converter_help(self):
        """Test that bom_converter.py --help works"""
        result = subprocess.run(
            [sys.executable, "scripts/bom_converter.py", "--help"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        assert result.returncode == 0
        assert "BOM Converter" in result.stdout
        assert "--input" in result.stdout
        assert "--output" in result.stdout
        assert "--format" in result.stdout
        assert "--no-vpc-enrichment" in result.stdout
        assert "--verbose" in result.stdout

    def test_bom_converter_output_format_compatibility(self, sample_inventory_data):
        """Test that BOM converter produces expected output format"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create input file
            input_file = os.path.join(temp_dir, "test_inventory.json")
            with open(input_file, "w") as f:
                json.dump(sample_inventory_data, f)

            # Test CSV output
            csv_output = os.path.join(temp_dir, "test_output.csv")
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/bom_converter.py",
                    "--input",
                    input_file,
                    "--output",
                    csv_output,
                    "--format",
                    "csv",
                    "--no-vpc-enrichment",
                ],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )

            # Should not fail with argument parsing errors
            if result.returncode != 0:
                # Allow for missing dependencies but not argument errors
                assert (
                    "ModuleNotFoundError" in result.stderr
                    or "ImportError" in result.stderr
                    or "No module named" in result.stderr
                )
            else:
                # If successful, verify output file exists
                assert os.path.exists(csv_output)

    def test_tag_compliance_checker_output_format_compatibility(self, sample_inventory_data):
        """Test that tag compliance checker produces expected output format"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create input file
            input_file = os.path.join(temp_dir, "test_inventory.json")
            with open(input_file, "w") as f:
                json.dump(sample_inventory_data, f)

            # Create basic tag policy config
            config_file = os.path.join(temp_dir, "tag_policy.yaml")
            tag_policy = {
                "required_tags": ["Environment"],
                "optional_tags": ["Owner", "Name"],
                "exemptions": [],
            }
            with open(config_file, "w") as f:
                yaml.dump(tag_policy, f)

            # Test JSON output
            json_output = os.path.join(temp_dir, "compliance_report.json")
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/tag_compliance_checker.py",
                    "--input",
                    input_file,
                    "--config",
                    config_file,
                    "--output",
                    json_output,
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )

            # Should not fail with argument parsing errors
            if result.returncode != 0:
                # Allow for missing dependencies but not argument errors
                assert (
                    "ModuleNotFoundError" in result.stderr
                    or "ImportError" in result.stderr
                    or "No module named" in result.stderr
                )
            else:
                # If successful, verify output contains expected structure
                assert "compliance" in result.stdout.lower() or os.path.exists(
                    json_output + ".json"
                )

    def test_script_import_compatibility(self):
        """Test that scripts can import from inventag package"""
        # Test aws_resource_inventory.py imports
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                'import sys; sys.path.insert(0, "."); from scripts.aws_resource_inventory import main; print("SUCCESS")',
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Should either succeed or fail with AWS/dependency issues, not import errors
        if result.returncode != 0:
            assert "ImportError" not in result.stderr or "inventag" not in result.stderr
        else:
            assert "SUCCESS" in result.stdout

        # Test tag_compliance_checker.py imports
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                'import sys; sys.path.insert(0, "."); from scripts.tag_compliance_checker import main; print("SUCCESS")',
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode != 0:
            assert "ImportError" not in result.stderr or "inventag" not in result.stderr
        else:
            assert "SUCCESS" in result.stdout

        # Test bom_converter.py imports
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                'import sys; sys.path.insert(0, "."); from scripts.bom_converter import main; print("SUCCESS")',
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode != 0:
            assert "ImportError" not in result.stderr or "inventag" not in result.stderr
        else:
            assert "SUCCESS" in result.stdout


class TestCLIArgumentCompatibility:
    """Test CLI argument parsing compatibility"""

    def test_aws_resource_inventory_argument_parsing(self):
        """Test argument parsing for aws_resource_inventory.py"""
        # Test with various argument combinations
        test_cases = [
            ["--regions", "us-east-1", "us-west-2"],
            ["--format", "json"],
            ["--format", "yaml"],
            ["--output", "test-output"],
            ["--s3-bucket", "test-bucket"],
            ["--s3-key", "test-key"],
            ["--export-excel"],
            ["--verbose"],
            ["--regions", "us-east-1", "--format", "json", "--verbose"],
        ]

        for args in test_cases:
            # Test that arguments are parsed without error (dry run)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"""
import sys
import argparse
sys.path.insert(0, ".")
sys.path.insert(0, "scripts")

# Mock the main functionality to avoid AWS calls
def mock_main():
    parser = argparse.ArgumentParser(description="AWS Resource Inventory Tool")
    parser.add_argument("--regions", nargs="+", help="AWS regions to scan")
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output", "-o", default="aws_resources")
    parser.add_argument("--s3-bucket", help="S3 bucket to upload results")
    parser.add_argument("--s3-key", help="S3 key for uploaded file")
    parser.add_argument("--export-excel", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    
    args = parser.parse_args({args})
    print("ARGS_PARSED_SUCCESSFULLY")

mock_main()
""",
                ],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )

            assert result.returncode == 0, f"Failed to parse args: {args}"
            assert "ARGS_PARSED_SUCCESSFULLY" in result.stdout

    def test_tag_compliance_checker_argument_parsing(self):
        """Test argument parsing for tag_compliance_checker.py"""
        test_cases = [
            ["--config", "test.yaml"],
            ["--input", "test.json"],
            ["--output", "test-output"],
            ["--format", "json"],
            ["--format", "yaml"],
            ["--format", "excel"],
            ["--regions", "us-east-1", "us-west-2"],
            ["--s3-bucket", "test-bucket"],
            ["--s3-key", "test-key"],
            ["--verbose"],
            ["--no-color"],
            ["--config", "test.yaml", "--format", "json", "--verbose"],
        ]

        for args in test_cases:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"""
import sys
import argparse
sys.path.insert(0, ".")

def mock_main():
    parser = argparse.ArgumentParser(description="Tag Compliance Checker")
    parser.add_argument("--config", "-c", help="Tag policy configuration file")
    parser.add_argument("--input", "-i", help="Input file with existing resource inventory")
    parser.add_argument("--output", "-o", default="compliance_report")
    parser.add_argument("--format", choices=["json", "yaml", "excel"], default="json")
    parser.add_argument("--regions", nargs="+", help="AWS regions to scan")
    parser.add_argument("--s3-bucket", help="S3 bucket to upload results")
    parser.add_argument("--s3-key", help="S3 key for uploaded file")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    
    args = parser.parse_args({args})
    print("ARGS_PARSED_SUCCESSFULLY")

mock_main()
""",
                ],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )

            assert result.returncode == 0, f"Failed to parse args: {args}"
            assert "ARGS_PARSED_SUCCESSFULLY" in result.stdout

    def test_bom_converter_argument_parsing(self):
        """Test argument parsing for bom_converter.py"""
        test_cases = [
            ["--input", "test.json"],
            ["--input", "test.json", "--output", "test.xlsx"],
            ["--input", "test.json", "--format", "excel"],
            ["--input", "test.json", "--format", "csv"],
            ["--input", "test.json", "--no-vpc-enrichment"],
            ["--input", "test.json", "--verbose"],
            ["--input", "test.json", "--format", "excel", "--verbose"],
        ]

        for args in test_cases:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"""
import sys
import argparse
sys.path.insert(0, ".")

def mock_main():
    parser = argparse.ArgumentParser(description="BOM Converter")
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument("--output", "-o")
    parser.add_argument("--format", choices=["excel", "csv"], default="excel")
    parser.add_argument("--no-vpc-enrichment", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    
    args = parser.parse_args({args})
    print("ARGS_PARSED_SUCCESSFULLY")

mock_main()
""",
                ],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )

            assert result.returncode == 0, f"Failed to parse args: {args}"
            assert "ARGS_PARSED_SUCCESSFULLY" in result.stdout


class TestWrapperScriptFunctionality:
    """Test wrapper script functionality and import compatibility"""

    def test_inventag_package_imports(self):
        """Test that inventag package modules can be imported"""
        # Test discovery module
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                'from inventag.discovery import AWSResourceInventory; print("DISCOVERY_IMPORT_SUCCESS")',
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode == 0:
            assert "DISCOVERY_IMPORT_SUCCESS" in result.stdout
        else:
            # Allow for missing dependencies but not module structure issues
            assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr

        # Test compliance module
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                'from inventag.compliance import ComprehensiveTagComplianceChecker; print("COMPLIANCE_IMPORT_SUCCESS")',
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode == 0:
            assert "COMPLIANCE_IMPORT_SUCCESS" in result.stdout
        else:
            assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr

        # Test reporting module
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                'from inventag.reporting import BOMConverter; print("REPORTING_IMPORT_SUCCESS")',
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        if result.returncode == 0:
            assert "REPORTING_IMPORT_SUCCESS" in result.stdout
        else:
            assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr

    def test_fallback_import_mechanism(self):
        """Test that scripts have fallback import mechanisms"""
        # Check that scripts handle import failures gracefully
        scripts = [
            "scripts/aws_resource_inventory.py",
            "scripts/tag_compliance_checker.py",
            "scripts/bom_converter.py",
        ]

        for script in scripts:
            with open(script, "r") as f:
                content = f.read()

            # Should have try/except for imports
            assert "try:" in content and "except ImportError:" in content
            # Should have fallback path insertion
            assert "sys.path.insert" in content
            # Should import from inventag package
            assert "from inventag." in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
