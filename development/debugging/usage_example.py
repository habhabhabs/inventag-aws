#!/usr/bin/env python3
"""
Usage Example for Optimized Discovery System
Shows how to use the optimized discovery system in your existing code.
"""

import sys
import logging
from datetime import datetime

# Import the optimized discovery system
from optimized_aws_discovery import OptimizedAWSDiscovery


def example_usage():
    """Example of how to use the optimized discovery system."""

    print("🚀 Optimized Discovery Usage Example")
    print("=" * 50)

    # Configure logging (optional)
    logging.basicConfig(level=logging.INFO)

    # Initialize the optimized discovery system
    # You can specify regions, or it will use all available regions
    discovery = OptimizedAWSDiscovery(regions=["us-east-1", "us-west-2"])

    print("\n1. 🔍 Starting Discovery...")
    start_time = datetime.now()

    # Discover all resources using the optimized system
    resources = discovery.discover_all_services()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n2. 📊 Discovery Complete!")
    print(f"   - Found {len(resources)} resources")
    print(f"   - Time taken: {duration:.2f} seconds")
    print(f"   - Rate: {len(resources)/duration:.2f} resources/second")

    # Analyze the results
    print(f"\n3. 🔬 Analysis:")

    # Group by service
    services = {}
    for resource in resources:
        service = resource.service_name
        services[service] = services.get(service, 0) + 1

    print(f"   Services discovered: {len(services)}")
    for service, count in sorted(services.items()):
        print(f"   - {service}: {count} resources")

    # Quality metrics
    high_quality = [r for r in resources if r.confidence_score >= 0.7]
    print(f"\n   High-quality resources: {len(high_quality)}")

    # Show some examples
    print(f"\n4. 🌟 Sample Resources:")
    for i, resource in enumerate(resources[:5]):
        print(f"   {i+1}. {resource.service_name} - {resource.resource_type}")
        print(f"      Name: {resource.resource_name or 'N/A'}")
        print(f"      ID: {resource.resource_id}")
        print(f"      Region: {resource.region}")
        print(f"      Confidence: {resource.confidence_score:.2f}")
        print()

    return resources


def compare_with_legacy():
    """Compare optimized discovery with legacy approach."""

    print("\n🔄 Comparison with Legacy System")
    print("=" * 50)

    # You can also use it alongside your existing inventory system
    try:
        from inventag.discovery import AWSResourceInventory

        print("\n📊 Running Legacy Discovery...")
        legacy_inventory = AWSResourceInventory(regions=["us-east-1"])
        legacy_inventory.configure_discovery_mode(use_intelligent=False)

        start_time = datetime.now()
        legacy_resources = legacy_inventory.discover_resources()
        legacy_time = (datetime.now() - start_time).total_seconds()

        print("\n🧠 Running Optimized Discovery...")
        optimized_discovery = OptimizedAWSDiscovery(regions=["us-east-1"])

        start_time = datetime.now()
        optimized_resources = optimized_discovery.discover_all_services()
        optimized_time = (datetime.now() - start_time).total_seconds()

        print(f"\n📈 Comparison Results:")
        print(f"   Legacy System:")
        print(f"   - Resources: {len(legacy_resources)}")
        print(f"   - Time: {legacy_time:.2f}s")
        print(f"   - Rate: {len(legacy_resources)/legacy_time:.2f} resources/s")

        print(f"\n   Optimized System:")
        print(f"   - Resources: {len(optimized_resources)}")
        print(f"   - Time: {optimized_time:.2f}s")
        print(f"   - Rate: {len(optimized_resources)/optimized_time:.2f} resources/s")

        # Service comparison
        legacy_services = set(r.get("service", "") for r in legacy_resources)
        optimized_services = set(r.service_name for r in optimized_resources)

        new_services = optimized_services - legacy_services
        if new_services:
            print(f"\n   🆕 New services found by optimized system: {sorted(new_services)}")

    except ImportError:
        print("   ⚠️  Legacy system not available for comparison")


if __name__ == "__main__":
    # Run the example
    resources = example_usage()

    # Compare with legacy if available
    compare_with_legacy()

    print("\n✅ Example complete!")
    print("\nYou can now use OptimizedAWSDiscovery in your own scripts.")
