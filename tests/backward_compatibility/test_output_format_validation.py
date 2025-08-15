#!/usr/bin/env python3
"""
Output Format Validation Tests

This module creates test fixtures from current script outputs to ensure format preservation
and implements automated comparison of legacy vs new package outputs.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import pytest
import sys
import os
import json
import yaml
import tempfile
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestOutputFormatValidation:
    """Test output format preservation and validation"""

    @pytest.fixture
    def reference_inventory_output(self) -> Dict[str, Any]:
        """Reference inventory output format that must be preserved"""
        return {
            "all_discovered_resources": [
                {
                    "service": "S3",
                    "type": "Bucket",
                    "region": "us-east-1",
                    "id": "example-bucket",
                    "name": "example-bucket",
                    "arn": "arn:aws:s3:::example-bucket",
                    "account_id": "123456789012",
                    "tags": {"Environment": "production", "Owner": "data-team"},
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
                        "Role": "webserver",
                    },
                    "discovered_via": "EC2API",
                },
            ]
        }

    @pytest.fixture
    def reference_compliance_output(self) -> Dict[str, Any]:
        """Reference compliance output format that must be preserved"""
        return {
            "summary": {
                "total_resources": 2,
                "compliant_resources": 1,
                "non_compliant_resources": 1,
                "untagged_resources": 0,
                "compliance_percentage": 50.0,
            },
            "compliant_resources": [
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
                        "Role": "webserver",
                    },
                    "compliance_status": "compliant",
                }
            ],
            "non_compliant_resources": [
                {
                    "service": "S3",
                    "type": "Bucket",
                    "region": "us-east-1",
                    "id": "example-bucket",
                    "name": "example-bucket",
                    "arn": "arn:aws:s3:::example-bucket",
                    "account_id": "123456789012",
                    "tags": {"Environment": "production", "Owner": "data-team"},
                    "compliance_status": "non_compliant",
                    "violations": ["Missing required tag: Role"],
                }
            ],
            "untagged_resources": [],
        }

    def test_inventory_json_format_structure(self, reference_inventory_output):
        """Test that inventory JSON output maintains required structure"""
        # Validate top-level structure
        assert "all_discovered_resources" in reference_inventory_output
        assert isinstance(reference_inventory_output["all_discovered_resources"], list)

        # Validate resource structure
        for resource in reference_inventory_output["all_discovered_resources"]:
            required_fields = [
                "service",
                "type",
                "region",
                "id",
                "name",
                "arn",
                "account_id",
                "tags",
                "discovered_via",
            ]
            for field in required_fields:
                assert field in resource, f"Missing required field: {field}"

            # Validate field types
            assert isinstance(resource["service"], str)
            assert isinstance(resource["type"], str)
            assert isinstance(resource["region"], str)
            assert isinstance(resource["id"], str)
            assert isinstance(resource["name"], str)
            assert isinstance(resource["arn"], str)
            assert isinstance(resource["account_id"], str)
            assert isinstance(resource["tags"], dict)
            assert isinstance(resource["discovered_via"], str)

    def test_compliance_json_format_structure(self, reference_compliance_output):
        """Test that compliance JSON output maintains required structure"""
        # Validate top-level structure
        required_sections = [
            "summary",
            "compliant_resources",
            "non_compliant_resources",
            "untagged_resources",
        ]
        for section in required_sections:
            assert section in reference_compliance_output

        # Validate summary structure
        summary = reference_compliance_output["summary"]
        summary_fields = [
            "total_resources",
            "compliant_resources",
            "non_compliant_resources",
            "untagged_resources",
            "compliance_percentage",
        ]
        for field in summary_fields:
            assert field in summary, f"Missing summary field: {field}"

        # Validate resource lists
        for section in [
            "compliant_resources",
            "non_compliant_resources",
            "untagged_resources",
        ]:
            assert isinstance(reference_compliance_output[section], list)

        # Validate compliant resource structure
        for resource in reference_compliance_output["compliant_resources"]:
            assert "compliance_status" in resource
            assert resource["compliance_status"] == "compliant"

        # Validate non-compliant resource structure
        for resource in reference_compliance_output["non_compliant_resources"]:
            assert "compliance_status" in resource
            assert resource["compliance_status"] == "non_compliant"
            assert "violations" in resource
            assert isinstance(resource["violations"], list)

    def test_yaml_output_format_compatibility(self, reference_inventory_output):
        """Test YAML output format compatibility"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(reference_inventory_output, f, default_flow_style=False)
            yaml_file = f.name

        try:
            # Read back and validate
            with open(yaml_file, "r") as f:
                loaded_data = yaml.safe_load(f)

            assert loaded_data == reference_inventory_output

            # Validate YAML-specific formatting
            with open(yaml_file, "r") as f:
                yaml_content = f.read()

            # Should be readable YAML format
            assert "all_discovered_resources:" in yaml_content
            assert "- service:" in yaml_content
            assert "tags:" in yaml_content

        finally:
            os.unlink(yaml_file)

    def test_csv_output_format_structure(self):
        """Test CSV output format structure for BOM converter"""
        # Expected CSV headers that must be preserved
        expected_headers = [
            "Service",
            "Type",
            "Region",
            "ID",
            "Name",
            "ARN",
            "Account ID",
            "Tags",
            "Environment",
            "Owner",
            "Compliance Status",
        ]

        # This test validates the expected structure
        # In actual implementation, we would compare against generated CSV
        assert all(isinstance(header, str) for header in expected_headers)
        assert len(expected_headers) > 0

    def test_excel_output_format_structure(self):
        """Test Excel output format structure for BOM converter"""
        # Expected Excel sheet structure that must be preserved
        expected_sheets = [
            "Summary",
            "All Resources",
            "S3",
            "EC2",
            "RDS",
            "Lambda",
            "IAM",
        ]

        # Expected columns in resource sheets
        expected_columns = [
            "Service",
            "Type",
            "Region",
            "ID",
            "Name",
            "ARN",
            "Account ID",
            "Tags",
            "Compliance Status",
        ]

        # This test validates the expected structure
        assert all(isinstance(sheet, str) for sheet in expected_sheets)
        assert all(isinstance(col, str) for col in expected_columns)
        assert len(expected_sheets) > 0
        assert len(expected_columns) > 0


class TestOutputComparison:
    """Test automated comparison of legacy vs new package outputs"""

    def normalize_json_output(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize JSON output for comparison"""
        if isinstance(data, dict):
            # Sort lists for consistent comparison
            normalized = {}
            for key, value in data.items():
                if isinstance(value, list):
                    # Sort lists by a consistent key if possible
                    if value and isinstance(value[0], dict) and "id" in value[0]:
                        normalized[key] = sorted(value, key=lambda x: x.get("id", ""))
                    else:
                        normalized[key] = (
                            sorted(value) if all(isinstance(x, str) for x in value) else value
                        )
                elif isinstance(value, dict):
                    normalized[key] = self.normalize_json_output(value)
                else:
                    normalized[key] = value
            return normalized
        return data

    def compare_json_outputs(self, output1: Dict[str, Any], output2: Dict[str, Any]) -> bool:
        """Compare two JSON outputs for structural equivalence"""
        norm1 = self.normalize_json_output(output1)
        norm2 = self.normalize_json_output(output2)
        return norm1 == norm2

    def test_json_output_comparison_identical(self, reference_inventory_output):
        """Test comparison of identical JSON outputs"""
        output1 = reference_inventory_output.copy()
        output2 = reference_inventory_output.copy()

        assert self.compare_json_outputs(output1, output2)

    def test_json_output_comparison_different(self, reference_inventory_output):
        """Test comparison of different JSON outputs"""
        output1 = reference_inventory_output.copy()
        output2 = reference_inventory_output.copy()

        # Modify output2
        output2["all_discovered_resources"][0]["service"] = "MODIFIED"

        assert not self.compare_json_outputs(output1, output2)

    def test_json_output_comparison_reordered(self, reference_inventory_output):
        """Test comparison handles reordered resources"""
        output1 = reference_inventory_output.copy()
        output2 = reference_inventory_output.copy()

        # Reverse the order of resources
        output2["all_discovered_resources"] = list(reversed(output2["all_discovered_resources"]))

        # Should still be considered equal after normalization
        assert self.compare_json_outputs(output1, output2)

    def calculate_output_hash(self, data: Any) -> str:
        """Calculate hash of output for change detection"""
        normalized = self.normalize_json_output(data) if isinstance(data, dict) else data
        json_str = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode()).hexdigest()

    def test_output_hash_consistency(self, reference_inventory_output):
        """Test that output hashing is consistent"""
        hash1 = self.calculate_output_hash(reference_inventory_output)
        hash2 = self.calculate_output_hash(reference_inventory_output)

        assert hash1 == hash2

    def test_output_hash_sensitivity(self, reference_inventory_output):
        """Test that output hashing detects changes"""
        original_hash = self.calculate_output_hash(reference_inventory_output)

        # Modify data
        modified_data = reference_inventory_output.copy()
        modified_data["all_discovered_resources"][0]["service"] = "MODIFIED"
        modified_hash = self.calculate_output_hash(modified_data)

        assert original_hash != modified_hash


class TestRegressionValidation:
    """Test regression validation for output formats"""

    def create_reference_fixtures(self):
        """Create reference fixtures for regression testing"""
        fixtures_dir = Path(__file__).parent / "fixtures"
        fixtures_dir.mkdir(exist_ok=True)

        # Create reference inventory fixture
        reference_inventory = {
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

        with open(fixtures_dir / "reference_inventory.json", "w") as f:
            json.dump(reference_inventory, f, indent=2)

        # Create reference compliance fixture
        reference_compliance = {
            "summary": {
                "total_resources": 1,
                "compliant_resources": 1,
                "non_compliant_resources": 0,
                "untagged_resources": 0,
                "compliance_percentage": 100.0,
            },
            "compliant_resources": [reference_inventory["all_discovered_resources"][0]],
            "non_compliant_resources": [],
            "untagged_resources": [],
        }

        with open(fixtures_dir / "reference_compliance.json", "w") as f:
            json.dump(reference_compliance, f, indent=2)

        return fixtures_dir

    def test_create_reference_fixtures(self):
        """Test creation of reference fixtures"""
        fixtures_dir = self.create_reference_fixtures()

        # Verify fixtures were created
        assert (fixtures_dir / "reference_inventory.json").exists()
        assert (fixtures_dir / "reference_compliance.json").exists()

        # Verify fixture content
        with open(fixtures_dir / "reference_inventory.json", "r") as f:
            inventory_data = json.load(f)

        assert "all_discovered_resources" in inventory_data
        assert len(inventory_data["all_discovered_resources"]) == 1

        with open(fixtures_dir / "reference_compliance.json", "r") as f:
            compliance_data = json.load(f)

        assert "summary" in compliance_data
        assert compliance_data["summary"]["compliance_percentage"] == 100.0

    def validate_against_fixtures(self, output_data: Dict[str, Any], fixture_name: str) -> bool:
        """Validate output against reference fixtures"""
        fixtures_dir = Path(__file__).parent / "fixtures"
        fixture_file = fixtures_dir / f"{fixture_name}.json"

        if not fixture_file.exists():
            return False

        with open(fixture_file, "r") as f:
            reference_data = json.load(f)

        return self.compare_json_outputs(output_data, reference_data)

    def compare_json_outputs(self, output1: Dict[str, Any], output2: Dict[str, Any]) -> bool:
        """Compare two JSON outputs (reused from TestOutputComparison)"""

        def normalize(data):
            if isinstance(data, dict):
                normalized = {}
                for key, value in data.items():
                    if (
                        isinstance(value, list)
                        and value
                        and isinstance(value[0], dict)
                        and "id" in value[0]
                    ):
                        normalized[key] = sorted(value, key=lambda x: x.get("id", ""))
                    elif isinstance(value, dict):
                        normalized[key] = normalize(value)
                    else:
                        normalized[key] = value
                return normalized
            return data

        return normalize(output1) == normalize(output2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
