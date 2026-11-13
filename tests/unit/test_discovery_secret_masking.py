"""Discovery must not keep values that can hold secrets."""

import io
import json
import zipfile

import boto3
import pytest
from moto import mock_aws

from inventag.discovery.sensitive_fields import MASK, mask_secret_values

PLANTED = "planted-secret-value-7f3a"


@pytest.mark.parametrize(
    "data, path",
    [
        ({"Environment": {"Variables": {"DB_PASS": PLANTED}}}, "lambda env"),
        (
            {
                "containerDefinitions": [
                    {"environment": [{"name": "K", "value": PLANTED}]}
                ]
            },
            "ecs env",
        ),
        (
            {
                "environment": {
                    "environmentVariables": [{"name": "K", "value": PLANTED}]
                }
            },
            "codebuild env without type",
        ),
        (
            {
                "environmentVariables": [
                    {"name": "K", "value": PLANTED, "type": "PLAINTEXT"}
                ]
            },
            "codebuild plaintext",
        ),
        ({"UserData": PLANTED}, "user data string"),
        ({"UserData": {"Value": PLANTED}}, "user data attribute"),
        ({"Parameters": [{"ParameterKey": "P", "ParameterValue": PLANTED}]}, "cfn"),
        ({"DefaultArguments": {"--password": PLANTED}}, "glue job"),
        ({"NonOverridableArguments": {"--token": PLANTED}}, "glue job 2"),
        ({"ConnectionProperties": {"PASSWORD": PLANTED}}, "glue connection"),
        ({"stateMachineArn": "arn:x", "definition": PLANTED}, "step functions"),
        ({"Code": {"Location": PLANTED}}, "lambda code url"),
        ({"id": "k1", "enabled": True, "value": PLANTED}, "api key"),
        ({"MasterUserPassword": PLANTED}, "rds password"),
        ({"ClientSecret": PLANTED}, "cognito client secret"),
        ({"SecretString": PLANTED}, "secret string"),
        (
            {"nested": [{"deeper": {"Environment": {"Variables": {"X": PLANTED}}}}]},
            "nested",
        ),
    ],
)
def test_secret_fields_are_masked(data, path):
    masked = mask_secret_values(data)
    assert PLANTED not in json.dumps(masked), path
    assert MASK in json.dumps(masked)
    # The input is not modified
    assert PLANTED in json.dumps(data)


def test_key_names_and_other_fields_are_kept():
    data = {
        "FunctionName": "fn",
        "Environment": {"Variables": {"DB_URL": PLANTED}},
        "environmentVariables": [
            {"name": "SSM_REF", "value": "/my/param", "type": "PARAMETER_STORE"}
        ],
        "Parameters": [{"ParameterKey": "Env", "ParameterValue": PLANTED}],
    }
    masked = mask_secret_values(data)
    assert masked["FunctionName"] == "fn"
    assert masked["Environment"]["Variables"] == {"DB_URL": MASK}
    # A reference to a parameter, not a value, is kept
    assert masked["environmentVariables"][0]["value"] == "/my/param"
    assert masked["Parameters"][0]["ParameterKey"] == "Env"


TEMPLATE = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Parameters": {"DbPassword": {"Type": "String"}},
    "Resources": {"Q": {"Type": "AWS::SQS::Queue"}},
}


@pytest.fixture
def account_with_planted_secrets(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        role = boto3.client("iam").create_role(
            RoleName="fn-role", AssumeRolePolicyDocument="{}"
        )["Role"]["Arn"]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.py", "def h(e, c):\n    return 1\n")
        boto3.client("lambda").create_function(
            FunctionName="fn-with-secret",
            Runtime="python3.12",
            Role=role,
            Handler="a.h",
            Code={"ZipFile": buf.getvalue()},
            Environment={"Variables": {"DB_PASSWORD": PLANTED}},
        )
        boto3.client("cloudformation").create_stack(
            StackName="stack-with-secret",
            TemplateBody=json.dumps(TEMPLATE),
            Parameters=[{"ParameterKey": "DbPassword", "ParameterValue": PLANTED}],
        )
        boto3.client("glue").create_job(
            Name="job-with-secret",
            Role=role,
            Command={"Name": "glueetl", "ScriptLocation": "s3://b/s.py"},
            DefaultArguments={"--db-password": PLANTED},
        )
        boto3.client("ec2").run_instances(
            ImageId="ami-12c6146b", MinCount=1, MaxCount=1, UserData=PLANTED
        )
        yield


def test_full_inventory_has_no_planted_secret(account_with_planted_secrets):
    from inventag.discovery.inventory import AWSResourceInventory

    resources = AWSResourceInventory(
        regions=["us-east-1"], enable_billing_validation=False
    ).discover_resources()
    names = {r.get("id") for r in resources}
    assert {"fn-with-secret", "stack-with-secret", "job-with-secret"} <= names
    assert PLANTED not in json.dumps(resources, default=str)
    fn = next(r for r in resources if r.get("id") == "fn-with-secret")
    assert fn["raw_data"]["Environment"]["Variables"] == {"DB_PASSWORD": MASK}
