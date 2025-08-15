#!/usr/bin/env python3
"""
Service Description Management Framework

Provides service description loading, management, and application to AWS resources.
Supports YAML/JSON configuration files with schema validation and template system.
"""

import json
import yaml
import logging
import os
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
from abc import ABC, abstractmethod


@dataclass
class ServiceDescription:
    """Service description configuration."""

    service: str
    resource_type: Optional[str] = None
    description: str = ""
    template: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    fallback: Optional[str] = None
    last_updated: Optional[str] = None


@dataclass
class DescriptionTemplate:
    """Template for dynamic description generation."""

    name: str
    template: str
    required_attributes: List[str] = field(default_factory=list)
    optional_attributes: List[str] = field(default_factory=list)
    fallback_template: Optional[str] = None


class DescriptionTemplateEngine:
    """Template engine for dynamic description generation."""

    def __init__(self):
        """Initialize template engine."""
        self.logger = logging.getLogger(f"{__name__}.DescriptionTemplateEngine")
        self.templates: Dict[str, DescriptionTemplate] = {}

    def register_template(self, template: DescriptionTemplate):
        """Register a description template."""
        self.templates[template.name] = template
        self.logger.debug(f"Registered template: {template.name}")

    def render_template(
        self, template_name: str, resource: Dict[str, Any]
    ) -> Optional[str]:
        """Render a template with resource attributes."""
        if template_name not in self.templates:
            self.logger.warning(f"Template not found: {template_name}")
            return None

        template = self.templates[template_name]

        try:
            # Check if required attributes are available
            missing_required = []
            for attr in template.required_attributes:
                if not self._get_nested_attribute(resource, attr):
                    missing_required.append(attr)

            if missing_required:
                self.logger.debug(
                    f"Missing required attributes for template {template_name}: {missing_required}"
                )
                if template.fallback_template:
                    return self.render_template(template.fallback_template, resource)
                return None

            # Prepare template variables
            template_vars = {}

            # Add required attributes
            for attr in template.required_attributes:
                value = self._get_nested_attribute(resource, attr)
                var_name = self._attribute_to_variable_name(attr)
                template_vars[var_name] = value

            # Add optional attributes
            for attr in template.optional_attributes:
                value = self._get_nested_attribute(resource, attr)
                if value:
                    var_name = self._attribute_to_variable_name(attr)
                    template_vars[var_name] = value

            # Add common resource attributes
            template_vars.update(
                {
                    "resource_id": resource.get("id", "Unknown"),
                    "resource_type": resource.get("type", "Unknown"),
                    "service": resource.get("service", "Unknown"),
                    "region": resource.get("region", "Unknown"),
                    "account_id": resource.get("account_id", "Unknown"),
                }
            )

            # Render template
            rendered = template.template.format(**template_vars)
            return rendered

        except Exception as e:
            self.logger.warning(f"Failed to render template {template_name}: {e}")
            if template.fallback_template:
                return self.render_template(template.fallback_template, resource)
            return None

    def _get_nested_attribute(self, resource: Dict[str, Any], attr_path: str) -> Any:
        """Get nested attribute from resource using dot notation."""
        try:
            value = resource
            for part in attr_path.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None

            return value
        except Exception:
            return None

    def _attribute_to_variable_name(self, attr_path: str) -> str:
        """Convert attribute path to template variable name."""
        # Remove service_attributes prefix and convert to snake_case variable name
        if attr_path.startswith("service_attributes."):
            attr_path = attr_path[len("service_attributes.") :]

        # Convert CamelCase to snake_case and replace dots with underscores
        # Handle nested attributes like Placement.AvailabilityZone -> availability_zone
        parts = attr_path.split(".")
        converted_parts = []

        for part in parts:
            # Convert CamelCase to snake_case
            snake_case = re.sub("([A-Z]+)([A-Z][a-z])", r"\1_\2", part)
            snake_case = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", snake_case)
            converted_parts.append(snake_case.lower())

        return "_".join(converted_parts)

    def list_templates(self) -> List[str]:
        """List all registered templates."""
        return list(self.templates.keys())


class ServiceDescriptionManager:
    """Manages service descriptions with configuration loading and template support."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize service description manager."""
        self.logger = logging.getLogger(f"{__name__}.ServiceDescriptionManager")
        self.descriptions: Dict[str, Dict[str, ServiceDescription]] = {}
        self.template_engine = DescriptionTemplateEngine()
        self.config_path = config_path
        self.last_reload = None
        self._default_descriptions = self._load_default_descriptions()

        # Load configuration if provided
        if config_path:
            self.load_descriptions_from_file(config_path)

    def _load_default_descriptions(self) -> Dict[str, Dict[str, ServiceDescription]]:
        """Load default AWS service descriptions."""
        defaults = {
            "EC2": {
                "default": ServiceDescription(
                    service="EC2",
                    description="Amazon Elastic Compute Cloud - Scalable virtual servers in the cloud",
                    template="ec2_default",
                ),
                "Instance": ServiceDescription(
                    service="EC2",
                    resource_type="Instance",
                    description="Virtual machine instance providing scalable compute capacity",
                    template="ec2_instance",
                ),
                "Volume": ServiceDescription(
                    service="EC2",
                    resource_type="Volume",
                    description="Block storage volume for EC2 instances",
                    template="ec2_volume",
                ),
                "SecurityGroup": ServiceDescription(
                    service="EC2",
                    resource_type="SecurityGroup",
                    description="Virtual firewall controlling inbound and outbound traffic",
                    template="ec2_security_group",
                ),
            },
            "S3": {
                "default": ServiceDescription(
                    service="S3",
                    description="Amazon Simple Storage Service - Scalable object storage",
                    template="s3_default",
                ),
                "Bucket": ServiceDescription(
                    service="S3",
                    resource_type="Bucket",
                    description="Container for objects stored in Amazon S3",
                    template="s3_bucket",
                ),
            },
            "RDS": {
                "default": ServiceDescription(
                    service="RDS",
                    description="Amazon Relational Database Service - Managed relational databases",
                    template="rds_default",
                ),
                "DBInstance": ServiceDescription(
                    service="RDS",
                    resource_type="DBInstance",
                    description="Managed relational database instance",
                    template="rds_instance",
                ),
                "DBCluster": ServiceDescription(
                    service="RDS",
                    resource_type="DBCluster",
                    description="Managed database cluster for high availability",
                    template="rds_cluster",
                ),
            },
            "LAMBDA": {
                "default": ServiceDescription(
                    service="LAMBDA",
                    description="AWS Lambda - Serverless compute service",
                    template="lambda_default",
                ),
                "Function": ServiceDescription(
                    service="LAMBDA",
                    resource_type="Function",
                    description="Serverless function that runs code in response to events",
                    template="lambda_function",
                ),
            },
            "VPC": {
                "default": ServiceDescription(
                    service="VPC",
                    description="Amazon Virtual Private Cloud - Isolated cloud resources",
                    template="vpc_default",
                ),
                "VPC": ServiceDescription(
                    service="VPC",
                    resource_type="VPC",
                    description="Logically isolated section of AWS cloud",
                    template="vpc_vpc",
                ),
                "Subnet": ServiceDescription(
                    service="VPC",
                    resource_type="Subnet",
                    description="Range of IP addresses in a VPC",
                    template="vpc_subnet",
                ),
            },
        }

        # Register default templates
        self._register_default_templates()

        return defaults

    def _register_default_templates(self):
        """Register default description templates."""
        templates = [
            DescriptionTemplate(
                name="ec2_instance",
                template="EC2 Instance ({resource_id}) - {instance_type} instance in {placement_availability_zone}",
                required_attributes=["service_attributes.InstanceType"],
                optional_attributes=["service_attributes.Placement.AvailabilityZone"],
                fallback_template="ec2_default",
            ),
            DescriptionTemplate(
                name="ec2_volume",
                template="EBS Volume ({resource_id}) - {volume_size}GB {volume_type} volume",
                required_attributes=[
                    "service_attributes.Size",
                    "service_attributes.VolumeType",
                ],
                fallback_template="ec2_default",
            ),
            DescriptionTemplate(
                name="ec2_security_group",
                template="Security Group ({resource_id}) - {group_name} controlling network access",
                required_attributes=["service_attributes.GroupName"],
                fallback_template="ec2_default",
            ),
            DescriptionTemplate(
                name="s3_bucket",
                template="S3 Bucket ({resource_id}) - Object storage with {encryption_status} encryption",
                optional_attributes=[
                    "service_attributes.encryption.ServerSideEncryptionConfiguration"
                ],
                fallback_template="s3_default",
            ),
            DescriptionTemplate(
                name="rds_instance",
                template="RDS Instance ({resource_id}) - {engine} {engine_version} database",
                required_attributes=["service_attributes.Engine"],
                optional_attributes=["service_attributes.EngineVersion"],
                fallback_template="rds_default",
            ),
            DescriptionTemplate(
                name="lambda_function",
                template="Lambda Function ({resource_id}) - {runtime} function with {memory}MB memory",
                required_attributes=["service_attributes.Runtime"],
                optional_attributes=["service_attributes.MemorySize"],
                fallback_template="lambda_default",
            ),
            # Fallback templates
            DescriptionTemplate(
                name="ec2_default",
                template="Amazon EC2 {resource_type} ({resource_id}) in {region}",
                required_attributes=[],
                optional_attributes=[],
            ),
            DescriptionTemplate(
                name="s3_default",
                template="Amazon S3 {resource_type} ({resource_id})",
                required_attributes=[],
                optional_attributes=[],
            ),
            DescriptionTemplate(
                name="rds_default",
                template="Amazon RDS {resource_type} ({resource_id}) in {region}",
                required_attributes=[],
                optional_attributes=[],
            ),
            DescriptionTemplate(
                name="lambda_default",
                template="AWS Lambda {resource_type} ({resource_id}) in {region}",
                required_attributes=[],
                optional_attributes=[],
            ),
            DescriptionTemplate(
                name="vpc_default",
                template="Amazon VPC {resource_type} ({resource_id}) in {region}",
                required_attributes=[],
                optional_attributes=[],
            ),
            DescriptionTemplate(
                name="vpc_vpc",
                template="VPC ({resource_id}) - {cidr_block} network in {region}",
                optional_attributes=["service_attributes.CidrBlock"],
                fallback_template="vpc_default",
            ),
            DescriptionTemplate(
                name="vpc_subnet",
                template="Subnet ({resource_id}) - {cidr_block} in {availability_zone}",
                optional_attributes=[
                    "service_attributes.CidrBlock",
                    "service_attributes.AvailabilityZone",
                ],
                fallback_template="vpc_default",
            ),
        ]

        for template in templates:
            self.template_engine.register_template(template)

    def load_descriptions_from_file(self, config_path: str) -> bool:
        """Load service descriptions from YAML or JSON file with schema validation."""
        try:
            if not os.path.exists(config_path):
                self.logger.warning(f"Configuration file not found: {config_path}")
                return False

            with open(config_path, "r", encoding="utf-8") as f:
                if config_path.lower().endswith(
                    ".yaml"
                ) or config_path.lower().endswith(".yml"):
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)

            if not self._validate_config_schema(config_data):
                return False

            self._parse_config_data(config_data)
            self.config_path = config_path
            self.last_reload = datetime.now(timezone.utc)

            self.logger.info(
                f"Successfully loaded service descriptions from {config_path}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to load service descriptions from {config_path}: {e}"
            )
            return False

    def _validate_config_schema(self, config_data: Dict[str, Any]) -> bool:
        """Validate configuration schema."""
        if not isinstance(config_data, dict):
            self.logger.error("Configuration must be a dictionary")
            return False

        # Check for required top-level keys
        if "service_descriptions" not in config_data:
            self.logger.error("Configuration must contain 'service_descriptions' key")
            return False

        service_descriptions = config_data["service_descriptions"]
        if not isinstance(service_descriptions, dict):
            self.logger.error("'service_descriptions' must be a dictionary")
            return False

        # Validate each service description
        for service, descriptions in service_descriptions.items():
            if not isinstance(descriptions, dict):
                self.logger.error(
                    f"Service '{service}' descriptions must be a dictionary"
                )
                return False

            for resource_type, desc_config in descriptions.items():
                if not isinstance(desc_config, dict):
                    self.logger.error(
                        f"Description for {service}/{resource_type} must be a dictionary"
                    )
                    return False

                # Check required fields
                if "description" not in desc_config:
                    self.logger.error(
                        f"Description for {service}/{resource_type} must have 'description' field"
                    )
                    return False

        return True

    def _parse_config_data(self, config_data: Dict[str, Any]):
        """Parse configuration data into service descriptions."""
        service_descriptions = config_data["service_descriptions"]

        # Parse templates if provided
        if "templates" in config_data:
            self._parse_templates(config_data["templates"])

        # Parse service descriptions
        for service, descriptions in service_descriptions.items():
            service_upper = service.upper()

            if service_upper not in self.descriptions:
                self.descriptions[service_upper] = {}

            for resource_type, desc_config in descriptions.items():
                description = ServiceDescription(
                    service=service_upper,
                    resource_type=resource_type if resource_type != "default" else None,
                    description=desc_config["description"],
                    template=desc_config.get("template"),
                    attributes=desc_config.get("attributes", {}),
                    fallback=desc_config.get("fallback"),
                    last_updated=datetime.now(timezone.utc).isoformat(),
                )

                self.descriptions[service_upper][resource_type] = description

    def _parse_templates(self, templates_config: Dict[str, Any]):
        """Parse template configurations."""
        for template_name, template_config in templates_config.items():
            if (
                not isinstance(template_config, dict)
                or "template" not in template_config
            ):
                self.logger.warning(
                    f"Invalid template configuration for {template_name}"
                )
                continue

            template = DescriptionTemplate(
                name=template_name,
                template=template_config["template"],
                required_attributes=template_config.get("required_attributes", []),
                optional_attributes=template_config.get("optional_attributes", []),
                fallback_template=template_config.get("fallback_template"),
            )

            self.template_engine.register_template(template)

    def get_service_description(
        self, service: str, resource_type: Optional[str] = None
    ) -> str:
        """Get custom description for AWS service/resource type with intelligent fallbacks."""
        service_upper = service.upper()

        # Strategy 1: Exact match (service + resource_type)
        if resource_type and service_upper in self.descriptions:
            if resource_type in self.descriptions[service_upper]:
                desc = self.descriptions[service_upper][resource_type]
                return desc.description

        # Strategy 2: Service default
        if (
            service_upper in self.descriptions
            and "default" in self.descriptions[service_upper]
        ):
            desc = self.descriptions[service_upper]["default"]
            return desc.description

        # Strategy 3: Default descriptions (built-in)
        if service_upper in self._default_descriptions:
            if (
                resource_type
                and resource_type in self._default_descriptions[service_upper]
            ):
                desc = self._default_descriptions[service_upper][resource_type]
                return desc.description
            elif "default" in self._default_descriptions[service_upper]:
                desc = self._default_descriptions[service_upper]["default"]
                return desc.description

        # Strategy 4: Generic fallback
        if resource_type:
            return f"AWS {service} {resource_type} - Cloud resource managed by Amazon Web Services"
        else:
            return f"AWS {service} - Amazon Web Services cloud service"

    def get_dynamic_description(self, resource: Dict[str, Any]) -> str:
        """Generate dynamic description using templates and resource attributes."""
        service = resource.get("service", "").upper()
        resource_type = resource.get("type", "")

        # Try to find a description with template
        template_name = None

        # Check custom descriptions first
        if service in self.descriptions:
            if resource_type and resource_type in self.descriptions[service]:
                desc = self.descriptions[service][resource_type]
                if desc.template:
                    template_name = desc.template
            elif "default" in self.descriptions[service]:
                desc = self.descriptions[service]["default"]
                if desc.template:
                    template_name = desc.template

        # Check default descriptions
        if not template_name and service in self._default_descriptions:
            if resource_type and resource_type in self._default_descriptions[service]:
                desc = self._default_descriptions[service][resource_type]
                if desc.template:
                    template_name = desc.template
            elif "default" in self._default_descriptions[service]:
                desc = self._default_descriptions[service]["default"]
                if desc.template:
                    template_name = desc.template

        # Render template if found
        if template_name:
            rendered = self.template_engine.render_template(template_name, resource)
            if rendered:
                return rendered

        # Fall back to static description
        return self.get_service_description(service, resource_type)

    def apply_descriptions_to_resources(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Add service descriptions to resource data."""
        enriched_resources = []

        for resource in resources:
            try:
                # Create a copy to avoid modifying original
                enriched_resource = resource.copy()

                # Get dynamic description
                description = self.get_dynamic_description(resource)
                enriched_resource["service_description"] = description

                # Add description metadata
                enriched_resource["description_metadata"] = {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "description_source": "ServiceDescriptionManager",
                    "has_custom_description": self._has_custom_description(
                        resource.get("service", ""), resource.get("type", "")
                    ),
                    "template_used": self._get_template_name(resource),
                }

                enriched_resources.append(enriched_resource)

            except Exception as e:
                self.logger.warning(
                    f"Failed to apply description to resource {resource.get('id', 'unknown')}: {e}"
                )
                enriched_resources.append(resource)  # Add original resource

        self.logger.info(f"Applied descriptions to {len(enriched_resources)} resources")
        return enriched_resources

    def _has_custom_description(self, service: str, resource_type: str) -> bool:
        """Check if resource has custom (non-default) description."""
        service_upper = service.upper()

        # Check if there's a custom description loaded from config
        if service_upper in self.descriptions:
            if resource_type and resource_type in self.descriptions[service_upper]:
                return True
            if "default" in self.descriptions[service_upper]:
                return True

        return False

    def _get_template_name(self, resource: Dict[str, Any]) -> Optional[str]:
        """Get template name used for resource description."""
        service = resource.get("service", "").upper()
        resource_type = resource.get("type", "")

        # Check custom descriptions
        if service in self.descriptions:
            if resource_type and resource_type in self.descriptions[service]:
                return self.descriptions[service][resource_type].template
            elif "default" in self.descriptions[service]:
                return self.descriptions[service]["default"].template

        # Check default descriptions
        if service in self._default_descriptions:
            if resource_type and resource_type in self._default_descriptions[service]:
                return self._default_descriptions[service][resource_type].template
            elif "default" in self._default_descriptions[service]:
                return self._default_descriptions[service]["default"].template

        return None

    def reload_descriptions(self, config_path: Optional[str] = None) -> bool:
        """Reload descriptions from updated config file."""
        path_to_use = config_path or self.config_path

        if not path_to_use:
            self.logger.warning("No configuration path specified for reload")
            return False

        # Clear existing custom descriptions
        self.descriptions.clear()

        # Reload from file
        success = self.load_descriptions_from_file(path_to_use)

        if success:
            self.logger.info(f"Successfully reloaded descriptions from {path_to_use}")
        else:
            self.logger.error(f"Failed to reload descriptions from {path_to_use}")

        return success

    def get_configuration_info(self) -> Dict[str, Any]:
        """Get information about current configuration."""
        return {
            "config_path": self.config_path,
            "last_reload": self.last_reload.isoformat() if self.last_reload else None,
            "custom_services": len(self.descriptions),
            "default_services": len(self._default_descriptions),
            "total_custom_descriptions": sum(
                len(descs) for descs in self.descriptions.values()
            ),
            "total_default_descriptions": sum(
                len(descs) for descs in self._default_descriptions.values()
            ),
            "registered_templates": self.template_engine.list_templates(),
        }

    def export_configuration_template(
        self, output_path: str, format_type: str = "yaml"
    ) -> bool:
        """Export a configuration template with examples."""
        template_config = {
            "service_descriptions": {
                "EC2": {
                    "default": {
                        "description": "Amazon Elastic Compute Cloud - Scalable virtual servers",
                        "template": "ec2_default",
                    },
                    "Instance": {
                        "description": "Virtual machine instance providing compute capacity",
                        "template": "ec2_instance",
                        "attributes": {"category": "compute", "managed": True},
                    },
                },
                "S3": {
                    "default": {
                        "description": "Amazon Simple Storage Service - Object storage",
                        "template": "s3_default",
                    },
                    "Bucket": {
                        "description": "Container for objects in S3",
                        "template": "s3_bucket",
                    },
                },
            },
            "templates": {
                "custom_ec2_instance": {
                    "template": "EC2 Instance {resource_id} - {instance_type} in {region}",
                    "required_attributes": ["service_attributes.InstanceType"],
                    "optional_attributes": ["region"],
                    "fallback_template": "ec2_default",
                }
            },
        }

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                if format_type.lower() == "yaml":
                    yaml.dump(template_config, f, default_flow_style=False, indent=2)
                else:
                    json.dump(template_config, f, indent=2)

            self.logger.info(f"Exported configuration template to {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export configuration template: {e}")
            return False
