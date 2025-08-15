#!/usr/bin/env python3
"""
Optimized Dynamic Discovery System

High-performance implementation with:
- Parallel processing across services and regions
- Smart caching to avoid redundant API calls
- Early termination when resources found
- Global service optimization
- Intelligent operation prioritization
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


@dataclass
class DiscoveryResult:
    """Results from dynamic discovery operation."""

    service_name: str
    region: str
    resources_found: int
    operations_tried: int
    execution_time: float
    success: bool
    error_message: Optional[str] = None


class OptimizedDynamicDiscovery:
    """High-performance dynamic discovery with parallel processing and caching."""

    def __init__(self, session: boto3.Session = None, max_workers: int = 20):
        self.session = session or boto3.Session()
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers

        # Performance caches
        self._client_cache = {}
        self._operation_cache = {}
        self._successful_operations = {}
        self._failed_services = set()

        # Thread safety
        self._cache_lock = threading.Lock()
        self._results_lock = threading.Lock()

        # Global services that should only be called from us-east-1
        self.global_services = {
            "cloudfront",
            "iam",
            "route53",
            "wa",
            "wafv2",
            "shield",
            "globalaccelerator",
            "organizations",
        }

        # Service priority based on common usage
        self.service_priority = {
            "s3": 1,
            "ec2": 2,
            "rds": 3,
            "lambda": 4,
            "cloudwatch": 5,
            "iam": 6,
            "cloudfront": 7,
            "route53": 8,
            "sns": 9,
            "sqs": 10,
        }

        # Most effective operations per service (from experience)
        self.known_effective_operations = {
            "ec2": ["DescribeInstances", "DescribeVolumes", "DescribeVpcs"],
            "s3": ["ListBuckets"],
            "rds": ["DescribeDBInstances", "DescribeDBClusters"],
            "lambda": ["ListFunctions"],
            "cloudwatch": ["DescribeAlarms"],
            "iam": ["ListRoles", "ListUsers", "ListPolicies"],
            "cloudfront": ["ListDistributions"],
            "route53": ["ListHostedZones"],
            "sns": ["ListTopics"],
            "sqs": ["ListQueues"],
            "dynamodb": ["ListTables"],
            "kms": ["ListKeys"],
            "ecs": ["ListClusters"],
            "eks": ["ListClusters"],
            "elasticloadbalancing": ["DescribeLoadBalancers"],
            "elbv2": ["DescribeLoadBalancers"],
            "apigateway": ["GetRestApis"],
            "kinesis": ["ListStreams"],
            "glue": ["GetDatabases", "GetCrawlers"],
            "batch": ["DescribeJobQueues"],
            "stepfunctions": ["ListStateMachines"],
            "ssm": ["DescribeParameters"],
            "secretsmanager": ["ListSecrets"],
            "acm": ["ListCertificates"],
        }

    def discover_services_parallel(
        self,
        services: List[str],
        regions: List[str],
        max_resources_per_service: int = 50,
    ) -> Dict[str, Any]:
        """
        High-performance parallel discovery across services and regions.

        Args:
            services: List of service names to discover
            regions: List of regions to search
            max_resources_per_service: Stop after finding this many resources per service

        Returns:
            Dictionary with discovery results and performance metrics
        """
        start_time = time.time()

        # Optimize service and region combinations
        discovery_tasks = self._optimize_discovery_tasks(services, regions)

        self.logger.info(
            f"Starting optimized discovery for {len(discovery_tasks)} tasks "
            f"using {self.max_workers} parallel workers"
        )

        results = []
        resources_discovered = []

        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for task in discovery_tasks:
                future = executor.submit(
                    self._discover_service_optimized,
                    task["service"],
                    task["region"],
                    task["priority"],
                    max_resources_per_service,
                )
                future_to_task[future] = task

            # Process completed futures
            for future in as_completed(future_to_task, timeout=300):  # 5 minute timeout
                task = future_to_task[future]
                try:
                    result = future.result(timeout=30)  # 30 second per-service timeout
                    results.append(result)

                    # Add discovered resources
                    if result.success and hasattr(result, "resources"):
                        resources_discovered.extend(result.resources)

                    # Early termination if we've found enough resources
                    if len(resources_discovered) > 1000:  # Reasonable limit
                        self.logger.info(
                            "Early termination - found sufficient resources"
                        )
                        break

                except Exception as e:
                    self.logger.warning(
                        f"Task failed for {task['service']}-{task['region']}: {e}"
                    )
                    results.append(
                        DiscoveryResult(
                            service_name=task["service"],
                            region=task["region"],
                            resources_found=0,
                            operations_tried=0,
                            execution_time=0,
                            success=False,
                            error_message=str(e),
                        )
                    )

        # Calculate performance metrics
        total_time = time.time() - start_time
        successful_discoveries = [r for r in results if r.success]
        total_resources = sum(r.resources_found for r in successful_discoveries)

        performance_metrics = {
            "total_execution_time": total_time,
            "tasks_completed": len(results),
            "successful_discoveries": len(successful_discoveries),
            "total_resources_found": total_resources,
            "average_time_per_task": total_time / len(results) if results else 0,
            "resources_per_second": (
                total_resources / total_time if total_time > 0 else 0
            ),
            "parallel_efficiency": (
                len(results) / (total_time * self.max_workers) if total_time > 0 else 0
            ),
        }

        return {
            "resources": resources_discovered,
            "results": results,
            "performance": performance_metrics,
            "cache_stats": self._get_cache_stats(),
        }

    def _optimize_discovery_tasks(
        self, services: List[str], regions: List[str]
    ) -> List[Dict[str, Any]]:
        """Optimize the order and combination of discovery tasks."""
        tasks = []

        for service in services:
            # Skip if we know this service consistently fails
            if service in self._failed_services:
                continue

            # Handle global services (only use us-east-1)
            if service in self.global_services:
                if "us-east-1" in regions:
                    tasks.append(
                        {
                            "service": service,
                            "region": "us-east-1",
                            "priority": self.service_priority.get(service, 100),
                        }
                    )
            else:
                # Regional services - try all regions
                for region in regions:
                    tasks.append(
                        {
                            "service": service,
                            "region": region,
                            "priority": self.service_priority.get(service, 100),
                        }
                    )

        # Sort by priority (lower number = higher priority)
        tasks.sort(key=lambda x: x["priority"])

        return tasks

    def _discover_service_optimized(
        self, service_name: str, region: str, priority: int, max_resources: int
    ) -> DiscoveryResult:
        """Optimized service discovery with caching and smart operation selection."""
        start_time = time.time()
        resources_found = []
        operations_tried = 0

        try:
            # Get cached client or create new one
            client = self._get_cached_client(service_name, region)
            if not client:
                return DiscoveryResult(
                    service_name=service_name,
                    region=region,
                    resources_found=0,
                    operations_tried=0,
                    execution_time=time.time() - start_time,
                    success=False,
                    error_message="Failed to create client",
                )

            # Get optimized operations for this service
            operations = self._get_optimized_operations(client, service_name)

            # Try operations in priority order
            for operation_name in operations:
                if len(resources_found) >= max_resources:
                    break  # Early termination

                try:
                    operation_resources = self._execute_operation_cached(
                        client, operation_name, service_name, region
                    )
                    resources_found.extend(operation_resources)
                    operations_tried += 1

                    # If we found resources, record this as a successful operation
                    if operation_resources:
                        self._record_successful_operation(service_name, operation_name)

                except Exception as e:
                    self.logger.debug(
                        f"Operation {operation_name} failed for {service_name}: {e}"
                    )
                    continue

            execution_time = time.time() - start_time
            result = DiscoveryResult(
                service_name=service_name,
                region=region,
                resources_found=len(resources_found),
                operations_tried=operations_tried,
                execution_time=execution_time,
                success=True,
            )
            result.resources = resources_found  # Attach resources for collection

            return result

        except Exception as e:
            # Record failed service to avoid future attempts
            with self._cache_lock:
                self._failed_services.add(service_name)

            return DiscoveryResult(
                service_name=service_name,
                region=region,
                resources_found=0,
                operations_tried=operations_tried,
                execution_time=time.time() - start_time,
                success=False,
                error_message=str(e),
            )

    def _get_cached_client(self, service_name: str, region: str):
        """Get cached AWS service client or create new one."""
        cache_key = f"{service_name}:{region}"

        with self._cache_lock:
            if cache_key in self._client_cache:
                return self._client_cache[cache_key]

        try:
            # Map service name to client name
            client_name = self._get_client_name(service_name)
            client = self.session.client(client_name, region_name=region)

            with self._cache_lock:
                self._client_cache[cache_key] = client

            return client

        except Exception as e:
            self.logger.debug(f"Failed to create client for {service_name}: {e}")
            return None

    def _get_optimized_operations(self, client, service_name: str) -> List[str]:
        """Get optimized list of operations to try for a service."""
        cache_key = service_name

        with self._cache_lock:
            if cache_key in self._operation_cache:
                return self._operation_cache[cache_key]

        # Start with known effective operations if available
        if service_name in self.known_effective_operations:
            operations = self.known_effective_operations[service_name].copy()
        else:
            # Fall back to discovering operations
            operations = []

        # Add any previously successful operations for this service
        if service_name in self._successful_operations:
            for op in self._successful_operations[service_name]:
                if op not in operations:
                    operations.append(op)

        # If no known operations, discover them
        if not operations:
            try:
                available_operations = client._service_model.operation_names

                # Prioritize List and Describe operations
                list_ops = [op for op in available_operations if op.startswith("List")]
                describe_ops = [
                    op for op in available_operations if op.startswith("Describe")
                ]

                # Combine and limit to most promising operations
                operations = (list_ops[:3] + describe_ops[:3])[:5]

            except Exception as e:
                self.logger.debug(f"Failed to get operations for {service_name}: {e}")
                operations = []

        # Cache the operations list
        with self._cache_lock:
            self._operation_cache[cache_key] = operations

        return operations

    def _execute_operation_cached(
        self, client, operation_name: str, service_name: str, region: str
    ) -> List[Dict]:
        """Execute AWS operation with intelligent result processing."""
        try:
            # Get the operation
            operation = getattr(client, self._snake_case(operation_name))

            # Handle paginated operations
            if hasattr(client, "get_paginator"):
                try:
                    paginator = client.get_paginator(self._snake_case(operation_name))
                    resources = []

                    page_count = 0
                    for page in paginator.paginate():
                        page_count += 1
                        resources.extend(
                            self._extract_resources_from_response(
                                page, service_name, region, operation_name
                            )
                        )

                        # Limit pages to avoid excessive API calls
                        if page_count >= 5:
                            break

                    return resources

                except Exception:
                    # Fall back to direct operation call
                    pass

            # Direct operation call
            response = operation()
            return self._extract_resources_from_response(
                response, service_name, region, operation_name
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ["AccessDenied", "UnauthorizedOperation"]:
                # Expected for some operations, don't log as error
                pass
            else:
                self.logger.debug(f"Client error in {operation_name}: {e}")
            return []

        except Exception as e:
            self.logger.debug(f"Operation error in {operation_name}: {e}")
            return []

    def _extract_resources_from_response(
        self, response: Dict, service_name: str, region: str, operation_name: str
    ) -> List[Dict]:
        """Extract resource information from AWS API response."""
        resources = []

        # Common response keys that contain resource lists
        resource_keys = [
            # Generic
            "Resources",
            "Items",
            "Results",
            "Data",
            # Service-specific
            "Reservations",
            "Instances",
            "Volumes",
            "Snapshots",
            "Buckets",
            "Tables",
            "Functions",
            "Distributions",
            "HostedZones",
            "Topics",
            "Queues",
            "Clusters",
            "Services",
            "Tasks",
            "Roles",
            "Users",
            "Policies",
            "Alarms",
            "Rules",
            "Keys",
            "Certificates",
            "Stacks",
        ]

        for key in resource_keys:
            if key in response:
                items = response[key]
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            # Special handling for EC2 reservations
                            if key == "Reservations" and "Instances" in item:
                                for instance in item["Instances"]:
                                    resources.append(
                                        self._normalize_resource(
                                            instance,
                                            service_name,
                                            region,
                                            operation_name,
                                        )
                                    )
                            else:
                                resources.append(
                                    self._normalize_resource(
                                        item, service_name, region, operation_name
                                    )
                                )
                elif isinstance(items, dict):
                    resources.append(
                        self._normalize_resource(
                            items, service_name, region, operation_name
                        )
                    )

                # If we found resources in this key, we're done
                if resources:
                    break

        return resources[:50]  # Limit resources per operation

    def _normalize_resource(
        self, resource_data: Dict, service_name: str, region: str, operation_name: str
    ) -> Dict:
        """Normalize resource data to standard format."""
        return {
            "service": service_name.upper(),
            "region": region,
            "resource_id": self._extract_resource_id(resource_data),
            "resource_name": self._extract_resource_name(resource_data),
            "resource_type": self._infer_resource_type(resource_data, operation_name),
            "tags": self._extract_tags(resource_data),
            "discovery_method": f"DynamicDiscovery:{operation_name}",
            "raw_data": resource_data,
        }

    def _extract_resource_id(self, resource_data: Dict) -> Optional[str]:
        """Extract resource ID from resource data."""
        id_fields = [
            "Id",
            "ResourceId",
            "Arn",
            "ARN",
            "Name",
            "InstanceId",
            "VolumeId",
            "SnapshotId",
            "BucketName",
            "TableName",
            "FunctionName",
            "DistributionId",
            "HostedZoneId",
            "TopicArn",
            "QueueUrl",
            "ClusterName",
        ]

        for field in id_fields:
            if field in resource_data and resource_data[field]:
                return str(resource_data[field])

        return str(resource_data.get("id", ""))

    def _extract_resource_name(self, resource_data: Dict) -> Optional[str]:
        """Extract resource name from resource data."""
        name_fields = ["Name", "ResourceName", "DisplayName", "Title"]

        for field in name_fields:
            if field in resource_data and resource_data[field]:
                return str(resource_data[field])

        # Check tags for Name
        tags = resource_data.get("Tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, dict) and tag.get("Key") == "Name":
                    return str(tag.get("Value", ""))

        return None

    def _extract_tags(self, resource_data: Dict) -> Dict[str, str]:
        """Extract tags from resource data."""
        tags = {}

        if "Tags" in resource_data:
            tag_data = resource_data["Tags"]
            if isinstance(tag_data, list):
                for tag in tag_data:
                    if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                        tags[tag["Key"]] = tag["Value"]
            elif isinstance(tag_data, dict):
                tags.update(tag_data)

        return tags

    def _infer_resource_type(self, resource_data: Dict, operation_name: str) -> str:
        """Infer resource type from operation and data."""
        # Map operation names to resource types
        operation_mapping = {
            "DescribeInstances": "Instance",
            "DescribeVolumes": "Volume",
            "ListBuckets": "Bucket",
            "ListFunctions": "Function",
            "DescribeAlarms": "Alarm",
            "ListTopics": "Topic",
            "ListQueues": "Queue",
            "ListDistributions": "Distribution",
            "ListHostedZones": "HostedZone",
        }

        return operation_mapping.get(operation_name, "Resource")

    def _record_successful_operation(self, service_name: str, operation_name: str):
        """Record successful operation for future optimization."""
        with self._cache_lock:
            if service_name not in self._successful_operations:
                self._successful_operations[service_name] = []
            if operation_name not in self._successful_operations[service_name]:
                self._successful_operations[service_name].append(operation_name)

    def _get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics for performance monitoring."""
        with self._cache_lock:
            return {
                "client_cache_size": len(self._client_cache),
                "operation_cache_size": len(self._operation_cache),
                "successful_operations": sum(
                    len(ops) for ops in self._successful_operations.values()
                ),
                "failed_services": len(self._failed_services),
            }

    @staticmethod
    def _snake_case(camel_case: str) -> str:
        """Convert CamelCase to snake_case."""
        import re

        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", camel_case).lower()

    @staticmethod
    def _get_client_name(service_name: str) -> str:
        """Map service name to AWS client name."""
        service_mappings = {
            "amazoncloudwatch": "cloudwatch",
            "amazonroute53": "route53",
            "amazons3": "s3",
            "amazonec2": "ec2",
            "amazonrds": "rds",
            "awslambda": "lambda",
            "keymanagementservice": "kms",
            "elasticloadbalancing": "elbv2",
            "amazonworkmail": "workmail",
        }

        # Try direct mapping first
        normalized = service_name.lower().replace(" ", "").replace("-", "")
        if normalized in service_mappings:
            return service_mappings[normalized]

        # For most services, the service name is the client name
        return service_name.lower()
