#!/usr/bin/env python3
"""
End-to-end integration tests for complete BOM generation workflow

Tests the complete workflow from resource discovery through compliance checking
to final BOM document generation with various data scenarios.
"""

import pytest
import tempfile
import json
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from inventag.core.cloud_bom_generator import CloudBOMGenerator
from inventag.reporting.document_generator import DocumentConfig, BrandingConfig
from inventag.discovery.inventory import AWSResourceInventory
from inventag.compliance.checker import TagComplianceChecker
from inventag.reporting.bom_processor import BOMDataProcessor


class TestEndToEndBOMGeneration:
    """Integration tests for complete BOM generation workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)

        # Create test configuration
        self.config = {
            "output_directory": self.output_dir,
            "output_formats": ["excel", "csv"],
            "branding": {"company_name": "Test Corporation", "enable_watermark": False},
            "service_descriptions": {
                "EC2": "Amazon Elastic Compute Cloud",
                "S3": "Amazon Simple Storage Service",
            },
            "tag_mappings": {
                "inventag:environment": {
                    "column_name": "Environment",
                    "default_value": "Unknown",
                }
            },
        }

    def test_complete_bom_generation_workflow(self):
        """Test complete BOM generation from discovery to document output."""
        # Mock AWS session and resources
        mock_session = Mock()

        # Sample resource data
        sample_resources = [
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-12345",
                "id": "i-12345",
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "tags": {"Name": "test-instance", "inventag:environment": "production"},
                "instance_type": "t3.micro",
                "state": "running",
                "vpc_id": "vpc-12345",
                "subnet_id": "subnet-12345",
                "security_groups": ["sg-12345"],
            },
            {
                "arn": "arn:aws:s3:::test-bucket",
                "id": "test-bucket",
                "service": "S3",
                "type": "Bucket",
                "region": "us-east-1",
                "tags": {"Name": "test-bucket", "inventag:environment": "production"},
                "encryption": {"enabled": True},
                "public_access": False,
            },
        ]

        # Mock the discovery process
        with patch("inventag.discovery.inventory.AWSResourceInventory") as mock_discovery:
            mock_discovery_instance = Mock()
            mock_discovery_instance.scan_resources.return_value = sample_resources
            mock_discovery.return_value = mock_discovery_instance

            # Mock the compliance checking
            with patch("inventag.compliance.checker.TagComplianceChecker") as mock_compliance:
                mock_compliance_instance = Mock()
                mock_compliance_instance.check_compliance.return_value = {
                    "compliant_resources": 2,
                    "non_compliant_resources": 0,
                    "compliance_percentage": 100.0,
                    "violations": [],
                }
                mock_compliance.return_value = mock_compliance_instance

                # Mock document generation
                with patch(
                    "inventag.reporting.document_generator.DocumentGenerator"
                ) as mock_doc_gen:
                    mock_doc_gen_instance = Mock()
                    mock_doc_gen_instance.generate_bom_documents.return_value = Mock(
                        successful_formats=2,
                        failed_formats=0,
                        results=[
                            Mock(format_type="excel", success=True, filename="test.xlsx"),
                            Mock(format_type="csv", success=True, filename="test.csv"),
                        ],
                    )
                    mock_doc_gen.return_value = mock_doc_gen_instance

                    # Create and run BOM generator
                    generator = CloudBOMGenerator(session=mock_session, config=self.config)

                    result = generator.generate_bom()

                    # Verify the workflow executed
                    assert result is not None
                    mock_discovery_instance.scan_resources.assert_called_once()
                    mock_compliance_instance.check_compliance.assert_called_once()
                    mock_doc_gen_instance.generate_bom_documents.assert_called_once()

    def test_bom_generation_with_network_analysis(self):
        """Test BOM generation with network analysis integration."""
        # Sample resources with network components
        sample_resources = [
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-12345",
                "id": "i-12345",
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "vpc_id": "vpc-12345",
                "subnet_id": "subnet-12345",
                "security_groups": ["sg-12345"],
                "private_ip": "10.0.1.100",
                "public_ip": "54.123.45.67",
            },
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345",
                "id": "vpc-12345",
                "service": "EC2",
                "type": "VPC",
                "region": "us-east-1",
                "cidr_block": "10.0.0.0/16",
                "tags": {"Name": "test-vpc"},
            },
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-12345",
                "id": "subnet-12345",
                "service": "EC2",
                "type": "Subnet",
                "region": "us-east-1",
                "vpc_id": "vpc-12345",
                "cidr_block": "10.0.1.0/24",
                "availability_zone": "us-east-1a",
            },
        ]

        # Mock network analyzer
        with patch("inventag.discovery.network_analyzer.NetworkAnalyzer") as mock_network:
            mock_network_instance = Mock()
            mock_network_instance.analyze_vpc_resources.return_value = {
                "vpc-12345": Mock(
                    vpc_id="vpc-12345",
                    vpc_name="test-vpc",
                    cidr_block="10.0.0.0/16",
                    total_ips=65531,
                    utilization_percentage=0.1,
                    subnets=[
                        Mock(
                            subnet_id="subnet-12345",
                            cidr_block="10.0.1.0/24",
                            total_ips=251,
                            available_ips=250,
                            utilization_percentage=0.4,
                        )
                    ],
                )
            }
            mock_network.return_value = mock_network_instance

            # Mock BOM processor
            with patch("inventag.reporting.bom_processor.BOMDataProcessor") as mock_processor:
                mock_processor_instance = Mock()
                mock_processor_instance.process_inventory_data.return_value = Mock(
                    resources=sample_resources,
                    network_analysis={"vpc-12345": Mock()},
                    generation_metadata={"timestamp": datetime.now().isoformat()},
                )
                mock_processor.return_value = mock_processor_instance

                processor = BOMDataProcessor(self.config)
                result = processor.process_inventory_data(sample_resources)

                # Verify network analysis was included
                assert hasattr(result, "network_analysis")
                mock_network_instance.analyze_vpc_resources.assert_called_once()

    def test_bom_generation_with_security_analysis(self):
        """Test BOM generation with security analysis integration."""
        # Sample resources with security components
        sample_resources = [
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-12345",
                "id": "sg-12345",
                "service": "EC2",
                "type": "SecurityGroup",
                "region": "us-east-1",
                "group_name": "web-sg",
                "vpc_id": "vpc-12345",
                "inbound_rules": [
                    {
                        "protocol": "tcp",
                        "port_range": "80",
                        "source": "0.0.0.0/0",
                        "description": "HTTP from anywhere",
                    }
                ],
            },
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-12345",
                "id": "i-12345",
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "security_groups": ["sg-12345"],
            },
        ]

        # Mock security analyzer
        with patch("inventag.discovery.security_analyzer.SecurityAnalyzer") as mock_security:
            mock_security_instance = Mock()
            mock_security_instance.analyze_security_groups.return_value = {
                "sg-12345": Mock(
                    group_id="sg-12345",
                    group_name="web-sg",
                    risk_level="medium",
                    overly_permissive_rules=1,
                    associated_resources=["i-12345"],
                )
            }
            mock_security_instance.identify_overly_permissive_rules.return_value = [
                {
                    "security_group_id": "sg-12345",
                    "rule_type": "inbound",
                    "protocol": "tcp",
                    "port_range": "80",
                    "source": "0.0.0.0/0",
                    "risk_level": "medium",
                }
            ]
            mock_security.return_value = mock_security_instance

            # Mock BOM processor
            with patch("inventag.reporting.bom_processor.BOMDataProcessor") as mock_processor:
                mock_processor_instance = Mock()
                mock_processor_instance.process_inventory_data.return_value = Mock(
                    resources=sample_resources,
                    security_analysis={"sg-12345": Mock()},
                    generation_metadata={"timestamp": datetime.now().isoformat()},
                )
                mock_processor.return_value = mock_processor_instance

                processor = BOMDataProcessor(self.config)
                result = processor.process_inventory_data(sample_resources)

                # Verify security analysis was included
                assert hasattr(result, "security_analysis")
                mock_security_instance.analyze_security_groups.assert_called_once()

    def test_bom_generation_with_service_enrichment(self):
        """Test BOM generation with service attribute enrichment."""
        # Sample resources for enrichment
        sample_resources = [
            {
                "arn": "arn:aws:s3:::test-bucket",
                "id": "test-bucket",
                "service": "S3",
                "type": "Bucket",
                "region": "us-east-1",
            },
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                "id": "test-function",
                "service": "Lambda",
                "type": "Function",
                "region": "us-east-1",
            },
        ]

        # Mock service enrichment
        with patch(
            "inventag.discovery.service_enrichment.ServiceAttributeEnricher"
        ) as mock_enricher:
            mock_enricher_instance = Mock()
            mock_enricher_instance.enrich_resources_with_attributes.return_value = [
                {
                    **sample_resources[0],
                    "service_attributes": {
                        "encryption": {"enabled": True},
                        "versioning_status": "Enabled",
                        "public_access_block": {"BlockPublicAcls": True},
                    },
                },
                {
                    **sample_resources[1],
                    "service_attributes": {
                        "runtime": "python3.9",
                        "memory_size": 128,
                        "timeout": 30,
                    },
                },
            ]
            mock_enricher.return_value = mock_enricher_instance

            # Mock BOM processor
            with patch("inventag.reporting.bom_processor.BOMDataProcessor") as mock_processor:
                mock_processor_instance = Mock()
                mock_processor_instance.enrich_with_service_attributes.return_value = (
                    sample_resources
                )
                mock_processor.return_value = mock_processor_instance

                processor = BOMDataProcessor(self.config)
                result = processor.enrich_with_service_attributes(sample_resources)

                # Verify enrichment was applied
                mock_enricher_instance.enrich_resources_with_attributes.assert_called_once()

    def test_bom_generation_error_handling(self):
        """Test BOM generation with various error scenarios."""
        mock_session = Mock()

        # Test discovery failure
        with patch("inventag.discovery.inventory.ResourceDiscovery") as mock_discovery:
            mock_discovery_instance = Mock()
            mock_discovery_instance.discover_all_resources.side_effect = Exception(
                "Discovery failed"
            )
            mock_discovery.return_value = mock_discovery_instance

            generator = CloudBOMGenerator(session=mock_session, config=self.config)

            # Should handle discovery failure gracefully
            with pytest.raises(Exception):
                generator.generate_bom()

    def test_bom_generation_with_large_dataset(self):
        """Test BOM generation with large dataset (performance test)."""
        # Generate large dataset
        large_dataset = []
        for i in range(1000):  # 1000 resources
            large_dataset.append(
                {
                    "arn": f"arn:aws:ec2:us-east-1:123456789012:instance/i-{i:05d}",
                    "id": f"i-{i:05d}",
                    "service": "EC2",
                    "type": "Instance",
                    "region": "us-east-1",
                    "tags": {"Name": f"instance-{i}", "inventag:environment": "test"},
                    "instance_type": "t3.micro",
                    "state": "running",
                }
            )

        # Mock components for performance test
        with patch("inventag.discovery.inventory.ResourceDiscovery") as mock_discovery:
            mock_discovery_instance = Mock()
            mock_discovery_instance.discover_all_resources.return_value = large_dataset
            mock_discovery.return_value = mock_discovery_instance

            with patch("inventag.compliance.checker.ComplianceChecker") as mock_compliance:
                mock_compliance_instance = Mock()
                mock_compliance_instance.check_compliance.return_value = {
                    "compliant_resources": 1000,
                    "non_compliant_resources": 0,
                    "compliance_percentage": 100.0,
                }
                mock_compliance.return_value = mock_compliance_instance

                with patch("inventag.reporting.bom_processor.BOMDataProcessor") as mock_processor:
                    mock_processor_instance = Mock()
                    mock_processor_instance.process_inventory_data.return_value = Mock(
                        resources=large_dataset,
                        generation_metadata={"timestamp": datetime.now().isoformat()},
                    )
                    mock_processor.return_value = mock_processor_instance

                    # Measure processing time
                    start_time = datetime.now()

                    processor = BOMDataProcessor(self.config)
                    result = processor.process_inventory_data(large_dataset)

                    end_time = datetime.now()
                    processing_time = (end_time - start_time).total_seconds()

                    # Verify performance (should process 1000 resources in reasonable time)
                    assert processing_time < 10.0  # Less than 10 seconds
                    assert len(large_dataset) == 1000

    def test_multi_format_document_generation(self):
        """Test generation of multiple document formats simultaneously."""
        sample_resources = [
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-12345",
                "id": "i-12345",
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
            }
        ]

        # Configure multiple formats
        multi_format_config = {
            **self.config,
            "output_formats": ["excel", "word", "csv"],
        }

        # Mock document generator
        with patch("inventag.reporting.document_generator.DocumentGenerator") as mock_doc_gen:
            mock_doc_gen_instance = Mock()
            mock_doc_gen_instance.generate_bom_documents.return_value = Mock(
                total_formats=3,
                successful_formats=3,
                failed_formats=0,
                results=[
                    Mock(format_type="excel", success=True, filename="test.xlsx"),
                    Mock(format_type="word", success=True, filename="test.docx"),
                    Mock(format_type="csv", success=True, filename="test.csv"),
                ],
            )
            mock_doc_gen.return_value = mock_doc_gen_instance

            # Mock BOM processor
            with patch("inventag.reporting.bom_processor.BOMDataProcessor") as mock_processor:
                mock_processor_instance = Mock()
                mock_processor_instance.process_inventory_data.return_value = Mock(
                    resources=sample_resources,
                    generation_metadata={"timestamp": datetime.now().isoformat()},
                )
                mock_processor.return_value = mock_processor_instance

                processor = BOMDataProcessor(multi_format_config)
                bom_data = processor.process_inventory_data(sample_resources)

                # Generate documents
                doc_config = DocumentConfig(
                    output_formats=["excel", "word", "csv"],
                    branding=BrandingConfig(company_name="Test Corp"),
                )
                generator = mock_doc_gen(doc_config)
                result = generator.generate_bom_documents(bom_data)

                # Verify all formats were generated
                assert result.total_formats == 3
                assert result.successful_formats == 3
                assert result.failed_formats == 0

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)


if __name__ == "__main__":
    pytest.main([__file__])
