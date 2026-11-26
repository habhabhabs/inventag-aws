"""D2 (A-35, decision 17): discovery makes one Cost Explorer request per account.

Until now billing validation (inventory) and the spend column (comprehensive
discovery) each asked Cost Explorer for the same data: two requests, and AWS
charges for each. Now the first answer, or the first failure, is shared.
Each consumer parses the answer as before, so the numbers do not change.
"""

import logging
from datetime import datetime, timedelta
from unittest import mock

import botocore.exceptions as bex
from botocore.exceptions import ClientError

from inventag.discovery import inventory as inventory_module
from inventag.discovery.inventory import AWSResourceInventory

ANSWER = {
    "ResultsByTime": [
        {
            "Groups": [
                {
                    "Keys": ["AWS Lambda"],
                    "Metrics": {
                        "BlendedCost": {"Amount": "12.5"},
                        "UsageQuantity": {"Amount": "100"},
                    },
                },
                {
                    # under the inventory's 0.01 cost threshold but with usage
                    "Keys": ["Amazon Simple Storage Service"],
                    "Metrics": {
                        "BlendedCost": {"Amount": "0.005"},
                        "UsageQuantity": {"Amount": "3"},
                    },
                },
                {
                    # no cost and no usage: in neither list
                    "Keys": ["Amazon Simple Queue Service"],
                    "Metrics": {
                        "BlendedCost": {"Amount": "0"},
                        "UsageQuantity": {"Amount": "0"},
                    },
                },
            ]
        }
    ]
}


class CostExplorer:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def get_cost_and_usage(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _inventory(ce, monkeypatch):
    inv = AWSResourceInventory(
        regions=["us-east-1"], session=mock.MagicMock(), enable_billing_validation=True
    )
    monkeypatch.setattr(inventory_module, "create_client", lambda *a, **k: ce)
    inv.comprehensive_discovery._client = lambda *a, **k: ce
    return inv


def _run(inv):
    inv._discover_services_via_billing()
    inv.comprehensive_discovery._discover_billing_services()


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def test_both_consumers_read_one_request(monkeypatch):
    ce = CostExplorer(ANSWER)
    inv = _inventory(ce, monkeypatch)
    _run(inv)
    assert len(ce.calls) == 1
    # the numbers each consumer got before: same answer, own thresholds
    assert inv.billing_spend_by_service == {"LAMBDA": 12.5, "S3": 0.005}
    assert inv.comprehensive_discovery.billing_spend == {"lambda": 12.5, "s3": 0.005}
    assert inv.comprehensive_discovery.billing_services == {"lambda", "s3"}
    assert inv.comprehensive_discovery.coverage.summary() == {"ok": 2}


def test_the_comprehensive_discovery_alone_still_asks_once(monkeypatch):
    ce = CostExplorer(ANSWER)
    inv = _inventory(ce, monkeypatch)
    inv.comprehensive_discovery._discover_billing_services()
    assert len(ce.calls) == 1
    assert inv.comprehensive_discovery.billing_spend == {"lambda": 12.5, "s3": 0.005}


def test_the_request_asks_for_the_widest_window_the_two_consumers_used(monkeypatch):
    ce = CostExplorer(ANSWER)
    _run(_inventory(ce, monkeypatch))
    (call,) = ce.calls
    today = datetime.now()
    assert call["TimePeriod"] == {
        "Start": (today.replace(day=1) - timedelta(days=30)).strftime("%Y-%m-%d"),
        "End": today.strftime("%Y-%m-%d"),
    }
    assert call["Granularity"] == "MONTHLY"
    assert call["Metrics"] == ["BlendedCost", "UsageQuantity"]
    assert call["GroupBy"] == [{"Type": "DIMENSION", "Key": "SERVICE"}]


def test_a_denied_answer_is_one_request_and_one_line(monkeypatch, caplog):
    error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "secret-detail"}},
        "GetCostAndUsage",
    )
    ce = CostExplorer(error)
    inv = _inventory(ce, monkeypatch)
    with caplog.at_level(logging.WARNING):
        _run(inv)
        inv.comprehensive_discovery._validate_with_billing()
    assert len(ce.calls) == 1
    assert _warnings(caplog) == [
        "Cost Explorer was denied (AccessDeniedException), so billing data is "
        "missing and billing checks are skipped. Allow ce:GetCostAndUsage for "
        "this role."
    ]
    assert inv.comprehensive_discovery.coverage.summary() == {"denied": 2}


def test_a_timeout_is_one_request_and_one_line(monkeypatch, caplog):
    ce = CostExplorer(
        bex.ReadTimeoutError(endpoint_url="https://ce.us-east-1.amazonaws.com")
    )
    inv = _inventory(ce, monkeypatch)
    with caplog.at_level(logging.WARNING):
        _run(inv)
        inv.comprehensive_discovery._validate_with_billing()
    assert len(ce.calls) == 1
    assert _warnings(caplog) == [
        "Cost Explorer did not answer in time (ReadTimeoutError), so billing "
        "data is missing and billing checks are skipped. Run the scan again."
    ]
    assert inv.comprehensive_discovery.coverage.summary() == {"error": 1}


def test_the_billing_log_line_names_the_start_of_the_period_it_read(
    monkeypatch, caplog
):
    """Review M1: billing validation reads the shared request, which starts 30
    days before the first day of the month, not 30 days ago; the --verbose
    line names that start date instead of "last 30 days"."""
    ce = CostExplorer(ANSWER)
    inv = _inventory(ce, monkeypatch)
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(inv.logger, "propagate", True)
    _run(inv)
    (call,) = ce.calls
    start = call["TimePeriod"]["Start"]
    lines = [
        r.getMessage() for r in caplog.records if "Billing analysis" in r.getMessage()
    ]
    # a handler an earlier test left can capture the record twice
    assert set(lines) == {
        f"Billing analysis: Found 2 services with usage since {start}"
    }, lines
