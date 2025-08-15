#!/usr/bin/env python3
"""
Optimized AWS Resource Discovery System
Addresses the issues found in the debugging session and provides enhanced detection.
"""

import json
import re
import logging
import asyncio
import concurrent.futures
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# Import the existing classes to extend them
from inventag.discovery.intelligent_discovery import (
    StandardResource,
    IntelligentFieldMapper,
    IntelligentAWSDiscovery,
)


class OptimizedFieldMapper(IntelligentFieldMapper):
    """Enhanced field mapper with better detection patterns."""

    def __init__(self):
        super().__init__()

        # Enhanced service-specific patterns based on debugging findings
        self.enhanced_service_patterns = {
            "cloudfront": {
                "resource_types": ["Distribution"],
                "id_patterns": [r"E[A-Z0-9]+"],
                "operations": ["ListDistributions", "GetDistribution"],
                "name_fields": ["DomainName", "Id"],
                "region_dependent": False,
                "global_service": True,
            },
            "iam": {
                "resource_types": ["Role", "User", "Policy", "Group"],
                "operations": ["ListRoles", "ListUsers", "ListPolicies"],
                "name_fields": ["RoleName", "UserName", "PolicyName"],
                "region_dependent": False,
                "global_service": True,
            },
            "route53": {
                "resource_types": ["HostedZone", "RecordSet"],
                "id_patterns": [r"Z[0-9A-Z]+"],
                "operations": ["ListHostedZones", "ListResourceRecordSets"],
                "name_fields": ["Name", "Id"],
                "region_dependent": False,
                "global_service": True,
            },
            "s3": {
                "resource_types": ["Bucket"],
                "operations": ["ListBuckets"],
                "name_fields": ["Name"],
                "region_dependent": False,
                "global_service": True,
            },
            "lambda": {
                "resource_types": ["Function"],
                "operations": ["ListFunctions"],
                "name_fields": ["FunctionName"],
                "region_dependent": True,
            },
        }

        # Enhanced confidence scoring weights
        self.confidence_weights = {
            "has_resource_id": 2.0,
            "has_resource_name": 1.5,
            "has_resource_arn": 1.5,
            "has_correct_type": 1.0,
            "has_tags": 1.0,
            "has_status": 0.5,
            "has_creation_date": 0.5,
            "has_vpc_info": 0.5,
            "has_security_groups": 0.5,
            "has_account_id": 0.5,
        }

    def analyze_and_map_resource(
        self,
        raw_data: Dict[str, Any],
        service_name: str,
        operation_name: str,
        region: str,
        account_id: str = None,
    ) -> StandardResource:
        """Enhanced resource analysis with better field detection."""

        try:
            # Enhanced resource ID extraction
            resource_id = self._enhanced_extract_resource_id(raw_data, service_name)
            resource_type = self._enhanced_determine_resource_type(
                raw_data, operation_name, service_name
            )

            # Initialize with enhanced detection
            resource = StandardResource(
                service_name=self._normalize_service_name(service_name),
                resource_type=resource_type,
                resource_id=resource_id,
                region=region,
                account_id=account_id or self._extract_account_from_data(raw_data),
                api_operation=operation_name,
                raw_data=raw_data,
            )

            # Enhanced field extraction
            resource.resource_name = self._enhanced_extract_resource_name(raw_data, service_name)
            resource.resource_arn = self._extract_arn(raw_data)

            # Status and lifecycle with fallbacks
            resource.status = self._extract_status(raw_data) or self._extract_state(raw_data)
            resource.state = self._extract_state(raw_data) or self._extract_status(raw_data)
            resource.created_date = self._extract_creation_date(raw_data)
            resource.last_modified = self._extract_modification_date(raw_data)

            # Enhanced tag extraction
            raw_tags = self._enhanced_extract_tags(raw_data)
            resource.tags = raw_tags
            resource.name_from_tags = raw_tags.get("Name")
            resource.environment = (
                raw_tags.get("Environment") or raw_tags.get("Env") or raw_tags.get("Stage")
            )
            resource.project = (
                raw_tags.get("Project")
                or raw_tags.get("ProjectName")
                or raw_tags.get("Application")
            )
            resource.cost_center = (
                raw_tags.get("CostCenter")
                or raw_tags.get("BillingCode")
                or raw_tags.get("Department")
            )

            # Enhanced security and network detection
            resource.vpc_id = self._extract_vpc_info(raw_data)
            resource.subnet_ids = self._extract_subnet_info(raw_data)
            resource.security_groups = self._extract_security_groups(raw_data)
            resource.public_access = self._determine_public_access(raw_data, service_name)
            resource.encrypted = self._determine_encryption_status(raw_data)

            # Resource relationships
            resource.dependencies = self._identify_dependencies(raw_data)
            resource.parent_resource = self._identify_parent_resource(raw_data)

            # Enhanced confidence calculation
            resource.confidence_score = self._enhanced_calculate_confidence_score(resource)

            return resource

        except Exception as e:
            self.logger.error(f"Enhanced mapping failed for {service_name}: {e}")
            # Return basic resource with minimal info
            return StandardResource(
                service_name=service_name,
                resource_type="Unknown",
                resource_id=str(raw_data.get("Id", raw_data.get("Name", "unknown"))),
                region=region,
                confidence_score=0.1,
                raw_data=raw_data,
            )

    def _enhanced_extract_resource_id(self, data: Dict[str, Any], service_name: str) -> str:
        """Enhanced resource ID extraction with service-specific logic."""

        # Service-specific ID extraction
        service_lower = service_name.lower()
        if service_lower in self.enhanced_service_patterns:
            patterns = self.enhanced_service_patterns[service_lower]

            # Try service-specific name fields first
            for field in patterns.get("name_fields", []):
                if field in data and data[field]:
                    return str(data[field])

        # Fall back to parent method
        return super()._extract_resource_id(data)

    def _enhanced_extract_resource_name(
        self, data: Dict[str, Any], service_name: str
    ) -> Optional[str]:
        """Enhanced resource name extraction with service-specific logic."""

        # Service-specific name extraction
        service_lower = service_name.lower()
        if service_lower in self.enhanced_service_patterns:
            patterns = self.enhanced_service_patterns[service_lower]

            # Try service-specific name fields
            for field in patterns.get("name_fields", []):
                if field in data and data[field]:
                    return str(data[field])

        # CloudFront specific logic
        if service_lower == "cloudfront":
            if "DomainName" in data:
                return data["DomainName"]
            if "Aliases" in data and data["Aliases"].get("Items"):
                return data["Aliases"]["Items"][0]

        # Fall back to parent method
        return super()._extract_resource_name(data)

    def _enhanced_determine_resource_type(
        self, data: Dict[str, Any], operation_name: str, service_name: str
    ) -> str:
        """Enhanced resource type determination."""

        # Service-specific type detection
        service_lower = service_name.lower()
        if service_lower in self.enhanced_service_patterns:
            patterns = self.enhanced_service_patterns[service_lower]
            resource_types = patterns.get("resource_types", [])

            # Match operation to resource type
            if "Distribution" in operation_name and "Distribution" in resource_types:
                return "Distribution"
            elif "HostedZone" in operation_name and "HostedZone" in resource_types:
                return "HostedZone"
            elif "Bucket" in operation_name and "Bucket" in resource_types:
                return "Bucket"
            elif "Function" in operation_name and "Function" in resource_types:
                return "Function"
            elif "Role" in operation_name and "Role" in resource_types:
                return "Role"
            elif "User" in operation_name and "User" in resource_types:
                return "User"

        # Fall back to parent method
        return super()._determine_resource_type(data, operation_name, service_name)

    def _enhanced_extract_tags(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Enhanced tag extraction with multiple fallback methods."""

        tags = super()._extract_tags(data)

        # Additional tag extraction patterns
        if not tags:
            # Try nested tag structures
            for key, value in data.items():
                if isinstance(value, dict) and "Tags" in value:
                    nested_tags = value["Tags"]
                    if isinstance(nested_tags, list):
                        for tag in nested_tags:
                            if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                                tags[tag["Key"]] = tag["Value"]
                    elif isinstance(nested_tags, dict):
                        tags.update(nested_tags)

        return tags

    def _enhanced_calculate_confidence_score(self, resource: StandardResource) -> float:
        """Enhanced confidence scoring with weighted factors."""

        score = 0.0
        total_weight = sum(self.confidence_weights.values())

        # Apply weighted scoring
        if resource.resource_id and resource.resource_id != "unknown":
            score += self.confidence_weights["has_resource_id"]

        if resource.resource_name:
            score += self.confidence_weights["has_resource_name"]

        if resource.resource_arn:
            score += self.confidence_weights["has_resource_arn"]

        if resource.resource_type and resource.resource_type != "Unknown":
            score += self.confidence_weights["has_correct_type"]

        if resource.tags:
            score += self.confidence_weights["has_tags"]

        if resource.status:
            score += self.confidence_weights["has_status"]

        if resource.created_date:
            score += self.confidence_weights["has_creation_date"]

        if resource.vpc_id:
            score += self.confidence_weights["has_vpc_info"]

        if resource.security_groups:
            score += self.confidence_weights["has_security_groups"]

        if resource.account_id:
            score += self.confidence_weights["has_account_id"]

        return min(score / total_weight, 1.0)


class OptimizedAWSDiscovery(IntelligentAWSDiscovery):
    """Optimized discovery system with parallel processing and better service coverage."""

    def __init__(self, session: boto3.Session = None, regions: List[str] = None):
        super().__init__(session, regions)
        self.field_mapper = OptimizedFieldMapper()

        # Services that were missing in intelligent discovery
        self.priority_services = [
            "cloudfront",
            "iam",
            "route53",
            "s3",
            "lambda",
            "ec2",
            "rds",
            "cloudformation",
            "cloudwatch",
        ]

        # Parallel processing settings
        self.max_workers = 4
        self.enable_parallel = True

    def discover_all_services(self) -> List[StandardResource]:
        """Optimized discovery with parallel processing and better service coverage."""

        self.logger.info("Starting optimized AWS discovery with enhanced detection...")

        if self.enable_parallel:
            return self._discover_services_parallel()
        else:
            return self._discover_services_sequential()

    def _discover_services_parallel(self) -> List[StandardResource]:
        """Parallel service discovery for better performance."""

        all_resources = []

        # Process priority services in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit discovery tasks for priority services
            future_to_service = {
                executor.submit(self._discover_service_safe, service): service
                for service in self.priority_services
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_service):
                service = future_to_service[future]
                try:
                    resources = future.result(timeout=30)  # 30 second timeout per service
                    all_resources.extend(resources)
                    self.logger.info(
                        f"Parallel discovery: {service} found {len(resources)} resources"
                    )
                except Exception as e:
                    self.logger.warning(f"Parallel discovery failed for {service}: {e}")

        # Deduplicate and enhance
        all_resources = self._intelligent_deduplication(all_resources)
        self.discovered_resources.extend(all_resources)

        self.logger.info(f"Optimized parallel discovery complete: {len(all_resources)} resources")
        return all_resources

    def _discover_services_sequential(self) -> List[StandardResource]:
        """Sequential discovery with enhanced service coverage."""

        all_resources = []

        for service in self.priority_services:
            try:
                resources = self._discover_service_safe(service)
                all_resources.extend(resources)
                self.logger.info(
                    f"Sequential discovery: {service} found {len(resources)} resources"
                )
            except Exception as e:
                self.logger.warning(f"Sequential discovery failed for {service}: {e}")

        # Deduplicate and enhance
        all_resources = self._intelligent_deduplication(all_resources)
        self.discovered_resources.extend(all_resources)

        self.logger.info(f"Optimized sequential discovery complete: {len(all_resources)} resources")
        return all_resources

    def _discover_service_safe(self, service_name: str) -> List[StandardResource]:
        """Safe service discovery with error handling."""

        try:
            return self.discover_service(service_name)
        except Exception as e:
            self.logger.error(f"Service discovery failed for {service_name}: {e}")
            return []

    def discover_service(self, service_name: str) -> List[StandardResource]:
        """Enhanced service discovery with better operation selection."""

        service_resources = []

        for region in self.regions:
            try:
                # Skip global services for non-primary regions
                if self._is_global_service(service_name) and region != "us-east-1":
                    continue

                # Get service client
                client = self.session.client(service_name, region_name=region)

                # Get enhanced operations for this service
                operations = self._get_enhanced_discovery_operations(service_name, client)

                # Try each discovery operation
                for operation_name in operations:
                    try:
                        resources = self._discover_via_operation(
                            client, operation_name, service_name, region
                        )
                        service_resources.extend(resources)

                        # Limit operations per service to avoid too many API calls
                        if len(service_resources) > 0:
                            break

                    except Exception as e:
                        self.logger.debug(
                            f"Operation {operation_name} failed for {service_name}: {e}"
                        )
                        continue

            except Exception as e:
                self.logger.warning(f"Failed to create {service_name} client in {region}: {e}")

        # Enhanced deduplication for this service
        service_resources = self._intelligent_deduplication(service_resources)

        return service_resources

    def _get_enhanced_discovery_operations(self, service_name: str, client) -> List[str]:
        """Get prioritized discovery operations for a service."""

        # Get all available operations
        all_operations = client._service_model.operation_names

        # Service-specific operation priorities
        service_lower = service_name.lower()
        if service_lower in self.field_mapper.enhanced_service_patterns:
            preferred_ops = self.field_mapper.enhanced_service_patterns[service_lower].get(
                "operations", []
            )
            # Prioritize preferred operations
            operations = [op for op in preferred_ops if op in all_operations]
            if operations:
                return operations

        # Fall back to generic discovery operations
        discovery_ops = [
            op
            for op in all_operations
            if op.startswith(("List", "Describe", "Get"))
            and not any(skip in op for skip in ["Policy", "Version", "Status", "Health", "Metrics"])
        ]

        # Prioritize List operations over Describe operations
        list_ops = [op for op in discovery_ops if op.startswith("List")]
        describe_ops = [op for op in discovery_ops if op.startswith("Describe")]
        get_ops = [op for op in discovery_ops if op.startswith("Get")]

        return list_ops[:2] + describe_ops[:2] + get_ops[:1]  # Limit to avoid too many calls

    def _is_global_service(self, service_name: str) -> bool:
        """Check if a service is global (not region-specific)."""

        global_services = {
            "cloudfront",
            "iam",
            "route53",
            "waf",
            "cloudformation",
            "organizations",
            "support",
            "trustedadvisor",
        }

        return service_name.lower() in global_services

    def _intelligent_deduplication(
        self, resources: List[StandardResource]
    ) -> List[StandardResource]:
        """Enhanced deduplication with better matching logic."""

        if not resources:
            return resources

        # Group by ARN first (most reliable)
        arn_groups = {}
        no_arn_resources = []

        for resource in resources:
            if resource.resource_arn:
                if resource.resource_arn not in arn_groups:
                    arn_groups[resource.resource_arn] = []
                arn_groups[resource.resource_arn].append(resource)
            else:
                no_arn_resources.append(resource)

        # Merge ARN groups (keep highest confidence)
        deduplicated = []
        for arn, group in arn_groups.items():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Merge resources with same ARN, keeping the one with highest confidence
                best_resource = max(group, key=lambda r: r.confidence_score)
                # Merge additional data from other resources
                for other in group:
                    if other != best_resource:
                        if not best_resource.tags and other.tags:
                            best_resource.tags = other.tags
                        if not best_resource.resource_name and other.resource_name:
                            best_resource.resource_name = other.resource_name
                deduplicated.append(best_resource)

        # Handle resources without ARN
        id_groups = {}
        for resource in no_arn_resources:
            key = f"{resource.service_name}:{resource.resource_type}:{resource.resource_id}"
            if key not in id_groups:
                id_groups[key] = []
            id_groups[key].append(resource)

        # Merge ID groups
        for key, group in id_groups.items():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                best_resource = max(group, key=lambda r: r.confidence_score)
                deduplicated.append(best_resource)

        self.logger.info(f"Deduplication: {len(resources)} -> {len(deduplicated)} resources")
        return deduplicated


def test_optimized_discovery():
    """Test the optimized discovery system."""

    print("🚀 Testing Optimized Discovery System")
    print("=" * 50)

    # Test with single region for speed
    optimized_discovery = OptimizedAWSDiscovery(regions=["us-east-1"])

    start_time = datetime.now()
    resources = optimized_discovery.discover_all_services()
    end_time = datetime.now()

    duration = (end_time - start_time).total_seconds()

    print(f"\n✅ Optimized Discovery Results:")
    print(f"  - Total Resources: {len(resources)}")
    print(f"  - Discovery Time: {duration:.2f} seconds")
    print(f"  - Resources/Second: {len(resources)/duration:.2f}")

    # Analyze quality
    high_confidence = [r for r in resources if r.confidence_score >= 0.7]
    medium_confidence = [r for r in resources if 0.4 <= r.confidence_score < 0.7]
    low_confidence = [r for r in resources if r.confidence_score < 0.4]

    print(f"\n📊 Quality Analysis:")
    print(f"  - High Confidence (≥0.7): {len(high_confidence)}")
    print(f"  - Medium Confidence (0.4-0.7): {len(medium_confidence)}")
    print(f"  - Low Confidence (<0.4): {len(low_confidence)}")

    # Show service breakdown
    services = {}
    for resource in resources:
        service = resource.service_name
        if service not in services:
            services[service] = 0
        services[service] += 1

    print(f"\n🔧 Service Breakdown:")
    for service, count in sorted(services.items()):
        print(f"  - {service}: {count} resources")

    # Show sample high-confidence resources
    print(f"\n🌟 Sample High-Confidence Resources:")
    for i, resource in enumerate(high_confidence[:5]):
        print(f"  {i+1}. {resource.service_name} - {resource.resource_type}")
        print(f"     Name: {resource.resource_name or 'N/A'}")
        print(f"     ID: {resource.resource_id}")
        print(f"     Confidence: {resource.confidence_score:.2f}")
        print(f"     Tags: {len(resource.tags)} tags")

    return resources


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Test the optimized system
    test_optimized_discovery()
