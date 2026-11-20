"""W2 of reports/v14-plan-readonlyaccess.md: say exactly which IAM action was missing.

Part 1 (this commit): ``iam_policy.action_for`` and the table of what ``ReadOnlyAccess`` does
and does not include. Part 2 (``inventag/security/permissions_report.py``) is added in the
commits that follow.

The fixture of the AWS managed policy (``tests/data/aws-managed/ReadOnlyAccess.json``) is
PROVISIONAL until the raw copy replaces it (``SOURCE.json`` says how). Not verified against
real AWS.
"""

import boto3
import pytest
from moto import mock_aws

from inventag.security.iam_policy import (
    LEDGER_CLIENT_SERVICES,
    NOT_IN_READONLYACCESS,
    READ_ONLY_ACTIONS,
    action_for,
    all_policy_actions,
    in_readonlyaccess,
)
from tests.policy_sim import matches_any, read_only_access_actions

GATEWAY = "apigateway:GET"


# ------------------------------------------------------------------------ action_for
@pytest.mark.parametrize(
    "service, operation, action",
    [
        # botocore names, as the guard and the ledger's detail records write them
        ("ec2", "DescribeVpcs", "ec2:DescribeVpcs"),
        ("lambda", "GetFunctionConfiguration", "lambda:GetFunctionConfiguration"),
        ("s3", "GetBucketLocation", "s3:GetBucketLocation"),
        ("resourcegroupstaggingapi", "GetResources", "tag:GetResources"),
        ("ce", "GetCostAndUsage", "ce:GetCostAndUsage"),
        ("pricing", "GetProducts", "pricing:GetProducts"),
        ("cloudwatch", "GetMetricStatistics", "cloudwatch:GetMetricStatistics"),
        # an IAM action whose name differs from the API name
        ("s3", "ListBuckets", "s3:ListAllMyBuckets"),
        ("s3", "GetBucketEncryption", "s3:GetEncryptionConfiguration"),
        ("stepfunctions", "ListStateMachines", "states:ListStateMachines"),
        ("efs", "DescribeFileSystems", "elasticfilesystem:DescribeFileSystems"),
        ("emr", "ListClusters", "elasticmapreduce:ListClusters"),
        ("opensearch", "ListDomainNames", "es:ListDomainNames"),
        # the ledger's snake_case operation names (the table writes them that way)
        ("ec2", "describe_vpcs", "ec2:DescribeVpcs"),
        ("s3", "list_buckets", "s3:ListAllMyBuckets"),
        ("kafka", "list_clusters_v2", "kafka:ListClustersV2"),
        # the ledger's service keys that are not botocore names
        ("vpc", "describe_subnets", "ec2:DescribeSubnets"),
        ("msk", "list_clusters_v2", "kafka:ListClustersV2"),
        ("cognito", "list_user_pools", "cognito-idp:ListUserPools"),
        ("wafv2-cloudfront", "list_web_acls", "wafv2:ListWebACLs"),
        # the classic and the v2 load balancer API share one IAM action
        (
            "elb",
            "describe_load_balancers",
            "elasticloadbalancing:DescribeLoadBalancers",
        ),
        ("elbv2", "DescribeTargetGroups", "elasticloadbalancing:DescribeTargetGroups"),
        # API Gateway authorises by HTTP verb
        ("apigateway", "get_rest_apis", GATEWAY),
        ("apigatewayv2", "GetApis", GATEWAY),
        # what is not in the policy file, and that ReadOnlyAccess may or may not include
        ("sts", "GetCallerIdentity", "sts:GetCallerIdentity"),
        ("sts", "AssumeRole", "sts:AssumeRole"),
        ("s3", "PutObject", "s3:PutObject"),
    ],
)
def test_action_for_names_the_iam_action_of_a_call(service, operation, action):
    assert action_for(service, operation) == action


@pytest.mark.parametrize(
    "service, operation",
    [
        (
            "iam",
            "GetAccountSummary",
        ),  # a real operation that InvenTag has no action for
        ("lambda", "delete_function"),  # a write: never an action of InvenTag
        ("ec2", "NoSuchOperation"),
        ("nosuchservice", "ListThings"),
        ("ec2", ""),  # a ledger entry that names a service but no operation
        ("", "DescribeVpcs"),
        ("ec2", None),
    ],
)
def test_action_for_is_none_when_the_action_is_not_known_and_never_guessed(
    service, operation
):
    assert action_for(service, operation) is None


def test_action_for_agrees_with_the_policy_file_for_every_action_in_it():
    for action, (service, operation) in READ_ONLY_ACTIONS.items():
        # the one action that two APIs share is answered by either
        assert action_for(service, operation) == action


def _discovery_table():
    """The discovery table of a ComprehensiveAWSDiscovery: key -> its configuration."""
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    with mock_aws():
        discovery = ComprehensiveAWSDiscovery(
            session=boto3.Session(region_name="us-east-1"), regions=["us-east-1"]
        )
        return discovery, discovery.service_discovery_patterns


def test_every_entry_of_the_discovery_table_maps_to_an_action_of_the_policy_file():
    """Ledger key and operation of each table entry give an action InvenTag's policy lists."""
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    _, table = _discovery_table()
    assert len(table) > 40, "the discovery table was not read"
    policy = set(all_policy_actions())
    unmapped = []
    for key, config in sorted(table.items()):
        for operation_config in config["operations"]:
            spec = ComprehensiveAWSDiscovery._op_spec(operation_config)
            operations = [spec["op"]]
            if spec.get("per_parent"):
                operations.append(spec["per_parent"]["op"])
            for operation in operations:
                action = action_for(key, operation)
                if action not in policy:
                    unmapped.append((key, operation, action))
    assert not unmapped, (
        "table entries whose IAM action is unknown or not in READ_ONLY_ACTIONS: "
        f"{unmapped}"
    )


def test_the_ledger_services_that_are_not_botocore_names_are_exactly_those_of_the_table():
    """LEDGER_CLIENT_SERVICES holds every key whose client differs, and nothing else."""
    _, table = _discovery_table()
    different = {
        key: config["client_service"]
        for key, config in table.items()
        if config.get("client_service", key) != key
    }
    assert LEDGER_CLIENT_SERVICES == different


# ------------------------------------------------------------- what ReadOnlyAccess has
def test_the_three_actions_that_readonlyaccess_does_not_include_are_the_planned_three():
    assert set(NOT_IN_READONLYACCESS) == {
        "sts:AssumeRole",
        "s3:PutObject",
        "kms:GenerateDataKey",
    }
    for action, feature in NOT_IN_READONLYACCESS.items():
        assert feature and feature == feature.strip()
        assert in_readonlyaccess(action) is False


def test_provisional_the_table_agrees_with_the_readonlyaccess_fixture():
    """``in_readonlyaccess`` says what the fixture says, for every action InvenTag knows."""
    allow = read_only_access_actions()
    known = set(all_policy_actions()) | {"sts:GetCallerIdentity"}
    for action in sorted(known):
        assert in_readonlyaccess(action) is True, action
        assert matches_any(action, allow), f"the fixture does not grant {action}"
    for action in sorted(NOT_IN_READONLYACCESS):
        assert not matches_any(action, allow), f"the fixture grants {action}"


def test_in_readonlyaccess_does_not_answer_for_an_action_it_has_not_checked():
    assert in_readonlyaccess("newservice:ListThings") is None
    assert in_readonlyaccess("") is None
