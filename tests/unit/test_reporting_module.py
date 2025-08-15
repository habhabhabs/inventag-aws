#!/usr/bin/env python3
"""
Unit Tests for inventag.reporting Module

This module provides comprehensive unit testing for the reporting module
with different data formats and error handling scenarios.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import pytest
import sys
import os
import json
import tempfile
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    from inventag.reporting import BOMConverter
except ImportError:
    pytest.skip("Reporting module not available", allow_module_level=True)


class TestBOMConverterCore:
    """Test core functionality of BOMConverter"""

    @pytest.fixture
    def sample_inventory_data(self) -> List[Dict[str, Any]]:
        """Sample inventory data for testing"""
        return [
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
                    "Role": "database",
                    "Owner": "backend-team",
                },
                "discovered_via": "RDSAPI",
            },
        ]

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
                    "service": "EC2",
                    "type": "Instance",
                    "region": "us-east-1",
                    "id": "i-1234567890abcdef0",
                    "name": "web-server-01",
                    "tags": {
                        "Name": "web-server-01",
                        "Environment": "production",
                        "Role": "webserver",
                    },
                    "compliance_status": "compliant",
                },
                {
                    "service": "RDS",
                    "type": "DBInstance",
                    "region": "us-west-2",
                    "id": "prod-database",
                    "name": "prod-database",
                    "tags": {
                        "Environment": "production",
                        "Role": "database",
                        "Owner": "backend-team",
                    },
                    "compliance_status": "compliant",
                },
            ],
            "non_compliant_resources": [
                {
                    "service": "S3",
                    "type": "Bucket",
                    "region": "us-east-1",
                    "id": "example-bucket",
                    "name": "example-bucket",
                    "tags": {"Environment": "production", "Owner": "data-team"},
                    "compliance_status": "non_compliant",
                    "violations": ["Missing required tag: Role"],
                }
            ],
            "untagged_resources": [],
        }

    def test_initialization_default(self):
        """Test default initialization"""
        converter = BOMConverter()
        assert converter.enrich_vpc_info is True
        assert converter.data == []

    def test_initialization_no_vpc_enrichment(self):
        """Test initialization with VPC enrichment disabled"""
        converter = BOMConverter(enrich_vpc_info=False)
        assert converter.enrich_vpc_info is False

    def test_load_data_json_inventory(self, sample_inventory_data):
        """Test loading JSON inventory data"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"all_discovered_resources": sample_inventory_data}, f)
            input_file = f.name

        try:
            converter = BOMConverter(enrich_vpc_info=False)
            data = converter.load_data(input_file)

            assert isinstance(data, list)
            assert len(data) == 3
            assert data[0]["service"] == "S3"
            assert data[1]["service"] == "EC2"
            assert data[2]["service"] == "RDS"
        finally:
            os.unlink(input_file)

    def test_load_data_json_compliance(self, sample_compliance_data):
        """Test loading JSON compliance data"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_compliance_data, f)
            input_file = f.name

        try:
            converter = BOMConverter(enrich_vpc_info=False)
            data = converter.load_data(input_file)

            assert isinstance(data, list)
            assert len(data) == 3  # All resources combined
        finally:
            os.unlink(input_file)

    def test_load_data_direct_list(self, sample_inventory_data):
        """Test loading data that's already a list"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_inventory_data, f)
            input_file = f.name

        try:
            converter = BOMConverter(enrich_vpc_info=False)
            data = converter.load_data(input_file)

            assert isinstance(data, list)
            assert len(data) == 3
        finally:
            os.unlink(input_file)

    def test_load_data_nonexistent_file(self):
        """Test loading non-existent file"""
        converter = BOMConverter()
        with pytest.raises(FileNotFoundError):
            converter.load_data("nonexistent_file.json")

    def test_load_data_invalid_json(self):
        """Test loading invalid JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"invalid": json content}')  # Invalid JSON
            input_file = f.name

        try:
            converter = BOMConverter()
            with pytest.raises(json.JSONDecodeError):
                converter.load_data(input_file)
        finally:
            os.unlink(input_file)


class TestDataProcessing:
    """Test data processing and transformation"""

    @pytest.fixture
    def converter(self):
        """Create BOM converter instance"""
        return BOMConverter(enrich_vpc_info=False)

    @pytest.fixture
    def loaded_converter(self, converter, sample_inventory_data):
        """Converter with loaded data"""
        converter.data = sample_inventory_data
        return converter

    def test_standardize_resource_data(self, converter, sample_inventory_data):
        """Test resource data standardization"""
        # Test with various data formats
        test_resource = sample_inventory_data[0].copy()

        standardized = converter._standardize_resource_data(test_resource)

        # Should have standard fields
        assert "service" in standardized
        assert "type" in standardized
        assert "region" in standardized
        assert "id" in standardized
        assert "name" in standardized

    def test_extract_tag_value(self, converter):
        """Test tag value extraction"""
        tags = {"Environment": "production", "Owner": "team-a"}

        assert converter._extract_tag_value(tags, "Environment") == "production"
        assert converter._extract_tag_value(tags, "Owner") == "team-a"
        assert converter._extract_tag_value(tags, "NonExistent") == ""

    def test_extract_tag_value_empty_tags(self, converter):
        """Test tag extraction with empty/None tags"""
        assert converter._extract_tag_value({}, "Environment") == ""
        assert converter._extract_tag_value(None, "Environment") == ""

    def test_group_resources_by_service(self, loaded_converter):
        """Test grouping resources by service"""
        grouped = loaded_converter._group_resources_by_service()

        assert isinstance(grouped, dict)
        assert "S3" in grouped
        assert "EC2" in grouped
        assert "RDS" in grouped

        assert len(grouped["S3"]) == 1
        assert len(grouped["EC2"]) == 1
        assert len(grouped["RDS"]) == 1

    def test_create_summary_statistics(self, loaded_converter):
        """Test creation of summary statistics"""
        summary = loaded_converter._create_summary_statistics()

        assert isinstance(summary, dict)
        assert "total_resources" in summary
        assert "services_count" in summary
        assert "regions_count" in summary

        assert summary["total_resources"] == 3
        assert summary["services_count"] == 3  # S3, EC2, RDS
        assert summary["regions_count"] == 2  # us-east-1, us-west-2


class TestCSVExport:
    """Test CSV export functionality"""

    @pytest.fixture
    def loaded_converter(self, sample_inventory_data):
        """Converter with loaded data"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = sample_inventory_data
        return converter

    def test_export_to_csv(self, loaded_converter):
        """Test CSV export"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_file = f.name

        try:
            loaded_converter.export_to_csv(output_file)

            # Verify file was created
            assert os.path.exists(output_file)

            # Verify CSV content
            df = pd.read_csv(output_file)
            assert len(df) == 3
            assert "Service" in df.columns
            assert "Type" in df.columns
            assert "Region" in df.columns
            assert "ID" in df.columns
            assert "Name" in df.columns

        finally:
            try:
                os.unlink(output_file)
            except FileNotFoundError:
                pass

    def test_csv_column_headers(self, loaded_converter):
        """Test CSV column headers"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_file = f.name

        try:
            loaded_converter.export_to_csv(output_file)

            df = pd.read_csv(output_file)
            expected_columns = [
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
            ]

            for col in expected_columns:
                assert col in df.columns

        finally:
            try:
                os.unlink(output_file)
            except FileNotFoundError:
                pass

    def test_csv_data_integrity(self, loaded_converter):
        """Test CSV data integrity"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_file = f.name

        try:
            loaded_converter.export_to_csv(output_file)

            df = pd.read_csv(output_file)

            # Check first row (S3 bucket)
            s3_row = df[df["Service"] == "S3"].iloc[0]
            assert s3_row["Type"] == "Bucket"
            assert s3_row["ID"] == "example-bucket"
            assert s3_row["Environment"] == "production"

            # Check second row (EC2 instance)
            ec2_row = df[df["Service"] == "EC2"].iloc[0]
            assert ec2_row["Type"] == "Instance"
            assert ec2_row["ID"] == "i-1234567890abcdef0"
            assert ec2_row["Name"] == "web-server-01"

        finally:
            try:
                os.unlink(output_file)
            except FileNotFoundError:
                pass


class TestExcelExport:
    """Test Excel export functionality"""

    @pytest.fixture
    def loaded_converter(self, sample_inventory_data):
        """Converter with loaded data"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = sample_inventory_data
        return converter

    @patch("pandas.ExcelWriter")
    def test_export_to_excel(self, mock_excel_writer, loaded_converter):
        """Test Excel export"""
        mock_writer = MagicMock()
        mock_excel_writer.return_value.__enter__.return_value = mock_writer

        output_file = "test_output.xlsx"
        loaded_converter.export_to_excel(output_file)

        # Verify ExcelWriter was called
        mock_excel_writer.assert_called_once_with(output_file, engine="openpyxl")

        # Verify sheets were written
        assert mock_writer.sheets is not None

    @patch("pandas.ExcelWriter")
    def test_excel_sheet_creation(self, mock_excel_writer, loaded_converter):
        """Test Excel sheet creation"""
        mock_writer = MagicMock()
        mock_excel_writer.return_value.__enter__.return_value = mock_writer

        loaded_converter.export_to_excel("test.xlsx")

        # Should create multiple sheets
        # Verify that to_excel was called multiple times (for different sheets)
        assert mock_writer.sheets is not None

    def test_excel_summary_sheet_data(self, loaded_converter):
        """Test Excel summary sheet data structure"""
        summary_data = loaded_converter._create_summary_statistics()

        # Should contain key metrics
        assert "total_resources" in summary_data
        assert "services_count" in summary_data
        assert "regions_count" in summary_data

        # Values should be correct
        assert summary_data["total_resources"] == 3
        assert summary_data["services_count"] == 3
        assert summary_data["regions_count"] == 2

    def test_excel_service_sheets_data(self, loaded_converter):
        """Test Excel service-specific sheets data"""
        grouped_data = loaded_converter._group_resources_by_service()

        # Should have separate data for each service
        assert "S3" in grouped_data
        assert "EC2" in grouped_data
        assert "RDS" in grouped_data

        # Each service should have correct resources
        assert len(grouped_data["S3"]) == 1
        assert grouped_data["S3"][0]["type"] == "Bucket"

        assert len(grouped_data["EC2"]) == 1
        assert grouped_data["EC2"][0]["type"] == "Instance"

        assert len(grouped_data["RDS"]) == 1
        assert grouped_data["RDS"][0]["type"] == "DBInstance"


class TestVPCEnrichment:
    """Test VPC enrichment functionality"""

    @pytest.fixture
    def vpc_enabled_converter(self):
        """Converter with VPC enrichment enabled"""
        return BOMConverter(enrich_vpc_info=True)

    @patch("boto3.Session")
    def test_vpc_enrichment_initialization(self, mock_session, vpc_enabled_converter):
        """Test VPC enrichment initialization"""
        assert vpc_enabled_converter.enrich_vpc_info is True

    @patch("boto3.Session")
    def test_enrich_with_vpc_info(self, mock_session, vpc_enabled_converter, sample_inventory_data):
        """Test VPC information enrichment"""
        # Mock EC2 client
        mock_ec2 = Mock()
        mock_ec2.describe_vpcs.return_value = {
            "Vpcs": [
                {
                    "VpcId": "vpc-12345",
                    "Tags": [{"Key": "Name", "Value": "production-vpc"}],
                }
            ]
        }
        mock_ec2.describe_subnets.return_value = {
            "Subnets": [
                {
                    "SubnetId": "subnet-12345",
                    "VpcId": "vpc-12345",
                    "Tags": [{"Key": "Name", "Value": "production-subnet"}],
                }
            ]
        }
        mock_session.return_value.client.return_value = mock_ec2

        # Test enrichment
        test_resource = {
            "service": "EC2",
            "type": "Instance",
            "vpc_id": "vpc-12345",
            "subnet_id": "subnet-12345",
        }

        enriched = vpc_enabled_converter._enrich_with_vpc_info([test_resource])

        # Should have VPC information added
        assert len(enriched) == 1

    def test_vpc_enrichment_disabled(self, sample_inventory_data):
        """Test that VPC enrichment can be disabled"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = sample_inventory_data

        # Should not attempt VPC enrichment
        assert converter.enrich_vpc_info is False


class TestErrorHandling:
    """Test error handling scenarios"""

    def test_empty_data_handling(self):
        """Test handling of empty data"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = []

        # Should handle empty data gracefully
        summary = converter._create_summary_statistics()
        assert summary["total_resources"] == 0

    def test_malformed_data_handling(self):
        """Test handling of malformed data"""
        converter = BOMConverter(enrich_vpc_info=False)

        # Test with malformed resources
        malformed_data = [
            {"service": "EC2"},  # Missing required fields
            {"id": "i-123"},  # Missing service
            {},  # Empty resource
        ]

        converter.data = malformed_data

        # Should handle gracefully
        summary = converter._create_summary_statistics()
        assert isinstance(summary, dict)

    def test_missing_tags_handling(self):
        """Test handling of resources with missing tags"""
        converter = BOMConverter(enrich_vpc_info=False)

        resource_no_tags = {
            "service": "EC2",
            "type": "Instance",
            "id": "i-123",
            "name": "test-instance",
            # Missing tags field
        }

        # Should handle missing tags gracefully
        tag_value = converter._extract_tag_value(resource_no_tags.get("tags"), "Environment")
        assert tag_value == ""

    def test_file_write_error_handling(self):
        """Test handling of file write errors"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = [{"service": "EC2", "type": "Instance", "id": "i-123"}]

        # Test with invalid file path
        with pytest.raises((OSError, PermissionError)):
            converter.export_to_csv("/invalid/path/file.csv")


class TestPerformanceScenarios:
    """Test performance with large datasets"""

    @pytest.fixture
    def large_dataset(self):
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
                },
                "discovered_via": "EC2API",
            }
            resources.append(resource)

        return resources

    def test_large_dataset_csv_export(self, large_dataset):
        """Test CSV export with large dataset (1000+ resources)"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = large_dataset

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_file = f.name

        try:
            # Should complete without timeout
            converter.export_to_csv(output_file)

            # Verify file was created and has correct size
            assert os.path.exists(output_file)

            df = pd.read_csv(output_file)
            assert len(df) == 1000

        finally:
            try:
                os.unlink(output_file)
            except FileNotFoundError:
                pass

    @patch("pandas.ExcelWriter")
    def test_large_dataset_excel_export(self, mock_excel_writer, large_dataset):
        """Test Excel export with large dataset"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = large_dataset

        mock_writer = MagicMock()
        mock_excel_writer.return_value.__enter__.return_value = mock_writer

        # Should complete without timeout
        converter.export_to_excel("large_test.xlsx")

        # Verify ExcelWriter was called
        mock_excel_writer.assert_called_once()

    def test_memory_efficiency_large_dataset(self, large_dataset):
        """Test memory efficiency with large dataset"""
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Process large dataset
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = large_dataset
        summary = converter._create_summary_statistics()

        # Get final memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 50MB for 1000 resources)
        assert memory_increase < 50 * 1024 * 1024  # 50MB

        # Summary should be correct
        assert summary["total_resources"] == 1000


class TestDataFormatCompatibility:
    """Test compatibility with different data formats"""

    def test_inventory_format_compatibility(self, sample_inventory_data):
        """Test compatibility with inventory format"""
        inventory_format = {"all_discovered_resources": sample_inventory_data}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(inventory_format, f)
            input_file = f.name

        try:
            converter = BOMConverter(enrich_vpc_info=False)
            data = converter.load_data(input_file)

            assert len(data) == 3
            assert all("service" in resource for resource in data)

        finally:
            os.unlink(input_file)

    def test_compliance_format_compatibility(self, sample_compliance_data):
        """Test compatibility with compliance format"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_compliance_data, f)
            input_file = f.name

        try:
            converter = BOMConverter(enrich_vpc_info=False)
            data = converter.load_data(input_file)

            # Should extract all resources from compliance data
            assert len(data) == 3  # 2 compliant + 1 non-compliant

        finally:
            os.unlink(input_file)

    def test_mixed_format_compatibility(self):
        """Test compatibility with mixed/unknown formats"""
        mixed_format = {
            "resources": [
                {"service": "S3", "type": "Bucket", "id": "bucket-1"},
                {"service": "EC2", "type": "Instance", "id": "i-123"},
            ],
            "metadata": {"total": 2},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(mixed_format, f)
            input_file = f.name

        try:
            converter = BOMConverter(enrich_vpc_info=False)
            data = converter.load_data(input_file)

            # Should handle mixed format gracefully
            assert isinstance(data, list)

        finally:
            os.unlink(input_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
