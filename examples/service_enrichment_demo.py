#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service Enrichment Demo - Comprehensive service attribute extraction demonstration

This script demonstrates the enhanced service enrichment capabilities for
deep attribute extraction from major AWS services including S3, RDS, EC2,
Lambda, ECS, and EKS.
"""

import json
import sys
import os
from datetime import datetime, timezone

# Add the parent directory to the path to import inventag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inventag.discovery.service_enrichment import (
    ServiceAttributeEnricher,
    ServiceHandlerFactory,
)

# Ensure proper encoding for Windows console
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")


def create_sample_resources():
    """Create sample resource data for demonstration"""
    return [
        {
            "arn": "arn:aws:s3:::production-data-bucket",
            "id": "production-data-bucket",
            "service": "S3",
            "type": "Bucket",
            "region": "us-east-1",
            "name": "production-data-bucket",
            "tags": {
                "Environment": "production",
                "Owner": "data-team",
                "Role": "storage",
            },
            "account_id": "123456789012",
        },
        {
            "arn": "arn:aws:rds:us-east-1:123456789012:db:prod-database",
            "id": "prod-database",
            "service": "RDS",
            "type": "DBInstance",
            "region": "us-east-1",
            "name": "prod-database",
            "tags": {
                "Environment": "production",
                "Owner": "backend-team",
                "Role": "database",
            },
            "account_id": "123456789012",
        },
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "id": "i-1234567890abcdef0",
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "name": "web-server-01",
            "tags": {
                "Name": "web-server-01",
                "Environment": "production",
                "Role": "webserver",
            },
            "account_id": "123456789012",
        },
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:volume/vol-1234567890abcdef0",
            "id": "vol-1234567890abcdef0",
            "service": "EC2",
            "type": "Volume",
            "region": "us-east-1",
            "name": "web-server-root-volume",
            "tags": {"Name": "web-server-root-volume", "Environment": "production"},
            "account_id": "123456789012",
        },
        {
            "arn": "arn:aws:lambda:us-east-1:123456789012:function:data-processor",
            "id": "data-processor",
            "service": "Lambda",
            "type": "Function",
            "region": "us-east-1",
            "name": "data-processor",
            "tags": {
                "Environment": "production",
                "Owner": "data-team",
                "Role": "processing",
            },
            "account_id": "123456789012",
        },
        {
            "arn": "arn:aws:ecs:us-east-1:123456789012:cluster/production-cluster",
            "id": "production-cluster",
            "service": "ECS",
            "type": "Cluster",
            "region": "us-east-1",
            "name": "production-cluster",
            "tags": {
                "Environment": "production",
                "Owner": "devops-team",
                "Role": "container-orchestration",
            },
            "account_id": "123456789012",
        },
        {
            "arn": "arn:aws:eks:us-east-1:123456789012:cluster/k8s-production",
            "id": "k8s-production",
            "service": "EKS",
            "type": "Cluster",
            "region": "us-east-1",
            "name": "k8s-production",
            "tags": {
                "Environment": "production",
                "Owner": "platform-team",
                "Role": "kubernetes",
            },
            "account_id": "123456789012",
        },
        {
            "arn": "arn:aws:customservice:us-east-1:123456789012:resource/custom-resource-1",
            "id": "custom-resource-1",
            "service": "CustomService",
            "type": "CustomResource",
            "region": "us-east-1",
            "name": "custom-resource-1",
            "tags": {"Environment": "production", "Owner": "custom-team"},
            "account_id": "123456789012",
        },
    ]


def print_service_handler_info():
    """Print information about available service handlers"""
    print("=" * 80)
    print("SERVICE ENRICHMENT FRAMEWORK")
    print("=" * 80)
    print()

    # Create a mock session for demonstration
    import boto3

    try:
        session = boto3.Session()
        factory = ServiceHandlerFactory(session)

        print("REGISTERED SERVICE HANDLERS")
        print("-" * 40)
        handlers = factory.list_registered_handlers()
        for handler in handlers:
            if handler == "*":
                print(f"- {handler} - Dynamic Service Handler (fallback for unknown services)")
            else:
                print(f"- {handler} - Dedicated service handler")
        print()

    except Exception as e:
        print(f"Note: AWS session not available for handler demonstration: {e}")
        print("In a real environment, handlers would be initialized with valid AWS credentials.")
        print()


def demonstrate_service_specific_enrichment():
    """Demonstrate service-specific enrichment capabilities"""
    print("SERVICE-SPECIFIC ENRICHMENT CAPABILITIES")
    print("=" * 80)
    print()

    # S3 Handler Capabilities
    print("S3 AMAZON S3 HANDLER")
    print("-" * 40)
    print("Deep bucket analysis with comprehensive configuration extraction:")
    print("- Encryption Configuration - Server-side encryption settings, KMS key details")
    print("- Versioning Status - Bucket versioning configuration and status")
    print("- Lifecycle Management - Lifecycle rules and transition policies")
    print("- Public Access Controls - Public access block configuration")
    print("- Object Lock - Object lock configuration and retention policies")
    print("- Location Constraints - Bucket region and location details")
    print()

    # RDS Handler Capabilities
    print("DB AMAZON RDS HANDLER")
    print("-" * 40)
    print("Database configuration deep dive with comprehensive operational data:")
    print("- Engine Details - Database engine, version, and class information")
    print("- Storage Configuration - Allocated storage, type, and encryption settings")
    print("- High Availability - Multi-AZ deployment and backup configuration")
    print("- Security Settings - VPC security groups, subnet groups, and parameter groups")
    print("- Performance Insights - Monitoring and performance configuration")
    print("- Maintenance Windows - Backup and maintenance scheduling")
    print()

    # EC2 Handler Capabilities
    print("EC2 AMAZON EC2 HANDLER")
    print("-" * 40)
    print("Instance and volume analysis with detailed configuration data:")
    print("- Instance Configuration - Type, state, platform, and architecture details")
    print("- Network Configuration - VPC, subnet, security groups, and IP addresses")
    print("- Storage Details - EBS optimization, block device mappings, and root device info")
    print("- Security Features - IAM instance profiles, key pairs, and monitoring state")
    print("- Advanced Features - CPU options, hibernation, metadata options, and enclave settings")
    print("- Volume Attributes - Size, type, IOPS, throughput, encryption, and attachment details")
    print()

    # Lambda Handler Capabilities
    print("LAMBDA AWS LAMBDA HANDLER")
    print("-" * 40)
    print("Function configuration analysis with comprehensive runtime data:")
    print("- Runtime Environment - Runtime version, handler, and execution role")
    print("- Resource Configuration - Memory size, timeout, and ephemeral storage")
    print("- Network Configuration - VPC settings and security groups")
    print("- Code Configuration - Code size, SHA256, deployment package details")
    print("- Advanced Features - Layers, environment variables, dead letter queues")
    print("- Monitoring - Tracing configuration and logging settings")
    print()

    # ECS Handler Capabilities
    print("ECS AMAZON ECS HANDLER")
    print("-" * 40)
    print("Container service details with cluster and service configuration:")
    print("- Cluster Configuration - Status, capacity providers, and service counts")
    print("- Service Configuration - Task definitions, desired count, and deployment settings")
    print("- Network Configuration - Load balancers, service registries, and VPC settings")
    print("- Scaling Configuration - Auto scaling and capacity provider strategies")
    print()

    # EKS Handler Capabilities
    print("EKS AMAZON EKS HANDLER")
    print("-" * 40)
    print("Kubernetes cluster analysis with comprehensive configuration data:")
    print("- Cluster Configuration - Version, endpoint, and platform details")
    print("- Network Configuration - VPC settings and Kubernetes network config")
    print("- Security Configuration - Encryption, identity providers, and access controls")
    print("- Node Group Details - Instance types, scaling configuration, and launch templates")
    print("- Add-on Configuration - Installed add-ons and their versions")
    print()


def demonstrate_dynamic_discovery():
    """Demonstrate dynamic service discovery capabilities"""
    print("DYNAMIC SERVICE DISCOVERY")
    print("=" * 80)
    print()
    print("For services not explicitly supported, InvenTag includes an intelligent")
    print("dynamic discovery system that automatically attempts to enrich resources")
    print("using pattern-based API discovery.")
    print()
    print("KEY FEATURES:")
    print(
        "- Pattern-Based API Discovery - Automatically discovers and tests read-only API operations"
    )
    print(
        "- Intelligent Parameter Mapping - Maps resource identifiers to appropriate API parameters"
    )
    print("- Response Analysis - Extracts meaningful attributes from API responses")
    print("- Caching System - Optimizes performance by caching successful patterns")
    print("- Comprehensive Coverage - Attempts multiple API patterns for maximum data extraction")
    print()
    print("DISCOVERY PROCESS:")
    print(
        "1. Operation Pattern Generation - Creates potential API operation names based on resource type"
    )
    print("2. Parameter Pattern Matching - Maps resource identifiers to API parameters")
    print("3. Safe API Execution - Validates operations as read-only before execution")
    print("4. Response Extraction - Intelligently extracts attributes from API responses")
    print("5. Result Caching - Caches successful patterns for performance optimization")
    print()


def simulate_enrichment_process(resources):
    """Simulate the enrichment process with sample data"""
    print("ENRICHMENT SIMULATION")
    print("=" * 80)
    print()

    print("Note: This is a simulation using sample data. In a real environment,")
    print("the enricher would connect to AWS APIs to extract detailed attributes.")
    print()

    # Simulate enrichment statistics
    enrichment_stats = {
        "total_resources": len(resources),
        "enriched_resources": 0,
        "failed_enrichments": 0,
        "unknown_services_count": 0,
    }

    discovered_services = set()
    unknown_services = set()

    print("PROCESSING RESOURCES:")
    print("-" * 40)

    for resource in resources:
        service = resource.get("service", "")
        resource_type = resource.get("type", "")
        resource_name = resource.get("name", resource.get("id", "unknown"))

        discovered_services.add(service)

        # Simulate enrichment based on service type
        if service in ["S3", "RDS", "EC2", "Lambda", "ECS", "EKS"]:
            print(f"[OK] {service}/{resource_type}: {resource_name}")
            print(f"   Handler: Dedicated {service}Handler")
            print(f"   Status: Successfully enriched with service-specific attributes")
            enrichment_stats["enriched_resources"] += 1
        else:
            print(f"[DYNAMIC] {service}/{resource_type}: {resource_name}")
            print(f"   Handler: DynamicServiceHandler")
            print(f"   Status: Attempting pattern-based discovery")
            unknown_services.add(service)
            enrichment_stats["unknown_services_count"] += 1
            enrichment_stats["enriched_resources"] += 1  # Assume dynamic discovery succeeds

        print()

    # Print enrichment statistics
    print("ENRICHMENT STATISTICS")
    print("-" * 40)
    print(f"Total Resources Processed: {enrichment_stats['total_resources']}")
    print(f"Successfully Enriched: {enrichment_stats['enriched_resources']}")
    print(f"Failed Enrichments: {enrichment_stats['failed_enrichments']}")
    print(f"Unknown Services: {enrichment_stats['unknown_services_count']}")
    print()

    print("DISCOVERED SERVICES:")
    for service in sorted(discovered_services):
        if service in unknown_services:
            print(f"- {service} (handled by dynamic discovery)")
        else:
            print(f"- {service} (dedicated handler)")
    print()

    return enrichment_stats


def demonstrate_enriched_data_structure():
    """Demonstrate the structure of enriched resource data"""
    print("ENRICHED DATA STRUCTURE")
    print("=" * 80)
    print()

    print("After enrichment, resources include a 'service_attributes' field with")
    print("detailed service-specific configuration data:")
    print()

    # Example S3 enriched resource
    s3_example = {
        "arn": "arn:aws:s3:::production-data-bucket",
        "id": "production-data-bucket",
        "service": "S3",
        "type": "Bucket",
        "region": "us-east-1",
        "name": "production-data-bucket",
        "tags": {"Environment": "production", "Owner": "data-team"},
        "service_attributes": {
            "encryption": {
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": "arn:aws:kms:us-east-1:123456789012:key/12345",
                        }
                    }
                ]
            },
            "versioning_status": "Enabled",
            "location": "us-east-1",
            "lifecycle_rules": [
                {
                    "ID": "transition-to-ia",
                    "Status": "Enabled",
                    "Transitions": [{"Days": 30, "StorageClass": "STANDARD_IA"}],
                }
            ],
            "public_access_block": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
            "object_lock": None,
        },
        "enrichment_metadata": {
            "handler_type": "S3Handler",
            "enriched_at": "2023-12-01T12:00:00Z",
            "read_only_operations": [
                "get_bucket_encryption",
                "get_bucket_versioning",
                "get_bucket_location",
                "get_bucket_lifecycle_configuration",
                "get_public_access_block",
            ],
        },
    }

    print("EXAMPLE: S3 Bucket with Enriched Attributes")
    print("-" * 50)
    print(json.dumps(s3_example, indent=2, default=str))
    print()


def demonstrate_usage_patterns():
    """Demonstrate common usage patterns for service enrichment"""
    print("USAGE PATTERNS")
    print("=" * 80)
    print()

    print("1. BASIC ENRICHMENT")
    print("-" * 30)
    print(
        """
from inventag.discovery.service_enrichment import ServiceAttributeEnricher

# Initialize enricher
enricher = ServiceAttributeEnricher()

# Enrich all resources with service-specific attributes
enriched_resources = enricher.enrich_resources_with_attributes(resources)

# Get enrichment statistics
stats = enricher.get_enrichment_statistics()
print(f"Enriched: {stats['statistics']['enriched_resources']}")
"""
    )

    print("2. SERVICE-SPECIFIC ANALYSIS")
    print("-" * 30)
    print(
        """
# Analyze S3 buckets
s3_resources = [r for r in resources if r.get('service') == 'S3']
enriched_s3 = enricher.enrich_resources_with_attributes(s3_resources)

for bucket in enriched_s3:
    if 'service_attributes' in bucket:
        attrs = bucket['service_attributes']
        print(f"Bucket: {bucket['name']}")
        print(f"  Encryption: {attrs.get('encryption', {}).get('enabled')}")
        print(f"  Versioning: {attrs.get('versioning_status')}")
"""
    )

    print("3. CUSTOM SERVICE HANDLERS")
    print("-" * 30)
    print(
        """
from inventag.discovery.service_enrichment import ServiceHandler

class CustomServiceHandler(ServiceHandler):
    def can_handle(self, service: str, resource_type: str) -> bool:
        return service.upper() == 'CUSTOM_SERVICE'
    
    def _define_read_only_operations(self) -> List[str]:
        return ['describe_custom_resource', 'get_custom_configuration']
    
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        # Custom enrichment logic
        return {**resource, 'service_attributes': attributes}

# Register custom handler
enricher.register_custom_handler('CUSTOM_SERVICE', CustomServiceHandler)
"""
    )

    print("4. INTEGRATION WITH STATE MANAGEMENT")
    print("-" * 30)
    print(
        """
from inventag.state import StateManager

# Save enriched resources to state
state_manager = StateManager()
state_id = state_manager.save_state(
    resources=enriched_resources,
    account_id='123456789012',
    regions=['us-east-1', 'us-west-2'],
    tags={'enrichment': 'enabled'}
)
"""
    )


def main():
    """Main demo function"""
    print("Service Enrichment Framework Demonstration")
    print("=" * 60)
    print()

    # Print service handler information
    print_service_handler_info()

    # Demonstrate service-specific enrichment capabilities
    demonstrate_service_specific_enrichment()

    # Demonstrate dynamic discovery
    demonstrate_dynamic_discovery()

    # Create sample resources
    resources = create_sample_resources()
    print(f"Created {len(resources)} sample resources for demonstration")
    print()

    # Simulate enrichment process
    stats = simulate_enrichment_process(resources)

    # Demonstrate enriched data structure
    demonstrate_enriched_data_structure()

    # Demonstrate usage patterns
    demonstrate_usage_patterns()

    print("BENEFITS OF SERVICE ENRICHMENT")
    print("=" * 80)
    print("- Enhanced Compliance Analysis - Detailed configuration data for compliance checking")
    print("- Security Auditing - Deep security configuration analysis")
    print("- Cost Optimization - Resource utilization and configuration insights")
    print("- Operational Intelligence - Comprehensive operational data for monitoring")
    print("- Change Impact Analysis - Detailed attribute tracking for change detection")
    print("- Custom Integration - Extensible framework for proprietary services")
    print()

    print("Demo completed successfully!")
    print()
    print("To see service enrichment in action with real AWS resources:")
    print("1. Configure AWS credentials: aws configure")
    print('2. Run: python -c "')
    print("from inventag import AWSResourceInventory")
    print("from inventag.discovery.service_enrichment import ServiceAttributeEnricher")
    print("inventory = AWSResourceInventory(regions=['us-east-1'])")
    print("resources = inventory.discover_resources()")
    print("enricher = ServiceAttributeEnricher()")
    print("enriched = enricher.enrich_resources_with_attributes(resources)")
    print("print(f'Enriched {len(enriched)} resources')")
    print('"')


if __name__ == "__main__":
    main()
