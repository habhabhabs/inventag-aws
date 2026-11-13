"""Release-gate review: adversarial checks of the read-only guard."""

import threading

import boto3
import botocore
import pytest
from botocore.config import Config
from botocore.stub import Stubber

from inventag.security import read_only_guard as rog
from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    check_client_call,
    install_global_guard,
    uninstall_global_guard,
)


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture
def guard(creds):
    uninstall_global_guard()
    g = install_global_guard(ReadOnlyGuard())
    yield g
    uninstall_global_guard()


# ---------------------------------------------------- check_client_call
@pytest.mark.parametrize(
    "service,method,allowed",
    [
        ("ssm", "describe_parameters", True),
        ("ssm", "get_parameter", False),
        ("ssm", "get_parameters_by_path", False),
        ("secretsmanager", "get_secret_value", False),
        ("cloudformation", "get_template", False),
        ("lambda", "get_function", False),
        ("dynamodb", "scan", False),
        ("dynamodb", "query", False),
        ("s3", "select_object_content", False),
        ("s3", "put_object", False),
        ("s3", "get_bucket_location", True),
        ("s3", "not_an_operation", False),
    ],
)
def test_check_client_call_applies_the_policy_without_a_global_guard(
    creds, service, method, allowed
):
    uninstall_global_guard()
    client = boto3.client(service, region_name="us-east-1")
    assert check_client_call(client, method)[0] is allowed


def test_check_client_call_on_a_non_client():
    assert check_client_call(object(), "get_parameter") == (False, "not an AWS client")


# ------------------------------------------------------- where the guard sits
def _blocked(client, call):
    with pytest.raises(ReadOnlyViolationError):
        call(client)


def test_clients_from_threads_resources_and_new_sessions_are_guarded(guard):
    errors = []

    def worker():
        try:
            _blocked(
                boto3.Session().client("s3"), lambda c: c.delete_bucket(Bucket="b")
            )
        except BaseException as e:  # pragma: no cover - reported below
            errors.append(e)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert not errors
    _blocked(
        boto3.resource("s3").meta.client, lambda c: c.put_object(Bucket="b", Key="k")
    )
    _blocked(
        botocore.session.get_session().create_client("iam", region_name="us-east-1"),
        lambda c: c.create_user(UserName="u"),
    )
    # A session built from static (for example assumed-role) credentials.
    assumed = boto3.Session(
        aws_access_key_id="ASIAEXAMPLE",
        aws_secret_access_key="x",
        aws_session_token="t",
        region_name="us-east-1",
    )
    _blocked(
        assumed.client("ec2"), lambda c: c.terminate_instances(InstanceIds=["i-1"])
    )


@pytest.mark.parametrize(
    "service,call",
    [
        ("pricing", lambda c: c.get_products(ServiceCode="AmazonEC2")),
        (
            "ce",
            lambda c: c.get_cost_and_usage(
                TimePeriod={"Start": "2026-01-01", "End": "2026-02-01"},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            ),
        ),
        ("accessanalyzer", lambda c: c.list_analyzers()),
    ],
)
def test_pricing_cost_and_analyzer_reads_pass_and_writes_do_not(guard, service, call):
    client = boto3.client(service, region_name="us-east-1")
    stub = Stubber(client)
    stub.activate()
    with pytest.raises(botocore.exceptions.StubResponseError):
        call(client)  # passed the guard; the stub has no answer queued
    stub.deactivate()  # the Stubber's own before-call handler runs first
    if service == "ce":
        _blocked(
            client,
            lambda c: c.create_cost_category_definition(
                Name="n",
                RuleVersion="CostCategoryExpression.v1",
                Rules=[
                    {
                        "Value": "v",
                        "Rule": {"Dimensions": {"Key": "SERVICE", "Values": ["x"]}},
                    }
                ],
            ),
        )


# ------------------------------------------------------ the sign-in exception
def test_sign_in_exception_needs_an_unsigned_client(guard):
    signed = boto3.client("sts", region_name="us-east-1")
    _blocked(
        signed,
        lambda c: c.assume_role_with_web_identity(
            RoleArn="arn:aws:iam::111111111111:role/r",
            RoleSessionName="ss",
            WebIdentityToken="t" * 20,
        ),
    )
    _blocked(
        boto3.client("sso", region_name="us-east-1"),
        lambda c: c.get_role_credentials(
            roleName="r", accountId="1" * 12, accessToken="t"
        ),
    )


@pytest.mark.parametrize(
    "service,call",
    [
        (
            "sts",
            lambda c: c.assume_role(
                RoleArn="arn:aws:iam::1:role/r", RoleSessionName="s"
            ),
        ),
        ("sts", lambda c: c.get_session_token()),
        ("s3", lambda c: c.put_object(Bucket="b", Key="k")),
        ("iam", lambda c: c.create_access_key()),
        ("secretsmanager", lambda c: c.get_secret_value(SecretId="s")),
        ("sso-oidc", lambda c: c.register_client(clientName="x", clientType="public")),
    ],
)
def test_an_unsigned_client_gets_nothing_beyond_the_four_exchanges(
    guard, service, call
):
    """UNSIGNED opens only the four sign-in exchanges, nothing else (the
    allow-list prefixes still apply as for any client)."""
    client = boto3.client(
        service,
        region_name="us-east-1",
        config=Config(signature_version=botocore.UNSIGNED),
    )
    if service == "sts" and call.__code__.co_names[-1] == "assume_role":
        # AssumeRole is allowed for every client (cross-account scans).
        assert guard.evaluate("sts", "AssumeRole", unsigned=True)[0]
        return
    _blocked(client, call)


def test_exchange_list_is_exactly_four():
    assert rog.UNSIGNED_CREDENTIAL_EXCHANGE_OPERATIONS == frozenset(
        {
            ("sso", "GetRoleCredentials"),
            ("sso-oidc", "CreateToken"),
            ("sts", "AssumeRoleWithWebIdentity"),
            ("signin", "CreateOAuth2Token"),
        }
    )


# ------------------------------------------------------------- presigning
def test_presigned_urls_and_db_tokens_follow_the_policy(guard):
    s3 = boto3.client("s3", region_name="us-east-1")
    _blocked(
        s3,
        lambda c: c.generate_presigned_url(
            "get_object", Params={"Bucket": "b", "Key": "k"}
        ),
    )
    _blocked(
        s3,
        lambda c: c.generate_presigned_url(
            ClientMethod="put_object", Params={"Bucket": "b", "Key": "k"}
        ),
    )
    _blocked(s3, lambda c: c.generate_presigned_post("b", "k"))
    rds = boto3.client("rds", region_name="us-east-1")
    _blocked(rds, lambda c: c.generate_db_auth_token("h", 5432, "u"))
    assert s3.generate_presigned_url("list_objects_v2", Params={"Bucket": "b"})


def test_parameter_rules_block_secret_returning_flags(guard):
    ec2 = boto3.client("ec2", region_name="us-east-1")
    _blocked(
        ec2,
        lambda c: c.describe_instance_attribute(InstanceId="i-1", Attribute="userData"),
    )
    apigw = boto3.client("apigateway", region_name="us-east-1")
    _blocked(apigw, lambda c: c.get_api_keys(includeValues=True))
    _blocked(apigw, lambda c: c.get_api_key(apiKey="k", includeValue=True))


def test_allow_on_client_is_per_client(guard):
    upload = boto3.client("s3", region_name="us-east-1")
    other = boto3.client("s3", region_name="us-east-1")
    ReadOnlyGuard.allow_on_client(upload, {"PutObject"})
    _blocked(other, lambda c: c.put_object(Bucket="b", Key="k", Body=b"x"))
    _blocked(upload, lambda c: c.delete_object(Bucket="b", Key="k"))


@pytest.mark.parametrize(
    "service,operation",
    [
        ("cognito-identity", "GetId"),
        ("ssm", "GetCommandInvocation"),
        ("ssm", "GetDocument"),
        ("ssm", "GetDeployablePatchSnapshotForInstance"),
        ("ssm", "GetMaintenanceWindowTask"),
        ("datapipeline", "GetPipelineDefinition"),
        ("cloudformation", "GetGeneratedTemplate"),
        ("apigateway", "GetExport"),
        ("codeartifact", "GetPackageVersionAsset"),
        ("connect", "GetAttachedFile"),
        ("bedrock-agent-runtime", "GetDocumentContent"),
        ("support", "GetAttachmentDownloadLink"),
        ("iot", "GetJobDocument"),
    ],
)
def test_review_additions_to_the_deny_list(service, operation):
    assert not ReadOnlyGuard().evaluate(service, operation)[0]


def test_every_denied_operation_exists_in_botocore():
    """A typo in the deny-list would silently allow the real operation."""
    session = botocore.session.get_session()
    available = set(session.get_available_services())
    missing = []
    for service, operation in rog.DENIED_OPERATIONS:
        if service == "*" or service not in available:
            continue
        if operation not in session.get_service_model(service).operation_names:
            missing.append(f"{service}:{operation}")
    assert not missing, missing
