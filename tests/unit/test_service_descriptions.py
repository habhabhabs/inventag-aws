#!/usr/bin/env python3
"""
Unit tests for ServiceDescriptionManager

Tests service description loading, template rendering, and resource enrichment.
"""

import pytest
import json
import yaml
import tempfile
import os
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timezone

from inventag.discovery.service_descriptions import (
    ServiceDescriptionManager,
    ServiceDescription,
    DescriptionTemplate,
    DescriptionTemplateEngine,
)


class TestDescriptionTemplateEngine:
    """Test cases for DescriptionTemplateEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = DescriptionTemplateEngine()

    def test_register_template(self):
        """Test template registration."""
        template = DescriptionTemplate(
            name="test_template",
            template="Test {resource_id} in {region}",
            required_attributes=["resource_id"],
            optional_attributes=["region"],
        )

        self.engine.register_template(template)
        assert "test_template" in self.engine.templates
        assert self.engine.templates["test_template"] == template

    def test_render_template_success(self):
        """Test successful template rendering."""
        template = DescriptionTemplate(
            name="ec2_template",
            template="EC2 Instance {resource_id} - {instance_type} in {region}",
            required_attributes=["service_attributes.InstanceType"],
            optional_attributes=["region"],
        )

        self.engine.register_template(template)

        resource = {
            "id": "i-1234567890abcdef0",
            "type": "Instance",
            "service": "EC2",
            "region": "us-east-1",
            "service_attributes": {"InstanceType": "t3.micro"},
        }

        result = self.engine.render_template("ec2_template", resource)
        expected = "EC2 Instance i-1234567890abcdef0 - t3.micro in us-east-1"
        assert result == expected

    def test_render_template_missing_required_attribute(self):
        """Test template rendering with missing required attribute."""
        template = DescriptionTemplate(
            name="test_template",
            template="Test {resource_id} - {required_attr}",
            required_attributes=["service_attributes.required_attr"],
        )

        self.engine.register_template(template)

        resource = {"id": "test-resource", "service_attributes": {}}

        result = self.engine.render_template("test_template", resource)
        assert result is None

    def test_render_template_with_fallback(self):
        """Test template rendering with fallback template."""
        fallback_template = DescriptionTemplate(
            name="fallback_template",
            template="Fallback for {resource_id}",
            required_attributes=[],
        )

        main_template = DescriptionTemplate(
            name="main_template",
            template="Main {resource_id} - {missing_attr}",
            required_attributes=["service_attributes.missing_attr"],
            fallback_template="fallback_template",
        )

        self.engine.register_template(fallback_template)
        self.engine.register_template(main_template)

        resource = {"id": "test-resource", "service_attributes": {}}

        result = self.engine.render_template("main_template", resource)
        assert result == "Fallback for test-resource"

    def test_render_template_nested_attributes(self):
        """Test template rendering with nested attributes."""
        template = DescriptionTemplate(
            name="nested_template",
            template="Resource {resource_id} in {placement_availability_zone}",
            required_attributes=["service_attributes.Placement.AvailabilityZone"],
        )

        self.engine.register_template(template)

        resource = {
            "id": "test-resource",
            "service_attributes": {"Placement": {"AvailabilityZone": "us-east-1a"}},
        }

        result = self.engine.render_template("nested_template", resource)
        assert result == "Resource test-resource in us-east-1a"

    def test_render_template_not_found(self):
        """Test rendering non-existent template."""
        resource = {"id": "test-resource"}
        result = self.engine.render_template("nonexistent", resource)
        assert result is None

    def test_list_templates(self):
        """Test listing registered templates."""
        template1 = DescriptionTemplate(name="template1", template="Test 1")
        template2 = DescriptionTemplate(name="template2", template="Test 2")

        self.engine.register_template(template1)
        self.engine.register_template(template2)

        templates = self.engine.list_templates()
        assert "template1" in templates
        assert "template2" in templates


class TestServiceDescriptionManager:
    """Test cases for ServiceDescriptionManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ServiceDescriptionManager()

    def test_initialization_without_config(self):
        """Test manager initialization without config file."""
        manager = ServiceDescriptionManager()

        # Should have default descriptions
        assert "EC2" in manager._default_descriptions
        assert "S3" in manager._default_descriptions
        assert "RDS" in manager._default_descriptions

        # Should have registered default templates
        templates = manager.template_engine.list_templates()
        assert "ec2_instance" in templates
        assert "s3_bucket" in templates

    def test_get_service_description_default(self):
        """Test getting default service descriptions."""
        # Test service with resource type
        desc = self.manager.get_service_description("EC2", "Instance")
        assert "Virtual machine instance" in desc

        # Test service default
        desc = self.manager.get_service_description("EC2")
        assert "Elastic Compute Cloud" in desc

        # Test unknown service
        desc = self.manager.get_service_description("UNKNOWN", "Resource")
        assert "AWS UNKNOWN Resource" in desc

    def test_load_descriptions_from_yaml_file(self):
        """Test loading descriptions from YAML file."""
        config_data = {
            "service_descriptions": {
                "EC2": {
                    "default": {"description": "Custom EC2 description"},
                    "Instance": {
                        "description": "Custom EC2 Instance description",
                        "template": "custom_ec2_template",
                    },
                },
                "CUSTOM": {"default": {"description": "Custom service description"}},
            },
            "templates": {
                "custom_ec2_template": {
                    "template": "Custom EC2 {resource_id}",
                    "required_attributes": [],
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            success = self.manager.load_descriptions_from_file(temp_path)
            assert success

            # Test custom descriptions are loaded
            desc = self.manager.get_service_description("EC2")
            assert desc == "Custom EC2 description"

            desc = self.manager.get_service_description("EC2", "Instance")
            assert desc == "Custom EC2 Instance description"

            desc = self.manager.get_service_description("CUSTOM")
            assert desc == "Custom service description"

            # Test custom template is registered
            templates = self.manager.template_engine.list_templates()
            assert "custom_ec2_template" in templates

        finally:
            os.unlink(temp_path)

    def test_load_descriptions_from_json_file(self):
        """Test loading descriptions from JSON file."""
        config_data = {
            "service_descriptions": {
                "S3": {"default": {"description": "Custom S3 description"}}
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            success = self.manager.load_descriptions_from_file(temp_path)
            assert success

            desc = self.manager.get_service_description("S3")
            assert desc == "Custom S3 description"

        finally:
            os.unlink(temp_path)

    def test_load_descriptions_invalid_schema(self):
        """Test loading descriptions with invalid schema."""
        invalid_configs = [
            # Missing service_descriptions key
            {"invalid": "config"},
            # service_descriptions not a dict
            {"service_descriptions": "invalid"},
            # Service descriptions not a dict
            {"service_descriptions": {"EC2": "invalid"}},
            # Missing description field
            {"service_descriptions": {"EC2": {"default": {"template": "test"}}}},
        ]

        for config_data in invalid_configs:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(config_data, f)
                temp_path = f.name

            try:
                success = self.manager.load_descriptions_from_file(temp_path)
                assert not success
            finally:
                os.unlink(temp_path)

    def test_load_descriptions_file_not_found(self):
        """Test loading descriptions from non-existent file."""
        success = self.manager.load_descriptions_from_file("/nonexistent/path.yaml")
        assert not success

    def test_get_dynamic_description_with_template(self):
        """Test dynamic description generation with templates."""
        resource = {
            "id": "i-1234567890abcdef0",
            "type": "Instance",
            "service": "EC2",
            "region": "us-east-1",
            "service_attributes": {
                "InstanceType": "t3.micro",
                "Placement": {"AvailabilityZone": "us-east-1a"},
            },
        }

        desc = self.manager.get_dynamic_description(resource)

        # Should use the ec2_instance template
        assert "i-1234567890abcdef0" in desc
        assert "t3.micro" in desc

    def test_get_dynamic_description_fallback(self):
        """Test dynamic description generation with fallback."""
        resource = {
            "id": "test-resource",
            "type": "UnknownType",
            "service": "UNKNOWN",
            "region": "us-east-1",
        }

        desc = self.manager.get_dynamic_description(resource)

        # Should fall back to generic description
        assert "AWS UNKNOWN UnknownType" in desc

    def test_apply_descriptions_to_resources(self):
        """Test applying descriptions to resource list."""
        resources = [
            {
                "id": "i-1234567890abcdef0",
                "type": "Instance",
                "service": "EC2",
                "region": "us-east-1",
                "service_attributes": {"InstanceType": "t3.micro"},
            },
            {
                "id": "bucket-name",
                "type": "Bucket",
                "service": "S3",
                "region": "us-east-1",
            },
        ]

        enriched = self.manager.apply_descriptions_to_resources(resources)

        assert len(enriched) == 2

        # Check first resource
        assert "service_description" in enriched[0]
        assert "description_metadata" in enriched[0]
        assert enriched[0]["service_description"] != ""

        # Check second resource
        assert "service_description" in enriched[1]
        assert "description_metadata" in enriched[1]
        assert enriched[1]["service_description"] != ""

        # Check metadata
        metadata = enriched[0]["description_metadata"]
        assert "generated_at" in metadata
        assert "description_source" in metadata
        assert metadata["description_source"] == "ServiceDescriptionManager"

    def test_apply_descriptions_error_handling(self):
        """Test error handling in description application."""
        # Resource with missing required fields
        resources = [
            {"id": "test"},  # Missing service field
            {"id": "valid-resource", "service": "EC2", "type": "Instance"},
        ]

        enriched = self.manager.apply_descriptions_to_resources(resources)

        # Should still return all resources
        assert len(enriched) == 2

        # Valid resource should have description
        assert "service_description" in enriched[1]

    def test_reload_descriptions(self):
        """Test reloading descriptions from file."""
        # Create initial config
        config_data = {
            "service_descriptions": {
                "EC2": {"default": {"description": "Initial description"}}
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            # Load initial config
            self.manager.load_descriptions_from_file(temp_path)
            desc = self.manager.get_service_description("EC2")
            assert desc == "Initial description"

            # Update config file
            updated_config = {
                "service_descriptions": {
                    "EC2": {"default": {"description": "Updated description"}}
                }
            }

            with open(temp_path, "w") as f:
                yaml.dump(updated_config, f)

            # Reload
            success = self.manager.reload_descriptions()
            assert success

            # Check updated description
            desc = self.manager.get_service_description("EC2")
            assert desc == "Updated description"

        finally:
            os.unlink(temp_path)

    def test_reload_descriptions_no_path(self):
        """Test reloading descriptions without config path."""
        success = self.manager.reload_descriptions()
        assert not success

    def test_get_configuration_info(self):
        """Test getting configuration information."""
        info = self.manager.get_configuration_info()

        assert "config_path" in info
        assert "last_reload" in info
        assert "custom_services" in info
        assert "default_services" in info
        assert "total_custom_descriptions" in info
        assert "total_default_descriptions" in info
        assert "registered_templates" in info

        # Should have default services
        assert info["default_services"] > 0
        assert len(info["registered_templates"]) > 0

    def test_export_configuration_template_yaml(self):
        """Test exporting configuration template as YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            success = self.manager.export_configuration_template(temp_path, "yaml")
            assert success

            # Verify file was created and is valid YAML
            with open(temp_path, "r") as f:
                config = yaml.safe_load(f)

            assert "service_descriptions" in config
            assert "templates" in config
            assert "EC2" in config["service_descriptions"]
            assert "S3" in config["service_descriptions"]

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_export_configuration_template_json(self):
        """Test exporting configuration template as JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            success = self.manager.export_configuration_template(temp_path, "json")
            assert success

            # Verify file was created and is valid JSON
            with open(temp_path, "r") as f:
                config = json.load(f)

            assert "service_descriptions" in config
            assert "templates" in config

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_has_custom_description(self):
        """Test checking for custom descriptions."""
        # Load custom config
        config_data = {
            "service_descriptions": {
                "EC2": {"default": {"description": "Custom EC2 description"}}
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            self.manager.load_descriptions_from_file(temp_path)

            # Should have custom description
            assert self.manager._has_custom_description("EC2", "Instance")

            # Should not have custom description
            assert not self.manager._has_custom_description("S3", "Bucket")

        finally:
            os.unlink(temp_path)

    def test_get_template_name(self):
        """Test getting template name for resource."""
        resource = {"service": "EC2", "type": "Instance"}

        template_name = self.manager._get_template_name(resource)
        assert template_name == "ec2_instance"

        # Unknown resource
        resource = {"service": "UNKNOWN", "type": "Unknown"}

        template_name = self.manager._get_template_name(resource)
        assert template_name is None


class TestServiceDescriptionIntegration:
    """Integration tests for service description functionality."""

    def test_end_to_end_workflow(self):
        """Test complete workflow from config to resource enrichment."""
        # Create comprehensive config
        config_data = {
            "service_descriptions": {
                "EC2": {
                    "Instance": {
                        "description": "Custom EC2 Instance description",
                        "template": "custom_ec2_instance",
                        "attributes": {"category": "compute", "managed": True},
                    }
                },
                "CUSTOM_SERVICE": {
                    "default": {
                        "description": "Custom service for testing",
                        "template": "custom_service_template",
                    }
                },
            },
            "templates": {
                "custom_ec2_instance": {
                    "template": "Custom EC2 {resource_id} ({instance_type}) in {region}",
                    "required_attributes": ["service_attributes.InstanceType"],
                    "optional_attributes": ["region"],
                    "fallback_template": "ec2_default",
                },
                "custom_service_template": {
                    "template": "Custom Service Resource {resource_id}",
                    "required_attributes": [],
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            # Initialize manager with config
            manager = ServiceDescriptionManager(temp_path)

            # Test resources
            resources = [
                {
                    "id": "i-1234567890abcdef0",
                    "type": "Instance",
                    "service": "EC2",
                    "region": "us-east-1",
                    "service_attributes": {"InstanceType": "t3.micro"},
                },
                {
                    "id": "custom-resource-123",
                    "type": "Resource",
                    "service": "CUSTOM_SERVICE",
                    "region": "us-west-2",
                },
                {
                    "id": "unknown-resource",
                    "type": "Unknown",
                    "service": "UNKNOWN_SERVICE",
                    "region": "eu-west-1",
                },
            ]

            # Apply descriptions
            enriched = manager.apply_descriptions_to_resources(resources)

            # Verify results
            assert len(enriched) == 3

            # EC2 instance should use custom template
            ec2_desc = enriched[0]["service_description"]
            assert "Custom EC2 i-1234567890abcdef0 (t3.micro) in us-east-1" == ec2_desc
            assert enriched[0]["description_metadata"]["has_custom_description"]

            # Custom service should use custom template
            custom_desc = enriched[1]["service_description"]
            assert "Custom Service Resource custom-resource-123" == custom_desc
            assert enriched[1]["description_metadata"]["has_custom_description"]

            # Unknown service should use fallback
            unknown_desc = enriched[2]["service_description"]
            assert "AWS UNKNOWN_SERVICE Unknown" in unknown_desc
            assert not enriched[2]["description_metadata"]["has_custom_description"]

            # Test configuration info
            info = manager.get_configuration_info()
            assert info["custom_services"] == 2
            assert info["config_path"] == temp_path
            assert info["last_reload"] is not None

        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__])
