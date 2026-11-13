"""Client retry settings and per-region detail calls in comprehensive discovery."""

import io
import zipfile

import boto3
import pytest
from moto import mock_aws

from inventag.discovery import aws_clients
from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery


@pytest.fixture
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_RETRY_MODE", raising=False)
    monkeypatch.delenv("AWS_MAX_ATTEMPTS", raising=False)
    with mock_aws():
        yield


def test_clients_use_standard_retry_mode_with_ten_attempts(aws_env):
    client = aws_clients.create_client(boto3.Session(), "ec2", "eu-west-1")
    retries = client.meta.config.retries
    assert retries["mode"] == "standard"
    assert retries["total_max_attempts"] == 10
    assert client.meta.region_name == "eu-west-1"


def test_user_retry_environment_wins(aws_env, monkeypatch):
    monkeypatch.setenv("AWS_RETRY_MODE", "adaptive")
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "3")
    client = aws_clients.create_client(boto3.Session(), "s3")
    assert client.meta.config.retries["mode"] == "adaptive"
    assert client.meta.config.retries["total_max_attempts"] == 3


def test_comprehensive_discovery_clients_get_the_shared_settings(aws_env):
    disc = ComprehensiveAWSDiscovery(regions=["us-east-1"])
    assert disc._client("sqs", "us-east-1").meta.config.retries["mode"] == "standard"


def _zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.py", "def h(e, c):\n    return 1\n")
    return buf.getvalue()


def test_same_named_functions_keep_their_own_region(aws_env):
    """A function was read in every region; the last region won."""
    role = boto3.client("iam").create_role(
        RoleName="fn-role", AssumeRolePolicyDocument="{}"
    )["Role"]["Arn"]
    resources = []
    for region, memory in (("us-east-1", 128), ("eu-west-1", 256)):
        fn = boto3.client("lambda", region_name=region).create_function(
            FunctionName="same-name",
            Runtime="python3.12",
            Role=role,
            Handler="a.h",
            Code={"ZipFile": _zip()},
            MemorySize=memory,
        )
        resources.append(
            {
                "service": "LAMBDA",
                "resource_type": "Function",
                "resource_id": "same-name",
                "region": region,
                "arn": fn["FunctionArn"],
                "raw_data": {},
            }
        )

    disc = ComprehensiveAWSDiscovery(
        regions=["us-east-1", "eu-west-1"], enable_billing_validation=False
    )
    disc.resources = resources
    disc._enhance_lambda_functions()

    by_region = {r["region"]: r for r in disc.resources}
    assert set(by_region) == {"us-east-1", "eu-west-1"}
    assert by_region["us-east-1"]["raw_data"]["memory_size"] == 128
    assert by_region["eu-west-1"]["raw_data"]["memory_size"] == 256
    assert by_region["eu-west-1"]["raw_data"]["boto3_config"]["FunctionArn"] == (
        by_region["eu-west-1"]["arn"]
    )
