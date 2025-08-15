#!/usr/bin/env python3
"""
Service Attribute Enrichment Framework

Provides dynamic service discovery and attribute enrichment for AWS resources.
Extracted and enhanced from existing aws_resource_inventory.py patterns.
"""

import boto3
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set, Type
from botocore.exceptions import ClientError
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ServiceDiscoveryResult:
    """Result of service discovery operation."""

    service: str
    resource_type: str
    discovered_services: Set[str]
    unknown_services: Set[str]
    enrichment_success: bool
    error_message: Optional[str] = None


class ServiceHandler(ABC):
    """Base class for service-specific attribute handlers."""

    def __init__(self, session: boto3.Session):
        """Initialize service handler with AWS session."""
        self.session = session
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._read_only_operations = self._define_read_only_operations()

    @abstractmethod
    def can_handle(self, service: str, resource_type: str) -> bool:
        """Check if this handler can process the service/resource type."""
        pass

    @abstractmethod
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich resource with service-specific attributes."""
        pass

    @abstractmethod
    def _define_read_only_operations(self) -> List[str]:
        """Define list of read-only operations this handler uses."""
        pass

    def get_read_only_operations(self) -> List[str]:
        """Return list of read-only operations this handler uses."""
        return self._read_only_operations

    def validate_read_only_operation(self, operation_name: str) -> bool:
        """Validate that an operation is read-only."""
        read_only_prefixes = [
            "describe",
            "get",
            "list",
            "head",
            "select",
            "query",
            "scan",
            "batch_get",
            "lookup",
        ]

        # Check if operation starts with read-only prefix (case insensitive)
        operation_lower = operation_name.lower()
        for prefix in read_only_prefixes:
            if operation_lower.startswith(prefix):
                return True

        # Check against explicitly defined read-only operations
        return operation_name in self._read_only_operations

    def _safe_api_call(self, client, operation_name: str, **kwargs) -> Optional[Dict]:
        """Safely execute API call with read-only validation."""
        if not self.validate_read_only_operation(operation_name):
            self.logger.warning(
                f"Operation {operation_name} is not validated as read-only"
            )
            return None

        try:
            operation = getattr(client, operation_name)
            return operation(**kwargs)
        except ClientError as e:
            self.logger.debug(f"API call {operation_name} failed: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"Unexpected error in {operation_name}: {e}")
            return None


class DynamicServiceHandler(ServiceHandler):
    """Generic handler for unknown services using pattern-based discovery with caching."""

    def __init__(self, session: boto3.Session):
        """Initialize with caching for discovered patterns."""
        super().__init__(session)
        self._pattern_cache: Dict[str, Dict[str, Any]] = {}
        self._failed_patterns: Set[str] = set()
        self._service_operation_cache: Dict[str, List[str]] = {}

    def can_handle(self, service: str, resource_type: str) -> bool:
        """Can handle any service as fallback."""
        return True

    def _define_read_only_operations(self) -> List[str]:
        """Define common read-only operations for pattern matching."""
        return [
            "describe_*",
            "get_*",
            "list_*",
            "head_*",
            "select_*",
            "query_*",
            "scan_*",
            "batch_get_*",
            "lookup_*",
        ]

    def _get_service_operations(self, client) -> List[str]:
        """Get all available operations for a service client with caching."""
        service_name = client._service_model.service_name

        if service_name in self._service_operation_cache:
            return self._service_operation_cache[service_name]

        try:
            operations = list(client._service_model.operation_names)
            # Filter to only read-only operations
            read_only_operations = [
                op for op in operations if self.validate_read_only_operation(op)
            ]

            self._service_operation_cache[service_name] = read_only_operations
            self.logger.debug(
                f"Cached {len(read_only_operations)} read-only operations for {service_name}"
            )
            return read_only_operations

        except Exception as e:
            self.logger.warning(f"Failed to get operations for {service_name}: {e}")
            return []

    def _generate_operation_patterns(self, resource_type: str) -> List[str]:
        """Generate comprehensive operation patterns for a resource type."""
        resource_lower = resource_type.lower()

        # Common AWS API patterns
        patterns = [
            # Describe patterns (most common)
            f"describe_{resource_lower}",
            f"describe_{resource_lower}s",
            f"describe_{resource_lower}_details",
            f"describe_{resource_lower}_configuration",
            f"describe_{resource_lower}_attributes",
            # Get patterns
            f"get_{resource_lower}",
            f"get_{resource_lower}s",
            f"get_{resource_lower}_details",
            f"get_{resource_lower}_configuration",
            f"get_{resource_lower}_attributes",
            f"get_{resource_lower}_policy",
            f"get_{resource_lower}_status",
            # List patterns (for single resource lookup)
            f"list_{resource_lower}s",
            f"list_{resource_lower}_details",
            # Lookup patterns
            f"lookup_{resource_lower}",
            f"lookup_{resource_lower}s",
            # Query patterns
            f"query_{resource_lower}",
            f"query_{resource_lower}s",
            # Head patterns (for metadata)
            f"head_{resource_lower}",
            # Batch patterns
            f"batch_get_{resource_lower}",
            f"batch_get_{resource_lower}s",
            f"batch_describe_{resource_lower}",
            f"batch_describe_{resource_lower}s",
        ]

        return patterns

    def _generate_parameter_patterns(
        self, resource_type: str, resource_id: str, arn: str
    ) -> List[Dict[str, str]]:
        """Generate comprehensive parameter patterns for API calls."""
        patterns = []

        if resource_id:
            # Resource-specific parameter names
            patterns.extend(
                [
                    {f"{resource_type}Name": resource_id},
                    {f"{resource_type}Id": resource_id},
                    {f"{resource_type}Identifier": resource_id},
                    {f"{resource_type}Key": resource_id},
                    {
                        f"{resource_type}Arn": (
                            resource_id if resource_id.startswith("arn:") else ""
                        )
                    },
                    # Generic parameter names
                    {"Name": resource_id},
                    {"Id": resource_id},
                    {"Identifier": resource_id},
                    {"Key": resource_id},
                    {"ResourceName": resource_id},
                    {"ResourceId": resource_id},
                    {"ResourceIdentifier": resource_id},
                    # Pluralized versions for list operations
                    {f"{resource_type}Names": [resource_id]},
                    {f"{resource_type}Ids": [resource_id]},
                    {"Names": [resource_id]},
                    {"Ids": [resource_id]},
                    {"ResourceNames": [resource_id]},
                    {"ResourceIds": [resource_id]},
                ]
            )

        if arn:
            patterns.extend(
                [
                    {"ResourceArn": arn},
                    {"Arn": arn},
                    {f"{resource_type}Arn": arn},
                    {"ResourceArns": [arn]},
                    {"Arns": [arn]},
                ]
            )

        # Remove empty parameter values
        return [p for p in patterns if all(v for v in p.values() if v != "")]

    def _extract_resource_data(
        self, response: Dict[str, Any], resource_type: str
    ) -> Dict[str, Any]:
        """Intelligently extract resource data from API response."""
        if not response or not isinstance(response, dict):
            return {}

        attributes = {}

        # Skip metadata
        filtered_response = {
            k: v for k, v in response.items() if k != "ResponseMetadata"
        }

        # Strategy 1: Look for keys that match the resource type
        resource_keys = [
            resource_type,
            f"{resource_type}s",
            f"{resource_type}Details",
            f"{resource_type}Configuration",
            f"{resource_type}Attributes",
        ]

        for key in resource_keys:
            if key in filtered_response:
                value = filtered_response[key]
                if isinstance(value, dict):
                    attributes.update(value)
                    return attributes
                elif isinstance(value, list) and value:
                    # Take first item if it's a list
                    if isinstance(value[0], dict):
                        attributes.update(value[0])
                        return attributes

        # Strategy 2: Look for the largest dictionary object
        largest_dict = None
        largest_size = 0

        for key, value in filtered_response.items():
            if isinstance(value, dict) and len(value) > largest_size:
                largest_dict = value
                largest_size = len(value)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                if len(value[0]) > largest_size:
                    largest_dict = value[0]
                    largest_size = len(value[0])

        if largest_dict:
            attributes.update(largest_dict)
            return attributes

        # Strategy 3: Flatten all non-metadata keys
        for key, value in filtered_response.items():
            if isinstance(value, (str, int, float, bool)):
                attributes[key] = value
            elif isinstance(value, dict):
                # Flatten nested dictionaries with prefixed keys
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, (str, int, float, bool)):
                        attributes[f"{key}_{nested_key}"] = nested_value

        return attributes

    def _is_pattern_cached_as_failed(self, service: str, pattern: str) -> bool:
        """Check if a pattern is cached as failed to avoid repeated attempts."""
        cache_key = f"{service}:{pattern}"
        return cache_key in self._failed_patterns

    def _cache_failed_pattern(self, service: str, pattern: str):
        """Cache a pattern as failed to avoid repeated attempts."""
        cache_key = f"{service}:{pattern}"
        self._failed_patterns.add(cache_key)

    def _get_cached_pattern_result(
        self, service: str, resource_type: str, resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached result for a service/resource combination."""
        cache_key = f"{service}:{resource_type}:{resource_id}"
        return self._pattern_cache.get(cache_key)

    def _cache_pattern_result(
        self, service: str, resource_type: str, resource_id: str, result: Dict[str, Any]
    ):
        """Cache successful pattern result."""
        cache_key = f"{service}:{resource_type}:{resource_id}"
        self._pattern_cache[cache_key] = result

        # Limit cache size to prevent memory issues
        if len(self._pattern_cache) > 1000:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(self._pattern_cache.keys())[:100]
            for key in oldest_keys:
                del self._pattern_cache[key]

    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to enrich unknown service resources using comprehensive pattern-based discovery."""
        service = resource.get("service", "").lower()
        resource_type = resource.get("type", "")
        resource_id = resource.get("id", "")
        arn = resource.get("arn", "")

        if not service or not resource_type:
            self.logger.warning(
                f"Missing service or resource_type for resource: {resource}"
            )
            return resource

        # Check cache first
        cached_result = self._get_cached_pattern_result(
            service, resource_type, resource_id
        )
        if cached_result is not None:
            self.logger.debug(
                f"Using cached result for {service}/{resource_type}/{resource_id}"
            )
            return {**resource, "service_attributes": cached_result}

        attributes = {}
        discovery_metadata = {
            "attempted_patterns": [],
            "successful_pattern": None,
            "parameter_pattern": None,
            "discovery_method": "dynamic_pattern_matching",
        }

        try:
            # Try to get a client for the service
            client = self.session.client(service)

            # Get available operations for this service
            available_operations = self._get_service_operations(client)
            if not available_operations:
                attributes["discovery_error"] = (
                    f"No read-only operations available for service: {service}"
                )
                return {**resource, "service_attributes": attributes}

            # Generate operation patterns
            operation_patterns = self._generate_operation_patterns(resource_type)

            # Filter patterns to only those available in the service
            valid_patterns = [
                pattern
                for pattern in operation_patterns
                if pattern in available_operations
                and not self._is_pattern_cached_as_failed(service, pattern)
            ]

            if not valid_patterns:
                # Fallback: try any available describe/get operations
                valid_patterns = [
                    op
                    for op in available_operations
                    if (op.startswith("describe_") or op.startswith("get_"))
                    and not self._is_pattern_cached_as_failed(service, op)
                ]

            self.logger.debug(
                f"Trying {len(valid_patterns)} patterns for {service}/{resource_type}"
            )

            # Generate parameter patterns
            parameter_patterns = self._generate_parameter_patterns(
                resource_type, resource_id, arn
            )

            # Try each operation pattern
            for pattern in valid_patterns:
                discovery_metadata["attempted_patterns"].append(pattern)

                try:
                    # Try each parameter pattern
                    for param_pattern in parameter_patterns:
                        try:
                            response = self._safe_api_call(
                                client, pattern, **param_pattern
                            )
                            if response:
                                # Extract resource data from response
                                extracted_attributes = self._extract_resource_data(
                                    response, resource_type
                                )

                                if extracted_attributes:
                                    attributes.update(extracted_attributes)
                                    discovery_metadata["successful_pattern"] = pattern
                                    discovery_metadata["parameter_pattern"] = (
                                        param_pattern
                                    )

                                    # Cache successful result
                                    self._cache_pattern_result(
                                        service,
                                        resource_type,
                                        resource_id,
                                        {
                                            **attributes,
                                            "discovery_metadata": discovery_metadata,
                                        },
                                    )

                                    self.logger.info(
                                        f"Successfully enriched {service}/{resource_type} using {pattern}"
                                    )
                                    break

                        except Exception as e:
                            self.logger.debug(
                                f"Parameter pattern {param_pattern} failed for {pattern}: {e}"
                            )
                            continue

                    if attributes:
                        break

                except Exception as e:
                    self.logger.debug(f"Operation pattern {pattern} failed: {e}")
                    self._cache_failed_pattern(service, pattern)
                    continue

            # Add discovery metadata
            attributes["discovery_metadata"] = discovery_metadata

            if not attributes or len(attributes) == 1:  # Only metadata
                attributes["discovery_error"] = (
                    f"No suitable API patterns found for {service}/{resource_type}"
                )
                self.logger.info(
                    f"Dynamic discovery failed for {service}/{resource_type} after trying {len(valid_patterns)} patterns"
                )

        except Exception as e:
            attributes["discovery_error"] = str(e)
            self.logger.warning(f"Dynamic discovery failed for {service}: {e}")

        return {**resource, "service_attributes": attributes}

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get statistics about the pattern cache."""
        return {
            "cached_results": len(self._pattern_cache),
            "failed_patterns": len(self._failed_patterns),
            "service_operations_cached": len(self._service_operation_cache),
            "total_cached_operations": sum(
                len(ops) for ops in self._service_operation_cache.values()
            ),
        }

    def clear_cache(self):
        """Clear all caches."""
        self._pattern_cache.clear()
        self._failed_patterns.clear()
        self._service_operation_cache.clear()
        self.logger.info("Cleared all dynamic service handler caches")


class ServiceHandlerFactory:
    """Factory for creating and managing service handlers."""

    def __init__(self, session: boto3.Session):
        """Initialize factory with AWS session."""
        self.session = session
        self.logger = logging.getLogger(f"{__name__}.ServiceHandlerFactory")
        self._handlers: Dict[str, Type[ServiceHandler]] = {}
        self._handler_instances: Dict[str, ServiceHandler] = {}
        self._dynamic_handler = DynamicServiceHandler(session)

        # Register built-in handlers
        self._register_builtin_handlers()

    def _register_builtin_handlers(self):
        """Register built-in service handlers."""
        # Import specific service handlers
        try:
            from .service_handlers import (
                S3Handler,
                RDSHandler,
                EC2Handler,
                LambdaHandler,
                ECSHandler,
                EKSHandler,
            )

            # Register specific service handlers
            self._handlers["S3"] = S3Handler
            self._handlers["RDS"] = RDSHandler
            self._handlers["EC2"] = EC2Handler
            self._handlers["LAMBDA"] = LambdaHandler
            self._handlers["ECS"] = ECSHandler
            self._handlers["EKS"] = EKSHandler

            self.logger.info(
                "Registered built-in service handlers: S3, RDS, EC2, Lambda, ECS, EKS"
            )

        except ImportError as e:
            self.logger.warning(f"Failed to import specific service handlers: {e}")

        # Dynamic handler is always available as fallback
        self._handlers["*"] = DynamicServiceHandler

    def register_handler(self, service: str, handler_class: Type[ServiceHandler]):
        """Register a service handler class."""
        self._handlers[service.upper()] = handler_class
        self.logger.info(f"Registered handler for service: {service}")

    def get_handler(self, service: str, resource_type: str) -> ServiceHandler:
        """Get appropriate handler for service and resource type."""
        service_upper = service.upper()

        # Check for specific service handler
        if service_upper in self._handlers:
            if service_upper not in self._handler_instances:
                self._handler_instances[service_upper] = self._handlers[service_upper](
                    self.session
                )

            handler = self._handler_instances[service_upper]
            if handler.can_handle(service, resource_type):
                return handler

        # Check all registered handlers
        for handler_service, handler_class in self._handlers.items():
            if handler_service == "*":  # Skip dynamic handler for now
                continue

            if handler_service not in self._handler_instances:
                self._handler_instances[handler_service] = handler_class(self.session)

            handler = self._handler_instances[handler_service]
            if handler.can_handle(service, resource_type):
                return handler

        # Fall back to dynamic handler
        return self._dynamic_handler

    def list_registered_handlers(self) -> List[str]:
        """List all registered service handlers."""
        return list(self._handlers.keys())


class ServiceAttributeEnricher:
    """Main service attribute enrichment orchestrator."""

    def __init__(self, session: Optional[boto3.Session] = None):
        """Initialize service attribute enricher."""
        self.session = session or boto3.Session()
        self.logger = logging.getLogger(f"{__name__}.ServiceAttributeEnricher")
        self.handler_factory = ServiceHandlerFactory(self.session)
        self.discovered_services: Set[str] = set()
        self.unknown_services: Set[str] = set()
        self.enrichment_stats = {
            "total_resources": 0,
            "enriched_resources": 0,
            "failed_enrichments": 0,
            "unknown_services_count": 0,
        }

    def discover_all_services(self, resources: List[Dict[str, Any]]) -> Set[str]:
        """Discover all AWS services from resource inventory."""
        services = set()

        for resource in resources:
            service = resource.get("service", "").upper()
            if service:
                services.add(service)

        self.discovered_services = services
        self.logger.info(f"Discovered {len(services)} unique AWS services")
        return services

    def enrich_resources_with_attributes(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enrich all resources with service-specific attributes."""
        enriched_resources = []
        self.enrichment_stats["total_resources"] = len(resources)

        self.logger.info(f"Starting enrichment of {len(resources)} resources")

        for resource in resources:
            try:
                enriched_resource = self.enrich_single_resource(resource)
                enriched_resources.append(enriched_resource)

                # Track success
                if "service_attributes" in enriched_resource:
                    self.enrichment_stats["enriched_resources"] += 1

            except Exception as e:
                self.logger.warning(
                    f"Failed to enrich resource {resource.get('id', 'unknown')}: {e}"
                )
                enriched_resources.append(resource)  # Add original resource
                self.enrichment_stats["failed_enrichments"] += 1

        self.logger.info(
            f"Enrichment complete. Success: {self.enrichment_stats['enriched_resources']}, "
            f"Failed: {self.enrichment_stats['failed_enrichments']}"
        )

        return enriched_resources

    def enrich_single_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a single resource with service-specific attributes."""
        service = resource.get("service", "")
        resource_type = resource.get("type", "")

        if not service:
            self.logger.warning(
                f"Resource missing service information: {resource.get('id', 'unknown')}"
            )
            return resource

        # Get appropriate handler
        handler = self.handler_factory.get_handler(service, resource_type)

        # Track unknown services
        if (
            isinstance(handler, DynamicServiceHandler)
            and service.upper() not in self.discovered_services
        ):
            self.unknown_services.add(service.upper())
            self.enrichment_stats["unknown_services_count"] += 1

        # Enrich resource
        try:
            enriched_resource = handler.enrich_resource(resource)

            # Add enrichment metadata
            enriched_resource["enrichment_metadata"] = {
                "handler_type": handler.__class__.__name__,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
                "read_only_operations": handler.get_read_only_operations(),
            }

            return enriched_resource

        except Exception as e:
            self.logger.warning(
                f"Handler {handler.__class__.__name__} failed for {service}/{resource_type}: {e}"
            )
            return resource

    def handle_unknown_service(
        self, service: str, resource: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dynamically handle unknown services using generic patterns."""
        self.logger.info(f"Attempting dynamic discovery for unknown service: {service}")

        handler = self.handler_factory.get_handler(service, resource.get("type", ""))
        return handler.enrich_resource(resource)

    def get_service_specific_attributes(
        self, service: str, resource: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get detailed attributes for specific service resources."""
        handler = self.handler_factory.get_handler(service, resource.get("type", ""))

        enriched = handler.enrich_resource(resource)
        return enriched.get("service_attributes", {})

    def get_enrichment_statistics(self) -> Dict[str, Any]:
        """Get enrichment statistics and discovered services."""
        return {
            "statistics": self.enrichment_stats,
            "discovered_services": sorted(list(self.discovered_services)),
            "unknown_services": sorted(list(self.unknown_services)),
            "registered_handlers": self.handler_factory.list_registered_handlers(),
        }

    def register_custom_handler(
        self, service: str, handler_class: Type[ServiceHandler]
    ):
        """Register a custom service handler."""
        self.handler_factory.register_handler(service, handler_class)
