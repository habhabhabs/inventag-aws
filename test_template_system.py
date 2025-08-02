#!/usr/bin/env python3
"""
Test script for the advanced document customization and template system.
"""

import sys
import os
sys.path.append('.')

from inventag.reporting.template_framework import TemplateManager, create_template_manager
from inventag.reporting.branding_system import BrandingThemeManager, create_default_branding_config
from inventag.reporting.configuration_manager import ConfigurationManager, create_configuration_manager

def test_template_framework():
    """Test the template framework."""
    print("Testing Template Framework...")
    
    # Create template manager
    template_manager = create_template_manager("templates")
    
    # Create default template
    default_template = template_manager.create_default_template("word")
    print(f"Created default template: {default_template.name}")
    print(f"Template has {len(default_template.sections)} sections")
    print(f"Template variables: {list(default_template.variables.keys())}")
    
    # Test template validation
    issues = template_manager.validate_template(default_template)
    if issues:
        print(f"Template validation issues: {issues}")
    else:
        print("Template validation passed!")
    
    print("✓ Template Framework test completed\n")

def test_branding_system():
    """Test the branding system."""
    print("Testing Branding System...")
    
    # Create branding theme manager
    branding_manager = BrandingThemeManager()
    
    # List available themes
    themes = branding_manager.list_themes()
    print(f"Available themes: {themes}")
    
    # Get a theme
    theme = branding_manager.get_theme("professional_blue")
    if theme:
        print(f"Loaded theme with company: {theme.company_name}")
        print(f"Primary color: {theme.colors.primary}")
        print(f"Primary font: {theme.fonts.primary_font}")
    
    # Create custom theme
    custom_theme = branding_manager.create_custom_theme(
        "professional_blue",
        company_name="Test Company",
        primary_color="#FF6B35"
    )
    print(f"Created custom theme for: {custom_theme.company_name}")
    print(f"Custom primary color: {custom_theme.colors.primary}")
    
    print("✓ Branding System test completed\n")

def test_configuration_manager():
    """Test the configuration management system."""
    print("Testing Configuration Manager...")
    
    # Create configuration manager
    config_manager = create_configuration_manager("config")
    
    # Create default configuration
    default_config = config_manager.create_default_configuration()
    print(f"Created default configuration: {default_config.name}")
    print(f"Service descriptions: {len(default_config.service_descriptions)}")
    print(f"Tag mappings: {len(default_config.tag_mappings)}")
    print(f"Document templates: {len(default_config.document_templates)}")
    
    # Test validation
    issues = config_manager.validate_configuration(default_config)
    if issues:
        print(f"Configuration validation issues: {issues}")
    else:
        print("Configuration validation passed!")
    
    # Test service descriptions
    service_descriptions = config_manager.get_service_descriptions()
    print(f"Loaded {len(service_descriptions)} service descriptions")
    if "EC2" in service_descriptions:
        ec2_desc = service_descriptions["EC2"]
        print(f"EC2 description: {ec2_desc.default_description[:50]}...")
    
    # Test tag mappings
    tag_mappings = config_manager.get_tag_mappings()
    print(f"Loaded {len(tag_mappings)} tag mappings")
    if "inventag:owner" in tag_mappings:
        owner_mapping = tag_mappings["inventag:owner"]
        print(f"Owner mapping column: {owner_mapping.column_name}")
    
    print("✓ Configuration Manager test completed\n")

def main():
    """Run all tests."""
    print("Testing Advanced Document Customization and Template System")
    print("=" * 60)
    
    try:
        test_template_framework()
        test_branding_system()
        test_configuration_manager()
        
        print("🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())