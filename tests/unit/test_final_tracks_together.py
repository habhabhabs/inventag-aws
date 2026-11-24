"""The cross-track pairs of the final patch (v1.3.0), each run with both sides
on the branch (v12-completion-plan.md section 2.2, "Cross-track pairs").

Each track tested its half alone, with a double or a feature check for the
other half. These tests run the real sides together under moto. The CLI runs
take 5 to 15 s each.
"""

import logging

import boto3
import botocore.client
from botocore.exceptions import ClientError
from unittest import mock

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.discovery.network_analyzer import NetworkAnalyzer
from tests.regression.faults import Fault, FaultInjector, deny_everything
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD_ID,
    accounts_file,
    aws,
    empty_aws,
    logged,
    run_cli,
)
from tests.unit.test_slow_cost_explorer_keeps_the_account import (
    FakeClock,
    short_limit,
    slow_cost_explorer,
)
from tests.unit.test_slow_cost_explorer_keeps_the_account import args as ce_args
from tests.unit.test_snapshot_not_poisoned import result_spy

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]
GOOD = {"account_id": GOOD_ID, "regions": ["us-east-1"]}


def _delta(result):
    d = (result.get("state_management") or {}).get("delta_detection") or {}
    return getattr(d.get("summary"), "summary", None) or {}


def _added(result):
    return int(_delta(result).get("added_count", 0) or 0)


def _removed(result):
    return int(_delta(result).get("removed_count", 0) or 0)


def _run(results, faults=(), extra=()):
    with FaultInjector(list(faults)) as injector:
        injector.arm()
        code = run_cli(*ARGS, *extra)
    return code, results[-1]


# ------------------------------- A8 (writer) with B1 (reader): units_not_read
def test_a_throttled_listing_then_a_clean_run_adds_nothing(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    """Lead A writes the units the run did not read; lead B's change report
    leaves their resources out. Without B the clean run reported the untagged
    queue as added (1)."""
    boto3.client("sqs", region_name="us-east-1").create_queue(QueueName="untagged-q")
    results = result_spy(monkeypatch)
    code, first = _run(
        results, [Fault(service="sqs", op="ListQueues", error="Throttling")]
    )
    assert code == 0
    assert first["state_management"]["state_saved"] is True
    code, second = _run(results)
    assert code == 0 and _added(second) == 0, _delta(second)


def test_a_tagging_only_run_then_a_full_run_adds_nothing(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    """Without B the full run reported 31 resources as added."""
    results = result_spy(monkeypatch)
    keep = ("sts", "resourcegroupstaggingapi")
    assert _run(results, [deny_everything(keep=keep)])[0] == 0
    code, second = _run(results)
    assert code == 0 and _added(second) == 0, _delta(second)


# ----------------------- D1 (service limit) with B1 (out of scope is not removed)
def test_a_service_left_out_by_the_limit_is_not_reported_as_removed(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    results = result_spy(monkeypatch)
    assert _run(results)[0] == 0
    code, second = _run(results, extra=("--account-services", "SQS"))
    assert code == 0
    assert _removed(second) == 0 and _added(second) == 0, _delta(second)


# --------------- D2 (one Cost Explorer request) with lead A's short limit (A-24)
def test_one_cost_explorer_request_and_one_line_when_it_does_not_answer(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    caplog.set_level(logging.INFO)
    clock = FakeClock()
    short_limit(monkeypatch, clock)
    slow_cost_explorer(monkeypatch, clock)
    calls = []
    original = botocore.client.BaseClient._make_api_call  # the slow endpoint

    def count(client, operation_name, api_params):
        if operation_name == "GetCostAndUsage":
            calls.append(operation_name)
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", count)
    assert run_cli(*ce_args(accounts_file(tmp_path, [GOOD]))) == 0
    assert calls == ["GetCostAndUsage"]
    lines = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING
        and r.name.startswith("inventag.discovery")
        and r.getMessage().startswith("Cost Explorer")
    ]
    assert len(lines) == 1 and "did not answer in time" in lines[0], lines


# ----------------- D5 (EKS DescribeCluster) with F2 (the analyzer counts it)
def test_an_eks_cluster_row_from_discovery_is_counted_in_its_subnets(aws):  # noqa: F811
    ec2 = boto3.client("ec2", region_name="us-east-1")
    vpc = ec2.create_vpc(CidrBlock="10.40.0.0/16")["Vpc"]
    subnets = [
        ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock=f"10.40.{n}.0/24")["Subnet"]
        for n in (1, 2)
    ]
    config = {
        "subnetIds": [s["SubnetId"] for s in subnets],
        "vpcId": vpc["VpcId"],
    }

    class Eks:
        def describe_cluster(self, **kwargs):
            return {"cluster": {"name": kwargs["name"], "resourcesVpcConfig": config}}

    row = {
        "service": "EKS",
        "type": "Cluster",
        "resource_type": "Cluster",
        "id": "c1",
        "resource_id": "c1",
        "region": "us-east-1",
        "arn": "arn:aws:eks:us-east-1:123456789012:cluster/c1",
        "raw_data": {"name": "c1"},
    }
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=["us-east-1"], enable_billing_validation=False
    )
    disc.coverage.account_id = "123456789012"
    disc.resources = [row]
    disc._client = lambda *a, **k: Eks()
    disc._enhance_eks_clusters()
    rows = (
        [
            {
                "service": "VPC",
                "type": "VPC",
                "id": vpc["VpcId"],
                "region": "us-east-1",
                "raw_data": vpc,
            },
        ]
        + [
            {
                "service": "VPC",
                "type": "Subnet",
                "id": s["SubnetId"],
                "region": "us-east-1",
                "raw_data": s,
            }
            for s in subnets
        ]
        + disc.resources
    )
    analyzer = NetworkAnalyzer(boto3.Session(region_name="us-east-1"))
    analyzer.analyze_vpc_resources(rows)
    assert "c1" in analyzer.vpc_cache[vpc["VpcId"]].associated_resources
    for subnet in subnets:
        assert "c1" in analyzer.subnet_cache[subnet["SubnetId"]].associated_resources


# ------------ A-73: one retry factory for discovery, analyzers and uploads
def test_every_client_factory_is_the_shared_one():
    """Senior D's create_client is the one factory; senior G's upload client
    goes through it (the analyzers and discovery are checked by the AST tests
    of tracks D and F)."""
    from inventag.core import s3_upload
    from inventag.discovery import aws_clients

    session = mock.MagicMock()
    with mock.patch.object(aws_clients, "create_client") as made:
        s3_upload.create_upload_client(session, "eu-west-1")
    assert made.call_args_list == [mock.call(session, "s3", "eu-west-1")]


def test_a_denied_cost_explorer_still_tells_one_story(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """D2 shares one Cost Explorer answer; a denial is one warning line."""
    caplog.set_level(logging.INFO)
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        if operation_name == "GetCostAndUsage":
            raise ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "no"}},
                operation_name,
            )
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)
    assert (
        run_cli(
            "--create-excel",
            "--account-regions",
            "us-east-1",
            "--output-directory",
            "out",
        )
        == 0
    )
    # F1b: the request count said before discovery is not a failure line
    lines = [
        m
        for m in logged(caplog)
        if m.startswith("Cost Explorer") and not m.startswith("Cost Explorer: up to")
    ]
    assert len(lines) == 1 and "denied" in lines[0], lines
    # architect v1.4.1 ruling: without --enable-cost-analysis the count line
    # is INFO, so a default run shows no such warning (the INFO line with
    # --verbose is tested in test_cost_requests.py)
    assert not [m for m in logged(caplog) if m.startswith("Cost Explorer: up to")]
