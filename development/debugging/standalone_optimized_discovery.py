#!/usr/bin/env python3
"""
Standalone Optimized AWS Resource Discovery System
Complete standalone implementation that addresses all the issues found in debugging.
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


@dataclass
class OptimizedResource:
    """Optimized resource representation with enhanced fields."""

    # Core identification
    service_name: str
    resource_type: str
    resource_id: str
    resource_name: Optional[str] = None
    resource_arn: Optional[str] = None

    # Location and ownership
    account_id: Optional[str] = None
    region: str = "global"
    availability_zone: Optional[str] = None

    # Resource state
    status: Optional[str] = None
    state: Optional[str] = None
    created_date: Optional[str] = None
    last_modified: Optional[str] = None

    # Tagging and organization
    tags: Dict[str, str] = field(default_factory=dict)
    environment: Optional[str] = None
    project: Optional[str] = None
    cost_center: Optional[str] = None

    # Security and networking
    public_access: bool = False
    encrypted: Optional[bool] = None
    vpc_id: Optional[str] = None
    subnet_ids: List[str] = field(default_factory=list)
    security_groups: List[str] = field(default_factory=list)

    # Discovery metadata
    discovered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    discovery_method: str = "OptimizedDiscovery"
    api_operation: Optional[str] = None
    confidence_score: float = 1.0
    raw_data: Dict[str, Any] = field(default_factory=dict)


class OptimizedFieldMapper:
    """Optimized field mapper with service-specific intelligence."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Service-specific extraction patterns
        self.service_patterns = {
            "cloudfront": {
                "name_fields": ["DomainName", "Id"],
                "type_indicators": ["Distribution"],
                "operations": ["ListDistributions"],
                "id_patterns": [r"E[A-Z0-9]+"],
                "global_service": True,
            },
            "iam": {
                "name_fields": ["RoleName", "UserName", "PolicyName", "GroupName"],
                "type_indicators": ["Role", "User", "Policy", "Group"],
                "operations": ["ListRoles", "ListUsers", "ListPolicies", "ListGroups"],
                "global_service": True,
            },
            "route53": {
                "name_fields": ["Name", "Id"],
                "type_indicators": ["HostedZone"],
                "operations": ["ListHostedZones"],
                "id_patterns": [r"Z[0-9A-Z]+"],
                "global_service": True,
            },
            "s3": {
                "name_fields": ["Name"],
                "type_indicators": ["Bucket"],
                "operations": ["ListBuckets"],
                "global_service": True,
            },
            "lambda": {
                "name_fields": ["FunctionName"],
                "type_indicators": ["Function"],
                "operations": ["ListFunctions"],
                "global_service": False,
            },
            "ec2": {
                "name_fields": ["InstanceId", "VpcId", "SubnetId", "GroupId"],
                "type_indicators": ["Instance", "VPC", "Subnet", "SecurityGroup"],
                "operations": ["DescribeInstances", "DescribeVpcs", "DescribeSubnets"],
                "global_service": False,
            },
            "rds": {
                "name_fields": ["DBInstanceIdentifier", "DBClusterIdentifier"],
                "type_indicators": ["DBInstance", "DBCluster"],
                "operations": ["DescribeDBInstances", "DescribeDBClusters"],
                "global_service": False,
            },
        }

    def map_resource(
        self,
        raw_data: Dict[str, Any],
        service_name: str,
        operation_name: str,
        region: str,
        account_id: str = None,
    ) -> OptimizedResource:
        """Map raw AWS API response to optimized resource."""

        try:
            service_key = service_name.lower()

            # Extract core fields
            resource_id = self._extract_resource_id(raw_data, service_key)
            resource_name = self._extract_resource_name(raw_data, service_key)
            resource_type = self._extract_resource_type(raw_data, operation_name, service_key)

            # Create optimized resource
            resource = OptimizedResource(
                service_name=service_name.upper(),
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                region=region,
                account_id=account_id or self._extract_account_id(raw_data),
                api_operation=operation_name,
                raw_data=raw_data,
            )

            # Extract additional fields
            resource.resource_arn = self._extract_arn(raw_data)
            resource.status = self._extract_status(raw_data)
            resource.created_date = self._extract_creation_date(raw_data)
            resource.tags = self._extract_tags(raw_data)

            # Extract derived fields from tags
            if resource.tags:
                resource.environment = (
                    resource.tags.get("Environment")
                    or resource.tags.get("Env")
                    or resource.tags.get("Stage")
                )
                resource.project = (
                    resource.tags.get("Project")
                    or resource.tags.get("ProjectName")
                    or resource.tags.get("Application")
                )
                resource.cost_center = resource.tags.get("CostCenter") or resource.tags.get(
                    "BillingCode"
                )

            # Extract security and network info
            resource.vpc_id = self._extract_vpc_id(raw_data)
            resource.subnet_ids = self._extract_subnet_ids(raw_data)
            resource.security_groups = self._extract_security_groups(raw_data)
            resource.public_access = self._determine_public_access(raw_data, service_key)
            resource.encrypted = self._determine_encryption(raw_data)

            # Calculate confidence score
            resource.confidence_score = self._calculate_confidence(resource)

            return resource

        except Exception as e:
            self.logger.error(f"Failed to map resource from {service_name}: {e}")
            return self._create_fallback_resource(raw_data, service_name, region)

    def _extract_resource_id(self, data: Dict[str, Any], service_key: str) -> str:
        """Extract resource ID using service-specific patterns."""

        if service_key in self.service_patterns:
            # Try service-specific name fields
            for field in self.service_patterns[service_key]["name_fields"]:
                if field in data and data[field]:
                    return str(data[field])

        # Generic fallback
        for field in ["Id", "Name", "Identifier", "ResourceId"]:
            if field in data and data[field]:
                return str(data[field])

        return "unknown"

    def _extract_resource_name(self, data: Dict[str, Any], service_key: str) -> Optional[str]:
        """Extract resource name using service-specific patterns."""

        if service_key in self.service_patterns:
            # Try service-specific name fields
            for field in self.service_patterns[service_key]["name_fields"]:
                if field in data and data[field]:
                    return str(data[field])

        # CloudFront specific logic
        if service_key == "cloudfront":
            if "DomainName" in data:
                return data["DomainName"]
            if "Aliases" in data and data["Aliases"].get("Items"):
                return data["Aliases"]["Items"][0]

        # Generic fallback
        for field in ["Name", "ResourceName", "DisplayName"]:
            if field in data and data[field]:
                return str(data[field])

        # Extract from tags
        tags = self._extract_tags(data)
        if "Name" in tags:
            return tags["Name"]

        return None

    def _extract_resource_type(
        self, data: Dict[str, Any], operation_name: str, service_key: str
    ) -> str:
        """Extract resource type using service-specific patterns."""

        if service_key in self.service_patterns:
            # Match operation to resource type
            for type_indicator in self.service_patterns[service_key]["type_indicators"]:
                if type_indicator.lower() in operation_name.lower():
                    return type_indicator

        # Extract from operation name
        if operation_name.startswith("List"):
            return operation_name[4:].rstrip("s")
        elif operation_name.startswith("Describe"):
            return operation_name[8:].rstrip("s")
        elif operation_name.startswith("Get"):
            return operation_name[3:].rstrip("s")

        return "Resource"

    def _extract_arn(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract ARN from resource data."""

        arn_fields = ["Arn", "ARN", "ResourceArn", "TopicArn", "RoleArn"]
        for field in arn_fields:
            if field in data and data[field]:
                arn = str(data[field])
                if arn.startswith("arn:aws:"):
                    return arn
        return None

    def _extract_status(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract status information."""

        status_fields = ["Status", "State", "LifecycleState"]
        for field in status_fields:
            if field in data:
                value = data[field]
                if isinstance(value, str):
                    return value
                elif isinstance(value, dict) and "Name" in value:
                    return value["Name"]
        return None

    def _extract_creation_date(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract creation date."""

        date_fields = ["CreatedDate", "CreationDate", "LaunchTime", "CreateTime"]
        for field in date_fields:
            if field in data and data[field]:
                return str(data[field])
        return None

    def _extract_tags(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Extract tags from various AWS tag formats."""

        tags = {}

        # Try different tag field names
        tag_fields = ["Tags", "TagList", "TagSet", "ResourceTags"]
        for tag_field in tag_fields:
            if tag_field in data:
                tag_data = data[tag_field]
                if isinstance(tag_data, list):
                    # List format: [{"Key": "Name", "Value": "MyResource"}]
                    for tag in tag_data:
                        if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                            tags[tag["Key"]] = tag["Value"]
                elif isinstance(tag_data, dict):
                    # Direct dict format: {"Name": "MyResource"}
                    tags.update(tag_data)

        return tags

    def _extract_account_id(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract AWS account ID."""

        # Try to extract from ARN
        arn = self._extract_arn(data)
        if arn:
            try:
                return arn.split(":")[4]
            except:
                pass

        # Direct account fields
        account_fields = ["AccountId", "Account", "OwnerId"]
        for field in account_fields:
            if field in data and data[field]:
                return str(data[field])

        return None

    def _extract_vpc_id(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract VPC ID."""

        vpc_fields = ["VpcId", "VpcConfig"]
        for field in vpc_fields:
            if field in data:
                vpc_data = data[field]
                if isinstance(vpc_data, str):
                    return vpc_data
                elif isinstance(vpc_data, dict) and "VpcId" in vpc_data:
                    return vpc_data["VpcId"]
        return None

    def _extract_subnet_ids(self, data: Dict[str, Any]) -> List[str]:
        """Extract subnet IDs."""

        subnets = []
        subnet_fields = ["SubnetId", "SubnetIds", "Subnets"]
        for field in subnet_fields:
            if field in data:
                subnet_data = data[field]
                if isinstance(subnet_data, str):
                    subnets.append(subnet_data)
                elif isinstance(subnet_data, list):
                    subnets.extend([str(s) for s in subnet_data if s])
        return subnets

    def _extract_security_groups(self, data: Dict[str, Any]) -> List[str]:
        """Extract security group IDs."""

        sgs = []
        sg_fields = ["SecurityGroups", "SecurityGroupIds"]
        for field in sg_fields:
            if field in data:
                sg_data = data[field]
                if isinstance(sg_data, list):
                    for sg in sg_data:
                        if isinstance(sg, dict):
                            sgs.append(sg.get("GroupId") or sg.get("GroupName") or str(sg))
                        else:
                            sgs.append(str(sg))
                elif isinstance(sg_data, str):
                    sgs.append(sg_data)
        return sgs

    def _determine_public_access(self, data: Dict[str, Any], service_key: str) -> bool:
        """Determine if resource has public access."""

        # Service-specific public access detection
        if service_key == "s3":
            if "PublicAccessBlock" in data:
                pab = data["PublicAccessBlock"]
                return not all(
                    [
                        pab.get("BlockPublicAcls", True),
                        pab.get("IgnorePublicAcls", True),
                        pab.get("BlockPublicPolicy", True),
                        pab.get("RestrictPublicBuckets", True),
                    ]
                )

        # General indicators
        public_indicators = ["PublicIpAddress", "PublicDnsName", "PubliclyAccessible"]
        for indicator in public_indicators:
            if indicator in data and data[indicator]:
                return True

        return False

    def _determine_encryption(self, data: Dict[str, Any]) -> Optional[bool]:
        """Determine if resource is encrypted."""

        encryption_fields = [
            "Encrypted",
            "EncryptionAtRest",
            "ServerSideEncryption",
            "KmsKeyId",
        ]
        for field in encryption_fields:
            if field in data:
                value = data[field]
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str) and value.lower() in [
                    "true",
                    "enabled",
                    "aes256",
                ]:
                    return True
                elif isinstance(value, dict) and value.get("Enabled"):
                    return True
        return None

    def _calculate_confidence(self, resource: OptimizedResource) -> float:
        """Calculate confidence score based on data completeness."""

        score = 0.0

        # Core fields (high weight)
        if resource.resource_id and resource.resource_id != "unknown":
            score += 0.3
        if resource.resource_name:
            score += 0.25
        if resource.resource_type and resource.resource_type != "Resource":
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
    ) -> OptimizedResource:
        """Create fallback resource when mapping fails."""

        return OptimizedResource(
            service_name=service_name.upper(),
            resource_type="Resource",
            resource_id=str(raw_data.get("Id", raw_data.get("Name", "unknown"))),
            region=region,
            confidence_score=0.2,
            raw_data=raw_data,
        )


class OptimizedAWSDiscovery:
    """Optimized AWS discovery system with enhanced service coverage."""

    def __init__(self, session: boto3.Session = None, regions: List[str] = None):
        self.session = session or boto3.Session()
        self.regions = regions or self._get_available_regions()
        self.field_mapper = OptimizedFieldMapper()
        self.logger = logging.getLogger(__name__)
        self.discovered_resources: List[OptimizedResource] = []

        # Priority services that had issues in the original system
        self.priority_services = [
            "cloudfront",  # Missing distributions
            "iam",  # Missing roles/users
            "route53",  # Missing hosted zones
            "s3",  # Detection issues
            "lambda",  # Detection issues
            "ec2",  # Core service
            "rds",  # Database service
            "cloudwatch",  # Monitoring
        ]

        # Performance settings
        self.max_workers = 3
        self.enable_parallel = True
        self.operation_timeout = 20

    def discover_all_services(self) -> List[OptimizedResource]:
        """Discover resources from all priority services."""

        self.logger.info("Starting optimized AWS discovery...")

        if self.enable_parallel:
            return self._discover_parallel()
        else:
            return self._discover_sequential()

    def _discover_parallel(self) -> List[OptimizedResource]:
        """Parallel discovery for better performance."""

        all_resources = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit discovery tasks
            future_to_service = {
                executor.submit(self._safe_discover_service, service): service
                for service in self.priority_services
            }

            # Collect results
            for future in concurrent.futures.as_completed(future_to_service, timeout=120):
                service = future_to_service[future]
                try:
                    resources = future.result(timeout=self.operation_timeout)
                    all_resources.extend(resources)
                    self.logger.info(f"Parallel discovery: {service} -> {len(resources)} resources")
                except Exception as e:
                    self.logger.warning(f"Parallel discovery failed for {service}: {e}")

        # Deduplicate
        all_resources = self._deduplicate_resources(all_resources)
        self.discovered_resources.extend(all_resources)

        self.logger.info(f"Optimized parallel discovery complete: {len(all_resources)} resources")
        return all_resources

    def _discover_sequential(self) -> List[OptimizedResource]:
        """Sequential discovery as fallback."""

        all_resources = []

        for service in self.priority_services:
            try:
                resources = self._safe_discover_service(service)
                all_resources.extend(resources)
                self.logger.info(f"Sequential discovery: {service} -> {len(resources)} resources")
            except Exception as e:
                self.logger.warning(f"Sequential discovery failed for {service}: {e}")

        all_resources = self._deduplicate_resources(all_resources)
        self.discovered_resources.extend(all_resources)

        return all_resources

    def _safe_discover_service(self, service_name: str) -> List[OptimizedResource]:
        """Safely discover a service with error handling."""

        try:
            return self.discover_service(service_name)
        except Exception as e:
            self.logger.error(f"Service discovery failed for {service_name}: {e}")
            return []

    def discover_service(self, service_name: str) -> List[OptimizedResource]:
        """Discover resources from a specific service."""

        service_resources = []

        for region in self.regions:
            try:
                # Skip global services for non-primary regions
                if self._is_global_service(service_name) and region != "us-east-1":
                    continue

                client = self.session.client(service_name, region_name=region)
                operations = self._get_discovery_operations(service_name, client)

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

        return self._deduplicate_resources(service_resources)

    def _get_discovery_operations(self, service_name: str, client) -> List[str]:
        """Get optimized discovery operations for a service."""

        all_operations = client._service_model.operation_names
        service_key = service_name.lower()

        # Use service-specific operations if available
        if service_key in self.field_mapper.service_patterns:
            preferred_ops = self.field_mapper.service_patterns[service_key]["operations"]
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

    def _discover_via_operation(
        self, client, operation_name: str, service_name: str, region: str
    ) -> List[OptimizedResource]:
        """Discover resources via a specific API operation."""

        resources = []

        try:
            # Get the operation
            operation = getattr(client, self._snake_case(operation_name))

            # Call the operation
            response = operation()

            # Extract resources from response
            resources = self._extract_resources_from_response(
                response, service_name, operation_name, region
            )

        except Exception as e:
            self.logger.debug(f"Operation {operation_name} failed: {e}")

        return resources

    def _extract_resources_from_response(
        self,
        response: Dict[str, Any],
        service_name: str,
        operation_name: str,
        region: str,
    ) -> List[OptimizedResource]:
        """Extract resources from API response."""

        resources = []

        # Find the resource list in the response
        resource_lists = self._find_resource_lists(response)

        for resource_list in resource_lists:
            for item in resource_list:
                if isinstance(item, dict):
                    try:
                        resource = self.field_mapper.map_resource(
                            item, service_name, operation_name, region
                        )
                        resources.append(resource)
                    except Exception as e:
                        self.logger.debug(f"Failed to map resource: {e}")

        return resources

    def _find_resource_lists(self, response: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
        """Find resource lists in API response."""

        resource_lists = []

        for key, value in response.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                # Skip metadata lists
                if key not in ["ResponseMetadata", "Errors"]:
                    resource_lists.append(value)

        return resource_lists

    def _is_global_service(self, service_name: str) -> bool:
        """Check if service is global."""

        service_key = service_name.lower()
        if service_key in self.field_mapper.service_patterns:
            return self.field_mapper.service_patterns[service_key].get("global_service", False)

        # Default global services
        global_services = {"cloudfront", "iam", "route53", "waf"}
        return service_key in global_services

    def _deduplicate_resources(self, resources: List[OptimizedResource]) -> List[OptimizedResource]:
        """Remove duplicate resources."""

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

        # Keep best resource from each ARN group
        deduplicated = []
        for arn, group in arn_groups.items():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Keep the one with highest confidence
                best_resource = max(group, key=lambda r: r.confidence_score)
                deduplicated.append(best_resource)

        # Handle resources without ARN
        id_groups = {}
        for resource in no_arn_resources:
            key = f"{resource.service_name}:{resource.resource_type}:{resource.resource_id}"
            if key not in id_groups:
                id_groups[key] = []
            id_groups[key].append(resource)

        for key, group in id_groups.items():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                best_resource = max(group, key=lambda r: r.confidence_score)
                deduplicated.append(best_resource)

        self.logger.info(f"Deduplication: {len(resources)} -> {len(deduplicated)} resources")
        return deduplicated

    def _get_available_regions(self) -> List[str]:
        """Get available AWS regions."""

        try:
            ec2 = self.session.client("ec2", region_name="us-east-1")
            regions = ec2.describe_regions()["Regions"]
            return [region["RegionName"] for region in regions]
        except Exception as e:
            self.logger.warning(f"Failed to get regions: {e}")
            return ["us-east-1", "us-west-2"]  # Fallback

    def _snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def test_optimized_discovery():
    """Test the optimized discovery system."""

    print("🧪 Testing Standalone Optimized Discovery System")
    print("=" * 60)

    # Initialize discovery
    discovery = OptimizedAWSDiscovery(regions=["us-east-1"])

    print(f"\n🔍 Starting discovery...")
    start_time = datetime.now()
    resources = discovery.discover_all_services()
    end_time = datetime.now()

    duration = (end_time - start_time).total_seconds()

    print(f"\n✅ Discovery Complete!")
    print(f"  - Total Resources: {len(resources)}")
    print(f"  - Discovery Time: {duration:.2f} seconds")
    print(f"  - Resources/Second: {len(resources)/duration:.2f}")

    # Service breakdown
    services = {}
    for resource in resources:
        service = resource.service_name
        services[service] = services.get(service, 0) + 1

    print(f"\n📊 Service Coverage ({len(services)} services):")
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
    print(f"\n🌟 Sample Resources:")
    for i, resource in enumerate(resources[:5]):
        print(f"  {i+1}. {resource.service_name} - {resource.resource_type}")
        print(f"     Name: {resource.resource_name or 'N/A'}")
        print(f"     ID: {resource.resource_id}")
        print(f"     Region: {resource.region}")
        print(f"     Confidence: {resource.confidence_score:.2f}")
        print(f"     Tags: {len(resource.tags)} tags")
        print()

    # Show services that were problematic before
    problematic_services = ["CLOUDFRONT", "IAM", "ROUTE53", "S3", "LAMBDA"]
    found_problematic = [s for s in services.keys() if s in problematic_services]

    print(f"🔧 Previously Problematic Services Found:")
    for service in found_problematic:
        print(f"  ✅ {service}: {services[service]} resources")

    missing_problematic = [s for s in problematic_services if s not in services]
    if missing_problematic:
        print(f"\n❌ Still Missing Services:")
        for service in missing_problematic:
            print(f"  - {service}")

    return resources


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Test the system
    test_optimized_discovery()
