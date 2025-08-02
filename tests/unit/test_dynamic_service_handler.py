#!/usr/bin/env python3
"""
Unit tests for DynamicServiceHandler

Tests the pattern-based discovery system for unknown AWS services.
"""

import pytest
import boto3
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError

from inventag.discovery.service_enrichment import DynamicServiceHandler


class TestDynamicServiceHandler:
    """Test the DynamicServiceHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.handler = DynamicServiceHandler(self.mock_session)
    
    def test_can_handle_any_service(self):
        """Test that DynamicServiceHandler can handle any service."""
        assert self.handler.can_handle('UNKNOWN_SERVICE', 'UnknownType')
        assert self.handler.can_handle('TEXTRACT', 'Document')
        assert self.handler.can_handle('COMPREHEND', 'Entity')
    
    def test_define_read_only_operations(self):
        """Test that DynamicServiceHandler defines generic read-only operations."""
        operations = self.handler._define_read_only_operations()
        
        expected_patterns = [
            'describe_*',
            'get_*',
            'list_*'
        ]
        
        # Should return pattern-based operations
        assert len(operations) > 0
        assert any('describe' in op for op in operations)
        assert any('get' in op for op in operations)
    
    def test_generate_operation_patterns(self):
        """Test operation pattern generation for unknown services."""
        patterns = self.handler._generate_operation_patterns('TestResource')
        
        expected_patterns = [
            'describe_testresource',
            'describe_testresources',
            'get_testresource',
            'get_testresources',
            'list_testresources'
        ]
        
        for pattern in expected_patterns:
            assert pattern in patterns
    
    def test_generate_parameter_patterns(self):
        """Test parameter pattern generation."""
        resource_type = 'TestResource'
        resource_id = 'test-resource-123'
        arn = 'arn:aws:service:region:account:testresource/test-resource-123'
        
        patterns = self.handler._generate_parameter_patterns(resource_type, resource_id, arn)
        
        expected_patterns = [
            {'TestResourceName': resource_id},
            {'TestResourceId': resource_id},
            {'Name': resource_id},
            {'Id': resource_id},
            {'ResourceArn': arn},
            {'Arn': arn}
        ]
        
        for pattern in expected_patterns:
            assert pattern in patterns
    
    def test_enrich_resource_success(self):
        """Test successful resource enrichment using pattern discovery."""
        resource = {
            'service': 'TEXTRACT',
            'type': 'Document',
            'id': 'test-document-123',
            'arn': 'arn:aws:textract:us-east-1:123456789012:document/test-document-123'
        }
        
        # Mock client and successful API response
        mock_client = Mock()
        mock_client._service_model.service_name = 'textract'
        mock_client._service_model.operation_names = ['describe_document', 'get_document']
        
        mock_response = {
            'Document': {
                'DocumentId': 'test-document-123',
                'Status': 'SUCCEEDED',
                'Pages': 5,
                'CreationTime': '2023-01-01T12:00:00Z'
            },
            'ResponseMetadata': {'RequestId': 'test-request-id'}
        }
        
        self.mock_session.client.return_value = mock_client
        
        # Mock the _get_service_operations method to return available operations
        with patch.object(self.handler, '_get_service_operations', return_value=['describe_document']):
            with patch.object(self.handler, '_safe_api_call', return_value=mock_response):
                result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert 'DocumentId' in attributes
        assert attributes['DocumentId'] == 'test-document-123'
        assert 'Status' in attributes
        assert attributes['Status'] == 'SUCCEEDED'
    
    def test_enrich_resource_no_matching_operations(self):
        """Test resource enrichment when no operations match."""
        resource = {
            'service': 'UNKNOWN',
            'type': 'UnknownType',
            'id': 'unknown-123'
        }
        
        # Mock client with no matching operations
        mock_client = Mock()
        self.mock_session.client.return_value = mock_client
        
        # Mock hasattr to return False for all operations
        with patch('builtins.hasattr', return_value=False):
            result = self.handler.enrich_resource(resource)
        
        # Should return original resource with discovery error
        assert 'service_attributes' in result
        assert 'discovery_error' in result['service_attributes']
    
    def test_enrich_resource_api_errors(self):
        """Test resource enrichment with API errors."""
        resource = {
            'service': 'COMPREHEND',
            'type': 'Entity',
            'id': 'entity-123'
        }
        
        # Mock client that raises exceptions
        mock_client = Mock()
        mock_client.describe_entity.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}}, 
            'describe_entity'
        )
        
        self.mock_session.client.return_value = mock_client
        
        with patch('builtins.hasattr', return_value=True):
            result = self.handler.enrich_resource(resource)
        
        # Should return original resource with discovery error
        assert 'service_attributes' in result
        assert 'discovery_error' in result['service_attributes']
    
    def test_enrich_resource_client_creation_failure(self):
        """Test resource enrichment when client creation fails."""
        resource = {
            'service': 'INVALID_SERVICE',
            'type': 'Resource',
            'id': 'resource-123'
        }
        
        # Mock session to raise exception when creating client
        self.mock_session.client.side_effect = Exception("Unknown service")
        
        result = self.handler.enrich_resource(resource)
        
        # Should return original resource with discovery error
        assert 'service_attributes' in result
        assert 'discovery_error' in result['service_attributes']
        assert 'Unknown service' in result['service_attributes']['discovery_error']
    
    def test_extract_resource_data(self):
        """Test extraction of main resource data from API response."""
        # Test response with single resource object
        response1 = {
            'Document': {'DocumentId': 'doc-123', 'Status': 'SUCCEEDED'},
            'ResponseMetadata': {'RequestId': 'req-123'}
        }
        
        data1 = self.handler._extract_resource_data(response1, 'Document')
        assert data1 == {'DocumentId': 'doc-123', 'Status': 'SUCCEEDED'}
        
        # Test response with list of resources
        response2 = {
            'Documents': [
                {'DocumentId': 'doc-1', 'Status': 'SUCCEEDED'},
                {'DocumentId': 'doc-2', 'Status': 'FAILED'}
            ],
            'ResponseMetadata': {'RequestId': 'req-123'}
        }
        
        data2 = self.handler._extract_resource_data(response2, 'Document')
        assert data2 == {'DocumentId': 'doc-1', 'Status': 'SUCCEEDED'}
        
        # Test response with no resource data
        response3 = {
            'ResponseMetadata': {'RequestId': 'req-123'}
        }
        
        data3 = self.handler._extract_resource_data(response3, 'Document')
        assert data3 == {}
    
    def test_get_service_operations(self):
        """Test service operations retrieval."""
        mock_client = Mock()
        mock_client._service_model.service_name = 'textract'
        mock_client._service_model.operation_names = [
            'DescribeDocument', 'GetDocument', 'ListDocuments', 'CreateDocument'
        ]
        
        with patch.object(self.handler, 'validate_read_only_operation') as mock_validate:
            mock_validate.side_effect = lambda op: op.startswith(('Describe', 'Get', 'List'))
            
            operations = self.handler._get_service_operations(mock_client)
        
        assert 'DescribeDocument' in operations
        assert 'GetDocument' in operations
        assert 'ListDocuments' in operations
        assert 'CreateDocument' not in operations  # Should be filtered out
    
    def test_cache_pattern_result(self):
        """Test caching of successful pattern results."""
        service = 'textract'
        resource_type = 'Document'
        resource_id = 'doc-123'
        result = {'DocumentId': 'doc-123', 'Status': 'SUCCEEDED'}
        
        # Cache the result
        self.handler._cache_pattern_result(service, resource_type, resource_id, result)
        
        # Retrieve from cache
        cached_result = self.handler._get_cached_pattern_result(service, resource_type, resource_id)
        assert cached_result == result
    
    def test_failed_pattern_caching(self):
        """Test caching of failed patterns."""
        service = 'textract'
        pattern = 'describe_document'
        
        # Initially should not be cached as failed
        assert not self.handler._is_pattern_cached_as_failed(service, pattern)
        
        # Cache as failed
        self.handler._cache_failed_pattern(service, pattern)
        
        # Should now be cached as failed
        assert self.handler._is_pattern_cached_as_failed(service, pattern)


if __name__ == '__main__':
    pytest.main([__file__])