#!/usr/bin/env python3
"""
BOM Data Processor Demonstration Script

This script demonstrates the comprehensive BOM data processing capabilities
of the InvenTag BOM Data Processor, including central orchestration,
coordinated analysis integration, and configurable processing options.
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the parent directory to the path to import inventag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inventag.reporting.bom_processor import (
    BOMDataProcessor,
    BOMProcessingConfig,
    BOMData,
    ProcessingStatistics,
)


def main():
    """Demonstrate BOM Data Processor functionality"""
    print("=== InvenTag BOM Data Processor Demonstration ===\n")

    # Sample resource data for demonstration
    sample_resources = [
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "id": "i-1234567890abcdef0",
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "tags": {
                "Name": "web-server",
                "Environment": "production",
                "Role": "webserver",
            },
            "compliance_status": "compliant",
        },
        {
            "arn": "arn:aws:s3:::production-data-bucket",
            "id": "production-data-bucket",
            "service": "S3",
            "type": "Bucket",
            "region": "us-east-1",
            "tags": {"Name": "production-data-bucket", "Environment": "production"},
            "compliance_status": "non-compliant",
        },
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
            "id": "vpc-12345678",
            "service": "EC2",
            "type": "VPC",
            "region": "us-east-1",
            "tags": {"Name": "production-vpc", "Environment": "production"},
            "compliance_status": "compliant",
        },
    ]

    print("1. Configuration Examples")
    print("=" * 50)

    # Default configuration
    print("\n[OK] Default Configuration (All Features Enabled):")
    default_config = BOMProcessingConfig()
    print(f"   Network Analysis: {default_config.enable_network_analysis}")
    print(f"   Security Analysis: {default_config.enable_security_analysis}")
    print(f"   Service Enrichment: {default_config.enable_service_enrichment}")
    print(f"   Service Descriptions: {default_config.enable_service_descriptions}")
    print(f"   Tag Mapping: {default_config.enable_tag_mapping}")
    print(f"   Parallel Processing: {default_config.enable_parallel_processing}")
    print(f"   Max Worker Threads: {default_config.max_worker_threads}")
    print(f"   Processing Timeout: {default_config.processing_timeout}s")

    # Performance-optimized configuration
    print("\n[OK] Performance-Optimized Configuration:")
    performance_config = BOMProcessingConfig(
        enable_parallel_processing=True,
        max_worker_threads=8,
        cache_results=True,
        processing_timeout=600,
    )
    print(f"   Parallel Processing: {performance_config.enable_parallel_processing}")
    print(f"   Worker Threads: {performance_config.max_worker_threads}")
    print(f"   Result Caching: {performance_config.cache_results}")
    print(f"   Timeout: {performance_config.processing_timeout}s")

    # Selective analysis configuration
    print("\n[OK] Network-Focused Configuration:")
    network_config = BOMProcessingConfig(
        enable_network_analysis=True,
        enable_security_analysis=False,
        enable_service_enrichment=False,
        enable_service_descriptions=False,
        enable_tag_mapping=False,
    )
    print(f"   Network Analysis: {network_config.enable_network_analysis}")
    print(f"   Security Analysis: {network_config.enable_security_analysis}")
    print(f"   Service Enrichment: {network_config.enable_service_enrichment}")

    print("\n2. Processing Pipeline Demonstration")
    print("=" * 50)

    # Initialize processor with default configuration
    print("\n[OK] Initializing BOM Data Processor...")
    try:
        # Use mock session for demonstration
        import boto3
        from unittest.mock import Mock

        mock_session = Mock(spec=boto3.Session)

        processor = BOMDataProcessor(default_config, mock_session)
        print("   BOM Data Processor initialized successfully")
        print(f"   Components enabled: Network, Security, Service, Descriptions, Tags")
    except Exception as e:
        print(f"   [ERROR] Failed to initialize processor: {e}")
        print("   Note: This is expected in demo mode without AWS credentials")
        return

    print("\n[OK] Data Extraction and Standardization:")
    print("   Stage 1: Extracting resources from input data...")
    print(f"   - Found {len(sample_resources)} resources")
    print("   - Formats supported: Direct lists, inventory containers, compliance reports")

    print("\n   Stage 2: Resource standardization...")
    print("   - Service name standardization (EC2 -> EC2, CloudFormation -> CLOUDFORMATION)")
    print("   - Resource type fixes (LoadBalancer -> Load-Balancer)")
    print("   - ID extraction from ARNs when missing")
    print("   - Account ID population from ARNs")

    print("\n   Stage 3: Service reclassification...")
    print("   - VPC-related resources reclassified from EC2 to VPC service")
    print("   - VPC, Subnet, SecurityGroup, NetworkAcl -> VPC service")

    print("\n   Stage 4: Data cleaning and deduplication...")
    print("   - Missing field population")
    print("   - Duplicate resource removal with preference for complete records")

    print("\n3. Analysis Component Integration")
    print("=" * 50)

    print("\n[OK] Network Analysis:")
    print("   - VPC and subnet utilization analysis")
    print("   - IP capacity planning and availability zone distribution")
    print("   - Network component mapping (IGW, NAT, VPC endpoints)")
    print("   - Resource-to-network context enrichment")

    print("\n[OK] Security Analysis:")
    print("   - Security group rule analysis")
    print("   - Public access detection and risk assessment")
    print("   - IAM role and policy analysis")
    print("   - Encryption configuration validation")

    print("\n[OK] Service Enrichment:")
    print("   - Deep attribute extraction for S3, RDS, EC2, Lambda, ECS, EKS")
    print("   - Dynamic service discovery for unknown services")
    print("   - Service-specific configuration analysis")
    print("   - Performance and operational metrics")

    print("\n[OK] Service Descriptions:")
    print("   - Template-based dynamic description generation")
    print("   - Intelligent fallback mechanisms")
    print("   - Custom configuration support")
    print("   - Metadata tracking and source attribution")

    print("\n[OK] Tag Mapping:")
    print("   - Tag transformation and standardization")
    print("   - Custom mapping rule application")
    print("   - Tag validation and enrichment")
    print("   - Compliance tag generation")

    print("\n4. Processing Results and Statistics")
    print("=" * 50)

    # Simulate processing results
    print("\n[OK] Processing Statistics:")
    mock_stats = ProcessingStatistics(
        total_resources=len(sample_resources),
        processed_resources=len(sample_resources),
        failed_resources=0,
        network_enriched=len(sample_resources),
        security_enriched=len(sample_resources),
        service_enriched=len(sample_resources),
        description_enriched=len(sample_resources),
        tag_mapped=len(sample_resources),
        processing_time_seconds=2.5,
        errors=[],
        warnings=[],
    )

    print(f"   Total Resources: {mock_stats.total_resources}")
    print(f"   Successfully Processed: {mock_stats.processed_resources}")
    print(f"   Failed Processing: {mock_stats.failed_resources}")
    print(f"   Network Enriched: {mock_stats.network_enriched}")
    print(f"   Security Enriched: {mock_stats.security_enriched}")
    print(f"   Service Enriched: {mock_stats.service_enriched}")
    print(f"   Description Enriched: {mock_stats.description_enriched}")
    print(f"   Tag Mapped: {mock_stats.tag_mapped}")
    print(f"   Processing Time: {mock_stats.processing_time_seconds:.2f} seconds")
    print(
        f"   Throughput: {mock_stats.processed_resources / mock_stats.processing_time_seconds:.1f} resources/second"
    )

    print("\n[OK] BOM Data Structure:")
    mock_bom_data = BOMData(
        resources=sample_resources,
        network_analysis={
            "total_vpcs": 1,
            "total_subnets": 3,
            "total_available_ips": 65536,
            "average_utilization": 15.2,
        },
        security_analysis={
            "total_security_groups": 5,
            "high_risk_rules": 2,
            "public_resources": 1,
            "encryption_enabled": 2,
        },
        compliance_summary={
            "total_resources": 3,
            "compliant_resources": 2,
            "non_compliant_resources": 1,
            "compliance_percentage": 66.7,
        },
        generation_metadata={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "processing_version": "1.0",
            "total_resources": 3,
            "processing_time_seconds": 2.5,
        },
        custom_attributes=["Role", "CostCenter", "Project"],
        processing_statistics=mock_stats.__dict__,
        error_summary={"has_errors": False, "has_warnings": False},
    )

    print(f"   Processed Resources: {len(mock_bom_data.resources)}")
    print(f"   Network Analysis: {len(mock_bom_data.network_analysis)} metrics")
    print(f"   Security Analysis: {len(mock_bom_data.security_analysis)} metrics")
    print(
        f"   Compliance Summary: {mock_bom_data.compliance_summary['compliance_percentage']:.1f}% compliant"
    )
    print(f"   Custom Attributes: {len(mock_bom_data.custom_attributes)} discovered")
    print(f"   Generation Metadata: {len(mock_bom_data.generation_metadata)} fields")

    print("\n5. Error Handling and Recovery")
    print("=" * 50)

    print("\n[OK] Graceful Degradation:")
    print("   - Component failures don't stop overall processing")
    print("   - Partial results available even with errors")
    print("   - Comprehensive error tracking and reporting")
    print("   - Warning system for non-critical issues")

    print("\n[OK] Error Recovery Strategies:")
    print("   - Retry logic for transient failures")
    print("   - Fallback mechanisms for missing data")
    print("   - Cache clearing for memory management")
    print("   - Timeout handling for long-running operations")

    print("\n6. Integration Patterns")
    print("=" * 50)

    print("\n[OK] Resource Discovery Integration:")
    print("   - Seamless integration with AWSResourceInventory")
    print("   - Support for multi-region discovery")
    print("   - Automatic session management")

    print("\n[OK] State Management Integration:")
    print("   - Enhanced state saving with analysis results")
    print("   - Comprehensive metadata tracking")
    print("   - Change detection with enriched data")

    print("\n[OK] Compliance Checking Integration:")
    print("   - Enhanced compliance analysis with enriched attributes")
    print("   - Service-specific compliance insights")
    print("   - Automated compliance reporting")

    print("\n[OK] BOM Converter Integration:")
    print("   - Direct integration with Excel/CSV export")
    print("   - Analysis summaries in reports")
    print("   - Enriched data in output formats")

    print("\n7. Performance Optimization")
    print("=" * 50)

    print("\n[OK] Caching System:")
    print("   - Result caching for repeated operations")
    print("   - Intelligent cache invalidation")
    print("   - Memory management and cleanup")

    print("\n[OK] Parallel Processing:")
    print("   - Multi-threaded resource processing")
    print("   - Configurable worker thread pools")
    print("   - Load balancing across components")

    print("\n[OK] Memory Management:")
    print("   - Batch processing for large datasets")
    print("   - Streaming data processing")
    print("   - Garbage collection optimization")

    print("\n8. Configuration Management")
    print("=" * 50)

    print("\n[OK] External Configuration Files:")
    print("   - Service descriptions: config/service_descriptions.yaml")
    print("   - Tag mappings: config/tag_mappings.yaml")
    print("   - Custom templates and rules")

    print("\n[OK] Environment-Specific Configurations:")
    print("   - Development: Fast processing, minimal analysis")
    print("   - Staging: Balanced processing with validation")
    print("   - Production: Comprehensive analysis with monitoring")

    print("\n=== BOM Data Processor Demonstration Complete ===")
    print("\nKey capabilities demonstrated:")
    print("✓ Comprehensive data processing pipeline with 8 stages")
    print("✓ Coordinated analysis integration with 5 specialized components")
    print("✓ Configurable processing options for different use cases")
    print("✓ Performance optimization with parallel processing and caching")
    print("✓ Error handling and graceful degradation")
    print("✓ Integration patterns with other InvenTag components")
    print("✓ Processing statistics and monitoring capabilities")
    print("✓ Flexible configuration management")

    print("\nNext steps:")
    print("• Review the comprehensive documentation: docs/BOM_DATA_PROCESSOR.md")
    print("• Explore the test suite: tests/unit/test_bom_processor.py")
    print("• Try the integration examples in the main documentation")
    print("• Configure custom processing options for your environment")


if __name__ == "__main__":
    main()
