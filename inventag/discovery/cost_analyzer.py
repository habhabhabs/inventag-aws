#!/usr/bin/env python3
"""
Cost Analyzer - Resource Cost Estimation and Optimization

Provides cost analysis capabilities for AWS resources using the AWS Pricing API.
Identifies expensive resources, forgotten resources, and provides cost optimization recommendations.
"""

import logging
import boto3
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


@dataclass
class CostThresholds:
    """Configuration for cost analysis thresholds."""

    expensive_resource_monthly_threshold: Decimal = Decimal("100.00")
    forgotten_resource_days_threshold: int = 30
    high_cost_alert_threshold: Decimal = Decimal("1000.00")
    cost_trend_alert_percentage: float = 50.0
    unused_resource_utilization_threshold: float = 5.0


@dataclass
class ResourceCostEstimate:
    """Cost estimate for a single resource."""

    resource_id: str
    resource_type: str
    service: str
    region: str
    estimated_monthly_cost: Decimal
    cost_breakdown: Dict[str, Decimal] = field(default_factory=dict)
    pricing_model: str = "on-demand"
    cost_factors: Dict[str, Any] = field(default_factory=dict)
    confidence_level: str = "medium"
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ForgottenResourceAnalysis:
    """Analysis of potentially forgotten resources."""

    resource_id: str
    resource_type: str
    service: str
    days_since_last_activity: int
    estimated_monthly_cost: Decimal
    activity_indicators: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"
    recommendations: List[str] = field(default_factory=list)


@dataclass
class CostOptimizationRecommendation:
    """Cost optimization recommendation."""

    resource_id: str
    resource_type: str
    service: str
    recommendation_type: str
    current_monthly_cost: Decimal
    potential_monthly_savings: Decimal
    confidence_level: str
    implementation_effort: str
    description: str
    action_items: List[str] = field(default_factory=list)


@dataclass
class CostTrendAnalysis:
    """Cost trend analysis over time."""

    resource_id: str
    service: str
    current_monthly_cost: Decimal
    previous_monthly_cost: Decimal
    cost_change_percentage: float
    trend_direction: str
    alert_triggered: bool = False
    historical_costs: List[Tuple[datetime, Decimal]] = field(default_factory=list)


@dataclass
class CostAnalysisSummary:
    """Summary of cost analysis results."""

    total_estimated_monthly_cost: Decimal
    expensive_resources_count: int
    forgotten_resources_count: int
    total_potential_savings: Decimal
    high_risk_resources: List[str] = field(default_factory=list)
    cost_by_service: Dict[str, Decimal] = field(default_factory=dict)
    cost_by_region: Dict[str, Decimal] = field(default_factory=dict)
    optimization_opportunities: int = 0
    analysis_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class CostAnalyzer:
    """
    Resource cost estimation and optimization analyzer.

    Provides comprehensive cost analysis capabilities including:
    - Resource cost estimation using AWS Pricing API
    - Expensive resource identification with configurable thresholds
    - Forgotten resource detection based on activity patterns
    - Cost trend analysis and alerting functionality
    - Cost optimization recommendations based on resource utilization
    """

    def __init__(
        self,
        session: Optional[boto3.Session] = None,
        thresholds: Optional[CostThresholds] = None,
    ):
        """Initialize the cost analyzer."""
        self.session = session or boto3.Session()
        self.thresholds = thresholds or CostThresholds()
        self.logger = logging.getLogger(f"{__name__}.CostAnalyzer")

        # Initialize AWS clients
        self._initialize_clients()

        # Caching for pricing data
        self._pricing_cache: Dict[str, Any] = {}
        self._cache_lock = threading.Lock()

        # Historical cost data storage
        self._historical_costs: Dict[str, List[Tuple[datetime, Decimal]]] = defaultdict(
            list
        )

    def _initialize_clients(self):
        """Initialize AWS service clients."""
        # Initialize clients as None - will create lazily when needed
        self.pricing_client = None
        self.cloudwatch_client = None
        self.cost_explorer_client = None

        self.logger.info("Cost analyzer initialized with lazy client loading")

    def _get_pricing_client(self):
        """Lazily create and return pricing client."""
        if self.pricing_client is None:
            try:
                self.pricing_client = boto3.client("pricing", region_name="us-east-1")
                self.logger.debug("Created pricing client")
            except Exception as e:
                self.logger.warning(f"Failed to create pricing client: {e}")
                raise
        return self.pricing_client

    def _get_cloudwatch_client(self):
        """Lazily create and return CloudWatch client."""
        if self.cloudwatch_client is None:
            try:
                self.cloudwatch_client = self.session.client("cloudwatch")
                self.logger.debug("Created CloudWatch client")
            except Exception as e:
                self.logger.warning(f"Failed to create CloudWatch client: {e}")
                raise
        return self.cloudwatch_client

    def _get_cost_explorer_client(self):
        """Lazily create and return Cost Explorer client."""
        if self.cost_explorer_client is None:
            try:
                self.cost_explorer_client = self.session.client("ce")
                self.logger.debug("Created Cost Explorer client")
            except Exception as e:
                self.logger.warning(f"Failed to create Cost Explorer client: {e}")
                self.cost_explorer_client = False  # Mark as failed to avoid retry
                raise
        return (
            self.cost_explorer_client
            if self.cost_explorer_client is not False
            else None
        )

    def estimate_resource_costs(
        self, resources: List[Dict[str, Any]]
    ) -> List[ResourceCostEstimate]:
        """
        Estimate costs for a list of resources using AWS Pricing API.

        Args:
            resources: List of resource dictionaries

        Returns:
            List of ResourceCostEstimate objects
        """
        self.logger.info(f"Estimating costs for {len(resources)} resources")

        cost_estimates = []

        # Process resources in parallel for better performance
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_resource = {
                executor.submit(self._estimate_single_resource_cost, resource): resource
                for resource in resources
            }

            for future in as_completed(future_to_resource):
                try:
                    cost_estimate = future.result()
                    if cost_estimate:
                        cost_estimates.append(cost_estimate)
                except Exception as e:
                    resource = future_to_resource[future]
                    self.logger.warning(
                        f"Cost estimation failed for resource {resource.get('id', 'unknown')}: {e}"
                    )

        self.logger.info(
            f"Generated cost estimates for {len(cost_estimates)} resources"
        )
        return cost_estimates

    def _estimate_single_resource_cost(
        self, resource: Dict[str, Any]
    ) -> Optional[ResourceCostEstimate]:
        """Estimate cost for a single resource."""
        try:
            service = resource.get("service", "").upper()
            resource_type = resource.get("type", "")
            resource_id = resource.get("id", "")
            region = resource.get("region", "")

            if not all([service, resource_type, resource_id, region]):
                return None

            # Get pricing information
            pricing_info = self._get_pricing_info(
                service, resource_type, region, resource
            )

            if not pricing_info:
                return None

            # Calculate estimated monthly cost
            monthly_cost = self._calculate_monthly_cost(pricing_info, resource)

            # Create cost breakdown
            cost_breakdown = self._create_cost_breakdown(pricing_info, resource)

            # Determine confidence level
            confidence_level = self._determine_confidence_level(
                service, resource_type, pricing_info
            )

            return ResourceCostEstimate(
                resource_id=resource_id,
                resource_type=resource_type,
                service=service,
                region=region,
                estimated_monthly_cost=monthly_cost,
                cost_breakdown=cost_breakdown,
                pricing_model=pricing_info.get("pricing_model", "on-demand"),
                cost_factors=pricing_info.get("cost_factors", {}),
                confidence_level=confidence_level,
            )

        except Exception as e:
            self.logger.debug(
                f"Cost estimation failed for resource {resource.get('id', 'unknown')}: {e}"
            )
            return None

    def _get_pricing_info(
        self, service: str, resource_type: str, region: str, resource: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get pricing information from AWS Pricing API."""
        cache_key = f"{service}:{resource_type}:{region}"

        with self._cache_lock:
            if cache_key in self._pricing_cache:
                return self._pricing_cache[cache_key]

        try:
            # Map service names to pricing service codes
            service_code = self._map_service_to_pricing_code(service)
            if not service_code:
                return None

            # Build filters for pricing query
            filters = self._build_pricing_filters(
                service, resource_type, region, resource
            )

            # Query pricing API
            response = self._get_pricing_client().get_products(
                ServiceCode=service_code, Filters=filters, MaxResults=10
            )

            pricing_info = self._parse_pricing_response(
                response, service, resource_type
            )

            with self._cache_lock:
                self._pricing_cache[cache_key] = pricing_info

            return pricing_info

        except Exception as e:
            self.logger.debug(
                f"Pricing API query failed for {service}:{resource_type}: {e}"
            )
            return None

    def _map_service_to_pricing_code(self, service: str) -> Optional[str]:
        """Map AWS service names to pricing service codes."""
        service_mapping = {
            "EC2": "AmazonEC2",
            "S3": "AmazonS3",
            "RDS": "AmazonRDS",
            "LAMBDA": "AWSLambda",
            "ELB": "AWSELB",
            "ELBV2": "AWSELB",
            "CLOUDFRONT": "AmazonCloudFront",
            "ROUTE53": "AmazonRoute53",
            "VPC": "AmazonVPC",
            "ECS": "AmazonECS",
            "EKS": "AmazonEKS",
            "DYNAMODB": "AmazonDynamoDB",
            "ELASTICACHE": "AmazonElastiCache",
            "REDSHIFT": "AmazonRedshift",
            "GLUE": "AWSGlue",
            "SAGEMAKER": "AmazonSageMaker",
            "KINESIS": "AmazonKinesis",
            "SNS": "AmazonSNS",
            "SQS": "AmazonSQS",
        }
        return service_mapping.get(service.upper())

    def _build_pricing_filters(
        self, service: str, resource_type: str, region: str, resource: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build filters for pricing API query."""
        filters = [
            {
                "Type": "TERM_MATCH",
                "Field": "location",
                "Value": self._map_region_to_location(region),
            }
        ]

        # Add service-specific filters
        if service == "EC2":
            filters.extend(self._build_ec2_filters(resource_type, resource))
        elif service == "RDS":
            filters.extend(self._build_rds_filters(resource_type, resource))
        elif service == "S3":
            filters.extend(self._build_s3_filters(resource_type, resource))
        elif service == "LAMBDA":
            filters.extend(self._build_lambda_filters(resource_type, resource))

        return filters

    def _map_region_to_location(self, region: str) -> str:
        """Map AWS region codes to pricing location names."""
        region_mapping = {
            "us-east-1": "US East (N. Virginia)",
            "us-east-2": "US East (Ohio)",
            "us-west-1": "US West (N. California)",
            "us-west-2": "US West (Oregon)",
            "eu-west-1": "Europe (Ireland)",
            "eu-west-2": "Europe (London)",
            "eu-west-3": "Europe (Paris)",
            "eu-central-1": "Europe (Frankfurt)",
            "ap-southeast-1": "Asia Pacific (Singapore)",
            "ap-southeast-2": "Asia Pacific (Sydney)",
            "ap-northeast-1": "Asia Pacific (Tokyo)",
            "ap-northeast-2": "Asia Pacific (Seoul)",
            "ap-south-1": "Asia Pacific (Mumbai)",
            "ca-central-1": "Canada (Central)",
            "sa-east-1": "South America (Sao Paulo)",
        }
        return region_mapping.get(region, region)

    def _build_ec2_filters(
        self, resource_type: str, resource: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build EC2-specific pricing filters."""
        filters = []

        if resource_type == "Instance":
            # Get instance type from resource attributes
            instance_type = resource.get("instance_type", "t3.micro")
            filters.append(
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type}
            )
            filters.append(
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"}
            )
            filters.append(
                {"Type": "TERM_MATCH", "Field": "operating-system", "Value": "Linux"}
            )
        elif resource_type == "Volume":
            volume_type = resource.get("volume_type", "gp3")
            filters.append(
                {"Type": "TERM_MATCH", "Field": "volumeType", "Value": volume_type}
            )

        return filters

    def _build_rds_filters(
        self, resource_type: str, resource: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build RDS-specific pricing filters."""
        filters = []

        if resource_type == "DBInstance":
            instance_class = resource.get("db_instance_class", "db.t3.micro")
            engine = resource.get("engine", "mysql")

            filters.extend(
                [
                    {
                        "Type": "TERM_MATCH",
                        "Field": "instanceType",
                        "Value": instance_class,
                    },
                    {"Type": "TERM_MATCH", "Field": "databaseEngine", "Value": engine},
                ]
            )

        return filters

    def _build_s3_filters(
        self, resource_type: str, resource: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build S3-specific pricing filters."""
        filters = []

        if resource_type == "Bucket":
            storage_class = resource.get("storage_class", "Standard")
            filters.append(
                {"Type": "TERM_MATCH", "Field": "storageClass", "Value": storage_class}
            )

        return filters

    def _build_lambda_filters(
        self, resource_type: str, resource: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build Lambda-specific pricing filters."""
        filters = []

        if resource_type == "Function":
            filters.append(
                {"Type": "TERM_MATCH", "Field": "group", "Value": "AWS-Lambda-Requests"}
            )

        return filters

    def _parse_pricing_response(
        self, response: Dict[str, Any], service: str, resource_type: str
    ) -> Optional[Dict[str, Any]]:
        """Parse pricing API response to extract relevant pricing information."""
        try:
            price_list = response.get("PriceList", [])
            if not price_list:
                return None

            # Take the first matching product
            product = json.loads(price_list[0])

            # Extract pricing terms
            on_demand_terms = product.get("terms", {}).get("OnDemand", {})
            if not on_demand_terms:
                return None

            # Get the first term
            term_key = list(on_demand_terms.keys())[0]
            term = on_demand_terms[term_key]

            # Get price dimensions
            price_dimensions = term.get("priceDimensions", {})
            if not price_dimensions:
                return None

            # Extract pricing information
            dimension_key = list(price_dimensions.keys())[0]
            dimension = price_dimensions[dimension_key]

            price_per_unit = dimension.get("pricePerUnit", {}).get("USD", "0")
            unit = dimension.get("unit", "Hrs")

            return {
                "price_per_unit": Decimal(price_per_unit),
                "unit": unit,
                "pricing_model": "on-demand",
                "cost_factors": {
                    "service": service,
                    "resource_type": resource_type,
                    "unit": unit,
                },
                "product_attributes": product.get("product", {}).get("attributes", {}),
            }

        except Exception as e:
            self.logger.debug(f"Failed to parse pricing response: {e}")
            return None

    def _calculate_monthly_cost(
        self, pricing_info: Dict[str, Any], resource: Dict[str, Any]
    ) -> Decimal:
        """Calculate estimated monthly cost based on pricing information."""
        try:
            price_per_unit = pricing_info.get("price_per_unit", Decimal("0"))
            unit = pricing_info.get("unit", "Hrs")

            # Calculate usage based on unit type
            if unit in ["Hrs", "Hour"]:
                # Assume 24/7 usage for compute resources
                monthly_usage = Decimal("730")  # Average hours per month
            elif unit in ["GB-Mo", "GB-Month"]:
                # For storage, get size from resource attributes
                size_gb = Decimal(str(resource.get("size_gb", 20)))
                monthly_usage = size_gb
            elif unit == "Requests":
                # Estimate requests based on resource type
                monthly_usage = self._estimate_monthly_requests(resource)
            else:
                # Default to 1 unit per month
                monthly_usage = Decimal("1")

            return price_per_unit * monthly_usage

        except Exception as e:
            self.logger.debug(f"Cost calculation failed: {e}")
            return Decimal("0")

    def _estimate_monthly_requests(self, resource: Dict[str, Any]) -> Decimal:
        """Estimate monthly requests for request-based pricing."""
        service = resource.get("service", "").upper()
        resource_type = resource.get("type", "")

        # Default estimates based on service type
        if service == "LAMBDA":
            return Decimal("100000")  # 100K requests per month
        elif service == "S3":
            return Decimal("10000")  # 10K requests per month
        else:
            return Decimal("1000")  # 1K requests per month

    def _create_cost_breakdown(
        self, pricing_info: Dict[str, Any], resource: Dict[str, Any]
    ) -> Dict[str, Decimal]:
        """Create detailed cost breakdown."""
        breakdown = {}

        service = resource.get("service", "").upper()
        price_per_unit = pricing_info.get("price_per_unit", Decimal("0"))
        unit = pricing_info.get("unit", "Hrs")

        if service == "EC2" and resource.get("type") == "Instance":
            breakdown["compute"] = price_per_unit * Decimal("730")
            # Add storage cost if available
            if "storage_gb" in resource:
                storage_cost = Decimal("0.10") * Decimal(str(resource["storage_gb"]))
                breakdown["storage"] = storage_cost
        elif service == "RDS":
            breakdown["database"] = price_per_unit * Decimal("730")
        elif service == "S3":
            breakdown["storage"] = price_per_unit * Decimal(
                str(resource.get("size_gb", 20))
            )
        else:
            breakdown["base_cost"] = price_per_unit

        return breakdown

    def _determine_confidence_level(
        self, service: str, resource_type: str, pricing_info: Dict[str, Any]
    ) -> str:
        """Determine confidence level of cost estimate."""
        # High confidence for well-supported services
        high_confidence_services = ["EC2", "RDS", "S3", "LAMBDA"]

        if service in high_confidence_services:
            return "high"
        elif pricing_info and pricing_info.get("price_per_unit", Decimal("0")) > 0:
            return "medium"
        else:
            return "low"

    def identify_expensive_resources(
        self, cost_estimates: List[ResourceCostEstimate]
    ) -> List[ResourceCostEstimate]:
        """
        Identify expensive resources based on configurable thresholds.

        Args:
            cost_estimates: List of resource cost estimates

        Returns:
            List of expensive resources
        """
        expensive_resources = []

        for estimate in cost_estimates:
            if (
                estimate.estimated_monthly_cost
                >= self.thresholds.expensive_resource_monthly_threshold
            ):
                expensive_resources.append(estimate)

        self.logger.info(f"Identified {len(expensive_resources)} expensive resources")
        return expensive_resources

    def detect_forgotten_resources(
        self, resources: List[Dict[str, Any]]
    ) -> List[ForgottenResourceAnalysis]:
        """
        Detect forgotten resources based on activity patterns and usage metrics.

        Args:
            resources: List of resource dictionaries

        Returns:
            List of ForgottenResourceAnalysis objects
        """
        self.logger.info(
            f"Analyzing {len(resources)} resources for forgotten resource detection"
        )

        forgotten_resources = []

        for resource in resources:
            try:
                analysis = self._analyze_resource_activity(resource)
                if (
                    analysis
                    and analysis.days_since_last_activity
                    >= self.thresholds.forgotten_resource_days_threshold
                ):
                    forgotten_resources.append(analysis)
            except Exception as e:
                self.logger.debug(
                    f"Activity analysis failed for resource {resource.get('id', 'unknown')}: {e}"
                )

        self.logger.info(
            f"Detected {len(forgotten_resources)} potentially forgotten resources"
        )
        return forgotten_resources

    def _analyze_resource_activity(
        self, resource: Dict[str, Any]
    ) -> Optional[ForgottenResourceAnalysis]:
        """Analyze activity patterns for a single resource."""
        try:
            service = resource.get("service", "").upper()
            resource_type = resource.get("type", "")
            resource_id = resource.get("id", "")

            # Get activity metrics from CloudWatch
            activity_indicators = self._get_activity_metrics(
                service, resource_type, resource_id, resource
            )

            # Calculate days since last activity
            days_since_activity = self._calculate_days_since_activity(
                activity_indicators
            )

            if days_since_activity < self.thresholds.forgotten_resource_days_threshold:
                return None

            # Estimate cost for this resource
            estimated_cost = self._estimate_resource_cost_simple(resource)

            # Determine risk level
            risk_level = self._determine_forgotten_resource_risk(
                days_since_activity, estimated_cost
            )

            # Generate recommendations
            recommendations = self._generate_forgotten_resource_recommendations(
                service, resource_type, days_since_activity, estimated_cost
            )

            return ForgottenResourceAnalysis(
                resource_id=resource_id,
                resource_type=resource_type,
                service=service,
                days_since_last_activity=days_since_activity,
                estimated_monthly_cost=estimated_cost,
                activity_indicators=activity_indicators,
                risk_level=risk_level,
                recommendations=recommendations,
            )

        except Exception as e:
            self.logger.debug(f"Resource activity analysis failed: {e}")
            return None

    def _get_activity_metrics(
        self,
        service: str,
        resource_type: str,
        resource_id: str,
        resource: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get activity metrics from CloudWatch."""
        activity_indicators = {}
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(
            days=self.thresholds.forgotten_resource_days_threshold
        )

        try:
            if service == "EC2" and resource_type == "Instance":
                # Get CPU utilization
                cpu_metrics = self._get_cloudwatch_client().get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName="CPUUtilization",
                    Dimensions=[{"Name": "InstanceId", "Value": resource_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,  # Daily
                    Statistics=["Average", "Maximum"],
                )
                activity_indicators["cpu_utilization"] = cpu_metrics.get(
                    "Datapoints", []
                )

                # Get network activity
                network_metrics = self._get_cloudwatch_client().get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName="NetworkIn",
                    Dimensions=[{"Name": "InstanceId", "Value": resource_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=["Sum"],
                )
                activity_indicators["network_activity"] = network_metrics.get(
                    "Datapoints", []
                )

            elif service == "RDS" and resource_type == "DBInstance":
                # Get database connections
                connection_metrics = (
                    self._get_cloudwatch_client().get_metric_statistics(
                        Namespace="AWS/RDS",
                        MetricName="DatabaseConnections",
                        Dimensions=[
                            {"Name": "DBInstanceIdentifier", "Value": resource_id}
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=86400,
                        Statistics=["Average", "Maximum"],
                    )
                )
                activity_indicators["database_connections"] = connection_metrics.get(
                    "Datapoints", []
                )

            elif service == "S3" and resource_type == "Bucket":
                # Get request metrics (if enabled)
                try:
                    request_metrics = (
                        self._get_cloudwatch_client().get_metric_statistics(
                            Namespace="AWS/S3",
                            MetricName="AllRequests",
                            Dimensions=[{"Name": "BucketName", "Value": resource_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,
                            Statistics=["Sum"],
                        )
                    )
                    activity_indicators["s3_requests"] = request_metrics.get(
                        "Datapoints", []
                    )
                except Exception:
                    # S3 request metrics might not be enabled
                    activity_indicators["s3_requests"] = []

        except Exception as e:
            self.logger.debug(f"Failed to get activity metrics for {resource_id}: {e}")

        return activity_indicators

    def _calculate_days_since_activity(
        self, activity_indicators: Dict[str, Any]
    ) -> int:
        """Calculate days since last significant activity."""
        latest_activity = None

        for metric_name, datapoints in activity_indicators.items():
            if not datapoints:
                continue

            for datapoint in datapoints:
                timestamp = datapoint.get("Timestamp")
                value = datapoint.get(
                    "Average", datapoint.get("Sum", datapoint.get("Maximum", 0))
                )

                # Consider activity significant if value is above threshold
                if value > self._get_activity_threshold(metric_name):
                    if not latest_activity or timestamp > latest_activity:
                        latest_activity = timestamp

        if latest_activity:
            days_since = (
                datetime.now(timezone.utc)
                - latest_activity.replace(tzinfo=timezone.utc)
            ).days
            return max(0, days_since)
        else:
            # No activity found, assume maximum threshold
            return self.thresholds.forgotten_resource_days_threshold + 1

    def _get_activity_threshold(self, metric_name: str) -> float:
        """Get activity threshold for different metrics."""
        thresholds = {
            "cpu_utilization": 5.0,  # 5% CPU
            "network_activity": 1000000,  # 1MB network traffic
            "database_connections": 1,  # At least 1 connection
            "s3_requests": 10,  # At least 10 requests
        }
        return thresholds.get(metric_name, 0)

    def _estimate_resource_cost_simple(self, resource: Dict[str, Any]) -> Decimal:
        """Simple cost estimation for forgotten resource analysis."""
        service = resource.get("service", "").upper()
        resource_type = resource.get("type", "")

        # Simple cost estimates based on service type
        cost_estimates = {
            ("EC2", "Instance"): Decimal("50.00"),  # Average EC2 instance
            ("RDS", "DBInstance"): Decimal("100.00"),  # Average RDS instance
            ("S3", "Bucket"): Decimal("10.00"),  # Average S3 bucket
            ("ELB", "LoadBalancer"): Decimal("25.00"),  # Load balancer
            ("LAMBDA", "Function"): Decimal("5.00"),  # Lambda function
        }

        return cost_estimates.get((service, resource_type), Decimal("20.00"))

    def _determine_forgotten_resource_risk(
        self, days_since_activity: int, estimated_cost: Decimal
    ) -> str:
        """Determine risk level for forgotten resource."""
        if days_since_activity > 90 and estimated_cost > Decimal("100.00"):
            return "high"
        elif days_since_activity > 60 or estimated_cost > Decimal("50.00"):
            return "medium"
        else:
            return "low"

    def _generate_forgotten_resource_recommendations(
        self,
        service: str,
        resource_type: str,
        days_since_activity: int,
        estimated_cost: Decimal,
    ) -> List[str]:
        """Generate recommendations for forgotten resources."""
        recommendations = []

        if days_since_activity > 90:
            recommendations.append(
                "Consider terminating this resource as it has been inactive for over 90 days"
            )
        elif days_since_activity > 60:
            recommendations.append(
                "Review if this resource is still needed - inactive for over 60 days"
            )
        else:
            recommendations.append(
                "Monitor resource usage to confirm if it's still needed"
            )

        if estimated_cost > Decimal("100.00"):
            recommendations.append(
                "High cost resource - prioritize review and potential termination"
            )

        # Service-specific recommendations
        if service == "EC2":
            recommendations.append(
                "Consider stopping the instance if not needed, or downsizing if underutilized"
            )
        elif service == "RDS":
            recommendations.append(
                "Consider taking a final snapshot before terminating the database"
            )
        elif service == "S3":
            recommendations.append(
                "Review bucket contents and consider archiving to cheaper storage class"
            )

        return recommendations

    def analyze_cost_trends(
        self, resources: List[Dict[str, Any]]
    ) -> List[CostTrendAnalysis]:
        """
        Analyze cost trends and generate alerts for significant changes.

        Args:
            resources: List of resource dictionaries

        Returns:
            List of CostTrendAnalysis objects
        """
        self.logger.info(f"Analyzing cost trends for {len(resources)} resources")

        trend_analyses = []

        cost_client = self._get_cost_explorer_client()
        if not cost_client:
            self.logger.warning(
                "Cost Explorer client not available - skipping trend analysis"
            )
            return trend_analyses

        try:
            # Get cost data for the last two months
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

            # Group resources by service for cost analysis
            resources_by_service = defaultdict(list)
            for resource in resources:
                service = resource.get("service", "Unknown")
                resources_by_service[service].append(resource)

            for service, service_resources in resources_by_service.items():
                try:
                    trend_analysis = self._analyze_service_cost_trend(
                        service, service_resources, start_date, end_date
                    )
                    if trend_analysis:
                        trend_analyses.extend(trend_analysis)
                except Exception as e:
                    self.logger.debug(
                        f"Cost trend analysis failed for service {service}: {e}"
                    )

        except Exception as e:
            self.logger.error(f"Cost trend analysis failed: {e}")

        self.logger.info(f"Generated {len(trend_analyses)} cost trend analyses")
        return trend_analyses

    def _analyze_service_cost_trend(
        self,
        service: str,
        resources: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
    ) -> List[CostTrendAnalysis]:
        """Analyze cost trend for a specific service."""
        try:
            # Get cost and usage data from Cost Explorer
            cost_client = self._get_cost_explorer_client()
            if not cost_client:
                return []

            response = cost_client.get_cost_and_usage(
                TimePeriod={"Start": start_date, "End": end_date},
                Granularity="MONTHLY",
                Metrics=["BlendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )

            # Find cost data for this service
            service_costs = []
            for result in response.get("ResultsByTime", []):
                for group in result.get("Groups", []):
                    if service.lower() in group.get("Keys", [""])[0].lower():
                        cost = Decimal(
                            group.get("Metrics", {})
                            .get("BlendedCost", {})
                            .get("Amount", "0")
                        )
                        service_costs.append(cost)

            if len(service_costs) >= 2:
                current_cost = service_costs[-1]
                previous_cost = service_costs[-2]

                # Calculate trend
                if previous_cost > 0:
                    change_percentage = float(
                        (current_cost - previous_cost) / previous_cost * 100
                    )
                else:
                    change_percentage = 100.0 if current_cost > 0 else 0.0

                # Determine trend direction
                if abs(change_percentage) < 5:
                    trend_direction = "stable"
                elif change_percentage > 0:
                    trend_direction = "increasing"
                else:
                    trend_direction = "decreasing"

                # Check if alert should be triggered
                alert_triggered = (
                    abs(change_percentage) > self.thresholds.cost_trend_alert_percentage
                )

                # Create trend analysis for each resource in the service
                trend_analyses = []
                for resource in resources:
                    trend_analyses.append(
                        CostTrendAnalysis(
                            resource_id=resource.get("id", ""),
                            service=service,
                            current_monthly_cost=current_cost
                            / len(resources),  # Distribute cost across resources
                            previous_monthly_cost=previous_cost / len(resources),
                            cost_change_percentage=change_percentage,
                            trend_direction=trend_direction,
                            alert_triggered=alert_triggered,
                            historical_costs=[
                                (datetime.now(), current_cost),
                                (datetime.now() - timedelta(days=30), previous_cost),
                            ],
                        )
                    )

                return trend_analyses

        except Exception as e:
            self.logger.debug(f"Service cost trend analysis failed for {service}: {e}")

        return []

    def generate_cost_optimization_recommendations(
        self,
        cost_estimates: List[ResourceCostEstimate],
        forgotten_resources: List[ForgottenResourceAnalysis],
    ) -> List[CostOptimizationRecommendation]:
        """
        Generate cost optimization recommendations based on resource utilization.

        Args:
            cost_estimates: List of resource cost estimates
            forgotten_resources: List of forgotten resource analyses

        Returns:
            List of CostOptimizationRecommendation objects
        """
        self.logger.info("Generating cost optimization recommendations")

        recommendations = []

        # Recommendations for expensive resources
        expensive_resources = self.identify_expensive_resources(cost_estimates)
        for resource in expensive_resources:
            rec = self._generate_expensive_resource_recommendation(resource)
            if rec:
                recommendations.append(rec)

        # Recommendations for forgotten resources
        for forgotten in forgotten_resources:
            rec = self._generate_forgotten_resource_recommendation(forgotten)
            if rec:
                recommendations.append(rec)

        # Recommendations for underutilized resources
        underutilized_recommendations = self._generate_underutilization_recommendations(
            cost_estimates
        )
        recommendations.extend(underutilized_recommendations)

        self.logger.info(
            f"Generated {len(recommendations)} cost optimization recommendations"
        )
        return recommendations

    def _generate_expensive_resource_recommendation(
        self, resource: ResourceCostEstimate
    ) -> Optional[CostOptimizationRecommendation]:
        """Generate recommendation for expensive resources."""
        try:
            # Determine recommendation type based on service
            if resource.service == "EC2":
                recommendation_type = "rightsizing"
                description = "Consider rightsizing this EC2 instance to reduce costs"
                potential_savings = resource.estimated_monthly_cost * Decimal(
                    "0.3"
                )  # 30% potential savings
                action_items = [
                    "Analyze CPU and memory utilization over the past 30 days",
                    "Consider downsizing to a smaller instance type if underutilized",
                    "Evaluate Reserved Instance pricing for long-term workloads",
                ]
            elif resource.service == "RDS":
                recommendation_type = "rightsizing"
                description = "Consider optimizing this RDS instance configuration"
                potential_savings = resource.estimated_monthly_cost * Decimal(
                    "0.25"
                )  # 25% potential savings
                action_items = [
                    "Review database performance metrics",
                    "Consider using Aurora Serverless for variable workloads",
                    "Evaluate Reserved Instance pricing",
                ]
            else:
                recommendation_type = "review"
                description = f"Review this high-cost {resource.service} resource"
                potential_savings = resource.estimated_monthly_cost * Decimal(
                    "0.2"
                )  # 20% potential savings
                action_items = [
                    f"Review {resource.service} resource configuration",
                    "Evaluate if all features are necessary",
                    "Consider alternative pricing models",
                ]

            return CostOptimizationRecommendation(
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                service=resource.service,
                recommendation_type=recommendation_type,
                current_monthly_cost=resource.estimated_monthly_cost,
                potential_monthly_savings=potential_savings,
                confidence_level="medium",
                implementation_effort="medium",
                description=description,
                action_items=action_items,
            )

        except Exception as e:
            self.logger.debug(
                f"Failed to generate recommendation for expensive resource {resource.resource_id}: {e}"
            )
            return None

    def _generate_forgotten_resource_recommendation(
        self, forgotten: ForgottenResourceAnalysis
    ) -> Optional[CostOptimizationRecommendation]:
        """Generate recommendation for forgotten resources."""
        try:
            return CostOptimizationRecommendation(
                resource_id=forgotten.resource_id,
                resource_type=forgotten.resource_type,
                service=forgotten.service,
                recommendation_type="termination",
                current_monthly_cost=forgotten.estimated_monthly_cost,
                potential_monthly_savings=forgotten.estimated_monthly_cost,  # 100% savings if terminated
                confidence_level="high" if forgotten.risk_level == "high" else "medium",
                implementation_effort="low",
                description=f"Consider terminating this resource inactive for {forgotten.days_since_last_activity} days",
                action_items=forgotten.recommendations,
            )

        except Exception as e:
            self.logger.debug(
                f"Failed to generate recommendation for forgotten resource {forgotten.resource_id}: {e}"
            )
            return None

    def _generate_underutilization_recommendations(
        self, cost_estimates: List[ResourceCostEstimate]
    ) -> List[CostOptimizationRecommendation]:
        """Generate recommendations for underutilized resources."""
        recommendations = []

        for estimate in cost_estimates:
            try:
                # This would require additional metrics analysis
                # For now, provide generic recommendations for high-cost resources
                if estimate.estimated_monthly_cost > Decimal("200.00"):
                    rec = CostOptimizationRecommendation(
                        resource_id=estimate.resource_id,
                        resource_type=estimate.resource_type,
                        service=estimate.service,
                        recommendation_type="utilization_review",
                        current_monthly_cost=estimate.estimated_monthly_cost,
                        potential_monthly_savings=estimate.estimated_monthly_cost
                        * Decimal("0.4"),
                        confidence_level="low",
                        implementation_effort="medium",
                        description=f"Review utilization patterns for this high-cost {estimate.service} resource",
                        action_items=[
                            "Analyze resource utilization metrics over the past 30 days",
                            "Consider scheduling or auto-scaling options",
                            "Evaluate if resource can be shared or consolidated",
                        ],
                    )
                    recommendations.append(rec)

            except Exception as e:
                self.logger.debug(
                    f"Failed to generate underutilization recommendation for {estimate.resource_id}: {e}"
                )

        return recommendations

    def generate_cost_analysis_summary(
        self,
        cost_estimates: List[ResourceCostEstimate],
        forgotten_resources: List[ForgottenResourceAnalysis],
        recommendations: List[CostOptimizationRecommendation],
    ) -> CostAnalysisSummary:
        """
        Generate comprehensive cost analysis summary.

        Args:
            cost_estimates: List of resource cost estimates
            forgotten_resources: List of forgotten resource analyses
            recommendations: List of cost optimization recommendations

        Returns:
            CostAnalysisSummary object
        """
        try:
            # Calculate total estimated monthly cost
            total_cost = sum(
                estimate.estimated_monthly_cost for estimate in cost_estimates
            )

            # Count expensive resources
            expensive_count = len(self.identify_expensive_resources(cost_estimates))

            # Calculate total potential savings
            total_savings = sum(
                rec.potential_monthly_savings for rec in recommendations
            )

            # Identify high-risk resources
            high_risk_resources = [
                forgotten.resource_id
                for forgotten in forgotten_resources
                if forgotten.risk_level == "high"
            ]

            # Calculate cost by service
            cost_by_service = defaultdict(Decimal)
            for estimate in cost_estimates:
                cost_by_service[estimate.service] += estimate.estimated_monthly_cost

            # Calculate cost by region
            cost_by_region = defaultdict(Decimal)
            for estimate in cost_estimates:
                cost_by_region[estimate.region] += estimate.estimated_monthly_cost

            return CostAnalysisSummary(
                total_estimated_monthly_cost=total_cost,
                expensive_resources_count=expensive_count,
                forgotten_resources_count=len(forgotten_resources),
                total_potential_savings=total_savings,
                high_risk_resources=high_risk_resources,
                cost_by_service=dict(cost_by_service),
                cost_by_region=dict(cost_by_region),
                optimization_opportunities=len(recommendations),
            )

        except Exception as e:
            self.logger.error(f"Failed to generate cost analysis summary: {e}")
            return CostAnalysisSummary(
                total_estimated_monthly_cost=Decimal("0"),
                expensive_resources_count=0,
                forgotten_resources_count=0,
                total_potential_savings=Decimal("0"),
            )

    def enrich_resource_with_cost_info(
        self, resource: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enrich a single resource with cost analysis information.

        Args:
            resource: Resource dictionary

        Returns:
            Enriched resource dictionary with cost information
        """
        try:
            enriched_resource = resource.copy()

            # Get cost estimate
            cost_estimate = self._estimate_single_resource_cost(resource)
            if cost_estimate:
                enriched_resource["cost_analysis"] = {
                    "estimated_monthly_cost": float(
                        cost_estimate.estimated_monthly_cost
                    ),
                    "cost_breakdown": {
                        k: float(v) for k, v in cost_estimate.cost_breakdown.items()
                    },
                    "pricing_model": cost_estimate.pricing_model,
                    "confidence_level": cost_estimate.confidence_level,
                    "is_expensive": cost_estimate.estimated_monthly_cost
                    >= self.thresholds.expensive_resource_monthly_threshold,
                }

            # Check if resource might be forgotten
            forgotten_analysis = self._analyze_resource_activity(resource)
            if forgotten_analysis:
                enriched_resource["forgotten_analysis"] = {
                    "days_since_last_activity": forgotten_analysis.days_since_last_activity,
                    "risk_level": forgotten_analysis.risk_level,
                    "is_potentially_forgotten": forgotten_analysis.days_since_last_activity
                    >= self.thresholds.forgotten_resource_days_threshold,
                    "recommendations": forgotten_analysis.recommendations,
                }

            return enriched_resource

        except Exception as e:
            self.logger.debug(
                f"Cost enrichment failed for resource {resource.get('id', 'unknown')}: {e}"
            )
            return resource
