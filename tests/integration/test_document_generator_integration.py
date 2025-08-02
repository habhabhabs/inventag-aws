#!/usr/bin/env python3
"""
Integration tests for DocumentGenerator.

Tests the complete document generation workflow with real builders.
"""

import unittest
import tempfile
import os
import csv
import shutil
from datetime import datetime, timezone

from inventag.reporting.document_generator import (
    DocumentGenerator, DocumentConfig, BrandingConfig, create_document_generator
)
from inventag.reporting.bom_processor import BOMData


class TestDocumentGeneratorIntegration(unittest.TestCase):
    """Integration test cases for DocumentGenerator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create comprehensive test BOM data
        self.test_bom_data = BOMData(
            resources=[
                {
                    "service": "EC2",
                    "type": "Instance",
                    "id": "i-1234567890abcdef0",
                    "name": "web-server-1",
                    "region": "us-east-1",
                    "account_id": "123456789012",
                    "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
                    "compliance_status": "compliant",
                    "tags": {
                        "Name": "web-server-1",
                        "Environment": "production",
                        "inventag:remarks": "Primary web server",
                        "inventag:costcenter": "IT-001"
                    },
                    "vpc_id": "vpc-12345678",
                    "subnet_id": "subnet-12345678",
                    "security_groups": ["sg-12345678"]
                },
                {
                    "service": "S3",
                    "type": "Bucket",
                    "id": "test-bucket-12345",
                    "name": "test-bucket-12345",
                    "region": "us-east-1",
                    "account_id": "123456789012",
                    "arn": "arn:aws:s3:::test-bucket-12345",
                    "compliance_status": "non_compliant",
                    "tags": {
                        "Name": "test-bucket-12345",
                        "Environment": "development",
                        "inventag:costcenter": "DEV-002"
                    },
                    "encryption": "AES256",
                    "versioning": "Enabled"
                },
                {
                    "service": "RDS",
                    "type": "DBInstance",
                    "id": "database-1",
                    "name": "database-1",
                    "region": "us-west-2",
                    "account_id": "123456789012",
                    "arn": "arn:aws:rds:us-west-2:123456789012:db:database-1",
                    "compliance_status": "compliant",
                    "tags": {
                        "Name": "database-1",
                        "Environment": "production",
                        "inventag:remarks": "Main application database",
                        "inventag:costcenter": "IT-001"
                    },
                    "engine": "mysql",
                    "engine_version": "8.0.35",
                    "instance_class": "db.t3.micro"
                }
            ],
            network_analysis={
                "total_vpcs": 2,
                "total_subnets": 4,
                "vpc_utilization": {
                    "vpc-12345678": {
                        "name": "main-vpc",
                        "cidr_block": "10.0.0.0/16",
                        "utilization_percentage": 25.5,
                        "available_ips": 65280
                    }
                }
            },
            security_analysis={
                "total_security_groups": 5,
                "high_risk_rules": 1,
                "overly_permissive_rules": [
                    {
                        "group_id": "sg-12345678",
                        "rule": "0.0.0.0/0:22",
                        "risk_level": "high"
                    }
                ]
            },
            compliance_summary={
                "total_resources": 3,
                "compliant_resources": 2,
                "non_compliant_resources": 1,
                "compliance_percentage": 66.7
            },
            generation_metadata={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_resources": 3,
                "processing_time_seconds": 2.5,
                "data_source": "aws_resource_inventory.py"
            },
            custom_attributes=["inventag:remarks", "inventag:costcenter"]
        )
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_csv_document_generation_integration(self):
        """Test complete CSV document generation workflow."""
        config = DocumentConfig(
            output_formats=["csv"],
            output_directory=self.temp_dir,
            filename_template="integration_test_{timestamp}",
            validate_before_generation=True
        )
        
        generator = DocumentGenerator(config)
        
        # Generate documents
        summary = generator.generate_bom_documents(self.test_bom_data)
        
        # Verify generation summary
        self.assertEqual(summary.total_formats, 1)
        self.assertEqual(summary.successful_formats, 1)
        self.assertEqual(summary.failed_formats, 0)
        self.assertEqual(len(summary.results), 1)
        
        result = summary.results[0]
        self.assertTrue(result.success)
        self.assertEqual(result.format_type, "csv")
        self.assertTrue(result.filename.endswith(".csv"))
        self.assertIsNone(result.error_message)
        
        # Verify file was created
        output_file = os.path.join(self.temp_dir, result.filename)
        self.assertTrue(os.path.exists(output_file))
        self.assertGreater(os.path.getsize(output_file), 0)
        
        # Verify CSV content
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        # Should have 3 resources
        self.assertEqual(len(rows), 3)
        
        # Verify headers include expected fields
        headers = reader.fieldnames
        expected_headers = [
            'service', 'type', 'id', 'name', 'region', 'account_id', 
            'compliance_status', 'tags.Name', 'tags.Environment'
        ]
        
        for header in expected_headers:
            self.assertIn(header, headers)
            
        # Verify data content
        ec2_row = next((row for row in rows if row['service'] == 'EC2'), None)
        self.assertIsNotNone(ec2_row)
        self.assertEqual(ec2_row['id'], 'i-1234567890abcdef0')
        self.assertEqual(ec2_row['compliance_status'], 'compliant')
        
        s3_row = next((row for row in rows if row['service'] == 'S3'), None)
        self.assertIsNotNone(s3_row)
        self.assertEqual(s3_row['id'], 'test-bucket-12345')
        self.assertEqual(s3_row['compliance_status'], 'non_compliant')
        
    def test_multiple_format_generation_with_fallback(self):
        """Test generation with multiple formats including unavailable ones."""
        config = DocumentConfig(
            output_formats=["csv", "excel", "word"],  # Excel and Word may not be available
            output_directory=self.temp_dir,
            filename_template="multi_format_test_{timestamp}",
            validate_before_generation=True
        )
        
        generator = DocumentGenerator(config)
        
        # Generate documents
        summary = generator.generate_bom_documents(self.test_bom_data)
        
        # Should have attempted all formats
        self.assertEqual(summary.total_formats, 3)
        
        # At least CSV should succeed
        csv_result = next((r for r in summary.results if r.format_type == "csv"), None)
        self.assertIsNotNone(csv_result)
        self.assertTrue(csv_result.success)
        
        # Verify CSV file exists
        csv_file = os.path.join(self.temp_dir, csv_result.filename)
        self.assertTrue(os.path.exists(csv_file))
        
    def test_branding_configuration(self):
        """Test document generation with custom branding."""
        branding = BrandingConfig(
            company_name="Test Corporation",
            color_scheme={
                "primary": "#FF0000",
                "secondary": "#00FF00"
            },
            font_family="Arial",
            font_size=12
        )
        
        config = DocumentConfig(
            output_formats=["csv"],
            output_directory=self.temp_dir,
            branding=branding,
            filename_template="branded_test_{timestamp}"
        )
        
        generator = DocumentGenerator(config)
        
        # Generate documents
        summary = generator.generate_bom_documents(self.test_bom_data)
        
        # Should succeed
        self.assertEqual(summary.successful_formats, 1)
        self.assertTrue(summary.results[0].success)
        
        # Verify branding config is applied
        self.assertEqual(generator.config.branding.company_name, "Test Corporation")
        self.assertEqual(generator.config.branding.color_scheme["primary"], "#FF0000")
        
    def test_factory_function_integration(self):
        """Test create_document_generator factory function."""
        generator = create_document_generator(
            output_formats=["csv"],
            branding_config=BrandingConfig(company_name="Factory Test Corp"),
            output_directory=self.temp_dir,
            filename_template="factory_test_{timestamp}"
        )
        
        # Generate documents
        summary = generator.generate_bom_documents(self.test_bom_data)
        
        # Should succeed
        self.assertEqual(summary.successful_formats, 1)
        self.assertTrue(summary.results[0].success)
        
        # Verify configuration
        self.assertEqual(generator.config.branding.company_name, "Factory Test Corp")
        
    def test_generation_report_saving(self):
        """Test saving generation report."""
        config = DocumentConfig(
            output_formats=["csv"],
            output_directory=self.temp_dir
        )
        
        generator = DocumentGenerator(config)
        
        # Generate documents
        summary = generator.generate_bom_documents(self.test_bom_data)
        
        # Save generation report
        report_path = os.path.join(self.temp_dir, "generation_report.json")
        generator.save_generation_report(summary, report_path)
        
        # Verify report file exists
        self.assertTrue(os.path.exists(report_path))
        
        # Verify report content
        import json
        with open(report_path, 'r') as f:
            report_data = json.load(f)
            
        self.assertIn("generation_summary", report_data)
        self.assertIn("results", report_data)
        self.assertEqual(report_data["generation_summary"]["total_formats"], 1)
        self.assertEqual(report_data["generation_summary"]["successful_formats"], 1)
        
    def test_error_handling_with_invalid_data(self):
        """Test error handling with invalid BOM data."""
        # Create invalid BOM data
        invalid_bom_data = BOMData(
            resources=[],  # Empty resources should trigger validation error
            generation_metadata={}
        )
        
        config = DocumentConfig(
            output_formats=["csv"],
            output_directory=self.temp_dir,
            validate_before_generation=True
        )
        
        generator = DocumentGenerator(config)
        
        # Should raise DocumentGenerationError
        with self.assertRaises(Exception):  # DocumentGenerationError
            generator.generate_bom_documents(invalid_bom_data)
            
    def test_format_capabilities_reporting(self):
        """Test format capabilities reporting."""
        config = DocumentConfig(output_directory=self.temp_dir)
        generator = DocumentGenerator(config)
        
        # Get available formats
        formats = generator.get_available_formats()
        self.assertIsInstance(formats, list)
        self.assertIn("csv", formats)  # CSV should always be available
        
        # Get format capabilities
        capabilities = generator.get_format_capabilities()
        self.assertIsInstance(capabilities, dict)
        
        # CSV should be available and have dependencies met
        if "csv" in capabilities:
            csv_caps = capabilities["csv"]
            self.assertTrue(csv_caps["available"])
            self.assertTrue(csv_caps["dependencies_met"])


if __name__ == '__main__':
    unittest.main()