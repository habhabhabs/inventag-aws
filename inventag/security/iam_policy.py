"""
Least-privilege, read-only IAM policy for InvenTag.

Every action is listed explicitly (no wildcards) and corresponds to an API
operation that InvenTag's discovery code calls. Each entry maps the IAM action
to the botocore service/operation it authorises, so tests can check that the
operation exists and is read-only. Action names were checked against the AWS
Service Authorization Reference (see ``tests/unit/test_security_iam_policy.py``).

Deliberately excluded:

* ``config:*``, ``resource-groups:*`` and other wildcards: they include write
  actions such as ``config:DeleteConfigRule`` or ``resource-groups:DeleteGroup``.
* Actions that return secrets or data (``secretsmanager:GetSecretValue``,
  ``ssm:GetParameter*``, ``s3:GetObject``, ``lambda:GetFunction`` which returns
  a presigned code URL) - InvenTag uses ``lambda:GetFunctionConfiguration``.
* ``apigateway:GET`` on ``/apikeys`` (API key values can be read there).
* ``cloudtrail:LookupEvents``: returns event records with request parameters,
  and no code path that runs calls it.

``sts:GetCallerIdentity`` needs no permission. ``sts:AssumeRole`` belongs on
the *scanning* identity (to reach the role), not in this policy.

Discovery of services outside this list is attempted dynamically; those calls
fail with AccessDenied and are skipped.
"""

import copy
from typing import Dict, List, Optional, Tuple

# IAM action -> (botocore service name, botocore operation name)
READ_ONLY_ACTIONS: Dict[str, Tuple[str, str]] = {
    "acm:ListCertificates": ("acm", "ListCertificates"),
    "ce:GetCostAndUsage": ("ce", "GetCostAndUsage"),
    "cloudformation:DescribeStacks": ("cloudformation", "DescribeStacks"),
    "cloudformation:ListStacks": ("cloudformation", "ListStacks"),
    "cloudformation:ListStackSets": ("cloudformation", "ListStackSets"),
    "cloudformation:ListChangeSets": ("cloudformation", "ListChangeSets"),
    "cloudfront:ListDistributions": ("cloudfront", "ListDistributions"),
    "cloudtrail:DescribeTrails": ("cloudtrail", "DescribeTrails"),
    "cloudwatch:DescribeAlarms": ("cloudwatch", "DescribeAlarms"),
    "cloudwatch:ListDashboards": ("cloudwatch", "ListDashboards"),
    "cloudwatch:GetMetricStatistics": ("cloudwatch", "GetMetricStatistics"),
    "codebuild:ListBuilds": ("codebuild", "ListBuilds"),
    "codebuild:ListProjects": ("codebuild", "ListProjects"),
    "codepipeline:ListPipelines": ("codepipeline", "ListPipelines"),
    "config:DescribeConfigurationRecorders": (
        "config",
        "DescribeConfigurationRecorders",
    ),
    "dynamodb:DescribeTable": ("dynamodb", "DescribeTable"),
    "dynamodb:ListBackups": ("dynamodb", "ListBackups"),
    "dynamodb:ListGlobalTables": ("dynamodb", "ListGlobalTables"),
    "dynamodb:ListTables": ("dynamodb", "ListTables"),
    "ec2:DescribeAddresses": ("ec2", "DescribeAddresses"),
    "ec2:DescribeInstances": ("ec2", "DescribeInstances"),
    "ec2:DescribeKeyPairs": ("ec2", "DescribeKeyPairs"),
    "ec2:DescribeInternetGateways": ("ec2", "DescribeInternetGateways"),
    "ec2:DescribeNatGateways": ("ec2", "DescribeNatGateways"),
    "ec2:DescribeNetworkAcls": ("ec2", "DescribeNetworkAcls"),
    "ec2:DescribeRegions": ("ec2", "DescribeRegions"),
    "ec2:DescribeRouteTables": ("ec2", "DescribeRouteTables"),
    "ec2:DescribeSnapshots": ("ec2", "DescribeSnapshots"),
    "ec2:DescribeSecurityGroups": ("ec2", "DescribeSecurityGroups"),
    "ec2:DescribeSubnets": ("ec2", "DescribeSubnets"),
    "ec2:DescribeTransitGatewayAttachments": (
        "ec2",
        "DescribeTransitGatewayAttachments",
    ),
    "ec2:DescribeVolumes": ("ec2", "DescribeVolumes"),
    "ec2:DescribeVpcEndpoints": ("ec2", "DescribeVpcEndpoints"),
    "ec2:DescribeVpcPeeringConnections": ("ec2", "DescribeVpcPeeringConnections"),
    "ec2:DescribeVpcs": ("ec2", "DescribeVpcs"),
    "ecs:DescribeClusters": ("ecs", "DescribeClusters"),
    "ecs:ListClusters": ("ecs", "ListClusters"),
    "ecs:ListContainerInstances": ("ecs", "ListContainerInstances"),
    "ecs:ListServices": ("ecs", "ListServices"),
    "ecs:ListTagsForResource": ("ecs", "ListTagsForResource"),
    "ecs:ListTaskDefinitions": ("ecs", "ListTaskDefinitions"),
    "eks:DescribeCluster": ("eks", "DescribeCluster"),
    "eks:ListAddons": ("eks", "ListAddons"),
    "eks:ListClusters": ("eks", "ListClusters"),
    "eks:ListFargateProfiles": ("eks", "ListFargateProfiles"),
    "eks:ListNodegroups": ("eks", "ListNodegroups"),
    "elasticache:DescribeCacheClusters": ("elasticache", "DescribeCacheClusters"),
    "elasticache:DescribeCacheParameterGroups": (
        "elasticache",
        "DescribeCacheParameterGroups",
    ),
    "elasticache:DescribeCacheSubnetGroups": (
        "elasticache",
        "DescribeCacheSubnetGroups",
    ),
    "elasticache:DescribeReplicationGroups": (
        "elasticache",
        "DescribeReplicationGroups",
    ),
    # Covers both Classic (elb) and v2 (elbv2) DescribeLoadBalancers.
    "elasticloadbalancing:DescribeLoadBalancers": ("elbv2", "DescribeLoadBalancers"),
    "elasticloadbalancing:DescribeTargetGroups": ("elbv2", "DescribeTargetGroups"),
    "events:ListEventBuses": ("events", "ListEventBuses"),
    "events:ListRules": ("events", "ListRules"),
    "glue:GetCrawlers": ("glue", "GetCrawlers"),
    "glue:GetDatabases": ("glue", "GetDatabases"),
    "glue:GetJobs": ("glue", "GetJobs"),
    "glue:GetTables": ("glue", "GetTables"),
    "glue:GetTriggers": ("glue", "GetTriggers"),
    "iam:GetUser": ("iam", "GetUser"),
    "iam:ListAccountAliases": ("iam", "ListAccountAliases"),
    "iam:ListGroups": ("iam", "ListGroups"),
    "iam:ListInstanceProfiles": ("iam", "ListInstanceProfiles"),
    "iam:ListPolicies": ("iam", "ListPolicies"),
    "iam:ListRoleTags": ("iam", "ListRoleTags"),
    "iam:ListRoles": ("iam", "ListRoles"),
    "iam:ListUserTags": ("iam", "ListUserTags"),
    "iam:ListUsers": ("iam", "ListUsers"),
    "kinesis:ListStreams": ("kinesis", "ListStreams"),
    "kms:DescribeKey": ("kms", "DescribeKey"),
    "kms:GetKeyRotationStatus": ("kms", "GetKeyRotationStatus"),
    "kms:ListAliases": ("kms", "ListAliases"),
    "kms:ListKeys": ("kms", "ListKeys"),
    "lambda:GetFunctionConfiguration": ("lambda", "GetFunctionConfiguration"),
    "lambda:ListFunctions": ("lambda", "ListFunctions"),
    "lambda:ListLayers": ("lambda", "ListLayers"),
    "lambda:ListTags": ("lambda", "ListTags"),
    "pricing:GetProducts": ("pricing", "GetProducts"),
    "rds:DescribeDBClusters": ("rds", "DescribeDBClusters"),
    "rds:DescribeDBSnapshots": ("rds", "DescribeDBSnapshots"),
    "rds:DescribeDBSubnetGroups": ("rds", "DescribeDBSubnetGroups"),
    "rds:DescribeDBInstances": ("rds", "DescribeDBInstances"),
    "rds:DescribeDBParameterGroups": ("rds", "DescribeDBParameterGroups"),
    "rds:ListTagsForResource": ("rds", "ListTagsForResource"),
    "redshift:DescribeClusters": ("redshift", "DescribeClusters"),
    "resource-groups:ListGroups": ("resource-groups", "ListGroups"),
    "route53:ListHostedZones": ("route53", "ListHostedZones"),
    # S3 IAM action names differ from the API names they authorise.
    "s3:GetBucketLocation": ("s3", "GetBucketLocation"),
    "s3:GetBucketTagging": ("s3", "GetBucketTagging"),
    "s3:GetEncryptionConfiguration": ("s3", "GetBucketEncryption"),
    "s3:ListAllMyBuckets": ("s3", "ListBuckets"),
    "secretsmanager:ListSecrets": ("secretsmanager", "ListSecrets"),
    "sns:ListPlatformApplications": ("sns", "ListPlatformApplications"),
    "sns:ListSubscriptions": ("sns", "ListSubscriptions"),
    "sns:ListTopics": ("sns", "ListTopics"),
    "sqs:ListQueues": ("sqs", "ListQueues"),
    "ssm:DescribeParameters": ("ssm", "DescribeParameters"),
    "ssm:DescribePatchBaselines": ("ssm", "DescribePatchBaselines"),
    "ssm:ListDocuments": ("ssm", "ListDocuments"),
    "states:ListStateMachines": ("stepfunctions", "ListStateMachines"),
    "tag:GetResources": ("resourcegroupstaggingapi", "GetResources"),
    "wafv2:ListIPSets": ("wafv2", "ListIPSets"),
    "wafv2:ListRuleGroups": ("wafv2", "ListRuleGroups"),
    "wafv2:ListWebACLs": ("wafv2", "ListWebACLs"),
    "workmail:ListOrganizations": ("workmail", "ListOrganizations"),
    # Added in this release: services listed by the table-driven discovery,
    # region discovery (account:ListRegions) and the network/security
    # analyzers (ec2:DescribeNetworkInterfaces).
    "account:ListRegions": ("account", "ListRegions"),
    "appsync:ListGraphqlApis": ("appsync", "ListGraphqlApis"),
    "athena:ListWorkGroups": ("athena", "ListWorkGroups"),
    "autoscaling:DescribeAutoScalingGroups": (
        "autoscaling",
        "DescribeAutoScalingGroups",
    ),
    "backup:ListBackupVaults": ("backup", "ListBackupVaults"),
    "cognito-idp:ListUserPools": ("cognito-idp", "ListUserPools"),
    "ec2:DescribeNetworkInterfaces": ("ec2", "DescribeNetworkInterfaces"),
    "ecr:DescribeRepositories": ("ecr", "DescribeRepositories"),
    "elasticbeanstalk:DescribeApplications": (
        "elasticbeanstalk",
        "DescribeApplications",
    ),
    "elasticbeanstalk:DescribeEnvironments": (
        "elasticbeanstalk",
        "DescribeEnvironments",
    ),
    "elasticfilesystem:DescribeFileSystems": ("efs", "DescribeFileSystems"),
    "elasticmapreduce:ListClusters": ("emr", "ListClusters"),
    "es:ListDomainNames": ("opensearch", "ListDomainNames"),
    "firehose:ListDeliveryStreams": ("firehose", "ListDeliveryStreams"),
    "kafka:ListClustersV2": ("kafka", "ListClustersV2"),
    "redshift-serverless:ListNamespaces": ("redshift-serverless", "ListNamespaces"),
    "redshift-serverless:ListWorkgroups": ("redshift-serverless", "ListWorkgroups"),
}

# API Gateway authorises by HTTP verb on resource paths. Only metadata paths,
# never /apikeys (whose values are readable with includeValues=true).
APIGATEWAY_READ_PATHS: Tuple[str, ...] = (
    "/restapis",
    "/domainnames",
    "/usageplans",
)

# Optional statement for --s3-bucket uploads (attach to the identity that runs
# InvenTag, scoped to the reports bucket/prefix).
S3_UPLOAD_ACTIONS: Tuple[str, ...] = ("s3:PutObject",)


def build_read_only_policy(partition: str = "aws") -> Dict:
    """Return the read-only policy document (a fresh dict each call)."""
    return copy.deepcopy(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "InvenTagReadOnlyDiscovery",
                    "Effect": "Allow",
                    "Action": sorted(READ_ONLY_ACTIONS),
                    "Resource": "*",
                },
                {
                    "Sid": "InvenTagApiGatewayMetadata",
                    "Effect": "Allow",
                    "Action": ["apigateway:GET"],
                    "Resource": [
                        f"arn:{partition}:apigateway:*::{path}"
                        for path in APIGATEWAY_READ_PATHS
                    ],
                },
            ],
        }
    )


def build_s3_upload_statement(
    bucket: str, key_prefix: str = "bom-reports", partition: str = "aws"
) -> Dict:
    """Statement allowing encrypted report uploads to one bucket prefix."""
    prefix = key_prefix.strip("/")
    resource = f"arn:{partition}:s3:::{bucket}/{prefix + '/' if prefix else ''}*"
    return {
        "Sid": "InvenTagReportUpload",
        "Effect": "Allow",
        "Action": list(S3_UPLOAD_ACTIONS),
        "Resource": [resource],
        "Condition": {"Null": {"s3:x-amz-server-side-encryption": "false"}},
    }


def all_policy_actions(policy: Optional[Dict] = None) -> List[str]:
    policy = policy or build_read_only_policy()
    actions: List[str] = []
    for statement in policy["Statement"]:
        value = statement["Action"]
        actions.extend([value] if isinstance(value, str) else value)
    return actions
