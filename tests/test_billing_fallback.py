"""Billed services that discovery missed are listed from billing."""

import logging
from types import SimpleNamespace

from inventag.discovery.inventory import AWSResourceInventory
from inventag.discovery.service_filter import canonical_service


def _inv(resources, spend, mode="auto", services=None):
    inv = object.__new__(AWSResourceInventory)
    inv.resources = resources
    inv.billing_spend_by_service = spend
    inv.fallback_display_mode = mode
    inv.services = services or []
    inv.logger = logging.getLogger("test")
    return inv


def test_billing_names_match_discovered_services():
    assert canonical_service("CLOUDWATCHEVENTS") == canonical_service("EVENTS")
    assert canonical_service("KEYMANAGEMENTSERVICE") == canonical_service("KMS")
    assert canonical_service("AMAZONCLOUDWATCH") == canonical_service("CLOUDWATCH")


def test_billed_service_without_resources_gets_a_row():
    inv = _inv(
        [{"service": "EC2", "account_id": "111122223333"}],
        {"EC2": 5.0, "GLUE": 1.25, "TAX": 0.5},
    )
    assert inv._add_billing_fallback_resources() == 1
    row = inv.resources[-1]
    assert row["service"] == "GLUE"
    assert row["discovered_via"] == "CostExplorer:Fallback"
    assert row["account_id"] == "111122223333"
    assert row["billing_cost_30d"] == 1.25


def test_no_rows_when_fallback_is_off_or_service_filtered():
    assert _inv([], {"GLUE": 1.0}, mode="never")._add_billing_fallback_resources() == 0
    assert (
        _inv([], {"GLUE": 1.0}, services=["s3"])._add_billing_fallback_resources() == 0
    )
