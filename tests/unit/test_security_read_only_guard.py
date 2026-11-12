"""Tests for the read-only guard (botocore before-call hook)."""

import boto3
import pytest
from moto import mock_aws

from inventag.cli import safety
from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    install_global_guard,
    uninstall_global_guard,
)


@pytest.fixture
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


@pytest.fixture
def global_guard():
    uninstall_global_guard()
    guard = install_global_guard(ReadOnlyGuard())
    yield guard
    uninstall_global_guard()


@pytest.mark.parametrize(
    "service, operation, allowed",
    [
        ("ec2", "DescribeInstances", True),
        ("s3", "ListBuckets", True),
        ("s3", "GetBucketTagging", True),
        ("s3", "HeadBucket", True),
        ("cloudtrail", "LookupEvents", True),
        ("resourcegroupstaggingapi", "GetResources", True),
        ("dynamodb", "BatchGetItem", False),
        ("sts", "GetCallerIdentity", True),
        ("sts", "AssumeRole", True),
        ("ec2", "TerminateInstances", False),
        ("ec2", "RunInstances", False),
        ("s3", "PutObject", False),
        ("s3", "DeleteBucket", False),
        ("s3", "PutBucketLifecycleConfiguration", False),
        ("iam", "CreateRole", False),
        ("iam", "AttachRolePolicy", False),
        ("config", "DeleteConfigRule", False),
        ("config", "StopConfigurationRecorder", False),
        ("resource-groups", "DeleteGroup", False),
        ("dynamodb", "Scan", False),
        ("dynamodb", "Query", False),
        ("secretsmanager", "GetSecretValue", False),
        ("ssm", "GetParameter", False),
        ("ssm", "GetParametersByPath", False),
        ("ecr", "GetAuthorizationToken", False),
        ("sts", "GetSessionToken", False),
        ("lambda", "GetFunction", False),
        ("lambda", "GetFunctionConfiguration", True),
        ("s3", "GetObject", False),
        ("ec2", "GetPasswordData", False),
        ("ec2", "DescribeRegions", True),
    ],
)
def test_policy(service, operation, allowed):
    assert ReadOnlyGuard().evaluate(service, operation)[0] is allowed


def test_write_call_is_blocked_before_reaching_aws(aws_env, global_guard):
    s3 = boto3.client("s3", region_name="us-east-1")
    with pytest.raises(ReadOnlyViolationError) as excinfo:
        s3.create_bucket(Bucket="should-not-exist")
    assert "s3:CreateBucket" in str(excinfo.value)
    # Bypass the guard to check the bucket really was not created.
    uninstall_global_guard()
    raw = boto3.client("s3", region_name="us-east-1")
    assert raw.list_buckets()["Buckets"] == []


def test_read_calls_pass_and_are_audited(aws_env, global_guard):
    boto3.client("ec2", region_name="us-east-1").describe_regions()
    boto3.Session().client("s3").list_buckets()
    report = global_guard.audit_report()
    ops = {(o["service"], o["operation"], o["allowed"]) for o in report["operations"]}
    assert ("ec2", "DescribeRegions", True) in ops
    assert ("s3", "ListBuckets", True) in ops
    assert report["blocked_calls"] == 0


def test_blocked_calls_are_audited(aws_env, global_guard):
    ec2 = boto3.client("ec2", region_name="us-east-1")
    with pytest.raises(ReadOnlyViolationError):
        ec2.create_vpc(CidrBlock="10.0.0.0/16")
    report = global_guard.audit_report()
    assert report["blocked_calls"] == 1
    assert report["blocked"][0]["operation"] == "CreateVpc"
    assert report["blocked"][0]["region"] == "us-east-1"


def test_per_client_allowance_does_not_leak_to_other_clients(aws_env):
    uninstall_global_guard()
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="reports")
    guard = install_global_guard(ReadOnlyGuard())
    try:
        uploader = boto3.client("s3", region_name="us-east-1")
        ReadOnlyGuard.allow_on_client(uploader, {"PutObject"})
        uploader.put_object(Bucket="reports", Key="k", Body=b"x")
        other = boto3.client("s3", region_name="us-east-1")
        with pytest.raises(ReadOnlyViolationError):
            other.put_object(Bucket="reports", Key="k2", Body=b"x")
        with pytest.raises(ReadOnlyViolationError):
            uploader.delete_object(Bucket="reports", Key="k")
    finally:
        uninstall_global_guard()
    assert guard.audit_report()["blocked_calls"] == 2


def test_attach_session_guards_clients_from_that_session(aws_env):
    session = boto3.Session()
    ReadOnlyGuard().attach_session(session)
    with pytest.raises(ReadOnlyViolationError):
        session.client("sqs").create_queue(QueueName="q")
    session.client("sqs").list_queues()


def test_discovery_under_guard_makes_no_write_calls(aws_env, global_guard):
    """Run the real discovery against moto; every call must be read-only."""
    from inventag.discovery.inventory import AWSResourceInventory

    uninstall_global_guard()
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="data")
    guard = install_global_guard(ReadOnlyGuard())
    inventory = AWSResourceInventory(regions=["us-east-1"])
    inventory.discover_resources()
    report = guard.audit_report()
    assert report["total_calls"] > 0
    assert report["blocked_calls"] == 0, report["blocked"]


@pytest.mark.parametrize(
    "ops, expected_ok",
    [
        (["ec2:DescribeInstances", "s3:ListBuckets"], True),
        (["ec2:describe_instances"], True),
        (["ec2:DescribeInstances", "s3:DeleteBucket"], False),
        (["not-a-valid-entry"], False),
    ],
)
def test_validate_operations(ops, expected_ok):
    ok, lines = safety.validate_operations(ops)
    assert ok is expected_ok
    assert len(lines) == len(ops)
