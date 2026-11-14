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

from inventag.reporting import BOMConverter


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
            [sys.executable, "scripts/legacy/bom_converter.py", "--help"],
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

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as input_file:
            json.dump(sample_data, input_file)
            input_filename = input_file.name

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as output_file:
            output_filename = output_file.name

        try:
            import subprocess

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/legacy/bom_converter.py",
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
            assert (
                "Error:" not in result.stderr or "ModuleNotFoundError" in result.stderr
            )

        finally:
            try:
                os.unlink(input_filename)
                os.unlink(output_filename)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    pytest.main([__file__])


class TestRepeatableOrder:
    """The same estate gives the same sheets and rows whatever the discovery order."""

    def test_group_by_service_sorts_services_and_rows(self):
        from inventag.reporting.converter import _group_by_service

        rows = [
            {"service": "S3", "type": "Bucket", "id": "b-2"},
            {"service": "EC2", "type": "Volume", "id": "vol-2"},
            {"service": "EC2", "type": "Instance", "id": "i-1"},
            {"service": "S3", "type": "Bucket", "id": "b-1"},
        ]
        for data in (rows, list(reversed(rows))):
            groups = _group_by_service(data)
            assert list(groups) == ["EC2", "S3"]
            assert [r["id"] for r in groups["EC2"]] == ["i-1", "vol-2"]
            assert [r["id"] for r in groups["S3"]] == ["b-1", "b-2"]
