#!/usr/bin/env python3
"""
Enhanced AWS Resource Discovery System with ReadOnlyAccess Support

This module extends the discovery capabilities to leverage AWS ReadOnlyAccess policy
for comprehensive resource attribute extraction while maintaining backward compatibility
with minimal IAM policies.

Key Features:
- Billing-first discovery workflow for active service identification
- Enhanced service-specific attribute extraction with ReadOnlyAccess
- Global service standardization (CloudFront, IAM, Route53 via us-east-1)
- S3 bucket region detection with ARN correction
- Comprehensive boto3 List*/Describe* operations
- Graceful degradation for minimal IAM policies
"""

import logging
import threading
import concurrent.futures
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Import base classes
from .optimized_discovery import OptimizedAWSDiscovery, StandardResource


class ReadOnlyAccessDiscovery(OptimizedAWSDiscovery):
    """Enhanced discovery system leveraging AWS ReadOnlyAccess policy capabilities."""

    def __init__(self, session: boto3.Session = None, **kwargs):
        super().__init__(session, **kwargs)
        self.logger = logging.getLogger(__name__)

        # Track IAM capability level
        self.has_readonly_access = False
        self.permission_level = "minimal"
        self._check_permission_level()

        # Global services that must use us-east-1
        self.global_services = {
            "cloudfront": "us-east-1",
            "iam": "us-east-1",
            "route53": "us-east-1",
            "wa": "us-east-1",
            "wafv2": "us-east-1",
            "shield": "us-east-1",
            "globalaccelerator": "us-east-1",
        }

        # Enhanced service patterns with ReadOnlyAccess capabilities
        self.enhanced_service_patterns = {
            "kms": {
                "resource_types": ["Key", "Alias"],
                "operations": ["ListKeys", "ListAliases", "DescribeKey"],
                "readonly_operations": [
                    "GetKeyPolicy",
                    "GetKeyRotationStatus",
                    "ListKeyPolicies",
                    "ListResourceTags",
                ],
                "enhanced_attributes": [
                    "key_policy",
                    "rotation_enabled",
                    "key_spec",
                    "multi_region",
                    "key_usage",
                    "encryption_algorithms",
                ],
                "region_dependent": True,
            },
            "s3": {
                "resource_types": ["Bucket", "Object"],
                "operations": ["ListBuckets", "GetBucketLocation"],
                "readonly_operations": [
                    "GetBucketEncryption",
                    "GetBucketVersioning",
                    "GetBucketNotification",
                    "GetBucketLifecycle",
                    "GetBucketPolicy",
                    "GetBucketAcl",
                    "GetBucketLogging",
                    "GetBucketReplication",
                    "GetBucketRetentionConfiguration",
                    "GetObjectLockConfiguration",
                    "GetBucketAccelerateConfiguration",
                ],
                "enhanced_attributes": [
                    "encryption_config",
                    "versioning_status",
                    "retention_period",
                    "lifecycle_config",
                    "replication_config",
                    "public_access_block",
                    "object_lock_enabled",
                    "transfer_acceleration",
                    "notification_config",
                ],
                "region_dependent": False,
                "global_service": True,
                "requires_region_detection": True,
            },
            "rds": {
                "resource_types": ["DBInstance", "DBCluster", "DBSnapshot"],
                "operations": ["DescribeDBInstances", "DescribeDBClusters"],
                "readonly_operations": [
                    "DescribeDBParameterGroups",
                    "DescribeDBSubnetGroups",
                    "DescribeDBSnapshots",
                    "DescribeDBClusterSnapshots",
                    "DescribePerformanceInsightsMetrics",
                    "DescribeDBLogFiles",
                ],
                "enhanced_attributes": [
                    "parameter_group",
                    "subnet_group",
                    "backup_window",
                    "maintenance_window",
                    "performance_insights_enabled",
                    "deletion_protection",
                    "automated_backup_retention",
                ],
                "region_dependent": True,
            },
            "lambda": {
                "resource_types": ["Function", "Layer", "EventSourceMapping"],
                "operations": ["ListFunctions", "ListLayers"],
                "readonly_operations": [
                    "GetFunction",
                    "GetFunctionConfiguration",
                    "ListEventSourceMappings",
                    "GetPolicy",
                    "ListVersionsByFunction",
                    "ListAliases",
                ],
                "enhanced_attributes": [
                    "runtime",
                    "memory_size",
                    "timeout",
                    "environment_variables",
                    "vpc_config",
                    "dead_letter_config",
                    "tracing_config",
                    "code_size",
                    "last_modified",
                    "reserved_concurrency",
                ],
                "region_dependent": True,
            },
            "cloudwatch": {
                "resource_types": ["Alarm", "Dashboard", "LogGroup"],
                "operations": ["DescribeAlarms", "ListDashboards"],
                "readonly_operations": [
                    "DescribeAlarmsForMetric",
                    "GetDashboard",
                    "DescribeLogGroups",
                    "DescribeMetricFilters",
                    "DescribeLogStreams",
                    "GetLogEvents",
                ],
                "enhanced_attributes": [
                    "alarm_actions",
                    "metric_name",
                    "threshold",
                    "comparison_operator",
                    "log_retention_days",
                    "metric_filters",
                ],
                "region_dependent": True,
            },
            "elasticloadbalancing": {
                "resource_types": ["LoadBalancer", "TargetGroup", "Listener"],
                "operations": ["DescribeLoadBalancers", "DescribeTargetGroups"],
                "readonly_operations": [
                    "DescribeListeners",
                    "DescribeTargetHealth",
                    "DescribeLoadBalancerAttributes",
                    "DescribeTags",
                ],
                "enhanced_attributes": [
                    "load_balancer_type",
                    "scheme",
                    "target_health",
                    "listener_rules",
                    "ssl_policy",
                    "access_logs_enabled",
                ],
                "region_dependent": True,
            },
        }

    def _check_permission_level(self) -> None:
        """Detect IAM permission level (minimal vs ReadOnlyAccess)."""
        try:
            # Test for ReadOnlyAccess by attempting a read operation
            iam_client = self.session.client("iam", region_name="us-east-1")
            iam_client.list_roles(MaxItems=1)

            # Test Cost Explorer access
            ce_client = self.session.client("ce", region_name="us-east-1")
            ce_client.get_cost_and_usage(
                TimePeriod={
                    "Start": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                    "End": datetime.now().strftime("%Y-%m-%d"),
                },
                Granularity="DAILY",
                Metrics=["BlendedCost"],
            )

            self.has_readonly_access = True
            self.permission_level = "readonly"
            self.logger.info(
                "Detected ReadOnlyAccess policy - enabling enhanced discovery"
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ["AccessDenied", "UnauthorizedOperation"]:
                self.has_readonly_access = False
                self.permission_level = "minimal"
                self.logger.info("Detected minimal IAM policy - using basic discovery")
            else:
                self.logger.warning(f"Permission check failed: {e}")

    def discover_resources_enhanced(
        self,
        regions: List[str] = None,
        services: List[str] = None,
        billing_first: bool = True,
    ) -> List[StandardResource]:
        """
        Enhanced discovery workflow with billing-first approach.

        Args:
            regions: List of regions to scan
            services: List of services to discover
            billing_first: Use billing data to identify active services first

        Returns:
            List of discovered StandardResource objects
        """
        if regions is None:
            regions = self._get_available_regions()

        discovered_resources = []
        active_services = set()

        # Step 1: Billing-first discovery (if ReadOnlyAccess available)
        if billing_first and self.has_readonly_access:
            self.logger.info("Starting billing-first service discovery")
            try:
                active_services = self._discover_active_services_from_billing()
                self.logger.info(
                    f"Found {len(active_services)} active services from billing data"
                )
            except Exception as e:
                self.logger.warning(
                    f"Billing discovery failed, falling back to service list: {e}"
                )

        # Step 2: Determine services to scan
        if services is None:
            if active_services:
                services = list(active_services)
            else:
                # Fallback to priority services
                services = ["ec2", "s3", "rds", "lambda", "cloudfront", "iam"]

        self.logger.info(f"Discovering resources for services: {services}")

        # Step 3: Enhanced resource discovery
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}

            for service_name in services:
                # Handle global services
                if service_name in self.global_services:
                    service_regions = [self.global_services[service_name]]
                else:
                    service_regions = regions

                for region in service_regions:
                    future = executor.submit(
                        self._discover_service_resources_enhanced, service_name, region
                    )
                    futures[future] = (service_name, region)

            # Collect results
            for future in concurrent.futures.as_completed(futures):
                service_name, region = futures[future]
                try:
                    resources = future.result()
                    discovered_resources.extend(resources)
                    self.logger.debug(
                        f"Discovered {len(resources)} resources for {service_name} in {region}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to discover {service_name} in {region}: {e}"
                    )

        # Step 4: Post-process and enhance
        self._post_process_resources(discovered_resources)

        self.logger.info(f"Total discovered resources: {len(discovered_resources)}")
        return discovered_resources

    def _discover_active_services_from_billing(self) -> Set[str]:
        """Discover active services from Cost Explorer billing data."""
        try:
            ce_client = self.session.client("ce", region_name="us-east-1")

            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity="MONTHLY",
                Metrics=["BlendedCost", "UsageQuantity"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )

            active_services = set()
            service_mappings = self._get_billing_service_mappings()

            for result in response.get("ResultsByTime", []):
                for group in result.get("Groups", []):
                    service_name = group.get("Keys", [""])[0]
                    metrics = group.get("Metrics", {})

                    # Check if service has usage or cost
                    cost = float(metrics.get("BlendedCost", {}).get("Amount", "0"))
                    usage = float(metrics.get("UsageQuantity", {}).get("Amount", "0"))

                    if cost > 0.01 or usage > 0:  # Active service threshold
                        aws_service = service_mappings.get(
                            service_name, service_name.lower()
                        )
                        active_services.add(aws_service)

            return active_services

        except Exception as e:
            self.logger.error(f"Failed to discover services from billing: {e}")
            return set()

    def _discover_service_resources_enhanced(
        self, service_name: str, region: str
    ) -> List[StandardResource]:
        """Enhanced service resource discovery with ReadOnlyAccess capabilities."""
        resources = []

        try:
            # Get service pattern configuration
            if service_name in self.enhanced_service_patterns:
                pattern = self.enhanced_service_patterns[service_name]
            else:
                # Fallback to basic discovery
                return self._discover_service_resources_basic(service_name, region)

            client = self.session.client(service_name, region_name=region)

            # Step 1: Basic resource discovery
            for operation in pattern.get("operations", []):
                try:
                    resources.extend(
                        self._execute_discovery_operation(
                            client, operation, service_name, region, pattern
                        )
                    )
                except Exception as e:
                    self.logger.debug(
                        f"Operation {operation} failed for {service_name}: {e}"
                    )

            # Step 2: Enhanced attribute extraction (ReadOnlyAccess only)
            if self.has_readonly_access and pattern.get("readonly_operations"):
                for resource in resources:
                    self._enhance_resource_attributes(
                        client,
                        resource,
                        pattern.get("readonly_operations", []),
                        pattern.get("enhanced_attributes", []),
                    )

        except Exception as e:
            self.logger.error(
                f"Failed to discover {service_name} resources in {region}: {e}"
            )

        return resources

    def _enhance_resource_attributes(
        self,
        client,
        resource: StandardResource,
        readonly_operations: List[str],
        enhanced_attributes: List[str],
    ) -> None:
        """Enhance resource with additional attributes using ReadOnlyAccess operations."""
        if not self.has_readonly_access:
            return

        for operation in readonly_operations:
            try:
                # Execute readonly operation based on resource type
                if resource.service_name == "s3" and operation == "GetBucketEncryption":
                    response = client.get_bucket_encryption(
                        Bucket=resource.resource_name
                    )
                    resource.raw_data["encryption_config"] = response
                    resource.encrypted = True

                elif (
                    resource.service_name == "kms"
                    and operation == "GetKeyRotationStatus"
                ):
                    response = client.get_key_rotation_status(
                        KeyId=resource.resource_id
                    )
                    resource.raw_data["rotation_enabled"] = response.get(
                        "KeyRotationEnabled", False
                    )

                elif (
                    resource.service_name == "rds"
                    and operation == "DescribeDBParameterGroups"
                ):
                    # Add parameter group information
                    if hasattr(resource, "raw_data") and "DBParameterGroupName" in str(
                        resource.raw_data
                    ):
                        param_group_name = self._extract_parameter_group_name(
                            resource.raw_data
                        )
                        if param_group_name:
                            response = client.describe_db_parameter_groups(
                                DBParameterGroupName=param_group_name
                            )
                            resource.raw_data["parameter_group_details"] = response

                # Add more service-specific enhancements as needed

            except Exception as e:
                self.logger.debug(
                    f"Failed to enhance {resource.resource_id} with {operation}: {e}"
                )

    def _get_billing_service_mappings(self) -> Dict[str, str]:
        """Map billing service names to AWS service codes."""
        return {
            "Amazon Elastic Compute Cloud - Compute": "ec2",
            "Amazon Simple Storage Service": "s3",
            "Amazon Relational Database Service": "rds",
            "AWS Lambda": "lambda",
            "Amazon CloudFront": "cloudfront",
            "AWS Identity and Access Management": "iam",
            "Amazon CloudWatch": "cloudwatch",
            "Amazon Route 53": "route53",
            "AWS Key Management Service": "kms",
            "Amazon Virtual Private Cloud": "ec2",
            "Elastic Load Balancing": "elasticloadbalancing",
            "Amazon Elastic Container Service": "ecs",
            "Amazon Elastic Kubernetes Service": "eks",
            "AWS Systems Manager": "ssm",
            "Amazon Simple Notification Service": "sns",
            "Amazon Simple Queue Service": "sqs",
            "Amazon DynamoDB": "dynamodb",
            "Amazon ElastiCache": "elasticache",
            "Amazon Elasticsearch Service": "elasticsearch",
            "AWS Certificate Manager": "acm",
            "AWS Secrets Manager": "secretsmanager",
            "Amazon API Gateway": "apigateway",
            "AWS Step Functions": "stepfunctions",
            "Amazon Kinesis": "kinesis",
            "Amazon Redshift": "redshift",
            "Amazon Aurora": "rds",
            "AWS Glue": "glue",
            "Amazon SageMaker": "sagemaker",
            "AWS Batch": "batch",
            "Amazon ECS": "ecs",
            "Amazon EKS": "eks",
        }

    def _post_process_resources(self, resources: List[StandardResource]) -> None:
        """Post-process discovered resources for consistency and enhancement."""
        # S3 bucket region detection and ARN correction
        s3_resources = [r for r in resources if r.service_name == "s3"]
        if s3_resources:
            self._fix_s3_bucket_regions(s3_resources)

        # Add cross-service relationships
        self._add_resource_relationships(resources)

        # Normalize tags and extract common fields
        for resource in resources:
            self._normalize_resource_tags(resource)

    def _add_resource_relationships(self, resources: List[StandardResource]) -> None:
        """Add cross-service relationships between resources."""
        # Simple relationship mapping - can be enhanced
        for resource in resources:
            if resource.vpc_id:
                # Find related VPC resources
                vpc_resources = [
                    r for r in resources if r.resource_id == resource.vpc_id
                ]
                if vpc_resources:
                    resource.parent_resource = vpc_resources[0].resource_arn

            if resource.subnet_ids:
                # Find related subnet resources
                subnet_resources = [
                    r for r in resources if r.resource_id in resource.subnet_ids
                ]
                resource.child_resources.extend(
                    [r.resource_arn for r in subnet_resources if r.resource_arn]
                )

    def _normalize_resource_tags(self, resource: StandardResource) -> None:
        """Normalize resource tags and extract common fields."""
        if resource.tags:
            # Extract common tag-based fields
            resource.name_from_tags = resource.tags.get("Name")
            resource.environment = resource.tags.get(
                "Environment"
            ) or resource.tags.get("Env")
            resource.project = resource.tags.get("Project") or resource.tags.get(
                "Application"
            )
            resource.cost_center = resource.tags.get("CostCenter") or resource.tags.get(
                "Cost-Center"
            )

    def _fix_s3_bucket_regions(self, s3_resources: List[StandardResource]) -> None:
        """Fix S3 bucket regions and ARNs using GetBucketLocation."""
        if not self.has_readonly_access:
            return

        try:
            s3_client = self.session.client("s3", region_name="us-east-1")

            for resource in s3_resources:
                if resource.resource_type == "Bucket":
                    try:
                        response = s3_client.get_bucket_location(
                            Bucket=resource.resource_name
                        )
                        bucket_region = response.get("LocationConstraint")

                        # Handle us-east-1 special case
                        if bucket_region is None or bucket_region == "":
                            bucket_region = "us-east-1"

                        resource.region = bucket_region
                        # Correct ARN with actual region
                        resource.resource_arn = f"arn:aws:s3:::{resource.resource_name}"

                    except Exception as e:
                        self.logger.debug(
                            f"Failed to get location for bucket {resource.resource_name}: {e}"
                        )

        except Exception as e:
            self.logger.error(f"Failed to fix S3 bucket regions: {e}")

    def get_permission_requirements(self) -> Dict[str, List[str]]:
        """Return IAM permission requirements for different access levels."""
        return {
            "minimal": [
                "resourcegroupstaggingapi:GetResources",
                "ce:GetCostAndUsage",
                "ce:GetUsageReport",
                "pricing:GetProducts",
            ],
            "readonly": ["ReadOnlyAccess"],  # AWS managed policy
            "specific_readonly": [
                # Core discovery permissions
                "resourcegroupstaggingapi:GetResources",
                "ce:GetCostAndUsage",
                # Service-specific read permissions
                "ec2:Describe*",
                "s3:List*",
                "s3:Get*",
                "rds:Describe*",
                "lambda:List*",
                "lambda:Get*",
                "iam:List*",
                "iam:Get*",
                "cloudfront:List*",
                "cloudfront:Get*",
                "route53:List*",
                "route53:Get*",
                "kms:List*",
                "kms:Describe*",
                "kms:Get*",
                "cloudwatch:List*",
                "cloudwatch:Describe*",
                "elasticloadbalancing:Describe*",
            ],
        }
