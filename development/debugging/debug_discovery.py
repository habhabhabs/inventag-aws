#!/usr/bin/env python3
"""
Live debugging script for AWS resource discovery optimization.
This script helps identify and fix detection issues in the intelligent discovery system.
"""

import sys
import json
import logging
from typing import Dict, List, Any
from datetime import datetime

# Add project root to path
sys.path.append(".")

from inventag.discovery import AWSResourceInventory
from inventag.discovery.intelligent_discovery import (
    IntelligentAWSDiscovery,
    IntelligentFieldMapper,
)

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class DiscoveryDebugger:
    """Debug and optimize AWS resource discovery."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.test_region = "us-east-1"  # Focus on one region for debugging

    def compare_discovery_methods(self):
        """Compare legacy vs intelligent discovery methods."""
        print("🔍 Comparing Discovery Methods")
        print("=" * 50)

        # Test legacy discovery
        print("\n1. Testing Legacy Discovery...")
        legacy_inventory = AWSResourceInventory(regions=[self.test_region])
        legacy_inventory.configure_discovery_mode(use_intelligent=False, standardized_output=False)
        legacy_resources = legacy_inventory.discover_resources()

        print(f"Legacy Discovery: Found {len(legacy_resources)} resources")
        legacy_services = set(r.get("service", "unknown") for r in legacy_resources)
        print(f"Legacy Services: {sorted(legacy_services)}")

        # Test intelligent discovery
        print("\n2. Testing Intelligent Discovery...")
        intelligent_inventory = AWSResourceInventory(regions=[self.test_region])
        intelligent_inventory.configure_discovery_mode(
            use_intelligent=True, standardized_output=True
        )
        intelligent_resources = intelligent_inventory.discover_resources()

        print(f"Intelligent Discovery: Found {len(intelligent_resources)} resources")
        intelligent_services = set(r.get("service", "unknown") for r in intelligent_resources)
        print(f"Intelligent Services: {sorted(intelligent_services)}")

        # Compare results
        print("\n3. Comparison Analysis")
        print("-" * 30)

        missing_in_intelligent = legacy_services - intelligent_services
        extra_in_intelligent = intelligent_services - legacy_services

        if missing_in_intelligent:
            print(f"❌ Services missing in intelligent discovery: {missing_in_intelligent}")

        if extra_in_intelligent:
            print(f"✅ Extra services found by intelligent discovery: {extra_in_intelligent}")

        # Resource type analysis
        print("\n4. Resource Type Analysis")
        print("-" * 30)

        legacy_types = {}
        for resource in legacy_resources:
            service = resource.get("service", "unknown")
            res_type = resource.get("type", "unknown")
            if service not in legacy_types:
                legacy_types[service] = set()
            legacy_types[service].add(res_type)

        intelligent_types = {}
        for resource in intelligent_resources:
            service = resource.get("service", "unknown")
            res_type = resource.get("type", "unknown")
            if service not in intelligent_types:
                intelligent_types[service] = set()
            intelligent_types[service].add(res_type)

        for service in sorted(legacy_services | intelligent_services):
            legacy_service_types = legacy_types.get(service, set())
            intelligent_service_types = intelligent_types.get(service, set())

            print(f"\n{service}:")
            print(f"  Legacy types: {sorted(legacy_service_types)}")
            print(f"  Intelligent types: {sorted(intelligent_service_types)}")

            missing_types = legacy_service_types - intelligent_service_types
            if missing_types:
                print(f"  ❌ Missing in intelligent: {sorted(missing_types)}")

        return {
            "legacy": {
                "count": len(legacy_resources),
                "services": legacy_services,
                "resources": legacy_resources,
            },
            "intelligent": {
                "count": len(intelligent_resources),
                "services": intelligent_services,
                "resources": intelligent_resources,
            },
        }

    def test_field_mapping(self):
        """Test the intelligent field mapping system."""
        print("\n🧠 Testing Field Mapping Intelligence")
        print("=" * 50)

        mapper = IntelligentFieldMapper()

        # Test with sample AWS API responses
        test_cases = [
            {
                "name": "EC2 Instance",
                "data": {
                    "InstanceId": "i-1234567890abcdef0",
                    "InstanceType": "m5.large",
                    "State": {"Name": "running"},
                    "LaunchTime": "2023-01-01T00:00:00.000Z",
                    "Tags": [
                        {"Key": "Name", "Value": "WebServer"},
                        {"Key": "Environment", "Value": "Production"},
                    ],
                    "VpcId": "vpc-12345678",
                    "SubnetId": "subnet-12345678",
                    "SecurityGroups": [{"GroupId": "sg-12345678", "GroupName": "web-sg"}],
                },
                "service": "ec2",
                "operation": "DescribeInstances",
            },
            {
                "name": "S3 Bucket",
                "data": {
                    "Name": "my-test-bucket",
                    "CreationDate": "2023-01-01T00:00:00.000Z",
                },
                "service": "s3",
                "operation": "ListBuckets",
            },
            {
                "name": "Lambda Function",
                "data": {
                    "FunctionName": "my-function",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
                    "Runtime": "python3.9",
                    "LastModified": "2023-01-01T00:00:00.000Z",
                    "VpcConfig": {"VpcId": "vpc-12345678"},
                    "Environment": {"Variables": {"ENV": "prod"}},
                },
                "service": "lambda",
                "operation": "ListFunctions",
            },
        ]

        for test_case in test_cases:
            print(f"\nTesting: {test_case['name']}")
            print("-" * 20)

            try:
                standard_resource = mapper.analyze_and_map_resource(
                    test_case["data"],
                    test_case["service"],
                    test_case["operation"],
                    self.test_region,
                    "123456789012",
                )

                print(f"✅ Resource ID: {standard_resource.resource_id}")
                print(f"✅ Resource Name: {standard_resource.resource_name}")
                print(f"✅ Resource Type: {standard_resource.resource_type}")
                print(f"✅ Tags: {standard_resource.tags}")
                print(f"✅ Confidence Score: {standard_resource.confidence_score:.2f}")

                if standard_resource.confidence_score < 0.7:
                    print(f"⚠️  Low confidence score - needs improvement")

            except Exception as e:
                print(f"❌ Field mapping failed: {e}")

    def test_service_discovery(self, service_name: str):
        """Test discovery for a specific service."""
        print(f"\n🔧 Testing Service Discovery: {service_name}")
        print("=" * 50)

        try:
            intelligent_discovery = IntelligentAWSDiscovery(regions=[self.test_region])
            resources = intelligent_discovery.discover_service(service_name)

            print(f"Found {len(resources)} resources for {service_name}")

            for i, resource in enumerate(resources[:5]):  # Show first 5
                print(
                    f"{i+1}. {resource.resource_type} - {resource.resource_name or resource.resource_id}"
                )
                print(f"   Confidence: {resource.confidence_score:.2f}")
                print(f"   API Operation: {resource.api_operation}")

                if resource.confidence_score < 0.7:
                    print(f"   ⚠️  Issues detected:")
                    if not resource.resource_name:
                        print(f"      - Missing resource name")
                    if not resource.tags:
                        print(f"      - No tags found")
                    if resource.resource_type == "Unknown":
                        print(f"      - Unknown resource type")

        except Exception as e:
            print(f"❌ Service discovery failed for {service_name}: {e}")
            import traceback

            traceback.print_exc()

    def optimize_discovery(self):
        """Identify and suggest optimizations."""
        print("\n⚡ Discovery Optimization Analysis")
        print("=" * 50)

        # Test current performance
        start_time = datetime.now()
        inventory = AWSResourceInventory(regions=[self.test_region])
        resources = inventory.discover_resources()
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()

        print(f"Current Performance:")
        print(f"  - Total Resources: {len(resources)}")
        print(f"  - Discovery Time: {duration:.2f} seconds")
        print(f"  - Resources/Second: {len(resources)/duration:.2f}")

        # Analyze resource quality
        quality_issues = []
        for resource in resources:
            if not resource.get("name") or resource.get("name") == resource.get("id"):
                quality_issues.append("missing_names")
            if not resource.get("tags"):
                quality_issues.append("missing_tags")
            if resource.get("type") == "Unknown":
                quality_issues.append("unknown_types")

        print(f"\nQuality Analysis:")
        print(f"  - Resources with missing names: {quality_issues.count('missing_names')}")
        print(f"  - Resources with missing tags: {quality_issues.count('missing_tags')}")
        print(f"  - Resources with unknown types: {quality_issues.count('unknown_types')}")

        # Suggest optimizations
        print(f"\n💡 Optimization Suggestions:")

        if quality_issues.count("missing_names") > len(resources) * 0.3:
            print("  1. Improve name extraction logic in field mapper")

        if quality_issues.count("unknown_types") > len(resources) * 0.1:
            print("  2. Enhance resource type detection patterns")

        if duration > 30:
            print("  3. Implement parallel discovery for better performance")

        if quality_issues.count("missing_tags") > len(resources) * 0.5:
            print("  4. Add fallback tag extraction methods")


def main():
    """Main debugging function."""
    debugger = DiscoveryDebugger()

    print("🚀 AWS Discovery Live Debugging Session")
    print("=" * 60)

    # 1. Compare discovery methods
    comparison = debugger.compare_discovery_methods()

    # 2. Test field mapping
    debugger.test_field_mapping()

    # 3. Test specific services that might have issues
    problem_services = ["ec2", "s3", "lambda", "rds", "cloudformation"]
    for service in problem_services:
        debugger.test_service_discovery(service)

    # 4. Optimization analysis
    debugger.optimize_discovery()

    print("\n✅ Debugging session complete!")
    print("Check the output above for specific issues and optimization opportunities.")


if __name__ == "__main__":
    main()
