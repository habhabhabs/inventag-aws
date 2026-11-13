"""Release-gate review: the published read-only IAM policy."""

from unittest.mock import MagicMock

import botocore.session
import pytest
from botocore import xform_name

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.security.iam_policy import READ_ONLY_ACTIONS, build_read_only_policy
from inventag.security.read_only_guard import ReadOnlyGuard

# Actions that read data or secrets rather than inventory metadata.
CONTENT_ACTIONS = {
    "s3:GetObject",
    "s3:GetObjectVersion",
    "secretsmanager:GetSecretValue",
    "ssm:GetParameter",
    "ssm:GetParameters",
    "ssm:GetParametersByPath",
    "ssm:GetParameterHistory",
    "kms:Decrypt",
    "lambda:GetFunction",
    "logs:GetLogEvents",
    "logs:FilterLogEvents",
    "cloudformation:GetTemplate",
    "cloudtrail:LookupEvents",
    "dynamodb:GetItem",
    "dynamodb:Scan",
    "dynamodb:Query",
    "ec2:GetPasswordData",
    "ec2:GetConsoleOutput",
    "ec2:DescribeInstanceAttribute",
    "ec2:GetLaunchTemplateData",
    "glue:GetConnection",
    "glue:GetConnections",
    "athena:GetQueryResults",
}


def test_no_action_grants_content_and_every_action_is_a_guarded_read():
    assert not (set(READ_ONLY_ACTIONS) & CONTENT_ACTIONS)
    guard = ReadOnlyGuard()
    for action, (service, operation) in READ_ONLY_ACTIONS.items():
        assert botocore.session.get_session().get_service_model(service)
        assert guard.evaluate(service, operation)[0], action
    for statement in build_read_only_policy()["Statement"]:
        assert statement["Effect"] == "Allow"
        assert all("*" not in a for a in statement["Action"])


def test_every_table_operation_of_a_default_scan_is_in_the_policy():
    discovery = ComprehensiveAWSDiscovery.__new__(ComprehensiveAWSDiscovery)
    discovery.__init__(session=MagicMock())
    authorised = set(READ_ONLY_ACTIONS.values())
    bs = botocore.session.get_session()
    missing = []
    for name, cfg in discovery.service_discovery_patterns.items():
        client_service = cfg.get("client_service", name)
        model = bs.get_service_model(client_service)
        ops = {xform_name(o): o for o in model.operation_names}
        for op in cfg["operations"]:
            spec = discovery._op_spec(op)
            operation = ops[spec["op"]]
            if client_service == "apigateway":
                continue  # authorised by apigateway:GET on /restapis
            # Classic and v2 load balancers share elasticloadbalancing:* actions.
            key = ("elbv2" if client_service == "elb" else client_service, operation)
            if key not in authorised:
                missing.append(f"{client_service}:{operation}")
    assert not missing, missing


def test_policy_size():
    assert len(READ_ONLY_ACTIONS) == 122
