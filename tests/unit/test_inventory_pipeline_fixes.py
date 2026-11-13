"""Fixes in the AWSResourceInventory pipeline (no AWS calls; engines stubbed)."""

from unittest import mock

import pytest

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.discovery.inventory import AWSResourceInventory
from inventag.discovery.optimized_dynamic_discovery import OptimizedDynamicDiscovery

LAMBDA = {
    "service": "Lambda",
    "type": "Function",
    "id": "fn1",
    "name": "fn1",
    "region": "us-east-1",
    "arn": "arn:aws:lambda:us-east-1:111122223333:function:fn1",
}
ALARM = {
    "service": "CloudWatch",
    "type": "Alarm",
    "id": "a1",
    "name": "a1",
    "region": "us-east-1",
    "arn": "arn:aws:cloudwatch:us-east-1:111122223333:alarm:a1",
}


def _inventory(**kwargs):
    kwargs.setdefault("regions", ["us-east-1"])
    kwargs.setdefault("enable_billing_validation", False)
    return AWSResourceInventory(session=mock.MagicMock(), **kwargs)


def test_no_predicted_rows_by_default():
    inv = _inventory()
    inv.resources = [dict(LAMBDA), dict(ALARM)]
    inv._apply_ai_predictions()
    assert len(inv.resources) == 2
    assert not any(r.get("predicted") for r in inv.resources)


def test_predicted_rows_only_when_asked_for_and_marked():
    inv = _inventory(enable_ai_prediction=True)
    inv.resources = [dict(LAMBDA), dict(ALARM)]
    inv._apply_ai_predictions()
    predicted = [r for r in inv.resources if r.get("predicted")]
    assert [r["id"] for r in predicted] == ["/aws/lambda/fn1"]


@pytest.fixture
def stubbed_engines():
    with (
        mock.patch.object(
            ComprehensiveAWSDiscovery, "discover_all_resources", return_value=[]
        ),
        mock.patch.object(AWSResourceInventory, "_perform_optimized_discovery"),
        mock.patch.object(AWSResourceInventory, "_discover_service_by_name") as by_name,
    ):
        yield by_name


def test_basic_generic_discovery_is_skipped_after_comprehensive(stubbed_engines):
    """It added only AWS-owned items (managed prefix lists) and missed the rest."""
    _inventory().discover_resources()
    stubbed_engines.assert_not_called()


def test_basic_generic_discovery_still_runs_without_comprehensive(stubbed_engines):
    with mock.patch.object(
        AWSResourceInventory, "_discover_via_resource_groups_tagging_api"
    ):
        _inventory(use_comprehensive=False).discover_resources()
    assert stubbed_engines.called


def test_dynamic_discovery_rows_get_id_type_and_name(stubbed_engines):
    raw = {
        "service": "KINESIS",
        "region": "us-east-1",
        "resource_id": "stream-1",
        "resource_name": "stream-1",
        "resource_type": "Stream",
        "tags": {},
        "discovery_method": "DynamicDiscovery:ListStreams",
        "raw_data": {},
    }
    inv = _inventory(enable_billing_validation=True)

    def billing():
        inv.billing_spend_by_service = {"KINESIS": 5.0}
        inv.billing_validated_services = {"KINESIS"}

    with (
        mock.patch.object(inv, "_discover_services_via_billing", side_effect=billing),
        mock.patch.object(
            OptimizedDynamicDiscovery,
            "discover_services_parallel",
            return_value={
                "resources": [raw],
                "results": [],
                "performance": {
                    "total_resources_found": 1,
                    "total_execution_time": 0.1,
                    "resources_per_second": 10.0,
                },
            },
        ),
    ):
        resources = inv.discover_resources()
    row = next(r for r in resources if r.get("resource_id") == "stream-1")
    assert (row["id"], row["type"], row["name"]) == ("stream-1", "Stream", "stream-1")


def test_dynamic_discovery_reads_global_services_once():
    tasks = OptimizedDynamicDiscovery(
        session=mock.MagicMock()
    )._optimize_discovery_tasks(["IAM", "KINESIS"], ["us-east-1", "eu-west-1"])
    assert [(t["service"], t["region"]) for t in tasks if t["service"] == "IAM"] == [
        ("IAM", "us-east-1")
    ]
    assert len([t for t in tasks if t["service"] == "KINESIS"]) == 2


def test_dynamic_discovery_finds_known_operations_for_billing_names():
    disc = OptimizedDynamicDiscovery(session=mock.MagicMock())
    ops = disc._get_optimized_operations(mock.MagicMock(), "SECRETSMANAGER")
    assert ops == ["ListSecrets"]
