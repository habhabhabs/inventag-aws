"""Adversarial tests for the read-only guard.

Each test tries a way to make an AWS call that writes, or that returns
secrets, object contents or a credential, and checks that the guard stops it
before anything leaves the process. Moto or stubbed endpoints only.
"""

import threading

import boto3
import botocore
import pytest
from botocore.config import Config
from moto import mock_aws

from inventag.security.read_only_guard import (
    DENIED_OPERATIONS,
    UNSIGNED_CREDENTIAL_EXCHANGE_OPERATIONS,
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


# ----------------------------------------------------------------- the policy
@pytest.mark.parametrize(
    "service, operation",
    [
        # Writes and actions
        ("ec2", "RunInstances"),
        ("iam", "CreateRole"),
        ("iam", "CreatePolicy"),
        ("iam", "GenerateCredentialReport"),
        ("s3", "PutBucketLifecycleConfiguration"),
        ("ssm", "StartSession"),
        ("ssm", "SendCommand"),
        ("lambda", "Invoke"),
        ("rds", "DownloadDBLogFilePortion"),
        ("logs", "FilterLogEvents"),
        ("logs", "StartQuery"),
        ("kms", "Decrypt"),
        ("kms", "GenerateDataKey"),
        ("s3", "SelectObjectContent"),
        ("dynamodb", "ExecuteStatement"),
        ("sts", "AssumeRoleWithSAML"),
        # Reads that return secrets, credentials or data
        ("secretsmanager", "GetSecretValue"),
        ("secretsmanager", "BatchGetSecretValue"),
        ("ssm", "GetParameter"),
        ("ssm", "GetParameters"),
        ("ssm", "GetParameterHistory"),
        ("ssm", "GetAccessToken"),
        ("s3", "GetObject"),
        ("mediastore-data", "GetObject"),
        ("lambda", "GetFunction"),
        ("ecr", "GetAuthorizationToken"),
        ("ecr-public", "GetAuthorizationToken"),
        ("codeartifact", "GetAuthorizationToken"),
        ("ec2", "GetPasswordData"),
        ("ec2", "GetLaunchTemplateData"),
        ("logs", "GetLogEvents"),
        ("athena", "GetQueryResults"),
        ("cloudformation", "GetTemplate"),
        ("codecommit", "GetFile"),
        ("codecommit", "GetBlob"),
        ("glacier", "GetJobOutput"),
        ("ebs", "GetSnapshotBlock"),
        ("redshift", "GetClusterCredentials"),
        ("redshift-serverless", "GetCredentials"),
        ("s3control", "GetDataAccess"),
        ("lightsail", "GetBucketAccessKeys"),
        ("lightsail", "GetRelationalDatabaseMasterUserPassword"),
        ("cognito-idp", "ListUserPoolClientSecrets"),
        ("storagegateway", "DescribeChapCredentials"),
        ("appsync", "ListApiKeys"),
        ("emr", "GetClusterSessionCredentials"),
        ("glue", "GetSessionEndpoint"),
        ("sts", "GetSessionToken"),
        ("sts", "GetFederationToken"),
        ("sso", "GetRoleCredentials"),
    ],
)
def test_denied_for_an_ordinary_signed_client(service, operation):
    allowed, _ = ReadOnlyGuard().evaluate(service, operation)
    assert allowed is False


@pytest.mark.parametrize(
    "service, operation",
    [
        ("sts", "AssumeRole"),
        ("sts", "GetCallerIdentity"),
        ("iam", "GetCredentialReport"),
        ("cloudformation", "GetTemplateSummary"),
        ("lambda", "GetFunctionConfiguration"),
        ("s3", "GetBucketLifecycleConfiguration"),
        ("ec2", "DescribeInstanceAttribute"),
        ("apigateway", "GetApiKeys"),
    ],
)
def test_inventory_reads_stay_allowed(service, operation):
    allowed, _ = ReadOnlyGuard().evaluate(service, operation)
    assert allowed is True


def test_credential_exchange_is_allowed_only_for_unsigned_clients():
    guard = ReadOnlyGuard()
    for service, operation in UNSIGNED_CREDENTIAL_EXCHANGE_OPERATIONS:
        assert guard.evaluate(service, operation, unsigned=True)[0] is True
        assert guard.evaluate(service, operation, unsigned=False)[0] is False
    # Being unsigned does not open anything else.
    assert guard.evaluate("s3", "PutObject", unsigned=True)[0] is False
    assert guard.evaluate("secretsmanager", "GetSecretValue", unsigned=True)[0] is (
        False
    )


def test_every_denied_rule_is_well_formed():
    for service, operation in DENIED_OPERATIONS:
        assert service == "*" or service == service.lower()
        assert operation[:1].isupper()


@pytest.mark.parametrize(
    "service, operation, params, allowed",
    [
        ("apigateway", "GetApiKey", {"includeValue": "true"}, False),
        ("apigateway", "GetApiKey", {"includeValue": "false"}, True),
        ("apigateway", "GetApiKeys", {"includeValues": "true"}, False),
        ("apigateway", "GetApiKeys", {}, True),
        ("ec2", "DescribeInstanceAttribute", {"Attribute": "userData"}, False),
        ("ec2", "DescribeInstanceAttribute", {"Attribute": "instanceType"}, True),
    ],
)
def test_parameters_that_return_secrets(service, operation, params, allowed):
    assert ReadOnlyGuard().evaluate(service, operation, params=params)[0] is allowed


# ------------------------------------------------- end to end through botocore
def test_ec2_user_data_is_blocked_on_the_wire(aws_env, global_guard):
    uninstall_global_guard()
    # Set up the instance without the guard (RunInstances is a write). A fixed
    # image ID: moto's default AMIs may be switched off by an earlier test
    # (MOTO_EC2_LOAD_DEFAULT_AMIS), and moto accepts any image ID.
    raw = boto3.client("ec2", region_name="us-east-1")
    instance = raw.run_instances(
        ImageId="ami-12c6146b", MinCount=1, MaxCount=1, UserData="password=hunter2"
    )["Instances"][0]["InstanceId"]
    install_global_guard(global_guard)

    ec2 = boto3.client("ec2", region_name="us-east-1")
    ec2.describe_instance_attribute(InstanceId=instance, Attribute="instanceType")
    with pytest.raises(ReadOnlyViolationError) as excinfo:
        ec2.describe_instance_attribute(InstanceId=instance, Attribute="userData")
    assert "Attribute=userData" in str(excinfo.value)


def test_api_gateway_key_values_are_blocked_on_the_wire(aws_env, global_guard):
    apigw = boto3.client("apigateway", region_name="us-east-1")
    apigw.get_api_keys()
    with pytest.raises(ReadOnlyViolationError):
        apigw.get_api_keys(includeValues=True)
    with pytest.raises(ReadOnlyViolationError):
        apigw.get_api_key(apiKey="abc", includeValue=True)


@pytest.mark.parametrize(
    "service, call, kwargs",
    [
        ("secretsmanager", "get_secret_value", {"SecretId": "x"}),
        ("ssm", "get_parameter", {"Name": "x", "WithDecryption": True}),
        ("ssm", "get_parameters", {"Names": ["x"], "WithDecryption": True}),
        ("s3", "get_object", {"Bucket": "b", "Key": "k"}),
        ("kms", "decrypt", {"CiphertextBlob": b"x"}),
        ("lambda", "get_function", {"FunctionName": "f"}),
        ("ecr", "get_authorization_token", {}),
        ("iam", "generate_credential_report", {}),
        ("ssm", "start_session", {"Target": "i-123"}),
        ("ec2", "get_password_data", {"InstanceId": "i-123"}),
        (
            "rds",
            "download_db_log_file_portion",
            {"DBInstanceIdentifier": "d", "LogFileName": "l"},
        ),
        ("logs", "get_log_events", {"logGroupName": "g", "logStreamName": "s"}),
        ("cloudformation", "get_template", {"StackName": "s"}),
        ("iam", "create_role", {"RoleName": "r", "AssumeRolePolicyDocument": "{}"}),
    ],
)
def test_calls_are_blocked_before_reaching_aws(
    aws_env, global_guard, service, call, kwargs
):
    client = boto3.client(service, region_name="us-east-1")
    with pytest.raises(ReadOnlyViolationError):
        getattr(client, call)(**kwargs)
    assert global_guard.audit_report()["blocked_calls"] == 1


def test_sts_assume_role_is_allowed(aws_env, global_guard):
    sts = boto3.client("sts", region_name="us-east-1")
    creds = sts.assume_role(
        RoleArn="arn:aws:iam::123456789012:role/R", RoleSessionName="inventag-test"
    )["Credentials"]
    assert creds["AccessKeyId"]


def test_clients_made_in_threads_and_from_assumed_role_sessions_are_guarded(
    aws_env, global_guard
):
    errors = []

    def worker():
        sts = boto3.Session().client("sts", region_name="us-east-1")
        temp = sts.assume_role(
            RoleArn="arn:aws:iam::123456789012:role/R", RoleSessionName="inventag-test"
        )["Credentials"]
        assumed = boto3.Session(
            aws_access_key_id=temp["AccessKeyId"],
            aws_secret_access_key=temp["SecretAccessKey"],
            aws_session_token=temp["SessionToken"],
        )
        for client in (
            assumed.client("s3", region_name="us-east-1"),
            assumed.resource("s3", region_name="us-east-1").meta.client,
        ):
            try:
                client.create_bucket(Bucket="must-not-exist")
            except ReadOnlyViolationError as e:
                errors.append(e)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert len(errors) == 2


def test_unsigned_client_cannot_call_secret_reads(aws_env, global_guard):
    client = boto3.client(
        "secretsmanager",
        region_name="us-east-1",
        config=Config(signature_version=botocore.UNSIGNED),
    )
    with pytest.raises(ReadOnlyViolationError):
        client.get_secret_value(SecretId="x")


# ------------------------------------------------------- local signing methods
def test_presigned_urls_follow_the_same_rules(aws_env, global_guard):
    s3 = boto3.client("s3", region_name="us-east-1")
    # A presigned read of bucket metadata is fine...
    assert s3.generate_presigned_url("list_buckets").startswith("https://")
    # ...but a presigned download or upload URL is a credential for that call.
    with pytest.raises(ReadOnlyViolationError):
        s3.generate_presigned_url(
            "get_object", Params={"Bucket": "b", "Key": "k"}, ExpiresIn=60
        )
    with pytest.raises(ReadOnlyViolationError):
        s3.generate_presigned_url(
            ClientMethod="put_object", Params={"Bucket": "b", "Key": "k"}
        )
    with pytest.raises(ReadOnlyViolationError):
        s3.generate_presigned_post("b", "k")


def test_presigned_put_is_allowed_on_the_upload_client_only(aws_env, global_guard):
    uploader = boto3.client("s3", region_name="us-east-1")
    ReadOnlyGuard.allow_on_client(uploader, {"PutObject"})
    uploader.generate_presigned_url("put_object", Params={"Bucket": "b", "Key": "k"})
    other = boto3.client("s3", region_name="us-east-1")
    with pytest.raises(ReadOnlyViolationError):
        other.generate_presigned_url("put_object", Params={"Bucket": "b", "Key": "k"})


def test_database_auth_tokens_are_blocked(aws_env, global_guard):
    rds = boto3.client("rds", region_name="us-east-1")
    with pytest.raises(ReadOnlyViolationError):
        rds.generate_db_auth_token("db.example.com", 5432, "admin")


def test_without_the_guard_presigning_is_unchanged(aws_env):
    uninstall_global_guard()
    s3 = boto3.client("s3", region_name="us-east-1")
    assert "Signature=" in s3.generate_presigned_url(
        "get_object", Params={"Bucket": "b", "Key": "k"}
    )


# ------------------------------------------- sign-in through credential providers
class _Sent(Exception):
    """Raised by the fake HTTP layer: the request got past the guard."""


@pytest.fixture
def sso_and_web_identity_profiles(tmp_path, monkeypatch):
    import datetime
    import hashlib
    import json

    start_url = "https://example.awsapps.com/start"
    cache = tmp_path / ".aws" / "sso" / "cache"
    cache.mkdir(parents=True)
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    (cache / (hashlib.sha1(start_url.encode()).hexdigest() + ".json")).write_text(
        json.dumps(
            {
                "startUrl": start_url,
                "region": "us-east-1",
                "accessToken": "x" * 40,
                "expiresAt": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    )
    token_file = tmp_path / "token"
    token_file.write_text("header.payload.signature")
    config = tmp_path / ".aws" / "config"
    config.write_text(f"""[profile sso]
sso_start_url = {start_url}
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = ReadOnly
region = us-east-1
[profile wi]
role_arn = arn:aws:iam::123456789012:role/WebIdentity
web_identity_token_file = {token_file}
region = us-east-1
""")
    monkeypatch.setenv("HOME", str(tmp_path))
    # botocore reads the SSO cache path once, at import time.
    monkeypatch.setattr(
        "botocore.credentials.SSOProvider._SSO_TOKEN_CACHE_DIR", str(cache)
    )
    monkeypatch.setattr(
        "botocore.tokens.SSOTokenProvider._SSO_TOKEN_CACHE_DIR", str(cache)
    )
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "none"))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE"):
        monkeypatch.delenv(name, raising=False)

    sent = []

    def fake_send(self, request):
        sent.append(request.url)
        raise _Sent(request.url)

    monkeypatch.setattr("botocore.httpsession.URLLib3Session.send", fake_send)
    return sent


@pytest.mark.parametrize("profile", ["sso", "wi"])
def test_sso_and_web_identity_sign_in_pass_the_guard(
    sso_and_web_identity_profiles, global_guard, profile
):
    session = boto3.Session(profile_name=profile)
    with pytest.raises(_Sent):
        session.get_credentials().get_frozen_credentials()
    assert sso_and_web_identity_profiles, "the sign-in request was not sent"
    assert global_guard.audit_report()["blocked_calls"] == 0
