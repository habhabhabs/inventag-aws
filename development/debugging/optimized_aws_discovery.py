#!/usr/bin/env python3
"""
Optimized AWS Resource Discovery System
Drop-in replacement with enhanced detection capabilities.
"""

import json
import re
import logging
import concurrent.futures
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# Import existing classes
try:
    from inventag.discovery.intelligent_discovery import (
        StandardResource,
        IntelligentFieldMapper,
        IntelligentAWSDiscovery,
    )
except ImportError:
    # Fallback for standalone usage
    import sys
    import os

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from inventag.discovery.intelligent_discovery import (
        StandardResource,
        IntelligentFieldMapper,
        IntelligentAWSDiscovery,
    )


class OptimizedFieldMapper(IntelligentFieldMapper):
    """Optimized field mapper with enhanced service-specific patterns."""

    def __init__(self):
        super().__init__()

        # Enhanced service patterns based on debugging findings
        self.service_enhancements = {
            "cloudfront": {
                "name_extractors": ["DomainName", "Id"],
                "type_indicators": ["Distribution"],
                "operations": ["ListDistributions"],
            },
            "iam": {
                "name_extractors": ["RoleName", "UserName", "PolicyName", "GroupName"],
                "type_indicators": ["Role", "User", "Policy", "Group"],
                "operations": ["ListRoles", "ListUsers", "ListPolicies", "ListGroups"],
            },
            "route53": {
                "name_extractors": ["Name", "Id"],
                "type_indicators": ["HostedZone"],
                "operations": ["ListHostedZones"],
            },
            "s3": {
                "name_extractors": ["Name"],
                "type_indicators": ["Bucket"],
                "operations": ["ListBuckets"],
            },
            "lambda": {
                "name_extractors": ["FunctionName"],
                "type_indicators": ["Function"],
                "operations": ["ListFunctions"],
            },
        }

    def analyze_and_map_resource(
        self,
        raw_data: Dict[str, Any],
        service_name: str,
        operation_name: str,
        region: str,
        account_id: str = None,
    ) -> StandardResource:
        """Enhanced resource mapping with service-specific optimizations."""

        try:
            # Use service-specific extraction if available
            service_key = service_name.lower()
            if service_key in self.service_enhancements:
                return self._extract_with_service_pattern(
                    raw_data, service_name, operation_name, region, account_id
                )
            else:
                # Fall back to parent method
                return super().analyze_and_map_resource(
                    raw_data, service_name, operation_name, region, account_id
                )

        except Exception as e:
            self.logger.error(f"Optimized mapping failed for {service_name}: {e}")
            return self._create_fallback_resource(raw_data, service_name, region)

    def _extract_with_service_pattern(
        self,
        raw_data: Dict[str, Any],
        service_name: str,
        operation_name: str,
        region: str,
        account_id: str = None,
    ) -> StandardResource:
        """Extract resource using service-specific patterns."""

        service_key = service_name.lower()
        patterns = self.service_enhancements[service_key]

        # Extract resource ID using service-specific name extractors
        resource_id = "unknown"
        resource_name = None

        for extractor in patterns["name_extractors"]:
            if extractor in raw_data and raw_data[extractor]:
                if not resource_id or resource_id == "unknown":
                    resource_id = str(raw_data[extractor])
                if not resource_name:
                    resource_name = str(raw_data[extractor])
                break

        # Determine resource type
        resource_type = "Resource"
        for type_indicator in patterns["type_indicators"]:
            if type_indicator.lower() in operation_name.lower():
                resource_type = type_indicator
                break

        # Create standard resource
        resource = StandardResource(
            service_name=self._normalize_service_name(service_name),
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            region=region,
            account_id=account_id or self._extract_account_from_data(raw_data),
            api_operation=operation_name,
            raw_data=raw_data,
        )

        # Extract additional fields
        resource.resource_arn = self._extract_arn(raw_data)
        resource.status = self._extract_status(raw_data)
        resource.created_date = self._extract_creation_date(raw_data)
        resource.tags = self._extract_tags(raw_data)

        # Enhanced confidence scoring
        resource.confidence_score = self._calculate_optimized_confidence(resource)

        return resource

    def _calculate_optimized_confidence(self, resource: StandardResource) -> float:
        """Calculate confidence score with optimized weights."""

        score = 0.0

        # Core fields (high weight)
        if resource.resource_id and resource.resource_id != "unknown":
            score += 0.3
        if resource.resource_name:
            score += 0.25
        if resource.resource_type and resource.resource_type != "Unknown":
            score += 0.2

        # Metadata (medium weight)
        if resource.resource_arn:
            score += 0.1
        if resource.tags:
            score += 0.05
        if resource.status:
            score += 0.05
        if resource.created_date:
            score += 0.05

        return min(score, 1.0)

    def _create_fallback_resource(
        self, raw_data: Dict[str, Any], service_name: str, region: str
    ) -> StandardResource:
        """Create a basic resource when enhanced mapping fails."""

        return StandardResource(
            service_name=service_name,
            resource_type="Resource",
            resource_id=str(raw_data.get("Id", raw_data.get("Name", "unknown"))),
            region=region,
            confidence_score=0.2,
            raw_data=raw_data,
        )


class OptimizedAWSDiscovery(IntelligentAWSDiscovery):
    """Optimized discovery system with better service coverage and performance."""

    def __init__(self, session: boto3.Session = None, regions: List[str] = None):
        super().__init__(session, regions)
        self.field_mapper = OptimizedFieldMapper()

        # Focus on services that were problematic in the original system
        self.priority_services = [
            "cloudfront",  # Was missing distributions
            "iam",  # Was missing roles/users
            "route53",  # Was missing hosted zones
            "s3",  # Had detection issues
            "lambda",  # Had detection issues
            "ec2",  # Core service
            "rds",  # Database service
            "cloudwatch",  # Monitoring
        ]

        # Performance settings
        self.max_workers = 3
        self.enable_parallel = True
        self.operation_timeout = 15

    def discover_all_services(self) -> List[StandardResource]:
        """Optimized discovery focusing on problematic services."""

        self.logger.info("Starting optimized AWS discovery with enhanced service coverage...")

        if self.enable_parallel:
            return self._discover_parallel()
        else:
            return self._discover_sequential()

    def _discover_parallel(self) -> List[StandardResource]:
        """Parallel discovery for better performance."""

        all_resources = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit tasks for priority services
            future_to_service = {
                executor.submit(self._safe_discover_service, service): service
                for service in self.priority_services
            }

            # Collect results
            for future in concurrent.futures.as_completed(future_to_service, timeout=60):
                service = future_to_service[future]
                try:
                    resources = future.result(timeout=self.operation_timeout)
                    all_resources.extend(resources)
                    self.logger.info(
                        f"Optimized discovery: {service} -> {len(resources)} resources"
                    )
                except Exception as e:
                    self.logger.warning(f"Parallel discovery failed for {service}: {e}")

        # Deduplicate
        all_resources = self._intelligent_deduplication(all_resources)
        self.discovered_resources.extend(all_resources)

        self.logger.info(f"Optimized parallel discovery complete: {len(all_resources)} resources")
        return all_resources

    def _discover_sequential(self) -> List[StandardResource]:
        """Sequential discovery as fallback."""

        all_resources = []

        for service in self.priority_services:
            try:
                resources = self._safe_discover_service(service)
                all_resources.extend(resources)
                self.logger.info(f"Sequential discovery: {service} -> {len(resources)} resources")
            except Exception as e:
                self.logger.warning(f"Sequential discovery failed for {service}: {e}")

        all_resources = self._intelligent_deduplication(all_resources)
        self.discovered_resources.extend(all_resources)

        return all_resources

    def _safe_discover_service(self, service_name: str) -> List[StandardResource]:
        """Safely discover a service with error handling."""

        try:
            return self.discover_service(service_name)
        except Exception as e:
            self.logger.error(f"Service discovery failed for {service_name}: {e}")
            return []

    def discover_service(self, service_name: str) -> List[StandardResource]:
        """Enhanced service discovery with optimized operation selection."""

        service_resources = []

        for region in self.regions:
            try:
                # Skip global services for non-primary regions
                if self._is_global_service(service_name) and region != "us-east-1":
                    continue

                client = self.session.client(service_name, region_name=region)
                operations = self._get_optimized_operations(service_name, client)

                # Try operations until we find resources
                for operation_name in operations:
                    try:
                        resources = self._discover_via_operation(
                            client, operation_name, service_name, region
                        )
                        service_resources.extend(resources)

                        # Stop after finding resources to avoid redundant calls
                        if resources:
                            break

                    except Exception as e:
                        self.logger.debug(
                            f"Operation {operation_name} failed for {service_name}: {e}"
                        )
                        continue

            except Exception as e:
                self.logger.warning(f"Failed to create {service_name} client in {region}: {e}")

        return self._intelligent_deduplication(service_resources)

    def _get_optimized_operations(self, service_name: str, client) -> List[str]:
        """Get optimized operations for a service."""

        all_operations = client._service_model.operation_names

        # Use service-specific operations if available
        service_key = service_name.lower()
        if service_key in self.field_mapper.service_enhancements:
            preferred_ops = self.field_mapper.service_enhancements[service_key]["operations"]
            operations = [op for op in preferred_ops if op in all_operations]
            if operations:
                return operations

        # Fallback to generic operations
        discovery_ops = [
            op
            for op in all_operations
            if op.startswith(("List", "Describe"))
            and not any(skip in op for skip in ["Policy", "Version", "Status", "Health"])
        ]

        # Prioritize List operations
        list_ops = [op for op in discovery_ops if op.startswith("List")]
        describe_ops = [op for op in discovery_ops if op.startswith("Describe")]

        return list_ops[:2] + describe_ops[:1]  # Limit to 3 operations max

    def _is_global_service(self, service_name: str) -> bool:
        """Check if service is global."""

        global_services = {"cloudfront", "iam", "route53", "waf"}
        return service_name.lower() in global_services


def test_optimized_system():
    """Test the optimized discovery system."""

    print("🧪 Testing Optimized Discovery System")
    print("=" * 50)

    # Initialize optimized discovery
    discovery = OptimizedAWSDiscovery(regions=["us-east-1"])

    start_time = datetime.now()
    resources = discovery.discover_all_services()
    end_time = datetime.now()

    duration = (end_time - start_time).total_seconds()

    print(f"\n✅ Optimized Discovery Results:")
    print(f"  - Total Resources: {len(resources)}")
    print(f"  - Discovery Time: {duration:.2f} seconds")
    print(f"  - Resources/Second: {len(resources)/duration:.2f}")

    # Service breakdown
    services = {}
    for resource in resources:
        service = resource.service_name
        services[service] = services.get(service, 0) + 1

    print(f"\n📊 Service Coverage:")
    for service, count in sorted(services.items()):
        print(f"  - {service}: {count} resources")

    # Quality analysis
    high_conf = [r for r in resources if r.confidence_score >= 0.7]
    medium_conf = [r for r in resources if 0.4 <= r.confidence_score < 0.7]
    low_conf = [r for r in resources if r.confidence_score < 0.4]

    print(f"\n🎯 Quality Analysis:")
    print(f"  - High Confidence (≥0.7): {len(high_conf)}")
    print(f"  - Medium Confidence (0.4-0.7): {len(medium_conf)}")
    print(f"  - Low Confidence (<0.4): {len(low_conf)}")

    # Show sample resources
    print(f"\n🌟 Sample High-Quality Resources:")
    for i, resource in enumerate(high_conf[:3]):
        print(f"  {i+1}. {resource.service_name} - {resource.resource_type}")
        print(f"     Name: {resource.resource_name or 'N/A'}")
        print(f"     ID: {resource.resource_id}")
        print(f"     Confidence: {resource.confidence_score:.2f}")

    return resources


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Test the optimized system
    test_optimized_system()
