#!/usr/bin/env python3
"""
Comprehensive AWS Resource Discovery System

This module implements a comprehensive discovery strategy that ensures ALL resources
are discovered, regardless of whether they are tagged or not.

Discovery Strategy:
1. Service-specific API discovery for ALL resources (primary)
2. ResourceGroupsTagging API for tag enrichment (secondary)
3. Billing validation for service confirmation (validation)

This ensures resources like VPCs, subnets, security groups, etc. are always discovered.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError


class ComprehensiveAWSDiscovery:
    """
    Comprehensive AWS resource discovery that finds ALL resources regardless of tags.

    Uses service-specific APIs as primary discovery method, then enriches with tags
    and validates against billing data.
    """

    def __init__(
        self,
        session: boto3.Session = None,
        regions: List[str] = None,
        hide_fallback_resources: bool = False,  # Legacy, deprecated
        fallback_display_mode: str = "auto",  # "auto", "always", "never"
    ):
        self.session = session or boto3.Session()
        self.logger = logging.getLogger(__name__)
        self.logger.propagate = False  # Prevent duplicate logging
        self.regions = regions or ["us-east-1"]

        # Handle legacy parameter
        if hide_fallback_resources and fallback_display_mode == "auto":
            fallback_display_mode = "never"

        self.fallback_display_mode = fallback_display_mode
        self.hide_fallback_resources = (
            hide_fallback_resources  # Keep for backward compatibility
        )

        if self.fallback_display_mode == "never":
            self.logger.info(
                "💡 Fallback resources from ResourceGroupsTagging API will be hidden"
            )
        elif self.fallback_display_mode == "always":
            self.logger.info(
                "💡 All fallback resources from ResourceGroupsTagging API will be "
                "shown (maximum visibility mode)"
            )
        else:  # auto mode
            self.logger.info(
                "💡 Smart fallback mode: fallback resources shown only when no "
                "primary resources found for a service (recommended for debugging)"
            )

        # Resource storage
        self.resources = []
        self.discovered_services = set()

        # Track services with primary discoveries for smart fallback logic
        self.services_with_primary_resources = set()

        # Billing data for validation
        self.billing_services = set()
        self.billing_spend = {}

        # Comprehensive service discovery patterns
        self.service_discovery_patterns = {
            # VPC & Network Infrastructure (separate from EC2)
            "vpc": {
                "operations": [
                    ("describe_vpcs", "Vpcs", "VPC"),
                    ("describe_subnets", "Subnets", "Subnet"),
                    ("describe_security_groups", "SecurityGroups", "SecurityGroup"),
                    (
                        "describe_internet_gateways",
                        "InternetGateways",
                        "InternetGateway",
                    ),
                    ("describe_nat_gateways", "NatGateways", "NatGateway"),
                    ("describe_route_tables", "RouteTables", "RouteTable"),
                    ("describe_network_acls", "NetworkAcls", "NetworkAcl"),
                    ("describe_addresses", "Addresses", "ElasticIP"),
                ],
                "regional": True,
                "critical": True,  # Always discover these
                "client_service": "ec2",  # Use EC2 client for VPC operations
            },
            # EC2 Compute Services (separate from VPC)
            "ec2": {
                "operations": [
                    ("describe_instances", "Reservations", "Instance"),
                    ("describe_volumes", "Volumes", "Volume"),
                    (
                        "describe_snapshots",
                        "Snapshots",
                        "Snapshot",
                        {"OwnerIds": ["self"]},
                    ),
                    ("describe_key_pairs", "KeyPairs", "KeyPair"),
                ],
                "regional": True,
                "critical": True,
            },
            # Storage Services
            "s3": {
                "operations": [
                    ("list_buckets", "Buckets", "Bucket"),
                ],
                "regional": False,  # Global service
                "critical": True,
                "post_process": "enhance_s3_buckets",  # Get bucket regions/details using boto3 API
            },
            # Database Services
            "rds": {
                "operations": [
                    ("describe_db_instances", "DBInstances", "DBInstance"),
                    ("describe_db_clusters", "DBClusters", "DBCluster"),
                    (
                        "describe_db_snapshots",
                        "DBSnapshots",
                        "DBSnapshot",
                        {"SnapshotType": "manual"},
                    ),
                    ("describe_db_subnet_groups", "DBSubnetGroups", "DBSubnetGroup"),
                    (
                        "describe_db_parameter_groups",
                        "DBParameterGroups",
                        "DBParameterGroup",
                    ),
                ],
                "regional": True,
                "critical": True,
            },
            # Compute Services
            "lambda": {
                "operations": [
                    ("list_functions", "Functions", "Function"),
                    ("list_layers", "Layers", "Layer"),
                ],
                "regional": True,
                "critical": True,
            },
            # Application Services (Classic ELB)
            "elb": {
                "operations": [
                    (
                        "describe_load_balancers",
                        "LoadBalancerDescriptions",
                        "LoadBalancer",
                    ),
                ],
                "regional": True,
                "critical": True,
            },
            "elbv2": {
                "operations": [
                    ("describe_load_balancers", "LoadBalancers", "LoadBalancerV2"),
                    ("describe_target_groups", "TargetGroups", "TargetGroup"),
                ],
                "regional": True,
                "critical": True,
            },
            # Identity & Security (Global)
            "iam": {
                "operations": [
                    ("list_users", "Users", "User"),
                    ("list_roles", "Roles", "Role"),
                    ("list_policies", "Policies", "Policy", {"Scope": "Local"}),
                    ("list_groups", "Groups", "Group"),
                    ("list_instance_profiles", "InstanceProfiles", "InstanceProfile"),
                ],
                "regional": False,  # Global service
                "critical": True,
            },
            # CDN & DNS (Global)
            "cloudfront": {
                "operations": [
                    ("list_distributions", "DistributionList.Items", "Distribution"),
                ],
                "regional": False,
                "critical": True,
            },
            "route53": {
                "operations": [
                    ("list_hosted_zones", "HostedZones", "HostedZone"),
                ],
                "regional": False,
                "critical": True,
            },
            # Security Services
            "kms": {
                "operations": [
                    ("list_keys", "Keys", "Key"),
                    ("list_aliases", "Aliases", "Alias"),
                ],
                "regional": True,
                "critical": False,
                "graceful_degradation": True,  # Handle access denied gracefully
            },
            # Monitoring
            "cloudwatch": {
                "operations": [
                    ("describe_alarms", "MetricAlarms", "Alarm"),
                    ("list_dashboards", "DashboardEntries", "Dashboard"),
                ],
                "regional": True,
                "critical": False,
            },
            # Container Services
            "ecs": {
                "operations": [
                    ("list_clusters", "clusterArns", "Cluster"),
                    ("list_services", "serviceArns", "Service"),
                ],
                "regional": True,
                "critical": False,
            },
            "eks": {
                "operations": [
                    ("list_clusters", "clusters", "Cluster"),
                ],
                "regional": True,
                "critical": False,
            },
            # Message Queuing
            "sns": {
                "operations": [
                    ("list_topics", "Topics", "Topic"),
                ],
                "regional": True,
                "critical": False,
            },
            "sqs": {
                "operations": [
                    ("list_queues", "QueueUrls", "Queue"),
                ],
                "regional": True,
                "critical": False,
            },
            # NoSQL Database
            "dynamodb": {
                "operations": [
                    ("list_tables", "TableNames", "Table"),
                ],
                "regional": True,
                "critical": False,
            },
            # API Gateway
            "apigateway": {
                "operations": [
                    ("get_rest_apis", "items", "RestApi"),
                ],
                "regional": True,
                "critical": False,
            },
            # AWS Glue
            "glue": {
                "operations": [
                    ("get_databases", "DatabaseList", "Database"),
                    ("get_jobs", "Jobs", "Job"),
                    ("get_crawlers", "CrawlerList", "Crawler"),
                    ("get_triggers", "Triggers", "Trigger"),
                ],
                "regional": True,
                "critical": False,
                "graceful_degradation": True,
            },
            # Amazon WorkMail
            "workmail": {
                "operations": [
                    ("list_organizations", "Organizations", "Organization"),
                ],
                "regional": True,
                "critical": False,
                "graceful_degradation": True,  # WorkMail requires specific permissions
            },
            # CloudFormation
            "cloudformation": {
                "operations": [
                    ("describe_stacks", "Stacks", "Stack"),
                    ("list_stack_sets", "Summaries", "StackSet"),
                ],
                "regional": True,
                "critical": False,
            },
            # AWS Certificate Manager
            "acm": {
                "operations": [
                    ("list_certificates", "CertificateSummaryList", "Certificate"),
                ],
                "regional": True,
                "critical": False,
                "graceful_degradation": True,
            },
            # AWS CloudTrail
            "cloudtrail": {
                "operations": [
                    ("describe_trails", "trailList", "Trail"),
                ],
                "regional": True,
                "critical": False,
                "graceful_degradation": True,
            },
            # CloudWatch Events (EventBridge)
            "events": {
                "operations": [
                    ("list_rules", "Rules", "Rule"),
                    ("list_event_buses", "EventBuses", "EventBus"),
                ],
                "regional": True,
                "critical": False,
                "graceful_degradation": True,
            },
        }

        # Global services that should only be called from us-east-1
        self.global_services = {"s3", "iam", "cloudfront", "route53"}

    def discover_all_resources(self, max_workers: int = 15) -> List[Dict[str, Any]]:
        """
        Comprehensive discovery of ALL AWS resources regardless of tags.

        Returns:
            List of discovered resources with complete metadata
        """
        self.logger.info("🔍 Starting comprehensive AWS resource discovery")
        self.logger.info(
            "Strategy: Service-specific APIs → Tag enrichment → Billing validation"
        )

        start_time = time.time()

        # Step 1: Discover billing services for validation
        self._discover_billing_services()

        # Step 2: Comprehensive service-specific discovery (PRIMARY)
        self._discover_all_service_resources(max_workers)

        # Step 3: Enrich with ResourceGroupsTagging API (SECONDARY)
        self._enrich_with_tagging_api()

        # Step 4: Validate against billing data
        self._validate_with_billing()

        # Step 5: Post-process and enhance (including S3 bucket regions)
        self._post_process_resources()

        execution_time = time.time() - start_time

        self.logger.info(
            f"✅ Comprehensive discovery complete: {len(self.resources)} resources "
            f"from {len(self.discovered_services)} services in {execution_time:.1f}s"
        )

        return self.resources

    def _discover_billing_services(self):
        """Discover services with billing usage for validation."""
        try:
            ce_client = self.session.client("ce", region_name="us-east-1")

            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    "Start": (
                        datetime.now().replace(day=1) - timedelta(days=30)
                    ).strftime("%Y-%m-%d"),
                    "End": datetime.now().strftime("%Y-%m-%d"),
                },
                Granularity="MONTHLY",
                Metrics=["BlendedCost", "UsageQuantity"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )

            for result in response.get("ResultsByTime", []):
                for group in result.get("Groups", []):
                    service_name = group.get("Keys", [""])[0]
                    cost = float(
                        group.get("Metrics", {})
                        .get("BlendedCost", {})
                        .get("Amount", "0")
                    )
                    usage = float(
                        group.get("Metrics", {})
                        .get("UsageQuantity", {})
                        .get("Amount", "0")
                    )

                    if cost > 0 or usage > 0:
                        normalized_service = self._normalize_billing_service_name(
                            service_name
                        )
                        self.billing_services.add(normalized_service)
                        self.billing_spend[normalized_service] = cost

            self.logger.info(
                f"💰 Found {len(self.billing_services)} services with billing usage"
            )

        except Exception as e:
            self.logger.warning(f"Billing discovery failed: {e}")

    def _discover_all_service_resources(self, max_workers: int):
        """Discover ALL resources using service-specific APIs (PRIMARY METHOD)."""
        self.logger.info("🚀 Starting comprehensive service-specific discovery")

        # Prepare discovery tasks
        discovery_tasks = []

        for service_name, config in self.service_discovery_patterns.items():
            if config.get("regional", True):
                # Regional service - discover in all regions
                for region in self.regions:
                    discovery_tasks.append(
                        {
                            "service": service_name,
                            "region": region,
                            "config": config,
                            "priority": 1 if config.get("critical", False) else 2,
                        }
                    )
            else:
                # Global service - discover from us-east-1 only
                if "us-east-1" in self.regions:
                    discovery_tasks.append(
                        {
                            "service": service_name,
                            "region": "us-east-1",
                            "config": config,
                            "priority": 1 if config.get("critical", False) else 2,
                        }
                    )

        # Sort by priority (critical services first)
        discovery_tasks.sort(key=lambda x: x["priority"])

        self.logger.info(
            f"🔍 Executing {len(discovery_tasks)} discovery tasks with {max_workers} workers"
        )

        # Execute parallel discovery
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {}

            for task in discovery_tasks:
                future = executor.submit(self._discover_service_in_region, task)
                future_to_task[future] = task

            # Collect results
            completed = 0
            for future in as_completed(future_to_task, timeout=600):
                task = future_to_task[future]
                try:
                    resources_found = future.result()
                    if resources_found > 0:
                        self.discovered_services.add(task["service"])
                        self.logger.debug(
                            f"✅ {task['service']} in {task['region']}: {resources_found} resources"
                        )
                    completed += 1

                    if completed % 10 == 0:  # Progress logging
                        self.logger.info(
                            f"   Progress: {completed}/{len(discovery_tasks)} tasks completed"
                        )

                except Exception as e:
                    self.logger.warning(
                        f"❌ {task['service']} in {task['region']} failed: {e}"
                    )

    def _discover_service_in_region(self, task: Dict[str, Any]) -> int:
        """Discover resources for a specific service in a specific region."""
        service_name = task["service"]
        region = task["region"]
        config = task["config"]
        resources_found = 0

        try:
            # Create service client (handle special cases like VPC using EC2 client)
            client_service = config.get("client_service", service_name)
            client = self.session.client(client_service, region_name=region)

            # Execute all operations for this service
            for operation_config in config["operations"]:
                try:
                    resources_found += self._execute_discovery_operation(
                        client, service_name, region, operation_config
                    )
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code in ["AccessDenied", "UnauthorizedOperation"]:
                        # Handle access denied gracefully for services that support it
                        if config.get("graceful_degradation", False):
                            self.logger.debug(
                                f"Access denied for {service_name} operation - continuing with limited permissions"
                            )
                        continue
                    else:
                        self.logger.debug(f"Operation failed for {service_name}: {e}")
                        continue
                except Exception as e:
                    self.logger.debug(f"Operation error for {service_name}: {e}")
                    continue

        except Exception as e:
            self.logger.warning(
                f"Service client creation failed for {service_name}: {e}"
            )

        return resources_found

    def _execute_discovery_operation(
        self, client, service_name: str, region: str, operation_config: Tuple
    ) -> int:
        """Execute a single discovery operation and extract resources."""
        operation_name, response_key, resource_type = operation_config[:3]
        operation_params = operation_config[3] if len(operation_config) > 3 else {}

        try:
            # Get the operation method
            operation = getattr(client, operation_name)

            # Execute with pagination if available
            resources_found = 0

            if hasattr(client, "get_paginator"):
                try:
                    paginator = client.get_paginator(operation_name)
                    pages = paginator.paginate(**operation_params)

                    for page in pages:
                        resources_found += self._extract_resources_from_response(
                            page,
                            response_key,
                            service_name,
                            region,
                            resource_type,
                            operation_name,
                        )

                except Exception:
                    # Fallback to direct call if pagination fails
                    response = operation(**operation_params)
                    resources_found += self._extract_resources_from_response(
                        response,
                        response_key,
                        service_name,
                        region,
                        resource_type,
                        operation_name,
                    )
            else:
                # Direct operation call
                response = operation(**operation_params)
                resources_found += self._extract_resources_from_response(
                    response,
                    response_key,
                    service_name,
                    region,
                    resource_type,
                    operation_name,
                )

            return resources_found

        except Exception:
            # Operation-level errors are expected and handled gracefully
            return 0

    def _extract_resources_from_response(
        self,
        response: Dict,
        response_key: str,
        service_name: str,
        region: str,
        resource_type: str,
        operation_name: str,
    ) -> int:
        """Extract resources from AWS API response."""
        try:
            # Handle nested response keys (like 'DistributionList.Items')
            data = response
            for key in response_key.split("."):
                data = data.get(key, [])

            if not isinstance(data, list):
                data = [data] if data else []

            resources_added = 0
            for item in data:
                if isinstance(item, dict):
                    resource = self._normalize_resource(
                        item, service_name, region, resource_type, operation_name
                    )
                    if resource:
                        # Handle EC2 reservations specially
                        if resource_type == "Instance" and "Instances" in item:
                            for instance in item["Instances"]:
                                instance_resource = self._normalize_resource(
                                    instance,
                                    service_name,
                                    region,
                                    resource_type,
                                    operation_name,
                                )
                                if instance_resource:
                                    self.resources.append(instance_resource)
                                    resources_added += 1
                                    # Track service with primary resources for smart fallback logic
                                    self.services_with_primary_resources.add(
                                        service_name
                                    )
                        else:
                            self.resources.append(resource)
                            resources_added += 1
                            # Track service with primary resources for smart fallback logic
                            self.services_with_primary_resources.add(service_name)
                elif isinstance(item, str):
                    # Handle string responses (like SQS queue URLs)
                    resource = self._create_string_resource(
                        item, service_name, region, resource_type, operation_name
                    )
                    if resource:
                        self.resources.append(resource)
                        resources_added += 1
                        # Track service with primary resources for smart fallback logic
                        self.services_with_primary_resources.add(service_name)

            return resources_added

        except Exception as e:
            self.logger.debug(f"Resource extraction failed for {service_name}: {e}")
            return 0

    def _normalize_resource(
        self,
        raw_data: Dict,
        service_name: str,
        region: str,
        resource_type: str,
        operation_name: str,
    ) -> Optional[Dict]:
        """Normalize a resource into standard format."""
        try:
            # Extract resource identifier
            resource_id = self._extract_resource_id(raw_data, resource_type)
            if not resource_id:
                return None

            # Extract resource name
            resource_name = self._extract_resource_name(raw_data)

            # Extract ARN if available
            arn = raw_data.get("Arn") or raw_data.get("ARN")
            if not arn:
                arn = self._construct_arn(
                    service_name, region, resource_type, resource_id
                )

            # Extract tags
            tags = self._extract_tags(raw_data)

            # Reclassify VPC-related resources from EC2 to VPC service
            actual_service = self._determine_actual_service(
                service_name, resource_type, resource_id, arn
            )

            # Build normalized resource
            resource = {
                "service": actual_service.upper(),
                "resource_type": resource_type,
                "resource_id": resource_id,
                "resource_name": resource_name,
                "arn": arn,
                "region": region,
                "account_id": self._extract_account_id(arn),
                "tags": tags,
                "raw_data": raw_data,
                "discovered_via": f"ServiceAPI:{operation_name}",
                "discovered_at": datetime.utcnow().isoformat(),
                "tagged": bool(tags),
                "priority": "primary",  # Service API discoveries are primary
            }

            return resource

        except Exception as e:
            self.logger.debug(f"Resource normalization failed: {e}")
            return None

    def _create_string_resource(
        self,
        value: str,
        service_name: str,
        region: str,
        resource_type: str,
        operation_name: str,
    ) -> Optional[Dict]:
        """Create resource from string value (like SQS queue URLs)."""
        try:
            resource = {
                "service": service_name.upper(),
                "resource_type": resource_type,
                "resource_id": value,
                "resource_name": value.split("/")[-1] if "/" in value else value,
                "arn": value,  # For some services, the URL is the ARN equivalent
                "region": region,
                "account_id": None,
                "tags": {},
                "raw_data": {"url": value},
                "discovered_via": f"ServiceAPI:{operation_name}",
                "discovered_at": datetime.utcnow().isoformat(),
                "tagged": False,
                "priority": "primary",  # Service API discoveries are primary
            }

            return resource

        except Exception as e:
            self.logger.debug(f"String resource creation failed: {e}")
            return None

    def _extract_resource_id(self, data: Dict, resource_type: str) -> Optional[str]:
        """Extract resource ID from AWS resource data."""
        # Common ID field patterns
        id_fields = [
            "Id",
            "ResourceId",
            "ARN",
            "Arn",
            f"{resource_type}Id",
            f"{resource_type}Name",
            "Name",
            "Identifier",
        ]

        # Service-specific patterns - prioritize human-readable IDs over ARNs
        service_patterns = {
            "VPC": ["VpcId"],
            "Subnet": ["SubnetId"],
            "SecurityGroup": ["GroupId"],
            "Instance": ["InstanceId"],
            "Volume": ["VolumeId"],
            "KeyPair": ["KeyName"],
            "Bucket": ["Name"],
            "DBInstance": ["DBInstanceIdentifier"],
            "Function": ["FunctionName"],
            "LoadBalancer": ["LoadBalancerName", "LoadBalancerArn"],
            "User": ["UserName"],
            "Role": ["RoleName"],
            "HostedZone": ["Id"],
            "Distribution": ["Id"],
            "Stack": ["StackName", "StackId"],  # Prefer StackName over StackId/ARN
            "StackSet": ["StackSetName", "StackSetId"],  # Prefer name over ID
            # Additional patterns for other services
            "Key": ["KeyId"],
            "Alias": ["AliasName"],
            "Alarm": ["AlarmName"],
            "Dashboard": ["DashboardName"],
            "Topic": ["TopicArn"],  # SNS topics use ARN as identifier
            "Queue": ["QueueUrl"],  # SQS queues use URL as identifier
            "Table": ["TableName"],
            "RestApi": ["id", "name"],
            "Certificate": ["CertificateArn"],
            "Trail": ["Name", "TrailARN"],
            "Rule": ["Name"],
            "EventBus": ["Name"],
        }

        # Try service-specific patterns first
        if resource_type in service_patterns:
            for field in service_patterns[resource_type]:
                if field in data and data[field]:
                    return str(data[field])

        # Try common patterns
        for field in id_fields:
            if field in data and data[field]:
                return str(data[field])

        return None

    def _extract_resource_name(self, data: Dict) -> Optional[str]:
        """Extract resource name from AWS resource data."""
        name_fields = ["Name", "ResourceName", "Tags.Name"]

        for field in name_fields:
            if field in data and data[field]:
                return str(data[field])

        # Check tags for Name
        if "Tags" in data:
            tags = data["Tags"]
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, dict) and tag.get("Key") == "Name":
                        return tag.get("Value", "")
            elif isinstance(tags, dict) and "Name" in tags:
                return str(tags["Name"])

        return None

    def _extract_tags(self, data: Dict) -> Dict[str, str]:
        """Extract tags from AWS resource data."""
        tags = {}

        if "Tags" in data:
            tag_data = data["Tags"]
            if isinstance(tag_data, list):
                for tag in tag_data:
                    if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                        tags[tag["Key"]] = tag["Value"]
            elif isinstance(tag_data, dict):
                tags.update(tag_data)

        return tags

    def _extract_account_id(self, arn: str) -> Optional[str]:
        """Extract account ID from ARN."""
        if arn and arn.startswith("arn:aws:"):
            parts = arn.split(":")
            if len(parts) >= 5:
                return parts[4]
        return None

    def _construct_arn(
        self, service: str, region: str, resource_type: str, resource_id: str
    ) -> str:
        """Construct ARN for resources that don't provide one."""
        try:
            # Get account ID from STS if available
            try:
                sts = self.session.client("sts")
                account_id = sts.get_caller_identity()["Account"]
            except Exception:
                account_id = "000000000000"  # Placeholder

            # Handle service-specific ARN formats
            if service == "s3":
                return f"arn:aws:s3:::{resource_id}"
            elif service == "iam":
                return (
                    f"arn:aws:iam::{account_id}:{resource_type.lower()}/{resource_id}"
                )
            elif service in ["cloudfront", "route53"]:
                return f"arn:aws:{service}::{account_id}:{resource_type.lower()}/{resource_id}"
            else:
                return f"arn:aws:{service}:{region}:{account_id}:{resource_type.lower()}/{resource_id}"

        except Exception:
            return f"arn:aws:{service}:{region}:unknown:{resource_type.lower()}/{resource_id}"

    def _enrich_with_tagging_api(self):
        """Enrich discovered resources with additional tag data from ResourceGroupsTagging API."""
        self.logger.info("🏷️ Enriching resources with ResourceGroupsTagging API data")

        # Create ARN lookup for existing resources
        arn_to_resource = {r["arn"]: r for r in self.resources if r.get("arn")}

        enriched_count = 0
        new_resources_found = 0

        for region in self.regions:
            try:
                rgt_client = self.session.client(
                    "resourcegroupstaggingapi", region_name=region
                )
                paginator = rgt_client.get_paginator("get_resources")

                for page in paginator.paginate():
                    for resource in page.get("ResourceTagMappingList", []):
                        arn = resource.get("ResourceARN", "")
                        tags = {
                            tag["Key"]: tag["Value"] for tag in resource.get("Tags", [])
                        }

                        if arn in arn_to_resource:
                            # Enrich existing resource with additional tags
                            existing_resource = arn_to_resource[arn]
                            existing_resource["tags"].update(tags)
                            existing_resource["tagged"] = bool(
                                existing_resource["tags"]
                            )
                            enriched_count += 1
                        else:
                            # This is a resource we missed - add it as fallback only
                            # Check if we should show this fallback resource based on display mode
                            should_show_fallback = False

                            if self.fallback_display_mode == "always":
                                should_show_fallback = True
                            elif self.fallback_display_mode == "never":
                                should_show_fallback = False
                            else:  # auto mode
                                # Show fallback only if no primary resources were found for this service
                                try:
                                    service = self._extract_service_from_arn(arn)
                                    should_show_fallback = (
                                        service
                                        not in self.services_with_primary_resources
                                    )
                                except Exception:
                                    # If we can't determine service, default to showing in auto mode
                                    should_show_fallback = True

                            if should_show_fallback:
                                try:
                                    service = self._extract_service_from_arn(arn)
                                    if service:
                                        resource_id = (
                                            arn.split("/")[-1]
                                            if "/" in arn
                                            else arn.split(":")[-1]
                                        )

                                        # Apply the same service classification logic for fallback resources
                                        actual_service = self._determine_actual_service(
                                            service, "Unknown", resource_id, arn
                                        )

                                        new_resource = {
                                            "service": actual_service.upper(),
                                            "resource_type": "Unknown",
                                            "resource_id": resource_id,
                                            "resource_name": tags.get("Name"),
                                            "arn": arn,
                                            "region": region,
                                            "account_id": self._extract_account_id(arn),
                                            "tags": tags,
                                            "raw_data": {"arn": arn},
                                            "discovered_via": "ResourceGroupsTaggingAPI:Fallback",
                                            "discovered_at": datetime.utcnow().isoformat(),
                                            "tagged": True,
                                            "priority": "fallback",  # Mark as lower priority
                                        }
                                        self.resources.append(new_resource)
                                        new_resources_found += 1
                                except Exception as e:
                                    self.logger.debug(
                                        f"Failed to process tagged resource {arn}: {e}"
                                    )
                            else:
                                # Resource would have been added as fallback but is filtered
                                if self.fallback_display_mode == "auto":
                                    self.logger.debug(
                                        f"Skipping fallback resource {arn} - primary resources exist for service"
                                    )
                                elif self.fallback_display_mode == "never":
                                    self.logger.debug(
                                        f"Skipping fallback resource {arn} - fallback display disabled"
                                    )

            except Exception as e:
                self.logger.warning(
                    f"ResourceGroupsTagging enrichment failed in {region}: {e}"
                )

        # Report services with primary resources for transparency
        if self.fallback_display_mode == "auto":
            if self.services_with_primary_resources:
                self.logger.info(
                    f"📊 Services with primary resources found: {sorted(self.services_with_primary_resources)}"
                )
            self.logger.info(
                "🔍 Auto mode: Fallback resources shown only for services "
                "without primary discoveries"
            )

        self.logger.info(
            f"🏷️ Tag enrichment complete: enriched {enriched_count} resources, "
            f"found {new_resources_found} additional tagged resources"
        )

    def _extract_service_from_arn(self, arn: str) -> Optional[str]:
        """Extract service name from ARN."""
        if arn and arn.startswith("arn:aws:"):
            parts = arn.split(":")
            if len(parts) >= 3:
                return parts[2]
        return None

    def _validate_with_billing(self):
        """Comprehensive validation of discovered resources against billing data."""
        if not self.billing_services:
            self.logger.warning(
                "💸 No billing data available - cannot validate discovery completeness"
            )
            return

        discovered_services = {r["service"].lower() for r in self.resources}

        self.logger.info("💰 BILLING vs DISCOVERY ANALYSIS")
        self.logger.info("=" * 50)

        # Create comprehensive comparison
        all_services = discovered_services | self.billing_services
        comparison_data = []

        for service in sorted(all_services):
            has_billing = service in self.billing_services
            has_resources = service in discovered_services
            billing_cost = self.billing_spend.get(service, 0.0)
            resource_count = len(
                [r for r in self.resources if r["service"].lower() == service]
            )

            status = "✅ MATCHED"
            if has_billing and not has_resources:
                status = "❌ MISSING RESOURCES"
            elif has_resources and not has_billing:
                status = "🆓 FREE TIER"

            comparison_data.append(
                {
                    "service": service.upper(),
                    "billing": f"${billing_cost:.3f}" if has_billing else "N/A",
                    "resources": resource_count if has_resources else 0,
                    "status": status,
                }
            )

            self.logger.info(
                f"{status:<20} {service.upper():<15} Billing: ${billing_cost:<8.3f} Resources: {resource_count}"
            )

        # Summary analysis
        missing_services = self.billing_services - discovered_services
        unbilled_services = discovered_services - self.billing_services
        matched_services = discovered_services & self.billing_services

        self.logger.info("=" * 50)
        self.logger.info("📊 DISCOVERY COMPLETENESS SUMMARY:")
        self.logger.info(
            f"   ✅ Matched (billing + resources): {len(matched_services)} services"
        )
        self.logger.info(
            f"   ❌ Missing resources (billing only): {len(missing_services)} services"
        )
        self.logger.info(
            f"   🆓 Free tier (resources only): {len(unbilled_services)} services"
        )

        if missing_services:
            self.logger.warning("💸 MISSING RESOURCES for services with billing:")
            for service in sorted(missing_services):
                cost = self.billing_spend.get(service, 0.0)
                self.logger.warning(
                    f"   • {service.upper()}: ${cost:.3f} - resources not discovered"
                )

        if unbilled_services:
            self.logger.info("🆓 FREE TIER SERVICES (no billing cost):")
            for service in sorted(unbilled_services):
                count = len(
                    [r for r in self.resources if r["service"].lower() == service]
                )
                self.logger.info(
                    f"   • {service.upper()}: {count} resources (likely free tier)"
                )

        # Calculate overall detection rate
        total_billing_services = len(self.billing_services)
        detected_billing_services = len(matched_services)
        if total_billing_services > 0:
            detection_rate = (detected_billing_services / total_billing_services) * 100
            self.logger.info(
                f"🎯 DETECTION RATE: {detection_rate:.1f}% ({detected_billing_services}/{total_billing_services} billing services)"
            )

        self.logger.info("=" * 50)

    def _post_process_resources(self):
        """Post-process resources for consistency and additional metadata."""
        # Enhanced S3 bucket region detection using boto3 API
        self._enhance_s3_buckets()

        # Smart duplicate removal prioritizing service APIs over fallback methods
        self._remove_duplicates_with_priority()

        # Add billing metadata
        for resource in self.resources:
            service = resource["service"].lower()
            resource["billing_validated"] = service in self.billing_services
            resource["monthly_spend"] = self.billing_spend.get(service, 0.0)

        self.logger.info(
            f"📊 Post-processing complete: {len(self.resources)} unique resources"
        )

    def _enhance_s3_buckets(self):
        """Use boto3 APIs to get correct regions and metadata for all services."""
        # S3 bucket region detection
        s3_client = self.session.client("s3")

        for resource in self.resources:
            if (
                resource.get("service") == "S3"
                and resource.get("resource_type") == "Bucket"
            ):
                bucket_name = resource.get("resource_id")
                try:
                    # Use boto3 S3 API to get bucket location
                    response = s3_client.get_bucket_location(Bucket=bucket_name)
                    region = (
                        response.get("LocationConstraint") or "us-east-1"
                    )  # us-east-1 returns None

                    # Update resource with correct region
                    resource["region"] = region
                    resource["raw_data"]["boto3_region"] = region

                    # Reconstruct ARN with correct region
                    resource["arn"] = f"arn:aws:s3:::{bucket_name}"

                    self.logger.debug(
                        f"Enhanced S3 bucket {bucket_name} with region {region}"
                    )

                except Exception as e:
                    self.logger.debug(
                        f"Failed to get S3 bucket region for {bucket_name}: {e}"
                    )
                    continue

        # Lambda function region/runtime enhancement
        self._enhance_lambda_functions()

        # RDS instance region/engine enhancement
        self._enhance_rds_resources()

        # CloudFormation stack region/status enhancement
        self._enhance_cloudformation_stacks()

    def _enhance_lambda_functions(self):
        """Enhance Lambda functions with detailed metadata from boto3 API."""
        for region in self.regions:
            lambda_functions = [
                r
                for r in self.resources
                if r.get("service") == "LAMBDA" and r.get("resource_type") == "Function"
            ]

            if not lambda_functions:
                continue

            try:
                lambda_client = self.session.client("lambda", region_name=region)

                for resource in lambda_functions:
                    function_name = resource.get("resource_id")
                    try:
                        # Get detailed function configuration
                        response = lambda_client.get_function(
                            FunctionName=function_name
                        )
                        config = response.get("Configuration", {})

                        # Update with accurate region and metadata
                        resource["region"] = region
                        resource["raw_data"]["boto3_config"] = config
                        resource["raw_data"]["runtime"] = config.get("Runtime")
                        resource["raw_data"]["memory_size"] = config.get("MemorySize")
                        resource["raw_data"]["timeout"] = config.get("Timeout")

                        self.logger.debug(
                            f"Enhanced Lambda function {function_name} in {region}"
                        )

                    except Exception as e:
                        self.logger.debug(
                            f"Failed to enhance Lambda function {function_name}: {e}"
                        )
                        continue

            except Exception as e:
                self.logger.debug(f"Failed to create Lambda client for {region}: {e}")
                continue

    def _enhance_rds_resources(self):
        """Enhance RDS resources with detailed metadata from boto3 API."""
        for region in self.regions:
            rds_instances = [
                r
                for r in self.resources
                if r.get("service") == "RDS"
                and "Instance" in r.get("resource_type", "")
            ]

            if not rds_instances:
                continue

            try:
                rds_client = self.session.client("rds", region_name=region)

                for resource in rds_instances:
                    instance_id = resource.get("resource_id")
                    try:
                        # Get detailed instance information
                        response = rds_client.describe_db_instances(
                            DBInstanceIdentifier=instance_id
                        )
                        instances = response.get("DBInstances", [])

                        if instances:
                            instance = instances[0]
                            # Update with accurate region and metadata
                            resource["region"] = region
                            resource["raw_data"]["boto3_instance"] = instance
                            resource["raw_data"]["engine"] = instance.get("Engine")
                            resource["raw_data"]["engine_version"] = instance.get(
                                "EngineVersion"
                            )
                            resource["raw_data"]["instance_class"] = instance.get(
                                "DBInstanceClass"
                            )
                            resource["raw_data"]["availability_zone"] = instance.get(
                                "AvailabilityZone"
                            )

                            self.logger.debug(
                                f"Enhanced RDS instance {instance_id} in {region}"
                            )

                    except Exception as e:
                        self.logger.debug(
                            f"Failed to enhance RDS instance {instance_id}: {e}"
                        )
                        continue

            except Exception as e:
                self.logger.debug(f"Failed to create RDS client for {region}: {e}")
                continue

    def _enhance_cloudformation_stacks(self):
        """Enhance CloudFormation stacks with detailed metadata from boto3 API."""
        for region in self.regions:
            cf_stacks = [
                r
                for r in self.resources
                if r.get("service") == "CLOUDFORMATION"
                and r.get("resource_type") == "Stack"
            ]

            if not cf_stacks:
                continue

            try:
                cf_client = self.session.client("cloudformation", region_name=region)

                for resource in cf_stacks:
                    stack_name = resource.get("resource_id")
                    try:
                        # Get detailed stack information
                        response = cf_client.describe_stacks(StackName=stack_name)
                        stacks = response.get("Stacks", [])

                        if stacks:
                            stack = stacks[0]
                            # Update with accurate region and metadata
                            resource["region"] = region
                            resource["raw_data"]["boto3_stack"] = stack
                            resource["raw_data"]["stack_status"] = stack.get(
                                "StackStatus"
                            )
                            resource["raw_data"]["creation_time"] = stack.get(
                                "CreationTime"
                            )
                            resource["raw_data"]["drift_status"] = stack.get(
                                "DriftInformation", {}
                            ).get("StackDriftStatus")

                            self.logger.debug(
                                f"Enhanced CloudFormation stack {stack_name} in {region}"
                            )

                    except Exception as e:
                        self.logger.debug(
                            f"Failed to enhance CloudFormation stack {stack_name}: {e}"
                        )
                        continue

            except Exception as e:
                self.logger.debug(
                    f"Failed to create CloudFormation client for {region}: {e}"
                )
                continue

    def _remove_duplicates_with_priority(self):
        """Remove duplicates prioritizing service API discoveries over fallback methods."""
        # Group resources by ARN
        arn_groups = {}
        for resource in self.resources:
            arn = resource.get("arn")
            if arn:
                if arn not in arn_groups:
                    arn_groups[arn] = []
                arn_groups[arn].append(resource)

        # Select best resource for each ARN (prioritize service API over fallback)
        deduplicated = []
        for arn, resource_group in arn_groups.items():
            if len(resource_group) == 1:
                deduplicated.append(resource_group[0])
            else:
                # Sort by priority: primary (service API) > fallback (ResourceGroupsTagging)
                resource_group.sort(
                    key=lambda r: (
                        r.get("priority", "fallback") != "primary",  # Primary first
                        not r.get("tagged", False),  # Tagged resources second
                        r.get("discovered_at", ""),  # Newer discoveries last
                    )
                )

                best_resource = resource_group[0]

                # Merge tags from all sources
                all_tags = {}
                for resource in resource_group:
                    all_tags.update(resource.get("tags", {}))

                best_resource["tags"] = all_tags
                best_resource["tagged"] = bool(all_tags)
                best_resource["duplicate_sources"] = len(resource_group)

                deduplicated.append(best_resource)

                self.logger.debug(
                    f"Merged {len(resource_group)} duplicates for {arn}, kept {best_resource.get('discovered_via', 'unknown')}"
                )

        self.resources = deduplicated

        self.logger.info(
            "🔄 Duplicate removal complete: prioritized service API discoveries over fallback methods"
        )

    def _determine_actual_service(
        self, service_name: str, resource_type: str, resource_id: str, arn: str
    ) -> str:
        """Determine the actual service for proper classification, especially for VPC resources discovered via EC2 client."""
        # VPC-related resources should be classified as VPC service, not EC2
        vpc_resource_indicators = [
            "vpc-",
            "subnet-",
            "igw-",
            "rtb-",
            "acl-",
            "sg-",
            "nat-",
            "eip-",
        ]
        vpc_resource_types = [
            "VPC",
            "Subnet",
            "SecurityGroup",
            "InternetGateway",
            "NatGateway",
            "RouteTable",
            "NetworkAcl",
            "ElasticIP",
        ]

        # Check resource ID prefixes
        if any(
            resource_id.startswith(indicator) for indicator in vpc_resource_indicators
        ):
            return "vpc"

        # Check resource types
        if resource_type in vpc_resource_types:
            return "vpc"

        # Check ARN for VPC service indicators
        if ":ec2:" in arn and any(
            indicator in arn
            for indicator in [
                "vpc/",
                "subnet/",
                "security-group/",
                "internet-gateway/",
                "nat-gateway/",
            ]
        ):
            return "vpc"

        # Default to original service
        return service_name

    def _normalize_billing_service_name(self, billing_name: str) -> str:
        """Normalize billing service name to match AWS service names."""
        mappings = {
            "Amazon Elastic Compute Cloud - Compute": "ec2",
            "Amazon Simple Storage Service": "s3",
            "Amazon Relational Database Service": "rds",
            "AWS Lambda": "lambda",
            "Amazon CloudFront": "cloudfront",
            "Amazon Route 53": "route53",
            "AWS Identity and Access Management": "iam",
            "Amazon CloudWatch": "cloudwatch",
            "AWS Key Management Service": "kms",
            "Elastic Load Balancing": "elasticloadbalancing",
            "Amazon Virtual Private Cloud": "vpc",
            "Amazon Elastic Container Service": "ecs",
            "Amazon Elastic Kubernetes Service": "eks",
            "Amazon Simple Notification Service": "sns",
            "Amazon Simple Queue Service": "sqs",
            "Amazon DynamoDB": "dynamodb",
            "Amazon API Gateway": "apigateway",
            "AWS Glue": "glue",
            "Amazon WorkMail": "workmail",
            "AWS CloudFormation": "cloudformation",
            "AWS Certificate Manager": "acm",
            "AWS CloudTrail": "cloudtrail",
            "CloudWatch Events": "events",
            "Amazon CloudWatch Events": "events",
        }

        return mappings.get(
            billing_name, billing_name.lower().replace(" ", "").replace("-", "")
        )
