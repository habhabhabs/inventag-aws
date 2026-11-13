"""The table-driven service entries: model checks, moto run, read-only guard."""

import json
from unittest import mock

import boto3
import pytest
from botocore.stub import Stubber
from moto import mock_aws

from inventag.discovery.comprehensive_discovery import (
    TABLE_DRIVEN_SERVICES,
    ComprehensiveAWSDiscovery,
)
from inventag.security.secret_values import MASK
from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    install_global_guard,
    uninstall_global_guard,
)

R = "us-east-1"


def _all_operations():
    disc = ComprehensiveAWSDiscovery(session=mock.MagicMock(), regions=[R])
    for key, config in disc.service_discovery_patterns.items():
        for op in config["operations"]:
            yield key, config.get("client_service", key), disc._op_spec(op)


def _offline_client(name):
    return boto3.Session(
        aws_access_key_id="a", aws_secret_access_key="b", region_name=R
    ).client(name)


@pytest.mark.parametrize(
    "key, client_name, spec",
    list(_all_operations()),
    ids=lambda v: v if isinstance(v, str) else v.get("op"),
)
def test_every_table_operation_is_valid_and_read_only(key, client_name, spec):
    client = _offline_client(client_name)
    assert hasattr(client, spec["op"]), f"{client_name} has no {spec['op']}"
    api_name = client.meta.method_to_api_mapping[spec["op"]]
    model = client.meta.service_model.operation_model(api_name)

    # Required request parameters are all supplied
    required = set(model.input_shape.required_members) if model.input_shape else set()
    supplied = set(spec["params"])
    if spec.get("per_parent"):
        supplied.add(spec["per_parent"]["param"])
    assert required <= supplied, f"{api_name} needs {required - supplied}"

    # The result key exists in the response
    top = spec["key"].split(".")[0]
    assert top in model.output_shape.members, f"{api_name} has no {top}"

    # Every page is read: botocore paginator, a known token, or one page only
    if not client.can_paginate(spec["op"]) and not spec.get("token"):
        outputs = set(model.output_shape.members)
        assert not outputs & {"NextToken", "nextToken", "NextMarker", "Marker"} or (
            set(model.input_shape.members if model.input_shape else ())
            & {"NextToken", "nextToken", "NextMarker", "Marker"}
        ), f"{api_name} pages but has no way to follow them"

    # The read-only guard allows it
    assert ReadOnlyGuard().evaluate(client.meta.service_model.service_name, api_name)[
        0
    ], api_name


def test_no_table_call_reads_values():
    ops = {spec["op"] for _, _, spec in _all_operations()}
    for forbidden in (
        "get_secret_value",
        "get_parameter",
        "get_parameters",
        "get_parameters_by_path",
        "batch_get_projects",
        "describe_state_machine",
        "get_function",
    ):
        assert forbidden not in ops


@pytest.fixture
def account(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", R)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


def c(name):
    return boto3.client(name, region_name=R)


def _setup_account():
    role = c("iam").create_role(RoleName="r", AssumeRolePolicyDocument="{}")["Role"][
        "Arn"
    ]
    acl = {
        "DefaultAction": {"Allow": {}},
        "VisibilityConfig": {
            "SampledRequestsEnabled": False,
            "CloudWatchMetricsEnabled": False,
            "MetricName": "m",
        },
    }
    c("elasticache").create_cache_cluster(
        CacheClusterId="cache-1",
        Engine="redis",
        CacheNodeType="cache.t3.micro",
        NumCacheNodes=1,
    )
    c("redshift").create_cluster(
        ClusterIdentifier="rs-1",
        NodeType="dc2.large",
        MasterUsername="admin",
        MasterUserPassword="Passw0rd1",
        ClusterType="single-node",
    )
    c("opensearch").create_domain(DomainName="search-1")
    c("efs").create_file_system(CreationToken="t1")
    c("ecr").create_repository(repositoryName="repo-1")
    c("stepfunctions").create_state_machine(name="sm-1", definition="{}", roleArn=role)
    c("kinesis").create_stream(StreamName="stream-1", ShardCount=1)
    c("firehose").create_delivery_stream(
        DeliveryStreamName="fh-1",
        ExtendedS3DestinationConfiguration={
            "RoleARN": role,
            "BucketARN": "arn:aws:s3:::bkt",
        },
    )
    c("secretsmanager").create_secret(Name="sec-1", SecretString="planted-secret-1")
    c("ssm").put_parameter(Name="/app/db", Value="planted-param-1", Type="SecureString")
    c("autoscaling").create_launch_configuration(
        LaunchConfigurationName="lc", ImageId="ami-12c6146b", InstanceType="t2.micro"
    )
    c("autoscaling").create_auto_scaling_group(
        AutoScalingGroupName="asg-1",
        LaunchConfigurationName="lc",
        MinSize=0,
        MaxSize=1,
        AvailabilityZones=["us-east-1a"],
    )
    c("backup").create_backup_vault(BackupVaultName="vault-1")
    c("cognito-idp").create_user_pool(PoolName="pool-1")
    c("athena").create_work_group(Name="wg-athena")
    c("emr").run_job_flow(
        Name="emr-1",
        Instances={
            "MasterInstanceType": "m5.xlarge",
            "InstanceCount": 1,
            "KeepJobFlowAliveWhenNoSteps": True,
        },
        JobFlowRole="EMR_EC2_DefaultRole",
        ServiceRole="EMR_DefaultRole",
        ReleaseLabel="emr-6.10.0",
    )
    c("kafka").create_cluster_v2(
        ClusterName="msk-1",
        Serverless={"VpcConfigs": [{"SubnetIds": ["subnet-1"]}]},
    )
    c("appsync").create_graphql_api(name="api-1", authenticationType="API_KEY")
    c("elasticbeanstalk").create_application(ApplicationName="app-1")
    c("elasticbeanstalk").create_environment(
        ApplicationName="app-1",
        EnvironmentName="env-1",
        SolutionStackName="64bit Amazon Linux 2",
    )
    c("wafv2").create_web_acl(Name="acl-1", Scope="REGIONAL", **acl)
    c("wafv2").create_web_acl(Name="acl-cf", Scope="CLOUDFRONT", **acl)


EXPECTED = {
    ("ELASTICACHE", "CacheCluster", "cache-1"): "arn:aws:elasticache:",
    (
        "REDSHIFT",
        "Cluster",
        "rs-1",
    ): "arn:aws:redshift:us-east-1:123456789012:cluster:rs-1",
    (
        "OPENSEARCH",
        "Domain",
        "search-1",
    ): "arn:aws:es:us-east-1:123456789012:domain/search-1",
    ("ECR", "Repository", "repo-1"): "arn:aws:ecr:",
    ("STEPFUNCTIONS", "StateMachine", "sm-1"): "arn:aws:states:",
    ("KINESIS", "Stream", "stream-1"): "arn:aws:kinesis:",
    (
        "FIREHOSE",
        "DeliveryStream",
        "fh-1",
    ): "arn:aws:firehose:us-east-1:123456789012:deliverystream/fh-1",
    ("SECRETSMANAGER", "Secret", "sec-1"): "arn:aws:secretsmanager:",
    (
        "SSM",
        "Parameter",
        "/app/db",
    ): "arn:aws:ssm:us-east-1:123456789012:parameter/app/db",
    ("AUTOSCALING", "AutoScalingGroup", "asg-1"): "arn:aws:autoscaling:",
    ("BACKUP", "BackupVault", "vault-1"): "arn:aws:backup:",
    (
        "ATHENA",
        "WorkGroup",
        "wg-athena",
    ): "arn:aws:athena:us-east-1:123456789012:workgroup/wg-athena",
    ("MSK", "Cluster", "msk-1"): "arn:aws:kafka:",
    ("ELASTICBEANSTALK", "Application", "app-1"): "arn:aws:elasticbeanstalk:",
    ("ELASTICBEANSTALK", "Environment", "env-1"): "arn:aws:elasticbeanstalk:",
    ("WAFV2", "WebACL", "acl-1"): "arn:aws:wafv2:us-east-1:123456789012:regional/",
    ("WAFV2", "WebACL", "acl-cf"): "arn:aws:wafv2:us-east-1:123456789012:global/",
}


def test_table_driven_services_against_moto_under_the_guard(account):
    _setup_account()
    disc = ComprehensiveAWSDiscovery(regions=[R], enable_billing_validation=False)
    disc.service_discovery_patterns = dict(TABLE_DRIVEN_SERVICES)
    guard = install_global_guard(ReadOnlyGuard())
    try:
        resources = disc.discover_all_resources()
    finally:
        uninstall_global_guard()
    assert guard.audit_report()["blocked_calls"] == 0

    by_key = {
        (r["service"], r["resource_type"], r["resource_id"]): r for r in resources
    }
    for key, arn_prefix in EXPECTED.items():
        assert key in by_key, key
        assert by_key[key]["arn"].startswith(arn_prefix), by_key[key]["arn"]
        assert by_key[key]["source"] == "service-api"
    services = {r["service"] for r in resources}
    assert {"EFS", "EMR", "COGNITO", "APPSYNC"} <= services
    # Metadata only: no secret or parameter value
    blob = json.dumps(resources, default=str)
    assert "planted-secret-1" not in blob and "planted-param-1" not in blob


def test_redshift_serverless_and_codebuild_with_stubs():
    """moto lacks Redshift Serverless; CodeBuild returns names only."""
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=[R], enable_billing_validation=False
    )
    disc._cached_account_id = "111122223333"
    rss = _offline_client("redshift-serverless")
    stub = Stubber(rss)
    stub.add_response(
        "list_workgroups",
        {
            "workgroups": [
                {
                    "workgroupName": "wg-1",
                    "workgroupArn": "arn:aws:redshift-serverless:us-east-1:111122223333:workgroup/abc",
                }
            ]
        },
        {},
    )
    with stub:
        disc._execute_discovery_operation(
            rss,
            "redshift-serverless",
            R,
            TABLE_DRIVEN_SERVICES["redshift-serverless"]["operations"][0],
        )
    cb = _offline_client("codebuild")
    stub = Stubber(cb)
    stub.add_response("list_projects", {"projects": ["proj-1"]}, {})
    with stub:
        disc._execute_discovery_operation(
            cb, "codebuild", R, TABLE_DRIVEN_SERVICES["codebuild"]["operations"][0]
        )
    rows = {r["resource_id"]: r for r in disc.resources}
    assert rows["wg-1"]["arn"].endswith(":workgroup/abc")
    assert (
        rows["proj-1"]["arn"]
        == "arn:aws:codebuild:us-east-1:111122223333:project/proj-1"
    )


def test_firehose_follows_its_own_paging():
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=[R], enable_billing_validation=False
    )
    disc._cached_account_id = "111122223333"
    fh = _offline_client("firehose")
    stub = Stubber(fh)
    stub.add_response(
        "list_delivery_streams",
        {"DeliveryStreamNames": ["a", "b"], "HasMoreDeliveryStreams": True},
        {},
    )
    stub.add_response(
        "list_delivery_streams",
        {"DeliveryStreamNames": ["c"], "HasMoreDeliveryStreams": False},
        {"ExclusiveStartDeliveryStreamName": "b"},
    )
    with stub:
        disc._execute_discovery_operation(
            fh, "firehose", R, TABLE_DRIVEN_SERVICES["firehose"]["operations"][0]
        )
    assert [r["resource_id"] for r in disc.resources] == ["a", "b", "c"]


def test_cloudfront_web_acls_only_in_the_aws_partition():
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(),
        regions=["cn-north-1"],
        enable_billing_validation=False,
    )
    with mock.patch.object(disc, "_discover_service_in_region", return_value=0) as run:
        disc._discover_all_service_resources(max_workers=2)
    services = {call.args[0]["service"] for call in run.call_args_list}
    assert "wafv2" in services
    assert "wafv2-cloudfront" not in services


def test_regions_without_the_service_are_skipped():
    session = mock.MagicMock()
    session.get_available_regions.side_effect = lambda svc, partition_name: (
        ["us-east-1"] if svc == "appsync" else ["us-east-1", "eu-south-2"]
    )
    disc = ComprehensiveAWSDiscovery(
        session=session,
        regions=["us-east-1", "eu-south-2"],
        enable_billing_validation=False,
    )
    with mock.patch.object(disc, "_discover_service_in_region", return_value=0) as run:
        disc._discover_all_service_resources(max_workers=2)
    appsync = [
        call.args[0]["region"]
        for call in run.call_args_list
        if call.args[0]["service"] == "appsync"
    ]
    assert appsync == ["us-east-1"]


def test_masked_constant_is_used_for_secrets():
    # One text for every place that hides a secret (reports, snapshots, logs)
    from inventag.security.redaction import REDACTED

    assert MASK == REDACTED == "***REDACTED***"
