"""D1 (A-49, decision 15): ``--account-services`` limits which services are listed.

Until now every service was listed and the result was filtered afterwards, so
a scan for SQS made EC2, RDS and S3 calls and warned about them. Now only the
chosen services are listed and the Tagging API pass is filtered to them. The
rows of the chosen services are the same as before. The other services are
recorded in the coverage ledger as ``out_of_scope`` (not a failure).

Slow on purpose (about 10 s): it runs real discovery against moto twice.
"""

import collections
import logging

import boto3
import botocore.client
import pytest
from moto import mock_aws

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.discovery.coverage import FAILED_OUTCOMES
from inventag.discovery.service_filter import filter_resources

REGION = "us-east-1"


@pytest.fixture()
def estate():
    with mock_aws():
        boto3.client("lambda", region_name=REGION).list_functions()
        sqs = boto3.client("sqs", region_name=REGION)
        sqs.create_queue(QueueName="q1", tags={"team": "a"})
        sqs.create_queue(QueueName="q2")
        boto3.client("ec2", region_name=REGION).create_vpc(CidrBlock="10.7.0.0/16")
        boto3.client("s3", region_name=REGION).create_bucket(Bucket="bkt-d1")
        boto3.client("sns", region_name=REGION).create_topic(Name="t1")
        yield


@pytest.fixture()
def calls(monkeypatch):
    log = collections.Counter()
    original = botocore.client.BaseClient._make_api_call

    def counting(self, operation, params):
        log[(self.meta.service_model.service_name, operation)] += 1
        return original(self, operation, params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", counting)
    return log


def _scan(services=None):
    disc = ComprehensiveAWSDiscovery(
        regions=[REGION], enable_billing_validation=False, services=services
    )
    return disc, disc.discover_all_resources()


def _key(r):
    return (r["service"], r["resource_id"], r["arn"], r["region"], r["resource_type"])


def test_a_scan_for_sqs_lists_only_sqs(estate, calls):
    _, rows = _scan(["SQS"])
    services_called = {service for service, _ in calls}
    assert "sqs" in services_called
    for other in ("ec2", "rds", "s3", "sns", "lambda", "iam", "dynamodb"):
        assert other not in services_called, calls
    assert {r["service"] for r in rows} == {"SQS"}


def test_the_chosen_services_have_the_same_rows_as_a_full_scan(estate):
    _, everything = _scan()
    _, limited = _scan(["SQS", "VPC"])
    expected = filter_resources(everything, ["SQS", "VPC"])
    assert sorted(map(_key, limited)) == sorted(map(_key, expected))
    assert {r["service"] for r in limited} == {"SQS", "VPC"}
    # tags from the Tagging API pass reach the rows of the chosen services
    by_id = {r["resource_id"]: r for r in limited if r["service"] == "SQS"}
    assert any(r.get("tags") for r in by_id.values())


def test_ec2_and_vpc_are_listed_together(estate):
    # VPC rows are found through the EC2 client and the other way round
    _, rows = _scan(["EC2"])
    _, everything = _scan()
    assert sorted(map(_key, rows)) == sorted(
        map(_key, filter_resources(everything, ["EC2"]))
    )


def test_other_services_are_out_of_scope_not_failed(estate):
    disc, _ = _scan(["SQS"])
    entries = disc.coverage.to_dict()
    out = [e for e in entries if e["outcome"] == "out_of_scope"]
    assert out and all(e["source"] == "service-api" for e in out)
    assert {e["service"] for e in out} >= {"ec2", "rds", "s3"}
    assert "sqs" not in {e["service"] for e in out}
    assert all(e["count"] == 0 and e["error_code"] == "" for e in out)
    assert [e for e in disc.coverage.failed_units() if e.service != "sqs"] == []
    assert "out_of_scope" not in FAILED_OUTCOMES


def test_no_warning_about_a_service_outside_the_filter(estate, caplog):
    # moto answers 404 for services it does not know (workmail ...): in a full
    # scan that is a warning for each; with the filter nothing else is called.
    with caplog.at_level(logging.WARNING):
        _scan(["SQS"])
    assert [
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    ] == []


def test_the_tagging_pass_adds_no_fallback_row_of_another_service(estate):
    # an SNS topic is found by the Tagging API only if a tagged one exists
    boto3.client("sns", region_name=REGION).tag_resource(
        ResourceArn=boto3.client("sns", region_name=REGION).list_topics()["Topics"][0][
            "TopicArn"
        ],
        Tags=[{"Key": "k", "Value": "v"}],
    )
    _, rows = _scan(["SQS"])
    assert {r["service"] for r in rows} == {"SQS"}


def test_without_a_filter_every_service_is_listed_as_before(estate, calls):
    disc, rows = _scan()
    assert {"ec2", "s3", "sqs", "sns"} <= {service for service, _ in calls}
    assert not [e for e in disc.coverage.entries if e.outcome == "out_of_scope"]
