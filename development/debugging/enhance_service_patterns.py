#!/usr/bin/env python3
"""
Enhanced service patterns for additional AWS services
Extends the optimized discovery system with more comprehensive service coverage
"""

import sys
import os

# Add the inventag package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from inventag.discovery.optimized_discovery import OptimizedFieldMapper


class EnhancedServicePatterns:
    """Enhanced patterns for additional AWS services"""

    @staticmethod
    def get_enhanced_service_patterns():
        """Get enhanced service-specific patterns for more AWS services"""
        return {
            # Existing services (from optimized_discovery.py)
            "cloudfront": {
                "resource_id_patterns": [
                    r"Id['\"]:\s*['\"]([A-Z0-9]+)['\"]",
                    r"['\"]Id['\"]:\s*['\"]([A-Z0-9]+)['\"]",
                    r"distribution['\"]:\s*['\"]([A-Z0-9]+)['\"]",
                ],
                "resource_type": "Distribution",
                "confidence_boost": 0.2,
            },
            # Enhanced ECS patterns
            "ecs": {
                "resource_id_patterns": [
                    r"clusterArn['\"]:\s*['\"]arn:aws:ecs:[^:]+:[^:]+:cluster/([^'\"]+)['\"]",
                    r"clusterName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"serviceName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"taskDefinitionArn['\"]:\s*['\"]arn:aws:ecs:[^:]+:[^:]+:task-definition/([^:]+)",
                    r"containerInstanceArn['\"]:\s*['\"]arn:aws:ecs:[^:]+:[^:]+:container-instance/([^'\"]+)['\"]",
                ],
                "resource_types": {
                    "list_clusters": "Cluster",
                    "list_services": "Service",
                    "list_task_definitions": "TaskDefinition",
                    "list_container_instances": "ContainerInstance",
                },
                "confidence_boost": 0.15,
            },
            # Enhanced EKS patterns
            "eks": {
                "resource_id_patterns": [
                    r"name['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"clusterName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"nodegroupName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"fargateProfileName['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {
                    "list_clusters": "Cluster",
                    "list_nodegroups": "NodeGroup",
                    "list_fargate_profiles": "FargateProfile",
                    "list_addons": "Addon",
                },
                "confidence_boost": 0.15,
            },
            # Enhanced ElastiCache patterns
            "elasticache": {
                "resource_id_patterns": [
                    r"CacheClusterId['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"ReplicationGroupId['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"CacheSubnetGroupName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"CacheParameterGroupName['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {
                    "describe_cache_clusters": "CacheCluster",
                    "describe_replication_groups": "ReplicationGroup",
                    "describe_cache_subnet_groups": "CacheSubnetGroup",
                    "describe_cache_parameter_groups": "CacheParameterGroup",
                },
                "confidence_boost": 0.15,
            },
            # Enhanced SNS patterns
            "sns": {
                "resource_id_patterns": [
                    r"TopicArn['\"]:\s*['\"]arn:aws:sns:[^:]+:[^:]+:([^'\"]+)['\"]",
                    r"SubscriptionArn['\"]:\s*['\"]arn:aws:sns:[^:]+:[^:]+:[^:]+:([^'\"]+)['\"]",
                    r"Name['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {
                    "list_topics": "Topic",
                    "list_subscriptions": "Subscription",
                    "list_platform_applications": "PlatformApplication",
                },
                "confidence_boost": 0.15,
            },
            # Enhanced SQS patterns
            "sqs": {
                "resource_id_patterns": [
                    r"QueueUrl['\"]:\s*['\"]https://sqs\.[^/]+/[^/]+/([^'\"]+)['\"]",
                    r"QueueName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"/([^/]+)$",  # Extract queue name from URL
                ],
                "resource_types": {"list_queues": "Queue"},
                "confidence_boost": 0.15,
            },
            # Enhanced DynamoDB patterns
            "dynamodb": {
                "resource_id_patterns": [
                    r"TableName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"IndexName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"BackupName['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {
                    "list_tables": "Table",
                    "list_backups": "Backup",
                    "list_global_tables": "GlobalTable",
                },
                "confidence_boost": 0.15,
            },
            # Enhanced API Gateway patterns
            "apigateway": {
                "resource_id_patterns": [
                    r"id['\"]:\s*['\"]([a-z0-9]+)['\"]",
                    r"restApiId['\"]:\s*['\"]([a-z0-9]+)['\"]",
                    r"name['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"domainName['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {
                    "get_rest_apis": "RestApi",
                    "get_domain_names": "DomainName",
                    "get_api_keys": "ApiKey",
                    "get_usage_plans": "UsagePlan",
                },
                "confidence_boost": 0.15,
            },
            # Enhanced CloudFormation patterns
            "cloudformation": {
                "resource_id_patterns": [
                    r"StackName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"StackId['\"]:\s*['\"]arn:aws:cloudformation:[^:]+:[^:]+:stack/([^/]+)",
                    r"ChangeSetName['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {
                    "list_stacks": "Stack",
                    "list_stack_sets": "StackSet",
                    "list_change_sets": "ChangeSet",
                },
                "confidence_boost": 0.15,
            },
            # Enhanced CodePipeline patterns
            "codepipeline": {
                "resource_id_patterns": [
                    r"name['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"pipelineName['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {"list_pipelines": "Pipeline"},
                "confidence_boost": 0.15,
            },
            # Enhanced CodeBuild patterns
            "codebuild": {
                "resource_id_patterns": [
                    r"name['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"projectName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"buildId['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {"list_projects": "Project", "list_builds": "Build"},
                "confidence_boost": 0.15,
            },
            # Enhanced Secrets Manager patterns
            "secretsmanager": {
                "resource_id_patterns": [
                    r"Name['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"ARN['\"]:\s*['\"]arn:aws:secretsmanager:[^:]+:[^:]+:secret:([^-]+)",
                    r"SecretId['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {"list_secrets": "Secret"},
                "confidence_boost": 0.15,
            },
            # Enhanced Systems Manager patterns
            "ssm": {
                "resource_id_patterns": [
                    r"Name['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"ParameterName['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"DocumentName['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {
                    "describe_parameters": "Parameter",
                    "list_documents": "Document",
                    "describe_patch_baselines": "PatchBaseline",
                },
                "confidence_boost": 0.15,
            },
            # Enhanced KMS patterns
            "kms": {
                "resource_id_patterns": [
                    r"KeyId['\"]:\s*['\"]([a-f0-9-]+)['\"]",
                    r"AliasName['\"]:\s*['\"]alias/([^'\"]+)['\"]",
                    r"Arn['\"]:\s*['\"]arn:aws:kms:[^:]+:[^:]+:key/([a-f0-9-]+)['\"]",
                ],
                "resource_types": {"list_keys": "Key", "list_aliases": "Alias"},
                "confidence_boost": 0.15,
            },
            # Enhanced ACM patterns
            "acm": {
                "resource_id_patterns": [
                    r"CertificateArn['\"]:\s*['\"]arn:aws:acm:[^:]+:[^:]+:certificate/([a-f0-9-]+)['\"]",
                    r"DomainName['\"]:\s*['\"]([^'\"]+)['\"]",
                ],
                "resource_types": {"list_certificates": "Certificate"},
                "confidence_boost": 0.15,
            },
            # Enhanced WAF patterns
            "wafv2": {
                "resource_id_patterns": [
                    r"Name['\"]:\s*['\"]([^'\"]+)['\"]",
                    r"Id['\"]:\s*['\"]([a-f0-9-]+)['\"]",
                    r"ARN['\"]:\s*['\"]arn:aws:wafv2:[^:]+:[^:]+:[^/]+/([^/]+)",
                ],
                "resource_types": {
                    "list_web_acls": "WebACL",
                    "list_rule_groups": "RuleGroup",
                    "list_ip_sets": "IPSet",
                },
                "confidence_boost": 0.15,
            },
        }

    @staticmethod
    def get_enhanced_aws_managed_patterns():
        """Get enhanced AWS managed resource patterns"""
        return {
            # Existing patterns (from optimized_discovery.py)
            "iam": [
                r"^aws-service-role/",
                r"^AWSServiceRole",
                r"^service-role/",
                r"^OrganizationAccountAccessRole$",
                r"^AWSReservedSSO_",
                # Additional IAM patterns
                r"^AWS.*Role$",
                r"^AWS.*Policy$",
                r"^.*ServiceLinkedRole$",
                r"^AmazonSSMRoleForInstancesQuickSetup$",
                r"^EC2RoleForSSM$",
                r"^rds-monitoring-role$",
            ],
            "route53": {"exclude_resource_types": ["GeoLocation", "HealthCheck"]},
            "ec2": [
                r"^default$",  # Default VPC/security groups
                r"^default-.*$",  # Default subnets, route tables, etc.
                r"^.*\.amazonaws\.com$",  # AWS managed endpoints
            ],
            # New service patterns
            "ecs": [r"^default$", r"^ecs-optimized-.*$", r"^AWSServiceRoleForECS.*$"],
            "eks": [r"^eks-.*-cluster$", r"^AWSServiceRoleForAmazonEKS.*$"],
            "lambda": [r"^AWSLambda.*$", r"^lambda-.*-role$"],
            "rds": [r"^default$", r"^default\..*$", r"^rds-.*$"],
            "elasticache": [r"^default$", r"^default\..*$"],
            "cloudformation": [r"^aws-.*$", r"^AWSServiceRole.*$"],
            "kms": [r"^alias/aws/.*$", r"^aws/.*$"],  # AWS managed KMS keys
            "secretsmanager": [
                r"^aws/.*$",
                r"^rds-db-credentials/.*$",
            ],  # RDS managed secrets
        }

    @staticmethod
    def get_enhanced_ai_prediction_patterns():
        """Get enhanced AI prediction patterns for cross-service dependencies"""
        return {
            # Existing patterns
            "lambda_to_logs": {
                "source_service": "lambda",
                "target_service": "logs",
                "pattern": lambda resource: f"/aws/lambda/{resource.resource_id}",
                "resource_type": "LogGroup",
                "confidence": 0.7,
            },
            # New prediction patterns
            "ecs_to_logs": {
                "source_service": "ecs",
                "target_service": "logs",
                "pattern": lambda resource: (
                    f"/ecs/{resource.resource_id}"
                    if resource.resource_type == "Cluster"
                    else f"/aws/ecs/containerinsights/{resource.resource_id}"
                ),
                "resource_type": "LogGroup",
                "confidence": 0.6,
            },
            "eks_to_logs": {
                "source_service": "eks",
                "target_service": "logs",
                "pattern": lambda resource: f"/aws/eks/{resource.resource_id}/cluster",
                "resource_type": "LogGroup",
                "confidence": 0.6,
            },
            "apigateway_to_logs": {
                "source_service": "apigateway",
                "target_service": "logs",
                "pattern": lambda resource: f"API-Gateway-Execution-Logs_{resource.resource_id}/prod",
                "resource_type": "LogGroup",
                "confidence": 0.5,
            },
            "rds_to_logs": {
                "source_service": "rds",
                "target_service": "logs",
                "pattern": lambda resource: f"/aws/rds/instance/{resource.resource_id}/error",
                "resource_type": "LogGroup",
                "confidence": 0.4,
            },
            "codebuild_to_logs": {
                "source_service": "codebuild",
                "target_service": "logs",
                "pattern": lambda resource: f"/aws/codebuild/{resource.resource_id}",
                "resource_type": "LogGroup",
                "confidence": 0.6,
            },
            # CloudWatch alarms for resources
            "lambda_to_cloudwatch": {
                "source_service": "lambda",
                "target_service": "cloudwatch",
                "pattern": lambda resource: f"{resource.resource_id}-errors",
                "resource_type": "Alarm",
                "confidence": 0.4,
            },
            "rds_to_cloudwatch": {
                "source_service": "rds",
                "target_service": "cloudwatch",
                "pattern": lambda resource: f"{resource.resource_id}-cpu-utilization",
                "resource_type": "Alarm",
                "confidence": 0.4,
            },
            # SNS topics for alarms
            "cloudwatch_to_sns": {
                "source_service": "cloudwatch",
                "target_service": "sns",
                "pattern": lambda resource: f"alarm-notifications",
                "resource_type": "Topic",
                "confidence": 0.3,
            },
            # IAM roles for services
            "lambda_to_iam": {
                "source_service": "lambda",
                "target_service": "iam",
                "pattern": lambda resource: f"{resource.resource_id}-role",
                "resource_type": "Role",
                "confidence": 0.5,
            },
            "ecs_to_iam": {
                "source_service": "ecs",
                "target_service": "iam",
                "pattern": lambda resource: f"ecsTaskExecutionRole",
                "resource_type": "Role",
                "confidence": 0.4,
            },
            # Security groups for services
            "rds_to_ec2": {
                "source_service": "rds",
                "target_service": "ec2",
                "pattern": lambda resource: f"{resource.resource_id}-sg",
                "resource_type": "SecurityGroup",
                "confidence": 0.4,
            },
            "elasticache_to_ec2": {
                "source_service": "elasticache",
                "target_service": "ec2",
                "pattern": lambda resource: f"{resource.resource_id}-sg",
                "resource_type": "SecurityGroup",
                "confidence": 0.4,
            },
        }


def apply_enhanced_patterns():
    """Apply enhanced patterns to the optimized discovery system"""
    print("🚀 Applying Enhanced Service Patterns...")

    enhanced_patterns = EnhancedServicePatterns()

    # Read the current optimized discovery file
    optimized_file = "inventag/discovery/optimized_discovery.py"

    try:
        with open(optimized_file, "r") as f:
            content = f.read()

        # Find the service patterns section and enhance it
        service_patterns = enhanced_patterns.get_enhanced_service_patterns()
        aws_managed_patterns = enhanced_patterns.get_enhanced_aws_managed_patterns()
        ai_patterns = enhanced_patterns.get_enhanced_ai_prediction_patterns()

        print(f"✅ Enhanced patterns ready:")
        print(f"  📊 Service patterns: {len(service_patterns)} services")
        print(f"  🔒 AWS managed patterns: {len(aws_managed_patterns)} services")
        print(f"  🤖 AI prediction patterns: {len(ai_patterns)} patterns")

        # Create a backup
        backup_file = f"{optimized_file}.backup"
        with open(backup_file, "w") as f:
            f.write(content)
        print(f"  💾 Backup created: {backup_file}")

        return service_patterns, aws_managed_patterns, ai_patterns

    except Exception as e:
        print(f"❌ Error applying enhanced patterns: {e}")
        return None, None, None


if __name__ == "__main__":
    print("🔧 Enhanced Service Patterns for AWS Discovery")
    print("=" * 50)

    service_patterns, aws_managed_patterns, ai_patterns = apply_enhanced_patterns()

    if service_patterns:
        print("\n📋 Enhanced Service Coverage:")
        for service, config in service_patterns.items():
            resource_types = config.get("resource_types", {})
            if resource_types:
                print(f"  🎯 {service.upper()}: {len(resource_types)} resource types")
            else:
                print(f"  🎯 {service.upper()}: Enhanced patterns")

        print(f"\n🎉 Enhanced patterns ready for integration!")
        print("Next steps:")
        print("1. Review the patterns above")
        print("2. Run the integration script to apply them")
        print("3. Test with the comprehensive test suite")
