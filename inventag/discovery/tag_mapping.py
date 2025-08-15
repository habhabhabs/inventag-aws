#!/usr/bin/env python3
"""
Tag Mapping Engine

Provides custom tag attribute extraction and mapping functionality for AWS resources.
Supports flexible tag object configuration formats and custom column header generation.
"""

import json
import yaml
import logging
import os
import re
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class TagMapping:
    """Tag mapping configuration."""

    tag: str
    name: str
    default_value: Optional[str] = ""
    description: Optional[str] = None
    validation_pattern: Optional[str] = None
    normalize_function: Optional[str] = None
    required: bool = False
    case_sensitive: bool = False


@dataclass
class TagMappingResult:
    """Result of tag mapping operation."""

    mapped_attributes: Dict[str, Any]
    missing_required_tags: List[str]
    validation_errors: List[str]
    normalized_values: Dict[str, str]


class TagNormalizer:
    """Handles tag value normalization and validation."""

    def __init__(self):
        """Initialize tag normalizer."""
        self.logger = logging.getLogger(f"{__name__}.TagNormalizer")

    def normalize_value(
        self, value: str, normalize_function: Optional[str] = None
    ) -> str:
        """Normalize tag value using specified function."""
        if not value or not normalize_function:
            return value

        try:
            if normalize_function == "lowercase":
                return value.lower()
            elif normalize_function == "uppercase":
                return value.upper()
            elif normalize_function == "title":
                return value.title()
            elif normalize_function == "strip":
                return value.strip()
            elif normalize_function == "strip_whitespace":
                return " ".join(value.split())
            elif normalize_function == "remove_special_chars":
                return re.sub(r"[^a-zA-Z0-9\s_-]", "", value)
            elif normalize_function == "alphanumeric_only":
                return re.sub(r"[^a-zA-Z0-9]", "", value)
            elif normalize_function == "slug":
                # Convert to URL-friendly slug
                slug = value.lower().strip()
                slug = re.sub(r"[^\w\s-]", "", slug)
                slug = re.sub(r"[-\s]+", "-", slug)
                return slug.strip("-")
            else:
                self.logger.warning(
                    f"Unknown normalization function: {normalize_function}"
                )
                return value

        except Exception as e:
            self.logger.warning(
                f"Failed to normalize value '{value}' with function '{normalize_function}': {e}"
            )
            return value

    def validate_value(self, value: str, pattern: Optional[str] = None) -> bool:
        """Validate tag value against pattern."""
        if not pattern:
            return True

        try:
            return bool(re.match(pattern, value))
        except Exception as e:
            self.logger.warning(
                f"Failed to validate value '{value}' against pattern '{pattern}': {e}"
            )
            return True  # Default to valid if pattern fails


class TagMappingEngine:
    """Handles custom tag attribute mappings and extracts organization-specific metadata."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize tag mapping engine."""
        self.logger = logging.getLogger(f"{__name__}.TagMappingEngine")
        self.mappings: Dict[str, TagMapping] = {}
        self.normalizer = TagNormalizer()
        self.config_path = config_path
        self.last_reload = None

        # Load configuration if provided
        if config_path:
            self.load_mappings_from_file(config_path)
        else:
            self._load_default_mappings()

    def _load_default_mappings(self):
        """Load default tag mappings."""
        default_mappings = [
            TagMapping(
                tag="inventag:remarks",
                name="Remarks",
                description="Additional remarks about the resource",
                default_value="",
                normalize_function="strip_whitespace",
            ),
            TagMapping(
                tag="inventag:costcenter",
                name="Cost Center",
                description="Cost center responsible for the resource",
                default_value="Unknown",
                normalize_function="uppercase",
                validation_pattern=r"^[A-Z0-9-]+$",
            ),
            TagMapping(
                tag="inventag:owner",
                name="Owner",
                description="Resource owner or responsible team",
                default_value="Unknown",
                normalize_function="strip_whitespace",
            ),
            TagMapping(
                tag="inventag:environment",
                name="Environment",
                description="Environment classification (dev, test, prod)",
                default_value="Unknown",
                normalize_function="lowercase",
                validation_pattern=r"^(dev|test|staging|prod|production)$",
            ),
            TagMapping(
                tag="inventag:project",
                name="Project",
                description="Project or application name",
                default_value="",
                normalize_function="strip_whitespace",
            ),
            TagMapping(
                tag="inventag:backup",
                name="Backup Required",
                description="Whether resource requires backup",
                default_value="Unknown",
                normalize_function="lowercase",
                validation_pattern=r"^(yes|no|true|false|required|optional)$",
            ),
            TagMapping(
                tag="inventag:compliance",
                name="Compliance Level",
                description="Compliance classification level",
                default_value="Standard",
                normalize_function="title",
                validation_pattern=r"^(Standard|High|Critical|PCI|HIPAA|SOX)$",
            ),
            TagMapping(
                tag="inventag:schedule",
                name="Schedule",
                description="Resource scheduling information",
                default_value="24/7",
                normalize_function="strip_whitespace",
            ),
        ]

        for mapping in default_mappings:
            self.mappings[mapping.tag] = mapping

        self.logger.info(f"Loaded {len(default_mappings)} default tag mappings")

    def load_mappings_from_file(self, config_path: str) -> bool:
        """Load tag mappings from YAML or JSON file with schema validation."""
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

            self.logger.info(f"Successfully loaded tag mappings from {config_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load tag mappings from {config_path}: {e}")
            return False

    def _validate_config_schema(self, config_data: Dict[str, Any]) -> bool:
        """Validate configuration schema."""
        if not isinstance(config_data, dict):
            self.logger.error("Configuration must be a dictionary")
            return False

        # Check for required top-level keys
        if "tag_mappings" not in config_data:
            self.logger.error("Configuration must contain 'tag_mappings' key")
            return False

        tag_mappings = config_data["tag_mappings"]
        if not isinstance(tag_mappings, list):
            self.logger.error("'tag_mappings' must be a list")
            return False

        # Validate each tag mapping
        for i, mapping in enumerate(tag_mappings):
            if not isinstance(mapping, dict):
                self.logger.error(f"Tag mapping {i} must be a dictionary")
                return False

            # Check required fields
            required_fields = ["tag", "name"]
            for field in required_fields:
                if field not in mapping:
                    self.logger.error(f"Tag mapping {i} must have '{field}' field")
                    return False

            # Validate tag format
            tag = mapping["tag"]
            if not isinstance(tag, str) or not tag.strip():
                self.logger.error(f"Tag mapping {i}: 'tag' must be a non-empty string")
                return False

            # Validate name format
            name = mapping["name"]
            if not isinstance(name, str) or not name.strip():
                self.logger.error(f"Tag mapping {i}: 'name' must be a non-empty string")
                return False

        return True

    def _parse_config_data(self, config_data: Dict[str, Any]):
        """Parse configuration data into tag mappings."""
        tag_mappings = config_data["tag_mappings"]

        # Clear existing mappings
        self.mappings.clear()

        for mapping_config in tag_mappings:
            mapping = TagMapping(
                tag=mapping_config["tag"],
                name=mapping_config["name"],
                default_value=mapping_config.get("default_value", ""),
                description=mapping_config.get("description"),
                validation_pattern=mapping_config.get("validation_pattern"),
                normalize_function=mapping_config.get("normalize_function"),
                required=mapping_config.get("required", False),
                case_sensitive=mapping_config.get("case_sensitive", False),
            )

            self.mappings[mapping.tag] = mapping

        self.logger.info(f"Parsed {len(self.mappings)} tag mappings from configuration")

    def extract_custom_attributes(self, resource: Dict[str, Any]) -> TagMappingResult:
        """Extract custom attributes based on tag mappings."""
        mapped_attributes = {}
        missing_required_tags = []
        validation_errors = []
        normalized_values = {}

        # Get resource tags
        tags = resource.get("tags", {})
        if not isinstance(tags, dict):
            tags = {}

        # Process each mapping
        for tag_key, mapping in self.mappings.items():
            # Find tag value (case sensitive or insensitive)
            tag_value = None

            if mapping.case_sensitive:
                tag_value = tags.get(tag_key)
            else:
                # Case insensitive search
                for key, value in tags.items():
                    if key.lower() == tag_key.lower():
                        tag_value = value
                        break

            # Handle missing tag
            if tag_value is None or (
                isinstance(tag_value, str) and not tag_value.strip()
            ):
                if mapping.required:
                    missing_required_tags.append(tag_key)

                # Use default value
                tag_value = mapping.default_value

            # Normalize value
            if tag_value and isinstance(tag_value, str):
                normalized_value = self.normalizer.normalize_value(
                    tag_value, mapping.normalize_function
                )
                normalized_values[tag_key] = normalized_value

                # Validate normalized value
                if mapping.validation_pattern:
                    if not self.normalizer.validate_value(
                        normalized_value, mapping.validation_pattern
                    ):
                        validation_errors.append(
                            f"Tag '{tag_key}' value '{normalized_value}' does not match pattern '{mapping.validation_pattern}'"
                        )

                tag_value = normalized_value

            # Add to mapped attributes
            mapped_attributes[mapping.name] = tag_value

        return TagMappingResult(
            mapped_attributes=mapped_attributes,
            missing_required_tags=missing_required_tags,
            validation_errors=validation_errors,
            normalized_values=normalized_values,
        )

    def apply_mappings_to_resources(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply tag mappings to all resources."""
        enriched_resources = []
        total_validation_errors = 0
        total_missing_required = 0

        for resource in resources:
            try:
                # Create a copy to avoid modifying original
                enriched_resource = resource.copy()

                # Extract custom attributes
                mapping_result = self.extract_custom_attributes(resource)

                # Add mapped attributes to resource
                enriched_resource["custom_attributes"] = (
                    mapping_result.mapped_attributes
                )

                # Add mapping metadata
                enriched_resource["tag_mapping_metadata"] = {
                    "mapped_at": datetime.now(timezone.utc).isoformat(),
                    "mapping_source": "TagMappingEngine",
                    "total_mappings": len(self.mappings),
                    "missing_required_tags": mapping_result.missing_required_tags,
                    "validation_errors": mapping_result.validation_errors,
                    "normalized_values": mapping_result.normalized_values,
                }

                # Track statistics
                total_validation_errors += len(mapping_result.validation_errors)
                total_missing_required += len(mapping_result.missing_required_tags)

                enriched_resources.append(enriched_resource)

            except Exception as e:
                self.logger.warning(
                    f"Failed to apply tag mappings to resource {resource.get('id', 'unknown')}: {e}"
                )
                enriched_resources.append(resource)  # Add original resource

        self.logger.info(
            f"Applied tag mappings to {len(enriched_resources)} resources. "
            f"Validation errors: {total_validation_errors}, Missing required: {total_missing_required}"
        )

        return enriched_resources

    def get_custom_columns(self) -> List[Dict[str, str]]:
        """Get list of custom column headers for BOM documents."""
        columns = []

        for mapping in self.mappings.values():
            columns.append(
                {
                    "name": mapping.name,
                    "tag": mapping.tag,
                    "description": mapping.description
                    or f"Custom attribute from tag {mapping.tag}",
                    "default_value": mapping.default_value,
                    "required": mapping.required,
                }
            )

        return columns

    def get_custom_column_names(self) -> List[str]:
        """Get list of custom column names for BOM documents."""
        return [mapping.name for mapping in self.mappings.values()]

    def validate_resource_tags(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Validate resource tags against all mappings."""
        mapping_result = self.extract_custom_attributes(resource)

        return {
            "resource_id": resource.get("id", "unknown"),
            "is_valid": len(mapping_result.validation_errors) == 0
            and len(mapping_result.missing_required_tags) == 0,
            "validation_errors": mapping_result.validation_errors,
            "missing_required_tags": mapping_result.missing_required_tags,
            "mapped_attributes": mapping_result.mapped_attributes,
        }

    def reload_mappings(self, config_path: Optional[str] = None) -> bool:
        """Reload mappings from updated config file."""
        path_to_use = config_path or self.config_path

        if not path_to_use:
            self.logger.warning("No configuration path specified for reload")
            return False

        # Reload from file
        success = self.load_mappings_from_file(path_to_use)

        if success:
            self.logger.info(f"Successfully reloaded tag mappings from {path_to_use}")
        else:
            self.logger.error(f"Failed to reload tag mappings from {path_to_use}")

        return success

    def add_mapping(self, mapping: TagMapping):
        """Add a new tag mapping."""
        self.mappings[mapping.tag] = mapping
        self.logger.info(f"Added tag mapping: {mapping.tag} -> {mapping.name}")

    def remove_mapping(self, tag: str) -> bool:
        """Remove a tag mapping."""
        if tag in self.mappings:
            del self.mappings[tag]
            self.logger.info(f"Removed tag mapping: {tag}")
            return True
        else:
            self.logger.warning(f"Tag mapping not found: {tag}")
            return False

    def get_mapping(self, tag: str) -> Optional[TagMapping]:
        """Get a specific tag mapping."""
        return self.mappings.get(tag)

    def list_mappings(self) -> List[TagMapping]:
        """List all tag mappings."""
        return list(self.mappings.values())

    def get_configuration_info(self) -> Dict[str, Any]:
        """Get information about current configuration."""
        return {
            "config_path": self.config_path,
            "last_reload": self.last_reload.isoformat() if self.last_reload else None,
            "total_mappings": len(self.mappings),
            "required_mappings": len([m for m in self.mappings.values() if m.required]),
            "mappings_with_validation": len(
                [m for m in self.mappings.values() if m.validation_pattern]
            ),
            "mappings_with_normalization": len(
                [m for m in self.mappings.values() if m.normalize_function]
            ),
            "tag_list": list(self.mappings.keys()),
        }

    def export_configuration_template(
        self, output_path: str, format_type: str = "yaml"
    ) -> bool:
        """Export a configuration template with examples."""
        template_config = {
            "tag_mappings": [
                {
                    "tag": "inventag:remarks",
                    "name": "Remarks",
                    "description": "Additional remarks about the resource",
                    "default_value": "",
                    "normalize_function": "strip_whitespace",
                    "required": False,
                    "case_sensitive": False,
                },
                {
                    "tag": "inventag:costcenter",
                    "name": "Cost Center",
                    "description": "Cost center responsible for the resource",
                    "default_value": "Unknown",
                    "normalize_function": "uppercase",
                    "validation_pattern": "^[A-Z0-9-]+$",
                    "required": True,
                    "case_sensitive": False,
                },
                {
                    "tag": "inventag:environment",
                    "name": "Environment",
                    "description": "Environment classification",
                    "default_value": "Unknown",
                    "normalize_function": "lowercase",
                    "validation_pattern": "^(dev|test|staging|prod|production)$",
                    "required": False,
                    "case_sensitive": False,
                },
                {
                    "tag": "custom:project-code",
                    "name": "Project Code",
                    "description": "Internal project identifier",
                    "default_value": "UNASSIGNED",
                    "normalize_function": "uppercase",
                    "validation_pattern": "^[A-Z]{2,4}-[0-9]{3,4}$",
                    "required": True,
                    "case_sensitive": True,
                },
            ]
        }

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                if format_type.lower() == "yaml":
                    yaml.dump(template_config, f, default_flow_style=False, indent=2)
                else:
                    json.dump(template_config, f, indent=2)

            self.logger.info(f"Exported tag mapping template to {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export tag mapping template: {e}")
            return False

    def generate_validation_report(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate comprehensive validation report for resources."""
        report = {
            "total_resources": len(resources),
            "valid_resources": 0,
            "invalid_resources": 0,
            "resources_with_missing_required": 0,
            "resources_with_validation_errors": 0,
            "validation_summary": {},
            "missing_tags_summary": {},
            "detailed_errors": [],
        }

        for resource in resources:
            validation_result = self.validate_resource_tags(resource)

            if validation_result["is_valid"]:
                report["valid_resources"] += 1
            else:
                report["invalid_resources"] += 1

            if validation_result["missing_required_tags"]:
                report["resources_with_missing_required"] += 1

                # Track missing tags
                for tag in validation_result["missing_required_tags"]:
                    if tag not in report["missing_tags_summary"]:
                        report["missing_tags_summary"][tag] = 0
                    report["missing_tags_summary"][tag] += 1

            if validation_result["validation_errors"]:
                report["resources_with_validation_errors"] += 1

                # Track validation errors
                for error in validation_result["validation_errors"]:
                    if error not in report["validation_summary"]:
                        report["validation_summary"][error] = 0
                    report["validation_summary"][error] += 1

            # Add detailed errors for invalid resources
            if not validation_result["is_valid"]:
                report["detailed_errors"].append(
                    {
                        "resource_id": validation_result["resource_id"],
                        "missing_required_tags": validation_result[
                            "missing_required_tags"
                        ],
                        "validation_errors": validation_result["validation_errors"],
                    }
                )

        # Calculate percentages
        if report["total_resources"] > 0:
            report["compliance_percentage"] = (
                report["valid_resources"] / report["total_resources"]
            ) * 100
        else:
            report["compliance_percentage"] = 100.0

        return report
