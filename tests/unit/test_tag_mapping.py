#!/usr/bin/env python3
"""
Unit tests for TagMappingEngine

Tests tag mapping functionality, validation, and normalization.
"""

import pytest
import json
import yaml
import tempfile
import os
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from inventag.discovery.tag_mapping import (
    TagMappingEngine,
    TagMapping,
    TagMappingResult,
    TagNormalizer
)


class TestTagNormalizer:
    """Test cases for TagNormalizer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.normalizer = TagNormalizer()
        
    def test_normalize_lowercase(self):
        """Test lowercase normalization."""
        result = self.normalizer.normalize_value('TEST VALUE', 'lowercase')
        assert result == 'test value'
        
    def test_normalize_uppercase(self):
        """Test uppercase normalization."""
        result = self.normalizer.normalize_value('test value', 'uppercase')
        assert result == 'TEST VALUE'
        
    def test_normalize_title(self):
        """Test title case normalization."""
        result = self.normalizer.normalize_value('test value', 'title')
        assert result == 'Test Value'
        
    def test_normalize_strip(self):
        """Test strip normalization."""
        result = self.normalizer.normalize_value('  test value  ', 'strip')
        assert result == 'test value'
        
    def test_normalize_strip_whitespace(self):
        """Test whitespace stripping normalization."""
        result = self.normalizer.normalize_value('  test   value  ', 'strip_whitespace')
        assert result == 'test value'
        
    def test_normalize_remove_special_chars(self):
        """Test special character removal."""
        result = self.normalizer.normalize_value('test@#$value!', 'remove_special_chars')
        assert result == 'testvalue'
        
    def test_normalize_alphanumeric_only(self):
        """Test alphanumeric only normalization."""
        result = self.normalizer.normalize_value('test-value_123!', 'alphanumeric_only')
        assert result == 'testvalue123'
        
    def test_normalize_slug(self):
        """Test slug normalization."""
        result = self.normalizer.normalize_value('Test Value 123!', 'slug')
        assert result == 'test-value-123'
        
    def test_normalize_unknown_function(self):
        """Test unknown normalization function."""
        result = self.normalizer.normalize_value('test value', 'unknown_function')
        assert result == 'test value'  # Should return original
        
    def test_normalize_no_function(self):
        """Test normalization without function."""
        result = self.normalizer.normalize_value('test value', None)
        assert result == 'test value'
        
    def test_validate_value_success(self):
        """Test successful value validation."""
        result = self.normalizer.validate_value('TEST-123', r'^[A-Z0-9-]+$')
        assert result is True
        
    def test_validate_value_failure(self):
        """Test failed value validation."""
        result = self.normalizer.validate_value('test-123', r'^[A-Z0-9-]+$')
        assert result is False
        
    def test_validate_value_no_pattern(self):
        """Test validation without pattern."""
        result = self.normalizer.validate_value('any value', None)
        assert result is True
        
    def test_validate_value_invalid_pattern(self):
        """Test validation with invalid regex pattern."""
        result = self.normalizer.validate_value('test', '[invalid regex')
        assert result is True  # Should default to valid


class TestTagMappingEngine:
    """Test cases for TagMappingEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = TagMappingEngine()
        
    def test_initialization_with_defaults(self):
        """Test engine initialization with default mappings."""
        engine = TagMappingEngine()
        
        # Should have default mappings
        assert len(engine.mappings) > 0
        assert 'inventag:remarks' in engine.mappings
        assert 'inventag:costcenter' in engine.mappings
        
    def test_load_mappings_from_yaml_file(self):
        """Test loading mappings from YAML file."""
        config_data = {
            'tag_mappings': [
                {
                    'tag': 'custom:project',
                    'name': 'Project Name',
                    'description': 'Project identifier',
                    'default_value': 'Unknown',
                    'normalize_function': 'title',
                    'validation_pattern': r'^[A-Za-z0-9\s-]+$',
                    'required': True,
                    'case_sensitive': False
                },
                {
                    'tag': 'custom:owner',
                    'name': 'Resource Owner',
                    'default_value': 'Unassigned'
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
            
        try:
            success = self.engine.load_mappings_from_file(temp_path)
            assert success
            
            # Test custom mappings are loaded
            assert 'custom:project' in self.engine.mappings
            assert 'custom:owner' in self.engine.mappings
            
            # Test mapping properties
            project_mapping = self.engine.mappings['custom:project']
            assert project_mapping.name == 'Project Name'
            assert project_mapping.required is True
            assert project_mapping.normalize_function == 'title'
            assert project_mapping.validation_pattern == r'^[A-Za-z0-9\s-]+$'
            
        finally:
            os.unlink(temp_path)
            
    def test_load_mappings_from_json_file(self):
        """Test loading mappings from JSON file."""
        config_data = {
            'tag_mappings': [
                {
                    'tag': 'json:test',
                    'name': 'JSON Test',
                    'default_value': 'test'
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
            
        try:
            success = self.engine.load_mappings_from_file(temp_path)
            assert success
            
            assert 'json:test' in self.engine.mappings
            
        finally:
            os.unlink(temp_path)
            
    def test_load_mappings_invalid_schema(self):
        """Test loading mappings with invalid schema."""
        invalid_configs = [
            # Missing tag_mappings key
            {'invalid': 'config'},
            
            # tag_mappings not a list
            {'tag_mappings': 'invalid'},
            
            # Mapping not a dict
            {'tag_mappings': ['invalid']},
            
            # Missing required fields
            {'tag_mappings': [{'name': 'Test'}]},  # Missing tag
            {'tag_mappings': [{'tag': 'test:tag'}]},  # Missing name
            
            # Invalid field types
            {'tag_mappings': [{'tag': 123, 'name': 'Test'}]},  # tag not string
            {'tag_mappings': [{'tag': 'test:tag', 'name': 123}]}  # name not string
        ]
        
        for config_data in invalid_configs:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(config_data, f)
                temp_path = f.name
                
            try:
                success = self.engine.load_mappings_from_file(temp_path)
                assert not success
            finally:
                os.unlink(temp_path)
                
    def test_load_mappings_file_not_found(self):
        """Test loading mappings from non-existent file."""
        success = self.engine.load_mappings_from_file('/nonexistent/path.yaml')
        assert not success
        
    def test_extract_custom_attributes_basic(self):
        """Test basic custom attribute extraction."""
        resource = {
            'id': 'test-resource',
            'tags': {
                'inventag:remarks': 'Test remarks',
                'inventag:costcenter': 'CC-123',
                'inventag:owner': 'Test Team'
            }
        }
        
        result = self.engine.extract_custom_attributes(resource)
        
        assert isinstance(result, TagMappingResult)
        assert 'Remarks' in result.mapped_attributes
        assert 'Cost Center' in result.mapped_attributes
        assert 'Owner' in result.mapped_attributes
        
        assert result.mapped_attributes['Remarks'] == 'Test remarks'
        assert result.mapped_attributes['Cost Center'] == 'CC-123'
        assert result.mapped_attributes['Owner'] == 'Test Team'
        
    def test_extract_custom_attributes_with_defaults(self):
        """Test custom attribute extraction with default values."""
        resource = {
            'id': 'test-resource',
            'tags': {
                'inventag:remarks': 'Test remarks'
                # Missing other tags
            }
        }
        
        result = self.engine.extract_custom_attributes(resource)
        
        # Should use default values for missing tags (normalized)
        assert result.mapped_attributes['Cost Center'] == 'UNKNOWN'  # Normalized to uppercase
        assert result.mapped_attributes['Owner'] == 'Unknown'
        
    def test_extract_custom_attributes_case_insensitive(self):
        """Test case insensitive tag matching."""
        # Create mapping with case insensitive setting
        mapping = TagMapping(
            tag='test:case',
            name='Case Test',
            case_sensitive=False
        )
        self.engine.add_mapping(mapping)
        
        resource = {
            'id': 'test-resource',
            'tags': {
                'TEST:CASE': 'value'  # Different case
            }
        }
        
        result = self.engine.extract_custom_attributes(resource)
        assert result.mapped_attributes['Case Test'] == 'value'
        
    def test_extract_custom_attributes_case_sensitive(self):
        """Test case sensitive tag matching."""
        # Create mapping with case sensitive setting
        mapping = TagMapping(
            tag='test:case',
            name='Case Test',
            case_sensitive=True
        )
        self.engine.add_mapping(mapping)
        
        resource = {
            'id': 'test-resource',
            'tags': {
                'TEST:CASE': 'value'  # Different case
            }
        }
        
        result = self.engine.extract_custom_attributes(resource)
        assert result.mapped_attributes['Case Test'] == ''  # Should use default
        
    def test_extract_custom_attributes_with_normalization(self):
        """Test custom attribute extraction with normalization."""
        # Create mapping with normalization
        mapping = TagMapping(
            tag='test:normalize',
            name='Normalize Test',
            normalize_function='uppercase'
        )
        self.engine.add_mapping(mapping)
        
        resource = {
            'id': 'test-resource',
            'tags': {
                'test:normalize': 'test value'
            }
        }
        
        result = self.engine.extract_custom_attributes(resource)
        assert result.mapped_attributes['Normalize Test'] == 'TEST VALUE'
        assert 'test:normalize' in result.normalized_values
        
    def test_extract_custom_attributes_with_validation(self):
        """Test custom attribute extraction with validation."""
        # Create a clean engine with only test mapping to avoid interference
        test_engine = TagMappingEngine()
        test_engine.mappings.clear()  # Clear default mappings
        
        # Create mapping with validation
        mapping = TagMapping(
            tag='test:validate',
            name='Validate Test',
            validation_pattern=r'^[A-Z0-9-]+$'
        )
        test_engine.add_mapping(mapping)
        
        # Test valid value
        resource = {
            'id': 'test-resource',
            'tags': {
                'test:validate': 'VALID-123'
            }
        }
        
        result = test_engine.extract_custom_attributes(resource)
        assert len(result.validation_errors) == 0
        
        # Test invalid value
        resource['tags']['test:validate'] = 'invalid-value'
        result = test_engine.extract_custom_attributes(resource)
        assert len(result.validation_errors) > 0
        
    def test_extract_custom_attributes_required_tags(self):
        """Test extraction with required tags."""
        # Create required mapping
        mapping = TagMapping(
            tag='test:required',
            name='Required Test',
            required=True
        )
        self.engine.add_mapping(mapping)
        
        # Test missing required tag
        resource = {
            'id': 'test-resource',
            'tags': {}
        }
        
        result = self.engine.extract_custom_attributes(resource)
        assert 'test:required' in result.missing_required_tags
        
    def test_extract_custom_attributes_no_tags(self):
        """Test extraction from resource without tags."""
        resource = {
            'id': 'test-resource'
            # No tags field
        }
        
        result = self.engine.extract_custom_attributes(resource)
        
        # Should use default values
        assert len(result.mapped_attributes) > 0
        for value in result.mapped_attributes.values():
            assert value is not None
            
    def test_apply_mappings_to_resources(self):
        """Test applying mappings to resource list."""
        resources = [
            {
                'id': 'resource-1',
                'tags': {
                    'inventag:remarks': 'First resource',
                    'inventag:costcenter': 'CC-001'
                }
            },
            {
                'id': 'resource-2',
                'tags': {
                    'inventag:remarks': 'Second resource',
                    'inventag:owner': 'Team B'
                }
            }
        ]
        
        enriched = self.engine.apply_mappings_to_resources(resources)
        
        assert len(enriched) == 2
        
        # Check first resource
        assert 'custom_attributes' in enriched[0]
        assert 'tag_mapping_metadata' in enriched[0]
        assert enriched[0]['custom_attributes']['Remarks'] == 'First resource'
        assert enriched[0]['custom_attributes']['Cost Center'] == 'CC-001'
        
        # Check second resource
        assert 'custom_attributes' in enriched[1]
        assert enriched[1]['custom_attributes']['Remarks'] == 'Second resource'
        assert enriched[1]['custom_attributes']['Owner'] == 'Team B'
        
        # Check metadata
        metadata = enriched[0]['tag_mapping_metadata']
        assert 'mapped_at' in metadata
        assert 'mapping_source' in metadata
        assert metadata['mapping_source'] == 'TagMappingEngine'
        
    def test_apply_mappings_error_handling(self):
        """Test error handling in mapping application."""
        # Resource with invalid tags field
        resources = [
            {'id': 'test', 'tags': 'invalid'},  # tags should be dict
            {
                'id': 'valid-resource',
                'tags': {'inventag:remarks': 'valid'}
            }
        ]
        
        enriched = self.engine.apply_mappings_to_resources(resources)
        
        # Should still return all resources
        assert len(enriched) == 2
        
        # Valid resource should have custom attributes
        assert 'custom_attributes' in enriched[1]
        
    def test_get_custom_columns(self):
        """Test getting custom column information."""
        columns = self.engine.get_custom_columns()
        
        assert len(columns) > 0
        
        # Check column structure
        for column in columns:
            assert 'name' in column
            assert 'tag' in column
            assert 'description' in column
            assert 'default_value' in column
            assert 'required' in column
            
    def test_get_custom_column_names(self):
        """Test getting custom column names."""
        names = self.engine.get_custom_column_names()
        
        assert len(names) > 0
        assert 'Remarks' in names
        assert 'Cost Center' in names
        
    def test_validate_resource_tags(self):
        """Test resource tag validation."""
        resource = {
            'id': 'test-resource',
            'tags': {
                'inventag:remarks': 'Test remarks',
                'inventag:costcenter': 'CC-123'
            }
        }
        
        validation_result = self.engine.validate_resource_tags(resource)
        
        assert 'resource_id' in validation_result
        assert 'is_valid' in validation_result
        assert 'validation_errors' in validation_result
        assert 'missing_required_tags' in validation_result
        assert 'mapped_attributes' in validation_result
        
        assert validation_result['resource_id'] == 'test-resource'
        
    def test_add_mapping(self):
        """Test adding new mapping."""
        mapping = TagMapping(
            tag='test:new',
            name='New Test',
            description='Test mapping'
        )
        
        initial_count = len(self.engine.mappings)
        self.engine.add_mapping(mapping)
        
        assert len(self.engine.mappings) == initial_count + 1
        assert 'test:new' in self.engine.mappings
        assert self.engine.mappings['test:new'] == mapping
        
    def test_remove_mapping(self):
        """Test removing mapping."""
        # Add a test mapping first
        mapping = TagMapping(tag='test:remove', name='Remove Test')
        self.engine.add_mapping(mapping)
        
        # Remove it
        success = self.engine.remove_mapping('test:remove')
        assert success
        assert 'test:remove' not in self.engine.mappings
        
        # Try to remove non-existent mapping
        success = self.engine.remove_mapping('nonexistent')
        assert not success
        
    def test_get_mapping(self):
        """Test getting specific mapping."""
        mapping = self.engine.get_mapping('inventag:remarks')
        assert mapping is not None
        assert mapping.name == 'Remarks'
        
        # Test non-existent mapping
        mapping = self.engine.get_mapping('nonexistent')
        assert mapping is None
        
    def test_list_mappings(self):
        """Test listing all mappings."""
        mappings = self.engine.list_mappings()
        assert len(mappings) > 0
        assert all(isinstance(m, TagMapping) for m in mappings)
        
    def test_reload_mappings(self):
        """Test reloading mappings from file."""
        # Create initial config
        config_data = {
            'tag_mappings': [
                {
                    'tag': 'test:initial',
                    'name': 'Initial Test'
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
            
        try:
            # Load initial config
            self.engine.load_mappings_from_file(temp_path)
            assert 'test:initial' in self.engine.mappings
            
            # Update config file
            updated_config = {
                'tag_mappings': [
                    {
                        'tag': 'test:updated',
                        'name': 'Updated Test'
                    }
                ]
            }
            
            with open(temp_path, 'w') as f:
                yaml.dump(updated_config, f)
                
            # Reload
            success = self.engine.reload_mappings()
            assert success
            
            # Check updated mappings
            assert 'test:updated' in self.engine.mappings
            assert 'test:initial' not in self.engine.mappings
            
        finally:
            os.unlink(temp_path)
            
    def test_reload_mappings_no_path(self):
        """Test reloading mappings without config path."""
        engine = TagMappingEngine()  # No config path
        success = engine.reload_mappings()
        assert not success
        
    def test_get_configuration_info(self):
        """Test getting configuration information."""
        info = self.engine.get_configuration_info()
        
        assert 'config_path' in info
        assert 'last_reload' in info
        assert 'total_mappings' in info
        assert 'required_mappings' in info
        assert 'mappings_with_validation' in info
        assert 'mappings_with_normalization' in info
        assert 'tag_list' in info
        
        # Should have default mappings
        assert info['total_mappings'] > 0
        assert len(info['tag_list']) > 0
        
    def test_export_configuration_template_yaml(self):
        """Test exporting configuration template as YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
            
        try:
            success = self.engine.export_configuration_template(temp_path, 'yaml')
            assert success
            
            # Verify file was created and is valid YAML
            with open(temp_path, 'r') as f:
                config = yaml.safe_load(f)
                
            assert 'tag_mappings' in config
            assert len(config['tag_mappings']) > 0
            
            # Check structure
            for mapping in config['tag_mappings']:
                assert 'tag' in mapping
                assert 'name' in mapping
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    def test_export_configuration_template_json(self):
        """Test exporting configuration template as JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
            
        try:
            success = self.engine.export_configuration_template(temp_path, 'json')
            assert success
            
            # Verify file was created and is valid JSON
            with open(temp_path, 'r') as f:
                config = json.load(f)
                
            assert 'tag_mappings' in config
            assert len(config['tag_mappings']) > 0
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    def test_generate_validation_report(self):
        """Test generating validation report."""
        # Create resources with various validation states
        resources = [
            {
                'id': 'valid-resource',
                'tags': {
                    'inventag:remarks': 'Valid remarks',
                    'inventag:costcenter': 'CC-123'
                }
            },
            {
                'id': 'missing-tags-resource',
                'tags': {}  # Missing tags
            },
            {
                'id': 'invalid-resource',
                'tags': {
                    'inventag:environment': 'invalid-env'  # Should fail validation
                }
            }
        ]
        
        report = self.engine.generate_validation_report(resources)
        
        assert 'total_resources' in report
        assert 'valid_resources' in report
        assert 'invalid_resources' in report
        assert 'compliance_percentage' in report
        assert 'validation_summary' in report
        assert 'missing_tags_summary' in report
        assert 'detailed_errors' in report
        
        assert report['total_resources'] == 3
        assert report['compliance_percentage'] >= 0
        assert report['compliance_percentage'] <= 100


class TestTagMappingIntegration:
    """Integration tests for tag mapping functionality."""
    
    def test_end_to_end_workflow(self):
        """Test complete workflow from config to resource enrichment."""
        # Create comprehensive config
        config_data = {
            'tag_mappings': [
                {
                    'tag': 'project:name',
                    'name': 'Project Name',
                    'description': 'Project identifier',
                    'default_value': 'Unknown',
                    'normalize_function': 'title',
                    'validation_pattern': r'^[A-Za-z0-9\s-]+$',
                    'required': True,
                    'case_sensitive': False
                },
                {
                    'tag': 'cost:center',
                    'name': 'Cost Center',
                    'description': 'Cost center code',
                    'default_value': 'UNASSIGNED',
                    'normalize_function': 'uppercase',
                    'validation_pattern': r'^[A-Z]{2,4}-[0-9]{3,4}$',
                    'required': True,
                    'case_sensitive': True
                },
                {
                    'tag': 'env:type',
                    'name': 'Environment',
                    'description': 'Environment type',
                    'default_value': 'dev',
                    'normalize_function': 'lowercase',
                    'validation_pattern': r'^(dev|test|staging|prod)$',
                    'required': False,
                    'case_sensitive': False
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
            
        try:
            # Initialize engine with config
            engine = TagMappingEngine(temp_path)
            
            # Test resources
            resources = [
                {
                    'id': 'resource-1',
                    'tags': {
                        'project:name': 'web application',
                        'cost:center': 'IT-1234',
                        'env:type': 'PROD'
                    }
                },
                {
                    'id': 'resource-2',
                    'tags': {
                        'PROJECT:NAME': 'mobile app',  # Different case
                        'cost:center': 'invalid-format'  # Invalid format
                    }
                },
                {
                    'id': 'resource-3',
                    'tags': {}  # Missing required tags
                }
            ]
            
            # Apply mappings
            enriched = engine.apply_mappings_to_resources(resources)
            
            # Verify results
            assert len(enriched) == 3
            
            # Resource 1 - should be valid with normalization
            r1 = enriched[0]
            assert r1['custom_attributes']['Project Name'] == 'Web Application'  # Title case
            assert r1['custom_attributes']['Cost Center'] == 'IT-1234'  # Uppercase
            assert r1['custom_attributes']['Environment'] == 'prod'  # Lowercase
            assert len(r1['tag_mapping_metadata']['validation_errors']) == 0
            assert len(r1['tag_mapping_metadata']['missing_required_tags']) == 0
            
            # Resource 2 - should have validation errors
            r2 = enriched[1]
            assert r2['custom_attributes']['Project Name'] == 'Mobile App'  # Case insensitive match
            assert len(r2['tag_mapping_metadata']['validation_errors']) > 0  # Invalid cost center
            
            # Resource 3 - should have missing required tags
            r3 = enriched[2]
            assert len(r3['tag_mapping_metadata']['missing_required_tags']) > 0
            assert r3['custom_attributes']['Project Name'] == 'Unknown'  # Default value
            
            # Test validation report
            report = engine.generate_validation_report(resources)
            assert report['total_resources'] == 3
            assert report['invalid_resources'] > 0
            assert report['compliance_percentage'] < 100
            
            # Test column information
            columns = engine.get_custom_columns()
            assert len(columns) == 3
            column_names = [col['name'] for col in columns]
            assert 'Project Name' in column_names
            assert 'Cost Center' in column_names
            assert 'Environment' in column_names
            
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    pytest.main([__file__])