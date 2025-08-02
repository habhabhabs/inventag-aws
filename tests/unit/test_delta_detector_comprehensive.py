#!/usr/bin/env python3
"""
Comprehensive unit tests for DeltaDetector

Tests delta detection algorithms, change categorization, impact analysis,
and comprehensive change tracking between AWS resource inventory states.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from inventag.state.delta_detector import (
    DeltaDetector,
    ChangeType,
    ChangeSeverity,
    ChangeCategory,
    AttributeChange,
    ResourceChange,
    DeltaReport
)


class TestDeltaDetector:
    """Test cases for DeltaDetector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = DeltaDetector()

    def test_init(self):
        """Test DeltaDetector initialization."""
        assert self.detector.ignore_metadata_fields == ['last_seen', 'discovery_timestamp', 'scan_time', 'metadata']
        assert ChangeSeverity.CRITICAL in self.detector.severity_rules.values()
        assert 'EC2' in self.detector.dependency_patterns
        assert 'depends_on' in self.detector.dependency_patterns['EC2']
        assert 'affects' in self.detector.dependency_patterns['EC2']

    def test_create_resource_map(self):
        """Test resource map creation."""
        resources = [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
                'id': 'i-12345',
                'service': 'EC2',
                'type': 'Instance'
            },
            {
                'arn': 'arn:aws:s3:::test-bucket',
                'id': 'test-bucket',
                'service': 'S3',
                'type': 'Bucket'
            }
        ]
        
        resource_map = self.detector._create_resource_map(resources)
        
        assert len(resource_map) == 2
        assert 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345' in resource_map
        assert 'arn:aws:s3:::test-bucket' in resource_map
        
        # Check resource data is preserved
        ec2_resource = resource_map['arn:aws:ec2:us-east-1:123456789012:instance/i-12345']
        assert ec2_resource['id'] == 'i-12345'
        assert ec2_resource['service'] == 'EC2'

    def test_create_resource_map_without_arn(self):
        """Test resource map creation for resources without ARN."""
        resources = [
            {
                'id': 'resource-without-arn',
                'service': 'CustomService',
                'type': 'CustomType',
                'region': 'us-east-1'
            }
        ]
        
        resource_map = self.detector._create_resource_map(resources)
        
        assert len(resource_map) == 1
        assert 'resource-without-arn' in resource_map

    def test_detect_added_resources(self):
        """Test detection of added resources."""
        old_resources = [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
                'id': 'i-12345',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1'
            }
        ]
        
        new_resources = old_resources + [
            {
                'arn': 'arn:aws:s3:::new-bucket',
                'id': 'new-bucket',
                'service': 'S3',
                'type': 'Bucket',
                'region': 'us-east-1'
            }
        ]
        
        old_map = self.detector._create_resource_map(old_resources)
        new_map = self.detector._create_resource_map(new_resources)
        
        added = self.detector._detect_added_resources(old_map, new_map)
        
        assert len(added) == 1
        assert added[0].resource_arn == 'arn:aws:s3:::new-bucket'
        assert added[0].change_type == ChangeType.ADDED
        assert added[0].service == 'S3'
        assert added[0].resource_type == 'Bucket'

    def test_detect_removed_resources(self):
        """Test detection of removed resources."""
        old_resources = [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
                'id': 'i-12345',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1'
            },
            {
                'arn': 'arn:aws:s3:::old-bucket',
                'id': 'old-bucket',
                'service': 'S3',
                'type': 'Bucket',
                'region': 'us-east-1'
            }
        ]
        
        new_resources = [old_resources[0]]  # Remove the S3 bucket
        
        old_map = self.detector._create_resource_map(old_resources)
        new_map = self.detector._create_resource_map(new_resources)
        
        removed = self.detector._detect_removed_resources(old_map, new_map)
        
        assert len(removed) == 1
        assert removed[0].resource_arn == 'arn:aws:s3:::old-bucket'
        assert removed[0].change_type == ChangeType.REMOVED
        assert removed[0].service == 'S3'

    def test_detect_modified_resources(self):
        """Test detection of modified resources."""
        old_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
            'id': 'i-12345',
            'service': 'EC2',
            'type': 'Instance',
            'region': 'us-east-1',
            'instance_type': 't3.micro',
            'tags': {'Name': 'test-instance', 'Environment': 'dev'}
        }
        
        new_resource = old_resource.copy()
        new_resource['instance_type'] = 't3.small'  # Changed instance type
        new_resource['tags'] = {'Name': 'test-instance', 'Environment': 'prod'}  # Changed tag
        
        old_map = self.detector._create_resource_map([old_resource])
        new_map = self.detector._create_resource_map([new_resource])
        
        modified, unchanged = self.detector._detect_modified_resources(old_map, new_map)
        
        assert len(modified) == 1
        change = modified[0]
        assert change.resource_arn == 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345'
        assert change.change_type == ChangeType.MODIFIED
        
        # Should have detected attribute changes
        assert len(change.attribute_changes) > 0

    def test_compare_resources(self):
        """Test resource comparison."""
        old_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
            'instance_type': 't3.micro',
            'tags': {'Name': 'test', 'Environment': 'dev'}
        }
        
        new_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
            'instance_type': 't3.small',  # Changed
            'tags': {'Name': 'test', 'Environment': 'prod'}  # Changed
        }
        
        changes = self.detector._compare_resources(old_resource, new_resource)
        
        # Should detect changes
        assert len(changes) >= 1
        
        # Check for instance type change
        instance_type_changes = [c for c in changes if c.attribute_path == 'instance_type']
        if instance_type_changes:
            assert instance_type_changes[0].old_value == 't3.micro'
            assert instance_type_changes[0].new_value == 't3.small'

    def test_categorize_attribute_change(self):
        """Test attribute change categorization."""
        # Test security-related change
        category = self.detector._categorize_attribute_change('security_groups', ['sg-old'], ['sg-new'])
        assert category == ChangeCategory.SECURITY

        # Test compliance-related change
        category = self.detector._categorize_attribute_change('compliance_status', 'compliant', 'non-compliant')
        assert category == ChangeCategory.COMPLIANCE

        # Test network-related change
        category = self.detector._categorize_attribute_change('vpc_id', 'vpc-old', 'vpc-new')
        assert category == ChangeCategory.NETWORK

        # Test configuration change
        category = self.detector._categorize_attribute_change('instance_type', 't3.micro', 't3.small')
        assert category == ChangeCategory.CONFIGURATION

    def test_determine_attribute_severity(self):
        """Test attribute severity determination."""
        # Critical severity
        severity = self.detector._determine_attribute_severity('security_groups', [], [])
        assert severity == ChangeSeverity.CRITICAL

        # High severity
        severity = self.detector._determine_attribute_severity('compliance_status', 'compliant', 'non-compliant')
        assert severity == ChangeSeverity.HIGH

        # Medium severity
        severity = self.detector._determine_attribute_severity('tags', {}, {})
        assert severity == ChangeSeverity.MEDIUM

        # Low severity
        severity = self.detector._determine_attribute_severity('description', 'old', 'new')
        assert severity == ChangeSeverity.LOW

    def test_detect_compliance_changes(self):
        """Test compliance change detection."""
        old_resource = {
            'compliance_status': 'compliant',
            'compliance_violations': []
        }
        
        new_resource = {
            'compliance_status': 'non-compliant',
            'compliance_violations': [{'type': 'missing_tag', 'details': 'Missing CostCenter tag'}]
        }
        
        compliance_changes = self.detector._detect_compliance_changes(old_resource, new_resource)
        
        assert len(compliance_changes) >= 1
        
        # Should detect compliance status change
        status_change = next((c for c in compliance_changes if c.attribute_path == 'compliance_status'), None)
        if status_change:
            assert status_change.old_value == 'compliant'
            assert status_change.new_value == 'non-compliant'

    def test_assess_security_impact(self):
        """Test security impact assessment."""
        # IAM resource changes
        iam_resource = {'service': 'IAM', 'type': 'Role'}
        impact = self.detector._assess_security_impact(iam_resource, ChangeType.ADDED)
        assert impact is not None
        assert 'IAM' in impact

    def test_assess_network_impact(self):
        """Test network impact assessment."""
        # VPC resource changes
        vpc_resource = {'service': 'VPC', 'type': 'VPC'}
        impact = self.detector._assess_network_impact(vpc_resource, ChangeType.REMOVED)
        assert impact is not None
        assert 'VPC' in impact

    def test_resources_are_related(self):
        """Test resource relationship detection."""
        resource1 = {
            'vpc_id': 'vpc-12345',
            'subnet_id': 'subnet-12345',
            'security_groups': ['sg-12345', 'sg-67890']
        }
        
        resource2 = {
            'vpc_id': 'vpc-12345',  # Same VPC
            'subnet_id': 'subnet-67890',  # Different subnet
            'security_groups': ['sg-12345']  # Overlapping security group
        }
        
        resource3 = {
            'vpc_id': 'vpc-67890',  # Different VPC
            'subnet_id': 'subnet-99999',  # Different subnet
            'security_groups': ['sg-99999']  # Different security groups
        }
        
        # Resources 1 and 2 should be related (same VPC and overlapping SG)
        assert self.detector._resources_are_related(resource1, resource2) is True
        
        # Resources 1 and 3 should not be related
        assert self.detector._resources_are_related(resource1, resource3) is False

    def test_generate_change_statistics(self):
        """Test change statistics generation."""
        added_resources = [
            ResourceChange('arn1', 'id1', 'EC2', 'Instance', 'us-east-1', ChangeType.ADDED, severity=ChangeSeverity.HIGH)
        ]
        
        removed_resources = [
            ResourceChange('arn2', 'id2', 'RDS', 'DBInstance', 'us-east-1', ChangeType.REMOVED, severity=ChangeSeverity.HIGH)
        ]
        
        modified_resources = [
            ResourceChange('arn3', 'id3', 'S3', 'Bucket', 'us-east-1', ChangeType.MODIFIED, severity=ChangeSeverity.MEDIUM)
        ]
        
        unchanged_resources = [
            ResourceChange('arn4', 'id4', 'Lambda', 'Function', 'us-east-1', ChangeType.UNCHANGED, severity=ChangeSeverity.INFO)
        ]
        
        stats = self.detector._generate_change_statistics(
            added_resources, removed_resources, modified_resources, unchanged_resources
        )
        
        assert stats['total_changes'] == 3  # added + removed + modified
        assert stats['service_statistics']['EC2'] == 1
        assert stats['service_statistics']['RDS'] == 1
        assert stats['service_statistics']['S3'] == 1

    def test_detect_changes_integration(self):
        """Test the main detect_changes method integration."""
        old_resources = [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
                'id': 'i-12345',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1',
                'instance_type': 't3.micro',
                'tags': {'Name': 'test-instance'}
            }
        ]
        
        new_resources = [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
                'id': 'i-12345',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1',
                'instance_type': 't3.small',  # Changed
                'tags': {'Name': 'test-instance', 'Environment': 'prod'}  # Added tag
            },
            {
                'arn': 'arn:aws:s3:::new-bucket',
                'id': 'new-bucket',
                'service': 'S3',
                'type': 'Bucket',
                'region': 'us-east-1'
            }
        ]
        
        delta_report = self.detector.detect_changes(
            old_resources=old_resources,
            new_resources=new_resources,
            state1_id='state-1',
            state2_id='state-2'
        )
        
        # Verify report structure
        assert isinstance(delta_report, DeltaReport)
        assert delta_report.state1_id == 'state-1'
        assert delta_report.state2_id == 'state-2'
        
        # Should detect one added resource (S3 bucket)
        assert len(delta_report.added_resources) == 1
        assert delta_report.added_resources[0].service == 'S3'
        
        # Should detect one modified resource (EC2 instance)
        assert len(delta_report.modified_resources) == 1
        assert delta_report.modified_resources[0].service == 'EC2'
        
        # Should have no removed resources
        assert len(delta_report.removed_resources) == 0
        
        # Should have summary statistics
        assert delta_report.summary['added_count'] == 1
        assert delta_report.summary['modified_count'] == 1
        assert delta_report.summary['removed_count'] == 0


if __name__ == '__main__':
    pytest.main([__file__])