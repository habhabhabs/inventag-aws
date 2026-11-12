"""Tests for the service/tag result filter and the CLI switches that use it."""

from unittest.mock import patch

import pytest

from inventag.cli.main import create_parser
from inventag.discovery import AWSResourceInventory
from inventag.discovery.service_filter import (
    canonical_service,
    filter_resources,
    tags_match,
)


@pytest.mark.parametrize(
    "left,right",
    [
        ("Route 53", "route53"),
        ("Amazon Route 53", "ROUTE53"),
        ("elbv2", "ELB"),
        ("AWS Lambda", "lambda"),
        ("Systems Manager", "ssm"),
        ("cognito-idp", "Cognito"),
        ("Step Functions", "states"),
    ],
)
def test_canonical_service_variants_match(left, right):
    assert canonical_service(left) == canonical_service(right)


def test_canonical_service_keeps_different_services_apart():
    assert canonical_service("EC2") != canonical_service("ECS")
    assert canonical_service(None) == ""


def test_filter_resources_by_service_and_tag():
    resources = [
        {"service": "EC2", "id": "i-1", "tags": {"Env": "prod"}},
        {"service": "S3", "id": "b-1", "tags": {"Env": "dev"}},
        {"service": "Lambda", "id": "f-1", "tags": {}},
        {"service": "RDS", "id": "db-1"},
    ]
    assert [r["id"] for r in filter_resources(resources, ["ec2", "s3"])] == [
        "i-1",
        "b-1",
    ]
    assert [r["id"] for r in filter_resources(resources, None, {"Env": "prod"})] == [
        "i-1"
    ]
    assert [
        r["id"] for r in filter_resources(resources, ["S3"], {"Env": ["dev", "test"]})
    ] == ["b-1"]
    assert filter_resources(resources) is resources


def test_tags_match_handles_missing_tags():
    assert tags_match(None, {}) is True
    assert tags_match(None, {"Env": "prod"}) is False


@pytest.fixture
def inventory():
    with patch("boto3.Session"):
        yield AWSResourceInventory(
            regions=["us-east-1"],
            services=["EC2"],
            enable_billing_validation=False,
        )


def test_inventory_filters_resources_from_every_path(inventory):
    inventory.resources = [
        {"service": "EC2", "type": "Instance", "id": "i-1"},
        {"service": "S3", "type": "Bucket", "id": "b-1"},
        {"service": "CloudTrail", "type": "Trail", "id": "t-1"},
    ]
    inventory._apply_resource_filters()
    assert [r["id"] for r in inventory.resources] == ["i-1"]


def test_comprehensive_resources_get_inventory_keys():
    resource = {
        "service": "S3",
        "resource_type": "Bucket",
        "resource_id": "b-1",
        "resource_name": "b-1",
    }
    converted = AWSResourceInventory._to_inventory_format(resource)
    assert (converted["type"], converted["id"], converted["name"]) == (
        "Bucket",
        "b-1",
        "b-1",
    )


def test_billing_switch_reaches_comprehensive_discovery(inventory):
    assert inventory.enable_billing_validation is False
    assert inventory.comprehensive_discovery.enable_billing_validation is False


def test_cli_switches_default_on_and_can_be_turned_off():
    parser = create_parser()
    defaults = parser.parse_args([])
    assert defaults.generate_changelog is True
    assert defaults.billing_validation is True
    off = parser.parse_args(["--no-generate-changelog", "--no-billing-validation"])
    assert off.generate_changelog is False
    assert off.billing_validation is False
