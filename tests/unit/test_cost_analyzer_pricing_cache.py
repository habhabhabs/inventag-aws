"""Pricing API lookups are cached per full lookup key, failures included."""

import json
import logging
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from inventag.discovery.cost_analyzer import CostAnalyzer

N_PER_KEY = 12


def _price_list():
    product = {
        "product": {"attributes": {}},
        "terms": {
            "OnDemand": {
                "t": {
                    "priceDimensions": {
                        "d": {"unit": "Hrs", "pricePerUnit": {"USD": "0.1"}}
                    }
                }
            }
        },
    }
    return [json.dumps(product)]


def _analyzer(client):
    session = Mock()
    session.client.return_value = client
    analyzer = CostAnalyzer(session=session)
    analyzer._PRICING_RETRY_DELAY = 0
    return analyzer


def _resources():
    """3 distinct lookup keys: two EC2 instance types and one Lambda region."""
    out = []
    for i in range(N_PER_KEY):
        out.append(
            {
                "service": "EC2",
                "type": "Instance",
                "id": f"i-a{i}",
                "region": "us-east-1",
                "instance_type": "t3.micro",
            }
        )
        out.append(
            {
                "service": "EC2",
                "type": "Instance",
                "id": f"i-b{i}",
                "region": "us-east-1",
                "instance_type": "m5.large",
            }
        )
        out.append(
            {
                "service": "LAMBDA",
                "type": "Function",
                "id": f"f{i}",
                "region": "eu-west-1",
            }
        )
    return out


def test_successful_lookups_cost_one_call_per_distinct_key():
    client = Mock()
    client.get_products.return_value = {"PriceList": _price_list()}
    analyzer = _analyzer(client)
    estimates = analyzer.estimate_resource_costs(_resources())
    assert len(estimates) == 3 * N_PER_KEY
    assert client.get_products.call_count == 3


def test_failed_lookups_are_cached_and_warned_once(caplog):
    client = Mock()
    client.get_products.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameterException", "Message": "bad filter"}},
        "GetProducts",
    )
    analyzer = _analyzer(client)
    with caplog.at_level(logging.WARNING):
        estimates = analyzer.estimate_resource_costs(_resources())
    assert estimates == []
    assert client.get_products.call_count == 3
    warnings = [r for r in caplog.records if "Pricing API lookup failed" in r.message]
    assert len(warnings) == 1


def test_denied_lookup_warns_once_and_is_not_repeated(caplog):
    client = Mock()
    client.get_products.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "GetProducts"
    )
    analyzer = _analyzer(client)
    with caplog.at_level(logging.WARNING):
        analyzer.estimate_resource_costs(_resources())
    assert client.get_products.call_count == 3
    assert len([r for r in caplog.records if "was denied" in r.message]) == 1


def test_empty_price_list_is_cached():
    client = Mock()
    client.get_products.return_value = {"PriceList": []}
    analyzer = _analyzer(client)
    analyzer.estimate_resource_costs(_resources())
    assert client.get_products.call_count == 3


def test_instance_types_do_not_share_a_price():
    prices = {"t3.micro": "0.01", "m5.large": "0.10"}

    def get_products(ServiceCode, Filters, MaxResults):
        itype = next(f["Value"] for f in Filters if f["Field"] == "instanceType")
        product = json.loads(_price_list()[0])
        dim = product["terms"]["OnDemand"]["t"]["priceDimensions"]["d"]
        dim["pricePerUnit"]["USD"] = prices[itype]
        return {"PriceList": [json.dumps(product)]}

    client = Mock()
    client.get_products.side_effect = get_products
    analyzer = _analyzer(client)
    small = analyzer._get_pricing_info(
        "EC2", "Instance", "us-east-1", {"instance_type": "t3.micro"}
    )
    large = analyzer._get_pricing_info(
        "EC2", "Instance", "us-east-1", {"instance_type": "m5.large"}
    )
    assert str(small["price_per_unit"]) == "0.01"
    assert str(large["price_per_unit"]) == "0.10"


def test_unmapped_service_makes_no_call():
    client = Mock()
    analyzer = _analyzer(client)
    assert analyzer._get_pricing_info("NOPE", "X", "us-east-1", {}) is None
    client.get_products.assert_not_called()


def _throttled():
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "slow down"}},
        "GetProducts",
    )


def test_throttled_lookup_is_retried_once_then_cached(caplog):
    client = Mock()
    client.get_products.side_effect = _throttled()
    analyzer = _analyzer(client)
    with caplog.at_level(logging.WARNING):
        estimates = analyzer.estimate_resource_costs(_resources())
    assert estimates == []
    # one retry per distinct key, then the failure is cached for the run
    assert client.get_products.call_count == 6
    warnings = [r for r in caplog.records if "Pricing API lookup failed" in r.message]
    assert len(warnings) == 1


def test_throttled_lookup_recovers_on_retry():
    client = Mock()
    client.get_products.side_effect = [_throttled(), {"PriceList": _price_list()}]
    analyzer = _analyzer(client)
    resource = {"instance_type": "t3.micro"}
    first = analyzer._get_pricing_info("EC2", "Instance", "us-east-1", resource)
    again = analyzer._get_pricing_info("EC2", "Instance", "us-east-1", resource)
    assert str(first["price_per_unit"]) == "0.1"
    assert str(again["price_per_unit"]) == "0.1"
    assert client.get_products.call_count == 2


def test_resource_types_sharing_a_key_keep_their_own_cost_factors():
    client = Mock()
    client.get_products.return_value = {"PriceList": _price_list()}
    analyzer = _analyzer(client)
    # EC2 snapshots and security groups get the same filters (location only)
    snap = analyzer._get_pricing_info("EC2", "Snapshot", "us-east-1", {})
    sg = analyzer._get_pricing_info("EC2", "SecurityGroup", "us-east-1", {})
    assert client.get_products.call_count == 1
    assert snap["cost_factors"]["resource_type"] == "Snapshot"
    assert sg["cost_factors"]["resource_type"] == "SecurityGroup"
    assert snap["cost_factors"] is not sg["cost_factors"]


def test_key_locks_are_released_after_lookup():
    client = Mock()
    client.get_products.return_value = {"PriceList": _price_list()}
    analyzer = _analyzer(client)
    analyzer.estimate_resource_costs(_resources())
    assert analyzer._pricing_key_locks == {}
    assert len(analyzer._pricing_cache) == 3


def test_pricing_client_uses_the_account_session():
    session = Mock()
    analyzer = CostAnalyzer(session=session)
    client = analyzer._get_pricing_client()
    session.client.assert_called_once_with("pricing", region_name="us-east-1")
    assert client is session.client.return_value
    assert analyzer._get_pricing_client() is client
    session.client.assert_called_once()
