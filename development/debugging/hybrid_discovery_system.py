#!/usr/bin/env python3
"""
Hybrid Discovery System - Combines Legacy Reliability with Intelligent Detection
This system provides the best of both worlds: the reliability of legacy discovery
with the intelligence and standardization of the new system.
"""

import sys
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add project root to path
sys.path.append(".")

from inventag.discovery import AWSResourceInventory
from optimized_discovery import OptimizedAWSDiscovery, OptimizedFieldMapper


class HybridDiscoverySystem:
    """
    Hybrid system that combines legacy discovery reliability with intelligent enhancement.
    """

    def __init__(self, regions: List[str] = None):
        self.logger = logging.getLogger(__name__)
        self.regions = regions or ["us-east-1"]

        # Initialize both systems
        self.legacy_inventory = AWSResourceInventory(regions=self.regions)
        self.legacy_inventory.configure_discovery_mode(
            use_intelligent=False, standardized_output=False
        )

        self.intelligent_discovery = OptimizedAWSDiscovery(regions=self.regions)
        self.field_mapper = OptimizedFieldMapper()

    def discover_resources_hybrid(self) -> List[Dict[str, Any]]:
        """
        Hybrid discovery that combines legacy reliability with intelligent enhancement.
        """

        print("🔄 Starting Hybrid Discovery System")
        print("=" * 50)

        # Step 1: Use legacy discovery for reliable resource detection
        print("\n1. 🏗️  Legacy Discovery (Reliable Detection)")
        start_time = datetime.now()
        legacy_resources = self.legacy_inventory.discover_resources()
        legacy_time = (datetime.now() - start_time).total_seconds()

        print(f"   ✅ Found {len(legacy_resources)} resources in {legacy_time:.2f}s")

        # Step 2: Use intelligent discovery for missing services
        print("\n2. 🧠 Intelligent Discovery (Missing Services)")
        start_time = datetime.now()
        intelligent_resources = self.intelligent_discovery.discover_all_services()
        intelligent_time = (datetime.now() - start_time).total_seconds()

        print(f"   ✅ Found {len(intelligent_resources)} resources in {intelligent_time:.2f}s")

        # Step 3: Merge and enhance resources
        print("\n3. 🔗 Merging and Enhancing Resources")
        merged_resources = self._merge_and_enhance_resources(
            legacy_resources, intelligent_resources
        )

        print(f"   ✅ Final result: {len(merged_resources)} enhanced resources")

        # Step 4: Quality analysis
        self._analyze_quality(merged_resources)

        return merged_resources

    def _merge_and_enhance_resources(
        self, legacy_resources: List[Dict[str, Any]], intelligent_resources: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Merge legacy and intelligent resources, enhancing with the best data from both.
        """

        # Convert intelligent resources to dict format for easier merging
        intelligent_dict = {}
        for resource in intelligent_resources:
            # Create a key for matching
            key = f"{resource.service_name}:{resource.resource_type}:{resource.resource_id}"
            intelligent_dict[key] = {
                "arn": resource.resource_arn,
                "id": resource.resource_id,
                "service": resource.service_name,
                "type": resource.resource_type,
                "name": resource.resource_name,
                "region": resource.region,
                "account_id": resource.account_id,
                "status": resource.status,
                "state": resource.state,
                "created_date": resource.created_date,
                "last_modified": resource.last_modified,
                "tags": resource.tags,
                "environment": resource.environment,
                "project": resource.project,
                "cost_center": resource.cost_center,
                "public_access": resource.public_access,
                "encrypted": resource.encrypted,
                "vpc_id": resource.vpc_id,
                "subnet_ids": resource.subnet_ids,
                "security_groups": resource.security_groups,
                "availability_zone": resource.availability_zone,
                "discovered_at": resource.discovered_at,
                "discovery_method": "Hybrid",
                "api_operation": resource.api_operation,
                "confidence_score": resource.confidence_score,
                "compliance_status": "unknown",
            }

        # Start with legacy resources as the base (they're more reliable)
        enhanced_resources = []
        legacy_keys = set()

        for legacy_resource in legacy_resources:
            # Create matching key
            key = f"{legacy_resource.get('service', '')}:{legacy_resource.get('type', '')}:{legacy_resource.get('id', '')}"
            legacy_keys.add(key)

            # Check if we have intelligent enhancement for this resource
            if key in intelligent_dict:
                intelligent_data = intelligent_dict[key]

                # Merge data, preferring legacy for core fields and intelligent for enhanced fields
                enhanced_resource = legacy_resource.copy()

                # Enhance with intelligent data where legacy is missing or less detailed
                if not enhanced_resource.get("account_id") and intelligent_data.get("account_id"):
                    enhanced_resource["account_id"] = intelligent_data["account_id"]

                if not enhanced_resource.get("status") and intelligent_data.get("status"):
                    enhanced_resource["status"] = intelligent_data["status"]

                if not enhanced_resource.get("created_date") and intelligent_data.get(
                    "created_date"
                ):
                    enhanced_resource["created_date"] = intelligent_data["created_date"]

                # Always enhance with intelligent analysis
                enhanced_resource.update(
                    {
                        "environment": intelligent_data.get("environment"),
                        "project": intelligent_data.get("project"),
                        "cost_center": intelligent_data.get("cost_center"),
                        "public_access": intelligent_data.get("public_access", False),
                        "encrypted": intelligent_data.get("encrypted"),
                        "vpc_id": intelligent_data.get("vpc_id"),
                        "subnet_ids": intelligent_data.get("subnet_ids", []),
                        "security_groups": intelligent_data.get("security_groups", []),
                        "availability_zone": intelligent_data.get("availability_zone"),
                        "discovery_method": "Hybrid",
                        "confidence_score": intelligent_data.get("confidence_score", 0.8),
                    }
                )

                enhanced_resources.append(enhanced_resource)
            else:
                # No intelligent enhancement available, use legacy as-is but mark it
                legacy_resource["discovery_method"] = "Legacy"
                legacy_resource["confidence_score"] = 0.6  # Default confidence for legacy
                enhanced_resources.append(legacy_resource)

        # Add intelligent-only resources (not found in legacy)
        for key, intelligent_data in intelligent_dict.items():
            if key not in legacy_keys:
                enhanced_resources.append(intelligent_data)

        return enhanced_resources

    def _analyze_quality(self, resources: List[Dict[str, Any]]):
        """Analyze the quality of the hybrid discovery results."""

        print("\n4. 📊 Quality Analysis")
        print("-" * 30)

        # Discovery method breakdown
        methods = {}
        for resource in resources:
            method = resource.get("discovery_method", "Unknown")
            methods[method] = methods.get(method, 0) + 1

        print("Discovery Methods:")
        for method, count in methods.items():
            print(f"  - {method}: {count} resources")

        # Confidence score analysis
        high_confidence = [r for r in resources if r.get("confidence_score", 0) >= 0.7]
        medium_confidence = [r for r in resources if 0.4 <= r.get("confidence_score", 0) < 0.7]
        low_confidence = [r for r in resources if r.get("confidence_score", 0) < 0.4]

        print(f"\nConfidence Distribution:")
        print(f"  - High (≥0.7): {len(high_confidence)}")
        print(f"  - Medium (0.4-0.7): {len(medium_confidence)}")
        print(f"  - Low (<0.4): {len(low_confidence)}")

        # Service coverage
        services = {}
        for resource in resources:
            service = resource.get("service", "Unknown")
            services[service] = services.get(service, 0) + 1

        print(f"\nService Coverage ({len(services)} services):")
        for service, count in sorted(services.items()):
            print(f"  - {service}: {count} resources")

        # Enhanced fields analysis
        enhanced_fields = {
            "environment": 0,
            "project": 0,
            "cost_center": 0,
            "public_access": 0,
            "encrypted": 0,
            "vpc_id": 0,
        }

        for resource in resources:
            for field in enhanced_fields:
                if resource.get(field):
                    enhanced_fields[field] += 1

        print(f"\nEnhanced Field Coverage:")
        for field, count in enhanced_fields.items():
            percentage = (count / len(resources)) * 100 if resources else 0
            print(f"  - {field}: {count} resources ({percentage:.1f}%)")

    def compare_with_legacy_only(self):
        """Compare hybrid results with legacy-only results."""

        print("\n🔍 Comparison: Hybrid vs Legacy-Only")
        print("=" * 50)

        # Get hybrid results
        hybrid_resources = self.discover_resources_hybrid()

        # Get legacy-only results
        print("\n📊 Legacy-Only Discovery")
        legacy_only = AWSResourceInventory(regions=self.regions)
        legacy_only.configure_discovery_mode(use_intelligent=False, standardized_output=False)
        legacy_resources = legacy_only.discover_resources()

        print(f"\nComparison Results:")
        print(f"  - Legacy-Only: {len(legacy_resources)} resources")
        print(f"  - Hybrid: {len(hybrid_resources)} resources")
        print(f"  - Improvement: +{len(hybrid_resources) - len(legacy_resources)} resources")

        # Service comparison
        legacy_services = set(r.get("service", "") for r in legacy_resources)
        hybrid_services = set(r.get("service", "") for r in hybrid_resources)

        new_services = hybrid_services - legacy_services
        if new_services:
            print(f"  - New services discovered: {sorted(new_services)}")

        # Enhanced data comparison
        legacy_with_tags = [r for r in legacy_resources if r.get("tags")]
        hybrid_with_tags = [r for r in hybrid_resources if r.get("tags")]

        print(
            f"  - Resources with tags - Legacy: {len(legacy_with_tags)}, Hybrid: {len(hybrid_with_tags)}"
        )

        return hybrid_resources


def main():
    """Main function to demonstrate the hybrid discovery system."""

    # Configure logging
    logging.basicConfig(level=logging.WARNING)  # Reduce noise

    print("🚀 Hybrid AWS Discovery System")
    print("Combining Legacy Reliability with Intelligent Enhancement")
    print("=" * 60)

    # Initialize hybrid system
    hybrid_system = HybridDiscoverySystem(regions=["us-east-1"])

    # Run hybrid discovery
    start_time = datetime.now()
    resources = hybrid_system.discover_resources_hybrid()
    total_time = (datetime.now() - start_time).total_seconds()

    print(f"\n🎯 Final Results:")
    print(f"  - Total Resources: {len(resources)}")
    print(f"  - Total Time: {total_time:.2f} seconds")
    print(f"  - Resources/Second: {len(resources)/total_time:.2f}")

    # Show sample enhanced resources
    print(f"\n🌟 Sample Enhanced Resources:")
    enhanced_resources = [r for r in resources if r.get("discovery_method") == "Hybrid"][:5]

    for i, resource in enumerate(enhanced_resources):
        print(f"  {i+1}. {resource.get('service')} - {resource.get('type')}")
        print(f"     Name: {resource.get('name', 'N/A')}")
        print(f"     Environment: {resource.get('environment', 'N/A')}")
        print(f"     Public Access: {resource.get('public_access', 'N/A')}")
        print(f"     Confidence: {resource.get('confidence_score', 0):.2f}")

    print(f"\n✅ Hybrid Discovery Complete!")
    print(f"The system successfully combines legacy reliability with intelligent enhancement.")

    return resources


if __name__ == "__main__":
    main()
