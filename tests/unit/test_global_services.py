"""Global services (IAM, S3, CloudFront, Route 53) are found for any region list.

The user must not have to add us-east-1 to ``--account-regions``.
"""

import boto3
import pytest
from moto import mock_aws

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.discovery.inventory import AWSResourceInventory

GLOBAL = {"IAM", "S3", "ROUTE53"}


@pytest.fixture(scope="module")
def account():
    with mock_aws():
        iam = boto3.client("iam")
        iam.create_role(
            RoleName="global-role",
            AssumeRolePolicyDocument="{}",
            Tags=[{"Key": "Owner", "Value": "alex"}],
        )
        s3 = boto3.client("s3", region_name="eu-west-1")
        s3.create_bucket(
            Bucket="eu-bucket",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        boto3.client("route53").create_hosted_zone(
            Name="example.com", CallerReference="ref-1"
        )
        boto3.client("ec2", region_name="eu-west-1").create_vpc(CidrBlock="10.1.0.0/16")
        boto3.client("sqs", region_name="us-west-2").create_queue(QueueName="usw2")
        yield


def _discover(regions):
    return ComprehensiveAWSDiscovery(
        regions=regions, enable_billing_validation=False
    ).discover_all_resources()


def _names(resources, service):
    return {r["resource_id"] for r in resources if r["service"] == service}


def test_eu_west_1_alone_still_lists_global_services(account):
    resources = _discover(["eu-west-1"])
    assert "global-role" in _names(resources, "IAM")
    assert "eu-bucket" in _names(resources, "S3")
    assert _names(resources, "ROUTE53")
    # Regional services stay inside the requested region.
    assert all(r["region"] == "eu-west-1" for r in resources if r["service"] == "VPC")
    assert not _names(resources, "SQS")


def test_global_resources_are_labelled_global_and_s3_keeps_its_region(account):
    resources = _discover(["eu-west-1"])
    by = {(r["service"], r["resource_id"]): r for r in resources}
    assert by[("IAM", "global-role")]["region"] == "global"
    assert by[("S3", "eu-bucket")]["region"] == "eu-west-1"
    zone = next(r for r in resources if r["service"] == "ROUTE53")
    assert zone["region"] == "global"


def test_global_services_are_listed_once_when_us_east_1_is_included(account):
    resources = _discover(["us-east-1", "eu-west-1"])
    roles = [r for r in resources if r["resource_id"] == "global-role"]
    buckets = [r for r in resources if r["resource_id"] == "eu-bucket"]
    assert len(roles) == 1
    assert len(buckets) == 1


def test_all_regions_list_global_services_once(account):
    regions = [
        "us-east-1",
        "us-west-2",
        "eu-west-1",
        "ap-southeast-1",
    ]
    resources = _discover(regions)
    assert len([r for r in resources if r["resource_id"] == "global-role"]) == 1
    assert len(_names(resources, "SQS")) == 1


def test_global_tags_come_from_us_east_1_when_it_is_not_requested(account):
    resources = _discover(["eu-west-1"])
    role = next(r for r in resources if r["resource_id"] == "global-role")
    assert role["resource_type"] == "Role"


def test_pipeline_filters_still_apply_to_global_services(account):
    inv = AWSResourceInventory(
        regions=["eu-west-1"],
        services=["iam"],
        enable_billing_validation=False,
        use_intelligent=False,
        use_optimized=False,
    )
    resources = inv.discover_resources()
    assert resources
    assert {r["service"] for r in resources} == {"IAM"}


def test_tag_filter_applies_to_global_services(account):
    inv = AWSResourceInventory(
        regions=["eu-west-1"],
        tag_filters={"Owner": "alex"},
        enable_billing_validation=False,
        use_intelligent=False,
        use_optimized=False,
    )
    resources = inv.discover_resources()
    assert all(r["tags"].get("Owner") == "alex" for r in resources)


def test_pipeline_lists_global_services_without_us_east_1(account):
    inv = AWSResourceInventory(regions=["eu-west-1"], enable_billing_validation=False)
    resources = inv.discover_resources()
    services = {r["service"] for r in resources}
    assert GLOBAL <= {s.replace(" ", "").upper() for s in services}, services
