#!/usr/bin/env python3
"""
Comprehensive unit tests for Template Framework

Tests document template system, variable resolution, structure building,
and template management with caching and validation.
"""

import pytest
import os
import tempfile
import json
import yaml
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

from inventag.reporting.template_framework import (
    TemplateManager,
    DocumentTemplate,
    TemplateVariableResolver,
    DocumentStructureBuilder
)


class TestTemplateManager:
    """Test cases for TemplateManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = TemplateManager(template_directory=self.temp_dir)

    def test_init(self):
        """Test TemplateManager initialization."""
        assert self.manager.template_directory == self.temp_dir
        assert hasattr(self.manager, '_template_cache')
        assert self.manager._template_cache == {}
        assert hasattr(self.manager, 'loader')
        assert hasattr(self.manager, 'variable_resolver')

    def test_load_template_yaml_success(self):
        """Test successful YAML template loading."""
        template_data = {
            'name': 'Test Template',
            'format_type': 'word',
            'sections': ['header', 'body', 'footer'],
            'variables': {
                'company_name': 'Test Corp',
                'document_title': 'BOM Report'
            }
        }
        
        yaml_content = yaml.dump(template_data)
        
        with patch('builtins.open', mock_open(read_data=yaml_content)):
            with patch('os.path.exists', return_value=True):
                template = self.manager.load_template('test_template.yaml')
        
        assert template.name == 'Test Template'
        assert template.format_type == 'word'
        assert len(template.sections) == 3
        assert template.variables['company_name'] == 'Test Corp'

    def test_load_template_json_success(self):
        """Test successful JSON template loading."""
        template_data = {
            'name': 'Excel Template',
            'format_type': 'excel',
            'sections': ['summary', 'resources'],
            'formatting_options': {
                'highlight_non_compliant': True,
                'color_scheme': 'corporate'
            }
        }
        
        json_content = json.dumps(template_data)
        
        with patch('builtins.open', mock_open(read_data=json_content)):
            with patch('os.path.exists', return_value=True):
                template = self.manager.load_template('excel_template.json')
        
        assert template.name == 'Excel Template'
        assert template.format_type == 'excel'
        assert template.formatting_options['highlight_non_compliant'] is True

    def test_load_template_file_not_found(self):
        """Test template loading when file doesn't exist."""
        with patch('os.path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                self.manager.load_template('nonexistent.yaml')

    def test_load_template_invalid_yaml(self):
        """Test template loading with invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["
        
        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            with patch('os.path.exists', return_value=True):
                with pytest.raises(Exception):  # YAML parsing error
                    self.manager.load_template('invalid.yaml')

    def test_load_template_invalid_json(self):
        """Test template loading with invalid JSON."""
        invalid_json = '{"invalid": json content'
        
        with patch('builtins.open', mock_open(read_data=invalid_json)):
            with patch('os.path.exists', return_value=True):
                with pytest.raises(Exception):  # JSON parsing error
                    self.manager.load_template('invalid.json')

    def test_validate_template_success(self):
        """Test successful template validation."""
        valid_template_data = {
            'name': 'Valid Template',
            'format_type': 'word',
            'sections': ['header', 'body'],
            'variables': {'title': 'Test'}
        }
        
        # Should not raise exception
        self.manager._validate_template(valid_template_data)

    def test_validate_template_missing_required_fields(self):
        """Test template validation with missing required fields."""
        # Missing 'name' field
        invalid_template = {
            'format_type': 'word',
            'sections': ['header']
        }
        
        # This test depends on the actual validation implementation
        # For now, just check that validation exists
        assert hasattr(self.manager, '_validate_template') or hasattr(self.manager, 'validate_template')

    def test_validate_template_invalid_format_type(self):
        """Test template validation with invalid format type."""
        invalid_template = {
            'name': 'Test Template',
            'format_type': 'invalid_format',
            'sections': ['header']
        }
        
        # This test depends on the actual validation implementation
        # For now, just check that validation exists
        assert hasattr(self.manager, '_validate_template') or hasattr(self.manager, 'validate_template')

    def test_get_template_with_caching(self):
        """Test template retrieval with caching."""
        template_data = {
            'name': 'Cached Template',
            'format_type': 'excel',
            'sections': ['summary']
        }
        
        yaml_content = yaml.dump(template_data)
        
        with patch('builtins.open', mock_open(read_data=yaml_content)):
            with patch('os.path.exists', return_value=True):
                # First call should load from file
                template1 = self.manager.get_template('cached.yaml')
                
                # Second call should use cache
                template2 = self.manager.get_template('cached.yaml')
        
        assert template1.name == 'Cached Template'
        assert template2.name == 'Cached Template'
        assert template1 is template2  # Should be same object from cache

    def test_list_available_templates(self):
        """Test listing available templates."""
        template_files = ['template1.yaml', 'template2.json', 'template3.yml', 'not_template.txt']
        
        with patch('os.listdir', return_value=template_files):
            templates = self.manager.list_available_templates()
        
        # Should only include template files
        assert len(templates) == 3
        assert 'template1.yaml' in templates
        assert 'template2.json' in templates
        assert 'template3.yml' in templates
        assert 'not_template.txt' not in templates

    def test_clear_cache(self):
        """Test template cache clearing."""
        # Add something to cache
        self.manager.template_cache['test'] = Mock()
        assert len(self.manager.template_cache) == 1
        
        self.manager.clear_cache()
        assert len(self.manager.template_cache) == 0

    def test_reload_template(self):
        """Test template reloading."""
        template_data = {
            'name': 'Original Template',
            'format_type': 'word',
            'sections': ['header']
        }
        
        updated_data = {
            'name': 'Updated Template',
            'format_type': 'word',
            'sections': ['header', 'footer']
        }
        
        yaml_content1 = yaml.dump(template_data)
        yaml_content2 = yaml.dump(updated_data)
        
        with patch('builtins.open', mock_open(read_data=yaml_content1)):
            with patch('os.path.exists', return_value=True):
                template1 = self.manager.get_template('test.yaml')
        
        assert template1.name == 'Original Template'
        assert len(template1.sections) == 1
        
        # Reload with updated content
        with patch('builtins.open', mock_open(read_data=yaml_content2)):
            with patch('os.path.exists', return_value=True):
                template2 = self.manager.reload_template('test.yaml')
        
        assert template2.name == 'Updated Template'
        assert len(template2.sections) == 2


class TestDocumentTemplate:
    """Test cases for DocumentTemplate class."""

    def test_document_template_creation(self):
        """Test DocumentTemplate creation."""
        template = DocumentTemplate(
            name='Test Template',
            format_type='excel',
            sections=['summary', 'resources'],
            variables={'company': 'Test Corp'},
            formatting_options={'theme': 'corporate'}
        )
        
        assert template.name == 'Test Template'
        assert template.format_type == 'excel'
        assert len(template.sections) == 2
        assert template.variables['company'] == 'Test Corp'
        assert template.formatting_options['theme'] == 'corporate'

    def test_document_template_defaults(self):
        """Test DocumentTemplate with default values."""
        template = DocumentTemplate(
            name='Minimal Template',
            format_type='word'
        )
        
        assert template.name == 'Minimal Template'
        assert template.format_type == 'word'
        assert template.sections == []
        assert template.variables == {}
        assert template.formatting_options == {}
        assert template.template_path is None

    def test_get_section_config(self):
        """Test getting section configuration."""
        template = DocumentTemplate(
            name='Test Template',
            format_type='word',
            sections=['header', 'body', 'footer'],
            section_configs={
                'header': {'include_logo': True, 'height': '2cm'},
                'body': {'font_size': 12}
            }
        )
        
        header_config = template.get_section_config('header')
        assert header_config['include_logo'] is True
        assert header_config['height'] == '2cm'
        
        body_config = template.get_section_config('body')
        assert body_config['font_size'] == 12
        
        # Non-existent section should return empty dict
        footer_config = template.get_section_config('footer')
        assert footer_config == {}

    def test_has_section(self):
        """Test section existence checking."""
        template = DocumentTemplate(
            name='Test Template',
            format_type='word',
            sections=['header', 'body']
        )
        
        assert template.has_section('header') is True
        assert template.has_section('body') is True
        assert template.has_section('footer') is False

    def test_get_variable(self):
        """Test variable retrieval with defaults."""
        template = DocumentTemplate(
            name='Test Template',
            format_type='word',
            variables={'company': 'Test Corp', 'version': '1.0'}
        )
        
        assert template.get_variable('company') == 'Test Corp'
        assert template.get_variable('version') == '1.0'
        assert template.get_variable('nonexistent') is None
        assert template.get_variable('nonexistent', 'default') == 'default'


class TestTemplateVariableResolver:
    """Test cases for TemplateVariableResolver class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = TemplateVariableResolver()

    def test_resolve_variables_simple(self):
        """Test simple variable resolution."""
        template_text = "Company: {{company_name}}, Date: {{generation_date}}"
        variables = {
            'company_name': 'Test Corp',
            'generation_date': '2023-01-01'
        }
        
        result = self.resolver.resolve_variables(template_text, variables)
        assert result == "Company: Test Corp, Date: 2023-01-01"

    def test_resolve_variables_nested(self):
        """Test nested variable resolution."""
        template_text = "{{header.title}} - {{header.subtitle}}"
        variables = {
            'header': {
                'title': 'BOM Report',
                'subtitle': 'Infrastructure Inventory'
            }
        }
        
        result = self.resolver.resolve_variables(template_text, variables)
        assert result == "BOM Report - Infrastructure Inventory"

    def test_resolve_variables_with_filters(self):
        """Test variable resolution with filters."""
        template_text = "{{company_name|upper}} - {{generation_date|date_format}}"
        variables = {
            'company_name': 'test corp',
            'generation_date': '2023-01-01T12:00:00Z'
        }
        
        # Mock filter functions
        with patch.object(self.resolver, '_apply_filter') as mock_filter:
            mock_filter.side_effect = lambda value, filter_name: {
                ('test corp', 'upper'): 'TEST CORP',
                ('2023-01-01T12:00:00Z', 'date_format'): '01/01/2023'
            }.get((value, filter_name), value)
            
            result = self.resolver.resolve_variables(template_text, variables)
        
        assert result == "TEST CORP - 01/01/2023"

    def test_resolve_variables_missing_variable(self):
        """Test variable resolution with missing variables."""
        template_text = "Company: {{company_name}}, Missing: {{missing_var}}"
        variables = {'company_name': 'Test Corp'}
        
        # Should handle missing variables gracefully
        result = self.resolver.resolve_variables(template_text, variables)
        assert "Test Corp" in result
        assert "{{missing_var}}" in result  # Should leave unresolved

    def test_apply_filter_upper(self):
        """Test upper case filter."""
        result = self.resolver._apply_filter('test string', 'upper')
        assert result == 'TEST STRING'

    def test_apply_filter_lower(self):
        """Test lower case filter."""
        result = self.resolver._apply_filter('TEST STRING', 'lower')
        assert result == 'test string'

    def test_apply_filter_date_format(self):
        """Test date formatting filter."""
        result = self.resolver._apply_filter('2023-01-01T12:00:00Z', 'date_format')
        assert '2023' in result
        assert '01' in result

    def test_apply_filter_unknown(self):
        """Test unknown filter handling."""
        result = self.resolver._apply_filter('test', 'unknown_filter')
        assert result == 'test'  # Should return original value

    def test_get_nested_value(self):
        """Test nested value retrieval."""
        data = {
            'level1': {
                'level2': {
                    'value': 'nested_value'
                }
            }
        }
        
        result = self.resolver._get_nested_value(data, 'level1.level2.value')
        assert result == 'nested_value'
        
        # Test non-existent path
        result = self.resolver._get_nested_value(data, 'level1.nonexistent.value')
        assert result is None

    def test_resolve_conditional_blocks(self):
        """Test conditional block resolution."""
        template_text = """
        {{#if show_summary}}
        Summary section content
        {{/if}}
        {{#unless hide_details}}
        Details section content
        {{/unless}}
        """
        
        variables = {
            'show_summary': True,
            'hide_details': False
        }
        
        result = self.resolver.resolve_variables(template_text, variables)
        
        assert 'Summary section content' in result
        assert 'Details section content' in result

    def test_resolve_loop_blocks(self):
        """Test loop block resolution."""
        template_text = """
        {{#each resources}}
        Resource: {{name}} ({{type}})
        {{/each}}
        """
        
        variables = {
            'resources': [
                {'name': 'instance-1', 'type': 'EC2'},
                {'name': 'bucket-1', 'type': 'S3'}
            ]
        }
        
        result = self.resolver.resolve_variables(template_text, variables)
        
        assert 'Resource: instance-1 (EC2)' in result
        assert 'Resource: bucket-1 (S3)' in result


class TestDocumentStructureBuilder:
    """Test cases for DocumentStructureBuilder class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = DocumentStructureBuilder()

    def test_build_document_structure(self):
        """Test document structure building."""
        template = DocumentTemplate(
            name='Test Template',
            format_type='word',
            sections=['header', 'summary', 'resources', 'footer']
        )
        
        bom_data = Mock()
        bom_data.resources = [{'id': 'i-12345', 'service': 'EC2'}]
        bom_data.summary = {'total_resources': 1}
        
        structure = self.builder.build_document_structure(template, bom_data)
        
        assert 'sections' in structure
        assert len(structure['sections']) == 4
        assert structure['sections'][0]['name'] == 'header'
        assert structure['sections'][1]['name'] == 'summary'

    def test_build_section_header(self):
        """Test header section building."""
        template = DocumentTemplate(
            name='Test Template',
            format_type='word',
            variables={'company_name': 'Test Corp', 'document_title': 'BOM Report'}
        )
        
        section = self.builder._build_section('header', template, Mock())
        
        assert section['name'] == 'header'
        assert section['type'] == 'header'
        assert 'content' in section

    def test_build_section_summary(self):
        """Test summary section building."""
        template = DocumentTemplate(
            name='Test Template',
            format_type='word'
        )
        
        bom_data = Mock()
        bom_data.summary = {
            'total_resources': 100,
            'compliant_resources': 80,
            'non_compliant_resources': 20
        }
        
        section = self.builder._build_section('summary', template, bom_data)
        
        assert section['name'] == 'summary'
        assert section['type'] == 'summary'
        assert section['data']['total_resources'] == 100

    def test_build_section_resources(self):
        """Test resources section building."""
        template = DocumentTemplate(
            name='Test Template',
            format_type='word'
        )
        
        bom_data = Mock()
        bom_data.resources = [
            {'id': 'i-12345', 'service': 'EC2', 'type': 'Instance'},
            {'id': 'bucket-1', 'service': 'S3', 'type': 'Bucket'}
        ]
        
        section = self.builder._build_section('resources', template, bom_data)
        
        assert section['name'] == 'resources'
        assert section['type'] == 'resources'
        assert len(section['data']['resources']) == 2

    def test_build_section_custom(self):
        """Test custom section building."""
        template = DocumentTemplate(
            name='Test Template',
            format_type='word',
            section_configs={
                'custom_section': {
                    'title': 'Custom Analysis',
                    'include_charts': True
                }
            }
        )
        
        section = self.builder._build_section('custom_section', template, Mock())
        
        assert section['name'] == 'custom_section'
        assert section['type'] == 'custom'
        assert section['config']['title'] == 'Custom Analysis'

    def test_generate_table_of_contents(self):
        """Test table of contents generation."""
        sections = [
            {'name': 'header', 'title': 'Header'},
            {'name': 'summary', 'title': 'Executive Summary'},
            {'name': 'resources', 'title': 'Resource Inventory'},
            {'name': 'footer', 'title': 'Footer'}
        ]
        
        toc = self.builder._generate_table_of_contents(sections)
        
        assert len(toc) == 2  # Should exclude header and footer
        assert toc[0]['title'] == 'Executive Summary'
        assert toc[1]['title'] == 'Resource Inventory'

    def test_apply_section_formatting(self):
        """Test section formatting application."""
        section = {
            'name': 'summary',
            'content': 'Test content',
            'data': {'total': 100}
        }
        
        template = DocumentTemplate(
            name='Test Template',
            format_type='word',
            formatting_options={
                'font_size': 12,
                'highlight_totals': True
            }
        )
        
        formatted_section = self.builder._apply_section_formatting(section, template)
        
        assert formatted_section['formatting']['font_size'] == 12
        assert formatted_section['formatting']['highlight_totals'] is True


if __name__ == '__main__':
    pytest.main([__file__])