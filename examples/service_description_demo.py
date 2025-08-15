#!/usr/bin/env python3
"""
Service Description Management Framework Demonstration

This script demonstrates the comprehensive service description capabilities
of the InvenTag Service Description Management Framework, including template
rendering, configuration management, and integration with resource discovery.
"""

import sys
import os
import json
import yaml
from datetime import datetime, timezone

# Add the parent directory to the path to import inventag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inventag.discovery.service_descriptions import (
    ServiceDescriptionManager,
    DescriptionTemplate,
    ServiceDescription,
)


def main():
    """Demonstrate Service Description Management Framework functionality"""
    print("=== InvenTag Service Description Management Framework Demonstration ===\n")

    # Sample resource data for demonstration
    sample_resources = [
        {
            "id": "i-1234567890abcdef0",
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "account_id": "123456789012",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "tags": {"Name": "web-server", "Environment": "production"},
            "service_attributes": {
                "InstanceType": "t3.medium",
                "State": {"Name": "running"},
                "Placement": {"AvailabilityZone": "us-east-1a"},
                "VpcId": "vpc-12345",
                "SubnetId": "subnet-12345",
            },
        },
        {
            "id": "vol-1234567890abcdef0",
            "service": "EC2",
            "type": "Volume",
            "region": "us-east-1",
            "account_id": "123456789012",
            "arn": "arn:aws:ec2:us-east-1:123456789012:volume/vol-1234567890abcdef0",
            "tags": {"Name": "web-server-root", "Environment": "production"},
            "service_attributes": {
                "Size": 20,
                "VolumeType": "gp3",
                "State": "in-use",
                "Encrypted": True,
            },
        },
        {
            "id": "production-data-bucket",
            "service": "S3",
            "type": "Bucket",
            "region": "us-east-1",
            "account_id": "123456789012",
            "arn": "arn:aws:s3:::production-data-bucket",
            "tags": {"Environment": "production", "Owner": "data-team"},
            "service_attributes": {
                "encryption": {
                    "enabled": True,
                    "ServerSideEncryptionConfiguration": {
                        "Rules": [
                            {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                        ]
                    },
                },
                "versioning_status": "Enabled",
                "public_access_block": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                },
            },
        },
        {
            "id": "prod-database",
            "service": "RDS",
            "type": "DBInstance",
            "region": "us-west-2",
            "account_id": "123456789012",
            "arn": "arn:aws:rds:us-west-2:123456789012:db:prod-database",
            "tags": {"Environment": "production", "Owner": "backend-team"},
            "service_attributes": {
                "Engine": "mysql",
                "EngineVersion": "8.0.35",
                "DBInstanceClass": "db.t3.micro",
                "MultiAZ": True,
                "StorageEncrypted": True,
            },
        },
        {
            "id": "data-processor",
            "service": "Lambda",
            "type": "Function",
            "region": "us-east-1",
            "account_id": "123456789012",
            "arn": "arn:aws:lambda:us-east-1:123456789012:function:data-processor",
            "tags": {"Environment": "production", "Owner": "data-team"},
            "service_attributes": {
                "Runtime": "python3.11",
                "MemorySize": 512,
                "Timeout": 300,
                "Handler": "lambda_function.lambda_handler",
            },
        },
    ]

    print("1. Initializing Service Description Manager with default descriptions...")
    manager = ServiceDescriptionManager()

    # Show configuration information
    config_info = manager.get_configuration_info()
    print(f"   Default services: {config_info['default_services']}")
    print(f"   Total default descriptions: {config_info['total_default_descriptions']}")
    print(f"   Registered templates: {len(config_info['registered_templates'])}")
    print()

    print("2. Applying default descriptions to sample resources...")
    enriched_resources = manager.apply_descriptions_to_resources(sample_resources)

    for resource in enriched_resources:
        print(f"   {resource['service']} {resource['type']} ({resource['id']}):")
        print(f"     Description: {resource['service_description']}")

        if "description_metadata" in resource:
            metadata = resource["description_metadata"]
            print(f"     Template used: {metadata.get('template_used', 'None')}")
            print(f"     Custom description: {metadata.get('has_custom_description', False)}")
        print()

    print("3. Creating custom configuration with advanced templates...")

    # Create custom configuration
    custom_config = {
        "service_descriptions": {
            "EC2": {
                "default": {
                    "description": "Amazon Elastic Compute Cloud - Scalable virtual servers",
                    "template": "custom_ec2_default",
                },
                "Instance": {
                    "description": "Virtual machine instance providing scalable compute capacity",
                    "template": "custom_ec2_instance",
                    "attributes": {"category": "compute", "managed": True},
                },
                "Volume": {
                    "description": "Block storage volume for EC2 instances",
                    "template": "custom_ec2_volume",
                },
            },
            "S3": {
                "Bucket": {
                    "description": "Object storage container with advanced security features",
                    "template": "custom_s3_bucket",
                }
            },
            "RDS": {
                "DBInstance": {
                    "description": "Managed relational database with high availability",
                    "template": "custom_rds_instance",
                }
            },
        },
        "templates": {
            "custom_ec2_instance": {
                "template": "EC2 Instance {resource_id} - {instance_type} server running in {availability_zone} (Status: {state_name})",
                "required_attributes": [
                    "service_attributes.InstanceType",
                    "service_attributes.State.Name",
                ],
                "optional_attributes": ["service_attributes.Placement.AvailabilityZone"],
                "fallback_template": "custom_ec2_default",
            },
            "custom_ec2_volume": {
                "template": "EBS Volume {resource_id} - {size}GB {volume_type} storage (State: {state})",
                "required_attributes": [
                    "service_attributes.Size",
                    "service_attributes.VolumeType",
                    "service_attributes.State",
                ],
                "fallback_template": "custom_ec2_default",
            },
            "custom_s3_bucket": {
                "template": "S3 Bucket {resource_id} - Secure object storage with {encryption_status} encryption and {versioning_status} versioning",
                "required_attributes": [],
                "optional_attributes": [
                    "service_attributes.encryption.enabled",
                    "service_attributes.versioning_status",
                ],
                "fallback_template": "s3_default",
            },
            "custom_rds_instance": {
                "template": "RDS Database {resource_id} - {engine} {engine_version} ({db_instance_class}) with Multi-AZ: {multi_az}",
                "required_attributes": ["service_attributes.Engine"],
                "optional_attributes": [
                    "service_attributes.EngineVersion",
                    "service_attributes.DBInstanceClass",
                    "service_attributes.MultiAZ",
                ],
                "fallback_template": "rds_default",
            },
            "custom_ec2_default": {
                "template": "Amazon EC2 {resource_type} {resource_id} - Compute resource in {region}",
                "required_attributes": [],
                "optional_attributes": [],
            },
        },
    }

    # Save custom configuration to file
    config_file = "demo_service_descriptions.yaml"
    with open(config_file, "w") as f:
        yaml.dump(custom_config, f, default_flow_style=False, indent=2)

    print(f"   Custom configuration saved to: {config_file}")
    print()

    print("4. Loading custom configuration and applying advanced descriptions...")
    custom_manager = ServiceDescriptionManager(config_path=config_file)

    # Apply custom descriptions
    custom_enriched_resources = custom_manager.apply_descriptions_to_resources(sample_resources)

    for resource in custom_enriched_resources:
        print(f"   {resource['service']} {resource['type']} ({resource['id']}):")
        print(f"     Custom Description: {resource['service_description']}")

        if "description_metadata" in resource:
            metadata = resource["description_metadata"]
            print(f"     Template used: {metadata.get('template_used', 'None')}")
            print(f"     Has custom description: {metadata.get('has_custom_description', False)}")
        print()

    print("5. Demonstrating template engine capabilities...")

    # Register a new template dynamically
    dynamic_template = DescriptionTemplate(
        name="dynamic_lambda",
        template="Lambda Function {resource_id} - {runtime} runtime with {memory_size}MB memory (Timeout: {timeout}s)",
        required_attributes=["service_attributes.Runtime"],
        optional_attributes=[
            "service_attributes.MemorySize",
            "service_attributes.Timeout",
        ],
        fallback_template="lambda_default",
    )

    custom_manager.template_engine.register_template(dynamic_template)
    print(f"   Registered dynamic template: {dynamic_template.name}")

    # Apply the new template to Lambda function
    lambda_resource = next(r for r in sample_resources if r["service"] == "Lambda")
    dynamic_description = custom_manager.template_engine.render_template(
        "dynamic_lambda", lambda_resource
    )
    print(f"   Dynamic Lambda description: {dynamic_description}")
    print()

    print("6. Configuration management features...")

    # Get updated configuration information
    updated_config_info = custom_manager.get_configuration_info()
    print(f"   Config path: {updated_config_info['config_path']}")
    print(f"   Last reload: {updated_config_info['last_reload']}")
    print(f"   Custom services: {updated_config_info['custom_services']}")
    print(f"   Total custom descriptions: {updated_config_info['total_custom_descriptions']}")
    print(f"   Registered templates: {len(updated_config_info['registered_templates'])}")
    print()

    print("7. Exporting configuration template for customization...")
    template_file = "exported_service_descriptions_template.yaml"
    success = custom_manager.export_configuration_template(
        output_path=template_file, format_type="yaml"
    )

    if success:
        print(f"   Configuration template exported to: {template_file}")

        # Show a snippet of the exported template
        with open(template_file, "r") as f:
            template_content = f.read()

        print("   Template snippet:")
        lines = template_content.split("\n")[:15]  # First 15 lines
        for line in lines:
            print(f"     {line}")
        print("     ...")
    print()

    print("8. Demonstrating fallback mechanisms...")

    # Create a resource with missing attributes to test fallbacks
    incomplete_resource = {
        "id": "incomplete-instance",
        "service": "EC2",
        "type": "Instance",
        "region": "us-east-1",
        "account_id": "123456789012",
        "tags": {"Name": "incomplete-instance"},
        "service_attributes": {
            # Missing InstanceType and State - should trigger fallback
            "Placement": {"AvailabilityZone": "us-east-1b"}
        },
    }

    print("   Testing fallback with incomplete resource attributes:")
    fallback_description = custom_manager.get_dynamic_description(incomplete_resource)
    print(f"   Fallback description: {fallback_description}")
    print()

    print("9. Performance and statistics...")

    # Process all resources and show statistics
    all_enriched = custom_manager.apply_descriptions_to_resources(
        sample_resources + [incomplete_resource]
    )

    # Count template usage
    template_usage = {}
    custom_descriptions = 0

    for resource in all_enriched:
        if "description_metadata" in resource:
            metadata = resource["description_metadata"]
            template_used = metadata.get("template_used", "None")
            template_usage[template_used] = template_usage.get(template_used, 0) + 1

            if metadata.get("has_custom_description", False):
                custom_descriptions += 1

    print(f"   Total resources processed: {len(all_enriched)}")
    print(f"   Resources with custom descriptions: {custom_descriptions}")
    print("   Template usage statistics:")
    for template, count in template_usage.items():
        print(f"     {template}: {count} resources")
    print()

    print("10. Integration example with JSON export...")

    # Export enriched resources with descriptions
    export_data = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "description_config": config_file,
            "total_resources": len(all_enriched),
            "custom_descriptions": custom_descriptions,
        },
        "resources": all_enriched,
    }

    export_file = "enriched_resources_with_descriptions.json"
    with open(export_file, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"   Enriched resources exported to: {export_file}")
    print()

    print("=== Service Description Management Framework Demonstration Complete ===")
    print("\nKey capabilities demonstrated:")
    print("✓ Default service descriptions with built-in templates")
    print("✓ Custom configuration loading with YAML support")
    print("✓ Advanced template system with variable substitution")
    print("✓ Intelligent fallback mechanisms for missing attributes")
    print("✓ Dynamic template registration and management")
    print("✓ Configuration export and template generation")
    print("✓ Comprehensive metadata tracking and statistics")
    print("✓ Integration with resource discovery and enrichment")
    print("✓ Performance optimization and batch processing")
    print("✓ Error handling and graceful degradation")

    # Cleanup demo files
    cleanup_files = [config_file, template_file, export_file]
    print(f"\nDemo files created: {', '.join(cleanup_files)}")
    print(
        "You can examine these files to understand the configuration format and output structure."
    )


if __name__ == "__main__":
    main()
