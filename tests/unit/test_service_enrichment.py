#!/usr/bin/env python3
"""
Unit tests for Service Attribute Enrichment Framework

Tests the service handler framework and dynamic discovery patterns.
"""

import pytest
import boto3
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError
from datetime import datetime, timezone

from inventag.discovery.service_enrichment import (
    ServiceAttributeEnricher,
    ServiceHandler,
    ServiceHandlerFactory,
    DynamicServiceHandler,
    ServiceDiscoveryResult,
)


class TestServiceHandler:
    """Test the base ServiceHandler class."""

    def test_service_handler_abstract_methods(self):
        """Test that ServiceHandler is abstract and requires implementation."""
        with pytest.raises(TypeError):
            ServiceHandler(Mock())

    def test_read_only_operation_validation(self):
        """Test read-only operation validation."""

        class TestHandler(ServiceHandler):
            def can_handle(self, service, resource_type):
                return True

            def enrich_resource(self, resource):
                return resource

            def _define_read_only_operations(self):
                return ["custom_read_operation"]

        handler = TestHandler(Mock())

        # Test standard read-only prefixes
        assert handler.validate_read_only_operation("describe_instances")
        assert handler.validate_read_only_operation("get_bucket_location")
        assert handler.validate_read_only_operation("list_functions")
        assert handler.validate_read_only_operation("head_object")

        # Test custom read-only operations
        assert handler.validate_read_only_operation("custom_read_operation")

        # Test non-read-only operations
        assert not handler.validate_read_only_operation("create_bucket")
        assert not handler.validate_read_only_operation("delete_instance")
        assert not handler.validate_read_only_operation("put_object")

    def test_safe_api_call_success(self):
        """Test successful API call execution."""

        class TestHandler(ServiceHandler):
            def can_handle(self, service, resource_type):
                return True

            def enrich_resource(self, resource):
                return resource

            def _define_read_only_operations(self):
                return []

        mock_session = Mock()
        handler = TestHandler(mock_session)

        mock_client = Mock()
        mock_operation = Mock(return_value={"result": "success"})
        mock_client.describe_test = mock_operation

        result = handler._safe_api_call(mock_client, "describe_test", param="value")

        assert result == {"result": "success"}
        mock_operation.assert_called_once_with(param="value")

    def test_safe_api_call_non_readonly_operation(self):
        """Test that non-read-only operations are rejected."""

        class TestHandler(ServiceHandler):
            def can_handle(self, service, resource_type):
                return True

            def enrich_resource(self, resource):
                return resource

            def _define_read_only_operations(self):
                return []

        handler = TestHandler(Mock())
        mock_client = Mock()

        result = handler._safe_api_call(mock_client, "create_bucket", Bucket="test")

        assert result is None

    def test_safe_api_call_client_error(self):
        """Test handling of ClientError during API call."""

        class TestHandler(ServiceHandler):
            def can_handle(self, service, resource_type):
                return True

            def enrich_resource(self, resource):
                return resource

            def _define_read_only_operations(self):
                return []

        handler = TestHandler(Mock())

        mock_client = Mock()
        mock_operation = Mock(
            side_effect=ClientError(
                {"Error": {"Code": "AccessDenied"}}, "describe_test"
            )
        )
        mock_client.describe_test = mock_operation

        result = handler._safe_api_call(mock_client, "describe_test")

        assert result is None


class TestDynamicServiceHandler:
    """Test the DynamicServiceHandler class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.handler = DynamicServiceHandler(self.mock_session)

    def test_can_handle_any_service(self):
        """Test that DynamicServiceHandler can handle any service."""
        assert self.handler.can_handle("S3", "Bucket")
        assert self.handler.can_handle("EC2", "Instance")
        assert self.handler.can_handle("UnknownService", "UnknownType")

    def test_get_service_operations_with_caching(self):
        """Test service operations retrieval and caching."""
        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = [
            "DescribeTestResource",
            "GetTestResource",
            "CreateTestResource",
            "DeleteTestResource",
        ]

        operations = self.handler._get_service_operations(mock_client)

        # Should only return read-only operations
        assert "DescribeTestResource" in operations
        assert "GetTestResource" in operations
        assert "CreateTestResource" not in operations
        assert "DeleteTestResource" not in operations

        # Test caching
        operations2 = self.handler._get_service_operations(mock_client)
        assert operations == operations2
        assert "testservice" in self.handler._service_operation_cache

    def test_generate_operation_patterns(self):
        """Test operation pattern generation."""
        patterns = self.handler._generate_operation_patterns("TestResource")

        expected_patterns = [
            "describe_testresource",
            "describe_testresources",
            "get_testresource",
            "get_testresources",
            "list_testresources",
            "lookup_testresource",
            "query_testresource",
            "head_testresource",
            "batch_get_testresource",
        ]

        for pattern in expected_patterns:
            assert pattern in patterns

    def test_generate_parameter_patterns(self):
        """Test parameter pattern generation."""
        patterns = self.handler._generate_parameter_patterns(
            "TestResource",
            "test-id",
            "arn:aws:service:region:account:testresource/test-id",
        )

        # Should include various parameter name patterns
        param_names = [list(p.keys())[0] for p in patterns]

        expected_names = [
            "TestResourceName",
            "TestResourceId",
            "Name",
            "Id",
            "ResourceName",
            "ResourceId",
            "ResourceArn",
            "Arn",
        ]

        for name in expected_names:
            assert name in param_names

    def test_extract_resource_data_strategy_1(self):
        """Test resource data extraction - strategy 1 (matching resource type)."""
        response = {
            "TestResource": {"attribute1": "value1", "attribute2": "value2"},
            "ResponseMetadata": {"RequestId": "test-id"},
        }

        attributes = self.handler._extract_resource_data(response, "TestResource")

        assert attributes["attribute1"] == "value1"
        assert attributes["attribute2"] == "value2"
        assert "RequestId" not in attributes

    def test_extract_resource_data_strategy_2(self):
        """Test resource data extraction - strategy 2 (largest dict)."""
        response = {
            "SmallDict": {"key1": "value1"},
            "LargeDict": {"key1": "value1", "key2": "value2", "key3": "value3"},
            "ResponseMetadata": {"RequestId": "test-id"},
        }

        attributes = self.handler._extract_resource_data(response, "UnknownType")

        # Should extract from the largest dictionary
        assert attributes["key1"] == "value1"
        assert attributes["key2"] == "value2"
        assert attributes["key3"] == "value3"

    def test_extract_resource_data_strategy_3(self):
        """Test resource data extraction - strategy 3 (flatten all)."""
        response = {
            "StringValue": "test",
            "IntValue": 42,
            "NestedDict": {
                "nested_key1": "nested_value1",
                "nested_key2": "nested_value2",
            },
            "ResponseMetadata": {"RequestId": "test-id"},
        }

        # This response should trigger strategy 2 since NestedDict is the largest dict
        attributes = self.handler._extract_resource_data(response, "UnknownType")

        # Strategy 2 should pick the NestedDict as it's the largest dict
        assert attributes["nested_key1"] == "nested_value1"
        assert attributes["nested_key2"] == "nested_value2"

    def test_extract_resource_data_strategy_3_flatten(self):
        """Test resource data extraction - strategy 3 (flatten all) with no large dicts."""
        response = {
            "StringValue": "test",
            "IntValue": 42,
            "BoolValue": True,
            "SmallDict1": {"key1": "value1"},
            "SmallDict2": {"key2": "value2"},
            "ResponseMetadata": {"RequestId": "test-id"},
        }

        # This should trigger strategy 2 since SmallDict1 and SmallDict2 are tied for largest
        # Strategy 2 will pick the first one it encounters
        attributes = self.handler._extract_resource_data(response, "UnknownType")

        # Should get the first dict encountered (SmallDict1)
        assert attributes["key1"] == "value1"

    def test_pattern_caching_mechanisms(self):
        """Test pattern caching for failed and successful patterns."""
        service = "testservice"
        pattern = "describe_testresource"

        # Test failed pattern caching
        assert not self.handler._is_pattern_cached_as_failed(service, pattern)
        self.handler._cache_failed_pattern(service, pattern)
        assert self.handler._is_pattern_cached_as_failed(service, pattern)

        # Test successful result caching
        resource_type = "TestResource"
        resource_id = "test-id"
        result = {"test": "data"}

        cached = self.handler._get_cached_pattern_result(
            service, resource_type, resource_id
        )
        assert cached is None

        self.handler._cache_pattern_result(service, resource_type, resource_id, result)
        cached = self.handler._get_cached_pattern_result(
            service, resource_type, resource_id
        )
        assert cached == result

    def test_cache_size_limit(self):
        """Test that cache size is limited to prevent memory issues."""
        # Fill cache beyond limit
        for i in range(1100):
            self.handler._cache_pattern_result(
                f"service{i}", "Type", f"id{i}", {"data": i}
            )

        # Cache should be limited
        assert len(self.handler._pattern_cache) <= 1000

    def test_enrich_resource_comprehensive_success(self):
        """Test comprehensive resource enrichment with all features."""
        resource = {
            "service": "TestService",
            "type": "TestResource",
            "id": "test-resource-123",
            "arn": "arn:aws:testservice:us-east-1:123456789012:testresource/test-resource-123",
        }

        # Mock client with service model
        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = [
            "describe_testresource",
            "get_testresource",
        ]

        # Mock successful API response
        mock_response = {
            "TestResource": {
                "attribute1": "value1",
                "attribute2": "value2",
                "nested": {"nested_attr": "nested_value"},
            },
            "ResponseMetadata": {"RequestId": "test-request-id"},
        }

        self.mock_session.client.return_value = mock_client

        with patch.object(self.handler, "_safe_api_call") as mock_safe_call:
            mock_safe_call.return_value = mock_response

            result = self.handler.enrich_resource(resource)

        # Verify enrichment
        assert "service_attributes" in result
        attributes = result["service_attributes"]

        assert attributes["attribute1"] == "value1"
        assert attributes["attribute2"] == "value2"
        assert "discovery_metadata" in attributes
        assert (
            attributes["discovery_metadata"]["successful_pattern"]
            == "describe_testresource"
        )
        assert (
            attributes["discovery_metadata"]["discovery_method"]
            == "dynamic_pattern_matching"
        )

        # Verify original resource data is preserved
        assert result["service"] == "TestService"
        assert result["type"] == "TestResource"
        assert result["id"] == "test-resource-123"

    def test_enrich_resource_with_caching(self):
        """Test that cached results are used on subsequent calls."""
        resource = {
            "service": "TestService",
            "type": "TestResource",
            "id": "test-resource-123",
        }

        # First call - should make API call
        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = ["describe_testresource"]

        mock_response = {
            "TestResource": {"cached": "data"},
            "ResponseMetadata": {"RequestId": "test-request-id"},
        }

        self.mock_session.client.return_value = mock_client

        with patch.object(self.handler, "_safe_api_call") as mock_safe_call:
            mock_safe_call.return_value = mock_response

            result1 = self.handler.enrich_resource(resource)

            # Second call - should use cache
            result2 = self.handler.enrich_resource(resource)

            # Should only call API once
            assert mock_safe_call.call_count == 1

            # Results should be identical
            assert result1["service_attributes"]["cached"] == "data"
            assert result2["service_attributes"]["cached"] == "data"

    def test_enrich_resource_missing_service_or_type(self):
        """Test handling of resources missing service or type."""
        # Missing service
        resource1 = {"type": "TestResource", "id": "test-id"}
        result1 = self.handler.enrich_resource(resource1)
        assert result1 == resource1

        # Missing type
        resource2 = {"service": "TestService", "id": "test-id"}
        result2 = self.handler.enrich_resource(resource2)
        assert result2 == resource2

    def test_enrich_resource_no_available_operations(self):
        """Test handling when service has no available read-only operations."""
        resource = {
            "service": "TestService",
            "type": "TestResource",
            "id": "test-resource-123",
        }

        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = [
            "CreateTestResource",
            "DeleteTestResource",
        ]

        self.mock_session.client.return_value = mock_client

        result = self.handler.enrich_resource(resource)

        assert "service_attributes" in result
        assert "discovery_error" in result["service_attributes"]
        assert (
            "No read-only operations available"
            in result["service_attributes"]["discovery_error"]
        )

    def test_enrich_resource_fallback_patterns(self):
        """Test fallback to generic describe/get operations."""
        resource = {
            "service": "TestService",
            "type": "UnknownResource",
            "id": "test-resource-123",
        }

        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = [
            "describe_something_else",
            "get_other_thing",
        ]

        mock_response = {
            "SomethingElse": {"fallback": "success"},
            "ResponseMetadata": {"RequestId": "test-request-id"},
        }

        self.mock_session.client.return_value = mock_client

        with patch.object(self.handler, "_safe_api_call") as mock_safe_call:
            mock_safe_call.return_value = mock_response

            result = self.handler.enrich_resource(resource)

        assert "service_attributes" in result
        assert result["service_attributes"]["fallback"] == "success"

    def test_enrich_resource_all_patterns_fail(self):
        """Test handling when all patterns fail."""
        resource = {
            "service": "TestService",
            "type": "TestResource",
            "id": "test-resource-123",
        }

        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = ["describe_testresource"]

        self.mock_session.client.return_value = mock_client

        with patch.object(self.handler, "_safe_api_call") as mock_safe_call:
            mock_safe_call.return_value = None  # All calls fail

            result = self.handler.enrich_resource(resource)

        assert "service_attributes" in result
        assert "discovery_error" in result["service_attributes"]
        assert (
            "No suitable API patterns found"
            in result["service_attributes"]["discovery_error"]
        )

    def test_get_cache_statistics(self):
        """Test cache statistics reporting."""
        # Add some data to caches
        self.handler._cache_pattern_result("service1", "Type1", "id1", {"data": 1})
        self.handler._cache_pattern_result("service2", "Type2", "id2", {"data": 2})
        self.handler._cache_failed_pattern("service1", "failed_pattern")

        # Mock service operations cache
        self.handler._service_operation_cache["service1"] = ["op1", "op2", "op3"]
        self.handler._service_operation_cache["service2"] = ["op4", "op5"]

        stats = self.handler.get_cache_statistics()

        assert stats["cached_results"] == 2
        assert stats["failed_patterns"] == 1
        assert stats["service_operations_cached"] == 2
        assert stats["total_cached_operations"] == 5

    def test_clear_cache(self):
        """Test cache clearing functionality."""
        # Add data to all caches
        self.handler._cache_pattern_result("service1", "Type1", "id1", {"data": 1})
        self.handler._cache_failed_pattern("service1", "failed_pattern")
        self.handler._service_operation_cache["service1"] = ["op1", "op2"]

        # Verify caches have data
        assert len(self.handler._pattern_cache) > 0
        assert len(self.handler._failed_patterns) > 0
        assert len(self.handler._service_operation_cache) > 0

        # Clear caches
        self.handler.clear_cache()

        # Verify caches are empty
        assert len(self.handler._pattern_cache) == 0
        assert len(self.handler._failed_patterns) == 0
        assert len(self.handler._service_operation_cache) == 0

    def test_enrich_resource_success(self):
        """Test successful resource enrichment with dynamic discovery."""
        resource = {
            "service": "TestService",
            "type": "TestResource",
            "id": "test-resource-123",
            "arn": "arn:aws:testservice:us-east-1:123456789012:testresource/test-resource-123",
        }

        # Mock client and API response
        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = ["describe_testresource"]
        mock_response = {
            "TestResource": {"attribute1": "value1", "attribute2": "value2"},
            "ResponseMetadata": {"RequestId": "test-request-id"},
        }

        self.mock_session.client.return_value = mock_client

        with patch.object(self.handler, "_safe_api_call") as mock_safe_call:
            mock_safe_call.return_value = mock_response
            result = self.handler.enrich_resource(resource)

        # Verify enrichment
        assert "service_attributes" in result
        assert result["service_attributes"]["attribute1"] == "value1"
        assert result["service_attributes"]["attribute2"] == "value2"

        # Verify original resource data is preserved
        assert result["service"] == "TestService"
        assert result["type"] == "TestResource"
        assert result["id"] == "test-resource-123"

    def test_enrich_resource_multiple_patterns(self):
        """Test that handler tries multiple API patterns."""
        resource = {
            "service": "TestService",
            "type": "TestResource",
            "id": "test-resource-123",
        }

        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = [
            "describe_testresource",
            "get_testresource",
        ]

        self.mock_session.client.return_value = mock_client

        # Mock safe API call to fail first, succeed second
        def mock_safe_call_side_effect(client, operation, **kwargs):
            if operation == "describe_testresource":
                return None  # First pattern fails
            elif operation == "get_testresource":
                return {
                    "TestResource": {"found": "success"},
                    "ResponseMetadata": {"RequestId": "test-request-id"},
                }
            return None

        with patch.object(
            self.handler, "_safe_api_call", side_effect=mock_safe_call_side_effect
        ):
            result = self.handler.enrich_resource(resource)

        assert result["service_attributes"]["found"] == "success"

    def test_enrich_resource_parameter_patterns(self):
        """Test that handler tries multiple parameter patterns."""
        resource = {
            "service": "TestService",
            "type": "TestResource",
            "id": "test-resource-123",
            "arn": "arn:aws:testservice:us-east-1:123456789012:testresource/test-resource-123",
        }

        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = ["describe_testresource"]

        self.mock_session.client.return_value = mock_client

        # Mock operation that succeeds with specific parameter pattern
        def mock_safe_call_side_effect(client, operation, **kwargs):
            if "Name" in kwargs:
                return {
                    "TestResource": {"parameter_pattern": "Name"},
                    "ResponseMetadata": {"RequestId": "test-request-id"},
                }
            return None

        with patch.object(
            self.handler, "_safe_api_call", side_effect=mock_safe_call_side_effect
        ):
            result = self.handler.enrich_resource(resource)

        assert result["service_attributes"]["parameter_pattern"] == "Name"

    def test_enrich_resource_client_creation_failure(self):
        """Test handling when client creation fails."""
        resource = {
            "service": "InvalidService",
            "type": "TestResource",
            "id": "test-resource-123",
        }

        self.mock_session.client.side_effect = Exception("Invalid service")

        result = self.handler.enrich_resource(resource)

        assert "service_attributes" in result
        assert "discovery_error" in result["service_attributes"]
        assert "Invalid service" in result["service_attributes"]["discovery_error"]

    def test_enrich_resource_list_response_handling(self):
        """Test handling of list responses from API calls."""
        resource = {
            "service": "TestService",
            "type": "TestResource",
            "id": "test-resource-123",
        }

        mock_client = Mock()
        mock_client._service_model.service_name = "testservice"
        mock_client._service_model.operation_names = ["list_testresources"]

        mock_response = {
            "TestResources": [
                {"attribute1": "value1", "attribute2": "value2"},
                {"attribute1": "value3", "attribute2": "value4"},
            ],
            "ResponseMetadata": {"RequestId": "test-request-id"},
        }

        self.mock_session.client.return_value = mock_client

        with patch.object(self.handler, "_safe_api_call") as mock_safe_call:
            mock_safe_call.return_value = mock_response
            result = self.handler.enrich_resource(resource)

        # Should take first item from list
        assert result["service_attributes"]["attribute1"] == "value1"
        assert result["service_attributes"]["attribute2"] == "value2"


class TestServiceHandlerFactory:
    """Test the ServiceHandlerFactory class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.factory = ServiceHandlerFactory(self.mock_session)

    def test_factory_initialization(self):
        """Test factory initialization with built-in handlers."""
        handlers = self.factory.list_registered_handlers()
        assert "*" in handlers  # Dynamic handler should be registered

    def test_register_custom_handler(self):
        """Test registering a custom service handler."""

        class CustomHandler(ServiceHandler):
            def can_handle(self, service, resource_type):
                return service == "CUSTOM"

            def enrich_resource(self, resource):
                return resource

            def _define_read_only_operations(self):
                return []

        self.factory.register_handler("CUSTOM", CustomHandler)

        handlers = self.factory.list_registered_handlers()
        assert "CUSTOM" in handlers

    def test_get_handler_specific_service(self):
        """Test getting handler for specific service."""

        class S3Handler(ServiceHandler):
            def can_handle(self, service, resource_type):
                return service.upper() == "S3"

            def enrich_resource(self, resource):
                return resource

            def _define_read_only_operations(self):
                return []

        self.factory.register_handler("S3", S3Handler)

        handler = self.factory.get_handler("S3", "Bucket")
        assert isinstance(handler, S3Handler)

    def test_get_handler_fallback_to_dynamic(self):
        """Test fallback to dynamic handler for unknown services."""
        handler = self.factory.get_handler("UnknownService", "UnknownType")
        assert isinstance(handler, DynamicServiceHandler)

    def test_handler_instance_caching(self):
        """Test that handler instances are cached."""

        class TestHandler(ServiceHandler):
            def can_handle(self, service, resource_type):
                return service == "TEST"

            def enrich_resource(self, resource):
                return resource

            def _define_read_only_operations(self):
                return []

        self.factory.register_handler("TEST", TestHandler)

        handler1 = self.factory.get_handler("TEST", "Resource")
        handler2 = self.factory.get_handler("TEST", "Resource")

        # Should be the same instance (cached)
        assert handler1 is handler2


class TestServiceAttributeEnricher:
    """Test the main ServiceAttributeEnricher class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.enricher = ServiceAttributeEnricher(self.mock_session)

    def test_discover_all_services(self):
        """Test service discovery from resource inventory."""
        resources = [
            {"service": "EC2", "type": "Instance", "id": "i-123"},
            {"service": "S3", "type": "Bucket", "id": "bucket-123"},
            {"service": "EC2", "type": "Volume", "id": "vol-123"},
            {"service": "RDS", "type": "Instance", "id": "db-123"},
            {"service": "", "type": "Unknown", "id": "unknown-123"},  # Empty service
        ]

        services = self.enricher.discover_all_services(resources)

        expected_services = {"EC2", "S3", "RDS"}
        assert services == expected_services
        assert self.enricher.discovered_services == expected_services

    def test_enrich_single_resource_success(self):
        """Test successful single resource enrichment."""
        resource = {"service": "S3", "type": "Bucket", "id": "test-bucket"}

        # Mock handler
        mock_handler = Mock()
        mock_handler.enrich_resource.return_value = {
            **resource,
            "service_attributes": {"encryption": "AES256"},
        }
        mock_handler.get_read_only_operations.return_value = ["get_bucket_encryption"]
        mock_handler.__class__.__name__ = "S3Handler"

        with patch.object(
            self.enricher.handler_factory, "get_handler", return_value=mock_handler
        ):
            result = self.enricher.enrich_single_resource(resource)

        assert "service_attributes" in result
        assert result["service_attributes"]["encryption"] == "AES256"
        assert "enrichment_metadata" in result
        assert result["enrichment_metadata"]["handler_type"] == "S3Handler"
        assert "enriched_at" in result["enrichment_metadata"]

    def test_enrich_single_resource_missing_service(self):
        """Test handling of resource with missing service information."""
        resource = {"type": "Unknown", "id": "unknown-123"}

        result = self.enricher.enrich_single_resource(resource)

        # Should return original resource unchanged
        assert result == resource

    def test_enrich_single_resource_handler_failure(self):
        """Test handling when handler fails."""
        resource = {"service": "S3", "type": "Bucket", "id": "test-bucket"}

        # Mock handler that raises exception
        mock_handler = Mock()
        mock_handler.enrich_resource.side_effect = Exception("Handler failed")
        mock_handler.__class__.__name__ = "S3Handler"

        with patch.object(
            self.enricher.handler_factory, "get_handler", return_value=mock_handler
        ):
            result = self.enricher.enrich_single_resource(resource)

        # Should return original resource
        assert result == resource

    def test_enrich_resources_with_attributes(self):
        """Test bulk resource enrichment."""
        resources = [
            {"service": "S3", "type": "Bucket", "id": "bucket-1"},
            {"service": "EC2", "type": "Instance", "id": "i-123"},
            {"service": "RDS", "type": "Instance", "id": "db-123"},
        ]

        # Mock successful enrichment
        def mock_enrich_single(resource):
            return {
                **resource,
                "service_attributes": {"enriched": True},
                "enrichment_metadata": {
                    "handler_type": "TestHandler",
                    "enriched_at": datetime.now(timezone.utc).isoformat(),
                    "read_only_operations": [],
                },
            }

        with patch.object(
            self.enricher, "enrich_single_resource", side_effect=mock_enrich_single
        ):
            result = self.enricher.enrich_resources_with_attributes(resources)

        assert len(result) == 3
        assert all("service_attributes" in r for r in result)
        assert self.enricher.enrichment_stats["total_resources"] == 3
        assert self.enricher.enrichment_stats["enriched_resources"] == 3

    def test_enrich_resources_with_failures(self):
        """Test bulk enrichment with some failures."""
        resources = [
            {"service": "S3", "type": "Bucket", "id": "bucket-1"},
            {"service": "EC2", "type": "Instance", "id": "i-123"},
        ]

        def mock_enrich_single(resource):
            if resource["service"] == "S3":
                return {**resource, "service_attributes": {"enriched": True}}
            else:
                raise Exception("Enrichment failed")

        with patch.object(
            self.enricher, "enrich_single_resource", side_effect=mock_enrich_single
        ):
            result = self.enricher.enrich_resources_with_attributes(resources)

        assert len(result) == 2
        assert self.enricher.enrichment_stats["enriched_resources"] == 1
        assert self.enricher.enrichment_stats["failed_enrichments"] == 1

    def test_handle_unknown_service(self):
        """Test handling of unknown services."""
        resource = {
            "service": "UnknownService",
            "type": "UnknownType",
            "id": "unknown-123",
        }

        # Mock dynamic handler
        mock_handler = Mock()
        mock_handler.enrich_resource.return_value = {
            **resource,
            "service_attributes": {"discovered": True},
        }

        with patch.object(
            self.enricher.handler_factory, "get_handler", return_value=mock_handler
        ):
            result = self.enricher.handle_unknown_service("UnknownService", resource)

        assert result["service_attributes"]["discovered"] is True

    def test_get_service_specific_attributes(self):
        """Test getting service-specific attributes."""
        resource = {"service": "S3", "type": "Bucket", "id": "test-bucket"}

        mock_handler = Mock()
        mock_handler.enrich_resource.return_value = {
            **resource,
            "service_attributes": {"encryption": "AES256", "versioning": "Enabled"},
        }

        with patch.object(
            self.enricher.handler_factory, "get_handler", return_value=mock_handler
        ):
            attributes = self.enricher.get_service_specific_attributes("S3", resource)

        assert attributes == {"encryption": "AES256", "versioning": "Enabled"}

    def test_get_enrichment_statistics(self):
        """Test getting enrichment statistics."""
        # Set up some test data
        self.enricher.discovered_services = {"S3", "EC2", "RDS"}
        self.enricher.unknown_services = {"UnknownService1", "UnknownService2"}
        self.enricher.enrichment_stats = {
            "total_resources": 10,
            "enriched_resources": 8,
            "failed_enrichments": 2,
            "unknown_services_count": 2,
        }

        stats = self.enricher.get_enrichment_statistics()

        assert stats["statistics"]["total_resources"] == 10
        assert stats["statistics"]["enriched_resources"] == 8
        assert stats["discovered_services"] == ["EC2", "RDS", "S3"]  # Sorted
        assert stats["unknown_services"] == [
            "UnknownService1",
            "UnknownService2",
        ]  # Sorted
        assert "*" in stats["registered_handlers"]  # Dynamic handler

    def test_register_custom_handler(self):
        """Test registering custom handler through enricher."""

        class CustomHandler(ServiceHandler):
            def can_handle(self, service, resource_type):
                return True

            def enrich_resource(self, resource):
                return resource

            def _define_read_only_operations(self):
                return []

        self.enricher.register_custom_handler("CUSTOM", CustomHandler)

        handlers = self.enricher.handler_factory.list_registered_handlers()
        assert "CUSTOM" in handlers


class TestServiceDiscoveryResult:
    """Test the ServiceDiscoveryResult dataclass."""

    def test_service_discovery_result_creation(self):
        """Test creating ServiceDiscoveryResult."""
        result = ServiceDiscoveryResult(
            service="S3",
            resource_type="Bucket",
            discovered_services={"S3", "EC2"},
            unknown_services={"UnknownService"},
            enrichment_success=True,
            error_message=None,
        )

        assert result.service == "S3"
        assert result.resource_type == "Bucket"
        assert result.discovered_services == {"S3", "EC2"}
        assert result.unknown_services == {"UnknownService"}
        assert result.enrichment_success is True
        assert result.error_message is None

    def test_service_discovery_result_with_error(self):
        """Test creating ServiceDiscoveryResult with error."""
        result = ServiceDiscoveryResult(
            service="FailedService",
            resource_type="FailedType",
            discovered_services=set(),
            unknown_services={"FailedService"},
            enrichment_success=False,
            error_message="Service discovery failed",
        )

        assert result.enrichment_success is False
        assert result.error_message == "Service discovery failed"


if __name__ == "__main__":
    pytest.main([__file__])
