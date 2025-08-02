# Service Description Management Framework

The Service Description Management Framework provides intelligent, customizable descriptions for AWS resources with template-based dynamic generation and comprehensive configuration support.

## Overview

The framework consists of three main components:

1. **ServiceDescriptionManager** - Main interface for managing service descriptions
2. **DescriptionTemplateEngine** - Template processing and rendering engine
3. **Configuration System** - YAML/JSON configuration file support with schema validation

## Key Features

### 🎯 Dynamic Description Generation
- **Template-based rendering** with variable substitution
- **Intelligent fallback mechanisms** when templates fail
- **Nested attribute access** using dot notation
- **Automatic variable mapping** from resource attributes

### 🔧 Configuration Management
- **YAML/JSON configuration files** with schema validation
- **Hot reloading** of configuration without restart
- **Service hierarchies** (service-level and resource-type-level descriptions)
- **Template registration** and management

### 📋 Built-in Service Support
Pre-configured templates and descriptions for major AWS services:
- **EC2**: Instances, volumes, security groups
- **S3**: Buckets with encryption details
- **RDS**: Database instances and clusters
- **Lambda**: Functions with runtime specifications
- **VPC**: VPCs and subnets with network details

## Quick Start

### Basic Usage

```python
from inventag.discovery.service_descriptions import ServiceDescriptionManager

# Initialize with default descriptions
manager = ServiceDescriptionManager()

# Apply descriptions to resources
enriched_resources = manager.apply_descriptions_to_resources(resources)

# Get dynamic description for a single resource
description = manager.get_dynamic_description(resource)
print(f"{resource['id']}: {description}")
```

### With Configuration File

```python
# Initialize with custom configuration
manager = ServiceDescriptionManager(config_path='config/service_descriptions.yaml')

# Apply descriptions
enriched_resources = manager.apply_descriptions_to_resources(resources)

# Each resource now has:
# - service_description: Human-readable description
# - description_metadata: Generation metadata and source tracking
```

## Configuration Format

### Basic Configuration Structure

```yaml
# config/service_descriptions.yaml
service_descriptions:
  EC2:
    default:
      description: "Amazon Elastic Compute Cloud - Scalable virtual servers"
      template: "ec2_default"
    Instance:
      description: "Virtual machine instance providing compute capacity"
      template: "ec2_instance"
      attributes:
        category: "compute"
        managed: true
    Volume:
      description: "Block storage volume for EC2 instances"
      template: "ec2_volume"

  S3:
    default:
      description: "Amazon Simple Storage Service - Object storage"
      template: "s3_default"
    Bucket:
      description: "Container for objects in S3"
      template: "s3_bucket"

templates:
  ec2_instance:
    template: "EC2 Instance {resource_id} - {instance_type} in {availability_zone}"
    required_attributes:
      - "service_attributes.InstanceType"
    optional_attributes:
      - "service_attributes.Placement.AvailabilityZone"
    fallback_template: "ec2_default"
  
  ec2_volume:
    template: "EBS Volume {resource_id} - {size}GB {volume_type} volume"
    required_attributes:
      - "service_attributes.Size"
      - "service_attributes.VolumeType"
    fallback_template: "ec2_default"
  
  ec2_default:
    template: "Amazon EC2 {resource_type} ({resource_id}) in {region}"
    required_attributes: []
    optional_attributes: []
```

### Configuration Schema

#### Service Descriptions
```yaml
service_descriptions:
  <SERVICE_NAME>:
    <RESOURCE_TYPE>:
      description: string          # Required: Human-readable description
      template: string            # Optional: Template name to use
      attributes: object          # Optional: Custom attributes
      fallback: string           # Optional: Fallback description
```

#### Templates
```yaml
templates:
  <TEMPLATE_NAME>:
    template: string                    # Required: Template string with variables
    required_attributes: array          # Optional: Required resource attributes
    optional_attributes: array          # Optional: Optional resource attributes
    fallback_template: string          # Optional: Fallback template name
```

## Template System

### Template Variables

Templates support automatic variable mapping from resource attributes:

```python
# Resource attribute mapping examples:
# service_attributes.InstanceType -> {instance_type}
# service_attributes.Placement.AvailabilityZone -> {availability_zone}
# service_attributes.State.Name -> {state_name}

# Standard variables available in all templates:
# {resource_id} - Resource ID
# {resource_type} - Resource type
# {service} - AWS service name
# {region} - AWS region
# {account_id} - AWS account ID
```

### Template Examples

#### EC2 Instance Template
```yaml
ec2_instance:
  template: "EC2 Instance {resource_id} - {instance_type} in {availability_zone} ({state_name})"
  required_attributes:
    - "service_attributes.InstanceType"
    - "service_attributes.State.Name"
  optional_attributes:
    - "service_attributes.Placement.AvailabilityZone"
  fallback_template: "ec2_default"
```

#### S3 Bucket Template
```yaml
s3_bucket:
  template: "S3 Bucket {resource_id} - {encryption_status} encryption in {region}"
  required_attributes: []
  optional_attributes:
    - "service_attributes.encryption.ServerSideEncryptionConfiguration"
  fallback_template: "s3_default"
```

#### RDS Instance Template
```yaml
rds_instance:
  template: "RDS Instance {resource_id} - {engine} {engine_version} database"
  required_attributes:
    - "service_attributes.Engine"
  optional_attributes:
    - "service_attributes.EngineVersion"
  fallback_template: "rds_default"
```

## Fallback Strategy

The system uses intelligent fallback mechanisms in this order:

1. **Exact Match**: Service + resource type specific template
2. **Service Default**: Service-level default template
3. **Built-in Templates**: Pre-configured AWS service templates
4. **Generic Fallback**: Basic AWS service description

```python
# Example fallback chain for EC2 Instance:
# 1. Custom EC2.Instance template (if configured)
# 2. Custom EC2.default template (if configured)
# 3. Built-in EC2.Instance template
# 4. Built-in EC2.default template
# 5. Generic "AWS EC2 Instance - Cloud resource managed by Amazon Web Services"
```

## Advanced Features

### Hot Reloading

```python
# Reload configuration without restart
success = manager.reload_descriptions('updated_config.yaml')
if success:
    print("Configuration reloaded successfully")
```

### Configuration Information

```python
# Get detailed configuration information
config_info = manager.get_configuration_info()
print(f"Config path: {config_info['config_path']}")
print(f"Custom services: {config_info['custom_services']}")
print(f"Total templates: {len(config_info['registered_templates'])}")
```

### Export Configuration Template

```python
# Export a configuration template for customization
manager.export_configuration_template(
    output_path='my_service_descriptions.yaml',
    format_type='yaml'
)
```

### Custom Template Registration

```python
from inventag.discovery.service_descriptions import DescriptionTemplate

# Create custom template
custom_template = DescriptionTemplate(
    name='custom_lambda',
    template='Lambda Function {resource_id} - {runtime} with {memory_size}MB memory',
    required_attributes=['service_attributes.Runtime'],
    optional_attributes=['service_attributes.MemorySize'],
    fallback_template='lambda_default'
)

# Register template
manager.template_engine.register_template(custom_template)
```

## Integration Examples

### With Service Enrichment

```python
from inventag.discovery.service_enrichment import ServiceAttributeEnricher
from inventag.discovery.service_descriptions import ServiceDescriptionManager

# First enrich resources with service attributes
enricher = ServiceAttributeEnricher()
enriched_resources = enricher.enrich_resources_with_attributes(resources)

# Then apply intelligent descriptions
desc_manager = ServiceDescriptionManager(config_path='config/descriptions.yaml')
final_resources = desc_manager.apply_descriptions_to_resources(enriched_resources)

# Resources now have both service_attributes and service_description
for resource in final_resources:
    print(f"Resource: {resource['id']}")
    print(f"Description: {resource['service_description']}")
    if 'description_metadata' in resource:
        metadata = resource['description_metadata']
        print(f"Template used: {metadata.get('template_used', 'None')}")
        print(f"Custom description: {metadata.get('has_custom_description', False)}")
```

### With BOM Converter

```python
from inventag.reporting import BOMConverter

# Apply descriptions before generating reports
desc_manager = ServiceDescriptionManager(config_path='config/descriptions.yaml')
described_resources = desc_manager.apply_descriptions_to_resources(resources)

# Generate BOM with descriptions
converter = BOMConverter()
converter.data = described_resources
converter.export_to_excel('report_with_descriptions.xlsx')
```

### With State Management

```python
from inventag.state import StateManager

# Save state with described resources
state_manager = StateManager()
state_id = state_manager.save_state(
    resources=described_resources,
    account_id='123456789012',
    regions=['us-east-1'],
    tags={'description_config': 'production_descriptions.yaml'}
)
```

## Built-in Templates

### EC2 Templates
- **ec2_instance**: Instance type, availability zone, state
- **ec2_volume**: Size, volume type, state
- **ec2_security_group**: Group name, network access control
- **ec2_default**: Generic EC2 resource description

### S3 Templates
- **s3_bucket**: Encryption status, region
- **s3_default**: Generic S3 resource description

### RDS Templates
- **rds_instance**: Engine, version, database type
- **rds_cluster**: Cluster configuration, high availability
- **rds_default**: Generic RDS resource description

### Lambda Templates
- **lambda_function**: Runtime, memory size, execution details
- **lambda_default**: Generic Lambda resource description

### VPC Templates
- **vpc_vpc**: CIDR block, network configuration
- **vpc_subnet**: CIDR block, availability zone
- **vpc_default**: Generic VPC resource description

## Error Handling

The framework includes comprehensive error handling:

```python
# Configuration validation errors
try:
    manager = ServiceDescriptionManager(config_path='invalid_config.yaml')
except Exception as e:
    print(f"Configuration error: {e}")

# Template rendering errors are handled gracefully
# - Missing attributes fall back to simpler templates
# - Invalid templates fall back to static descriptions
# - All errors are logged but don't stop processing
```

## Performance Considerations

- **Template caching**: Templates are compiled and cached for performance
- **Lazy loading**: Configuration is loaded only when needed
- **Batch processing**: Resources are processed in batches for efficiency
- **Memory efficient**: Large resource sets are processed without excessive memory usage

## Best Practices

### Configuration Organization
```yaml
# Organize by service hierarchy
service_descriptions:
  EC2:
    default: { ... }      # Service-level default
    Instance: { ... }     # Resource-type specific
    Volume: { ... }       # Resource-type specific
  
  S3:
    default: { ... }
    Bucket: { ... }
```

### Template Design
- Use **required_attributes** for essential information
- Use **optional_attributes** for nice-to-have details
- Always provide **fallback_template** for reliability
- Keep templates **concise but informative**

### Integration Workflow
1. **Discover resources** with AWSResourceInventory
2. **Enrich with service attributes** using ServiceAttributeEnricher
3. **Apply descriptions** using ServiceDescriptionManager
4. **Generate reports** or **save state** with enriched data

## Troubleshooting

### Common Issues

**Template not rendering:**
- Check required attributes are available in resource
- Verify template name matches configuration
- Check for typos in attribute paths

**Configuration not loading:**
- Validate YAML/JSON syntax
- Check file permissions and path
- Review schema validation errors in logs

**Missing descriptions:**
- Ensure service enrichment runs before description application
- Check fallback chain is properly configured
- Verify resource has required service/type fields

### Debug Information

```python
# Enable debug logging
import logging
logging.getLogger('inventag.discovery.service_descriptions').setLevel(logging.DEBUG)

# Get template information
templates = manager.template_engine.list_templates()
print(f"Available templates: {templates}")

# Check configuration status
config_info = manager.get_configuration_info()
print(f"Configuration loaded: {config_info}")
```