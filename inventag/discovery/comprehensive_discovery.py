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
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import boto3
from botocore.exceptions import ClientError

from .aws_clients import create_client
from .regions import cost_explorer_region, global_home_region
from .sensitive_fields import mask_secret_values
from .service_filter import canonical_service
from .arn_utils import (
    ResourceArnIndex,
    arn_service,
    build_arn,
    dedupe_key,
    extract_arn,
    parse_arn,
    partition_for_region,
)

# Services whose resources belong to the account, not to a region. They are
# listed once per account from the home region and shown with this region.
GLOBAL_REGION_LABEL = "global"
GLOBAL_HOME_REGION = "us-east-1"


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
        enable_billing_validation: bool = True,
    ):
        self.session = session or boto3.Session()
        # False: never call Cost Explorer (AWS charges for each request)
        self.enable_billing_validation = enable_billing_validation
        self.logger = logging.getLogger(__name__)
        self.logger.propagate = False  # Prevent duplicate logging
        self.regions = regions or ["us-east-1"]
        # Where account-wide services are read: us-east-1 in the aws
        # partition, cn-north-1 in China, us-gov-west-1 in GovCloud.
        self.home_region = global_home_region(self.regions)

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
                    {
                        # Without a cluster, ListServices reads only the
                        # cluster named "default".
                        "op": "list_services",
                        "key": "serviceArns",
                        "type": "Service",
                        "per_parent": {
                            "op": "list_clusters",
                            "key": "clusterArns",
                            "param": "cluster",
                        },
                    },
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
                    ("get_crawlers", "Crawlers", "Crawler"),
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

    def _client(self, service_name: str, region: Optional[str] = None):
        """A client with the shared retry settings (see aws_clients.py)."""
        return create_client(self.session, service_name, region)

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
        if self.enable_billing_validation:
            self._discover_billing_services()

        # Step 2: Comprehensive service-specific discovery (PRIMARY)
        self._discover_all_service_resources(max_workers)

        # Step 3: Enrich with ResourceGroupsTagging API (SECONDARY)
        self._enrich_with_tagging_api()

        # Step 4: Validate against billing data
        if self.enable_billing_validation:
            self._validate_with_billing()
            self._add_billing_fallback_resources()

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
            ce_client = self._client("ce", cost_explorer_region(self.regions))

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
            self._warn_once(
                "billing",
                f"Cost Explorer data is not available, so billing "
                f"checks are skipped: {e}",
            )

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
                # Global service - listed once per account from the home
                # region, whichever regions were requested.
                discovery_tasks.append(
                    {
                        "service": service_name,
                        "region": self.home_region,
                        "config": config,
                        "priority": 1 if config.get("critical", False) else 2,
                    }
                )

        # Certificates CloudFront uses must be in us-east-1. Read them even
        # when us-east-1 is not one of the requested regions.
        # (CloudFront certificates exist only in the aws partition.)
        if self.home_region not in self.regions and self.home_region == "us-east-1":
            self._discover_cloudfront_certificates()

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
            # No overall timeout: a TimeoutError here threw away every
            # result of a long scan. Each call has botocore's own timeouts.
            for future in as_completed(future_to_task):
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

    def _discover_cloudfront_certificates(self) -> int:
        """ACM certificates in us-east-1 that a CloudFront distribution uses."""
        found = 0
        try:
            acm = self._client("acm", self.home_region)
            for page in acm.get_paginator("list_certificates").paginate():
                for summary in page.get("CertificateSummaryList", []):
                    arn = summary.get("CertificateArn", "")
                    detail = acm.describe_certificate(CertificateArn=arn)
                    cert = detail.get("Certificate", {})
                    if not any(":cloudfront:" in a for a in cert.get("InUseBy", [])):
                        continue
                    resource = self._normalize_resource(
                        summary,
                        "acm",
                        self.home_region,
                        "Certificate",
                        "list_certificates",
                    )
                    if resource:
                        self.resources.append(resource)
                        self.services_with_primary_resources.add("acm")
                        found += 1
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in self.DENIED_CODES:
                self._warn_once(
                    "denied:acm",
                    f"No permission for acm in {self.home_region} ({code}); "
                    "CloudFront certificates are skipped.",
                )
            else:
                self.logger.debug(f"CloudFront certificate lookup failed: {e}")
        except Exception as e:
            self.logger.debug(f"CloudFront certificate lookup failed: {e}")
        return found

    def _discover_service_in_region(self, task: Dict[str, Any]) -> int:
        """Discover resources for a specific service in a specific region."""
        service_name = task["service"]
        region = task["region"]
        config = task["config"]
        resources_found = 0

        try:
            # Create service client (handle special cases like VPC using EC2 client)
            client_service = config.get("client_service", service_name)
            client = self._client(client_service, region)

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

    @staticmethod
    def _op_spec(operation_config) -> Dict[str, Any]:
        """One operation of ``service_discovery_patterns`` as a dict.

        Entries are either the short tuple ``(operation, result_key,
        resource_type[, params])`` or a dict with these keys:

        - ``op``, ``key``, ``type``: operation (snake_case), result key
          (dots for nesting) and the resource type shown in the report.
        - ``params``: fixed request parameters (read-only filters only).
        - ``id`` / ``name`` / ``arn``: response fields with the resource ID,
          name and ARN. Without them the generic field guessing is used.
        - ``arn_template``: ARN to build when the response has none, with
          ``{partition}``, ``{region}``, ``{account}`` and ``{id}``.
        - ``per_parent``: ``{"op", "key", "param"}``: list the parents first
          (for example ECS clusters) and call ``op`` once per parent.
        - ``token``: ``(request_param, response_field)`` for operations that
          botocore cannot paginate (for example Firehose's
          ``ExclusiveStartDeliveryStreamName``).
        """
        if isinstance(operation_config, dict):
            spec = dict(operation_config)
            spec.setdefault("params", {})
            return spec
        spec = {
            "op": operation_config[0],
            "key": operation_config[1],
            "type": operation_config[2],
            "params": operation_config[3] if len(operation_config) > 3 else {},
        }
        return spec

    _TOKEN_FIELDS = (
        ("NextToken", "NextToken"),
        ("nextToken", "nextToken"),
        ("Marker", "NextMarker"),
        ("NextMarker", "NextMarker"),
        ("Marker", "Marker"),
    )

    def _pages(self, client, operation_name: str, params: Dict[str, Any]):
        """Every page of a list/describe call.

        botocore's paginator when it has one. Otherwise follow the operation's
        own continuation token, so a second page is never silently dropped.
        A failing page raises; pages already returned are kept by the caller.
        """
        if client.can_paginate(operation_name):
            yield from client.get_paginator(operation_name).paginate(**params)
            return
        operation = getattr(client, operation_name)
        api_name = client.meta.method_to_api_mapping.get(operation_name)
        input_members, output_members = set(), set()
        if api_name:
            model = client.meta.service_model.operation_model(api_name)
            if model.input_shape is not None:
                input_members = set(model.input_shape.members)
            if model.output_shape is not None:
                output_members = set(model.output_shape.members)
        token = next(
            (
                (req, resp)
                for req, resp in self._TOKEN_FIELDS
                if req in input_members and resp in output_members
            ),
            None,
        )
        request = dict(params)
        seen = set()
        while True:
            page = operation(**request)
            yield page
            if not token:
                return
            next_token = page.get(token[1])
            if not next_token or next_token in seen:
                return
            seen.add(next_token)
            request[token[0]] = next_token

    def _pages_with_token(self, client, spec: Dict[str, Any], params: Dict):
        """Pages of an operation that uses a custom token (see ``_op_spec``)."""
        operation = getattr(client, spec["op"])
        request_param, more_field = spec["token"]
        request = dict(params)
        while True:
            page = operation(**request)
            yield page
            items = page.get(spec["key"]) or []
            if not page.get(more_field) or not items:
                return
            last = items[-1]
            request[request_param] = (
                last if isinstance(last, str) else last.get(spec.get("id", ""))
            )

    def _execute_discovery_operation(
        self, client, service_name: str, region: str, operation_config
    ) -> int:
        """Execute a single discovery operation and extract resources."""
        spec = self._op_spec(operation_config)
        operation_name = spec["op"]

        try:
            param_sets = [dict(spec["params"])]
            parent = spec.get("per_parent")
            if parent:
                param_sets = []
                for page in self._pages(client, parent["op"], {}):
                    for value in page.get(parent["key"], []) or []:
                        param_sets.append({**spec["params"], parent["param"]: value})

            resources_found = 0
            for params in param_sets:
                pages = (
                    self._pages_with_token(client, spec, params)
                    if spec.get("token")
                    else self._pages(client, operation_name, params)
                )
                for page in pages:
                    resources_found += self._extract_resources_from_response(
                        page,
                        spec["key"],
                        service_name,
                        region,
                        spec["type"],
                        operation_name,
                        spec,
                    )
            return resources_found

        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in self.DENIED_CODES:
                self._warn_once(
                    f"denied:{service_name}",
                    f"No permission for {service_name} "
                    f"({operation_name} in {region}: {code}). "
                    f"Resources of {service_name} are skipped; add the "
                    "read permission to see them.",
                )
            else:
                self.logger.debug(
                    f"{service_name} {operation_name} in {region} failed: {e}"
                )
            return 0
        except Exception as e:
            # Operation-level errors are expected and handled gracefully
            self.logger.debug(f"{service_name} {operation_name} failed: {e}")
            return 0

    DENIED_CODES = {
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
        "UnauthorizedAccess",
        "AuthorizationError",
        "OptInRequired",
    }

    def _extract_resources_from_response(
        self,
        response: Dict,
        response_key: str,
        service_name: str,
        region: str,
        resource_type: str,
        operation_name: str,
        spec: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Extract resources from AWS API response."""
        try:
            # Handle nested response keys (like 'DistributionList.Items')
            data = response
            for key in response_key.split("."):
                data = data.get(key, [])

            if not isinstance(data, list):
                data = [data] if data else []

            # DescribeInstances returns reservations. The instances are one
            # level down, and a reservation has no resource ID of its own.
            if resource_type == "Instance":
                data = [
                    instance
                    for item in data
                    for instance in (
                        item.get("Instances", [])
                        if isinstance(item, dict) and "Instances" in item
                        else [item]
                    )
                ]

            resources_added = 0
            for item in data:
                if isinstance(item, dict):
                    resource = self._normalize_resource(
                        item,
                        service_name,
                        region,
                        resource_type,
                        operation_name,
                        spec,
                    )
                    if resource:
                        self.resources.append(resource)
                        resources_added += 1
                        # Track service with primary resources for smart fallback logic
                        self.services_with_primary_resources.add(service_name)
                elif isinstance(item, str):
                    # Handle string responses (like SQS queue URLs)
                    resource = self._create_string_resource(
                        item, service_name, region, resource_type, operation_name, spec
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
        spec: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict]:
        """Normalize a resource into standard format."""
        spec = spec or {}
        try:
            # Extract resource identifier
            resource_id = (
                raw_data.get(spec["id"]) if spec.get("id") else None
            ) or self._extract_resource_id(raw_data, resource_type)
            if not resource_id:
                return None
            resource_id = str(resource_id)

            # Extract resource name
            resource_name = (
                raw_data.get(spec["name"]) if spec.get("name") else None
            ) or self._extract_resource_name(raw_data)

            # Extract ARN if available
            arn = (raw_data.get(spec["arn"]) if spec.get("arn") else None) or (
                self._arn_from_template(spec, region, resource_id)
                if spec.get("arn_template") and not extract_arn(raw_data)
                else self._construct_arn(
                    service_name, region, resource_type, resource_id, raw_data
                )
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
                "region": (
                    GLOBAL_REGION_LABEL
                    if actual_service.lower() in self.GLOBAL_ARN_SERVICES
                    else region
                ),
                "account_id": self._extract_account_id(arn) or raw_data.get("OwnerId"),
                "tags": tags,
                # Values such as Lambda environment variables are masked
                "raw_data": mask_secret_values(raw_data),
                "discovered_via": f"ServiceAPI:{operation_name}",
                "discovered_at": datetime.now(timezone.utc).isoformat(),
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
        spec: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict]:
        """Create a resource from a string a list call returns.

        The string is a queue URL (SQS), an ARN (ECS) or a name (EKS).
        """
        spec = spec or {}
        try:
            if spec.get("arn_template") and not value.startswith("arn:"):
                arn = self._arn_from_template(spec, region, value)
            else:
                arn = self._construct_arn(
                    service_name, region, resource_type, value, {}
                )
            name = re.split(r"[/]", value)[-1] if value else value
            resource = {
                "service": service_name.upper(),
                "resource_type": resource_type,
                "resource_id": value,
                "resource_name": name,
                "arn": arn,
                "region": region,
                "account_id": self._extract_account_id(arn),
                "tags": {},
                "raw_data": {"url" if value.startswith("http") else "name": value},
                "discovered_via": f"ServiceAPI:{operation_name}",
                "discovered_at": datetime.now(timezone.utc).isoformat(),
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
            "DBCluster": ["DBClusterIdentifier"],
            "DBSnapshot": ["DBSnapshotIdentifier"],
            "DBSubnetGroup": ["DBSubnetGroupName"],
            "DBParameterGroup": ["DBParameterGroupName"],
            "Function": ["FunctionName"],
            "LoadBalancer": ["LoadBalancerName", "LoadBalancerArn"],
            "LoadBalancerV2": ["LoadBalancerName", "LoadBalancerArn"],
            "TargetGroup": ["TargetGroupName", "TargetGroupArn"],
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
            "ElasticIP": ["AllocationId", "PublicIp"],
            "Organization": ["OrganizationId"],
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

        # RDS returns its tags as "TagList"; most services use "Tags"
        for tag_key in ("Tags", "TagList"):
            if tag_key not in data:
                continue
            tag_data = data[tag_key]
            if isinstance(tag_data, list):
                for tag in tag_data:
                    if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                        tags[tag["Key"]] = tag["Value"]
            elif isinstance(tag_data, dict):
                tags.update(tag_data)

        return tags

    def _extract_account_id(self, arn: str) -> Optional[str]:
        """Account ID from an ARN of any partition (aws, aws-cn, aws-us-gov)."""
        parsed = parse_arn(arn)
        return (parsed or {}).get("account") or None

    def _get_account_id(self) -> str:
        """Account ID of the session. One STS call, then cached.

        This was one GetCallerIdentity call for each resource without an ARN.
        """
        account_id = getattr(self, "_cached_account_id", None)
        if account_id is None:
            try:
                sts = self._client("sts")
                account_id = sts.get_caller_identity()["Account"]
            except Exception:
                account_id = "000000000000"  # Placeholder
            self._cached_account_id = account_id
        return account_id

    def _construct_arn(
        self,
        service: str,
        region: str,
        resource_type: str,
        resource_id: str,
        raw_data: Optional[Dict] = None,
    ) -> str:
        """The real ARN: the one the list call returned, else the AWS form."""
        found = extract_arn(raw_data)
        if found:
            return found
        if service in ("s3",):
            return build_arn(service, resource_type, resource_id, region, None)
        return build_arn(
            service,
            resource_type,
            resource_id,
            region,
            self._get_account_id(),
            raw_data,
        )

    def _arn_from_template(
        self, spec: Dict[str, Any], region: str, resource_id: str
    ) -> str:
        """Build an ARN from ``arn_template`` (see ``_op_spec``)."""
        return spec["arn_template"].format(
            partition=partition_for_region(region),
            region=region,
            account=self._get_account_id(),
            id=resource_id,
            id_noslash=resource_id.lstrip("/"),
        )

    def _tagging_regions(self) -> List[str]:
        """Regions to read tags from: the requested ones, plus the home region.

        Tags of global services (IAM, Route 53, CloudFront) live in us-east-1.
        """
        regions = list(self.regions)
        if self.home_region not in regions:
            regions.append(self.home_region)
        return regions

    def _prefetch_tagging_resources(self) -> Dict[str, List[Dict[str, Any]]]:
        """Read ResourceGroupsTagging API results for every region in parallel.

        GetResources is slow (one page at a time, throttled per account), so
        the regions are fetched concurrently and the results are merged by the
        caller on a single thread. A region that fails is logged and left out.
        """

        def fetch(region: str) -> List[Dict[str, Any]]:
            client = self._client("resourcegroupstaggingapi", region)
            items: List[Dict[str, Any]] = []
            for page in client.get_paginator("get_resources").paginate(
                ResourcesPerPage=100
            ):
                items.extend(page.get("ResourceTagMappingList", []))
            return items

        results: Dict[str, List[Dict[str, Any]]] = {}
        regions = self._tagging_regions()
        with ThreadPoolExecutor(max_workers=min(8, len(regions))) as pool:
            futures = {pool.submit(fetch, r): r for r in regions}
            for fut, region in futures.items():
                try:
                    results[region] = fut.result()
                except Exception as e:
                    self._warn_once(
                        f"tagging:{region}",
                        f"ResourceGroupsTagging enrichment failed in {region}: {e}",
                    )
        return results

    def _warn_once(self, key: str, message: str) -> None:
        """Log a warning once per key (a service or region), not once per call."""
        warned = self.__dict__.setdefault("_warned_keys", set())
        if key in warned:
            self.logger.debug(message)
            return
        warned.add(key)
        self.logger.warning(message)

    def _enrich_with_tagging_api(self):
        """Enrich discovered resources with tags from the ResourceGroupsTagging API.

        An ARN from the API is matched to a discovered resource by normalised
        ARN, then by (service, region, name or ID), so a small ARN difference
        never drops tags. An ARN that matches nothing is added as a fallback
        resource, subject to ``fallback_display_mode``.
        """
        self.logger.info("🏷️ Enriching resources with ResourceGroupsTagging API data")

        index = ResourceArnIndex(r for r in self.resources if r.get("arn"))
        requested = set(self.regions)

        enriched_count = 0
        new_resources_found = 0

        prefetched = self._prefetch_tagging_resources()

        for region in self._tagging_regions():
            if region not in prefetched:
                continue  # the fetch failed and was already logged
            for resource in prefetched[region]:
                arn = resource.get("ResourceARN", "")
                tags = {tag["Key"]: tag["Value"] for tag in resource.get("Tags", [])}
                parsed = parse_arn(arn) or {}
                is_global = parsed.get(
                    "service"
                ) in self.GLOBAL_ARN_SERVICES or not parsed.get("region")

                existing_resource = index.find(arn)
                if existing_resource is not None:
                    existing_resource.setdefault("tags", {}).update(tags)
                    existing_resource["tagged"] = bool(existing_resource["tags"])
                    enriched_count += 1
                    continue

                if region not in requested and not is_global:
                    continue  # the home region was read only for global tags
                if not self._should_show_fallback(arn):
                    continue
                try:
                    service = self._extract_service_from_arn(arn)
                    if not service:
                        continue
                    resource_id = re.split(r"[/:]", parsed["resource"])[-1]
                    actual_service = self._determine_actual_service(
                        service, "Unknown", resource_id, arn
                    )
                    new_resource = {
                        "service": actual_service.upper(),
                        "resource_type": "Unknown",
                        "resource_id": resource_id,
                        "resource_name": tags.get("Name"),
                        "arn": arn,
                        "region": (
                            GLOBAL_REGION_LABEL
                            if parsed.get("service") in self.GLOBAL_ARN_SERVICES
                            else region
                        ),
                        "account_id": self._extract_account_id(arn),
                        "tags": tags,
                        "raw_data": {"arn": arn},
                        "discovered_via": "ResourceGroupsTaggingAPI:Fallback",
                        "discovered_at": datetime.now(timezone.utc).isoformat(),
                        "tagged": True,
                        "priority": "fallback",  # Mark as lower priority
                    }
                    self.resources.append(new_resource)
                    index.add(new_resource)
                    new_resources_found += 1
                except Exception as e:
                    self.logger.debug(f"Failed to process tagged resource {arn}: {e}")

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

    # ARN service codes of services that are not tied to one region.
    GLOBAL_ARN_SERVICES = {"iam", "route53", "cloudfront"}

    def _should_show_fallback(self, arn: str) -> bool:
        """Whether an ARN no discovery handler returned is added to the report."""
        if self.fallback_display_mode == "always":
            return True
        if self.fallback_display_mode == "never":
            return False
        service = self._extract_service_from_arn(arn)
        covered = {
            self.service_discovery_patterns.get(key, {}).get("arn_service")
            or arn_service(key)
            for key in self.services_with_primary_resources
        }
        return service not in covered

    def _extract_service_from_arn(self, arn: str) -> Optional[str]:
        """ARN service code, for ARNs of any partition (aws, aws-cn, aws-us-gov)."""
        parsed = parse_arn(arn)
        return (parsed or {}).get("service") or None

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

    # Billing lines that are not a service with resources.
    _NON_SERVICE_BILLING = {"tax", "refund", "credit", "savingsplans", "support"}

    def _add_billing_fallback_resources(self) -> int:
        """Add one placeholder row per billed service with no discovered resources.

        Discovery only knows the services it has handlers for. Cost Explorer
        knows every service that was used, so a billed service that discovery
        missed is still listed (as "detected from billing", with its monthly
        cost) instead of disappearing from the report.
        """
        if self.fallback_display_mode == "never" or not self.billing_services:
            return 0

        found = {r["service"].lower() for r in self.resources}
        found_keys = {canonical_service(d) for d in found}

        def covered(billed: str) -> bool:
            if canonical_service(billed) in found_keys:
                return True
            return any(
                d == billed
                or (len(d) >= 3 and d in billed)
                or (len(billed) >= 3 and billed in d)
                for d in found
            )

        added = 0
        for service in sorted(self.billing_services):
            if (
                not service
                or service in self._NON_SERVICE_BILLING
                or any(service.startswith(x) for x in ("tax", "refund"))
                or covered(service)
            ):
                continue
            cost = self.billing_spend.get(service, 0.0)
            self.resources.append(
                {
                    "service": service.upper(),
                    "resource_type": "Service (detected from billing)",
                    "resource_id": service,
                    "resource_name": None,
                    "arn": "",
                    "region": "global",
                    "account_id": getattr(self, "account_id", "") or "",
                    "tags": {},
                    "raw_data": {"billing_service": service, "monthly_cost": cost},
                    "discovered_via": "CostExplorer:Fallback",
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "tagged": False,
                    "priority": "fallback",
                    "estimated_monthly_cost": cost,
                }
            )
            added += 1

        if added:
            self.logger.info(
                f"💰 Added {added} services found only on the bill "
                "(no resources discovered; listed as 'detected from billing')"
            )
        return added

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
        s3_client = self._client("s3")

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

    def _resources_by_region(self, service: str, type_test) -> Dict[str, List[Dict]]:
        """Group discovered resources of one service by the region they were
        found in, so each detail call goes to that region only."""
        grouped: Dict[str, List[Dict]] = {}
        for r in self.resources:
            if r.get("service") == service and type_test(r.get("resource_type", "")):
                region = r.get("region")
                if region and region != GLOBAL_REGION_LABEL:
                    grouped.setdefault(region, []).append(r)
        return grouped

    def _enhance_lambda_functions(self):
        """Enhance Lambda functions with detailed metadata from boto3 API.

        Each function is read in the region it was listed in. Reading every
        function in every region gave a function the region (and settings) of
        a same-named function in another region.
        """
        grouped = self._resources_by_region("LAMBDA", lambda t: t == "Function")
        for region, lambda_functions in grouped.items():
            try:
                lambda_client = self._client("lambda", region)

                for resource in lambda_functions:
                    function_name = resource.get("resource_id")
                    try:
                        # Get detailed function configuration. GetFunction would
                        # also return a presigned URL to download the code,
                        # which an inventory never needs.
                        config = lambda_client.get_function_configuration(
                            FunctionName=function_name
                        )
                        config.pop("ResponseMetadata", None)
                        config = mask_secret_values(config)

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
        """Enhance RDS instances with detailed metadata, read in their own region."""
        grouped = self._resources_by_region("RDS", lambda t: t == "DBInstance")
        for region, rds_instances in grouped.items():
            try:
                rds_client = self._client("rds", region)

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
                            resource["raw_data"]["boto3_instance"] = mask_secret_values(
                                instance
                            )
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
        """Enhance CloudFormation stacks with detailed metadata, read in their
        own region."""
        grouped = self._resources_by_region("CLOUDFORMATION", lambda t: t == "Stack")
        for region, cf_stacks in grouped.items():
            try:
                cf_client = self._client("cloudformation", region)

                for resource in cf_stacks:
                    stack_name = resource.get("resource_id")
                    try:
                        # Get detailed stack information
                        response = cf_client.describe_stacks(StackName=stack_name)
                        stacks = response.get("Stacks", [])

                        if stacks:
                            stack = stacks[0]
                            resource["raw_data"]["boto3_stack"] = mask_secret_values(
                                stack
                            )
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
        # Group resources by normalised ARN, so the same resource found under
        # two spellings of its ARN (vpc/ec2, function/x or function:x) is one.
        arn_groups = {}
        for resource in self.resources:
            if resource.get("arn"):
                arn_groups.setdefault(dedupe_key(resource), []).append(resource)
            else:
                arn_groups.setdefault(f"noarn:{id(resource)}", []).append(resource)

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

        # Only EC2 resources can be VPC resources. A Lambda function or an S3
        # bucket named "vpc-..." or "nat-..." stays in its own service.
        if service_name.lower() not in ("ec2", "vpc"):
            return service_name

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

        if billing_name in mappings:
            return mappings[billing_name]
        name = billing_name
        for prefix in ("Amazon ", "AWS "):
            if name.startswith(prefix):
                name = name[len(prefix) :]
                break
        return "".join(ch for ch in name.lower() if ch.isalnum())
