#!/usr/bin/env python3
"""
Unit tests for BOM Data Processor

Tests the central orchestrator that processes raw inventory data and coordinates
with specialized analyzers.
"""

import json
import unittest
from unittest.mock import Mock, patch, MagicMock
import boto3
from datetime import datetime, timezone
import logging
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Import the module under test
from inventag.reporting.bom_processor import (
    BOMDataProcessor,
    BOMProcessingConfig,
    BOMData,
    ProcessingStatistics,
)
from inventag.discovery.network_analyzer import (
    NetworkAnalyzer as RealNetworkAnalyzer,
    SubnetAnalysis,
    VPCAnalysis,
)
from inventag.discovery.security_analyzer import (
    SecurityAnalyzer as RealSecurityAnalyzer,
    SecurityGroupAnalysis,
    SecurityRule,
)


class TestBOMProcessingConfig(unittest.TestCase):
    """Test BOMProcessingConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BOMProcessingConfig()

        self.assertTrue(config.enable_network_analysis)
        self.assertTrue(config.enable_security_analysis)
        self.assertTrue(config.enable_service_enrichment)
        self.assertTrue(config.enable_service_descriptions)
        self.assertTrue(config.enable_tag_mapping)
        self.assertTrue(config.enable_parallel_processing)
        self.assertEqual(config.max_worker_threads, 4)
        self.assertTrue(config.cache_results)
        self.assertIsNone(config.service_descriptions_config)
        self.assertIsNone(config.tag_mappings_config)
        self.assertEqual(config.processing_timeout, 300)

    def test_custom_config(self):
        """Test custom configuration values."""
        config = BOMProcessingConfig(
            enable_network_analysis=False,
            enable_parallel_processing=False,
            max_worker_threads=8,
            processing_timeout=600,
            service_descriptions_config="test_config.yaml",
        )

        self.assertFalse(config.enable_network_analysis)
        self.assertFalse(config.enable_parallel_processing)
        self.assertEqual(config.max_worker_threads, 8)
        self.assertEqual(config.processing_timeout, 600)
        self.assertEqual(config.service_descriptions_config, "test_config.yaml")


class TestBOMData(unittest.TestCase):
    """Test BOMData dataclass."""

    def test_default_bom_data(self):
        """Test default BOM data structure."""
        resources = [{"id": "test-resource", "service": "EC2"}]
        bom_data = BOMData(resources=resources)

        self.assertEqual(bom_data.resources, resources)
        self.assertEqual(bom_data.network_analysis, {})
        self.assertEqual(bom_data.security_analysis, {})
        self.assertEqual(bom_data.compliance_summary, {})
        self.assertEqual(bom_data.generation_metadata, {})
        self.assertEqual(bom_data.custom_attributes, [])
        self.assertEqual(bom_data.processing_statistics, {})
        self.assertEqual(bom_data.error_summary, {})

    def test_custom_bom_data(self):
        """Test BOM data with custom values."""
        resources = [{"id": "test-resource", "service": "EC2"}]
        network_analysis = {"vpc_count": 2}
        security_analysis = {"security_groups": 5}

        bom_data = BOMData(
            resources=resources,
            network_analysis=network_analysis,
            security_analysis=security_analysis,
        )

        self.assertEqual(bom_data.resources, resources)
        self.assertEqual(bom_data.network_analysis, network_analysis)
        self.assertEqual(bom_data.security_analysis, security_analysis)


class TestProcessingStatistics(unittest.TestCase):
    """Test ProcessingStatistics dataclass."""

    def test_default_statistics(self):
        """Test default statistics values."""
        stats = ProcessingStatistics()

        self.assertEqual(stats.total_resources, 0)
        self.assertEqual(stats.processed_resources, 0)
        self.assertEqual(stats.failed_resources, 0)
        self.assertEqual(stats.network_enriched, 0)
        self.assertEqual(stats.security_enriched, 0)
        self.assertEqual(stats.service_enriched, 0)
        self.assertEqual(stats.description_enriched, 0)
        self.assertEqual(stats.tag_mapped, 0)
        self.assertEqual(stats.processing_time_seconds, 0.0)
        self.assertEqual(stats.errors, [])
        self.assertEqual(stats.warnings, [])


class TestBOMDataProcessor(unittest.TestCase):
    """Test BOMDataProcessor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = BOMProcessingConfig(
            enable_network_analysis=True,
            enable_security_analysis=True,
            enable_service_enrichment=True,
            enable_service_descriptions=True,
            enable_tag_mapping=True,
            enable_parallel_processing=False,  # Use sequential for easier testing
        )

        # Mock boto3 session
        self.mock_session = Mock(spec=boto3.Session)

        # Sample test data
        self.sample_resources = [
            {
                "id": "i-1234567890abcdef0",
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
                "tags": [{"Key": "Name", "Value": "test-instance"}],
            },
            {
                "id": "vpc-12345678",
                "service": "EC2",
                "type": "VPC",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
            },
        ]

    @patch("inventag.reporting.bom_processor.NetworkAnalyzer")
    @patch("inventag.reporting.bom_processor.SecurityAnalyzer")
    @patch("inventag.reporting.bom_processor.ServiceAttributeEnricher")
    @patch("inventag.reporting.bom_processor.ServiceDescriptionManager")
    @patch("inventag.reporting.bom_processor.TagMappingEngine")
    def test_initialization_all_components_enabled(
        self,
        mock_tag_engine,
        mock_desc_manager,
        mock_service_enricher,
        mock_security_analyzer,
        mock_network_analyzer,
    ):
        """Test processor initialization with all components enabled."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        # Verify all components were initialized
        mock_network_analyzer.assert_called_once_with(self.mock_session)
        mock_security_analyzer.assert_called_once_with(self.mock_session)
        mock_service_enricher.assert_called_once_with(self.mock_session)
        mock_desc_manager.assert_called_once_with(None)
        mock_tag_engine.assert_called_once_with(None)

        # Verify processor attributes
        self.assertIsNotNone(processor.network_analyzer)
        self.assertIsNotNone(processor.security_analyzer)
        self.assertIsNotNone(processor.service_enricher)
        self.assertIsNotNone(processor.service_desc_manager)
        self.assertIsNotNone(processor.tag_mapping_engine)

    def test_initialization_components_disabled(self):
        """Test processor initialization with components disabled."""
        config = BOMProcessingConfig(
            enable_network_analysis=False,
            enable_security_analysis=False,
            enable_service_enrichment=False,
            enable_service_descriptions=False,
            enable_tag_mapping=False,
        )

        processor = BOMDataProcessor(config, self.mock_session)

        # Verify components are None when disabled
        self.assertIsNone(processor.network_analyzer)
        self.assertIsNone(processor.security_analyzer)
        self.assertIsNone(processor.service_enricher)
        self.assertIsNone(processor.service_desc_manager)
        self.assertIsNone(processor.tag_mapping_engine)

    def test_extract_resources_from_data_direct_resources(self):
        """Test extracting resources from direct resource list."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = processor._extract_resources_from_data(self.sample_resources)

        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]["id"], "i-1234567890abcdef0")
        self.assertEqual(resources[1]["id"], "vpc-12345678")

    def test_extract_resources_from_data_container_format(self):
        """Test extracting resources from container format."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        container_data = [
            {
                "all_discovered_resources": self.sample_resources,
                "metadata": {"scan_date": "2024-01-01"},
            }
        ]

        resources = processor._extract_resources_from_data(container_data)

        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]["id"], "i-1234567890abcdef0")

    def test_extract_resources_from_data_compliance_format(self):
        """Test extracting resources from compliance checker format."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        compliance_data = [
            {
                "compliant_resources": [self.sample_resources[0]],
                "non_compliant_resources": [self.sample_resources[1]],
            }
        ]

        resources = processor._extract_resources_from_data(compliance_data)

        self.assertEqual(len(resources), 2)

    def test_reclassify_vpc_resources(self):
        """Test VPC resource reclassification."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = [
            {"service": "EC2", "type": "VPC", "id": "vpc-123"},
            {"service": "EC2", "type": "Subnet", "id": "subnet-123"},
            {"service": "EC2", "type": "Instance", "id": "i-123"},
            {"service": "EC2", "type": "SecurityGroup", "id": "sg-123"},
        ]

        reclassified = processor._reclassify_vpc_resources(resources)

        # VPC and Subnet should be reclassified to VPC service
        self.assertEqual(reclassified[0]["service"], "VPC")  # VPC
        self.assertEqual(reclassified[1]["service"], "VPC")  # Subnet
        self.assertEqual(reclassified[2]["service"], "EC2")  # Instance stays EC2
        self.assertEqual(reclassified[3]["service"], "VPC")  # SecurityGroup to VPC

    def test_standardize_service_names(self):
        """Test service name standardization."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = [
            {"service": "CloudFormation", "id": "stack-1"},
            {"service": "Lambda", "id": "function-1"},
            {"service": "ElasticLoadBalancing", "id": "elb-1"},
            {"service": "EC2", "id": "i-1"},
        ]

        standardized = processor._standardize_service_names(resources)

        self.assertEqual(standardized[0]["service"], "CLOUDFORMATION")
        self.assertEqual(standardized[1]["service"], "LAMBDA")
        self.assertEqual(standardized[2]["service"], "ELB")
        self.assertEqual(standardized[3]["service"], "EC2")  # Unchanged

    def test_fix_resource_types(self):
        """Test resource type fixes."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = [
            {"type": "LoadBalancer", "id": "elb-1"},
            {"type": "TargetGroup", "id": "tg-1"},
            {"type": "Instance", "id": "i-1"},
        ]

        fixed = processor._fix_resource_types(resources)

        self.assertEqual(fixed[0]["type"], "Load-Balancer")
        self.assertEqual(fixed[1]["type"], "Target-Group")
        self.assertEqual(fixed[2]["type"], "Instance")  # Unchanged

    def test_fix_id_and_name_parsing(self):
        """Test ID extraction from ARNs."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = [
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
                # Missing id field
            },
            {
                "arn": "arn:aws:s3:::my-bucket/object-key",
                # Missing id field
            },
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
                "id": "existing-id",  # Should not be overwritten
            },
        ]

        fixed = processor._fix_id_and_name_parsing(resources)

        self.assertEqual(fixed[0]["id"], "i-1234567890abcdef0")
        self.assertEqual(fixed[1]["id"], "object-key")
        self.assertEqual(fixed[2]["id"], "existing-id")  # Unchanged

    def test_fix_account_id_from_arn(self):
        """Test account ID extraction from ARNs."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = [
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
                # Missing account_id field
            },
            {
                "arn": "arn:aws:s3:::my-bucket",
                "account_id": "existing-account",  # Should not be overwritten
            },
        ]

        fixed = processor._fix_account_id_from_arn(resources)

        self.assertEqual(fixed[0]["account_id"], "123456789012")
        self.assertEqual(fixed[1]["account_id"], "existing-account")  # Unchanged

    def test_deduplicate_resources(self):
        """Test resource deduplication."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = [
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-123",
                "id": "i-123",
                "name": "instance-1",
            },
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-123",
                "id": "i-123",
                "name": "instance-1",
                "extra_field": "more_data",  # More complete resource
            },
            {"service": "S3", "id": "bucket-1", "region": "us-east-1"},
        ]

        deduplicated = processor._deduplicate_resources(resources)

        # Should have 2 resources (duplicate removed, more complete one kept)
        self.assertEqual(len(deduplicated), 2)

        # Find the EC2 instance (should be the more complete one)
        ec2_resource = next(
            r for r in deduplicated if r.get("service") == "EC2" or "instance" in r.get("arn", "")
        )
        self.assertIn("extra_field", ec2_resource)

    def test_generate_compliance_summary(self):
        """Test compliance summary generation."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = [
            {"id": "r1", "compliance_status": "compliant"},
            {"id": "r2", "compliance_status": "compliant"},
            {"id": "r3", "compliance_status": "non_compliant"},
            {"id": "r4", "compliance_status": "unknown"},
            {"id": "r5"},  # No compliance status
        ]

        summary = processor._generate_compliance_summary(resources)

        self.assertEqual(summary["total_resources"], 5)
        self.assertEqual(summary["compliant_resources"], 2)
        self.assertEqual(summary["non_compliant_resources"], 1)
        self.assertEqual(summary["unknown_compliance"], 2)
        self.assertEqual(summary["compliance_percentage"], 40.0)

    def test_extract_custom_attributes(self):
        """Test custom attributes extraction."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = [
            {
                "id": "r1",
                "custom_attributes": {"cost_center": "IT", "environment": "prod"},
            },
            {
                "id": "r2",
                "custom_attributes": {"cost_center": "Finance", "project": "ProjectX"},
            },
            {"id": "r3"},  # No custom attributes
        ]

        attributes = processor._extract_custom_attributes(resources)

        # Should be sorted list of unique attributes
        expected = ["cost_center", "environment", "project"]
        self.assertEqual(attributes, expected)

    @patch("inventag.reporting.bom_processor.NetworkAnalyzer")
    @patch("inventag.reporting.bom_processor.SecurityAnalyzer")
    @patch("inventag.reporting.bom_processor.ServiceAttributeEnricher")
    @patch("inventag.reporting.bom_processor.ServiceDescriptionManager")
    @patch("inventag.reporting.bom_processor.TagMappingEngine")
    def test_process_inventory_data_success(
        self,
        mock_tag_engine,
        mock_desc_manager,
        mock_service_enricher,
        mock_security_analyzer,
        mock_network_analyzer,
    ):
        """Test successful inventory data processing.

        The AWS-calling analysis steps are replaced with canned analysis
        objects; the summary generation is the real analyzer code, so this
        checks that the dataclass summaries reach BOMData as the plain
        dictionaries the document builders read.
        """
        # Only the bom_processor names are patched; these are the real classes.
        real_network = RealNetworkAnalyzer(self.mock_session)
        real_security = RealSecurityAnalyzer(self.mock_session)

        vpc_analysis = {
            "vpc-12345678": VPCAnalysis(
                vpc_id="vpc-12345678",
                vpc_name="prod-vpc",
                cidr_block="10.0.0.0/16",
                total_ips=65531,
                available_ips=65000,
                utilization_percentage=0.8,
                subnets=[
                    SubnetAnalysis(
                        subnet_id="subnet-0a1b2c3d",
                        subnet_name="prod-private-a",
                        cidr_block="10.0.1.0/24",
                        availability_zone="us-east-1a",
                        vpc_id="vpc-12345678",
                        total_ips=251,
                        available_ips=200,
                        utilization_percentage=20.3,
                    )
                ],
            )
        }
        sg_analysis = {
            "sg-0123456789abcdef0": SecurityGroupAnalysis(
                group_id="sg-0123456789abcdef0",
                group_name="web-sg",
                description="Web tier",
                vpc_id="vpc-12345678",
                inbound_rules=[
                    SecurityRule(
                        protocol="tcp",
                        port_range="22",
                        source_destination="0.0.0.0/0",
                        description="SSH from anywhere",
                        rule_type="inbound",
                        risk_assessment="high",
                        is_permissive=True,
                        common_service="SSH",
                    ),
                    SecurityRule(
                        protocol="tcp",
                        port_range="443",
                        source_destination="10.0.0.0/16",
                        description="HTTPS from the VPC",
                        rule_type="inbound",
                        risk_assessment="low",
                    ),
                ],
                associated_resources=["i-1234567890abcdef0"],
                risk_level="high",
            ),
            "sg-0fedcba9876543210": SecurityGroupAnalysis(
                group_id="sg-0fedcba9876543210",
                group_name="unused-sg",
                description="Left over",
                vpc_id="vpc-12345678",
                is_unused=True,
            ),
        }

        network = mock_network_analyzer.return_value
        network.enrich_resource_with_network_info.side_effect = lambda x: x
        network.analyze_vpc_resources.return_value = vpc_analysis
        network.generate_network_summary.side_effect = real_network.generate_network_summary

        security = mock_security_analyzer.return_value
        security.enrich_resource_with_security_info.side_effect = lambda x: x
        security.analyze_security_groups.return_value = sg_analysis
        security.generate_security_summary.side_effect = real_security.generate_security_summary
        security.identify_overly_permissive_rules.side_effect = (
            real_security.identify_overly_permissive_rules
        )

        mock_service_enricher.return_value.enrich_resource.side_effect = lambda x: x
        mock_desc_manager.return_value.apply_description_to_resource.side_effect = lambda x: x
        mock_tag_engine.return_value.apply_mappings_to_resource.side_effect = lambda x: x

        processor = BOMDataProcessor(self.config, self.mock_session)

        resources = self.sample_resources + [
            {
                "id": "sg-0123456789abcdef0",
                "service": "EC2",
                "type": "SecurityGroup",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-0123456789abcdef0",
            }
        ]

        # Process data
        bom_data = processor.process_inventory_data(resources)

        # Verify results
        self.assertIsInstance(bom_data, BOMData)
        self.assertEqual(len(bom_data.resources), 3)
        self.assertIn("generated_at", bom_data.generation_metadata)
        self.assertIn("processing_statistics", bom_data.generation_metadata)
        self.assertFalse(bom_data.error_summary["has_errors"])

        # Only the reclassified VPC/SecurityGroup resources reach the analyzers
        (vpc_arg,), _ = network.analyze_vpc_resources.call_args
        self.assertEqual([r["id"] for r in vpc_arg], ["vpc-12345678"])
        (sg_arg,), _ = security.analyze_security_groups.call_args
        self.assertEqual([r["id"] for r in sg_arg], ["sg-0123456789abcdef0"])

        # Network summary is a plain dict in the shape the builders read
        self.assertIsInstance(bom_data.network_analysis, dict)
        self.assertEqual(bom_data.network_analysis["total_vpcs"], 1)
        self.assertEqual(bom_data.network_analysis["total_subnets"], 1)
        self.assertEqual(
            bom_data.network_analysis["vpc_utilization"]["vpc-12345678"],
            {
                "name": "prod-vpc",
                "cidr_block": "10.0.0.0/16",
                "utilization_percentage": 0.8,
                "available_ips": 65000,
            },
        )

        # Security summary: counts are real, rules are a list of dicts
        self.assertIsInstance(bom_data.security_analysis, dict)
        self.assertEqual(bom_data.security_analysis["total_security_groups"], 2)
        self.assertEqual(bom_data.security_analysis["unused_security_groups"], 1)
        self.assertEqual(bom_data.security_analysis["overly_permissive_rule_count"], 1)
        self.assertEqual(bom_data.security_analysis["high_risk_rules"], 1)
        self.assertEqual(
            bom_data.security_analysis["high_risk_resources"], ["i-1234567890abcdef0"]
        )
        (rule,) = bom_data.security_analysis["overly_permissive_rules"]
        self.assertEqual(rule["group_id"], "sg-0123456789abcdef0")
        self.assertEqual(rule["rule"], "inbound tcp 22 0.0.0.0/0")
        self.assertEqual(rule["risk_level"], "high")

        # The analysis must survive JSON output and document validation
        json.dumps(bom_data.network_analysis)
        json.dumps(bom_data.security_analysis)

        # Verify VPC reclassification happened
        vpc_resource = next(r for r in bom_data.resources if r["type"] == "VPC")
        self.assertEqual(vpc_resource["service"], "VPC")

    @patch("inventag.reporting.bom_processor.NetworkAnalyzer")
    @patch("inventag.reporting.bom_processor.SecurityAnalyzer")
    def test_process_inventory_data_without_network_resources(
        self, mock_security_analyzer, mock_network_analyzer
    ):
        """No VPC, subnet or security group resources: analysis stays empty."""
        mock_network_analyzer.return_value.enrich_resource_with_network_info.side_effect = (
            lambda x: x
        )
        mock_security_analyzer.return_value.enrich_resource_with_security_info.side_effect = (
            lambda x: x
        )
        config = BOMProcessingConfig(
            enable_service_enrichment=False,
            enable_service_descriptions=False,
            enable_tag_mapping=False,
            enable_parallel_processing=False,
        )
        processor = BOMDataProcessor(config, self.mock_session)

        bom_data = processor.process_inventory_data([self.sample_resources[0]])

        self.assertEqual(bom_data.network_analysis, {})
        self.assertEqual(bom_data.security_analysis, {})
        mock_network_analyzer.return_value.analyze_vpc_resources.assert_not_called()
        mock_security_analyzer.return_value.analyze_security_groups.assert_not_called()

    @patch("inventag.reporting.bom_processor.NetworkAnalyzer")
    def test_process_inventory_data_with_errors(self, mock_network_analyzer):
        """Test inventory data processing with errors."""
        # Per-resource enrichment passes resources through unchanged; the
        # summary step then fails.
        mock_network_analyzer.return_value.enrich_resource_with_network_info.side_effect = (
            lambda x: x
        )
        mock_network_analyzer.return_value.generate_network_summary.side_effect = Exception(
            "Network error"
        )

        config = BOMProcessingConfig(
            enable_security_analysis=False,
            enable_service_enrichment=False,
            enable_service_descriptions=False,
            enable_tag_mapping=False,
        )

        processor = BOMDataProcessor(config, self.mock_session)

        # Process data - should handle errors gracefully
        bom_data = processor.process_inventory_data(self.sample_resources)

        # Verify error handling
        self.assertTrue(bom_data.error_summary["has_errors"])
        self.assertIn("Network analysis failed", str(bom_data.error_summary["errors"]))
        self.assertEqual(bom_data.network_analysis, {})  # Should be empty due to error

    def test_get_processing_statistics(self):
        """Test getting processing statistics."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        stats = processor.get_processing_statistics()

        self.assertIsInstance(stats, ProcessingStatistics)
        self.assertEqual(stats.total_resources, 0)  # Initial state

    def test_clear_cache(self):
        """Test cache clearing."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        # Add something to cache
        processor._processing_cache["test"] = "data"
        self.assertEqual(len(processor._processing_cache), 1)

        # Clear cache
        processor.clear_cache()
        self.assertEqual(len(processor._processing_cache), 0)


class TestBOMDataProcessorErrorHandling(unittest.TestCase):
    """Test error handling scenarios in BOMDataProcessor."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = BOMProcessingConfig(enable_parallel_processing=False)
        self.mock_session = Mock(spec=boto3.Session)

    @patch("inventag.reporting.bom_processor.NetworkAnalyzer")
    def test_component_initialization_failure(self, mock_network_analyzer):
        """Test handling of component initialization failures."""
        mock_network_analyzer.side_effect = Exception("Initialization failed")

        with self.assertRaises(Exception) as context:
            BOMDataProcessor(self.config, self.mock_session)

        # The exception should be re-raised from the initialization
        self.assertIn("Initialization failed", str(context.exception))

    def test_invalid_resource_data(self):
        """Test handling of invalid resource data."""
        processor = BOMDataProcessor(self.config, self.mock_session)

        # Test with invalid data types
        invalid_data = ["not a dict", 123, None, {"valid": "resource"}]

        # Should not crash and should extract valid resources
        resources = processor._extract_resources_from_data(invalid_data)
        self.assertEqual(len(resources), 1)  # Only the valid dict

    @patch("inventag.reporting.bom_processor.NetworkAnalyzer")
    def test_enrichment_partial_failure(self, mock_network_analyzer):
        """Test handling of partial enrichment failures."""
        # Setup mock to fail for network enrichment at the resource level
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.enrich_resource_with_network_info.side_effect = Exception(
            "Network failed"
        )
        mock_analyzer_instance.generate_network_summary.return_value = {}
        mock_network_analyzer.return_value = mock_analyzer_instance

        config = BOMProcessingConfig(
            enable_security_analysis=False,
            enable_service_enrichment=False,
            enable_service_descriptions=False,
            enable_tag_mapping=False,
            enable_parallel_processing=False,
        )

        processor = BOMDataProcessor(config, self.mock_session)

        sample_data = [{"id": "test", "service": "EC2"}]

        # Should complete processing despite enrichment failure
        bom_data = processor.process_inventory_data(sample_data)

        # Verify resource is still processed
        self.assertEqual(len(bom_data.resources), 1)
        # The enrichment failure should be logged as a debug message, not a warning
        # So we just verify the resource was processed without enrichment
        self.assertEqual(bom_data.resources[0]["id"], "test")


if __name__ == "__main__":
    # Configure logging for tests
    logging.basicConfig(level=logging.WARNING)

    unittest.main()
