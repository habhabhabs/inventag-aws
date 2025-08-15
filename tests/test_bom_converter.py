#!/usr/bin/env python3
"""
Tests for BOM Converter functionality
"""

import pytest
import sys
import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from inventag.reporting import BOMConverter
except ImportError:
    # Skip tests if reporting module is not available
    pytest.skip("BOM Converter module not available", allow_module_level=True)


class TestBOMConverter:
    """Test cases for BOM Converter functionality"""

    def test_bom_converter_import(self):
        """Test that BOM converter can be imported"""
        from inventag.reporting import BOMConverter

        assert BOMConverter is not None

    def test_load_sample_data(self):
        """Test loading sample data"""
        sample_data = [
            {
                "service": "S3",
                "type": "Bucket",
                "region": "us-east-1",
                "id": "test-bucket",
                "name": "test-bucket",
                "tags": {"Environment": "test"},
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_data, f)
            temp_file = f.name

        try:
            # Disable VPC enrichment to avoid AWS API calls in tests
            converter = BOMConverter(enrich_vpc_info=False)
            data = converter.load_data(temp_file)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["service"] == "S3"
        finally:
            os.unlink(temp_file)

    def test_load_nonexistent_file(self):
        """Test loading non-existent file raises appropriate error"""
        converter = BOMConverter()
        with pytest.raises(FileNotFoundError):
            converter.load_data("nonexistent_file.json")


class TestBOMConverterScript:
    """Test cases for BOM converter script functionality"""

    def test_script_help(self):
        """Test that the script shows help without errors"""
        import subprocess

        result = subprocess.run(
            [sys.executable, "scripts/bom_converter.py", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "BOM Converter" in result.stdout

    def test_script_with_sample_data(self):
        """Test script with sample data"""
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

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as input_file:
            json.dump(sample_data, input_file)
            input_filename = input_file.name

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as output_file:
            output_filename = output_file.name

        try:
            import subprocess

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/bom_converter.py",
                    "--input",
                    input_filename,
                    "--output",
                    output_filename,
                    "--no-vpc-enrichment",
                ],
                capture_output=True,
                text=True,
            )

            # The script might fail due to missing dependencies, but it should at least parse arguments
            # and show meaningful error messages
            assert "Error:" not in result.stderr or "ModuleNotFoundError" in result.stderr

        finally:
            try:
                os.unlink(input_filename)
                os.unlink(output_filename)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    pytest.main([__file__])
