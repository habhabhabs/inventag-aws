#!/usr/bin/env python3
"""
Service Description and Tag Mapping Demo

Demonstrates the ServiceDescriptionManager and TagMappingEngine functionality
for enriching AWS resources with custom descriptions and tag-based attributes.
"""

import json
from inventag.discovery import ServiceDescriptionManager, TagMappingEngine


def main():
    """Demonstrate service description and tag mapping functionality."""
    print("=== Service Description and Tag Mapping Demo ===\n")
    
    # Initialize managers
    desc_manager = ServiceDescriptionManager()
    tag_engine = TagMappingEngine()
    
    # Sample AWS resources
    sample_resources = [
        {
            'id': 'i-1234567890abcdef0',
            'type': 'Instance',
            'service': 'EC2',
            'region': 'us-east-1',
            'account_id': '123456789012',
            'tags': {
                'inventag:remarks': 'Production web server',
                'inventag:costcenter': 'IT-1001',
                'inventag:owner': 'DevOps Team',
                'inventag:environment': 'prod',
                'inventag:project': 'E-commerce Platform'
            },
            'service_attributes': {
                'InstanceType': 't3.large',
                'Placement': {
                    'AvailabilityZone': 'us-east-1a'
                }
            }
        },
        {
            'id': 'my-s3-bucket',
            'type': 'Bucket',
            'service': 'S3',
            'region': 'us-east-1',
            'account_id': '123456789012',
            'tags': {
                'inventag:remarks': 'Static website assets',
                'inventag:costcenter': 'MKT-2001',
                'inventag:environment': 'prod',
                'inventag:backup': 'required'
            },
            'service_attributes': {
                'encryption': {
                    'ServerSideEncryptionConfiguration': {
                        'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]
                    }
                }
            }
        },
        {
            'id': 'db-instance-1',
            'type': 'DBInstance',
            'service': 'RDS',
            'region': 'us-east-1',
            'account_id': '123456789012',
            'tags': {
                'inventag:costcenter': 'invalid-format',  # Invalid format
                'inventag:environment': 'development'  # Invalid value
            },
            'service_attributes': {
                'Engine': 'mysql',
                'EngineVersion': '8.0.35'
            }
        }
    ]
    
    print("1. Service Description Management")
    print("-" * 40)
    
    # Apply service descriptions
    enriched_with_descriptions = desc_manager.apply_descriptions_to_resources(sample_resources)
    
    for resource in enriched_with_descriptions:
        print(f"Resource: {resource['id']}")
        print(f"Service: {resource['service']} {resource['type']}")
        print(f"Description: {resource['service_description']}")
        print(f"Has Custom Description: {resource['description_metadata']['has_custom_description']}")
        print()
    
    print("2. Tag Mapping and Custom Attributes")
    print("-" * 40)
    
    # Apply tag mappings
    enriched_with_tags = tag_engine.apply_mappings_to_resources(sample_resources)
    
    for resource in enriched_with_tags:
        print(f"Resource: {resource['id']}")
        print("Custom Attributes:")
        for attr_name, attr_value in resource['custom_attributes'].items():
            print(f"  {attr_name}: {attr_value}")
        
        # Show validation issues
        metadata = resource['tag_mapping_metadata']
        if metadata['missing_required_tags']:
            print(f"Missing Required Tags: {metadata['missing_required_tags']}")
        if metadata['validation_errors']:
            print(f"Validation Errors: {metadata['validation_errors']}")
        print()
    
    print("3. Tag Validation Report")
    print("-" * 40)
    
    # Generate validation report
    validation_report = tag_engine.generate_validation_report(sample_resources)
    
    print(f"Total Resources: {validation_report['total_resources']}")
    print(f"Valid Resources: {validation_report['valid_resources']}")
    print(f"Invalid Resources: {validation_report['invalid_resources']}")
    print(f"Compliance Percentage: {validation_report['compliance_percentage']:.1f}%")
    
    if validation_report['missing_tags_summary']:
        print("\nMost Common Missing Tags:")
        for tag, count in validation_report['missing_tags_summary'].items():
            print(f"  {tag}: {count} resources")
    
    if validation_report['validation_summary']:
        print("\nValidation Errors:")
        for error, count in validation_report['validation_summary'].items():
            print(f"  {error}: {count} resources")
    
    print("\n4. Custom Column Configuration")
    print("-" * 40)
    
    # Show custom columns for BOM documents
    columns = tag_engine.get_custom_columns()
    print("Available Custom Columns for BOM Documents:")
    for column in columns[:5]:  # Show first 5
        print(f"  Column: {column['name']}")
        print(f"    Tag: {column['tag']}")
        print(f"    Default: {column['default_value']}")
        print(f"    Required: {column['required']}")
        print()
    
    print("5. Dynamic Description Generation")
    print("-" * 40)
    
    # Show dynamic descriptions with templates
    for resource in sample_resources:
        dynamic_desc = desc_manager.get_dynamic_description(resource)
        print(f"Resource: {resource['id']}")
        print(f"Dynamic Description: {dynamic_desc}")
        print()
    
    print("6. Configuration Information")
    print("-" * 40)
    
    # Show configuration info
    desc_info = desc_manager.get_configuration_info()
    tag_info = tag_engine.get_configuration_info()
    
    print("Service Description Manager:")
    print(f"  Default Services: {desc_info['default_services']}")
    print(f"  Total Default Descriptions: {desc_info['total_default_descriptions']}")
    print(f"  Registered Templates: {len(desc_info['registered_templates'])}")
    
    print("\nTag Mapping Engine:")
    print(f"  Total Mappings: {tag_info['total_mappings']}")
    print(f"  Required Mappings: {tag_info['required_mappings']}")
    print(f"  Mappings with Validation: {tag_info['mappings_with_validation']}")
    print(f"  Mappings with Normalization: {tag_info['mappings_with_normalization']}")
    
    print("\n=== Demo Complete ===")


if __name__ == '__main__':
    main()