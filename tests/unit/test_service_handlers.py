#!/usr/bin/env python3
"""
Unit tests for Specific AWS Service Handlers

Tests the service-specific handlers for major AWS services.
"""

import pytest
import boto3
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError
from datetime import datetime

from inventag.discovery.service_handlers import (
    S3Handler,
    RDSHandler,
    EC2Handler,
    LambdaHandler,
    ECSHandler,
    EKSHandler
)


class TestS3Handler:
    """Test the S3Handler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.handler = S3Handler(self.mock_session)
    
    def test_can_handle_s3_service(self):
        """Test that S3Handler can handle S3 service."""
        assert self.handler.can_handle('S3', 'Bucket')
        assert self.handler.can_handle('s3', 'Bucket')
        assert not self.handler.can_handle('EC2', 'Instance')
    
    def test_define_read_only_operations(self):
        """Test that S3Handler defines appropriate read-only operations."""
        operations = self.handler._define_read_only_operations()
        
        expected_operations = [
            'get_bucket_encryption',
            'get_bucket_versioning',
            'get_bucket_location',
            'get_bucket_tagging',
            'get_public_access_block'
        ]
        
        for op in expected_operations:
            assert op in operations
    
    def test_enrich_s3_bucket_success(self):
        """Test successful S3 bucket enrichment."""
        resource = {
            'service': 'S3',
            'type': 'Bucket',
            'id': 'test-bucket',
            'region': 'us-east-1'
        }
        
        # Mock S3 client and responses
        mock_s3_client = Mock()
        
        # Mock encryption response
        mock_s3_client.get_bucket_encryption.return_value = {
            'ServerSideEncryptionConfiguration': {
                'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]
            }
        }
        
        # Mock versioning response
        mock_s3_client.get_bucket_versioning.return_value = {
            'Status': 'Enabled'
        }
        
        # Mock location response
        mock_s3_client.get_bucket_location.return_value = {
            'LocationConstraint': 'us-west-2'
        }
        
        # Mock lifecycle response
        mock_s3_client.get_bucket_lifecycle_configuration.return_value = {
            'Rules': [{'Status': 'Enabled', 'Id': 'test-rule'}]
        }
        
        # Mock public access block response
        mock_s3_client.get_public_access_block.return_value = {
            'PublicAccessBlockConfiguration': {
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True
            }
        }
        
        # Mock object lock response (returns None to simulate no object lock)
        mock_s3_client.get_object_lock_configuration.side_effect = ClientError(
            {'Error': {'Code': 'ObjectLockConfigurationNotFoundError'}}, 'get_object_lock_configuration'
        )
        
        self.mock_session.client.return_value = mock_s3_client
        
        # Mock the _safe_api_call method to return the expected responses
        with patch.object(self.handler, '_safe_api_call') as mock_safe_call:
            def side_effect(client, operation, **kwargs):
                if operation == 'get_bucket_encryption':
                    return {'ServerSideEncryptionConfiguration': {'Rules': []}}
                elif operation == 'get_bucket_versioning':
                    return {'Status': 'Enabled'}
                elif operation == 'get_bucket_location':
                    return {'LocationConstraint': 'us-west-2'}
                elif operation == 'get_bucket_lifecycle_configuration':
                    return {'Rules': [{'Status': 'Enabled'}]}
                elif operation == 'get_public_access_block':
                    return {'PublicAccessBlockConfiguration': {'BlockPublicAcls': True}}
                elif operation == 'get_object_lock_configuration':
                    return None
                return None
            
            mock_safe_call.side_effect = side_effect
            
            result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert 'encryption' in attributes
        assert 'versioning_status' in attributes
        assert 'location' in attributes
        assert 'lifecycle_rules' in attributes
        assert 'public_access_block' in attributes
        assert 'object_lock' in attributes
        
        assert attributes['versioning_status'] == 'Enabled'
        assert attributes['location'] == 'us-west-2'
    
    def test_enrich_non_bucket_resource(self):
        """Test that non-bucket resources are returned unchanged."""
        resource = {
            'service': 'S3',
            'type': 'Object',
            'id': 'test-object'
        }
        
        result = self.handler.enrich_resource(resource)
        assert result == resource
    
    def test_enrich_bucket_without_id(self):
        """Test handling of bucket resource without ID."""
        resource = {
            'service': 'S3',
            'type': 'Bucket'
        }
        
        result = self.handler.enrich_resource(resource)
        assert result == resource
    
    def test_enrich_bucket_api_failure(self):
        """Test handling when S3 API calls fail."""
        resource = {
            'service': 'S3',
            'type': 'Bucket',
            'id': 'test-bucket'
        }
        
        # Mock session to raise exception
        self.mock_session.client.side_effect = Exception("AWS API Error")
        
        result = self.handler.enrich_resource(resource)
        
        # Should return original resource when enrichment fails
        assert result == resource


class TestRDSHandler:
    """Test the RDSHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.handler = RDSHandler(self.mock_session)
    
    def test_can_handle_rds_service(self):
        """Test that RDSHandler can handle RDS service."""
        assert self.handler.can_handle('RDS', 'DBInstance')
        assert self.handler.can_handle('rds', 'DBCluster')
        assert not self.handler.can_handle('S3', 'Bucket')
    
    def test_enrich_db_instance_success(self):
        """Test successful DB instance enrichment."""
        resource = {
            'service': 'RDS',
            'type': 'DBInstance',
            'id': 'test-db-instance'
        }
        
        mock_db_instance = {
            'Engine': 'mysql',
            'EngineVersion': '8.0.35',
            'DBInstanceClass': 'db.t3.micro',
            'AllocatedStorage': 20,
            'StorageType': 'gp2',
            'StorageEncrypted': True,
            'KmsKeyId': 'arn:aws:kms:us-east-1:123456789012:key/test-key',
            'MultiAZ': False,
            'PubliclyAccessible': False,
            'BackupRetentionPeriod': 7,
            'PreferredBackupWindow': '03:00-04:00',
            'PreferredMaintenanceWindow': 'sun:04:00-sun:05:00',
            'VpcSecurityGroups': [{'VpcSecurityGroupId': 'sg-123456'}],
            'DBSubnetGroup': {'DBSubnetGroupName': 'default-subnet-group'},
            'DBParameterGroups': [{'DBParameterGroupName': 'default.mysql8.0'}],
            'OptionGroupMemberships': [{'OptionGroupName': 'default:mysql-8-0'}],
            'DeletionProtection': True,
            'PerformanceInsightsEnabled': False,
            'MonitoringInterval': 0,
            'EnhancedMonitoringResourceArn': None
        }
        
        with patch.object(self.handler, '_safe_api_call') as mock_safe_call:
            mock_safe_call.return_value = {'DBInstances': [mock_db_instance]}
            
            result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert attributes['engine'] == 'mysql'
        assert attributes['engine_version'] == '8.0.35'
        assert attributes['db_instance_class'] == 'db.t3.micro'
        assert attributes['storage_encrypted'] is True
        assert attributes['multi_az'] is False
        assert attributes['backup_retention_period'] == 7
    
    def test_enrich_db_cluster_success(self):
        """Test successful DB cluster enrichment."""
        resource = {
            'service': 'RDS',
            'type': 'DBCluster',
            'id': 'test-db-cluster'
        }
        
        mock_db_cluster = {
            'Engine': 'aurora-mysql',
            'EngineVersion': '8.0.mysql_aurora.3.02.0',
            'EngineMode': 'provisioned',
            'StorageEncrypted': True,
            'KmsKeyId': 'arn:aws:kms:us-east-1:123456789012:key/test-key',
            'BackupRetentionPeriod': 7,
            'PreferredBackupWindow': '03:00-04:00',
            'PreferredMaintenanceWindow': 'sun:04:00-sun:05:00',
            'VpcSecurityGroups': [{'VpcSecurityGroupId': 'sg-123456'}],
            'DBSubnetGroup': 'default-subnet-group',
            'DBClusterParameterGroup': 'default.aurora-mysql8.0',
            'DeletionProtection': True,
            'MultiAZ': False,
            'DBClusterMembers': [{'DBInstanceIdentifier': 'test-instance-1'}],
            'GlobalWriteForwardingStatus': 'disabled',
            'CrossAccountClone': False,
            'Capacity': None,
            'ScalingConfigurationInfo': {}
        }
        
        with patch.object(self.handler, '_safe_api_call') as mock_safe_call:
            mock_safe_call.return_value = {'DBClusters': [mock_db_cluster]}
            
            result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert attributes['engine'] == 'aurora-mysql'
        assert attributes['engine_mode'] == 'provisioned'
        assert attributes['storage_encrypted'] is True
        assert attributes['cluster_members'] == ['test-instance-1']


class TestEC2Handler:
    """Test the EC2Handler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.handler = EC2Handler(self.mock_session)
    
    def test_can_handle_ec2_service(self):
        """Test that EC2Handler can handle EC2 service."""
        assert self.handler.can_handle('EC2', 'Instance')
        assert self.handler.can_handle('ec2', 'Volume')
        assert not self.handler.can_handle('S3', 'Bucket')
    
    def test_enrich_ec2_instance_success(self):
        """Test successful EC2 instance enrichment."""
        resource = {
            'service': 'EC2',
            'type': 'Instance',
            'id': 'i-1234567890abcdef0'
        }
        
        mock_instance = {
            'InstanceId': 'i-1234567890abcdef0',
            'InstanceType': 't3.micro',
            'State': {'Name': 'running'},
            'Platform': None,
            'Architecture': 'x86_64',
            'Hypervisor': 'xen',
            'VirtualizationType': 'hvm',
            'ImageId': 'ami-12345678',
            'KeyName': 'my-key-pair',
            'LaunchTime': datetime(2023, 1, 1, 12, 0, 0),
            'Placement': {
                'AvailabilityZone': 'us-east-1a',
                'Tenancy': 'default',
                'HostId': None
            },
            'SubnetId': 'subnet-12345678',
            'VpcId': 'vpc-12345678',
            'PrivateIpAddress': '10.0.1.100',
            'PublicIpAddress': '54.123.45.67',
            'PrivateDnsName': 'ip-10-0-1-100.ec2.internal',
            'PublicDnsName': 'ec2-54-123-45-67.compute-1.amazonaws.com',
            'SecurityGroups': [{'GroupId': 'sg-12345678'}],
            'IamInstanceProfile': {'Arn': 'arn:aws:iam::123456789012:instance-profile/test-role'},
            'Monitoring': {'State': 'disabled'},
            'SourceDestCheck': True,
            'EbsOptimized': False,
            'SriovNetSupport': 'simple',
            'EnaSupport': True,
            'RootDeviceType': 'ebs',
            'RootDeviceName': '/dev/xvda',
            'BlockDeviceMappings': [{'DeviceName': '/dev/xvda', 'Ebs': {'VolumeId': 'vol-12345678'}}],
            'NetworkInterfaces': [{'NetworkInterfaceId': 'eni-12345678'}],
            'CpuOptions': {'CoreCount': 1, 'ThreadsPerCore': 2},
            'CapacityReservationSpecification': {'CapacityReservationPreference': 'open'},
            'HibernationOptions': {'Configured': False},
            'MetadataOptions': {'State': 'applied', 'HttpTokens': 'optional'},
            'EnclaveOptions': {'Enabled': False}
        }
        
        with patch.object(self.handler, '_safe_api_call') as mock_safe_call:
            mock_safe_call.return_value = {
                'Reservations': [{'Instances': [mock_instance]}]
            }
            
            result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert attributes['instance_type'] == 't3.micro'
        assert attributes['state'] == 'running'
        assert attributes['architecture'] == 'x86_64'
        assert attributes['availability_zone'] == 'us-east-1a'
        assert attributes['vpc_id'] == 'vpc-12345678'
        assert attributes['security_groups'] == ['sg-12345678']
    
    def test_enrich_ebs_volume_success(self):
        """Test successful EBS volume enrichment."""
        resource = {
            'service': 'EC2',
            'type': 'Volume',
            'id': 'vol-1234567890abcdef0'
        }
        
        mock_volume = {
            'VolumeId': 'vol-1234567890abcdef0',
            'Size': 8,
            'VolumeType': 'gp3',
            'Iops': 3000,
            'Throughput': 125,
            'State': 'in-use',
            'Encrypted': True,
            'KmsKeyId': 'arn:aws:kms:us-east-1:123456789012:key/test-key',
            'SnapshotId': 'snap-12345678',
            'AvailabilityZone': 'us-east-1a',
            'CreateTime': datetime(2023, 1, 1, 12, 0, 0),
            'Attachments': [{'InstanceId': 'i-12345678', 'Device': '/dev/xvda'}],
            'MultiAttachEnabled': False,
            'FastRestored': False,
            'OutpostArn': None
        }
        
        with patch.object(self.handler, '_safe_api_call') as mock_safe_call:
            mock_safe_call.return_value = {'Volumes': [mock_volume]}
            
            result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert attributes['size'] == 8
        assert attributes['volume_type'] == 'gp3'
        assert attributes['encrypted'] is True
        assert attributes['state'] == 'in-use'
        assert attributes['availability_zone'] == 'us-east-1a'


class TestLambdaHandler:
    """Test the LambdaHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.handler = LambdaHandler(self.mock_session)
    
    def test_can_handle_lambda_service(self):
        """Test that LambdaHandler can handle Lambda service."""
        assert self.handler.can_handle('LAMBDA', 'Function')
        assert self.handler.can_handle('lambda', 'Function')
        assert not self.handler.can_handle('S3', 'Bucket')
    
    def test_enrich_lambda_function_success(self):
        """Test successful Lambda function enrichment."""
        resource = {
            'service': 'LAMBDA',
            'type': 'Function',
            'id': 'test-function'
        }
        
        mock_function_config = {
            'Runtime': 'python3.9',
            'Role': 'arn:aws:iam::123456789012:role/lambda-role',
            'Handler': 'lambda_function.lambda_handler',
            'CodeSize': 1024,
            'Description': 'Test Lambda function',
            'Timeout': 30,
            'MemorySize': 128,
            'LastModified': '2023-01-01T12:00:00.000+0000',
            'CodeSha256': 'abc123def456',
            'Version': '$LATEST',
            'VpcConfig': {
                'SubnetIds': ['subnet-12345678'],
                'SecurityGroupIds': ['sg-12345678']
            },
            'Environment': {
                'Variables': {'ENV': 'test'}
            },
            'DeadLetterConfig': {},
            'KMSKeyArn': 'arn:aws:kms:us-east-1:123456789012:key/test-key',
            'TracingConfig': {'Mode': 'PassThrough'},
            'MasterArn': None,
            'RevisionId': 'rev-123',
            'Layers': [],
            'State': 'Active',
            'StateReason': None,
            'StateReasonCode': None,
            'LastUpdateStatus': 'Successful',
            'LastUpdateStatusReason': None,
            'LastUpdateStatusReasonCode': None,
            'FileSystemConfigs': [],
            'PackageType': 'Zip',
            'ImageConfigResponse': {},
            'SigningProfileVersionArn': None,
            'SigningJobArn': None,
            'Architectures': ['x86_64'],
            'EphemeralStorage': {'Size': 512},
            'SnapStart': {'ApplyOn': 'None'},
            'RuntimeVersionConfig': {},
            'LoggingConfig': {}
        }
        
        mock_code = {
            'RepositoryType': 'S3',
            'Location': 'https://s3.amazonaws.com/test-bucket/function.zip',
            'ImageUri': None,
            'ResolvedImageUri': None
        }
        
        with patch.object(self.handler, '_safe_api_call') as mock_safe_call:
            def side_effect(client, operation, **kwargs):
                if operation == 'get_function':
                    return {
                        'Configuration': mock_function_config,
                        'Code': mock_code
                    }
                elif operation == 'get_function_concurrency':
                    return {'ReservedConcurrencyExecutions': 100}
                return None
            
            mock_safe_call.side_effect = side_effect
            
            result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert attributes['runtime'] == 'python3.9'
        assert attributes['handler'] == 'lambda_function.lambda_handler'
        assert attributes['memory_size'] == 128
        assert attributes['timeout'] == 30
        assert attributes['package_type'] == 'Zip'
        assert attributes['reserved_concurrency_executions'] == 100


class TestECSHandler:
    """Test the ECSHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.handler = ECSHandler(self.mock_session)
    
    def test_can_handle_ecs_service(self):
        """Test that ECSHandler can handle ECS service."""
        assert self.handler.can_handle('ECS', 'Cluster')
        assert self.handler.can_handle('ecs', 'Service')
        assert not self.handler.can_handle('S3', 'Bucket')
    
    def test_enrich_ecs_cluster_success(self):
        """Test successful ECS cluster enrichment."""
        resource = {
            'service': 'ECS',
            'type': 'Cluster',
            'id': 'test-cluster'
        }
        
        mock_cluster = {
            'status': 'ACTIVE',
            'runningTasksCount': 5,
            'pendingTasksCount': 0,
            'activeServicesCount': 3,
            'statistics': [{'name': 'runningTasksCount', 'value': '5'}],
            'capacityProviders': ['FARGATE', 'EC2'],
            'defaultCapacityProviderStrategy': [{'capacityProvider': 'FARGATE', 'weight': 1}],
            'attachments': [],
            'settings': [{'name': 'containerInsights', 'value': 'enabled'}],
            'configuration': {'executeCommandConfiguration': {'logging': 'DEFAULT'}},
            'serviceConnectDefaults': {}
        }
        
        with patch.object(self.handler, '_safe_api_call') as mock_safe_call:
            mock_safe_call.return_value = {'clusters': [mock_cluster]}
            
            result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert attributes['status'] == 'ACTIVE'
        assert attributes['running_tasks_count'] == 5
        assert attributes['active_services_count'] == 3
        assert attributes['capacity_providers'] == ['FARGATE', 'EC2']


class TestEKSHandler:
    """Test the EKSHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.handler = EKSHandler(self.mock_session)
    
    def test_can_handle_eks_service(self):
        """Test that EKSHandler can handle EKS service."""
        assert self.handler.can_handle('EKS', 'Cluster')
        assert self.handler.can_handle('eks', 'Nodegroup')
        assert not self.handler.can_handle('S3', 'Bucket')
    
    def test_enrich_eks_cluster_success(self):
        """Test successful EKS cluster enrichment."""
        resource = {
            'service': 'EKS',
            'type': 'Cluster',
            'id': 'test-cluster'
        }
        
        mock_cluster = {
            'version': '1.28',
            'endpoint': 'https://test-cluster.eks.us-east-1.amazonaws.com',
            'roleArn': 'arn:aws:iam::123456789012:role/eks-service-role',
            'resourcesVpcConfig': {
                'subnetIds': ['subnet-12345678', 'subnet-87654321'],
                'securityGroupIds': ['sg-12345678']
            },
            'kubernetesNetworkConfig': {'serviceIpv4Cidr': '10.100.0.0/16'},
            'logging': {'clusterLogging': [{'types': ['api'], 'enabled': True}]},
            'identity': {'oidc': {'issuer': 'https://oidc.eks.us-east-1.amazonaws.com/id/test'}},
            'status': 'ACTIVE',
            'certificateAuthority': {'data': 'LS0tLS1CRUdJTi...'},
            'clientRequestToken': 'test-token',
            'platformVersion': 'eks.1',
            'encryptionConfig': [],
            'connectorConfig': {},
            'id': 'test-cluster-id',
            'health': {'issues': []},
            'outpostConfig': {},
            'accessConfig': {'authenticationMode': 'API_AND_CONFIG_MAP'},
            'upgradePolicy': {'supportType': 'STANDARD'},
            'zonalShiftConfig': {},
            'storageConfig': {}
        }
        
        with patch.object(self.handler, '_safe_api_call') as mock_safe_call:
            mock_safe_call.return_value = {'cluster': mock_cluster}
            
            result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert attributes['version'] == '1.28'
        assert attributes['status'] == 'ACTIVE'
        assert 'test-cluster.eks.us-east-1.amazonaws.com' in attributes['endpoint']
        assert attributes['platform_version'] == 'eks.1'
    
    def test_enrich_eks_nodegroup_success(self):
        """Test successful EKS nodegroup enrichment."""
        resource = {
            'service': 'EKS',
            'type': 'Nodegroup',
            'id': 'test-nodegroup',
            'cluster': 'test-cluster'
        }
        
        mock_nodegroup = {
            'clusterName': 'test-cluster',
            'version': '1.28',
            'releaseVersion': '1.28.3-20231016',
            'status': 'ACTIVE',
            'capacityType': 'ON_DEMAND',
            'scalingConfig': {'minSize': 1, 'maxSize': 3, 'desiredSize': 2},
            'instanceTypes': ['t3.medium'],
            'subnets': ['subnet-12345678', 'subnet-87654321'],
            'remoteAccess': {'ec2SshKey': 'my-key-pair'},
            'amiType': 'AL2_x86_64',
            'nodeRole': 'arn:aws:iam::123456789012:role/NodeInstanceRole',
            'labels': {'environment': 'test'},
            'taints': [],
            'resources': {'autoScalingGroups': [{'name': 'eks-test-nodegroup-asg'}]},
            'diskSize': 20,
            'health': {'issues': []},
            'updateConfig': {'maxUnavailable': 1},
            'launchTemplate': {'name': 'test-launch-template', 'version': '1'}
        }
        
        with patch.object(self.handler, '_safe_api_call') as mock_safe_call:
            mock_safe_call.return_value = {'nodegroup': mock_nodegroup}
            
            result = self.handler.enrich_resource(resource)
        
        # Verify enrichment
        assert 'service_attributes' in result
        attributes = result['service_attributes']
        
        assert attributes['cluster_name'] == 'test-cluster'
        assert attributes['version'] == '1.28'
        assert attributes['status'] == 'ACTIVE'
        assert attributes['capacity_type'] == 'ON_DEMAND'
        assert attributes['instance_types'] == ['t3.medium']
        assert attributes['disk_size'] == 20


if __name__ == '__main__':
    pytest.main([__file__])