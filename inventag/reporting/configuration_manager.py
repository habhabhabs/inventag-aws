#!/usr/bin/env python3
"""
Configuration Management Framework

Comprehensive configuration management system for service descriptions,
tag mappings, document templates, and branding configurations.

Features:
- Service descriptions configuration loading (YAML/JSON)
- Tag mapping configuration with custom attribute definitions
- Document template configuration with validation
- Branding configuration with logo and styling options
- Configuration validation and error handling with helpful messages
"""

import logging
import os
import json
import yaml
from typing import Dict, List, Any, Optional, Union, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from abc import ABC, abstractmethod
try:
    import jsonschema
    from jsonschema import validate, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    # Create placeholder for ValidationError
    class ValidationError(Exception):
        def __init__(self, message):
            self.message = message
            super().__init__(message)

from .template_framework import DocumentTemplate, TemplateManager
from .branding_system import AdvancedBrandingConfig, BrandingThemeManager
from .document_generator import BrandingConfig


@dataclass
class ServiceDescriptionConfig:
    """Service description configuration."""
    service_name: str
    default_description: str
    resource_types: Dict[str, str] = field(default_factory=dict)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    display_name: Optional[str] = None
    category: Optional[str] = None
    documentation_url: Optional[str] = None


@dataclass
class TagMappingConfig:
    """Tag mapping configuration."""
    tag_key: str
    display_name: str
    column_name: str
    description: str = ""
    default_value: Any = None
    data_type: str = "string"  # string, number, boolean, date
    required: bool = False
    validation_pattern: Optional[str] = None
    allowed_values: Optional[List[str]] = None


@dataclass
class DocumentTemplateConfig:
    """Document template configuration."""
    template_name: str
    template_path: str
    format_type: str
    enabled: bool = True
    description: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    custom_sections: List[str] = field(default_factory=list)


@dataclass
class BrandingConfigurationSet:
    """Complete branding configuration set."""
    name: str
    description: str = ""
    branding_config: Optional[AdvancedBrandingConfig] = None
    logo_configurations: Dict[str, str] = field(default_factory=dict)
    color_themes: Dict[str, Dict[str, str]] = field(default_factory=dict)
    font_configurations: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ConfigurationSet:
    """Complete configuration set for BOM generation."""
    name: str
    description: str = ""
    version: str = "1.0"
    created_at: Optional[datetime] = None
    
    # Configuration components
    service_descriptions: Dict[str, ServiceDescriptionConfig] = field(default_factory=dict)
    tag_mappings: Dict[str, TagMappingConfig] = field(default_factory=dict)
    document_templates: Dict[str, DocumentTemplateConfig] = field(default_factory=dict)
    branding_configurations: Dict[str, BrandingConfigurationSet] = field(default_factory=dict)
    
    # Global settings
    default_template: Optional[str] = None
    default_branding: Optional[str] = None
    output_directory: str = "."
    enable_validation: bool = True
    
    # Custom settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)


class ConfigurationValidator:
    """Validates configuration files and provides detailed error messages."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ConfigurationValidator")
        self._schemas = self._initialize_schemas()
    
    def _initialize_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Initialize JSON schemas for configuration validation."""
        return {
            "service_descriptions": {
                "type": "object",
                "patternProperties": {
                    "^[A-Z][A-Z0-9]*$": {
                        "type": "object",
                        "properties": {
                            "default_description": {"type": "string"},
                            "display_name": {"type": "string"},
                            "category": {"type": "string"},
                            "documentation_url": {"type": "string", "format": "uri"},
                            "resource_types": {
                                "type": "object",
                                "patternProperties": {
                                    ".*": {"type": "string"}
                                }
                            },
                            "custom_fields": {"type": "object"}
                        },
                        "required": ["default_description"]
                    }
                }
            },
            
            "tag_mappings": {
                "type": "object",
                "patternProperties": {
                    ".*": {
                        "type": "object",
                        "properties": {
                            "display_name": {"type": "string"},
                            "column_name": {"type": "string"},
                            "description": {"type": "string"},
                            "default_value": {},
                            "data_type": {
                                "type": "string",
                                "enum": ["string", "number", "boolean", "date"]
                            },
                            "required": {"type": "boolean"},
                            "validation_pattern": {"type": "string"},
                            "allowed_values": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["display_name", "column_name"]
                    }
                }
            },
            
            "branding_config": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "company_tagline": {"type": "string"},
                    "document_classification": {"type": "string"},
                    "logo": {
                        "type": "object",
                        "properties": {
                            "enabled": {"type": "boolean"},
                            "logo_path": {"type": "string"},
                            "positions": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "size": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2
                            }
                        }
                    },
                    "colors": {
                        "type": "object",
                        "properties": {
                            "primary": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                            "secondary": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                            "accent": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"}
                        }
                    }
                },
                "required": ["company_name"]
            }
        }
    
    def validate_service_descriptions(self, config: Dict[str, Any]) -> List[str]:
        """Validate service descriptions configuration."""
        errors = []
        
        if JSONSCHEMA_AVAILABLE:
            try:
                validate(instance=config, schema=self._schemas["service_descriptions"])
            except ValidationError as e:
                errors.append(f"Service descriptions validation error: {e.message}")
        else:
            errors.append("jsonschema library not available - skipping schema validation")
        
        # Additional custom validations
        for service_name, service_config in config.items():
            if not service_name.isupper():
                errors.append(f"Service name '{service_name}' should be uppercase")
            
            if len(service_config.get("default_description", "")) < 10:
                errors.append(f"Service '{service_name}' description is too short")
        
        return errors
    
    def validate_tag_mappings(self, config: Dict[str, Any]) -> List[str]:
        """Validate tag mappings configuration."""
        errors = []
        
        if JSONSCHEMA_AVAILABLE:
            try:
                validate(instance=config, schema=self._schemas["tag_mappings"])
            except ValidationError as e:
                errors.append(f"Tag mappings validation error: {e.message}")
        else:
            errors.append("jsonschema library not available - skipping schema validation")
        
        # Check for duplicate column names
        column_names = set()
        for tag_key, tag_config in config.items():
            column_name = tag_config.get("column_name", "")
            if column_name in column_names:
                errors.append(f"Duplicate column name '{column_name}' for tag '{tag_key}'")
            column_names.add(column_name)
            
            # Validate tag key format
            if not tag_key.startswith(("inventag:", "custom:", "org:")):
                errors.append(f"Tag key '{tag_key}' should use a recognized prefix")
        
        return errors
    
    def validate_branding_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate branding configuration."""
        errors = []
        
        if JSONSCHEMA_AVAILABLE:
            try:
                validate(instance=config, schema=self._schemas["branding_config"])
            except ValidationError as e:
                errors.append(f"Branding configuration validation error: {e.message}")
        else:
            errors.append("jsonschema library not available - skipping schema validation")
        
        # Validate logo file exists
        logo_config = config.get("logo", {})
        if logo_config.get("enabled") and logo_config.get("logo_path"):
            logo_path = logo_config["logo_path"]
            if not os.path.exists(logo_path):
                errors.append(f"Logo file not found: {logo_path}")
        
        return errors
    
    def validate_configuration_set(self, config_set: ConfigurationSet) -> List[str]:
        """Validate complete configuration set."""
        errors = []
        
        # Validate service descriptions
        service_desc_dict = {name: asdict(config) for name, config in config_set.service_descriptions.items()}
        errors.extend(self.validate_service_descriptions(service_desc_dict))
        
        # Validate tag mappings
        tag_mapping_dict = {name: asdict(config) for name, config in config_set.tag_mappings.items()}
        errors.extend(self.validate_tag_mappings(tag_mapping_dict))
        
        # Validate template references
        if config_set.default_template and config_set.default_template not in config_set.document_templates:
            errors.append(f"Default template '{config_set.default_template}' not found in templates")
        
        # Validate branding references
        if config_set.default_branding and config_set.default_branding not in config_set.branding_configurations:
            errors.append(f"Default branding '{config_set.default_branding}' not found in branding configurations")
        
        return errors


class ConfigurationLoader:
    """Loads configuration from various sources."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ConfigurationLoader")
        self.validator = ConfigurationValidator()
    
    def load_from_file(self, config_path: str) -> ConfigurationSet:
        """Load configuration from file."""
        self.logger.info(f"Loading configuration from: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.endswith('.json'):
                    config_data = json.load(f)
                elif config_path.endswith(('.yaml', '.yml')):
                    config_data = yaml.safe_load(f)
                else:
                    raise ValueError(f"Unsupported configuration format: {config_path}")
            
            config_set = self._parse_configuration_data(config_data)
            
            # Validate configuration
            if config_set.enable_validation:
                errors = self.validator.validate_configuration_set(config_set)
                if errors:
                    self.logger.warning(f"Configuration validation issues: {errors}")
            
            self.logger.info(f"Successfully loaded configuration: {config_set.name}")
            return config_set
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration from {config_path}: {e}")
            raise
    
    def load_service_descriptions(self, config_path: str) -> Dict[str, ServiceDescriptionConfig]:
        """Load service descriptions from file."""
        self.logger.info(f"Loading service descriptions from: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.endswith('.json'):
                    data = json.load(f)
                elif config_path.endswith(('.yaml', '.yml')):
                    data = yaml.safe_load(f)
                else:
                    raise ValueError(f"Unsupported format: {config_path}")
            
            # Validate
            errors = self.validator.validate_service_descriptions(data)
            if errors:
                self.logger.warning(f"Service descriptions validation issues: {errors}")
            
            # Parse into ServiceDescriptionConfig objects
            service_descriptions = {}
            for service_name, service_data in data.items():
                service_descriptions[service_name] = ServiceDescriptionConfig(
                    service_name=service_name,
                    default_description=service_data["default_description"],
                    resource_types=service_data.get("resource_types", {}),
                    custom_fields=service_data.get("custom_fields", {}),
                    display_name=service_data.get("display_name"),
                    category=service_data.get("category"),
                    documentation_url=service_data.get("documentation_url")
                )
            
            self.logger.info(f"Loaded {len(service_descriptions)} service descriptions")
            return service_descriptions
            
        except Exception as e:
            self.logger.error(f"Failed to load service descriptions: {e}")
            raise
    
    def load_tag_mappings(self, config_path: str) -> Dict[str, TagMappingConfig]:
        """Load tag mappings from file."""
        self.logger.info(f"Loading tag mappings from: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.endswith('.json'):
                    data = json.load(f)
                elif config_path.endswith(('.yaml', '.yml')):
                    data = yaml.safe_load(f)
                else:
                    raise ValueError(f"Unsupported format: {config_path}")
            
            # Validate
            errors = self.validator.validate_tag_mappings(data)
            if errors:
                self.logger.warning(f"Tag mappings validation issues: {errors}")
            
            # Parse into TagMappingConfig objects
            tag_mappings = {}
            for tag_key, tag_data in data.items():
                tag_mappings[tag_key] = TagMappingConfig(
                    tag_key=tag_key,
                    display_name=tag_data["display_name"],
                    column_name=tag_data["column_name"],
                    description=tag_data.get("description", ""),
                    default_value=tag_data.get("default_value"),
                    data_type=tag_data.get("data_type", "string"),
                    required=tag_data.get("required", False),
                    validation_pattern=tag_data.get("validation_pattern"),
                    allowed_values=tag_data.get("allowed_values")
                )
            
            self.logger.info(f"Loaded {len(tag_mappings)} tag mappings")
            return tag_mappings
            
        except Exception as e:
            self.logger.error(f"Failed to load tag mappings: {e}")
            raise
    
    def _parse_configuration_data(self, data: Dict[str, Any]) -> ConfigurationSet:
        """Parse configuration data into ConfigurationSet object."""
        config_set = ConfigurationSet(
            name=data.get("name", "Default Configuration"),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            created_at=datetime.now(timezone.utc),
            default_template=data.get("default_template"),
            default_branding=data.get("default_branding"),
            output_directory=data.get("output_directory", "."),
            enable_validation=data.get("enable_validation", True),
            custom_settings=data.get("custom_settings", {})
        )
        
        # Parse service descriptions
        service_desc_data = data.get("service_descriptions", {})
        for service_name, service_data in service_desc_data.items():
            config_set.service_descriptions[service_name] = ServiceDescriptionConfig(
                service_name=service_name,
                default_description=service_data["default_description"],
                resource_types=service_data.get("resource_types", {}),
                custom_fields=service_data.get("custom_fields", {}),
                display_name=service_data.get("display_name"),
                category=service_data.get("category"),
                documentation_url=service_data.get("documentation_url")
            )
        
        # Parse tag mappings
        tag_mapping_data = data.get("tag_mappings", {})
        for tag_key, tag_data in tag_mapping_data.items():
            config_set.tag_mappings[tag_key] = TagMappingConfig(
                tag_key=tag_key,
                display_name=tag_data["display_name"],
                column_name=tag_data["column_name"],
                description=tag_data.get("description", ""),
                default_value=tag_data.get("default_value"),
                data_type=tag_data.get("data_type", "string"),
                required=tag_data.get("required", False),
                validation_pattern=tag_data.get("validation_pattern"),
                allowed_values=tag_data.get("allowed_values")
            )
        
        # Parse document templates
        template_data = data.get("document_templates", {})
        for template_name, template_config in template_data.items():
            config_set.document_templates[template_name] = DocumentTemplateConfig(
                template_name=template_name,
                template_path=template_config["template_path"],
                format_type=template_config["format_type"],
                enabled=template_config.get("enabled", True),
                description=template_config.get("description", ""),
                variables=template_config.get("variables", {}),
                custom_sections=template_config.get("custom_sections", [])
            )
        
        # Parse branding configurations
        branding_data = data.get("branding_configurations", {})
        for branding_name, branding_config in branding_data.items():
            config_set.branding_configurations[branding_name] = BrandingConfigurationSet(
                name=branding_name,
                description=branding_config.get("description", ""),
                logo_configurations=branding_config.get("logo_configurations", {}),
                color_themes=branding_config.get("color_themes", {}),
                font_configurations=branding_config.get("font_configurations", {})
            )
        
        return config_set


class ConfigurationManager:
    """Manages all configuration aspects for BOM generation."""
    
    def __init__(self, config_directory: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.ConfigurationManager")
        self.config_directory = config_directory or "config"
        self.loader = ConfigurationLoader()
        self.validator = ConfigurationValidator()
        self.template_manager = TemplateManager()
        self.branding_manager = BrandingThemeManager()
        
        # Configuration cache
        self._config_cache: Dict[str, ConfigurationSet] = {}
        self._service_descriptions_cache: Dict[str, Dict[str, ServiceDescriptionConfig]] = {}
        self._tag_mappings_cache: Dict[str, Dict[str, TagMappingConfig]] = {}
    
    def load_configuration(self, config_name: str) -> ConfigurationSet:
        """Load configuration by name."""
        if config_name in self._config_cache:
            return self._config_cache[config_name]
        
        # Try to find configuration file
        config_path = self._find_config_file(config_name)
        if not config_path:
            raise FileNotFoundError(f"Configuration not found: {config_name}")
        
        config_set = self.loader.load_from_file(config_path)
        self._config_cache[config_name] = config_set
        
        return config_set
    
    def get_service_descriptions(self, config_name: Optional[str] = None) -> Dict[str, ServiceDescriptionConfig]:
        """Get service descriptions from configuration."""
        if config_name:
            config_set = self.load_configuration(config_name)
            return config_set.service_descriptions
        else:
            # Load from default service descriptions file
            return self._load_default_service_descriptions()
    
    def get_tag_mappings(self, config_name: Optional[str] = None) -> Dict[str, TagMappingConfig]:
        """Get tag mappings from configuration."""
        if config_name:
            config_set = self.load_configuration(config_name)
            return config_set.tag_mappings
        else:
            # Load from default tag mappings file
            return self._load_default_tag_mappings()
    
    def get_branding_configuration(self, config_name: str, branding_name: Optional[str] = None) -> Optional[AdvancedBrandingConfig]:
        """Get branding configuration."""
        config_set = self.load_configuration(config_name)
        
        branding_name = branding_name or config_set.default_branding
        if not branding_name:
            return None
        
        branding_set = config_set.branding_configurations.get(branding_name)
        if not branding_set:
            return None
        
        return branding_set.branding_config
    
    def create_default_configuration(self) -> ConfigurationSet:
        """Create a default configuration set."""
        self.logger.info("Creating default configuration set")
        
        config_set = ConfigurationSet(
            name="Default Configuration",
            description="Default configuration for BOM generation",
            version="1.0",
            created_at=datetime.now(timezone.utc)
        )
        
        # Add default service descriptions
        config_set.service_descriptions = self._create_default_service_descriptions()
        
        # Add default tag mappings
        config_set.tag_mappings = self._create_default_tag_mappings()
        
        # Add default document templates
        config_set.document_templates = self._create_default_document_templates()
        
        # Add default branding
        config_set.branding_configurations = self._create_default_branding_configurations()
        
        config_set.default_template = "default_word"
        config_set.default_branding = "professional_blue"
        
        return config_set
    
    def save_configuration(self, config_set: ConfigurationSet, output_path: str):
        """Save configuration set to file."""
        self.logger.info(f"Saving configuration to: {output_path}")
        
        try:
            # Convert to dictionary
            config_data = self._config_set_to_dict(config_set)
            
            # Save based on file extension
            with open(output_path, 'w', encoding='utf-8') as f:
                if output_path.endswith('.json'):
                    json.dump(config_data, f, indent=2, ensure_ascii=False, default=str)
                elif output_path.endswith(('.yaml', '.yml')):
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                else:
                    raise ValueError(f"Unsupported output format: {output_path}")
            
            self.logger.info(f"Configuration saved successfully: {output_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise
    
    def validate_configuration(self, config_set: ConfigurationSet) -> List[str]:
        """Validate configuration and return list of issues."""
        return self.validator.validate_configuration_set(config_set)
    
    def _find_config_file(self, config_name: str) -> Optional[str]:
        """Find configuration file by name."""
        config_dir = Path(self.config_directory)
        
        # Try different extensions
        for ext in ['.json', '.yaml', '.yml']:
            config_path = config_dir / f"{config_name}{ext}"
            if config_path.exists():
                return str(config_path)
        
        return None
    
    def _load_default_service_descriptions(self) -> Dict[str, ServiceDescriptionConfig]:
        """Load default service descriptions."""
        if "default" in self._service_descriptions_cache:
            return self._service_descriptions_cache["default"]
        
        # Try to load from file
        service_desc_path = Path(self.config_directory) / "service_descriptions.yaml"
        if service_desc_path.exists():
            descriptions = self.loader.load_service_descriptions(str(service_desc_path))
            self._service_descriptions_cache["default"] = descriptions
            return descriptions
        else:
            # Return default descriptions
            descriptions = self._create_default_service_descriptions()
            self._service_descriptions_cache["default"] = descriptions
            return descriptions
    
    def _load_default_tag_mappings(self) -> Dict[str, TagMappingConfig]:
        """Load default tag mappings."""
        if "default" in self._tag_mappings_cache:
            return self._tag_mappings_cache["default"]
        
        # Try to load from file
        tag_mappings_path = Path(self.config_directory) / "tag_mappings.yaml"
        if tag_mappings_path.exists():
            mappings = self.loader.load_tag_mappings(str(tag_mappings_path))
            self._tag_mappings_cache["default"] = mappings
            return mappings
        else:
            # Return default mappings
            mappings = self._create_default_tag_mappings()
            self._tag_mappings_cache["default"] = mappings
            return mappings
    
    def _create_default_service_descriptions(self) -> Dict[str, ServiceDescriptionConfig]:
        """Create default service descriptions."""
        return {
            "EC2": ServiceDescriptionConfig(
                service_name="EC2",
                default_description="Amazon Elastic Compute Cloud - Virtual servers in the cloud",
                display_name="EC2 (Elastic Compute Cloud)",
                category="Compute",
                resource_types={
                    "Instance": "Virtual machine instances providing scalable compute capacity",
                    "Volume": "Block storage volumes attached to EC2 instances",
                    "SecurityGroup": "Virtual firewall controlling traffic to instances",
                    "KeyPair": "Key pairs for secure instance access"
                }
            ),
            "S3": ServiceDescriptionConfig(
                service_name="S3",
                default_description="Amazon Simple Storage Service - Object storage service",
                display_name="S3 (Simple Storage Service)",
                category="Storage",
                resource_types={
                    "Bucket": "Container for objects stored in Amazon S3"
                }
            ),
            "RDS": ServiceDescriptionConfig(
                service_name="RDS",
                default_description="Amazon Relational Database Service - Managed relational database",
                display_name="RDS (Relational Database Service)",
                category="Database",
                resource_types={
                    "DBInstance": "Managed database instance",
                    "DBCluster": "Database cluster for high availability",
                    "DBSubnetGroup": "Subnet group for database placement"
                }
            ),
            "LAMBDA": ServiceDescriptionConfig(
                service_name="LAMBDA",
                default_description="AWS Lambda - Serverless compute service",
                display_name="Lambda",
                category="Compute",
                resource_types={
                    "Function": "Serverless function that runs code in response to events"
                }
            ),
            "VPC": ServiceDescriptionConfig(
                service_name="VPC",
                default_description="Amazon Virtual Private Cloud - Isolated cloud resources",
                display_name="VPC (Virtual Private Cloud)",
                category="Networking",
                resource_types={
                    "VPC": "Virtual private cloud providing network isolation",
                    "Subnet": "Subnet within a VPC for resource placement",
                    "InternetGateway": "Gateway for internet access",
                    "RouteTable": "Route table for network traffic routing"
                }
            )
        }
    
    def _create_default_tag_mappings(self) -> Dict[str, TagMappingConfig]:
        """Create default tag mappings."""
        return {
            "inventag:remarks": TagMappingConfig(
                tag_key="inventag:remarks",
                display_name="Remarks",
                column_name="Remarks",
                description="Additional remarks about the resource",
                default_value="",
                data_type="string"
            ),
            "inventag:costcenter": TagMappingConfig(
                tag_key="inventag:costcenter",
                display_name="Cost Center",
                column_name="Cost Center",
                description="Cost center responsible for the resource",
                default_value="Unknown",
                data_type="string",
                required=True
            ),
            "inventag:owner": TagMappingConfig(
                tag_key="inventag:owner",
                display_name="Owner",
                column_name="Owner",
                description="Resource owner or responsible team",
                default_value="",
                data_type="string"
            ),
            "inventag:environment": TagMappingConfig(
                tag_key="inventag:environment",
                display_name="Environment",
                column_name="Environment",
                description="Environment classification (dev, test, prod)",
                default_value="unknown",
                data_type="string",
                allowed_values=["dev", "test", "staging", "prod", "unknown"]
            ),
            "inventag:criticality": TagMappingConfig(
                tag_key="inventag:criticality",
                display_name="Criticality",
                column_name="Criticality",
                description="Business criticality level",
                default_value="medium",
                data_type="string",
                allowed_values=["low", "medium", "high", "critical"]
            )
        }
    
    def _create_default_document_templates(self) -> Dict[str, DocumentTemplateConfig]:
        """Create default document template configurations."""
        return {
            "default_word": DocumentTemplateConfig(
                template_name="default_word",
                template_path="templates/default_word_template.yaml",
                format_type="word",
                description="Default Word document template"
            ),
            "default_excel": DocumentTemplateConfig(
                template_name="default_excel",
                template_path="templates/default_excel_template.json",
                format_type="excel",
                description="Default Excel workbook template"
            )
        }
    
    def _create_default_branding_configurations(self) -> Dict[str, BrandingConfigurationSet]:
        """Create default branding configurations."""
        return {
            "professional_blue": BrandingConfigurationSet(
                name="professional_blue",
                description="Professional blue theme",
                color_themes={
                    "primary": {"primary": "#366092", "secondary": "#4472C4", "accent": "#70AD47"}
                }
            ),
            "corporate_green": BrandingConfigurationSet(
                name="corporate_green",
                description="Corporate green theme",
                color_themes={
                    "primary": {"primary": "#2E7D32", "secondary": "#4CAF50", "accent": "#8BC34A"}
                }
            )
        }
    
    def _config_set_to_dict(self, config_set: ConfigurationSet) -> Dict[str, Any]:
        """Convert ConfigurationSet to dictionary."""
        data = {
            "name": config_set.name,
            "description": config_set.description,
            "version": config_set.version,
            "created_at": config_set.created_at.isoformat() if config_set.created_at else None,
            "default_template": config_set.default_template,
            "default_branding": config_set.default_branding,
            "output_directory": config_set.output_directory,
            "enable_validation": config_set.enable_validation,
            "custom_settings": config_set.custom_settings,
            "service_descriptions": {},
            "tag_mappings": {},
            "document_templates": {},
            "branding_configurations": {}
        }
        
        # Convert service descriptions
        for name, config in config_set.service_descriptions.items():
            data["service_descriptions"][name] = asdict(config)
        
        # Convert tag mappings
        for name, config in config_set.tag_mappings.items():
            data["tag_mappings"][name] = asdict(config)
        
        # Convert document templates
        for name, config in config_set.document_templates.items():
            data["document_templates"][name] = asdict(config)
        
        # Convert branding configurations
        for name, config in config_set.branding_configurations.items():
            data["branding_configurations"][name] = asdict(config)
        
        return data


# Factory function
def create_configuration_manager(config_directory: Optional[str] = None) -> ConfigurationManager:
    """Create a ConfigurationManager instance."""
    return ConfigurationManager(config_directory)