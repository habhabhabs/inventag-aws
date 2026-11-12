---
title: Service Enrichment
description: AWS service attribute enhancement and enrichment framework
sidebar_position: 4
---

# Service Enrichment Framework

## Overview

The Service Enrichment Framework provides dynamic service discovery and attribute enrichment for AWS resources. It automatically handles both known and unknown AWS services using intelligent pattern-based discovery with comprehensive caching and read-only validation.

## Architecture

### Core Components

1. **ServiceHandler (Abstract Base Class)**: Defines the interface for all service handlers
2. **DynamicServiceHandler**: Generic handler for unknown services using pattern-based discovery
3. **ServiceHandlerFactory**: Factory for creating and managing service handlers
4. **ServiceAttributeEnricher**: Main orchestrator for resource enrichment

### Service Handler Hierarchy

```
ServiceHandler (ABC)
├── DynamicServiceHandler (fallback for unknown services)
├── S3Handler (specific S3 enrichment)
├── RDSHandler (specific RDS enrichment)
├── EC2Handler (specific EC2 enrichment)
├── LambdaHandler (specific Lambda enrichment)
├── ECSHandler (specific ECS enrichment)
└── EKSHandler (specific EKS enrichment)
```

## Dynamic Service Discovery

### Pattern-Based Discovery

The `DynamicServiceHandler` uses intelligent pattern matching to discover and enrich resources from unknown AWS services:

#### Operation Pattern Generation

For a resource type like `Document`, the handler generates patterns such as:
- `describe_document`, `describe_documents`
- `get_document`, `get_documents`
- `list_documents`
- `lookup_document`
- `query_document`
- `batch_get_document`

#### Parameter Pattern Matching

For each operation, multiple parameter combinations are tried:
- Resource-specific: `{ResourceType}Name`, `{ResourceType}Id`
- Generic: `Name`, `Id`, `Identifier`, `Key`
- ARN-based: `ResourceArn`, `Arn`
- Pluralized versions for list operations

#### Response Data Extraction

The handler intelligently extracts resource data using multiple strategies:
1. **Resource Type Matching**: Look for keys matching the resource type
2. **Largest Dictionary**: Extract the largest dictionary object from the response
3. **Flattening**: Flatten all non-metadata keys with prefixed naming

### Caching System

The dynamic handler implements comprehensive caching for optimal performance:

- **Pattern Cache**: Caches successful API responses by service/resource/ID
- **Failed Pattern Cache**: Tracks failed patterns to avoid repeated attempts
- **Service Operation Cache**: Caches available operations per service
- **Cache Size Management**: Automatic cleanup when cache exceeds limits

## Usage Examples

### Basic Service Enrichment

```python
from inventag.discovery.service_enrichment import ServiceAttributeEnricher

# Initialize enricher
enricher = ServiceAttributeEnricher()

# Enrich a single resource
resource = {
    'service': 'TEXTRACT',
    'type': 'Document',
    'id': 'document-123',
    'arn': 'arn:aws:textract:us-east-1:123456789012:document/document-123'
}

enriched_resource = enricher.enrich_single_resource(resource)
print(f"Service attributes: {enriched_resource.get('service_attributes', {})}")
```

### Batch Resource Enrichment

```python
# Enrich multiple resources
resources = [
    {'service': 'EC2', 'type': 'Instance', 'id': 'i-1234567890abcdef0'},
    {'service': 'S3', 'type': 'Bucket', 'id': 'my-bucket'},
    {'service': 'TEXTRACT', 'type': 'Document', 'id': 'doc-123'}
]

enriched_resources = enricher.enrich_resources_with_attributes(resources)

# Get enrichment statistics
stats = enricher.get_enrichment_statistics()
print(f"Enriched: {stats['statistics']['enriched_resources']}")
print(f"Unknown services: {stats['unknown_services']}")
```

### Dynamic Handler Direct Usage

```python
from inventag.discovery.service_enrichment import DynamicServiceHandler
import boto3

# Initialize handler
handler = DynamicServiceHandler(boto3.Session())

# Enrich unknown service resource
resource = {
    'service': 'COMPREHEND',
    'type': 'Entity',
    'id': 'entity-123'
}

enriched = handler.enrich_resource(resource)

# Check cache statistics
stats = handler.get_cache_statistics()
print(f"Cache stats: {stats}")
```

### Custom Service Handler

```python
from inventag.discovery.service_enrichment import ServiceHandler

class CustomServiceHandler(ServiceHandler):
    def can_handle(self, service: str, resource_type: str) -> bool:
        return service.upper() == 'MYSERVICE'
    
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        # Custom enrichment logic
        attributes = {'custom_attribute': 'value'}
        return {**resource, 'service_attributes': attributes}
    
    def _define_read_only_operations(self) -> List[str]:
        return ['describe_my_resource', 'get_my_resource']

# Register custom handler
enricher = ServiceAttributeEnricher()
enricher.register_custom_handler('MYSERVICE', CustomServiceHandler)
```

## Read-Only Validation

All service handlers implement comprehensive read-only validation:

### Validation Methods

1. **Prefix-based validation**: Operations starting with `describe`, `get`, `list`, etc.
2. **Explicit operation lists**: Predefined lists of known read-only operations
3. **Safe API calls**: All API calls are wrapped with read-only validation

### Read-Only Prefixes

```python
read_only_prefixes = [
    'describe', 'get', 'list', 'head', 'select',
    'query', 'scan', 'batch_get', 'lookup'
]
```

### Safe API Call Example

```python
def _safe_api_call(self, client, operation_name: str, **kwargs) -> Optional[Dict]:
    """Safely execute API call with read-only validation."""
    if not self.validate_read_only_operation(operation_name):
        self.logger.warning(f"Operation {operation_name} is not validated as read-only")
        return None
        
    try:
        operation = getattr(client, operation_name)
        return operation(**kwargs)
    except ClientError as e:
        self.logger.debug(f"API call {operation_name} failed: {e}")
        return None
```

## Performance Optimization

### Caching Strategies

1. **Pattern Result Caching**: Cache successful API responses
2. **Failed Pattern Tracking**: Avoid repeated failed attempts
3. **Service Operation Caching**: Cache available operations per service
4. **Cache Size Management**: Automatic cleanup to prevent memory issues

### Cache Statistics

```python
# Get detailed cache statistics
stats = handler.get_cache_statistics()
print(f"Cached results: {stats['cached_results']}")
print(f"Failed patterns: {stats['failed_patterns']}")
print(f"Service operations cached: {stats['service_operations_cached']}")
print(f"Total cached operations: {stats['total_cached_operations']}")
```

### Cache Management

```python
# Clear all caches
handler.clear_cache()

# Check if pattern is cached as failed
is_failed = handler._is_pattern_cached_as_failed('textract', 'describe_document')
```

## Error Handling

### Graceful Degradation

The framework implements comprehensive error handling:

1. **Client Creation Failures**: Gracefully handle unknown services
2. **API Call Failures**: Log and continue with other patterns
3. **Parameter Validation**: Try multiple parameter combinations
4. **Response Parsing**: Handle various response formats

### Error Response Example

```python
# When enrichment fails, the resource includes error information
{
    'service': 'UNKNOWN_SERVICE',
    'type': 'Resource',
    'id': 'resource-123',
    'service_attributes': {
        'discovery_error': 'No suitable API patterns found for unknown_service/Resource',
        'discovery_metadata': {
            'attempted_patterns': ['describe_resource', 'get_resource'],
            'successful_pattern': None,
            'discovery_method': 'dynamic_pattern_matching'
        }
    }
}
```

## Testing

### Unit Tests

The framework includes comprehensive unit tests in `tests/unit/test_dynamic_service_handler.py`:

```python
# Run dynamic service handler tests
python -m pytest tests/unit/test_dynamic_service_handler.py -v

# Run with coverage
python -m pytest tests/unit/test_dynamic_service_handler.py --cov=inventag.discovery.service_enrichment
```

### Test Coverage

The test suite covers:
- ✅ Pattern generation for various resource types
- ✅ Parameter pattern matching
- ✅ Successful resource enrichment
- ✅ Error handling for unknown services
- ✅ API call failures and client creation errors
- ✅ Response data extraction
- ✅ Caching functionality
- ✅ Read-only operation validation

### Mock Testing Example

```python
def test_enrich_resource_success(self):
    """Test successful resource enrichment using pattern discovery."""
    resource = {
        'service': 'TEXTRACT',
        'type': 'Document',
        'id': 'test-document-123',
        'arn': 'arn:aws:textract:us-east-1:123456789012:document/test-document-123'
    }
    
    # Mock successful API response
    mock_response = {
        'Document': {
            'DocumentId': 'test-document-123',
            'Status': 'SUCCEEDED',
            'Pages': 5
        }
    }
    
    # Test enrichment
    result = self.handler.enrich_resource(resource)
    
    # Verify results
    assert 'service_attributes' in result
    assert result['service_attributes']['DocumentId'] == 'test-document-123'
```

## Integration with InvenTag

### Resource Inventory Integration

The service enrichment framework is integrated into the main resource inventory system:

```python
# In aws_resource_inventory.py
from inventag.discovery.service_enrichment import ServiceAttributeEnricher

class AWSResourceInventory:
    def __init__(self):
        self.enricher = ServiceAttributeEnricher()
    
    def enrich_discovered_resources(self, resources):
        return self.enricher.enrich_resources_with_attributes(resources)
```

### BOM Generation Integration

Enriched attributes are included in BOM reports:

```python
# Service attributes appear in Excel/CSV exports
{
    'service': 'TEXTRACT',
    'type': 'Document',
    'id': 'document-123',
    'service_attributes': {
        'DocumentId': 'document-123',
        'Status': 'SUCCEEDED',
        'Pages': 5,
        'CreationTime': '2023-01-01T12:00:00Z'
    }
}
```

## Best Practices

### Handler Development

1. **Extend ServiceHandler**: Always extend the base ServiceHandler class
2. **Implement Read-Only Operations**: Define comprehensive read-only operation lists
3. **Use Safe API Calls**: Always use the `_safe_api_call` method
4. **Handle Errors Gracefully**: Implement proper error handling and logging
5. **Cache Results**: Use caching for performance optimization

### Performance Considerations

1. **Batch Processing**: Process resources in batches for better performance
2. **Cache Management**: Monitor cache sizes and clear when necessary
3. **Pattern Optimization**: Use specific patterns before generic ones
4. **Error Tracking**: Track failed patterns to avoid repeated attempts

### Security Considerations

1. **Read-Only Validation**: Always validate operations as read-only
2. **Permission Handling**: Handle permission errors gracefully
3. **Credential Management**: Use appropriate AWS credential management
4. **Audit Logging**: Log all API calls for audit purposes

## Troubleshooting

### Common Issues

#### Unknown Service Errors

**Issue**: Service not recognized by boto3
**Solution**: Check service name spelling and AWS region availability

```python
# Debug service availability
try:
    client = session.client('unknown_service')
except Exception as e:
    print(f"Service not available: {e}")
```

#### Pattern Discovery Failures

**Issue**: No patterns work for a service
**Solution**: Check available operations and add custom patterns

```python
# Debug available operations
client = session.client('service_name')
operations = list(client._service_model.operation_names)
print(f"Available operations: {operations}")
```

#### Cache Performance Issues

**Issue**: Memory usage from large caches
**Solution**: Clear caches periodically or reduce cache size limits

```python
# Monitor cache sizes
stats = handler.get_cache_statistics()
if stats['cached_results'] > 1000:
    handler.clear_cache()
```

### Debug Logging

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Initialize handler with debug logging
handler = DynamicServiceHandler(session)
```

## Future Enhancements

### Planned Features

1. **Machine Learning Pattern Discovery**: Use ML to discover optimal patterns
2. **Service Documentation Integration**: Automatically discover operations from AWS docs
3. **Performance Analytics**: Detailed performance metrics and optimization suggestions
4. **Custom Pattern Templates**: User-defined pattern templates for specific services
5. **Distributed Caching**: Redis/Memcached integration for distributed deployments

### Contributing

To contribute new service handlers or improvements:

1. **Extend ServiceHandler**: Create new handler classes
2. **Add Tests**: Include comprehensive unit tests
3. **Update Documentation**: Document new features and usage
4. **Performance Testing**: Ensure new handlers don't impact performance
5. **Security Review**: Validate read-only operations and security practices

## Conclusion

The Service Enrichment Framework provides a robust, scalable solution for discovering and enriching AWS resources across all services. Its intelligent pattern-based discovery system ensures comprehensive coverage while maintaining security through read-only validation and performance through intelligent caching.

The framework's modular design allows for easy extension with custom handlers while providing a reliable fallback mechanism for unknown services. This makes it an essential component of InvenTag's comprehensive AWS resource management capabilities.
