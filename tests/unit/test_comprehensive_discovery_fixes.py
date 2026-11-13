"""Pagination, ECS services, partitions, classification and region discovery."""

from unittest import mock

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from moto import mock_aws

from inventag.discovery import regions as regions_mod
from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery


@pytest.fixture
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


def _disc(regions=("us-east-1",)):
    return ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=list(regions), enable_billing_validation=False
    )


def _client(service, region="us-east-1"):
    return boto3.client(
        service,
        region_name=region,
        aws_access_key_id="a",
        aws_secret_access_key="b",
    )


def test_operation_without_paginator_follows_next_token():
    events = _client("events")
    stub = Stubber(events)
    stub.add_response(
        "list_event_buses",
        {
            "EventBuses": [
                {"Name": "bus-1", "Arn": "arn:aws:events:us-east-1:1:event-bus/bus-1"}
            ],
            "NextToken": "t1",
        },
        {},
    )
    stub.add_response(
        "list_event_buses",
        {
            "EventBuses": [
                {"Name": "bus-2", "Arn": "arn:aws:events:us-east-1:1:event-bus/bus-2"}
            ]
        },
        {"NextToken": "t1"},
    )
    disc = _disc()
    with stub:
        found = disc._execute_discovery_operation(
            events,
            "events",
            "us-east-1",
            ("list_event_buses", "EventBuses", "EventBus"),
        )
    assert found == 2
    assert {r["resource_id"] for r in disc.resources} == {"bus-1", "bus-2"}


def test_failed_page_keeps_earlier_pages_and_adds_no_duplicates():
    events = _client("events")
    stub = Stubber(events)
    stub.add_response(
        "list_event_buses",
        {"EventBuses": [{"Name": "bus-1"}], "NextToken": "t1"},
        {},
    )
    stub.add_client_error("list_event_buses", "ThrottlingException")
    disc = _disc()
    with stub:
        disc._execute_discovery_operation(
            events,
            "events",
            "us-east-1",
            ("list_event_buses", "EventBuses", "EventBus"),
        )
    assert [r["resource_id"] for r in disc.resources] == ["bus-1"]


def test_ecs_services_are_listed_in_every_cluster(aws_env):
    ecs = boto3.client("ecs", region_name="us-east-1")
    task = ecs.register_task_definition(
        family="f", containerDefinitions=[{"name": "c", "image": "i", "memory": 64}]
    )["taskDefinition"]["taskDefinitionArn"]
    for cluster in ("blue", "green"):
        ecs.create_cluster(clusterName=cluster)
        ecs.create_service(
            cluster=cluster, serviceName=f"svc-{cluster}", taskDefinition=task
        )
    disc = ComprehensiveAWSDiscovery(
        regions=["us-east-1"], enable_billing_validation=False
    )
    disc._discover_service_in_region(
        {
            "service": "ecs",
            "region": "us-east-1",
            "config": disc.service_discovery_patterns["ecs"],
        }
    )
    services = {
        r["resource_name"] for r in disc.resources if r["resource_type"] == "Service"
    }
    assert services == {"svc-blue", "svc-green"}


@pytest.mark.parametrize(
    "service, rtype, rid, expected",
    [
        ("lambda", "Function", "vpc-flow-logs-processor", "lambda"),
        ("s3", "Bucket", "subnet-reports", "s3"),
        ("sqs", "Queue", "nat-events", "sqs"),
        ("ec2", "SecurityGroup", "sg-123", "vpc"),
        ("ec2", "Instance", "i-123", "ec2"),
    ],
)
def test_only_ec2_resources_move_to_vpc(service, rtype, rid, expected):
    assert _disc()._determine_actual_service(service, rtype, rid, "") == expected


@pytest.mark.parametrize(
    "regions, home, ce",
    [
        (["eu-west-1"], "us-east-1", "us-east-1"),
        (["cn-northwest-1"], "cn-north-1", "cn-northwest-1"),
        (["us-gov-east-1"], "us-gov-west-1", "us-gov-west-1"),
    ],
)
def test_global_services_use_the_partition_home_region(regions, home, ce):
    disc = _disc(regions)
    assert disc.home_region == home
    assert regions_mod.cost_explorer_region(regions) == ce
    assert home in disc._tagging_regions()


def test_arns_of_other_partitions_are_parsed():
    disc = _disc(["cn-north-1"])
    assert disc._extract_service_from_arn("arn:aws-cn:s3:::bucket") == "s3"
    assert (
        disc._extract_account_id("arn:aws-us-gov:iam::123456789012:role/r")
        == "123456789012"
    )


def test_tagged_load_balancer_is_not_a_fallback_row_when_elbv2_found_some():
    disc = _disc()
    disc.services_with_primary_resources = {"elbv2"}
    arn = "arn:aws:elasticloadbalancing:us-east-1:1:loadbalancer/app/x/1"
    assert disc._should_show_fallback(arn) is False
    assert disc._should_show_fallback("arn:aws:logs:us-east-1:1:log-group:g")


def _denied(op):
    return ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, op)


def test_regions_from_ec2_first():
    with mock.patch.object(
        regions_mod, "_from_describe_regions", return_value=["eu-west-1", "us-east-1"]
    ):
        assert regions_mod.discover_regions(mock.MagicMock(region_name=None)) == (
            ["eu-west-1", "us-east-1"],
            "ec2",
        )


def test_regions_from_account_api_when_ec2_is_denied():
    with (
        mock.patch.object(
            regions_mod,
            "_from_describe_regions",
            side_effect=_denied("DescribeRegions"),
        ),
        mock.patch.object(
            regions_mod, "_from_account_list_regions", return_value=["ap-southeast-1"]
        ),
    ):
        assert regions_mod.discover_regions(mock.MagicMock(region_name=None)) == (
            ["ap-southeast-1"],
            "account",
        )


def test_account_list_regions_asks_only_for_enabled_regions(aws_env):
    session = boto3.Session()
    account = _client("account")
    stub = Stubber(account)
    stub.add_response(
        "list_regions",
        {"Regions": [{"RegionName": "me-central-1", "RegionOptStatus": "ENABLED"}]},
        {"RegionOptStatusContains": ["ENABLED", "ENABLED_BY_DEFAULT"]},
    )
    with stub, mock.patch.object(regions_mod, "create_client", return_value=account):
        assert regions_mod._from_account_list_regions(session, "us-east-1") == [
            "me-central-1"
        ]


def test_regions_from_botocore_when_both_apis_fail(caplog):
    session = boto3.Session(region_name="us-gov-west-1")
    with (
        mock.patch.object(
            regions_mod,
            "_from_describe_regions",
            side_effect=_denied("DescribeRegions"),
        ),
        mock.patch.object(
            regions_mod,
            "_from_account_list_regions",
            side_effect=_denied("ListRegions"),
        ),
    ):
        regions, source = regions_mod.discover_regions(session)
    assert source == "botocore"
    assert "us-gov-west-1" in regions
    assert all(r.startswith("us-gov-") for r in regions)
    assert "access check" in caplog.text


def test_aws_partition_fallback_has_more_than_four_regions():
    session = boto3.Session(region_name="us-east-1")
    with (
        mock.patch.object(
            regions_mod,
            "_from_describe_regions",
            side_effect=_denied("DescribeRegions"),
        ),
        mock.patch.object(
            regions_mod,
            "_from_account_list_regions",
            side_effect=_denied("ListRegions"),
        ),
    ):
        regions, source = regions_mod.discover_regions(session)
    assert source == "botocore"
    assert {"us-east-1", "eu-central-1", "ap-southeast-1"} <= set(regions)
    assert not any(r.startswith(("cn-", "us-gov-")) for r in regions)


def test_time_limit_keeps_found_resources_and_records_unfinished():
    import threading

    release = threading.Event()
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(),
        regions=["us-east-1"],
        enable_billing_validation=False,
        discovery_timeout=0.2,
    )
    disc.service_discovery_patterns = {
        "fast": {"operations": [], "regional": True},
        "slow": {"operations": [], "regional": True},
    }

    def run(task):
        if task["service"] == "slow":
            release.wait(5)
            return 0
        disc.resources.append({"service": "FAST", "resource_id": "kept"})
        return 1

    try:
        with mock.patch.object(disc, "_discover_service_in_region", side_effect=run):
            disc._discover_all_service_resources(max_workers=2)
    finally:
        release.set()
    assert [r["resource_id"] for r in disc.resources] == ["kept"]
    timeouts = [e for e in disc.coverage.entries if e.outcome == "timeout"]
    assert [e.service for e in timeouts] == ["slow"]


def test_default_time_limit_is_600_seconds():
    assert _disc().discovery_timeout == 600


def test_throttled_and_denied_calls_are_in_the_ledger():
    sqs = _client("sqs")
    stub = Stubber(sqs)
    stub.add_client_error("list_queues", "RequestThrottled")
    disc = _disc()
    with stub:
        disc._execute_discovery_operation(
            sqs, "sqs", "us-east-1", ("list_queues", "QueueUrls", "Queue")
        )
    stub.add_client_error("list_queues", "AccessDenied")
    with stub:
        disc._execute_discovery_operation(
            sqs, "sqs", "eu-west-1", ("list_queues", "QueueUrls", "Queue")
        )
    outcomes = [(e.region, e.outcome, e.operation) for e in disc.coverage.entries]
    assert outcomes == [
        ("us-east-1", "throttled", "ListQueues"),
        ("eu-west-1", "denied", "ListQueues"),
    ]
    assert len(disc.coverage.failed_units()) == 2
    assert disc.coverage.summary() == {"throttled": 1, "denied": 1}
