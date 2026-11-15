"""A-21: the text of listing and Cost Explorer messages is true (golden texts).

Each text names one cause and one next step, and holds no botocore exception
text (that can hold request parameters). The ledger outcome stays ``denied``,
so the counts of ``coverage_summary`` do not move.
"""

import logging
from unittest import mock

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from inventag.discovery import inventory as inventory_module
from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.discovery.coverage import CoverageLedger

R = "us-east-1"


def _client(name):
    return boto3.Session(
        aws_access_key_id="a", aws_secret_access_key="b", region_name=R
    ).client(name)


def _disc():
    return ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=[R], enable_billing_validation=False
    )


def _op(disc, service, index):
    return disc.service_discovery_patterns[service]["operations"][index]


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def test_opt_in_required_does_not_ask_for_a_permission(caplog):
    disc = _disc()
    client = _client("sqs")
    stub = Stubber(client)
    stub.add_client_error("list_queues", service_error_code="OptInRequired")
    with stub, caplog.at_level(logging.WARNING):
        disc._execute_discovery_operation(client, "sqs", R, _op(disc, "sqs", 0))
    assert _warnings(caplog) == [
        "sqs needs an opt-in or subscription (list_queues in us-east-1: "
        "OptInRequired), so its resources are not listed. Enable it for this "
        "account in the AWS console."
    ]
    assert disc.coverage.summary() == {"denied": 1}


def test_denied_single_listing_keeps_its_text(caplog):
    disc = _disc()
    client = _client("sqs")
    stub = Stubber(client)
    stub.add_client_error("list_queues", service_error_code="AccessDenied")
    with stub, caplog.at_level(logging.WARNING):
        disc._execute_discovery_operation(client, "sqs", R, _op(disc, "sqs", 0))
    assert _warnings(caplog) == [
        "No permission for sqs (list_queues in us-east-1: AccessDenied). "
        "Resources of sqs are skipped; add the read permission to see them."
    ]


def test_denied_ecs_list_services_does_not_say_all_ecs_is_skipped(caplog):
    disc = _disc()
    client = _client("ecs")
    arn = "arn:aws:ecs:us-east-1:111122223333:cluster/c1"
    stub = Stubber(client)
    stub.add_response("list_clusters", {"clusterArns": [arn]}, {})
    stub.add_response("list_clusters", {"clusterArns": [arn]}, {})
    stub.add_client_error(
        "list_services",
        service_error_code="AccessDeniedException",
        expected_params={"cluster": arn},
    )
    with stub, caplog.at_level(logging.WARNING):
        disc._execute_discovery_operation(client, "ecs", R, _op(disc, "ecs", 0))
        disc._execute_discovery_operation(client, "ecs", R, _op(disc, "ecs", 1))
    assert _warnings(caplog) == [
        "No permission for ecs (list_services in us-east-1: "
        "AccessDeniedException). Some resources of ecs are skipped; add the "
        "read permission to see them."
    ]
    assert [r["resource_type"] for r in disc.resources] == ["Cluster"]
    assert disc.coverage.summary() == {"ok": 1, "denied": 1}


def _billing_client(error):
    class CE:
        def get_cost_and_usage(self, **kw):
            if isinstance(error, Exception):
                raise error
            return error

    return CE()


def _client_error(code):
    return ClientError({"Error": {"Code": code, "Message": "secret-detail"}}, "Op")


BAD_AMOUNT = {
    "ResultsByTime": [
        {
            "Groups": [
                {
                    "Keys": ["AWS Lambda"],
                    "Metrics": {
                        "BlendedCost": {"Amount": "12,5"},
                        "UsageQuantity": {"Amount": "1"},
                    },
                }
            ]
        }
    ]
}

TAIL = " so billing data is missing and billing checks are skipped. "
CASES = [
    (
        _client_error("AccessDeniedException"),
        "Cost Explorer was denied (AccessDeniedException)," + TAIL + "Allow "
        "ce:GetCostAndUsage for this role.",
    ),
    (
        _client_error("OptInRequired"),
        "Cost Explorer is not enabled for this account (OptInRequired),"
        + TAIL
        + "Enable Cost Explorer in the AWS Billing console.",
    ),
    (
        _client_error("ThrottlingException"),
        "Cost Explorer was throttled (ThrottlingException),"
        + TAIL
        + "Run the scan again later.",
    ),
    (
        _client_error("InternalFailure"),
        "Cost Explorer could not be read (InternalFailure),"
        + TAIL
        + "Run the scan again; if it repeats, report it with the --debug log.",
    ),
    (
        BAD_AMOUNT,
        "Cost Explorer returned an answer InvenTag could not read,"
        + TAIL
        + "Run the scan again; if it repeats, report it with the --debug log.",
    ),
]


@pytest.mark.parametrize("answer, text", CASES)
def test_inventory_says_one_true_line_for_a_cost_explorer_failure(
    answer, text, caplog, monkeypatch
):
    inv = object.__new__(inventory_module.AWSResourceInventory)
    inv.session = mock.MagicMock()
    inv.logger = logging.getLogger("test.inventory.billing")
    inv.coverage = CoverageLedger("111122223333")
    inv.enable_billing_validation = True
    monkeypatch.setattr(
        inventory_module, "create_client", lambda *a, **k: _billing_client(answer)
    )
    with caplog.at_level(logging.WARNING):
        inv._discover_services_via_billing()
    assert _warnings(caplog) == [text]
    assert "secret-detail" not in caplog.text
    assert inv.enable_billing_validation is False


@pytest.mark.parametrize("answer, text", CASES)
def test_comprehensive_says_the_same_line_when_it_runs_alone(answer, text, caplog):
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=[R], enable_billing_validation=True
    )
    disc._client = lambda *a, **k: _billing_client(answer)
    with caplog.at_level(logging.WARNING):
        disc._discover_billing_services()
        disc._validate_with_billing()
    assert _warnings(caplog) == [text]
    assert "secret-detail" not in caplog.text
