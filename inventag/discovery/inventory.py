#!/usr/bin/env python3
"""
AWS Resource Inventory Tool
Discovers and catalogs all AWS resources across services and regions.

Extracted from scripts/aws_resource_inventory.py and enhanced for the unified inventag package.
Now includes AI-capable intelligent discovery for sustainable service-agnostic resource detection.
"""

import json
import yaml
import boto3
import logging
import time
import sys
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from botocore.exceptions import ClientError

# Import the discovery systems
from .intelligent_discovery import IntelligentAWSDiscovery
from .optimized_discovery import OptimizedAWSDiscovery
from .comprehensive_discovery import ComprehensiveAWSDiscovery


class ProgressSpinner:
    """Simple progress spinner for long-running operations."""

    def __init__(self, message="Processing"):
        self.message = message
        self.spinning = False
        self.thread = None
        self.chars = "⣾⣽⣻⢿⡿⣟⣯⣷"

    def start(self):
        """Start the spinner animation."""
        self.spinning = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        """Stop the spinner animation."""
        self.spinning = False
        if self.thread:
            self.thread.join()
        # Clear the line
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def _spin(self):
        """Internal spinner animation loop."""
        i = 0
        while self.spinning:
            sys.stdout.write(f"\r{self.message} {self.chars[i % len(self.chars)]} ")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

    def update_message(self, new_message):
        """Update the spinner message."""
        self.message = new_message


class AWSResourceInventory:
    def __init__(
        self,
        regions: Optional[List[str]] = None,
        session: Optional[boto3.Session] = None,
        services: Optional[List[str]] = None,
        tag_filters: Optional[Dict[str, Any]] = None,
        enable_billing_validation: bool = True,
        use_intelligent: bool = True,
        use_optimized: bool = True,
        standardized_output: bool = True,
        use_comprehensive: bool = True,
        hide_fallback_resources: bool = False,  # Legacy, deprecated
        fallback_display_mode: str = "auto",  # "auto", "always", "never"
    ):
        """Initialize the AWS Resource Inventory tool."""
        self.session = session or boto3.Session()
        self.resources = []
        self.logger = self._setup_logging()
        self.regions = regions if regions is not None else self._get_available_regions()
        self.services = services  # Specific services to scan, None means all
        self.tag_filters = tag_filters or {}  # Tag filters to apply
        # Handle legacy parameter
        if hide_fallback_resources and fallback_display_mode == "auto":
            fallback_display_mode = "never"

        self.fallback_display_mode = fallback_display_mode
        self.hide_fallback_resources = (
            hide_fallback_resources  # Keep for backward compatibility
        )

        # Billing-based discovery state
        self.billing_validated_services: Set[str] = set()
        self.billing_spend_by_service: Dict[str, float] = {}
        self.enable_billing_validation = enable_billing_validation

        # Initialize discovery systems
        self.intelligent_discovery = IntelligentAWSDiscovery(
            session=self.session, regions=self.regions
        )
        self.optimized_discovery = OptimizedAWSDiscovery(
            session=self.session, regions=self.regions
        )
        self.comprehensive_discovery = ComprehensiveAWSDiscovery(
            session=self.session,
            regions=self.regions,
            fallback_display_mode=self.fallback_display_mode,
        )

        # Store original regions for fallback logic
        self.original_regions = self.regions.copy() if self.regions else None

        # Discovery modes - Configure from parameters
        self.use_intelligent_discovery = use_intelligent
        self.use_optimized_discovery = use_optimized
        self.use_comprehensive_discovery = use_comprehensive
        self.standardized_output = standardized_output

        # AI prediction and state management
        self.enable_ai_prediction = True  # Enable AI-based resource prediction
        self.ensure_consistent_results = (
            True  # Ensure consistent results for state management
        )
        self.resource_prediction_cache = {}  # Cache for AI predictions

    def configure_discovery_mode(
        self,
        use_intelligent: bool = True,
        standardized_output: bool = True,
        use_optimized: bool = True,
    ):
        """Configure the discovery mode and output format.

        Args:
            use_intelligent: Use AI-capable intelligent discovery system
            standardized_output: Use standardized column format for consistent output
            use_optimized: Use optimized discovery system with enhanced service coverage
        """
        self.use_intelligent_discovery = use_intelligent
        self.use_optimized_discovery = use_optimized
        self.standardized_output = standardized_output

        if use_optimized and use_intelligent:
            self.logger.info(
                "Configured to use optimized intelligent discovery with enhanced service coverage"
            )
        elif use_intelligent:
            self.logger.info(
                "Configured to use AI-capable intelligent discovery with standardized output"
            )
        else:
            self.logger.info("Configured to use legacy discovery methods")

    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration with fallback handling."""
        try:
            logger = logging.getLogger(__name__)

            # Avoid duplicate handlers if logger already configured
            if not logger.handlers:
                # Only configure basicConfig if no root handlers exist
                if not logging.root.handlers:
                    logging.basicConfig(
                        level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s",
                    )
                else:
                    # If root logger has handlers, just set level for this logger
                    logger.setLevel(logging.INFO)

                # Prevent propagation to root logger to avoid duplicates
                logger.propagate = False

                # Add handler only if none exists
                if not logger.handlers:
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    )
                    handler.setFormatter(formatter)
                    logger.addHandler(handler)

            logger.debug("Logger initialized successfully")
            return logger
        except Exception as e:
            # Fallback to basic logging if setup fails
            fallback_logger = logging.getLogger(__name__)
            if not fallback_logger.handlers:
                fallback_logger.addHandler(logging.StreamHandler())
                fallback_logger.setLevel(logging.INFO)
                fallback_logger.propagate = False
            fallback_logger.warning(f"Failed to setup logging, using fallback: {e}")
            return fallback_logger

    def _get_available_regions(self) -> List[str]:
        """Get all available AWS regions with fallback."""
        # Return static list to avoid recursion when creating EC2 client
        # This prevents infinite recursion during discovery initialization
        fallback_regions = [
            "us-east-1",
            "us-west-2",
            "eu-west-1",
            "eu-central-1",
            "ap-southeast-1",
            "ap-northeast-1",
            "us-east-2",
            "us-west-1",
            "eu-west-2",
            "eu-west-3",
            "ap-southeast-2",
            "ap-northeast-2",
            "ca-central-1",
            "sa-east-1",
        ]
        self.logger.info(
            f"Using static region list with {len(fallback_regions)} AWS regions"
        )
        return fallback_regions

    def discover_resources(self) -> List[Dict[str, Any]]:
        """Discover all AWS resources across regions and services with billing validation and intelligent discovery."""
        if self.use_comprehensive_discovery:
            discovery_method = "comprehensive"
        elif self.use_intelligent_discovery:
            discovery_method = "intelligent"
        else:
            discovery_method = "legacy"

        self.logger.info(
            f"Starting comprehensive AWS resource discovery ({discovery_method} mode) with billing validation..."
        )

        # Step 1: Discover services with actual usage via billing data
        if self.enable_billing_validation:
            spinner = ProgressSpinner(
                "🔍 Analyzing billing data to identify services with usage"
            )
            spinner.start()
            try:
                self._discover_services_via_billing()
            finally:
                spinner.stop()

        # Step 2: Intelligent AI-capable discovery (if enabled)
        if self.use_intelligent_discovery:
            initial_resource_count = len(self.resources)

            if self.use_optimized_discovery:
                spinner = ProgressSpinner("🚀 Optimized intelligent resource discovery")
                spinner.start()
                try:
                    self._perform_optimized_discovery()
                finally:
                    spinner.stop()
            else:
                spinner = ProgressSpinner(
                    "🧠 AI-capable intelligent resource discovery"
                )
                spinner.start()
                try:
                    self._perform_intelligent_discovery()
                finally:
                    spinner.stop()

            intelligent_resource_count = len(self.resources)
            self.logger.info(
                f"Intelligent discovery found {intelligent_resource_count - initial_resource_count} resources with enhanced detection"
            )

        # Step 3: Comprehensive discovery - service-specific APIs first, then ResourceGroupsTagging for enrichment
        if self.use_comprehensive_discovery:
            initial_resource_count = len(self.resources)
            spinner = ProgressSpinner(
                "🔍 Comprehensive discovery: service-specific APIs → tag enrichment → billing validation"
            )
            spinner.start()
            try:
                comprehensive_resources = (
                    self.comprehensive_discovery.discover_all_resources()
                )
                # Convert comprehensive discovery format to inventory format
                for resource in comprehensive_resources:
                    self.resources.append(resource)
            finally:
                spinner.stop()
            rgt_resource_count = len(self.resources)
        else:
            # Fallback to ResourceGroupsTagging API for backward compatibility
            initial_resource_count = len(self.resources)
            spinner = ProgressSpinner(
                "📋 Discovering resources via ResourceGroupsTagging API (fallback mode)"
            )
            spinner.start()
            try:
                self._discover_via_resource_groups_tagging_api()
            finally:
                spinner.stop()
            rgt_resource_count = len(self.resources)

        # Step 3: Cross-validate with billing and enhance discovery
        if self.enable_billing_validation:
            spinner = ProgressSpinner("💰 Cross-validating discovery with billing data")
            spinner.start()
            try:
                self._validate_discovery_with_billing()
            finally:
                spinner.stop()

        # Step 4: Dynamic discovery based on billing validation
        discovered_service_names = set(
            resource.get("service", "").upper() for resource in self.resources
        )

        # For services with billing usage but no discovered resources, try dynamic discovery
        if self.enable_billing_validation and hasattr(self, "billing_spend_by_service"):
            undiscovered_services = (
                set(self.billing_spend_by_service.keys()) - discovered_service_names
            )
            if undiscovered_services:
                self.logger.info(
                    f"Attempting optimized dynamic discovery for {len(undiscovered_services)} services with billing usage"
                )
                spinner = ProgressSpinner(
                    f"🚀 Performing optimized dynamic discovery for {len(undiscovered_services)} services"
                )
                spinner.start()
                try:
                    # Use optimized parallel discovery
                    from .optimized_dynamic_discovery import OptimizedDynamicDiscovery

                    optimizer = OptimizedDynamicDiscovery(
                        session=self.session,
                        max_workers=min(
                            10, len(undiscovered_services) * 2
                        ),  # Reasonable parallelism
                    )

                    # Limit services to avoid excessive API calls
                    services_to_discover = list(undiscovered_services)[:15]

                    spinner.update_message(
                        f"🚀 Parallel discovery across {len(self.regions)} regions"
                    )

                    # Run optimized discovery
                    discovery_results = optimizer.discover_services_parallel(
                        services=services_to_discover,
                        regions=self.regions,
                        max_resources_per_service=20,  # Reasonable limit per service
                    )

                    # Add discovered resources to main resource list
                    if discovery_results["resources"]:
                        self.resources.extend(discovery_results["resources"])

                    # Log performance metrics
                    perf = discovery_results["performance"]
                    self.logger.info(
                        f"✅ Dynamic discovery completed: {perf['total_resources_found']} resources "
                        f"in {perf['total_execution_time']:.1f}s "
                        f"({perf['resources_per_second']:.1f} resources/sec)"
                    )

                    # Log successful services
                    successful_services = [
                        r.service_name
                        for r in discovery_results["results"]
                        if r.success and r.resources_found > 0
                    ]
                    if successful_services:
                        self.logger.info(
                            f"📊 Resources found in: {', '.join(set(successful_services))}"
                        )

                except Exception as e:
                    self.logger.error(f"Optimized dynamic discovery failed: {e}")
                    # Fallback to original method for critical reliability
                    self.logger.info("Falling back to sequential discovery...")
                    for i, service_name in enumerate(
                        list(undiscovered_services)[:5]
                    ):  # Reduced fallback
                        spinner.update_message(f"🔄 Fallback: {service_name} ({i+1}/5)")
                        try:
                            self._discover_service_by_name(service_name)
                        except Exception as fallback_error:
                            self.logger.debug(
                                f"Fallback discovery failed for {service_name}: {fallback_error}"
                            )
                finally:
                    spinner.stop()

        # Step 5: Service-specific discovery for enhanced details (always run for legacy mode)
        if not self.use_intelligent_discovery:
            self._discover_service_specific_resources()

        # Step 6: If still very few resources, try basic service discovery
        total_resources_after_service_specific = len(self.resources)
        if total_resources_after_service_specific < 10:
            self.logger.warning(
                "Still few resources after service-specific discovery. Trying basic services."
            )
            basic_services = ["EC2", "S3", "RDS", "Lambda", "CloudWatch", "IAM"]
            for service in basic_services:
                try:
                    self._discover_service_by_name(service)
                except Exception as e:
                    self.logger.debug(f"Basic discovery failed for {service}: {e}")

        # Step 7: Remove duplicates based on ARN
        self._deduplicate_resources()

        # Step 8: Apply AI predictions for enhanced discovery
        if self.enable_ai_prediction:
            spinner = ProgressSpinner("🤖 Applying AI-based resource predictions")
            spinner.start()
            try:
                self._apply_ai_predictions()
            finally:
                spinner.stop()

        # Step 9: Add billing metadata to resources
        if self.enable_billing_validation:
            self._add_billing_metadata()

        # Step 10: Ensure consistent results for state management
        if self.ensure_consistent_results:
            self._ensure_consistent_results()

        discovered_services = len(self._get_discovered_services())
        billing_validated = (
            len(self.billing_validated_services)
            if hasattr(self, "billing_validated_services")
            else 0
        )

        self.logger.info(
            f"Comprehensive discovery complete. Found {len(self.resources)} unique resources "
            f"across {discovered_services} services "
            f"({billing_validated} billing-validated)."
        )
        return self.resources

    def _perform_intelligent_discovery(self):
        """Perform AI-capable intelligent resource discovery with standardized output."""
        self.logger.info(
            "Starting intelligent AWS discovery with standardized columns..."
        )

        try:
            # Use the intelligent discovery system
            standard_resources = self.intelligent_discovery.discover_all_services()

            if self.standardized_output:
                # Convert StandardResource objects to standardized dictionaries
                standardized_data = (
                    self.intelligent_discovery.export_standardized_data()
                )

                # Convert to our internal format while preserving standardized structure
                for standard_data in standardized_data:
                    # Create resource in the format expected by the rest of the system
                    resource = {
                        # Standardized core fields
                        "arn": standard_data.get("resource_arn")
                        or f"arn:aws:{standard_data['service_name'].lower()}:{standard_data['region']}:{standard_data.get('account_id', 'unknown')}:resource/{standard_data['resource_id']}",
                        "id": standard_data["resource_id"],
                        "service": standard_data["service_name"],
                        "type": standard_data["resource_type"],
                        "name": standard_data.get("resource_name")
                        or standard_data.get("name_from_tags")
                        or standard_data["resource_id"],
                        "region": standard_data["region"],
                        # Standardized metadata
                        "account_id": standard_data.get("account_id"),
                        "status": standard_data.get("status"),
                        "state": standard_data.get("state"),
                        "created_date": standard_data.get("created_date"),
                        "last_modified": standard_data.get("last_modified"),
                        # Standardized tagging
                        "tags": standard_data.get("tags", {}),
                        "environment": standard_data.get("environment"),
                        "project": standard_data.get("project"),
                        "cost_center": standard_data.get("cost_center"),
                        # Standardized security and networking
                        "public_access": standard_data.get("public_access", False),
                        "encrypted": standard_data.get("encrypted"),
                        "vpc_id": standard_data.get("vpc_id"),
                        "subnet_ids": standard_data.get("subnet_ids", []),
                        "security_groups": standard_data.get("security_groups", []),
                        "availability_zone": standard_data.get("availability_zone"),
                        # Discovery metadata
                        "discovered_at": standard_data.get("discovered_at"),
                        "discovery_method": standard_data.get(
                            "discovery_method", "IntelligentDiscovery"
                        ),
                        "api_operation": standard_data.get("api_operation"),
                        "confidence_score": standard_data.get("confidence_score", 1.0),
                        # Legacy compatibility
                        "compliance_status": "unknown",  # Will be updated by compliance analysis
                    }

                    self.resources.append(resource)

                self.logger.info(
                    f"Intelligent discovery added {len(standardized_data)} resources with standardized columns"
                )
            else:
                # Convert StandardResource objects to legacy format
                for standard_resource in standard_resources:
                    legacy_resource = {
                        "arn": standard_resource.resource_arn
                        or f"arn:aws:{standard_resource.service_name.lower()}:{standard_resource.region}:{standard_resource.account_id or 'unknown'}:resource/{standard_resource.resource_id}",
                        "id": standard_resource.resource_id,
                        "service": standard_resource.service_name,
                        "type": standard_resource.resource_type,
                        "name": standard_resource.resource_name
                        or standard_resource.name_from_tags
                        or standard_resource.resource_id,
                        "region": standard_resource.region,
                        "tags": standard_resource.tags,
                        "compliance_status": "unknown",
                    }

                    self.resources.append(legacy_resource)

                self.logger.info(
                    f"Intelligent discovery added {len(standard_resources)} resources in legacy format"
                )

        except Exception as e:
            self.logger.error(f"Intelligent discovery failed: {e}")
            self.logger.info("Falling back to traditional discovery methods...")

    def _perform_optimized_discovery(self):
        """Perform optimized AI-capable intelligent resource discovery with enhanced service coverage."""
        self.logger.info(
            "Starting optimized AWS discovery with enhanced service coverage..."
        )

        try:
            # Use the optimized discovery system with AI predictions
            if self.enable_ai_prediction:
                standard_resources = (
                    self.optimized_discovery.discover_all_services_with_ai()
                )
            else:
                standard_resources = self.optimized_discovery.discover_all_services()

            if self.standardized_output:
                # Convert StandardResource objects to standardized dictionaries
                for standard_resource in standard_resources:
                    # Create resource in the format expected by the rest of the system
                    resource = {
                        # Standardized core fields
                        "arn": standard_resource.resource_arn
                        or f"arn:aws:{standard_resource.service_name.lower()}:{standard_resource.region}:{standard_resource.account_id or 'unknown'}:resource/{standard_resource.resource_id}",
                        "id": standard_resource.resource_id,
                        "service": standard_resource.service_name,
                        "type": standard_resource.resource_type,
                        "name": standard_resource.resource_name
                        or standard_resource.name_from_tags
                        or standard_resource.resource_id,
                        "region": standard_resource.region,
                        # Standardized metadata
                        "account_id": standard_resource.account_id,
                        "status": standard_resource.status,
                        "state": standard_resource.state,
                        "created_date": standard_resource.created_date,
                        "last_modified": standard_resource.last_modified,
                        # Standardized tagging
                        "tags": standard_resource.tags,
                        "environment": standard_resource.environment,
                        "project": standard_resource.project,
                        "cost_center": standard_resource.cost_center,
                        # Standardized security and networking
                        "public_access": standard_resource.public_access,
                        "encrypted": standard_resource.encrypted,
                        "vpc_id": standard_resource.vpc_id,
                        "subnet_ids": standard_resource.subnet_ids,
                        "security_groups": standard_resource.security_groups,
                        "availability_zone": standard_resource.availability_zone,
                        # Discovery metadata
                        "discovered_at": standard_resource.discovered_at,
                        "discovery_method": "OptimizedDiscovery",
                        "api_operation": standard_resource.api_operation,
                        "confidence_score": standard_resource.confidence_score,
                        # Legacy compatibility
                        "compliance_status": "unknown",  # Will be updated by compliance analysis
                    }

                    self.resources.append(resource)

                self.logger.info(
                    f"Optimized discovery added {len(standard_resources)} resources with enhanced service coverage"
                )
            else:
                # Convert StandardResource objects to legacy format
                for standard_resource in standard_resources:
                    legacy_resource = {
                        "arn": standard_resource.resource_arn
                        or f"arn:aws:{standard_resource.service_name.lower()}:{standard_resource.region}:{standard_resource.account_id or 'unknown'}:resource/{standard_resource.resource_id}",
                        "id": standard_resource.resource_id,
                        "service": standard_resource.service_name,
                        "type": standard_resource.resource_type,
                        "name": standard_resource.resource_name
                        or standard_resource.name_from_tags
                        or standard_resource.resource_id,
                        "region": standard_resource.region,
                        "tags": standard_resource.tags,
                        "compliance_status": "unknown",
                        "confidence_score": standard_resource.confidence_score,
                    }

                    self.resources.append(legacy_resource)

                self.logger.info(
                    f"Optimized discovery added {len(standard_resources)} resources in legacy format"
                )

        except Exception as e:
            self.logger.error(f"Optimized discovery failed: {e}")
            self.logger.info("Falling back to standard intelligent discovery...")
            # Fall back to standard intelligent discovery
            try:
                self._perform_intelligent_discovery()
            except Exception as fallback_error:
                self.logger.error(
                    f"Fallback intelligent discovery also failed: {fallback_error}"
                )
                self.logger.info("Continuing with traditional discovery methods...")

    def _ensure_consistent_results(self):
        """Ensure consistent results for state management by sorting and normalizing resources."""

        if not self.ensure_consistent_results:
            return

        self.logger.info("Ensuring consistent results for state management...")

        # Sort resources by ARN, then by service, type, and ID for consistency
        def sort_key(resource):
            return (
                resource.get("arn", ""),
                resource.get("service", ""),
                resource.get("type", ""),
                resource.get("id", ""),
                resource.get("region", ""),
            )

        self.resources.sort(key=sort_key)

        # Normalize resource data for consistency
        for resource in self.resources:
            # Ensure consistent field formats
            if "tags" in resource and not isinstance(resource["tags"], dict):
                resource["tags"] = {}

            # Normalize region names
            if "region" in resource and resource["region"]:
                resource["region"] = resource["region"].lower().strip()

            # Ensure consistent service names
            if "service" in resource and resource["service"]:
                resource["service"] = self._normalize_service_name_for_consistency(
                    resource["service"]
                )

        self.logger.info(
            f"Normalized {len(self.resources)} resources for consistent state management"
        )

    def _normalize_service_name_for_consistency(self, service_name: str) -> str:
        """Normalize service names for consistency across discoveries."""

        # Mapping for consistent service names
        service_mappings = {
            "CLOUDFRONT": "CloudFront",
            "ROUTE53": "Route 53",
            "ROUTE 53": "Route 53",
            "LAMBDA": "Lambda",
            "CLOUDWATCH": "CloudWatch",
            "CLOUDFORMATION": "CloudFormation",
            "EC2": "EC2",
            "S3": "S3",
            "IAM": "IAM",
            "RDS": "RDS",
        }

        return service_mappings.get(service_name.upper(), service_name)

    def _apply_ai_predictions(self):
        """Apply AI-based predictions to enhance resource discovery."""

        if not self.enable_ai_prediction:
            return

        self.logger.info("Applying AI-based resource predictions...")

        # Predict missing resources based on existing patterns
        predicted_resources = self._predict_missing_resources()

        if predicted_resources:
            self.logger.info(
                f"AI prediction suggests {len(predicted_resources)} potentially missing resources"
            )

            # Add predicted resources with lower confidence scores
            for predicted in predicted_resources:
                predicted["discovery_method"] = "AI_Prediction"
                predicted["confidence_score"] = predicted.get("confidence_score", 0.3)
                predicted["predicted"] = True
                self.resources.append(predicted)

    def _predict_missing_resources(self) -> List[Dict[str, Any]]:
        """Predict missing resources based on existing resource patterns."""

        predicted = []

        # Analyze existing resources for patterns
        service_patterns = {}
        region_patterns = {}

        for resource in self.resources:
            service = resource.get("service", "")
            region = resource.get("region", "")

            if service not in service_patterns:
                service_patterns[service] = []
            service_patterns[service].append(resource)

            if region not in region_patterns:
                region_patterns[region] = []
            region_patterns[region].append(resource)

        # Predict based on service patterns
        predicted.extend(self._predict_from_service_patterns(service_patterns))

        # Predict based on region patterns
        predicted.extend(self._predict_from_region_patterns(region_patterns))

        return predicted

    def _predict_from_service_patterns(
        self, service_patterns: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Predict missing resources based on service usage patterns."""

        predicted = []

        # If we have Lambda functions, predict CloudWatch log groups
        if "Lambda" in service_patterns and "CloudWatch" in service_patterns:
            lambda_functions = service_patterns["Lambda"]
            cloudwatch_resources = service_patterns["CloudWatch"]

            # Check if we have log groups for all Lambda functions
            log_group_names = {
                r.get("name", "")
                for r in cloudwatch_resources
                if "log" in r.get("type", "").lower()
            }

            for func in lambda_functions:
                func_name = func.get("name", "")
                expected_log_group = f"/aws/lambda/{func_name}"

                if expected_log_group not in log_group_names:
                    predicted.append(
                        {
                            "arn": f"arn:aws:logs:{func.get('region', 'us-east-1')}:{func.get('account_id', 'unknown')}:log-group:{expected_log_group}",
                            "id": expected_log_group,
                            "service": "CloudWatch",
                            "type": "LogGroup",
                            "name": expected_log_group,
                            "region": func.get("region", "us-east-1"),
                            "account_id": func.get("account_id"),
                            "tags": {},
                            "confidence_score": 0.7,
                            "predicted_reason": f"Lambda function {func_name} typically has associated log group",
                        }
                    )

        return predicted

    def _predict_from_region_patterns(
        self, region_patterns: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Predict missing resources based on region usage patterns."""

        predicted = []

        # If we have resources in multiple regions, predict default VPCs
        regions_with_resources = [
            r for r in region_patterns.keys() if r and r != "global"
        ]

        if len(regions_with_resources) > 1:
            # Check if we have VPCs in all regions where we have resources
            vpc_regions = set()
            for region, resources in region_patterns.items():
                for resource in resources:
                    if (
                        resource.get("service") == "EC2"
                        and resource.get("type") == "VPC"
                    ):
                        vpc_regions.add(region)

            # Predict missing default VPCs (but these would be filtered out as AWS managed)
            # This is more for demonstration of the prediction capability

        return predicted

    def _discover_services_via_billing(self):
        """Discover services with actual usage via AWS Cost Explorer billing data."""
        self.logger.info("Discovering services with actual usage via billing data...")

        try:
            # Cost Explorer is only available in us-east-1
            ce = self.session.client("ce", region_name="us-east-1")

            # Get cost data for the last 30 days to identify active services
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)

            # Query cost and usage data grouped by service
            response = ce.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity="MONTHLY",
                Metrics=["BlendedCost", "UsageQuantity"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )

            # Process billing data to identify active services
            services_with_usage = {}
            total_spend = 0.0

            for result_by_time in response["ResultsByTime"]:
                for group in result_by_time["Groups"]:
                    service_name = group["Keys"][0] if group["Keys"] else "Unknown"
                    cost_amount = float(group["Metrics"]["BlendedCost"]["Amount"])
                    usage_quantity = float(group["Metrics"]["UsageQuantity"]["Amount"])

                    if (
                        cost_amount > 0.01 or usage_quantity > 0
                    ):  # Services with minimal spend or usage
                        normalized_service = self._normalize_billing_service_name(
                            service_name
                        )
                        services_with_usage[normalized_service] = {
                            "billing_name": service_name,
                            "cost": cost_amount,
                            "usage": usage_quantity,
                            "aws_service_code": normalized_service,
                        }
                        total_spend += cost_amount

            # Store billing-validated services
            self.billing_validated_services = set(services_with_usage.keys())
            self.billing_spend_by_service = {
                svc: data["cost"] for svc, data in services_with_usage.items()
            }

            self.logger.info(
                f"Billing analysis: Found {len(services_with_usage)} services with usage "
                f"(${total_spend:.2f} total spend in last 30 days)"
            )

            # Log top spending services
            top_services = sorted(
                services_with_usage.items(), key=lambda x: x[1]["cost"], reverse=True
            )[:10]

            for service, data in top_services:
                self.logger.info(f"  💰 {service}: ${data['cost']:.2f}")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "UnauthorizedOperation":
                self.logger.warning(
                    "No permission for Cost Explorer API. Skipping billing validation."
                )
            elif error_code == "OptInRequired":
                self.logger.warning(
                    "Cost Explorer not enabled. Skipping billing validation."
                )
            else:
                self.logger.warning(f"Cost Explorer API failed: {e}")
            self.enable_billing_validation = False
        except Exception as e:
            self.logger.warning(f"Billing discovery failed: {e}")
            self.enable_billing_validation = False

    def _normalize_billing_service_name(self, billing_service_name: str) -> str:
        """Normalize billing service names to AWS service codes."""
        # Mapping of billing service names to standard AWS service codes
        service_mappings = {
            # Compute
            "Amazon Elastic Compute Cloud - Compute": "EC2",
            "Amazon Elastic Container Service": "ECS",
            "Amazon Elastic Kubernetes Service": "EKS",
            "AWS Lambda": "LAMBDA",
            "Amazon Lightsail": "LIGHTSAIL",
            "AWS Batch": "BATCH",
            # Storage
            "Amazon Simple Storage Service": "S3",
            "Amazon Elastic Block Store": "EBS",
            "Amazon Elastic File System": "EFS",
            "Amazon FSx": "FSX",
            "AWS Storage Gateway": "STORAGEGATEWAY",
            # Database
            "Amazon Relational Database Service": "RDS",
            "Amazon DynamoDB": "DYNAMODB",
            "Amazon ElastiCache": "ELASTICACHE",
            "Amazon Redshift": "REDSHIFT",
            "Amazon DocumentDB (with MongoDB compatibility)": "DOCDB",
            "Amazon Neptune": "NEPTUNE",
            # Networking
            "Amazon Virtual Private Cloud": "VPC",
            "Elastic Load Balancing": "ELB",
            "Amazon CloudFront": "CLOUDFRONT",
            "Amazon Route 53": "ROUTE53",
            "AWS Direct Connect": "DIRECTCONNECT",
            "Amazon API Gateway": "APIGATEWAY",
            # Security & Identity
            "AWS Identity and Access Management": "IAM",
            "AWS Certificate Manager": "ACM",
            "Amazon Cognito": "COGNITO",
            "AWS Secrets Manager": "SECRETSMANAGER",
            "AWS Systems Manager": "SSM",
            "AWS WAF": "WAF",
            # Application Integration
            "Amazon Simple Notification Service": "SNS",
            "Amazon Simple Queue Service": "SQS",
            "AWS Step Functions": "STEPFUNCTIONS",
            "Amazon EventBridge": "EVENTS",
            "Amazon MQ": "MQ",
            # Analytics
            "Amazon Kinesis": "KINESIS",
            "Amazon Athena": "ATHENA",
            "AWS Glue": "GLUE",
            "Amazon EMR": "EMR",
            "Amazon QuickSight": "QUICKSIGHT",
            # Machine Learning
            "Amazon SageMaker": "SAGEMAKER",
            "Amazon Rekognition": "REKOGNITION",
            "Amazon Comprehend": "COMPREHEND",
            "Amazon Translate": "TRANSLATE",
            # Management & Governance
            "AWS CloudFormation": "CLOUDFORMATION",
            "Amazon CloudWatch": "CLOUDWATCH",
            "AWS CloudTrail": "CLOUDTRAIL",
            "AWS Config": "CONFIG",
            "AWS Organizations": "ORGANIZATIONS",
            # Developer Tools
            "AWS CodeCommit": "CODECOMMIT",
            "AWS CodeBuild": "CODEBUILD",
            "AWS CodePipeline": "CODEPIPELINE",
            "AWS CodeDeploy": "CODEDEPLOY",
        }

        # Try exact match first
        if billing_service_name in service_mappings:
            return service_mappings[billing_service_name]

        # Try partial matches for services not in the mapping
        billing_lower = billing_service_name.lower()

        # Extract service name from billing strings
        if "amazon" in billing_lower:
            service_part = billing_service_name.replace("Amazon ", "").replace(
                "AWS ", ""
            )
            # Convert to uppercase and replace spaces/hyphens
            return service_part.upper().replace(" ", "").replace("-", "")[:20]
        elif "aws" in billing_lower:
            service_part = billing_service_name.replace("AWS ", "").replace(
                "Amazon ", ""
            )
            return service_part.upper().replace(" ", "").replace("-", "")[:20]

        # Fallback: return cleaned up version
        return billing_service_name.upper().replace(" ", "").replace("-", "")[:20]

    def _validate_discovery_with_billing(self):
        """Cross-validate ResourceGroupsTagging discovery with billing data."""
        if not self.enable_billing_validation:
            return

        discovered_services = self._get_discovered_services()

        # Find services with billing usage but no discovered resources
        missing_services = self.billing_validated_services - discovered_services

        if missing_services:
            self.logger.warning(
                f"Found {len(missing_services)} services with billing usage but no discovered resources:"
            )
            for service in sorted(missing_services):
                spend = self.billing_spend_by_service.get(service, 0)
                self.logger.warning(
                    f"  💸 {service}: ${spend:.2f} (may have untagged resources)"
                )

        # Find services with discovered resources but no billing usage
        unbilled_services = discovered_services - self.billing_validated_services
        if unbilled_services:
            self.logger.info(
                f"Found {len(unbilled_services)} services with discovered resources but no recent billing:"
            )
            for service in sorted(unbilled_services):
                self.logger.info(f"  🆓 {service}: (free tier or no recent usage)")

    def _discover_missing_billing_services(self):
        """Attempt to discover resources for services that have billing usage but no discovered resources."""
        if not self.enable_billing_validation:
            return

        discovered_services = self._get_discovered_services()
        missing_services = self.billing_validated_services - discovered_services

        if not missing_services:
            return

        self.logger.info(
            f"Attempting targeted discovery for {len(missing_services)} services with billing usage..."
        )

        # Attempt service-specific discovery for missing services
        for service in missing_services:
            spend = self.billing_spend_by_service.get(service, 0)
            self.logger.info(f"Targeting {service} (${spend:.2f} spend)...")

            try:
                self._discover_service_by_name(service)
            except Exception as e:
                self.logger.warning(f"Failed to discover resources for {service}: {e}")

    def _discover_service_by_name(self, service_name: str):
        """Dynamically discover resources for a service using generic AWS API calls."""
        service_normalized = self._normalize_service_name(service_name.lower())

        # Get the AWS service client name from the service name
        service_client_name = self._get_service_client_name(service_name)

        if not service_client_name:
            self.logger.debug(f"No client mapping found for service: {service_name}")
            return

        self.logger.info(
            f"Attempting dynamic discovery for service: {service_normalized} (client: {service_client_name})"
        )

        for region in self.regions:
            try:
                self._discover_service_dynamically(
                    service_client_name, service_normalized, region
                )
            except Exception as e:
                self.logger.warning(
                    f"Dynamic discovery failed for {service_name} in {region}: {e}"
                )

    def _get_discovered_services(self) -> Set[str]:
        """Get set of services that have been discovered."""
        return set(resource.get("service", "").upper() for resource in self.resources)

    def _add_billing_metadata(self):
        """Add billing metadata to discovered resources."""
        if not self.enable_billing_validation:
            return

        for resource in self.resources:
            service = resource.get("service", "").upper()
            if service in self.billing_spend_by_service:
                resource["billing_validated"] = True
                resource["service_monthly_spend"] = self.billing_spend_by_service[
                    service
                ]
            else:
                resource["billing_validated"] = False
                resource["service_monthly_spend"] = 0.0

    def _discover_via_resource_groups_tagging_api(self):
        """Use Resource Groups Tagging API to discover all taggable resources."""
        self.logger.info("Discovering resources via ResourceGroupsTagging API...")

        for region in self.regions:
            try:
                rgt_client = self.session.client(
                    "resourcegroupstaggingapi", region_name=region
                )

                # Get all resources (paginated)
                paginator = rgt_client.get_paginator("get_resources")
                region_resources = 0

                for page in paginator.paginate():
                    for resource in page.get("ResourceTagMappingList", []):
                        try:
                            # Parse ARN to extract service and resource info
                            arn = resource["ResourceARN"]
                            arn_parts = arn.split(":")

                            if len(arn_parts) >= 6:
                                service = arn_parts[2]
                                region_from_arn = arn_parts[3] or region
                                account_id = arn_parts[4]
                                resource_part = arn_parts[5]

                                # Extract resource type and ID
                                if "/" in resource_part:
                                    resource_type, resource_id = resource_part.split(
                                        "/", 1
                                    )
                                else:
                                    resource_type = resource_part
                                    resource_id = resource_part

                                # Convert tag list to dictionary
                                tags = {
                                    tag["Key"]: tag["Value"]
                                    for tag in resource.get("Tags", [])
                                }

                                # Create resource entry with normalized service name
                                normalized_service = self._normalize_service_name(
                                    service
                                )
                                resource_entry = {
                                    "service": normalized_service,
                                    "type": self._normalize_resource_type(
                                        service, resource_type
                                    ),
                                    "region": region_from_arn,
                                    "id": resource_id,
                                    "name": tags.get("Name", ""),
                                    "arn": arn,
                                    "account_id": account_id,
                                    "tags": tags,
                                    "discovered_via": "ResourceGroupsTaggingAPI",
                                    "discovered_at": datetime.utcnow().isoformat(),
                                }

                                # Apply service filters if specified
                                if self.services and service.upper() not in [
                                    s.upper() for s in self.services
                                ]:
                                    continue

                                # Apply tag filters if specified
                                if self.tag_filters and not self._matches_tag_filters(
                                    tags
                                ):
                                    continue

                                self.resources.append(resource_entry)
                                region_resources += 1

                        except Exception as e:
                            self.logger.warning(
                                f"Failed to process resource {resource.get('ResourceARN', 'unknown')}: {e}"
                            )
                            continue

                self.logger.info(
                    f"Found {region_resources} resources in region {region} via ResourceGroupsTagging API"
                )

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "UnauthorizedOperation":
                    self.logger.warning(
                        f"No permission for ResourceGroupsTagging API in region {region}"
                    )
                else:
                    self.logger.warning(
                        f"ResourceGroupsTagging API failed in region {region}: {e}"
                    )
            except Exception as e:
                self.logger.warning(
                    f"ResourceGroupsTagging API failed in region {region}: {e}"
                )

    def _normalize_service_name(self, service: str) -> str:
        """Normalize service names for consistent display across discovery methods."""
        # Mapping from AWS service identifiers to consistent display names
        service_normalizations = {
            # Compute
            "ec2": "EC2",
            "lambda": "Lambda",
            "ecs": "ECS",
            "eks": "EKS",
            "batch": "Batch",
            "elasticbeanstalk": "Elastic Beanstalk",
            # Storage
            "s3": "S3",
            "ebs": "EBS",
            "efs": "EFS",
            "fsx": "FSx",
            # Database
            "rds": "RDS",
            "dynamodb": "DynamoDB",
            "elasticache": "ElastiCache",
            "redshift": "Redshift",
            "neptune": "Neptune",
            "documentdb": "DocumentDB",
            # Networking
            "vpc": "VPC",
            "elb": "ELB",
            "elbv2": "ELB",
            "cloudfront": "CloudFront",
            "route53": "Route 53",
            "directconnect": "Direct Connect",
            "apigateway": "API Gateway",
            "apigatewayv2": "API Gateway",
            # Security & Identity
            "iam": "IAM",
            "cognito-idp": "Cognito",
            "cognito-identity": "Cognito",
            "secretsmanager": "Secrets Manager",
            "acm": "ACM",
            "kms": "KMS",
            "keymanagementservice": "KMS",
            "wa": "WAF",
            "wafv2": "WAF",
            "shield": "Shield",
            # Management & Governance
            "cloudwatch": "CloudWatch",
            "amazoncloudwatch": "CloudWatch",
            "cloudwatchevents": "CloudWatch Events",
            "cloudformation": "CloudFormation",
            "cloudtrail": "CloudTrail",
            "config": "Config",
            "organizations": "Organizations",
            "ssm": "Systems Manager",
            # Developer Tools
            "codecommit": "CodeCommit",
            "codebuild": "CodeBuild",
            "codepipeline": "CodePipeline",
            "codedeploy": "CodeDeploy",
            # Application Integration
            "sns": "SNS",
            "sqs": "SQS",
            "kinesis": "Kinesis",
            "stepfunctions": "Step Functions",
            # Analytics
            "glue": "Glue",
            "athena": "Athena",
            "quicksight": "QuickSight",
            "elasticsearch": "Elasticsearch",
            # Machine Learning
            "sagemaker": "SageMaker",
            "rekognition": "Rekognition",
            "comprehend": "Comprehend",
            "translate": "Translate",
        }

        service_lower = service.lower()
        return service_normalizations.get(service_lower, service.upper())

    def _get_service_client_name(self, service_name: str) -> Optional[str]:
        """Map service names to boto3 client names for dynamic discovery."""
        service_lower = service_name.lower()

        # Mapping from service identifiers to boto3 client names
        service_client_mapping = {
            # Core services
            "ec2": "ec2",
            "lambda": "lambda",
            "s3": "s3",
            "rds": "rds",
            "dynamodb": "dynamodb",
            "iam": "iam",
            "vpc": "ec2",
            # Management & Governance
            "cloudwatch": "cloudwatch",
            "amazoncloudwatch": "cloudwatch",
            "cloudwatchevents": "events",
            "cloudtrail": "cloudtrail",
            "cloudformation": "cloudformation",
            "config": "config",
            "ssm": "ssm",
            "organizations": "organizations",
            # Security & Identity
            "acm": "acm",
            "kms": "kms",
            "keymanagementservice": "kms",
            "secretsmanager": "secretsmanager",
            "wa": "wa",
            "wafv2": "wafv2",
            "shield": "shield",
            # Storage
            "efs": "efs",
            "fsx": "fsx",
            "backup": "backup",
            # Database
            "elasticache": "elasticache",
            "redshift": "redshift",
            "neptune": "neptune",
            "docdb": "docdb",
            "documentdb": "docdb",
            # Networking
            "elb": "elbv2",
            "elbv2": "elbv2",
            "route53": "route53",
            "cloudfront": "cloudfront",
            "directconnect": "directconnect",
            "apigateway": "apigateway",
            "apigatewayv2": "apigatewayv2",
            # Application Integration
            "sns": "sns",
            "sqs": "sqs",
            "kinesis": "kinesis",
            "stepfunctions": "stepfunctions",
            # Analytics
            "glue": "glue",
            "athena": "athena",
            "quicksight": "quicksight",
            "elasticsearch": "es",
            "opensearch": "opensearch",
            # Compute
            "ecs": "ecs",
            "eks": "eks",
            "batch": "batch",
            "elasticbeanstalk": "elasticbeanstalk",
            # Machine Learning
            "sagemaker": "sagemaker",
            "rekognition": "rekognition",
            "comprehend": "comprehend",
            "translate": "translate",
            # Developer Tools
            "codecommit": "codecommit",
            "codebuild": "codebuild",
            "codepipeline": "codepipeline",
            "codedeploy": "codedeploy",
            # Business Applications
            "workmail": "workmail",
            "amazonworkmail": "workmail",
            "connect": "connect",
            "chime": "chime",
            # Other
            "support": "support",
            "trustedadvisor": "support",
        }

        return service_client_mapping.get(service_lower)

    def _discover_service_dynamically(
        self, client_name: str, service_display_name: str, region: str
    ):
        """Dynamically discover resources for a service using its AWS API."""
        try:
            client = self.session.client(client_name, region_name=region)

            # Get all available operations for this client
            available_operations = client._service_model.operation_names

            # Common list operations that typically return resources
            list_operations = [
                op
                for op in available_operations
                if op.startswith(("List", "Describe", "Get"))
                and not any(
                    skip in op
                    for skip in ["Policy", "Version", "Status", "Health", "Metrics"]
                )
            ]

            # Priority list operations (most likely to return actual resources)
            priority_operations = [
                op
                for op in list_operations
                if any(
                    keyword in op
                    for keyword in [
                        "List",
                        "DescribeInstances",
                        "DescribeVolumes",
                        "DescribeClusters",
                        "DescribeServices",
                        "DescribeTables",
                        "DescribeBuckets",
                        "DescribeFunctions",
                        "DescribeStacks",
                        "DescribeAlarms",
                        "DescribeRules",
                        "DescribeKeys",
                        "DescribeCertificates",
                        "DescribeQueues",
                        "DescribeTopics",
                    ]
                )
            ]

            operations_to_try = (
                priority_operations[:5] if priority_operations else list_operations[:3]
            )

            self.logger.debug(
                f"Trying {len(operations_to_try)} operations for {service_display_name} in {region}"
            )

            for operation_name in operations_to_try:
                try:
                    self._call_operation_and_extract_resources(
                        client, operation_name, service_display_name, region
                    )
                except Exception as e:
                    self.logger.debug(
                        f"Operation {operation_name} failed for {service_display_name}: {e}"
                    )
                    continue

        except Exception as e:
            self.logger.warning(
                f"Failed to create client for {client_name} in {region}: {e}"
            )

    def _call_operation_and_extract_resources(
        self, client, operation_name: str, service_name: str, region: str
    ):
        """Call an AWS API operation and generically extract resource information."""
        try:
            # Get the operation model to understand parameters
            operation_model = client._service_model.operation_model(operation_name)

            # Convert PascalCase operation name to snake_case for boto3
            snake_case_operation = self._pascal_to_snake_case(operation_name)
            operation = getattr(client, snake_case_operation)

            # Handle paginated operations
            if hasattr(client, "get_paginator"):
                try:
                    paginator = client.get_paginator(snake_case_operation)
                    response_data = []
                    for page in paginator.paginate():
                        response_data.append(page)
                except Exception:
                    # Fallback to direct call
                    response_data = [operation()]
            else:
                response_data = [operation()]

            # Extract resources from the response
            for response in response_data:
                self._extract_resources_from_response(
                    response, service_name, region, operation_name
                )

        except Exception as e:
            # Don't log every failed operation as it's expected for some services
            raise

    def _extract_resources_from_response(
        self, response: dict, service_name: str, region: str, operation_name: str
    ):
        """Extract resource information from AWS API response generically."""
        if not isinstance(response, dict):
            return

        # Common response keys that contain resource lists
        resource_list_keys = [
            # Generic patterns
            key
            for key in response.keys()
            if any(
                pattern in key
                for pattern in [
                    "List",
                    "Items",
                    "Resources",
                    "Results",
                    "Stacks",
                    "Instances",
                    "Volumes",
                    "Buckets",
                    "Functions",
                    "Tables",
                    "Clusters",
                    "Services",
                    "Alarms",
                    "Rules",
                    "Keys",
                    "Certificates",
                    "Queues",
                    "Topics",
                    "Databases",
                    "Snapshots",
                    "Images",
                    "Groups",
                    "Policies",
                ]
            )
        ]

        for key in resource_list_keys:
            resource_list = response.get(key, [])
            if isinstance(resource_list, list):
                for resource_data in resource_list:
                    if isinstance(resource_data, dict):
                        self._create_resource_from_api_data(
                            resource_data, service_name, region, operation_name, key
                        )

    def _create_resource_from_api_data(
        self,
        resource_data: dict,
        service_name: str,
        region: str,
        operation_name: str,
        list_key: str,
    ):
        """Create a standardized resource entry from AWS API data."""
        try:
            # Extract common fields that most AWS resources have
            resource_id = self._extract_resource_id(resource_data)
            resource_name = self._extract_resource_name(resource_data)
            resource_arn = resource_data.get("Arn") or resource_data.get("ARN") or ""

            if not resource_id:
                return  # Skip if we can't identify the resource

            # Determine resource type from the operation name and data
            resource_type = self._determine_resource_type(
                operation_name, list_key, resource_data
            )

            # Extract tags if present
            tags = self._extract_tags(resource_data)

            # Create the standardized resource entry
            resource_entry = {
                "service": service_name,
                "type": resource_type,
                "region": region,
                "id": resource_id,
                "name": resource_name or resource_id,
                "arn": resource_arn,
                "tags": tags,
                "discovered_via": "DynamicDiscovery",
                "api_operation": operation_name,
                "discovered_at": datetime.utcnow().isoformat(),
                "raw_data": resource_data,  # Include raw data for debugging/enhancement
            }

            self.resources.append(resource_entry)

        except Exception as e:
            self.logger.debug(f"Failed to create resource from API data: {e}")

    def _extract_resource_id(self, resource_data: dict) -> Optional[str]:
        """Extract resource ID from AWS API response data."""
        # Common ID fields in AWS API responses (prioritized order)
        id_fields = [
            # Primary identifiers
            "Id",
            "ResourceId",
            "InstanceId",
            "VolumeId",
            "ClusterId",
            "ServiceName",
            "FunctionName",
            "TableName",
            "BucketName",
            "StackName",
            "AlarmName",
            "RuleName",
            "KeyId",
            "Name",
            # ARN-based identifiers (extract ID from ARN)
            "CertificateArn",
            "TopicArn",
            "QueueUrl",
            "RoleArn",
            "PolicyArn",
            # Database identifiers
            "DBInstanceIdentifier",
            "DBClusterIdentifier",
            "DBSubnetGroupName",
            # API Gateway identifiers
            "RestApiId",
            "ApiId",
            "DomainName",
            # User/Auth identifiers
            "UserPoolId",
            "IdentityPoolId",
            "UserName",
            # Network identifiers
            "VpcId",
            "SubnetId",
            "SecurityGroupId",
            "NetworkInterfaceId",
            # Route53 identifiers
            "HostedZoneId",
            "RecordName",
        ]

        for field in id_fields:
            if field in resource_data and resource_data[field]:
                value = str(resource_data[field])

                # Extract ID from ARN if needed
                if value.startswith("arn:aws:"):
                    # ARN format: arn:partition:service:region:account:resourcetype/resourcename
                    try:
                        arn_parts = value.split(":")
                        if len(arn_parts) >= 6:
                            resource_part = arn_parts[5]
                            if "/" in resource_part:
                                return resource_part.split("/")[-1]  # Get resource name
                            return resource_part
                    except Exception:
                        pass

                return value

        # Fallback: look for any string field that could be an identifier
        fallback_patterns = ["identifier", "re", "reference", "key", "token"]
        for key, value in resource_data.items():
            if isinstance(value, str) and len(value) > 0 and len(value) < 200:
                key_lower = key.lower()
                if any(pattern in key_lower for pattern in fallback_patterns):
                    return value

        # Last resort: use the first meaningful string field
        for key, value in resource_data.items():
            if isinstance(value, str) and len(value) > 0 and len(value) < 200:
                # Skip metadata fields
                if key.lower() not in [
                    "status",
                    "state",
                    "type",
                    "kind",
                    "description",
                ]:
                    return value

        return None

    def _extract_resource_name(self, resource_data: dict) -> Optional[str]:
        """Extract resource name from AWS API response data."""
        name_fields = [
            # Primary name fields
            "Name",
            "ResourceName",
            "DisplayName",
            "Title",
            "Label",
            # Service-specific name fields
            "BucketName",
            "TableName",
            "FunctionName",
            "StackName",
            "AlarmName",
            "RuleName",
            "ClusterName",
            "ServiceName",
            "DomainName",
            # Tag-based naming
            "Tags.Name",
            "TagList.Name",
        ]

        for field in name_fields:
            if field in resource_data and resource_data[field]:
                return str(resource_data[field])

        # Check tags for Name tag
        if "Tags" in resource_data:
            tags = resource_data["Tags"]
            if isinstance(tags, list):
                # List of {"Key": "Name", "Value": "value"} format
                for tag in tags:
                    if isinstance(tag, dict) and tag.get("Key") == "Name":
                        return str(tag.get("Value", ""))
            elif isinstance(tags, dict):
                # Direct key-value mapping
                if "Name" in tags:
                    return str(tags["Name"])

        # For ARN-based resources, extract meaningful name from ARN
        for arn_field in ["Arn", "ARN", "CertificateArn", "TopicArn", "RoleArn"]:
            if arn_field in resource_data:
                arn = str(resource_data[arn_field])
                if arn.startswith("arn:aws:"):
                    try:
                        # Extract resource name from ARN
                        resource_part = arn.split(":")[-1]
                        if "/" in resource_part:
                            return resource_part.split("/")[-1]
                        return resource_part
                    except Exception:
                        pass

        return None

    def _determine_resource_type(
        self, operation_name: str, list_key: str, resource_data: dict
    ) -> str:
        """Determine resource type from operation name, response key, and data."""
        # First check for explicit type fields in resource data
        type_fields = [
            "Type",
            "ResourceType",
            "ServiceType",
            "InstanceType",
            "AlarmType",
        ]
        for field in type_fields:
            if field in resource_data and resource_data[field]:
                return str(resource_data[field])

        # Service-specific type determination
        if "CertificateArn" in resource_data:
            return "Certificate"
        elif "HostedZoneId" in resource_data:
            return "Hosted Zone"
        elif "BucketName" in resource_data:
            return "Bucket"
        elif "TableName" in resource_data:
            return "Table"
        elif "FunctionName" in resource_data:
            return "Function"
        elif "StackName" in resource_data:
            return "Stack"
        elif "AlarmName" in resource_data:
            return "Alarm"
        elif "RuleName" in resource_data:
            return "Rule"
        elif "KeyId" in resource_data:
            return "Key"
        elif "ClusterName" in resource_data or "ClusterId" in resource_data:
            return "Cluster"
        elif "InstanceId" in resource_data:
            return "Instance"
        elif "VolumeId" in resource_data:
            return "Volume"
        elif "VpcId" in resource_data:
            return "VPC"
        elif "SubnetId" in resource_data:
            return "Subnet"

        # Infer from response list key
        if list_key:
            key_mappings = {
                "CertificateSummaryList": "Certificate",
                "HostedZones": "Hosted Zone",
                "Buckets": "Bucket",
                "TableNames": "Table",
                "Functions": "Function",
                "Stacks": "Stack",
                "MetricAlarms": "Alarm",
                "Rules": "Rule",
                "Keys": "Key",
                "Clusters": "Cluster",
                "Instances": "Instance",
                "Volumes": "Volume",
            }
            if list_key in key_mappings:
                return key_mappings[list_key]

        # Extract from operation name as fallback
        if operation_name.startswith("Describe"):
            type_from_op = operation_name[8:]  # Remove 'Describe'
        elif operation_name.startswith("List"):
            type_from_op = operation_name[4:]  # Remove 'List'
        elif operation_name.startswith("Get"):
            type_from_op = operation_name[3:]  # Remove 'Get'
        else:
            type_from_op = operation_name

        # Clean up the type name
        type_from_op = type_from_op.rstrip("s")  # Remove plural 's'

        # Apply common transformations
        type_transformations = {
            "Certificate": "Certificate",
            "HostedZone": "Hosted Zone",
            "MetricAlarm": "Alarm",
            "EventRule": "Rule",
            "DatabaseCluster": "DB Cluster",
            "DatabaseInstance": "DB Instance",
        }

        return type_transformations.get(type_from_op, type_from_op)

    def _extract_tags(self, resource_data: dict) -> dict:
        """Extract tags from AWS API response data."""
        tags = {}

        # Different tag formats in AWS APIs
        if "Tags" in resource_data:
            tag_data = resource_data["Tags"]
            if isinstance(tag_data, list):
                # List of {"Key": "key", "Value": "value"} format
                for tag in tag_data:
                    if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                        tags[tag["Key"]] = tag["Value"]
            elif isinstance(tag_data, dict):
                # Direct key-value mapping
                tags.update(tag_data)

        elif "TagList" in resource_data:
            for tag in resource_data.get("TagList", []):
                if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                    tags[tag["Key"]] = tag["Value"]

        return tags

    def _pascal_to_snake_case(self, pascal_string: str) -> str:
        """Convert PascalCase to snake_case for boto3 method names."""
        import re

        # Insert underscore before uppercase letters (except the first one)
        snake = re.sub("([a-z0-9])([A-Z])", r"\1_\2", pascal_string)
        return snake.lower()

    def _normalize_resource_type(self, service: str, resource_type: str) -> str:
        """Normalize resource type names for consistent display."""
        # Common normalizations
        normalizations = {
            # EC2 normalizations
            "instance": "Instance",
            "volume": "EBS Volume",
            "security-group": "Security Group",
            "snapshot": "EBS Snapshot",
            "image": "AMI",
            "key-pair": "Key Pair",
            "network-interface": "Network Interface",
            "vpc": "VPC",
            "subnet": "Subnet",
            "internet-gateway": "Internet Gateway",
            "nat-gateway": "NAT Gateway",
            "route-table": "Route Table",
            "network-acl": "Network ACL",
            "vpc-endpoint": "VPC Endpoint",
            # S3 normalizations
            "bucket": "Bucket",
            "object": "Object",
            # Lambda normalizations
            "function": "Function",
            "layer": "Layer",
            # RDS normalizations
            "db": "DB Instance",
            "cluster": "DB Cluster",
            "db-subnet-group": "DB Subnet Group",
            "db-parameter-group": "DB Parameter Group",
            # IAM normalizations
            "role": "Role",
            "user": "User",
            "group": "Group",
            "policy": "Policy",
            # CloudFormation
            "stack": "Stack",
            # ECS
            "cluster": "Cluster",
            "service": "Service",
            "task-definition": "Task Definition",
            # EKS
            "cluster": "Cluster",
            "nodegroup": "Node Group",
        }

        resource_type_lower = resource_type.lower()
        if resource_type_lower in normalizations:
            return normalizations[resource_type_lower]

        # Capitalize first letter as fallback
        return resource_type.replace("-", " ").replace("_", " ").title()

    def _matches_tag_filters(self, tags: Dict[str, str]) -> bool:
        """Check if resource tags match the specified tag filters."""
        if not self.tag_filters:
            return True

        for filter_key, filter_value in self.tag_filters.items():
            if filter_key not in tags:
                return False
            if isinstance(filter_value, str) and tags[filter_key] != filter_value:
                return False
            elif (
                isinstance(filter_value, list) and tags[filter_key] not in filter_value
            ):
                return False

        return True

    def _discover_legacy_service_resources(self):
        """Fallback to original hardcoded service discovery if ResourceGroupsTagging API fails."""
        self.logger.info("Using legacy service-specific discovery as fallback...")

        for region in self.regions:
            self.logger.info(f"Legacy scanning region: {region}")
            self._discover_ec2_resources_legacy(region)
            self._discover_s3_resources_legacy(region)
            self._discover_rds_resources_legacy(region)
            self._discover_lambda_resources_legacy(region)
            self._discover_iam_resources_legacy(region)
            self._discover_vpc_resources_legacy(region)
            self._discover_cloudformation_resources_legacy(region)
            self._discover_ecs_resources_legacy(region)
            self._discover_eks_resources_legacy(region)
            self._discover_cloudwatch_resources_legacy(region)

    def _discover_service_specific_resources(self):
        """Discover additional resources using service-specific APIs for enhanced details."""
        self.logger.info(
            "Running service-specific discovery for enhanced resource details..."
        )

        # Get existing services from ResourceGroupsTagging discovery
        discovered_services = set(r.get("service", "").upper() for r in self.resources)

        for region in self.regions:
            self.logger.info(f"Enhanced scanning region: {region}")

            # Always run core service discovery (these might not have tags)
            self._enhance_ec2_resources(region)
            self._enhance_vpc_resources(region)  # VPCs often don't have tags

            if region == "us-east-1":  # Global services
                self._enhance_s3_resources(region)  # S3 buckets might not have tags
                self._enhance_iam_resources(region)
                self._discover_route53_resources(region)  # Add Route53 discovery
                self._discover_cloudfront_resources(region)  # Add CloudFront discovery

            # Only run other service-specific discovery if found via RGT API
            if "RDS" in discovered_services:
                self._enhance_rds_resources(region)
            if "LAMBDA" in discovered_services:
                self._enhance_lambda_resources(region)
            if "CLOUDFORMATION" in discovered_services:
                self._enhance_cloudformation_resources(region)
            if "ECS" in discovered_services:
                self._enhance_ecs_resources(region)
            if "EKS" in discovered_services:
                self._enhance_eks_resources(region)
            if "CLOUDWATCH" in discovered_services:
                self._discover_cloudwatch_resources(region)

    def _deduplicate_resources(self):
        """Remove duplicate resources with smart deduplication and merge enhanced data."""
        seen_resources = {}
        deduplicated = []
        merge_stats = {"duplicates_removed": 0, "resources_enhanced": 0}

        for resource in self.resources:
            # Create comprehensive unique key
            unique_key = self._create_unique_resource_key(resource)

            if unique_key in seen_resources:
                # Merge resources - keep the one with more complete data
                existing_resource = seen_resources[unique_key]
                merged_resource = self._merge_resource_data(existing_resource, resource)
                seen_resources[unique_key] = merged_resource
                merge_stats["duplicates_removed"] += 1
                if merged_resource != existing_resource:
                    merge_stats["resources_enhanced"] += 1
            else:
                seen_resources[unique_key] = resource

        # Convert back to list, prioritizing resources with more complete data
        deduplicated = list(seen_resources.values())

        removed_count = len(self.resources) - len(deduplicated)
        if removed_count > 0:
            self.logger.info(
                f"Smart deduplication: removed {merge_stats['duplicates_removed']} duplicates, "
                f"enhanced {merge_stats['resources_enhanced']} resources with additional data"
            )

        self.resources = deduplicated

    def _create_unique_resource_key(self, resource: dict) -> str:
        """Create a comprehensive unique key for resource deduplication."""
        arn = resource.get("arn", "")
        if arn:
            return f"arn:{arn}"

        # Service-specific unique key generation
        service = resource.get("service", "").upper()
        resource_type = resource.get("type", "")
        resource_id = resource.get("id", "")
        region = resource.get("region", "")

        # Handle service-specific cases
        if service == "ROUTE53" or service == "ROUTE 53":
            # Route53 resources are global, use hosted zone ID or domain name
            return f"route53:{resource_id}:{resource.get('name', '')}"

        elif service == "S3":
            # S3 buckets are globally unique
            bucket_name = resource.get("name", "") or resource_id
            return f"s3:bucket:{bucket_name}"

        elif service == "VPC" or service == "EC2":
            # VPC resources need region specificity
            return f"vpc:{region}:{resource_type}:{resource_id}"

        elif service == "IAM":
            # IAM resources are global
            return f"iam:{resource_type}:{resource_id}"

        elif service == "CLOUDFRONT" or service == "CLOUDTRAIL":
            # Global services
            return f"{service.lower()}:{resource_id}"

        # Default case
        return f"{service.lower()}:{region}:{resource_type}:{resource_id}"

    def _merge_resource_data(self, existing: dict, new: dict) -> dict:
        """Merge two resource records, prioritizing completeness and accuracy."""
        # Start with the resource that has more fields
        if len(new) > len(existing):
            base_resource = new.copy()
            additional_resource = existing
        else:
            base_resource = existing.copy()
            additional_resource = new

        # Merge data intelligently
        for key, value in additional_resource.items():
            if key not in base_resource or not base_resource[key]:
                # Add missing data
                base_resource[key] = value
            elif key == "tags":
                # Merge tags
                base_tags = base_resource.get("tags", {})
                additional_tags = value if isinstance(value, dict) else {}
                base_resource["tags"] = {**base_tags, **additional_tags}
            elif key == "discovered_via":
                # Track all discovery methods
                existing_methods = base_resource.get("discovered_via", "")
                if value not in existing_methods:
                    base_resource["discovered_via"] = (
                        f"{existing_methods}+{value}" if existing_methods else value
                    )
            elif key in ["arn", "name"] and not base_resource.get(key):
                # Prefer non-empty ARNs and names
                base_resource[key] = value

        # Add merge metadata
        base_resource["data_sources"] = list(
            set(
                [
                    existing.get("discovered_via", "Unknown"),
                    new.get("discovered_via", "Unknown"),
                ]
            )
        )

        return base_resource

    # Legacy discovery methods (fallback when ResourceGroupsTagging API fails)
    def _discover_ec2_resources_legacy(self, region: str):
        """Legacy EC2 resource discovery method."""
        return self._enhance_ec2_resources(region)

    def _discover_s3_resources_legacy(self, region: str):
        """Legacy S3 resource discovery method."""
        return self._enhance_s3_resources(region)

    def _discover_rds_resources_legacy(self, region: str):
        """Legacy RDS resource discovery method."""
        return self._enhance_rds_resources(region)

    def _discover_lambda_resources_legacy(self, region: str):
        """Legacy Lambda resource discovery method."""
        return self._enhance_lambda_resources(region)

    def _discover_iam_resources_legacy(self, region: str):
        """Legacy IAM resource discovery method."""
        return self._enhance_iam_resources(region)

    def _discover_vpc_resources_legacy(self, region: str):
        """Legacy VPC resource discovery method."""
        return self._enhance_vpc_resources(region)

    def _discover_cloudformation_resources_legacy(self, region: str):
        """Legacy CloudFormation resource discovery method."""
        return self._enhance_cloudformation_resources(region)

    def _discover_ecs_resources_legacy(self, region: str):
        """Legacy ECS resource discovery method."""
        return self._enhance_ecs_resources(region)

    def _discover_eks_resources_legacy(self, region: str):
        """Legacy EKS resource discovery method."""
        return self._enhance_eks_resources(region)

    def _discover_cloudwatch_resources_legacy(self, region: str):
        """Legacy CloudWatch resource discovery method."""
        return self._discover_cloudwatch_resources(region)

    # Additional service discovery methods for billing-validated services
    def _discover_rds_comprehensive(self, region: str):
        """Comprehensive RDS discovery including all resource types."""
        try:
            rds = self.session.client("rds", region_name=region)

            # DB Instances, Clusters, Snapshots, Parameter Groups, etc.
            resources_found = []

            # DB Instances
            try:
                instances = rds.describe_db_instances()
                for instance in instances["DBInstances"]:
                    self.resources.append(
                        {
                            "service": "RDS",
                            "type": "DB Instance",
                            "region": region,
                            "id": instance["DBInstanceIdentifier"],
                            "name": instance["DBInstanceIdentifier"],
                            "arn": instance.get("DBInstanceArn", ""),
                            "engine": instance["Engine"],
                            "status": instance["DBInstanceStatus"],
                            "discovered_via": "BillingTargetedDiscovery",
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )
                    resources_found.append("DB Instance")
            except Exception as e:
                self.logger.warning(
                    f"Failed to discover RDS instances in {region}: {e}"
                )

            # DB Clusters
            try:
                clusters = rds.describe_db_clusters()
                for cluster in clusters["DBClusters"]:
                    self.resources.append(
                        {
                            "service": "RDS",
                            "type": "DB Cluster",
                            "region": region,
                            "id": cluster["DBClusterIdentifier"],
                            "name": cluster["DBClusterIdentifier"],
                            "arn": cluster.get("DBClusterArn", ""),
                            "engine": cluster["Engine"],
                            "status": cluster["Status"],
                            "discovered_via": "BillingTargetedDiscovery",
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )
                    resources_found.append("DB Cluster")
            except Exception as e:
                self.logger.warning(f"Failed to discover RDS clusters in {region}: {e}")

            if resources_found:
                self.logger.info(
                    f"RDS targeted discovery in {region}: {', '.join(set(resources_found))}"
                )

        except ClientError as e:
            self.logger.warning(f"RDS comprehensive discovery failed in {region}: {e}")

    def _discover_dynamodb_resources(self, region: str):
        """Discover DynamoDB resources."""
        try:
            dynamodb = self.session.client("dynamodb", region_name=region)

            tables = dynamodb.list_tables()
            for table_name in tables["TableNames"]:
                try:
                    table_details = dynamodb.describe_table(TableName=table_name)
                    table = table_details["Table"]

                    self.resources.append(
                        {
                            "service": "DYNAMODB",
                            "type": "Table",
                            "region": region,
                            "id": table_name,
                            "name": table_name,
                            "arn": table.get("TableArn", ""),
                            "status": table["TableStatus"],
                            "discovered_via": "BillingTargetedDiscovery",
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to get details for DynamoDB table {table_name}: {e}"
                    )

        except ClientError as e:
            self.logger.warning(f"DynamoDB discovery failed in {region}: {e}")

    def _discover_elasticache_resources(self, region: str):
        """Discover ElastiCache resources."""
        try:
            elasticache = self.session.client("elasticache", region_name=region)

            # Redis clusters
            try:
                redis_clusters = elasticache.describe_cache_clusters()
                for cluster in redis_clusters["CacheClusters"]:
                    self.resources.append(
                        {
                            "service": "ELASTICACHE",
                            "type": "Cache Cluster",
                            "region": region,
                            "id": cluster["CacheClusterId"],
                            "name": cluster["CacheClusterId"],
                            "engine": cluster["Engine"],
                            "status": cluster["CacheClusterStatus"],
                            "discovered_via": "BillingTargetedDiscovery",
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )
            except Exception as e:
                self.logger.warning(
                    f"Failed to discover ElastiCache clusters in {region}: {e}"
                )

        except ClientError as e:
            self.logger.warning(f"ElastiCache discovery failed in {region}: {e}")

    def _discover_redshift_resources(self, region: str):
        """Discover Redshift resources."""
        try:
            redshift = self.session.client("redshift", region_name=region)

            clusters = redshift.describe_clusters()
            for cluster in clusters["Clusters"]:
                self.resources.append(
                    {
                        "service": "REDSHIFT",
                        "type": "Cluster",
                        "region": region,
                        "id": cluster["ClusterIdentifier"],
                        "name": cluster["ClusterIdentifier"],
                        "status": cluster["ClusterStatus"],
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Redshift discovery failed in {region}: {e}")

    def _discover_elb_resources(self, region: str):
        """Discover ELB/ALB/NLB resources."""
        try:
            # ELBv2 (ALB/NLB)
            elbv2 = self.session.client("elbv2", region_name=region)
            load_balancers = elbv2.describe_load_balancers()

            for lb in load_balancers["LoadBalancers"]:
                self.resources.append(
                    {
                        "service": "ELB",
                        "type": f"{lb['Type'].upper()}",
                        "region": region,
                        "id": lb["LoadBalancerName"],
                        "name": lb["LoadBalancerName"],
                        "arn": lb["LoadBalancerArn"],
                        "status": lb["State"]["Code"],
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"ELB discovery failed in {region}: {e}")

    def _discover_apigateway_resources(self, region: str):
        """Discover API Gateway resources."""
        try:
            apigw = self.session.client("apigateway", region_name=region)

            # REST APIs
            rest_apis = apigw.get_rest_apis()
            for api in rest_apis["items"]:
                self.resources.append(
                    {
                        "service": "APIGATEWAY",
                        "type": "REST API",
                        "region": region,
                        "id": api["id"],
                        "name": api["name"],
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"API Gateway discovery failed in {region}: {e}")

    def _discover_sns_resources(self, region: str):
        """Discover SNS resources."""
        try:
            sns = self.session.client("sns", region_name=region)

            topics = sns.list_topics()
            for topic in topics["Topics"]:
                topic_arn = topic["TopicArn"]
                topic_name = topic_arn.split(":")[-1]

                self.resources.append(
                    {
                        "service": "SNS",
                        "type": "Topic",
                        "region": region,
                        "id": topic_name,
                        "name": topic_name,
                        "arn": topic_arn,
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"SNS discovery failed in {region}: {e}")

    def _discover_sqs_resources(self, region: str):
        """Discover SQS resources."""
        try:
            sqs = self.session.client("sqs", region_name=region)

            queues = sqs.list_queues()
            for queue_url in queues.get("QueueUrls", []):
                queue_name = queue_url.split("/")[-1]

                self.resources.append(
                    {
                        "service": "SQS",
                        "type": "Queue",
                        "region": region,
                        "id": queue_name,
                        "name": queue_name,
                        "queue_url": queue_url,
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"SQS discovery failed in {region}: {e}")

    def _discover_kinesis_resources(self, region: str):
        """Discover Kinesis resources."""
        try:
            kinesis = self.session.client("kinesis", region_name=region)

            streams = kinesis.list_streams()
            for stream_name in streams["StreamNames"]:
                self.resources.append(
                    {
                        "service": "KINESIS",
                        "type": "Stream",
                        "region": region,
                        "id": stream_name,
                        "name": stream_name,
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Kinesis discovery failed in {region}: {e}")

    def _discover_stepfunctions_resources(self, region: str):
        """Discover Step Functions resources."""
        try:
            sfn = self.session.client("stepfunctions", region_name=region)

            state_machines = sfn.list_state_machines()
            for sm in state_machines["stateMachines"]:
                self.resources.append(
                    {
                        "service": "STEPFUNCTIONS",
                        "type": "State Machine",
                        "region": region,
                        "id": sm["name"],
                        "name": sm["name"],
                        "arn": sm["stateMachineArn"],
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Step Functions discovery failed in {region}: {e}")

    def _discover_secretsmanager_resources(self, region: str):
        """Discover Secrets Manager resources."""
        try:
            secrets = self.session.client("secretsmanager", region_name=region)

            secret_list = secrets.list_secrets()
            for secret in secret_list["SecretList"]:
                self.resources.append(
                    {
                        "service": "SECRETSMANAGER",
                        "type": "Secret",
                        "region": region,
                        "id": secret["Name"],
                        "name": secret["Name"],
                        "arn": secret["ARN"],
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Secrets Manager discovery failed in {region}: {e}")

    def _discover_ssm_resources(self, region: str):
        """Discover Systems Manager resources."""
        try:
            ssm = self.session.client("ssm", region_name=region)

            # Parameters
            try:
                parameters = ssm.describe_parameters()
                for param in parameters["Parameters"]:
                    self.resources.append(
                        {
                            "service": "SSM",
                            "type": "Parameter",
                            "region": region,
                            "id": param["Name"],
                            "name": param["Name"],
                            "discovered_via": "BillingTargetedDiscovery",
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )
            except Exception as e:
                self.logger.warning(
                    f"Failed to discover SSM parameters in {region}: {e}"
                )

        except ClientError as e:
            self.logger.warning(f"SSM discovery failed in {region}: {e}")

    def _discover_route53_resources(self, region: str):
        """Discover Route53 resources (global service)."""
        if region != "us-east-1":  # Route53 is global
            return

        try:
            route53 = self.session.client("route53", region_name=region)

            hosted_zones = route53.list_hosted_zones()
            for zone in hosted_zones["HostedZones"]:
                self.resources.append(
                    {
                        "service": "ROUTE53",
                        "type": "Hosted Zone",
                        "region": "global",
                        "id": zone["Id"].split("/")[-1],
                        "name": zone["Name"],
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Route53 discovery failed: {e}")

    def _discover_cloudfront_resources(self, region: str):
        """Discover CloudFront resources (global service)."""
        if region != "us-east-1":  # CloudFront is global
            return

        try:
            cloudfront = self.session.client("cloudfront", region_name=region)

            distributions = cloudfront.list_distributions()
            for dist in distributions.get("DistributionList", {}).get("Items", []):
                self.resources.append(
                    {
                        "service": "CLOUDFRONT",
                        "type": "Distribution",
                        "region": "global",
                        "id": dist["Id"],
                        "name": dist.get("DomainName", dist["Id"]),
                        "status": dist["Status"],
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"CloudFront discovery failed: {e}")

    def _discover_acm_resources(self, region: str):
        """Discover ACM (Certificate Manager) resources."""
        try:
            acm = self.session.client("acm", region_name=region)

            certificates = acm.list_certificates()
            for cert in certificates["CertificateSummaryList"]:
                self.resources.append(
                    {
                        "service": "ACM",
                        "type": "Certificate",
                        "region": region,
                        "id": cert["CertificateArn"].split("/")[-1],
                        "name": cert["DomainName"],
                        "arn": cert["CertificateArn"],
                        "status": cert["Status"],
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"ACM discovery failed in {region}: {e}")

    def _discover_waf_resources(self, region: str):
        """Discover WAF resources."""
        try:
            waf = self.session.client("wafv2", region_name=region)

            # Web ACLs
            web_acls = waf.list_web_acls(Scope="REGIONAL")
            for acl in web_acls["WebACLs"]:
                self.resources.append(
                    {
                        "service": "WAF",
                        "type": "Web ACL",
                        "region": region,
                        "id": acl["Id"],
                        "name": acl["Name"],
                        "arn": acl["ARN"],
                        "discovered_via": "BillingTargetedDiscovery",
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"WAF discovery failed in {region}: {e}")

    def _enhance_ec2_resources(self, region: str):
        """Enhance EC2 resources with additional details from EC2 API."""
        try:
            ec2 = self.session.client("ec2", region_name=region)

            # EC2 Instances
            instances = ec2.describe_instances()
            for reservation in instances["Reservations"]:
                for instance in reservation["Instances"]:
                    self.resources.append(
                        {
                            "service": "EC2",
                            "type": "Instance",
                            "region": region,
                            "id": instance["InstanceId"],
                            "name": self._get_tag_value(
                                instance.get("Tags", []), "Name"
                            ),
                            "state": instance["State"]["Name"],
                            "instance_type": instance["InstanceType"],
                            "vpc_id": instance.get("VpcId"),
                            "subnet_id": instance.get("SubnetId"),
                            "launch_time": (
                                instance["LaunchTime"].isoformat()
                                if "LaunchTime" in instance
                                else None
                            ),
                            "tags": {
                                tag["Key"]: tag["Value"]
                                for tag in instance.get("Tags", [])
                            },
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )

            # EBS Volumes
            volumes = ec2.describe_volumes()
            for volume in volumes["Volumes"]:
                self.resources.append(
                    {
                        "service": "EC2",
                        "type": "EBS Volume",
                        "region": region,
                        "id": volume["VolumeId"],
                        "name": self._get_tag_value(volume.get("Tags", []), "Name"),
                        "state": volume["State"],
                        "size": volume["Size"],
                        "volume_type": volume["VolumeType"],
                        "availability_zone": volume["AvailabilityZone"],
                        "encrypted": volume["Encrypted"],
                        "tags": {
                            tag["Key"]: tag["Value"] for tag in volume.get("Tags", [])
                        },
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

            # Security Groups
            security_groups = ec2.describe_security_groups()
            for sg in security_groups["SecurityGroups"]:
                self.resources.append(
                    {
                        "service": "EC2",
                        "type": "Security Group",
                        "region": region,
                        "id": sg["GroupId"],
                        "name": sg["GroupName"],
                        "description": sg["Description"],
                        "vpc_id": sg.get("VpcId"),
                        "tags": {
                            tag["Key"]: tag["Value"] for tag in sg.get("Tags", [])
                        },
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Failed to discover EC2 resources in {region}: {e}")

    def _enhance_s3_resources(self, region: str):
        """Enhance S3 resources with additional details from S3 API."""
        try:
            s3 = self.session.client("s3", region_name=region)

            # S3 Buckets (global service, only check once)
            if region == "us-east-1":  # Only check from one region
                buckets = s3.list_buckets()
                for bucket in buckets["Buckets"]:
                    try:
                        bucket_region = s3.get_bucket_location(Bucket=bucket["Name"])[
                            "LocationConstraint"
                        ]
                        bucket_region = bucket_region or "us-east-1"

                        # Get bucket tags
                        try:
                            tags_response = s3.get_bucket_tagging(Bucket=bucket["Name"])
                            tags = {
                                tag["Key"]: tag["Value"]
                                for tag in tags_response.get("TagSet", [])
                            }
                        except ClientError:
                            tags = {}

                        self.resources.append(
                            {
                                "service": "S3",
                                "type": "Bucket",
                                "region": bucket_region,
                                "id": bucket["Name"],
                                "name": bucket["Name"],
                                "creation_date": bucket["CreationDate"].isoformat(),
                                "tags": tags,
                                "discovered_at": datetime.utcnow().isoformat(),
                            }
                        )
                    except ClientError as e:
                        self.logger.warning(
                            f"Failed to get details for S3 bucket {bucket['Name']}: {e}"
                        )

        except ClientError as e:
            self.logger.warning(f"Failed to discover S3 resources: {e}")

    def _enhance_rds_resources(self, region: str):
        """Enhance RDS resources with additional details from RDS API."""
        try:
            rds = self.session.client("rds", region_name=region)

            # RDS Instances
            instances = rds.describe_db_instances()
            for instance in instances["DBInstances"]:
                # Get tags
                try:
                    tags_response = rds.list_tags_for_resource(
                        ResourceName=instance["DBInstanceArn"]
                    )
                    tags = {
                        tag["Key"]: tag["Value"]
                        for tag in tags_response.get("TagList", [])
                    }
                except ClientError:
                    tags = {}

                self.resources.append(
                    {
                        "service": "RDS",
                        "type": "DB Instance",
                        "region": region,
                        "id": instance["DBInstanceIdentifier"],
                        "name": instance["DBInstanceIdentifier"],
                        "engine": instance["Engine"],
                        "engine_version": instance["EngineVersion"],
                        "instance_class": instance["DBInstanceClass"],
                        "status": instance["DBInstanceStatus"],
                        "allocated_storage": instance.get("AllocatedStorage"),
                        "vpc_id": instance.get("DbSubnetGroup", {}).get("VpcId"),
                        "tags": tags,
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Failed to discover RDS resources in {region}: {e}")

    def _enhance_lambda_resources(self, region: str):
        """Enhance Lambda resources with additional details from Lambda API."""
        try:
            lambda_client = self.session.client("lambda", region_name=region)

            functions = lambda_client.list_functions()
            for function in functions["Functions"]:
                # Get tags
                try:
                    tags_response = lambda_client.list_tags(
                        Resource=function["FunctionArn"]
                    )
                    tags = tags_response.get("Tags", {})
                except ClientError:
                    tags = {}

                self.resources.append(
                    {
                        "service": "Lambda",
                        "type": "Function",
                        "region": region,
                        "id": function["FunctionName"],
                        "name": function["FunctionName"],
                        "runtime": function["Runtime"],
                        "memory_size": function["MemorySize"],
                        "timeout": function["Timeout"],
                        "last_modified": function["LastModified"],
                        "tags": tags,
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Failed to discover Lambda resources in {region}: {e}")

    def _enhance_iam_resources(self, region: str):
        """Enhance IAM resources with additional details from IAM API (global service, only check once)."""
        if region != "us-east-1":  # IAM is global, only check from one region
            return

        try:
            iam = self.session.client("iam")

            # IAM Roles
            roles = iam.list_roles()
            for role in roles["Roles"]:
                # Get tags
                try:
                    tags_response = iam.list_role_tags(RoleName=role["RoleName"])
                    tags = {
                        tag["Key"]: tag["Value"]
                        for tag in tags_response.get("Tags", [])
                    }
                except ClientError:
                    tags = {}

                self.resources.append(
                    {
                        "service": "IAM",
                        "type": "Role",
                        "region": "global",
                        "id": role["RoleName"],
                        "name": role["RoleName"],
                        "path": role["Path"],
                        "create_date": role["CreateDate"].isoformat(),
                        "tags": tags,
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

            # IAM Users
            users = iam.list_users()
            for user in users["Users"]:
                # Get tags
                try:
                    tags_response = iam.list_user_tags(UserName=user["UserName"])
                    tags = {
                        tag["Key"]: tag["Value"]
                        for tag in tags_response.get("Tags", [])
                    }
                except ClientError:
                    tags = {}

                self.resources.append(
                    {
                        "service": "IAM",
                        "type": "User",
                        "region": "global",
                        "id": user["UserName"],
                        "name": user["UserName"],
                        "path": user["Path"],
                        "create_date": user["CreateDate"].isoformat(),
                        "tags": tags,
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Failed to discover IAM resources: {e}")

    def _enhance_vpc_resources(self, region: str):
        """Enhance VPC resources with additional details from VPC API."""
        try:
            ec2 = self.session.client("ec2", region_name=region)

            # VPCs
            vpcs = ec2.describe_vpcs()
            for vpc in vpcs["Vpcs"]:
                self.resources.append(
                    {
                        "service": "VPC",
                        "type": "VPC",
                        "region": region,
                        "id": vpc["VpcId"],
                        "name": self._get_tag_value(vpc.get("Tags", []), "Name"),
                        "cidr_block": vpc["CidrBlock"],
                        "state": vpc["State"],
                        "is_default": vpc["IsDefault"],
                        "tags": {
                            tag["Key"]: tag["Value"] for tag in vpc.get("Tags", [])
                        },
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

            # Subnets
            subnets = ec2.describe_subnets()
            for subnet in subnets["Subnets"]:
                self.resources.append(
                    {
                        "service": "VPC",
                        "type": "Subnet",
                        "region": region,
                        "id": subnet["SubnetId"],
                        "name": self._get_tag_value(subnet.get("Tags", []), "Name"),
                        "vpc_id": subnet["VpcId"],
                        "cidr_block": subnet["CidrBlock"],
                        "availability_zone": subnet["AvailabilityZone"],
                        "available_ip_count": subnet["AvailableIpAddressCount"],
                        "tags": {
                            tag["Key"]: tag["Value"] for tag in subnet.get("Tags", [])
                        },
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Failed to discover VPC resources in {region}: {e}")

    def _enhance_cloudformation_resources(self, region: str):
        """Enhance CloudFormation resources with additional details from CloudFormation API."""
        try:
            cf = self.session.client("cloudformation", region_name=region)

            stacks = cf.list_stacks(
                StackStatusFilter=[
                    "CREATE_COMPLETE",
                    "UPDATE_COMPLETE",
                    "ROLLBACK_COMPLETE",
                ]
            )
            for stack in stacks["StackSummaries"]:
                # Get stack tags
                try:
                    stack_details = cf.describe_stacks(StackName=stack["StackName"])
                    tags = {
                        tag["Key"]: tag["Value"]
                        for tag in stack_details["Stacks"][0].get("Tags", [])
                    }
                except ClientError:
                    tags = {}

                self.resources.append(
                    {
                        "service": "CloudFormation",
                        "type": "Stack",
                        "region": region,
                        "id": stack["StackName"],
                        "name": stack["StackName"],
                        "status": stack["StackStatus"],
                        "creation_time": stack["CreationTime"].isoformat(),
                        "tags": tags,
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(
                f"Failed to discover CloudFormation resources in {region}: {e}"
            )

    def _enhance_ecs_resources(self, region: str):
        """Enhance ECS resources with additional details from ECS API."""
        try:
            ecs = self.session.client("ecs", region_name=region)

            # ECS Clusters
            clusters = ecs.list_clusters()
            for cluster_arn in clusters["clusterArns"]:
                cluster_details = ecs.describe_clusters(clusters=[cluster_arn])
                for cluster in cluster_details["clusters"]:
                    # Get tags
                    try:
                        tags_response = ecs.list_tags_for_resource(
                            resourceArn=cluster_arn
                        )
                        tags = {
                            tag["key"]: tag["value"]
                            for tag in tags_response.get("tags", [])
                        }
                    except ClientError:
                        tags = {}

                    self.resources.append(
                        {
                            "service": "ECS",
                            "type": "Cluster",
                            "region": region,
                            "id": cluster["clusterName"],
                            "name": cluster["clusterName"],
                            "status": cluster["status"],
                            "running_tasks": cluster["runningTasksCount"],
                            "pending_tasks": cluster["pendingTasksCount"],
                            "active_services": cluster["activeServicesCount"],
                            "tags": tags,
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )

        except ClientError as e:
            self.logger.warning(f"Failed to discover ECS resources in {region}: {e}")

    def _enhance_eks_resources(self, region: str):
        """Enhance EKS resources with additional details from EKS API."""
        try:
            eks = self.session.client("eks", region_name=region)

            clusters = eks.list_clusters()
            for cluster_name in clusters["clusters"]:
                cluster_details = eks.describe_cluster(name=cluster_name)
                cluster = cluster_details["cluster"]

                self.resources.append(
                    {
                        "service": "EKS",
                        "type": "Cluster",
                        "region": region,
                        "id": cluster["name"],
                        "name": cluster["name"],
                        "status": cluster["status"],
                        "version": cluster["version"],
                        "endpoint": cluster.get("endpoint"),
                        "created_at": (
                            cluster["createdAt"].isoformat()
                            if "createdAt" in cluster
                            else None
                        ),
                        "tags": cluster.get("tags", {}),
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(f"Failed to discover EKS resources in {region}: {e}")

    def _discover_cloudwatch_resources(self, region: str):
        """Discover CloudWatch resources using CloudWatch API."""
        try:
            cw = self.session.client("cloudwatch", region_name=region)

            # CloudWatch Alarms
            alarms = cw.describe_alarms()
            for alarm in alarms["MetricAlarms"]:
                self.resources.append(
                    {
                        "service": "CloudWatch",
                        "type": "Alarm",
                        "region": region,
                        "id": alarm["AlarmName"],
                        "name": alarm["AlarmName"],
                        "description": alarm.get("AlarmDescription"),
                        "state": alarm["StateValue"],
                        "metric_name": alarm["MetricName"],
                        "namespace": alarm["Namespace"],
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(
                f"Failed to discover CloudWatch resources in {region}: {e}"
            )

    def _get_tag_value(self, tags: List[Dict], key: str) -> Optional[str]:
        """Get tag value by key."""
        for tag in tags:
            if tag["Key"] == key:
                return tag["Value"]
        return None

    def _discover_cloudtrail_resources(self, region: str):
        """Discover CloudTrail resources."""
        try:
            client = self.session.client("cloudtrail", region_name=region)

            # CloudTrail trails
            trails_response = client.describe_trails()
            for trail in trails_response["trailList"]:
                self.resources.append(
                    {
                        "service": "CloudTrail",
                        "type": "Trail",
                        "region": region,
                        "id": trail["Name"],
                        "name": trail["Name"],
                        "arn": trail.get("TrailARN", ""),
                        "home_region": trail.get("HomeRegion", ""),
                        "is_multi_region": trail.get(
                            "IncludeGlobalServiceEvents", False
                        ),
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(
                f"Failed to discover CloudTrail resources in {region}: {e}"
            )

    def _discover_kms_resources(self, region: str):
        """Discover KMS resources."""
        try:
            client = self.session.client("kms", region_name=region)

            # KMS keys
            keys_response = client.list_keys()
            for key in keys_response["Keys"]:
                try:
                    key_details = client.describe_key(KeyId=key["KeyId"])
                    key_metadata = key_details["KeyMetadata"]

                    self.resources.append(
                        {
                            "service": "KMS",
                            "type": "Key",
                            "region": region,
                            "id": key["KeyId"],
                            "name": key_metadata.get("Description", ""),
                            "arn": key_metadata.get("Arn", ""),
                            "key_usage": key_metadata.get("KeyUsage", ""),
                            "key_state": key_metadata.get("KeyState", ""),
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )
                except ClientError as key_error:
                    # Skip keys we can't access
                    continue

        except ClientError as e:
            self.logger.warning(f"Failed to discover KMS resources in {region}: {e}")

    def _discover_glue_resources(self, region: str):
        """Discover Glue resources."""
        try:
            client = self.session.client("glue", region_name=region)

            # Glue databases
            try:
                databases_response = client.get_databases()
                for database in databases_response["DatabaseList"]:
                    self.resources.append(
                        {
                            "service": "Glue",
                            "type": "Database",
                            "region": region,
                            "id": database["Name"],
                            "name": database["Name"],
                            "description": database.get("Description", ""),
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )
            except ClientError:
                pass  # Skip if no permissions

            # Glue tables
            try:
                tables_response = client.get_tables()
                for table in tables_response["TableList"]:
                    self.resources.append(
                        {
                            "service": "Glue",
                            "type": "Table",
                            "region": region,
                            "id": table["Name"],
                            "name": table["Name"],
                            "database": table.get("DatabaseName", ""),
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )
            except ClientError:
                pass  # Skip if no permissions

        except ClientError as e:
            self.logger.warning(f"Failed to discover Glue resources in {region}: {e}")

    def _discover_cloudwatch_events_resources(self, region: str):
        """Discover CloudWatch Events resources."""
        try:
            client = self.session.client("events", region_name=region)

            # EventBridge rules
            rules_response = client.list_rules()
            for rule in rules_response["Rules"]:
                self.resources.append(
                    {
                        "service": "CloudWatch Events",
                        "type": "Rule",
                        "region": region,
                        "id": rule["Name"],
                        "name": rule["Name"],
                        "arn": rule.get("Arn", ""),
                        "state": rule.get("State", ""),
                        "description": rule.get("Description", ""),
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

            # Event buses
            buses_response = client.list_event_buses()
            for bus in buses_response["EventBuses"]:
                self.resources.append(
                    {
                        "service": "CloudWatch Events",
                        "type": "Event Bus",
                        "region": region,
                        "id": bus["Name"],
                        "name": bus["Name"],
                        "arn": bus.get("Arn", ""),
                        "discovered_at": datetime.utcnow().isoformat(),
                    }
                )

        except ClientError as e:
            self.logger.warning(
                f"Failed to discover CloudWatch Events resources in {region}: {e}"
            )

    def _discover_workmail_resources(self, region: str):
        """Discover WorkMail resources."""
        try:
            client = self.session.client("workmail", region_name=region)

            # WorkMail organizations
            try:
                orgs_response = client.list_organizations()
                for org in orgs_response["OrganizationSummaries"]:
                    self.resources.append(
                        {
                            "service": "WorkMail",
                            "type": "Organization",
                            "region": region,
                            "id": org["OrganizationId"],
                            "name": org.get("Alias", org["OrganizationId"]),
                            "state": org.get("State", ""),
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    )
            except ClientError as e:
                if (
                    e.response.get("Error", {}).get("Code")
                    == "OrganizationNotFoundException"
                ):
                    # No WorkMail organizations in this region
                    pass
                else:
                    raise

        except ClientError as e:
            self.logger.warning(
                f"Failed to discover WorkMail resources in {region}: {e}"
            )

    def save_to_file(self, filename: str, format_type: str = "json"):
        """Save resources to file."""
        if format_type.lower() == "json":
            with open(filename, "w") as f:
                json.dump(self.resources, f, indent=2, default=str)
        elif format_type.lower() == "yaml":
            with open(filename, "w") as f:
                yaml.dump(
                    self.resources,
                    f,
                    default_flow_style=False,
                    default_style="",
                    allow_unicode=True,
                )
        else:
            raise ValueError("Format must be 'json' or 'yaml'")

        self.logger.info(f"Resources saved to {filename}")

    def upload_to_s3(self, bucket_name: str, key: str, format_type: str = "json"):
        """Upload resources to S3."""
        try:
            s3 = self.session.client("s3")

            if format_type.lower() == "json":
                content = json.dumps(self.resources, indent=2, default=str)
                content_type = "application/json"
            elif format_type.lower() == "yaml":
                content = yaml.dump(
                    self.resources,
                    default_flow_style=False,
                    default_style="",
                    allow_unicode=True,
                )
                content_type = "text/yaml"
            else:
                raise ValueError("Format must be 'json' or 'yaml'")

            s3.put_object(
                Bucket=bucket_name, Key=key, Body=content, ContentType=content_type
            )

            self.logger.info(f"Resources uploaded to s3://{bucket_name}/{key}")

        except ClientError as e:
            self.logger.error(f"Failed to upload to S3: {e}")
            raise

    def discover_all_resources(self) -> List[Dict[str, Any]]:
        """Alias for discover_resources() for backward compatibility."""
        return self.discover_resources()
