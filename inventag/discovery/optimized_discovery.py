#!/usr/bin/env python3
"""
Optimized AWS Resource Discovery System

Enhanced discovery system that addresses the issues found in the original intelligent discovery:
- Missing services (CloudFront, IAM, Route53, S3, Lambda)
- Poor performance and low confidence scores
- Inadequate field mapping and service-specific patterns

This module provides optimized discovery with:
- Service-specific extraction patterns
- Parallel processing for better performance
- Enhanced field mapping and confidence scoring
- Better resource name and type detection
"""

import re
import threading
import concurrent.futures
from typing import Dict, List, Any, Optional
from datetime import datetime
import boto3

# Import the base classes
from .intelligent_discovery import (
    StandardResource,
    IntelligentFieldMapper,
    IntelligentAWSDiscovery,
)


class OptimizedFieldMapper(IntelligentFieldMapper):
    """Optimized field mapper with enhanced service-specific patterns and AWS managed resource filtering."""

    def __init__(self):
        super().__init__()

        # Enhanced service-specific patterns based on debugging findings
        self.optimized_service_patterns = {
            "cloudfront": {
                "resource_types": ["Distribution"],
                "id_patterns": [r"E[A-Z0-9]+"],
                "operations": ["ListDistributions"],
                "name_fields": ["DomainName", "Id"],
                "region_dependent": False,
                "global_service": True,
                "exclude_aws_managed": True,
            },
            "iam": {
                "resource_types": ["Role", "User", "Policy", "Group"],
                "operations": ["ListRoles", "ListUsers", "ListPolicies", "ListGroups"],
                "name_fields": ["RoleName", "UserName", "PolicyName", "GroupName"],
                "region_dependent": False,
                "global_service": True,
                "exclude_aws_managed": True,
                "aws_managed_patterns": [
                    r"^aws-service-role/",
                    r"^AWSServiceRole",
                    r"^service-role/",
                    r"^OrganizationAccountAccessRole$",
                    r"^AWSReservedSSO_",
                    r"^StackSet-",
                    r"^CloudFormation-",
                ],
            },
            "route53": {
                "resource_types": ["HostedZone"],
                "id_patterns": [r"Z[0-9A-Z]+"],
                "operations": ["ListHostedZones"],
                "name_fields": ["Name", "Id"],
                "region_dependent": False,
                "global_service": True,
                "exclude_aws_managed": True,
                "exclude_resource_types": [
                    "GeoLocation"
                ],  # Exclude geolocation records
                "aws_managed_patterns": [
                    r".*\.amazonaws\.com\.$",  # AWS service domains
                    r".*\.aws\.amazon\.com\.$",  # AWS internal domains
                ],
            },
            "s3": {
                "resource_types": ["Bucket"],
                "operations": ["ListBuckets", "GetBucketLocation"],
                "name_fields": ["Name"],
                "region_dependent": False,
                "global_service": True,
                "exclude_aws_managed": True,
                "requires_region_detection": True,
            },
            "lambda": {
                "resource_types": ["Function"],
                "operations": ["ListFunctions"],
                "name_fields": ["FunctionName"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            "ec2": {
                "resource_types": [
                    "Instance",
                    "VPC",
                    "Subnet",
                    "SecurityGroup",
                    "InternetGateway",
                ],
                "operations": [
                    "DescribeInstances",
                    "DescribeVpcs",
                    "DescribeSubnets",
                    "DescribeSecurityGroups",
                ],
                "name_fields": ["InstanceId", "VpcId", "SubnetId", "GroupId"],
                "region_dependent": True,
                "exclude_aws_managed": True,
                "aws_managed_patterns": [
                    r"^default$",  # Default VPC/security groups
                ],
            },
            "rds": {
                "resource_types": ["DBInstance", "DBCluster"],
                "operations": ["DescribeDBInstances", "DescribeDBClusters"],
                "name_fields": ["DBInstanceIdentifier", "DBClusterIdentifier"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            # Enhanced ECS patterns
            "ecs": {
                "resource_types": [
                    "Cluster",
                    "Service",
                    "TaskDefinition",
                    "ContainerInstance",
                ],
                "operations": [
                    "ListClusters",
                    "ListServices",
                    "ListTaskDefinitions",
                    "ListContainerInstances",
                ],
                "name_fields": [
                    "clusterName",
                    "serviceName",
                    "taskDefinitionArn",
                    "containerInstanceArn",
                ],
                "region_dependent": True,
                "exclude_aws_managed": True,
                "aws_managed_patterns": [
                    r"^default$",
                    r"^ecs-optimized-.*$",
                    r"^AWSServiceRoleForECS.*$",
                ],
            },
            # Enhanced EKS patterns
            "eks": {
                "resource_types": ["Cluster", "NodeGroup", "FargateProfile", "Addon"],
                "operations": [
                    "ListClusters",
                    "ListNodegroups",
                    "ListFargateProfiles",
                    "ListAddons",
                ],
                "name_fields": [
                    "name",
                    "clusterName",
                    "nodegroupName",
                    "fargateProfileName",
                ],
                "region_dependent": True,
                "exclude_aws_managed": True,
                "aws_managed_patterns": [
                    r"^eks-.*-cluster$",
                    r"^AWSServiceRoleForAmazonEKS.*$",
                ],
            },
            # Enhanced ElastiCache patterns
            "elasticache": {
                "resource_types": [
                    "CacheCluster",
                    "ReplicationGroup",
                    "CacheSubnetGroup",
                    "CacheParameterGroup",
                ],
                "operations": [
                    "DescribeCacheClusters",
                    "DescribeReplicationGroups",
                    "DescribeCacheSubnetGroups",
                    "DescribeCacheParameterGroups",
                ],
                "name_fields": [
                    "CacheClusterId",
                    "ReplicationGroupId",
                    "CacheSubnetGroupName",
                    "CacheParameterGroupName",
                ],
                "region_dependent": True,
                "exclude_aws_managed": True,
                "aws_managed_patterns": [r"^default$", r"^default\..*$"],
            },
            # Enhanced SNS patterns
            "sns": {
                "resource_types": ["Topic", "Subscription", "PlatformApplication"],
                "operations": [
                    "ListTopics",
                    "ListSubscriptions",
                    "ListPlatformApplications",
                ],
                "name_fields": ["TopicArn", "SubscriptionArn", "Name"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            # Enhanced SQS patterns
            "sqs": {
                "resource_types": ["Queue"],
                "operations": ["ListQueues"],
                "name_fields": ["QueueUrl", "QueueName"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            # Enhanced DynamoDB patterns
            "dynamodb": {
                "resource_types": ["Table", "Backup", "GlobalTable"],
                "operations": ["ListTables", "ListBackups", "ListGlobalTables"],
                "name_fields": ["TableName", "BackupName", "GlobalTableName"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            # Enhanced API Gateway patterns
            "apigateway": {
                "resource_types": ["RestApi", "DomainName", "ApiKey", "UsagePlan"],
                "operations": [
                    "GetRestApis",
                    "GetDomainNames",
                    "GetApiKeys",
                    "GetUsagePlans",
                ],
                "name_fields": ["id", "restApiId", "name", "domainName"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            # Enhanced CloudFormation patterns
            "cloudformation": {
                "resource_types": ["Stack", "StackSet", "ChangeSet"],
                "operations": ["ListStacks", "ListStackSets", "ListChangeSets"],
                "name_fields": ["StackName", "StackSetName", "ChangeSetName"],
                "region_dependent": True,
                "exclude_aws_managed": True,
                "aws_managed_patterns": [r"^aws-.*$", r"^AWSServiceRole.*$"],
            },
            # Enhanced CodePipeline patterns
            "codepipeline": {
                "resource_types": ["Pipeline"],
                "operations": ["ListPipelines"],
                "name_fields": ["name", "pipelineName"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            # Enhanced CodeBuild patterns
            "codebuild": {
                "resource_types": ["Project", "Build"],
                "operations": ["ListProjects", "ListBuilds"],
                "name_fields": ["name", "projectName", "buildId"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            # Enhanced Secrets Manager patterns
            "secretsmanager": {
                "resource_types": ["Secret"],
                "operations": ["ListSecrets"],
                "name_fields": ["Name", "ARN", "SecretId"],
                "region_dependent": True,
                "exclude_aws_managed": True,
                "aws_managed_patterns": [
                    r"^aws/.*$",
                    r"^rds-db-credentials/.*$",  # RDS managed secrets
                ],
            },
            # Enhanced Systems Manager patterns
            "ssm": {
                "resource_types": ["Parameter", "Document", "PatchBaseline"],
                "operations": [
                    "DescribeParameters",
                    "ListDocuments",
                    "DescribePatchBaselines",
                ],
                "name_fields": ["Name", "ParameterName", "DocumentName"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            # Enhanced KMS patterns
            "kms": {
                "resource_types": ["Key", "Alias"],
                "operations": ["ListKeys", "ListAliases"],
                "name_fields": ["KeyId", "AliasName"],
                "region_dependent": True,
                "exclude_aws_managed": True,
                "aws_managed_patterns": [
                    r"^alias/aws/.*$",
                    r"^aws/.*$",
                ],  # AWS managed KMS keys
            },
            # Enhanced ACM patterns
            "acm": {
                "resource_types": ["Certificate"],
                "operations": ["ListCertificates"],
                "name_fields": ["CertificateArn", "DomainName"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
            # Enhanced WAF patterns
            "wafv2": {
                "resource_types": ["WebACL", "RuleGroup", "IPSet"],
                "operations": ["ListWebACLs", "ListRuleGroups", "ListIPSets"],
                "name_fields": ["Name", "Id", "ARN"],
                "region_dependent": True,
                "exclude_aws_managed": True,
            },
        }

        # AWS managed resource patterns (global)
        self.global_aws_managed_patterns = [
            r"^aws-",
            r"^AWS",
            r"^amazon-",
            r"^Amazon",
            r"^default",
            r"^Default",
        ]

        # Extract AWS managed patterns from service patterns for easy access
        self.aws_managed_patterns = {}
        for service, config in self.optimized_service_patterns.items():
            if "aws_managed_patterns" in config:
                self.aws_managed_patterns[service] = config["aws_managed_patterns"]

        # Enhanced confidence scoring weights
        self.confidence_weights = {
            "has_resource_id": 2.5,
            "has_resource_name": 2.0,
            "has_resource_arn": 1.5,
            "has_correct_type": 1.5,
            "has_tags": 1.0,
            "has_status": 0.5,
            "has_creation_date": 0.5,
            "has_vpc_info": 0.5,
            "has_security_groups": 0.5,
            "has_account_id": 0.5,
        }

    def analyze_and_map_resource(
        self,
        raw_data: Dict[str, Any],
        service_name: str,
        operation_name: str,
        region: str,
        account_id: str = None,
    ) -> Optional[StandardResource]:
        """Enhanced resource analysis with optimized service-specific patterns."""

        try:
            # Use optimized extraction methods
            resource_id = self._optimized_extract_resource_id(raw_data, service_name)
            resource_type = self._optimized_determine_resource_type(
                raw_data, operation_name, service_name
            )

            # Check if this is an AWS managed resource that should be excluded
            if self._is_aws_managed_resource(
                raw_data, service_name, resource_id, resource_type
            ):
                self.logger.debug(
                    f"Excluding AWS managed resource: {service_name}:{resource_type}:{resource_id}"
                )
                return None

            # Detect actual region for global services like S3
            actual_region = self._detect_actual_region(raw_data, service_name, region)

            # Initialize with optimized detection
            resource = StandardResource(
                service_name=self._normalize_service_name(service_name),
                resource_type=resource_type,
                resource_id=resource_id,
                region=actual_region,
                account_id=account_id or self._extract_account_from_data(raw_data),
                api_operation=operation_name,
                raw_data=raw_data,
            )

            # Enhanced field extraction
            resource.resource_name = self._optimized_extract_resource_name(
                raw_data, service_name
            )
            resource.resource_arn = self._extract_arn(raw_data)

            # Status and lifecycle with fallbacks
            resource.status = self._extract_status(raw_data) or self._extract_state(
                raw_data
            )
            resource.state = self._extract_state(raw_data) or self._extract_status(
                raw_data
            )
            resource.created_date = self._extract_creation_date(raw_data)
            resource.last_modified = self._extract_modification_date(raw_data)

            # Enhanced tag extraction
            raw_tags = self._optimized_extract_tags(raw_data)
            resource.tags = raw_tags
            resource.name_from_tags = raw_tags.get("Name")
            resource.environment = (
                raw_tags.get("Environment")
                or raw_tags.get("Env")
                or raw_tags.get("Stage")
            )
            resource.project = (
                raw_tags.get("Project")
                or raw_tags.get("ProjectName")
                or raw_tags.get("Application")
            )
            resource.cost_center = (
                raw_tags.get("CostCenter")
                or raw_tags.get("BillingCode")
                or raw_tags.get("Department")
            )

            # Enhanced security and network detection
            resource.vpc_id = self._extract_vpc_info(raw_data)
            resource.subnet_ids = self._extract_subnet_info(raw_data)
            resource.security_groups = self._extract_security_groups(raw_data)
            resource.public_access = self._determine_public_access(
                raw_data, service_name
            )
            resource.encrypted = self._determine_encryption_status(raw_data)

            # Resource relationships
            resource.dependencies = self._identify_dependencies(raw_data)
            resource.parent_resource = self._identify_parent_resource(raw_data)

            # Optimized confidence calculation
            resource.confidence_score = self._optimized_calculate_confidence_score(
                resource
            )

            return resource

        except Exception as e:
            self.logger.error(f"Optimized mapping failed for {service_name}: {e}")
            # Return basic resource with minimal info
            return StandardResource(
                service_name=service_name,
                resource_type="Unknown",
                resource_id=str(raw_data.get("Id", raw_data.get("Name", "unknown"))),
                region=region,
                confidence_score=0.1,
                raw_data=raw_data,
            )

    def _optimized_extract_resource_id(
        self, data: Dict[str, Any], service_name: str
    ) -> str:
        """Optimized resource ID extraction with service-specific logic."""

        service_lower = service_name.lower()
        if service_lower in self.optimized_service_patterns:
            patterns = self.optimized_service_patterns[service_lower]

            # Try service-specific name fields first
            for field in patterns.get("name_fields", []):
                if field in data and data[field]:
                    return str(data[field])

        # Fall back to parent method
        return super()._extract_resource_id(data)

    def _optimized_extract_resource_name(
        self, data: Dict[str, Any], service_name: str
    ) -> Optional[str]:
        """Optimized resource name extraction with service-specific logic."""

        service_lower = service_name.lower()
        if service_lower in self.optimized_service_patterns:
            patterns = self.optimized_service_patterns[service_lower]

            # Try service-specific name fields
            for field in patterns.get("name_fields", []):
                if field in data and data[field]:
                    return str(data[field])

        # CloudFront specific logic
        if service_lower == "cloudfront":
            if "DomainName" in data:
                return data["DomainName"]
            if "Aliases" in data and data["Aliases"].get("Items"):
                return data["Aliases"]["Items"][0]

        # Fall back to parent method
        return super()._extract_resource_name(data)

    def _optimized_determine_resource_type(
        self, data: Dict[str, Any], operation_name: str, service_name: str
    ) -> str:
        """Optimized resource type determination."""

        service_lower = service_name.lower()
        if service_lower in self.optimized_service_patterns:
            patterns = self.optimized_service_patterns[service_lower]
            resource_types = patterns.get("resource_types", [])

            # Match operation to resource type
            for resource_type in resource_types:
                if resource_type.lower() in operation_name.lower():
                    return resource_type

        # Fall back to parent method
        return super()._determine_resource_type(data, operation_name, service_name)

    def _optimized_extract_tags(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Optimized tag extraction with multiple fallback methods."""

        tags = super()._extract_tags(data)

        # Additional tag extraction patterns
        if not tags:
            # Try nested tag structures
            for key, value in data.items():
                if isinstance(value, dict) and "Tags" in value:
                    nested_tags = value["Tags"]
                    if isinstance(nested_tags, list):
                        for tag in nested_tags:
                            if (
                                isinstance(tag, dict)
                                and "Key" in tag
                                and "Value" in tag
                            ):
                                tags[tag["Key"]] = tag["Value"]
                    elif isinstance(nested_tags, dict):
                        tags.update(nested_tags)

        return tags

    def _optimized_calculate_confidence_score(
        self, resource: StandardResource
    ) -> float:
        """Optimized confidence scoring with weighted factors."""

        score = 0.0
        total_weight = sum(self.confidence_weights.values())

        # Apply weighted scoring
        if resource.resource_id and resource.resource_id != "unknown":
            score += self.confidence_weights["has_resource_id"]

        if resource.resource_name:
            score += self.confidence_weights["has_resource_name"]

        if resource.resource_arn:
            score += self.confidence_weights["has_resource_arn"]

        if resource.resource_type and resource.resource_type != "Unknown":
            score += self.confidence_weights["has_correct_type"]

        if resource.tags:
            score += self.confidence_weights["has_tags"]

        if resource.status:
            score += self.confidence_weights["has_status"]

        if resource.created_date:
            score += self.confidence_weights["has_creation_date"]

        if resource.vpc_id:
            score += self.confidence_weights["has_vpc_info"]

        if resource.security_groups:
            score += self.confidence_weights["has_security_groups"]

        if resource.account_id:
            score += self.confidence_weights["has_account_id"]

        return min(score / total_weight, 1.0)

    def _is_aws_managed_resource(
        self,
        data: Dict[str, Any],
        service_name: str,
        resource_id: str,
        resource_type: str,
    ) -> bool:
        """Check if a resource is AWS managed and should be excluded."""

        service_lower = service_name.lower()

        # Skip filtering if not configured for this service
        if service_lower not in self.optimized_service_patterns:
            return False

        patterns = self.optimized_service_patterns[service_lower]
        if not patterns.get("exclude_aws_managed", False):
            return False

        # Check if resource type should be excluded
        if resource_type in patterns.get("exclude_resource_types", []):
            return True

        # Check service-specific AWS managed patterns
        service_patterns = patterns.get("aws_managed_patterns", [])
        for pattern in service_patterns:
            if re.match(pattern, resource_id, re.IGNORECASE):
                return True

        # Check global AWS managed patterns
        for pattern in self.global_aws_managed_patterns:
            if re.match(pattern, resource_id, re.IGNORECASE):
                return True

        # Service-specific checks
        if service_lower == "iam":
            return self._is_aws_managed_iam_resource(data, resource_id, resource_type)
        elif service_lower == "route53":
            return self._is_aws_managed_route53_resource(
                data, resource_id, resource_type
            )
        elif service_lower == "ec2":
            return self._is_aws_managed_ec2_resource(data, resource_id, resource_type)

        return False

    def _is_aws_managed_iam_resource(
        self, data: Dict[str, Any], resource_id: str, resource_type: str
    ) -> bool:
        """Check if IAM resource is AWS managed."""

        # Check for AWS managed policies
        if resource_type == "Policy":
            arn = data.get("Arn", "")
            # AWS managed policies
            if arn.startswith("arn:aws:iam::aws:policy/"):
                return True
            # Service-linked role policies
            if ":policy/aws-service-role/" in arn or ":policy/service-role/" in arn:
                return True
            # Check policy name patterns
            policy_name = data.get("PolicyName", resource_id)
            aws_policy_patterns = [
                r"^AWS.*Policy$",
                r"^Amazon.*Policy$",
                r"^.*ServiceRolePolicy$",
                r"^.*ServiceLinkedRolePolicy$",
            ]
            for pattern in aws_policy_patterns:
                if re.match(pattern, policy_name, re.IGNORECASE):
                    return True

        # Check for service-linked roles and AWS managed roles
        if resource_type == "Role":
            path = data.get("Path", "")
            # Service-linked roles
            if path.startswith("/aws-service-role/") or path.startswith(
                "/service-role/"
            ):
                return True

            # Check role creation date - roles created before account creation
            # are likely AWS managed
            create_date = data.get("CreateDate")
            if create_date and self._is_pre_account_creation(create_date):
                return True

            # Check assume role policy for service-linked roles
            assume_role_policy = data.get("AssumeRolePolicyDocument", "")
            if self._is_service_linked_role_policy(assume_role_policy):
                return True

        # Check for AWS managed users (rare but possible)
        if resource_type == "User":
            path = data.get("Path", "")
            if path.startswith("/aws-service-role/") or path.startswith(
                "/service-role/"
            ):
                return True

        # Check for AWS managed groups
        if resource_type == "Group":
            path = data.get("Path", "")
            if path.startswith("/aws-service-role/") or path.startswith(
                "/service-role/"
            ):
                return True

        return False

    def _is_service_linked_role_policy(self, assume_role_policy: Any) -> bool:
        """Check if assume role policy indicates a service-linked role."""

        if not assume_role_policy:
            return False

        try:
            import json as json_module

            # Parse policy if it's a string
            if isinstance(assume_role_policy, str):
                policy = json_module.loads(assume_role_policy)
            else:
                policy = assume_role_policy

            statements = policy.get("Statement", [])
            for statement in statements:
                principal = statement.get("Principal", {})
                if isinstance(principal, dict):
                    service = principal.get("Service", "")
                    # Check for AWS service principals
                    if isinstance(service, str) and service.endswith(".amazonaws.com"):
                        # Additional check for service-linked role indicators
                        if any(
                            svc in service
                            for svc in [
                                "autoscaling",
                                "ec2",
                                "rds",
                                "lambda",
                                "ecs",
                                "eks",
                                "elasticloadbalancing",
                                "cloudformation",
                                "config",
                            ]
                        ):
                            return True
                elif isinstance(principal, str) and principal.endswith(
                    ".amazonaws.com"
                ):
                    return True
        except Exception as e:
            self.logger.debug(f"Failed to parse assume role policy: {e}")

        return False

    def _is_pre_account_creation(self, create_date) -> bool:
        """Check if resource was created before typical account creation (likely AWS managed)."""

        try:
            from datetime import datetime, timezone

            # Convert to datetime if it's not already
            if isinstance(create_date, str):
                # Try to parse ISO format
                create_dt = datetime.fromisoformat(create_date.replace("Z", "+00:00"))
            elif hasattr(create_date, "timestamp"):
                create_dt = create_date
            else:
                return False

            # If resource was created before 2010 (when AWS was very limited), it's likely AWS managed
            aws_early_date = datetime(2010, 1, 1, tzinfo=timezone.utc)
            return create_dt < aws_early_date

        except Exception as e:
            self.logger.debug(f"Failed to parse create date {create_date}: {e}")
            return False

    def _is_aws_managed_route53_resource(
        self, data: Dict[str, Any], resource_id: str, resource_type: str
    ) -> bool:
        """Check if Route53 resource is AWS managed."""

        # Exclude geolocation records and other AWS managed resources
        if resource_type == "GeoLocation":
            return True

        # Check for AWS managed hosted zones
        if resource_type == "HostedZone":
            name = data.get("Name", "")

            # Exclude reverse DNS zones
            if name.endswith(".in-addr.arpa.") or name.endswith(".ip6.arpa."):
                return True

            # Exclude AWS service domains
            aws_domain_patterns = [
                r".*\.amazonaws\.com\.$",
                r".*\.aws\.amazon\.com\.$",
                r".*\.awsapps\.com\.$",
                r".*\.elb\.amazonaws\.com\.$",
                r".*\.s3\.amazonaws\.com\.$",
                r".*\.cloudfront\.net\.$",
            ]

            for pattern in aws_domain_patterns:
                if re.match(pattern, name, re.IGNORECASE):
                    return True

            # Check if it's a private hosted zone for VPC (these might be user-created)
            config = data.get("Config", {})
            if config.get("PrivateZone", False):
                # Private zones are typically user-created, so don't filter them
                return False

            # Check resource record count - AWS managed zones typically have minimal records
            resource_record_set_count = data.get("ResourceRecordSetCount", 0)
            if resource_record_set_count <= 2:  # Only NS and SOA records
                # Could be AWS managed, but let's be conservative and keep it
                pass

        return False

    def _is_aws_managed_ec2_resource(
        self, data: Dict[str, Any], resource_id: str, resource_type: str
    ) -> bool:
        """Check if EC2 resource is AWS managed."""

        # Check for default VPC and security groups
        if resource_type == "VPC":
            is_default = data.get("IsDefault", False)
            if is_default:
                return True
            # Check for VPC CIDR blocks that indicate default VPCs
            cidr_block = data.get("CidrBlock", "")
            if cidr_block == "172.31.0.0/16":  # Default VPC CIDR
                return True

        # Check for default security groups and AWS managed security groups
        if resource_type == "SecurityGroup":
            is_default = data.get("IsDefault", False)
            group_name = data.get("GroupName", "")

            if is_default or group_name == "default":
                return True

            # Check for AWS managed security group patterns
            aws_sg_patterns = [
                r"^aws-.*",
                r"^Amazon.*",
                r"^rds-launch-wizard.*",
                r"^elasticache-.*",
                r"^ElasticMapReduce-.*",
            ]

            for pattern in aws_sg_patterns:
                if re.match(pattern, group_name, re.IGNORECASE):
                    return True

        # Check for default subnets
        if resource_type == "Subnet":
            # Default subnets typically have specific naming patterns
            # availability_zone = data.get("AvailabilityZone", "")
            # vpc_id = data.get("VpcId", "")

            # If it's in a default VPC, it's likely a default subnet
            # We would need to check the VPC separately, but for now use heuristics
            cidr_block = data.get("CidrBlock", "")
            if cidr_block.startswith("172.31."):  # Default VPC subnet range
                return True

        # Check for default route tables
        if resource_type == "RouteTable":
            # Default route tables have specific associations
            associations = data.get("Associations", [])
            for assoc in associations:
                if assoc.get("Main", False):  # Main route table
                    return True

        # Check for default internet gateways
        if resource_type == "InternetGateway":
            # Internet gateways attached to default VPCs
            attachments = data.get("Attachments", [])
            for attachment in attachments:
                # vpc_id = attachment.get("VpcId", "")
                # We'd need to check if this VPC is default, but that requires another call
                # For now, be conservative and don't filter IGWs
                pass

        return False

    def _detect_actual_region(
        self, data: Dict[str, Any], service_name: str, default_region: str
    ) -> str:
        """Detect the actual region for resources, especially for global services like S3."""

        service_lower = service_name.lower()

        # S3 bucket region detection
        if service_lower == "s3":
            # Try to get region from bucket location
            bucket_name = data.get("Name", "")
            if bucket_name:
                try:
                    # This would need to be called from the discovery class with proper session
                    # For now, we'll use a placeholder that can be enhanced later
                    region_hint = data.get("Region", data.get("LocationConstraint", ""))
                    if region_hint and region_hint != "":
                        return region_hint if region_hint != "null" else "us-east-1"
                except Exception:
                    pass

        # For other services, check if region is specified in the data
        region_fields = ["Region", "AvailabilityZone", "Placement"]
        for field in region_fields:
            if field in data:
                if field == "AvailabilityZone":
                    az = data[field]
                    if isinstance(az, str) and len(az) > 2:
                        return az[
                            :-1
                        ]  # Remove the AZ letter (e.g., us-east-1a -> us-east-1)
                elif field == "Placement":
                    placement = data[field]
                    if isinstance(placement, dict) and "AvailabilityZone" in placement:
                        az = placement["AvailabilityZone"]
                        if isinstance(az, str) and len(az) > 2:
                            return az[:-1]
                else:
                    region = data[field]
                    if isinstance(region, str) and region:
                        return region

        return default_region


class OptimizedAWSDiscovery(IntelligentAWSDiscovery):
    """Optimized discovery system with enhanced service coverage, region handling, and AWS managed resource filtering."""

    def __init__(self, session: boto3.Session = None, regions: List[str] = None):
        super().__init__(session, regions)
        self.field_mapper = OptimizedFieldMapper()

        # Priority services that had issues in the original system
        self.priority_services = [
            "cloudfront",  # Was missing distributions
            "iam",  # Was missing roles/users
            "route53",  # Was missing hosted zones
            "s3",  # Had detection issues
            "lambda",  # Had detection issues
            "ec2",  # Core service
            "rds",  # Database service
            "cloudwatch",  # Monitoring
        ]

        # Performance settings
        self.max_workers = 4
        self.enable_parallel = True
        self.operation_timeout = 20

        # Region handling
        self.specified_regions = regions

        # Use parent's circuit breaker for recursion protection
        # (parent already initialized self._clients_in_progress)
        self.fallback_to_all_regions = True

        # S3 region cache for bucket location detection
        self.s3_region_cache = {}

    def _create_client_safely(self, service_name: str, region: str):
        """Safely create AWS client with recursion protection (thread-safe)."""
        client_key = f"{service_name}:{region}"

        with self._client_lock:
            if client_key in self._clients_in_progress:
                self.logger.warning(
                    f"Recursion detected during {service_name} client creation in {region}"
                )
                return None

            self._clients_in_progress.add(client_key)

        try:
            client = self.session.client(service_name, region_name=region)
            return client
        except Exception as e:
            self.logger.error(
                f"Failed to create {service_name} client in {region}: {e}"
            )
            return None
        finally:
            with self._client_lock:
                self._clients_in_progress.discard(client_key)

    def discover_all_services(self) -> List[StandardResource]:
        """Optimized discovery with enhanced service coverage."""

        self.logger.info(
            "Starting optimized AWS discovery with enhanced service coverage..."
        )

        if self.enable_parallel:
            return self._discover_services_parallel()
        else:
            return self._discover_services_sequential()

    def _discover_services_parallel(self) -> List[StandardResource]:
        """Parallel service discovery for better performance."""

        all_resources = []

        # Process priority services in parallel
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            # Submit discovery tasks for priority services
            future_to_service = {
                executor.submit(self._discover_service_safe, service): service
                for service in self.priority_services
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(
                future_to_service, timeout=120
            ):
                service = future_to_service[future]
                try:
                    resources = future.result(timeout=self.operation_timeout)
                    all_resources.extend(resources)
                    self.logger.info(
                        f"Optimized discovery: {service} found {len(resources)} resources"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Optimized discovery failed for {service}: {e}"
                    )

        # Deduplicate and enhance
        all_resources = self._intelligent_deduplication(all_resources)
        self.discovered_resources.extend(all_resources)

        self.logger.info(
            f"Optimized parallel discovery complete: {len(all_resources)} resources"
        )
        return all_resources

    def _discover_services_sequential(self) -> List[StandardResource]:
        """Sequential discovery with enhanced service coverage."""

        all_resources = []

        for service in self.priority_services:
            try:
                resources = self._discover_service_safe(service)
                all_resources.extend(resources)
                self.logger.info(
                    f"Optimized discovery: {service} found {len(resources)} resources"
                )
            except Exception as e:
                self.logger.warning(f"Optimized discovery failed for {service}: {e}")

        # Deduplicate and enhance
        all_resources = self._intelligent_deduplication(all_resources)
        self.discovered_resources.extend(all_resources)

        self.logger.info(
            f"Optimized sequential discovery complete: {len(all_resources)} resources"
        )
        return all_resources

    def _discover_service_safe(self, service_name: str) -> List[StandardResource]:
        """Safe service discovery with error handling."""

        try:
            return self.discover_service(service_name)
        except Exception as e:
            self.logger.error(f"Service discovery failed for {service_name}: {e}")
            return []

    def discover_service(self, service_name: str) -> List[StandardResource]:
        """Enhanced service discovery with region handling and AWS managed resource filtering."""

        service_resources = []
        regions_to_use = self._get_regions_for_service(service_name)

        # Track if we successfully discovered from any region
        discovery_successful = False

        for region in regions_to_use:
            try:
                # Skip global services for non-primary regions
                if self._is_global_service(service_name) and region != "us-east-1":
                    continue

                # Get service client safely
                client = self._create_client_safely(service_name, region)
                if client is None:
                    continue

                # Get optimized operations for this service
                operations = self._get_optimized_discovery_operations(
                    service_name, client
                )

                # Try each discovery operation
                region_resources = []
                for operation_name in operations:
                    try:
                        resources = self._discover_via_operation_enhanced(
                            client, operation_name, service_name, region
                        )
                        # Filter out None results (AWS managed resources)
                        resources = [r for r in resources if r is not None]
                        region_resources.extend(resources)

                        if resources:
                            discovery_successful = True

                    except Exception as e:
                        self.logger.debug(
                            f"Operation {operation_name} failed for {service_name} in {region}: {e}"
                        )
                        continue

                # Add region resources to total
                service_resources.extend(region_resources)

            except Exception as e:
                self.logger.warning(
                    f"Failed to create {service_name} client in {region}: {e}"
                )
                continue

        # If specified regions failed and we have fallback enabled, try all regions
        if (
            not discovery_successful
            and self.specified_regions
            and self.fallback_to_all_regions
        ):
            self.logger.info(f"Falling back to all regions for {service_name}")
            return self._discover_service_all_regions(service_name)

        # For S3, enhance with actual bucket regions after all regions are processed
        if service_name.lower() == "s3" and service_resources:
            service_resources = self._enhance_s3_bucket_regions_comprehensive(
                service_resources
            )

        # Enhanced deduplication for this service with consistent ordering
        service_resources = self._intelligent_deduplication_consistent(
            service_resources
        )

        return service_resources

    def _get_regions_for_service(self, service_name: str) -> List[str]:
        """Get regions to use for a specific service."""

        # If specific regions were provided, use them
        if self.specified_regions:
            return self.specified_regions

        # Otherwise use all available regions
        return self.regions

    def _discover_service_all_regions(
        self, service_name: str
    ) -> List[StandardResource]:
        """Fallback discovery using all available regions."""

        self.logger.info(
            f"Attempting discovery for {service_name} across all regions as fallback"
        )

        # Temporarily override regions and disable fallback to prevent infinite loop
        original_regions = self.regions
        original_fallback = self.fallback_to_all_regions
        try:
            self.regions = self._get_available_regions()
            self.fallback_to_all_regions = False  # Prevent recursive fallback
            return self.discover_service(service_name)
        finally:
            self.regions = original_regions
            self.fallback_to_all_regions = original_fallback

    def _discover_via_operation_enhanced(
        self, client, operation_name: str, service_name: str, region: str
    ) -> List[StandardResource]:
        """Enhanced operation discovery with AWS managed resource filtering."""

        resources = []

        try:
            # Get the operation
            operation = getattr(client, self._snake_case(operation_name))

            # Call the operation
            response = operation()

            # Extract resources from response
            resources = self._extract_resources_from_response_enhanced(
                response, service_name, operation_name, region, client
            )

        except Exception as e:
            self.logger.debug(f"Operation {operation_name} failed: {e}")

        return resources

    def _extract_resources_from_response_enhanced(
        self,
        response: Dict[str, Any],
        service_name: str,
        operation_name: str,
        region: str,
        client,
    ) -> List[StandardResource]:
        """Enhanced resource extraction with filtering and region detection."""

        resources = []

        # Find the resource list in the response
        resource_lists = self._find_resource_lists(response)

        for resource_list in resource_lists:
            for item in resource_list:
                if isinstance(item, dict):
                    try:
                        # Enhanced mapping with filtering
                        resource = self.field_mapper.analyze_and_map_resource(
                            item, service_name, operation_name, region
                        )

                        # Resource might be None if it's AWS managed and filtered out
                        if resource is not None:
                            resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Failed to map resource: {e}")

        return resources

    def _enhance_s3_bucket_regions(
        self, resources: List[StandardResource], s3_client
    ) -> List[StandardResource]:
        """Enhance S3 bucket resources with actual region information."""

        enhanced_resources = []

        for resource in resources:
            if (
                resource.service_name.upper() == "S3"
                and resource.resource_type == "Bucket"
            ):
                try:
                    # Get bucket location
                    bucket_name = resource.resource_id

                    # Check cache first
                    if bucket_name in self.s3_region_cache:
                        actual_region = self.s3_region_cache[bucket_name]
                    else:
                        # Get bucket location
                        try:
                            location_response = s3_client.get_bucket_location(
                                Bucket=bucket_name
                            )
                            location_constraint = location_response.get(
                                "LocationConstraint"
                            )

                            # Handle special cases
                            if location_constraint is None or location_constraint == "":
                                actual_region = "us-east-1"  # Default region
                            elif location_constraint == "EU":
                                actual_region = "eu-west-1"  # Legacy EU constraint
                            else:
                                actual_region = location_constraint

                            # Cache the result
                            self.s3_region_cache[bucket_name] = actual_region

                        except Exception as e:
                            self.logger.debug(
                                f"Failed to get bucket location for {bucket_name}: {e}"
                            )
                            actual_region = resource.region  # Keep original region

                    # Update resource region
                    resource.region = actual_region
                    enhanced_resources.append(resource)

                except Exception as e:
                    self.logger.debug(
                        f"Failed to enhance S3 bucket {resource.resource_id}: {e}"
                    )
                    enhanced_resources.append(resource)  # Keep original
            else:
                enhanced_resources.append(resource)

        return enhanced_resources

    def _enhance_s3_bucket_regions_comprehensive(
        self, resources: List[StandardResource]
    ) -> List[StandardResource]:
        """Comprehensive S3 bucket region enhancement for all discovered buckets."""

        enhanced_resources = []
        s3_buckets = [
            r
            for r in resources
            if r.service_name.upper() == "S3" and r.resource_type == "Bucket"
        ]
        other_resources = [
            r
            for r in resources
            if not (r.service_name.upper() == "S3" and r.resource_type == "Bucket")
        ]

        if not s3_buckets:
            return resources

        # Create S3 client for bucket location detection
        try:
            s3_client = self._create_client_safely("s3", "us-east-1")
            if not s3_client:
                self.logger.warning(
                    "Could not create S3 client for bucket location detection"
                )
                return s3_buckets

            for bucket_resource in s3_buckets:
                try:
                    bucket_name = bucket_resource.resource_id

                    # Check cache first
                    if bucket_name in self.s3_region_cache:
                        actual_region = self.s3_region_cache[bucket_name]
                    else:
                        # Get bucket location
                        try:
                            location_response = s3_client.get_bucket_location(
                                Bucket=bucket_name
                            )
                            location_constraint = location_response.get(
                                "LocationConstraint"
                            )

                            # Handle special cases for region mapping
                            if location_constraint is None or location_constraint == "":
                                actual_region = "us-east-1"  # Default region
                            elif location_constraint == "EU":
                                actual_region = "eu-west-1"  # Legacy EU constraint
                            else:
                                actual_region = location_constraint

                            # Cache the result
                            self.s3_region_cache[bucket_name] = actual_region

                            self.logger.debug(
                                f"S3 bucket {bucket_name} actual region: {actual_region}"
                            )

                        except Exception as e:
                            self.logger.debug(
                                f"Failed to get bucket location for {bucket_name}: {e}"
                            )
                            actual_region = (
                                bucket_resource.region
                            )  # Keep original region

                    # Update resource region and ARN
                    bucket_resource.region = actual_region
                    # Update ARN to reflect correct region
                    bucket_resource.arn = f"arn:aws:s3:::{bucket_name}"
                    enhanced_resources.append(bucket_resource)

                except Exception as e:
                    self.logger.debug(
                        f"Failed to enhance S3 bucket {bucket_resource.resource_id}: {e}"
                    )
                    enhanced_resources.append(bucket_resource)  # Keep original

        except Exception as e:
            self.logger.warning(f"Failed to create S3 client for region detection: {e}")
            enhanced_resources.extend(s3_buckets)  # Keep originals

        # Add back other resources
        enhanced_resources.extend(other_resources)
        return enhanced_resources

    def _intelligent_deduplication_consistent(
        self, resources: List[StandardResource]
    ) -> List[StandardResource]:
        """Enhanced deduplication with consistent ordering for state management."""

        if not resources:
            return resources

        # Create a map of unique resources by ARN (primary key)
        unique_resources = {}

        for resource in resources:
            # Use ARN as primary key, fallback to service:type:id:region
            if resource.arn:
                key = resource.arn
            else:
                key = f"{resource.service_name}:{resource.resource_type}:{resource.resource_id}:{resource.region}"

            # Keep the resource with higher confidence score
            if key not in unique_resources:
                unique_resources[key] = resource
            else:
                existing = unique_resources[key]
                if resource.confidence_score > existing.confidence_score:
                    unique_resources[key] = resource

        # Convert back to list and sort consistently for state management
        deduplicated = list(unique_resources.values())

        # Sort by ARN first, then by service, type, id, region for consistent ordering
        deduplicated.sort(
            key=lambda r: (
                r.arn or "",
                r.service_name,
                r.resource_type,
                r.resource_id,
                r.region,
            )
        )

        self.logger.debug(
            f"Deduplication: {len(resources)} -> {len(deduplicated)} resources"
        )
        return deduplicated

    def _get_optimized_discovery_operations(
        self, service_name: str, client
    ) -> List[str]:
        """Get optimized discovery operations for a service."""

        # Get all available operations
        all_operations = client._service_model.operation_names

        # Service-specific operation priorities
        service_lower = service_name.lower()
        if service_lower in self.field_mapper.optimized_service_patterns:
            preferred_ops = self.field_mapper.optimized_service_patterns[
                service_lower
            ].get("operations", [])
            # Prioritize preferred operations
            operations = [op for op in preferred_ops if op in all_operations]
            if operations:
                return operations

        # Fall back to generic discovery operations
        discovery_ops = [
            op
            for op in all_operations
            if op.startswith(("List", "Describe", "Get"))
            and not any(
                skip in op
                for skip in ["Policy", "Version", "Status", "Health", "Metrics"]
            )
        ]

        # Prioritize List operations over Describe operations
        list_ops = [op for op in discovery_ops if op.startswith("List")]
        describe_ops = [op for op in discovery_ops if op.startswith("Describe")]
        get_ops = [op for op in discovery_ops if op.startswith("Get")]

        return (
            list_ops[:2] + describe_ops[:2] + get_ops[:1]
        )  # Limit to avoid too many calls

    def _is_global_service(self, service_name: str) -> bool:
        """Check if a service is global (not region-specific)."""

        service_lower = service_name.lower()
        if service_lower in self.field_mapper.optimized_service_patterns:
            return self.field_mapper.optimized_service_patterns[service_lower].get(
                "global_service", False
            )

        # Default global services
        global_services = {
            "cloudfront",
            "iam",
            "route53",
            "wa",
            "cloudformation",
            "organizations",
            "support",
            "trustedadvisor",
        }

        return service_lower in global_services

    def _apply_ai_predictions(
        self, resources: List[StandardResource]
    ) -> List[StandardResource]:
        """Apply AI-based resource predictions for missing dependencies."""

        predicted_resources = []

        # AI prediction patterns for cross-service dependencies
        ai_patterns = {
            # Lambda functions -> CloudWatch log groups
            "lambda_to_logs": {
                "source_service": "lambda",
                "target_service": "logs",
                "pattern": lambda resource: f"/aws/lambda/{resource.resource_id}",
                "resource_type": "LogGroup",
                "confidence": 0.7,
            },
            # ECS clusters -> CloudWatch log groups
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
            # EKS clusters -> CloudWatch log groups
            "eks_to_logs": {
                "source_service": "eks",
                "target_service": "logs",
                "pattern": lambda resource: f"/aws/eks/{resource.resource_id}/cluster",
                "resource_type": "LogGroup",
                "confidence": 0.6,
            },
            # API Gateway -> CloudWatch log groups
            "apigateway_to_logs": {
                "source_service": "apigateway",
                "target_service": "logs",
                "pattern": lambda resource: f"API-Gateway-Execution-Logs_{resource.resource_id}/prod",
                "resource_type": "LogGroup",
                "confidence": 0.5,
            },
            # RDS instances -> CloudWatch log groups
            "rds_to_logs": {
                "source_service": "rds",
                "target_service": "logs",
                "pattern": lambda resource: f"/aws/rds/instance/{resource.resource_id}/error",
                "resource_type": "LogGroup",
                "confidence": 0.4,
            },
            # CodeBuild projects -> CloudWatch log groups
            "codebuild_to_logs": {
                "source_service": "codebuild",
                "target_service": "logs",
                "pattern": lambda resource: f"/aws/codebuild/{resource.resource_id}",
                "resource_type": "LogGroup",
                "confidence": 0.6,
            },
            # Lambda functions -> CloudWatch alarms
            "lambda_to_cloudwatch": {
                "source_service": "lambda",
                "target_service": "cloudwatch",
                "pattern": lambda resource: f"{resource.resource_id}-errors",
                "resource_type": "Alarm",
                "confidence": 0.4,
            },
            # RDS instances -> CloudWatch alarms
            "rds_to_cloudwatch": {
                "source_service": "rds",
                "target_service": "cloudwatch",
                "pattern": lambda resource: f"{resource.resource_id}-cpu-utilization",
                "resource_type": "Alarm",
                "confidence": 0.4,
            },
            # Lambda functions -> IAM roles
            "lambda_to_iam": {
                "source_service": "lambda",
                "target_service": "iam",
                "pattern": lambda resource: f"{resource.resource_id}-role",
                "resource_type": "Role",
                "confidence": 0.5,
            },
            # ECS services -> IAM roles
            "ecs_to_iam": {
                "source_service": "ecs",
                "target_service": "iam",
                "pattern": lambda resource: "ecsTaskExecutionRole",
                "resource_type": "Role",
                "confidence": 0.4,
            },
        }

        # Group resources by service
        resources_by_service = {}
        for resource in resources:
            service = resource.service_name.lower()
            if service not in resources_by_service:
                resources_by_service[service] = []
            resources_by_service[service].append(resource)

        # Apply prediction patterns
        for pattern_name, pattern_config in ai_patterns.items():
            source_service = pattern_config["source_service"]
            target_service = pattern_config["target_service"]

            if source_service in resources_by_service:
                for source_resource in resources_by_service[source_service]:
                    try:
                        # Generate predicted resource ID
                        predicted_id = pattern_config["pattern"](source_resource)

                        # Check if this predicted resource already exists
                        exists = False
                        if target_service in resources_by_service:
                            for existing in resources_by_service[target_service]:
                                if existing.resource_id == predicted_id:
                                    exists = True
                                    break

                        if not exists:
                            # Create predicted resource
                            predicted_resource = StandardResource(
                                service_name=target_service.upper(),
                                resource_type=pattern_config["resource_type"],
                                resource_id=predicted_id,
                                resource_name=predicted_id,
                                region=source_resource.region,
                                account_id=source_resource.account_id,
                                arn=f"arn:aws:{target_service}:{source_resource.region}:{source_resource.account_id}:{pattern_config['resource_type'].lower()}/{predicted_id}",
                                tags={},
                                raw_data={
                                    "predicted": True,
                                    "source_resource": source_resource.arn,
                                },
                                confidence_score=pattern_config["confidence"],
                                discovery_method="ai_prediction",
                                last_seen=datetime.now(),
                            )

                            predicted_resources.append(predicted_resource)

                    except Exception as e:
                        self.logger.debug(
                            f"AI prediction failed for {pattern_name}: {e}"
                        )

        self.logger.info(
            f"AI predictions generated {len(predicted_resources)} potential resources"
        )
        return predicted_resources

    def discover_all_services_with_ai(self) -> List[StandardResource]:
        """Enhanced discovery with AI predictions for missing resources."""

        # First, run standard optimized discovery
        discovered_resources = self.discover_all_services()

        # Apply AI predictions
        predicted_resources = self._apply_ai_predictions(discovered_resources)

        # Combine and deduplicate
        all_resources = discovered_resources + predicted_resources
        all_resources = self._intelligent_deduplication(all_resources)

        self.logger.info(
            f"Discovery with AI complete: {len(discovered_resources)} discovered + {len(predicted_resources)} predicted = {len(all_resources)} total"
        )

        return all_resources
