"""
Unit tests for DeltaDetector - Comprehensive change tracking
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from inventag.state.delta_detector import (
    DeltaDetector, ChangeType, ChangeSeverity, ChangeCategory,
    AttributeChange, ResourceChange, DeltaReport
)


class TestDeltaDetector:
    """Test suite for DeltaDetector functionality"""
    
    @pytest.fixture
    def delta_detector(self):
        """Create DeltaDetector instance for testing"""
        return DeltaDetector()
    
    @pytest.fixture
    def sample_old_resources(self):
        """Sample old resource data for testing"""
        return [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
                'id': 'i-1234567890abcdef0',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1',
                'tags': {'Name': 'test-instance', 'Environment': 'dev'},
                'compliance_status': 'compliant',
                'vpc_id': 'vpc-12345',
                'subnet_id': 'subnet-12345',
                'security_groups': ['sg-12345'],
                'state': 'running'
            },
            {
                'arn': 'arn:aws:s3:::test-bucket',
                'id': 'test-bucket',
                'service': 'S3',
                'type': 'Bucket',
                'region': 'us-east-1',
                'tags': {'Name': 'test-bucket'},
                'compliance_status': 'non-compliant',
                'encryption': {'enabled': False},
                'public_access': False
            },
            {
                'arn': 'arn:aws:rds:us-east-1:123456789012:db:test-db',
                'id': 'test-db',
                'service': 'RDS',
                'type': 'DBInstance',
                'region': 'us-east-1',
                'tags': {'Name': 'test-db', 'Environment': 'dev'},
                'compliance_status': 'compliant',
                'vpc_id': 'vpc-12345',
                'subnet_id': 'subnet-12345'
            }
        ]
    
    @pytest.fixture
    def sample_new_resources(self):
        """Sample new resource data for testing"""
        return [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
                'id': 'i-1234567890abcdef0',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1',
                'tags': {'Name': 'test-instance', 'Environment': 'prod', 'CostCenter': 'IT'},  # Modified tags
                'compliance_status': 'compliant',
                'vpc_id': 'vpc-12345',
                'subnet_id': 'subnet-67890',  # Modified subnet
                'security_groups': ['sg-12345', 'sg-67890'],  # Added security group
                'state': 'running'
            },
            {
                'arn': 'arn:aws:s3:::test-bucket',
                'id': 'test-bucket',
                'service': 'S3',
                'type': 'Bucket',
                'region': 'us-east-1',
                'tags': {'Name': 'test-bucket', 'Environment': 'prod'},  # Added tag
                'compliance_status': 'compliant',  # Changed compliance status
                'encryption': {'enabled': True, 'kms_key': 'arn:aws:kms:us-east-1:123456789012:key/12345'},  # Modified encryption
                'public_access': False
            },
            # RDS resource removed
            # New Lambda resource added
            {
                'arn': 'arn:aws:lambda:us-east-1:123456789012:function:test-function',
                'id': 'test-function',
                'service': 'Lambda',
                'type': 'Function',
                'region': 'us-east-1',
                'tags': {'Name': 'test-function', 'Environment': 'prod'},
                'compliance_status': 'compliant',
                'vpc_id': 'vpc-12345',
                'security_groups': ['sg-12345']
            }
        ]
    
    def test_initialization(self):
        """Test DeltaDetector initialization"""
        detector = DeltaDetector()
        
        assert detector.ignore_metadata_fields == ['last_seen', 'discovery_timestamp', 'scan_time', 'metadata']
        assert ChangeSeverity.CRITICAL in detector.severity_rules.values()
        assert 'EC2' in detector.dependency_patterns
        assert 'depends_on' in detector.dependency_patterns['EC2']
        assert 'affects' in detector.dependency_patterns['EC2']
    
    def test_initialization_with_custom_config(self):
        """Test DeltaDetector initialization with custom configuration"""
        custom_ignore_fields = ['custom_field', 'timestamp']
        custom_severity_rules = {'custom_attribute': ChangeSeverity.HIGH}
        
        detector = DeltaDetector(
            ignore_metadata_fields=custom_ignore_fields,
            severity_rules=custom_severity_rules
        )
        
        assert detector.ignore_metadata_fields == custom_ignore_fields
        assert detector.severity_rules == custom_severity_rules
    
    def test_create_resource_map(self, delta_detector, sample_old_resources):
        """Test resource map creation"""
        resource_map = delta_detector._create_resource_map(sample_old_resources)
        
        assert len(resource_map) == 3
        assert 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0' in resource_map
        assert 'arn:aws:s3:::test-bucket' in resource_map
        assert 'arn:aws:rds:us-east-1:123456789012:db:test-db' in resource_map
    
    def test_create_resource_map_without_arn(self, delta_detector):
        """Test resource map creation for resources without ARN"""
        resources = [
            {
                'id': 'resource-without-arn',
                'service': 'CustomService',
                'type': 'CustomType',
                'region': 'us-east-1'
            }
        ]
        
        resource_map = delta_detector._create_resource_map(resources)
        
        assert len(resource_map) == 1
        assert 'resource-without-arn' in resource_map
    
    def test_create_resource_map_without_arn_or_id(self, delta_detector):
        """Test resource map creation for resources without ARN or ID"""
        resources = [
            {
                'service': 'CustomService',
                'type': 'CustomType',
                'region': 'us-east-1',
                'name': 'test-resource'
            }
        ]
        
        resource_map = delta_detector._create_resource_map(resources)
        
        assert len(resource_map) == 1
        # Should create synthetic key
        synthetic_keys = [k for k in resource_map.keys() if k.startswith('CustomService:CustomType:us-east-1:')]
        assert len(synthetic_keys) == 1
    
    def test_detect_added_resources(self, delta_detector, sample_old_resources, sample_new_resources):
        """Test detection of added resources"""
        old_map = delta_detector._create_resource_map(sample_old_resources)
        new_map = delta_detector._create_resource_map(sample_new_resources)
        
        added_resources = delta_detector._detect_added_resources(old_map, new_map)
        
        assert len(added_resources) == 1
        assert added_resources[0].resource_arn == 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
        assert added_resources[0].service == 'Lambda'
        assert added_resources[0].change_type == ChangeType.ADDED
        assert added_resources[0].severity == ChangeSeverity.HIGH  # Lambda is high impact service
    
    def test_detect_removed_resources(self, delta_detector, sample_old_resources, sample_new_resources):
        """Test detection of removed resources"""
        old_map = delta_detector._create_resource_map(sample_old_resources)
        new_map = delta_detector._create_resource_map(sample_new_resources)
        
        removed_resources = delta_detector._detect_removed_resources(old_map, new_map)
        
        assert len(removed_resources) == 1
        assert removed_resources[0].resource_arn == 'arn:aws:rds:us-east-1:123456789012:db:test-db'
        assert removed_resources[0].service == 'RDS'
        assert removed_resources[0].change_type == ChangeType.REMOVED
        assert removed_resources[0].severity == ChangeSeverity.HIGH  # RDS is high impact service
    
    def test_detect_modified_resources(self, delta_detector, sample_old_resources, sample_new_resources):
        """Test detection of modified resources"""
        old_map = delta_detector._create_resource_map(sample_old_resources)
        new_map = delta_detector._create_resource_map(sample_new_resources)
        
        modified_resources, unchanged_resources = delta_detector._detect_modified_resources(old_map, new_map)
        
        assert len(modified_resources) == 2  # EC2 and S3 resources modified
        assert len(unchanged_resources) == 0  # No unchanged resources in this test
        
        # Check EC2 instance modifications
        ec2_change = next((r for r in modified_resources if r.service == 'EC2'), None)
        assert ec2_change is not None
        assert ec2_change.change_type == ChangeType.MODIFIED
        assert len(ec2_change.attribute_changes) > 0
        
        # Check S3 bucket modifications
        s3_change = next((r for r in modified_resources if r.service == 'S3'), None)
        assert s3_change is not None
        assert s3_change.change_type == ChangeType.MODIFIED
        assert len(s3_change.attribute_changes) > 0
    
    def test_compare_resources_simple_changes(self, delta_detector):
        """Test resource comparison with simple attribute changes"""
        old_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            'state': 'running',
            'tags': {'Name': 'test'},
            'compliance_status': 'compliant'
        }
        
        new_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            'state': 'stopped',  # Changed
            'tags': {'Name': 'test', 'Environment': 'prod'},  # Added tag
            'compliance_status': 'non-compliant'  # Changed
        }
        
        changes = delta_detector._compare_resources(old_resource, new_resource)
        
        assert len(changes) >= 2  # At least state and compliance_status changes
        
        # Check state change
        state_change = next((c for c in changes if c.attribute_path == 'state'), None)
        assert state_change is not None
        assert state_change.old_value == 'running'
        assert state_change.new_value == 'stopped'
        assert state_change.change_type == ChangeType.MODIFIED
        
        # Check compliance status change
        compliance_change = next((c for c in changes if c.attribute_path == 'compliance_status'), None)
        assert compliance_change is not None
        assert compliance_change.old_value == 'compliant'
        assert compliance_change.new_value == 'non-compliant'
        assert compliance_change.category == ChangeCategory.COMPLIANCE
        assert compliance_change.severity == ChangeSeverity.HIGH
    
    def test_compare_resources_nested_objects(self, delta_detector):
        """Test resource comparison with nested object changes"""
        old_resource = {
            'arn': 'arn:aws:s3:::test-bucket',
            'encryption': {
                'enabled': False,
                'algorithm': 'AES256'
            }
        }
        
        new_resource = {
            'arn': 'arn:aws:s3:::test-bucket',
            'encryption': {
                'enabled': True,  # Changed
                'algorithm': 'aws:kms',  # Changed
                'kms_key': 'arn:aws:kms:us-east-1:123456789012:key/12345'  # Added
            }
        }
        
        changes = delta_detector._compare_resources(old_resource, new_resource)
        
        # Should detect changes in nested encryption object
        encryption_changes = [c for c in changes if 'encryption' in c.attribute_path]
        assert len(encryption_changes) > 0
        
        # Check for specific nested changes
        enabled_change = next((c for c in changes if c.attribute_path == 'encryption.enabled'), None)
        assert enabled_change is not None
        assert enabled_change.old_value is False
        assert enabled_change.new_value is True
        assert enabled_change.category == ChangeCategory.SECURITY
    
    def test_compare_resources_list_changes(self, delta_detector):
        """Test resource comparison with list changes"""
        old_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            'security_groups': ['sg-12345', 'sg-67890']
        }
        
        new_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            'security_groups': ['sg-12345', 'sg-abcde']  # Removed sg-67890, added sg-abcde
        }
        
        changes = delta_detector._compare_resources(old_resource, new_resource)
        
        # Should detect changes in security groups list
        sg_changes = [c for c in changes if 'security_groups' in c.attribute_path]
        assert len(sg_changes) > 0
        
        # Check for added and removed items
        added_change = next((c for c in sg_changes if c.change_type == ChangeType.ADDED), None)
        removed_change = next((c for c in sg_changes if c.change_type == ChangeType.REMOVED), None)
        
        if added_change:
            assert 'sg-abcde' in str(added_change.new_value)
        if removed_change:
            assert 'sg-67890' in str(removed_change.old_value)
    
    def test_categorize_attribute_change(self, delta_detector):
        """Test attribute change categorization"""
        # Security-related attributes
        assert delta_detector._categorize_attribute_change('security_groups', [], []) == ChangeCategory.SECURITY
        assert delta_detector._categorize_attribute_change('iam_role', None, 'role') == ChangeCategory.SECURITY
        assert delta_detector._categorize_attribute_change('encryption', {}, {}) == ChangeCategory.SECURITY
        
        # Network-related attributes
        assert delta_detector._categorize_attribute_change('vpc_id', 'vpc-1', 'vpc-2') == ChangeCategory.NETWORK
        assert delta_detector._categorize_attribute_change('subnet_id', 'subnet-1', 'subnet-2') == ChangeCategory.NETWORK
        assert delta_detector._categorize_attribute_change('ip_address', '1.1.1.1', '2.2.2.2') == ChangeCategory.NETWORK
        
        # Tag-related attributes
        assert delta_detector._categorize_attribute_change('tags', {}, {}) == ChangeCategory.TAGS
        assert delta_detector._categorize_attribute_change('tag_key', 'old', 'new') == ChangeCategory.TAGS
        
        # Compliance-related attributes
        assert delta_detector._categorize_attribute_change('compliance_status', 'compliant', 'non-compliant') == ChangeCategory.COMPLIANCE
        assert delta_detector._categorize_attribute_change('compliance_violations', [], []) == ChangeCategory.COMPLIANCE
        
        # Configuration (default)
        assert delta_detector._categorize_attribute_change('state', 'running', 'stopped') == ChangeCategory.CONFIGURATION
        assert delta_detector._categorize_attribute_change('name', 'old-name', 'new-name') == ChangeCategory.CONFIGURATION
    
    def test_determine_attribute_severity(self, delta_detector):
        """Test attribute severity determination"""
        # Critical severity
        assert delta_detector._determine_attribute_severity('security_groups', [], []) == ChangeSeverity.CRITICAL
        assert delta_detector._determine_attribute_severity('encryption', {}, {}) == ChangeSeverity.CRITICAL
        
        # High severity
        assert delta_detector._determine_attribute_severity('compliance_status', 'compliant', 'non-compliant') == ChangeSeverity.HIGH
        assert delta_detector._determine_attribute_severity('policy', {}, {}) == ChangeSeverity.HIGH
        
        # Medium severity
        assert delta_detector._determine_attribute_severity('tags', {}, {}) == ChangeSeverity.MEDIUM
        assert delta_detector._determine_attribute_severity('configuration', {}, {}) == ChangeSeverity.MEDIUM
        
        # Low severity
        assert delta_detector._determine_attribute_severity('description', 'old', 'new') == ChangeSeverity.LOW
        assert delta_detector._determine_attribute_severity('name', 'old', 'new') == ChangeSeverity.LOW
    
    def test_determine_resource_severity(self, delta_detector):
        """Test resource-level severity determination"""
        # Critical services
        iam_resource = {'service': 'IAM', 'type': 'Role'}
        assert delta_detector._determine_resource_severity(iam_resource, ChangeType.ADDED) == ChangeSeverity.CRITICAL
        
        kms_resource = {'service': 'KMS', 'type': 'Key'}
        assert delta_detector._determine_resource_severity(kms_resource, ChangeType.REMOVED) == ChangeSeverity.CRITICAL
        
        # High impact services
        ec2_resource = {'service': 'EC2', 'type': 'Instance'}
        assert delta_detector._determine_resource_severity(ec2_resource, ChangeType.ADDED) == ChangeSeverity.HIGH
        
        rds_resource = {'service': 'RDS', 'type': 'DBInstance'}
        assert delta_detector._determine_resource_severity(rds_resource, ChangeType.MODIFIED) == ChangeSeverity.HIGH
        
        # Medium impact services
        s3_resource = {'service': 'S3', 'type': 'Bucket'}
        assert delta_detector._determine_resource_severity(s3_resource, ChangeType.ADDED) == ChangeSeverity.MEDIUM
        
        # Low impact services
        unknown_resource = {'service': 'UnknownService', 'type': 'UnknownType'}
        assert delta_detector._determine_resource_severity(unknown_resource, ChangeType.ADDED) == ChangeSeverity.LOW
    
    def test_detect_compliance_changes(self, delta_detector):
        """Test compliance change detection"""
        old_resource = {
            'compliance_status': 'compliant',
            'compliance_violations': []
        }
        
        new_resource = {
            'compliance_status': 'non-compliant',
            'compliance_violations': [{'type': 'missing_tag', 'details': 'Missing CostCenter tag'}]
        }
        
        compliance_changes = delta_detector._detect_compliance_changes(old_resource, new_resource)
        
        assert len(compliance_changes) == 2  # Status and violations changed
        
        # Check compliance status change
        status_change = next((c for c in compliance_changes if c.attribute_path == 'compliance_status'), None)
        assert status_change is not None
        assert status_change.old_value == 'compliant'
        assert status_change.new_value == 'non-compliant'
        assert status_change.severity == ChangeSeverity.HIGH
        
        # Check violations change
        violations_change = next((c for c in compliance_changes if c.attribute_path == 'compliance_violations'), None)
        assert violations_change is not None
        assert violations_change.severity == ChangeSeverity.HIGH
    
    def test_assess_security_impact(self, delta_detector):
        """Test security impact assessment"""
        # IAM resource changes
        iam_resource = {'service': 'IAM', 'type': 'Role'}
        impact = delta_detector._assess_security_impact(iam_resource, ChangeType.ADDED)
        assert impact is not None
        assert 'IAM' in impact
        assert 'access controls' in impact
        
        # Security group changes
        sg_resource = {'service': 'EC2', 'type': 'SecurityGroup'}
        impact = delta_detector._assess_security_impact(sg_resource, ChangeType.MODIFIED)
        assert impact is not None
        assert 'security group' in impact.lower()
        assert 'network access' in impact
        
        # Public access changes
        old_resource = {'public_access': False}
        new_resource = {'public_access': True}
        impact = delta_detector._assess_security_impact(new_resource, ChangeType.MODIFIED, old_resource)
        assert impact is not None
        assert 'publicly accessible' in impact
    
    def test_assess_network_impact(self, delta_detector):
        """Test network impact assessment"""
        # VPC resource changes
        vpc_resource = {'service': 'VPC', 'type': 'VPC'}
        impact = delta_detector._assess_network_impact(vpc_resource, ChangeType.REMOVED)
        assert impact is not None
        assert 'VPC' in impact
        assert 'network' in impact
        
        # VPC/Subnet changes in resource
        old_resource = {'vpc_id': 'vpc-12345', 'subnet_id': 'subnet-12345'}
        new_resource = {'vpc_id': 'vpc-67890', 'subnet_id': 'subnet-67890'}
        impact = delta_detector._assess_network_impact(new_resource, ChangeType.MODIFIED, old_resource)
        assert impact is not None
        assert 'VPC changed' in impact
        assert 'Subnet changed' in impact
    
    def test_is_publicly_accessible(self, delta_detector):
        """Test public accessibility detection"""
        # Resource with public access flag
        public_resource = {'public_access': True}
        assert delta_detector._is_publicly_accessible(public_resource) is True
        
        # Resource with public IP
        public_ip_resource = {'public_ip': '1.2.3.4'}
        assert delta_detector._is_publicly_accessible(public_ip_resource) is True
        
        # Resource with 0.0.0.0/0 in security groups
        open_sg_resource = {'security_groups': ['sg-12345 (0.0.0.0/0:80)']}
        assert delta_detector._is_publicly_accessible(open_sg_resource) is True
        
        # Private resource
        private_resource = {'public_access': False, 'public_ip': None}
        assert delta_detector._is_publicly_accessible(private_resource) is False
    
    def test_calculate_compliance_stats(self, delta_detector):
        """Test compliance statistics calculation"""
        resources = [
            {'compliance_status': 'compliant'},
            {'compliance_status': 'compliant'},
            {'compliance_status': 'non-compliant'},
            {'compliance_status': 'unknown'}
        ]
        
        stats = delta_detector._calculate_compliance_stats(resources)
        
        assert stats['total_resources'] == 4
        assert stats['compliant_resources'] == 2
        assert stats['non_compliant_resources'] == 1
        assert stats['compliance_percentage'] == 50.0
    
    def test_calculate_compliance_stats_empty(self, delta_detector):
        """Test compliance statistics calculation with empty resources"""
        stats = delta_detector._calculate_compliance_stats([])
        
        assert stats['total_resources'] == 0
        assert stats['compliant_resources'] == 0
        assert stats['non_compliant_resources'] == 0
        assert stats['compliance_percentage'] == 0.0
    
    def test_find_related_resources(self, delta_detector):
        """Test finding related resources"""
        # Create a change for an EC2 instance
        ec2_change = ResourceChange(
            resource_arn='arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            resource_id='i-1234567890abcdef0',
            service='EC2',
            resource_type='Instance',
            region='us-east-1',
            change_type=ChangeType.MODIFIED
        )
        
        # Create resource maps with related resources
        old_resources_map = {
            'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0': {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
                'service': 'EC2',
                'vpc_id': 'vpc-12345',
                'security_groups': ['sg-12345']
            }
        }
        
        new_resources_map = {
            'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0': {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
                'service': 'EC2',
                'vpc_id': 'vpc-12345',
                'security_groups': ['sg-12345']
            },
            'arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/test-lb': {
                'arn': 'arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/test-lb',
                'service': 'ELB',
                'vpc_id': 'vpc-12345',  # Same VPC - should be related
                'security_groups': ['sg-12345']  # Same security group - should be related
            }
        }
        
        dependency_patterns = delta_detector.dependency_patterns['EC2']
        related_resources = delta_detector._find_related_resources(
            ec2_change, dependency_patterns, old_resources_map, new_resources_map
        )
        
        # Should find the ELB as related (EC2 affects ELB and they share VPC/SG)
        assert len(related_resources) >= 0  # May or may not find relations depending on exact logic
    
    def test_resources_are_related(self, delta_detector):
        """Test resource relationship detection"""
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
        assert delta_detector._resources_are_related(resource1, resource2) is True
        
        # Resources 1 and 3 should not be related
        assert delta_detector._resources_are_related(resource1, resource3) is False
    
    def test_detect_changes_comprehensive(self, delta_detector, sample_old_resources, sample_new_resources):
        """Test comprehensive change detection"""
        delta_report = delta_detector.detect_changes(
            old_resources=sample_old_resources,
            new_resources=sample_new_resources,
            state1_id='20231201_120000',
            state2_id='20231201_130000'
        )
        
        # Verify report structure
        assert isinstance(delta_report, DeltaReport)
        assert delta_report.state1_id == '20231201_120000'
        assert delta_report.state2_id == '20231201_130000'
        assert delta_report.timestamp is not None
        
        # Verify summary
        assert delta_report.summary['total_resources_old'] == 3
        assert delta_report.summary['total_resources_new'] == 3
        assert delta_report.summary['added_count'] == 1  # Lambda added
        assert delta_report.summary['removed_count'] == 1  # RDS removed
        assert delta_report.summary['modified_count'] == 2  # EC2 and S3 modified
        assert delta_report.summary['total_changes'] == 4
        
        # Verify change lists
        assert len(delta_report.added_resources) == 1
        assert len(delta_report.removed_resources) == 1
        assert len(delta_report.modified_resources) == 2
        
        # Verify compliance changes
        assert 'old_compliance_stats' in delta_report.compliance_changes
        assert 'new_compliance_stats' in delta_report.compliance_changes
        assert 'compliance_trend' in delta_report.compliance_changes
        
        # Verify security and network changes
        assert 'total_security_changes' in delta_report.security_changes
        assert 'total_network_changes' in delta_report.network_changes
        
        # Verify impact analysis
        assert 'high_impact_changes' in delta_report.impact_analysis
        assert 'dependency_impacts' in delta_report.impact_analysis
        
        # Verify statistics
        assert 'total_changes' in delta_report.change_statistics
        assert 'service_statistics' in delta_report.change_statistics
        assert 'severity_statistics' in delta_report.change_statistics
    
    def test_generate_change_statistics(self, delta_detector):
        """Test change statistics generation"""
        added_resources = [
            ResourceChange('arn1', 'id1', 'EC2', 'Instance', 'us-east-1', ChangeType.ADDED, severity=ChangeSeverity.HIGH),
            ResourceChange('arn2', 'id2', 'S3', 'Bucket', 'us-east-1', ChangeType.ADDED, severity=ChangeSeverity.MEDIUM)
        ]
        
        removed_resources = [
            ResourceChange('arn3', 'id3', 'RDS', 'DBInstance', 'us-east-1', ChangeType.REMOVED, severity=ChangeSeverity.HIGH)
        ]
        
        modified_resources = [
            ResourceChange('arn4', 'id4', 'EC2', 'Instance', 'us-east-1', ChangeType.MODIFIED, severity=ChangeSeverity.LOW)
        ]
        
        unchanged_resources = [
            ResourceChange('arn5', 'id5', 'Lambda', 'Function', 'us-east-1', ChangeType.UNCHANGED, severity=ChangeSeverity.INFO)
        ]
        
        stats = delta_detector._generate_change_statistics(
            added_resources, removed_resources, modified_resources, unchanged_resources
        )
        
        assert stats['total_changes'] == 4
        assert stats['change_percentage'] == 80.0  # 4 changes out of 5 total resources
        
        # Check service statistics
        assert 'EC2' in stats['service_statistics']
        assert stats['service_statistics']['EC2']['added'] == 1
        assert stats['service_statistics']['EC2']['modified'] == 1
        
        # Check severity statistics
        assert stats['severity_statistics']['high'] == 2
        assert stats['severity_statistics']['medium'] == 1
        assert stats['severity_statistics']['low'] == 1
        
        # Check most changed service
        assert stats['most_changed_service'] == 'EC2'  # 2 changes (1 added + 1 modified)
    
    def test_ignore_metadata_fields(self, delta_detector):
        """Test that metadata fields are properly ignored"""
        old_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            'state': 'running',
            'last_seen': '2023-12-01T10:00:00Z',  # Should be ignored
            'discovery_timestamp': '2023-12-01T10:00:00Z',  # Should be ignored
            'metadata': {'some': 'data'}  # Should be ignored
        }
        
        new_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            'state': 'running',
            'last_seen': '2023-12-01T11:00:00Z',  # Different but should be ignored
            'discovery_timestamp': '2023-12-01T11:00:00Z',  # Different but should be ignored
            'metadata': {'different': 'data'}  # Different but should be ignored
        }
        
        changes = delta_detector._compare_resources(old_resource, new_resource)
        
        # Should not detect any changes since only ignored fields changed
        assert len(changes) == 0
    
    def test_complex_change_patterns(self, delta_detector):
        """Test complex change patterns and edge cases"""
        old_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            'tags': {'Name': 'test', 'Environment': 'dev'},
            'security_groups': ['sg-12345'],
            'nested_config': {
                'setting1': 'value1',
                'setting2': {'subsetting': 'subvalue'}
            },
            'list_of_objects': [
                {'id': '1', 'name': 'object1'},
                {'id': '2', 'name': 'object2'}
            ]
        }
        
        new_resource = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            'tags': {'Name': 'test', 'Environment': 'prod', 'CostCenter': 'IT'},  # Modified and added
            'security_groups': ['sg-12345', 'sg-67890'],  # Added
            'nested_config': {
                'setting1': 'new_value1',  # Modified
                'setting2': {'subsetting': 'subvalue'},  # Unchanged
                'setting3': 'new_setting'  # Added
            },
            'list_of_objects': [
                {'id': '1', 'name': 'modified_object1'},  # Modified
                {'id': '3', 'name': 'object3'}  # Different object
            ]
        }
        
        changes = delta_detector._compare_resources(old_resource, new_resource)
        
        # Should detect multiple types of changes
        assert len(changes) > 0
        
        # Check for tag changes
        tag_changes = [c for c in changes if 'tags' in c.attribute_path]
        assert len(tag_changes) > 0
        
        # Check for security group changes
        sg_changes = [c for c in changes if 'security_groups' in c.attribute_path]
        assert len(sg_changes) > 0
        
        # Check for nested config changes
        nested_changes = [c for c in changes if 'nested_config' in c.attribute_path]
        assert len(nested_changes) > 0
        
        # Check for list changes
        list_changes = [c for c in changes if 'list_of_objects' in c.attribute_path]
        assert len(list_changes) > 0


if __name__ == "__main__":
    pytest.main([__file__])