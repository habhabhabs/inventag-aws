#!/usr/bin/env python3
"""
Specific AWS Service Handlers

Implements service-specific handlers for major AWS services with comprehensive
attribute enrichment capabilities.
"""

import boto3
import logging
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
from .service_enrichment import ServiceHandler


class S3Handler(ServiceHandler):
    """Handler for Amazon S3 service with comprehensive bucket attribute enrichment."""
    
    def can_handle(self, service: str, resource_type: str) -> bool:
        """Handle S3 service resources."""
        return service.upper() == 'S3'
    
    def _define_read_only_operations(self) -> List[str]:
        """Define S3 read-only operations."""
        return [
            'get_bucket_encryption',
            'get_bucket_versioning',
            'get_bucket_location',
            'get_bucket_tagging',
            'get_public_access_block',
            'get_bucket_lifecycle_configuration',
            'get_bucket_policy',
            'get_bucket_acl',
            'get_bucket_cors',
            'get_bucket_website',
            'get_bucket_notification_configuration',
            'get_bucket_replication',
            'get_bucket_request_payment',
            'get_bucket_logging',
            'get_object_lock_configuration',
            'get_bucket_inventory_configuration',
            'get_bucket_metrics_configuration',
            'get_bucket_analytics_configuration'
        ]
    
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich S3 resources with bucket-specific attributes."""
        if resource.get('type') != 'Bucket':
            return resource
            
        bucket_name = resource.get('id', '')
        if not bucket_name:
            return resource
            
        try:
            s3_client = self.session.client('s3')
            attributes = {}
            
            # Get bucket encryption
            encryption_response = self._safe_api_call(
                s3_client, 'get_bucket_encryption', Bucket=bucket_name
            )
            if encryption_response:
                attributes['encryption'] = encryption_response.get('ServerSideEncryptionConfiguration', {})
            else:
                attributes['encryption'] = None
                
            # Get versioning status
            versioning_response = self._safe_api_call(
                s3_client, 'get_bucket_versioning', Bucket=bucket_name
            )
            if versioning_response:
                attributes['versioning_status'] = versioning_response.get('Status', 'Disabled')
            else:
                attributes['versioning_status'] = 'Unknown'
                
            # Get bucket location
            location_response = self._safe_api_call(
                s3_client, 'get_bucket_location', Bucket=bucket_name
            )
            if location_response:
                attributes['location'] = location_response.get('LocationConstraint') or 'us-east-1'
            else:
                attributes['location'] = 'Unknown'
                
            # Get lifecycle configuration
            lifecycle_response = self._safe_api_call(
                s3_client, 'get_bucket_lifecycle_configuration', Bucket=bucket_name
            )
            if lifecycle_response:
                attributes['lifecycle_rules'] = lifecycle_response.get('Rules', [])
            else:
                attributes['lifecycle_rules'] = []
                
            # Get public access block
            public_access_response = self._safe_api_call(
                s3_client, 'get_public_access_block', Bucket=bucket_name
            )
            if public_access_response:
                attributes['public_access_block'] = public_access_response.get('PublicAccessBlockConfiguration', {})
            else:
                attributes['public_access_block'] = {}
                
            # Get object lock configuration
            object_lock_response = self._safe_api_call(
                s3_client, 'get_object_lock_configuration', Bucket=bucket_name
            )
            if object_lock_response:
                attributes['object_lock'] = object_lock_response.get('ObjectLockConfiguration', {})
            else:
                attributes['object_lock'] = None
                
            return {**resource, 'service_attributes': attributes}
            
        except Exception as e:
            self.logger.warning(f"Failed to enrich S3 bucket {bucket_name}: {e}")
            return resource


class RDSHandler(ServiceHandler):
    """Handler for Amazon RDS service with database configuration enrichment."""
    
    def can_handle(self, service: str, resource_type: str) -> bool:
        """Handle RDS service resources."""
        return service.upper() == 'RDS'
    
    def _define_read_only_operations(self) -> List[str]:
        """Define RDS read-only operations."""
        return [
            'describe_db_instances',
            'describe_db_clusters',
            'describe_db_snapshots',
            'describe_db_cluster_snapshots',
            'describe_db_parameter_groups',
            'describe_db_cluster_parameter_groups',
            'describe_db_subnet_groups',
            'describe_option_groups',
            'describe_db_security_groups',
            'describe_db_cluster_endpoints',
            'describe_db_proxy',
            'describe_db_proxy_targets'
        ]
    
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich RDS resources with database-specific attributes."""
        resource_type = resource.get('type', '')
        resource_id = resource.get('id', '')
        
        if not resource_id:
            return resource
            
        try:
            rds_client = self.session.client('rds')
            attributes = {}
            
            if resource_type == 'DBInstance':
                # Get DB instance details
                response = self._safe_api_call(
                    rds_client, 'describe_db_instances', DBInstanceIdentifier=resource_id
                )
                if response and 'DBInstances' in response:
                    db_instance = response['DBInstances'][0]
                    attributes.update({
                        'engine': db_instance.get('Engine'),
                        'engine_version': db_instance.get('EngineVersion'),
                        'db_instance_class': db_instance.get('DBInstanceClass'),
                        'allocated_storage': db_instance.get('AllocatedStorage'),
                        'storage_type': db_instance.get('StorageType'),
                        'storage_encrypted': db_instance.get('StorageEncrypted'),
                        'kms_key_id': db_instance.get('KmsKeyId'),
                        'multi_az': db_instance.get('MultiAZ'),
                        'publicly_accessible': db_instance.get('PubliclyAccessible'),
                        'backup_retention_period': db_instance.get('BackupRetentionPeriod'),
                        'preferred_backup_window': db_instance.get('PreferredBackupWindow'),
                        'preferred_maintenance_window': db_instance.get('PreferredMaintenanceWindow'),
                        'vpc_security_groups': [sg['VpcSecurityGroupId'] for sg in db_instance.get('VpcSecurityGroups', [])],
                        'db_subnet_group': db_instance.get('DBSubnetGroup', {}).get('DBSubnetGroupName'),
                        'parameter_groups': [pg['DBParameterGroupName'] for pg in db_instance.get('DBParameterGroups', [])],
                        'option_group_memberships': [og['OptionGroupName'] for og in db_instance.get('OptionGroupMemberships', [])],
                        'deletion_protection': db_instance.get('DeletionProtection'),
                        'performance_insights_enabled': db_instance.get('PerformanceInsightsEnabled'),
                        'monitoring_interval': db_instance.get('MonitoringInterval'),
                        'enhanced_monitoring_resource_arn': db_instance.get('EnhancedMonitoringResourceArn')
                    })
                    
            elif resource_type == 'DBCluster':
                # Get DB cluster details
                response = self._safe_api_call(
                    rds_client, 'describe_db_clusters', DBClusterIdentifier=resource_id
                )
                if response and 'DBClusters' in response:
                    db_cluster = response['DBClusters'][0]
                    attributes.update({
                        'engine': db_cluster.get('Engine'),
                        'engine_version': db_cluster.get('EngineVersion'),
                        'engine_mode': db_cluster.get('EngineMode'),
                        'storage_encrypted': db_cluster.get('StorageEncrypted'),
                        'kms_key_id': db_cluster.get('KmsKeyId'),
                        'backup_retention_period': db_cluster.get('BackupRetentionPeriod'),
                        'preferred_backup_window': db_cluster.get('PreferredBackupWindow'),
                        'preferred_maintenance_window': db_cluster.get('PreferredMaintenanceWindow'),
                        'vpc_security_groups': [sg['VpcSecurityGroupId'] for sg in db_cluster.get('VpcSecurityGroups', [])],
                        'db_subnet_group': db_cluster.get('DBSubnetGroup'),
                        'db_cluster_parameter_group': db_cluster.get('DBClusterParameterGroup'),
                        'deletion_protection': db_cluster.get('DeletionProtection'),
                        'multi_az': db_cluster.get('MultiAZ'),
                        'cluster_members': [member['DBInstanceIdentifier'] for member in db_cluster.get('DBClusterMembers', [])],
                        'global_write_forwarding_status': db_cluster.get('GlobalWriteForwardingStatus'),
                        'cross_account_clone': db_cluster.get('CrossAccountClone'),
                        'capacity': db_cluster.get('Capacity'),
                        'scaling_configuration_info': db_cluster.get('ScalingConfigurationInfo', {})
                    })
                    
            return {**resource, 'service_attributes': attributes}
            
        except Exception as e:
            self.logger.warning(f"Failed to enrich RDS resource {resource_id}: {e}")
            return resource


class EC2Handler(ServiceHandler):
    """Handler for Amazon EC2 service with instance and volume enrichment."""
    
    def can_handle(self, service: str, resource_type: str) -> bool:
        """Handle EC2 service resources."""
        return service.upper() == 'EC2'
    
    def _define_read_only_operations(self) -> List[str]:
        """Define EC2 read-only operations."""
        return [
            'describe_instances',
            'describe_volumes',
            'describe_snapshots',
            'describe_images',
            'describe_security_groups',
            'describe_key_pairs',
            'describe_network_interfaces',
            'describe_subnets',
            'describe_vpcs',
            'describe_internet_gateways',
            'describe_route_tables',
            'describe_network_acls',
            'describe_vpc_endpoints',
            'describe_nat_gateways',
            'describe_elastic_ips',
            'describe_placement_groups',
            'describe_launch_templates',
            'describe_instance_types'
        ]
    
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich EC2 resources with instance and volume specific attributes."""
        resource_type = resource.get('type', '')
        resource_id = resource.get('id', '')
        
        if not resource_id:
            return resource
            
        try:
            ec2_client = self.session.client('ec2')
            attributes = {}
            
            if resource_type == 'Instance':
                # Get instance details
                response = self._safe_api_call(
                    ec2_client, 'describe_instances', InstanceIds=[resource_id]
                )
                if response and 'Reservations' in response:
                    for reservation in response['Reservations']:
                        for instance in reservation.get('Instances', []):
                            if instance['InstanceId'] == resource_id:
                                attributes.update({
                                    'instance_type': instance.get('InstanceType'),
                                    'state': instance.get('State', {}).get('Name'),
                                    'platform': instance.get('Platform'),
                                    'architecture': instance.get('Architecture'),
                                    'hypervisor': instance.get('Hypervisor'),
                                    'virtualization_type': instance.get('VirtualizationType'),
                                    'ami_id': instance.get('ImageId'),
                                    'key_name': instance.get('KeyName'),
                                    'launch_time': instance.get('LaunchTime'),
                                    'availability_zone': instance.get('Placement', {}).get('AvailabilityZone'),
                                    'tenancy': instance.get('Placement', {}).get('Tenancy'),
                                    'host_id': instance.get('Placement', {}).get('HostId'),
                                    'subnet_id': instance.get('SubnetId'),
                                    'vpc_id': instance.get('VpcId'),
                                    'private_ip_address': instance.get('PrivateIpAddress'),
                                    'public_ip_address': instance.get('PublicIpAddress'),
                                    'private_dns_name': instance.get('PrivateDnsName'),
                                    'public_dns_name': instance.get('PublicDnsName'),
                                    'security_groups': [sg['GroupId'] for sg in instance.get('SecurityGroups', [])],
                                    'iam_instance_profile': instance.get('IamInstanceProfile', {}).get('Arn'),
                                    'monitoring_state': instance.get('Monitoring', {}).get('State'),
                                    'source_dest_check': instance.get('SourceDestCheck'),
                                    'ebs_optimized': instance.get('EbsOptimized'),
                                    'sriov_net_support': instance.get('SriovNetSupport'),
                                    'ena_support': instance.get('EnaSupport'),
                                    'root_device_type': instance.get('RootDeviceType'),
                                    'root_device_name': instance.get('RootDeviceName'),
                                    'block_device_mappings': instance.get('BlockDeviceMappings', []),
                                    'network_interfaces': [ni['NetworkInterfaceId'] for ni in instance.get('NetworkInterfaces', [])],
                                    'cpu_options': instance.get('CpuOptions', {}),
                                    'capacity_reservation_specification': instance.get('CapacityReservationSpecification', {}),
                                    'hibernation_options': instance.get('HibernationOptions', {}),
                                    'metadata_options': instance.get('MetadataOptions', {}),
                                    'enclave_options': instance.get('EnclaveOptions', {})
                                })
                                break
                                
            elif resource_type == 'Volume':
                # Get volume details
                response = self._safe_api_call(
                    ec2_client, 'describe_volumes', VolumeIds=[resource_id]
                )
                if response and 'Volumes' in response:
                    volume = response['Volumes'][0]
                    attributes.update({
                        'size': volume.get('Size'),
                        'volume_type': volume.get('VolumeType'),
                        'iops': volume.get('Iops'),
                        'throughput': volume.get('Throughput'),
                        'state': volume.get('State'),
                        'encrypted': volume.get('Encrypted'),
                        'kms_key_id': volume.get('KmsKeyId'),
                        'snapshot_id': volume.get('SnapshotId'),
                        'availability_zone': volume.get('AvailabilityZone'),
                        'create_time': volume.get('CreateTime'),
                        'attachments': volume.get('Attachments', []),
                        'multi_attach_enabled': volume.get('MultiAttachEnabled'),
                        'fast_restored': volume.get('FastRestored'),
                        'outpost_arn': volume.get('OutpostArn')
                    })
                    
            return {**resource, 'service_attributes': attributes}
            
        except Exception as e:
            self.logger.warning(f"Failed to enrich EC2 resource {resource_id}: {e}")
            return resource


class LambdaHandler(ServiceHandler):
    """Handler for AWS Lambda service with function configuration enrichment."""
    
    def can_handle(self, service: str, resource_type: str) -> bool:
        """Handle Lambda service resources."""
        return service.upper() == 'LAMBDA'
    
    def _define_read_only_operations(self) -> List[str]:
        """Define Lambda read-only operations."""
        return [
            'get_function',
            'get_function_configuration',
            'get_function_code_signing_config',
            'get_function_concurrency',
            'get_function_event_invoke_config',
            'list_aliases',
            'list_versions_by_function',
            'list_layers',
            'list_layer_versions',
            'get_layer_version',
            'get_policy',
            'list_tags'
        ]
    
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich Lambda resources with function-specific attributes."""
        resource_type = resource.get('type', '')
        resource_id = resource.get('id', '')
        
        if not resource_id or resource_type != 'Function':
            return resource
            
        try:
            lambda_client = self.session.client('lambda')
            attributes = {}
            
            # Get function configuration
            response = self._safe_api_call(
                lambda_client, 'get_function', FunctionName=resource_id
            )
            if response:
                config = response.get('Configuration', {})
                code = response.get('Code', {})
                
                attributes.update({
                    'runtime': config.get('Runtime'),
                    'role': config.get('Role'),
                    'handler': config.get('Handler'),
                    'code_size': config.get('CodeSize'),
                    'description': config.get('Description'),
                    'timeout': config.get('Timeout'),
                    'memory_size': config.get('MemorySize'),
                    'last_modified': config.get('LastModified'),
                    'code_sha256': config.get('CodeSha256'),
                    'version': config.get('Version'),
                    'vpc_config': config.get('VpcConfig', {}),
                    'environment': config.get('Environment', {}),
                    'dead_letter_config': config.get('DeadLetterConfig', {}),
                    'kms_key_arn': config.get('KMSKeyArn'),
                    'tracing_config': config.get('TracingConfig', {}),
                    'master_arn': config.get('MasterArn'),
                    'revision_id': config.get('RevisionId'),
                    'layers': config.get('Layers', []),
                    'state': config.get('State'),
                    'state_reason': config.get('StateReason'),
                    'state_reason_code': config.get('StateReasonCode'),
                    'last_update_status': config.get('LastUpdateStatus'),
                    'last_update_status_reason': config.get('LastUpdateStatusReason'),
                    'last_update_status_reason_code': config.get('LastUpdateStatusReasonCode'),
                    'file_system_configs': config.get('FileSystemConfigs', []),
                    'package_type': config.get('PackageType'),
                    'image_config_response': config.get('ImageConfigResponse', {}),
                    'signing_profile_version_arn': config.get('SigningProfileVersionArn'),
                    'signing_job_arn': config.get('SigningJobArn'),
                    'architectures': config.get('Architectures', []),
                    'ephemeral_storage': config.get('EphemeralStorage', {}),
                    'snap_start': config.get('SnapStart', {}),
                    'runtime_version_config': config.get('RuntimeVersionConfig', {}),
                    'logging_config': config.get('LoggingConfig', {}),
                    'code_repository_type': code.get('RepositoryType'),
                    'code_location': code.get('Location'),
                    'code_image_uri': code.get('ImageUri'),
                    'code_resolved_image_uri': code.get('ResolvedImageUri')
                })
                
            # Get function concurrency
            concurrency_response = self._safe_api_call(
                lambda_client, 'get_function_concurrency', FunctionName=resource_id
            )
            if concurrency_response:
                attributes['reserved_concurrency_executions'] = concurrency_response.get('ReservedConcurrencyExecutions')
                
            return {**resource, 'service_attributes': attributes}
            
        except Exception as e:
            self.logger.warning(f"Failed to enrich Lambda function {resource_id}: {e}")
            return resource


class ECSHandler(ServiceHandler):
    """Handler for Amazon ECS service with cluster and service enrichment."""
    
    def can_handle(self, service: str, resource_type: str) -> bool:
        """Handle ECS service resources."""
        return service.upper() == 'ECS'
    
    def _define_read_only_operations(self) -> List[str]:
        """Define ECS read-only operations."""
        return [
            'describe_clusters',
            'describe_services',
            'describe_tasks',
            'describe_task_definition',
            'describe_container_instances',
            'describe_capacity_providers',
            'list_services',
            'list_tasks',
            'list_task_definitions',
            'list_container_instances',
            'list_attributes',
            'list_tags_for_resource'
        ]
    
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich ECS resources with cluster and service specific attributes."""
        resource_type = resource.get('type', '')
        resource_id = resource.get('id', '')
        
        if not resource_id:
            return resource
            
        try:
            ecs_client = self.session.client('ecs')
            attributes = {}
            
            if resource_type == 'Cluster':
                # Get cluster details
                response = self._safe_api_call(
                    ecs_client, 'describe_clusters', clusters=[resource_id]
                )
                if response and 'clusters' in response:
                    cluster = response['clusters'][0]
                    attributes.update({
                        'status': cluster.get('status'),
                        'running_tasks_count': cluster.get('runningTasksCount'),
                        'pending_tasks_count': cluster.get('pendingTasksCount'),
                        'active_services_count': cluster.get('activeServicesCount'),
                        'statistics': cluster.get('statistics', []),
                        'capacity_providers': cluster.get('capacityProviders', []),
                        'default_capacity_provider_strategy': cluster.get('defaultCapacityProviderStrategy', []),
                        'attachments': cluster.get('attachments', []),
                        'settings': cluster.get('settings', []),
                        'configuration': cluster.get('configuration', {}),
                        'service_connect_defaults': cluster.get('serviceConnectDefaults', {})
                    })
                    
            elif resource_type == 'Service':
                # For services, we need cluster name as well
                cluster_name = resource.get('cluster', 'default')
                response = self._safe_api_call(
                    ecs_client, 'describe_services', 
                    cluster=cluster_name, services=[resource_id]
                )
                if response and 'services' in response:
                    service = response['services'][0]
                    attributes.update({
                        'cluster_arn': service.get('clusterArn'),
                        'task_definition': service.get('taskDefinition'),
                        'desired_count': service.get('desiredCount'),
                        'running_count': service.get('runningCount'),
                        'pending_count': service.get('pendingCount'),
                        'launch_type': service.get('launchType'),
                        'capacity_provider_strategy': service.get('capacityProviderStrategy', []),
                        'platform_version': service.get('platformVersion'),
                        'platform_family': service.get('platformFamily'),
                        'role_arn': service.get('roleArn'),
                        'deployment_configuration': service.get('deploymentConfiguration', {}),
                        'deployments': service.get('deployments', []),
                        'load_balancers': service.get('loadBalancers', []),
                        'service_registries': service.get('serviceRegistries', []),
                        'status': service.get('status'),
                        'health_check_grace_period_seconds': service.get('healthCheckGracePeriodSeconds'),
                        'scheduling_strategy': service.get('schedulingStrategy'),
                        'deployment_controller': service.get('deploymentController', {}),
                        'network_configuration': service.get('networkConfiguration', {}),
                        'service_connect_configuration': service.get('serviceConnectConfiguration', {}),
                        'volume_configurations': service.get('volumeConfigurations', [])
                    })
                    
            return {**resource, 'service_attributes': attributes}
            
        except Exception as e:
            self.logger.warning(f"Failed to enrich ECS resource {resource_id}: {e}")
            return resource


class EKSHandler(ServiceHandler):
    """Handler for Amazon EKS service with cluster and node group enrichment."""
    
    def can_handle(self, service: str, resource_type: str) -> bool:
        """Handle EKS service resources."""
        return service.upper() == 'EKS'
    
    def _define_read_only_operations(self) -> List[str]:
        """Define EKS read-only operations."""
        return [
            'describe_cluster',
            'describe_nodegroup',
            'describe_fargate_profile',
            'describe_addon',
            'describe_identity_provider_config',
            'describe_update',
            'list_clusters',
            'list_nodegroups',
            'list_fargate_profiles',
            'list_addons',
            'list_identity_provider_configs',
            'list_updates',
            'list_tags_for_resource'
        ]
    
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich EKS resources with cluster and node group specific attributes."""
        resource_type = resource.get('type', '')
        resource_id = resource.get('id', '')
        
        if not resource_id:
            return resource
            
        try:
            eks_client = self.session.client('eks')
            attributes = {}
            
            if resource_type == 'Cluster':
                # Get cluster details
                response = self._safe_api_call(
                    eks_client, 'describe_cluster', name=resource_id
                )
                if response and 'cluster' in response:
                    cluster = response['cluster']
                    attributes.update({
                        'version': cluster.get('version'),
                        'endpoint': cluster.get('endpoint'),
                        'role_arn': cluster.get('roleArn'),
                        'resources_vpc_config': cluster.get('resourcesVpcConfig', {}),
                        'kubernetes_network_config': cluster.get('kubernetesNetworkConfig', {}),
                        'logging': cluster.get('logging', {}),
                        'identity': cluster.get('identity', {}),
                        'status': cluster.get('status'),
                        'certificate_authority': cluster.get('certificateAuthority', {}),
                        'client_request_token': cluster.get('clientRequestToken'),
                        'platform_version': cluster.get('platformVersion'),
                        'encryption_config': cluster.get('encryptionConfig', []),
                        'connector_config': cluster.get('connectorConfig', {}),
                        'id': cluster.get('id'),
                        'health': cluster.get('health', {}),
                        'outpost_config': cluster.get('outpostConfig', {}),
                        'access_config': cluster.get('accessConfig', {}),
                        'upgrade_policy': cluster.get('upgradePolicy', {}),
                        'zonal_shift_config': cluster.get('zonalShiftConfig', {}),
                        'storage_config': cluster.get('storageConfig', {})
                    })
                    
            elif resource_type == 'Nodegroup':
                # For node groups, we need cluster name as well
                cluster_name = resource.get('cluster', '')
                if cluster_name:
                    response = self._safe_api_call(
                        eks_client, 'describe_nodegroup',
                        clusterName=cluster_name, nodegroupName=resource_id
                    )
                    if response and 'nodegroup' in response:
                        nodegroup = response['nodegroup']
                        attributes.update({
                            'cluster_name': nodegroup.get('clusterName'),
                            'version': nodegroup.get('version'),
                            'release_version': nodegroup.get('releaseVersion'),
                            'status': nodegroup.get('status'),
                            'capacity_type': nodegroup.get('capacityType'),
                            'scaling_config': nodegroup.get('scalingConfig', {}),
                            'instance_types': nodegroup.get('instanceTypes', []),
                            'subnets': nodegroup.get('subnets', []),
                            'remote_access': nodegroup.get('remoteAccess', {}),
                            'ami_type': nodegroup.get('amiType'),
                            'node_role': nodegroup.get('nodeRole'),
                            'labels': nodegroup.get('labels', {}),
                            'taints': nodegroup.get('taints', []),
                            'resources': nodegroup.get('resources', {}),
                            'disk_size': nodegroup.get('diskSize'),
                            'health': nodegroup.get('health', {}),
                            'update_config': nodegroup.get('updateConfig', {}),
                            'launch_template': nodegroup.get('launchTemplate', {})
                        })
                        
            return {**resource, 'service_attributes': attributes}
            
        except Exception as e:
            self.logger.warning(f"Failed to enrich EKS resource {resource_id}: {e}")
            return resource