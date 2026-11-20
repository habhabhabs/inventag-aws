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
import functools
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


# ---------------------------------------------------------------------------
# From a call to the IAM action it needs (W2, the permissions summary of a run).
#
# The coverage ledger names a call by the discovery table's key and operation:
# the key is not always a botocore service name ("msk" is read with the "kafka"
# client) and the operation is not always the API name ("list_clusters_v2").
# ``action_for`` turns either form into the IAM action, from the tables of this
# module only. It never guesses: a call it has no action for gives None.
# ---------------------------------------------------------------------------

# Discovery table keys whose client is another botocore service. A test keeps
# this equal to the ``client_service`` entries of the table.
LEDGER_CLIENT_SERVICES: Dict[str, str] = {
    "cognito": "cognito-idp",
    "msk": "kafka",
    "vpc": "ec2",
    "wafv2-cloudfront": "wafv2",
}

# Listings that read a parent listing first (table entries with ``per_parent``):
# (child service, API name) -> (parent service, API name). When the parent is
# refused the child never runs, yet the ledger records the child as refused. A
# test keeps this equal to the table.
PARENT_LISTINGS: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("ecs", "ListServices"): ("ecs", "ListClusters"),
}

# Calls that need an action which ``READ_ONLY_ACTIONS`` does not key by that
# call: the classic load balancer API shares the action of the v2 API, and the
# identity and upload calls are outside the read-only policy file.
_OTHER_ACTIONS: Dict[Tuple[str, str], str] = {
    ("elb", "DescribeLoadBalancers"): "elasticloadbalancing:DescribeLoadBalancers",
    ("sts", "GetCallerIdentity"): "sts:GetCallerIdentity",
    ("sts", "AssumeRole"): "sts:AssumeRole",
    ("s3", "PutObject"): "s3:PutObject",
}

_APIGATEWAY_SERVICES = ("apigateway", "apigatewayv2")

_ACTION_OF_CALL: Dict[Tuple[str, str], str] = {
    target: action for action, target in READ_ONLY_ACTIONS.items()
}
_ACTION_OF_CALL.update(_OTHER_ACTIONS)

# The actions of InvenTag that the AWS managed policy ``ReadOnlyAccess`` does
# not include, each with the one feature that needs it. Everything else in
# ``all_policy_actions()`` and ``sts:GetCallerIdentity`` it includes (checked
# against the policy text, see tests/data/aws-managed/SOURCE.json). A test keeps
# this table equal to that fixture. The application does not carry AWS's policy.
NOT_IN_READONLYACCESS: Dict[str, str] = {
    "sts:AssumeRole": "scanning other accounts through a role",
    "s3:PutObject": "uploading the reports (--s3-bucket)",
    "kms:GenerateDataKey": "uploading the reports with a KMS key (--s3-bucket)",
}


@functools.lru_cache(maxsize=None)
def _botocore_session():
    import botocore.session

    return botocore.session.get_session()


@functools.lru_cache(maxsize=None)
def _api_name(service: str, operation: str) -> Optional[str]:
    """The botocore API name of ``operation`` (``list_buckets`` -> ``ListBuckets``).

    None when botocore has no such service or operation.
    """
    from botocore import xform_name
    from botocore.exceptions import BotoCoreError

    try:
        model = _botocore_session().get_service_model(service)
    except BotoCoreError:
        return None
    names = model.operation_names
    if operation in names:
        return operation
    for name in names:
        if xform_name(name) == operation:
            return name
    return None


def botocore_call(service: str, operation: str) -> Optional[Tuple[str, str]]:
    """(botocore service name, API name) of a ledger key and operation, or None.

    ``botocore_call("msk", "list_clusters_v2")`` is ``("kafka", "ListClustersV2")``.
    """
    if not service or not operation:
        return None
    service = LEDGER_CLIENT_SERVICES.get(service, service)
    api = _api_name(service, operation)
    return None if api is None else (service, api)


def action_for(service: str, operation: str) -> Optional[str]:
    """The IAM action a call needs, or None when InvenTag does not know it.

    ``service`` is a botocore service name or a key of the discovery table;
    ``operation`` is the API name or its snake_case form.
    """
    call = botocore_call(service, operation)
    if call is None:
        return None
    if call[0] in _APIGATEWAY_SERVICES and call[1].startswith("Get"):
        return "apigateway:GET"  # API Gateway authorises by HTTP verb
    return _ACTION_OF_CALL.get(call)


def in_readonlyaccess(action: str) -> Optional[bool]:
    """Whether ``ReadOnlyAccess`` includes ``action``; None when InvenTag has not checked."""
    if action in NOT_IN_READONLYACCESS:
        return False
    if action == "sts:GetCallerIdentity" or action in all_policy_actions():
        return True
    return None
