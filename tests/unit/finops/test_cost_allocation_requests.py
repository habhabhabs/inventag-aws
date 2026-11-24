"""`inventag.finops.cost_allocation.read_account`: the request budget, the
order of the requests, the tables, and what a failed request leaves."""

import datetime as dt

import pytest
from botocore.stub import Stubber

from inventag.finops import cost_allocation as ca
from tests.unit.finops import cost_stubs as cs

RUN = dt.datetime(2026, 11, 24, 3, 0, tzinfo=dt.timezone.utc)


def read(stub_client):
    return ca.read_account(stub_client, "111122223333", RUN, keys=list(cs.KEYS))


def calls(stub):
    # Stubber raises on any request it did not expect; an empty queue at the
    # end means every expected request was made.
    stub.assert_no_pending_responses()


# ------------------------------------------------------------ the budget
def test_the_budget_is_7_requests_per_account():
    assert ca.MAX_REQUESTS_PER_ACCOUNT == 7
    assert ca.MAX_PAGES_PER_GROUPING == 3
    assert ca.planned_requests(1) == 7
    assert ca.planned_requests(3) == 21
    assert ca.planned_requests(0) == 0


def test_the_keys_are_those_of_the_builtin_policy():
    assert ca.allocation_keys() == cs.KEYS


@pytest.mark.parametrize(
    "active, expected",
    [(tuple(cs.KEYS), 7), (("Owner",), 4), ((), 3)],
)
def test_requests_with_4_1_and_0_active_keys(active, expected):
    c = cs.client()
    inactive = [k for k in cs.KEYS if k not in active]
    with cs.full_stub(c, active=active, inactive=inactive) as stub:
        found = read(c)
        calls(stub)
    assert found["requests"] == expected
    assert found["metric"] == "UnblendedCost"
    assert found["period"] == {"start": "2026-10-01", "end": "2026-11-01"}
    for key in cs.KEYS:
        table = found["tables"][f"tag:{key}"]
        if key in active:
            assert table["status"] == "read"
        else:
            assert table == {"status": "not_active", "currency": "", "rows": []}


def test_a_key_that_is_not_a_cost_allocation_tag_is_not_queried():
    c = cs.client()
    with cs.full_stub(c, active=("Owner",), inactive=()) as stub:
        found = read(c)
        calls(stub)
    statuses = {t["key"]: t["status"] for t in found["tag_keys"]}
    assert statuses == {
        "CostCenter": "not_found",
        "Owner": "active",
        "Project": "not_found",
        "Environment": "not_found",
    }
    assert found["requests"] == 4


# ------------------------------------------------------------ the tables
def test_tables_hold_the_amounts_as_aws_returns_them():
    c = cs.client()
    with cs.full_stub(c) as stub:
        found = read(c)
        calls(stub)
    assert found["tables"]["service"] == {
        "status": "read",
        "currency": "USD",
        "rows": [
            {"name": "Amazon Simple Storage Service", "amount": "12.5", "unit": "USD"},
            {"name": "AmazonCloudWatch", "amount": "0.31", "unit": "USD"},
        ],
    }
    assert found["tables"]["linked_account"]["rows"] == [
        {"name": "111122223333", "amount": "12.81", "unit": "USD"}
    ]
    assert list(found["tables"]) == [
        "service",
        "linked_account",
        "tag:CostCenter",
        "tag:Owner",
        "tag:Project",
        "tag:Environment",
    ]


def test_spend_without_the_tag_is_the_no_value_row():
    c = cs.client()
    with cs.full_stub(c) as stub:
        found = read(c)
        calls(stub)
    assert found["tables"]["tag:CostCenter"]["rows"] == [
        {"name": "(no value)", "amount": "2.81", "unit": "USD"},
        {"name": "CC-1234", "amount": "10.0", "unit": "USD"},
    ]


# ------------------------------------------------------------ the period
@pytest.mark.parametrize(
    "started, period",
    [
        (
            dt.datetime(2026, 11, 24, tzinfo=dt.timezone.utc),
            ("2026-10-01", "2026-11-01"),
        ),
        (dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc), ("2025-12-01", "2026-01-01")),
        (
            dt.datetime(2026, 3, 31, 23, 0, tzinfo=dt.timezone.utc),
            ("2026-02-01", "2026-03-01"),
        ),
    ],
)
def test_the_period_is_the_last_full_month_before_the_run(started, period):
    assert ca.last_full_month(started) == period


def test_a_run_start_without_a_time_zone_is_refused():
    with pytest.raises(ValueError):
        ca.last_full_month(dt.datetime(2026, 11, 24))


# ------------------------------------------------------------ failures
def test_a_denied_tag_list_queries_every_key_and_stays_within_7():
    c = cs.client()
    stub = Stubber(c)
    stub.add_client_error(
        "list_cost_allocation_tags", "AccessDeniedException", http_status_code=400
    )
    cs.expect_usage(stub, "DIMENSION", "SERVICE", cs.usage(cs.SERVICES))
    cs.expect_usage(stub, "DIMENSION", "LINKED_ACCOUNT", cs.usage(cs.ACCOUNTS))
    for key in cs.KEYS:
        cs.expect_usage(stub, "TAG", key, cs.usage(cs.tag_groups(key)))
    with stub:
        found = read(c)
        calls(stub)
    assert found["requests"] == 7
    assert {t["status"] for t in found["tag_keys"]} == {"unknown"}
    assert found["failed"] == [
        {
            "operation": "ListCostAllocationTags",
            "status": "denied",
            "code": "AccessDeniedException",
        }
    ]
    assert ca.denials(ca.result([found])) == [
        ("111122223333", "ce", "ListCostAllocationTags")
    ]


def test_a_denied_and_a_throttled_grouping_are_noted_and_the_rest_is_read():
    c = cs.client()
    stub = Stubber(c)
    stub.add_response(
        "list_cost_allocation_tags", cs.tag_list(active=["Owner"]), {"TagKeys": cs.KEYS}
    )
    stub.add_client_error(
        "get_cost_and_usage", "AccessDeniedException", http_status_code=400
    )
    stub.add_client_error(
        "get_cost_and_usage", "ThrottlingException", http_status_code=400
    )
    cs.expect_usage(stub, "TAG", "Owner", cs.usage(cs.tag_groups("Owner")))
    with stub:
        found = read(c)
        calls(stub)
    tables = found["tables"]
    assert tables["service"]["status"] == "denied"
    assert tables["linked_account"]["status"] == "throttled"
    assert tables["tag:Owner"]["status"] == "read"
    notes = ca.run_notes(ca.result([found]))
    assert notes == [
        "Cost allocation in account 111122223333: Service (not read: access "
        "denied); Linked account (not read: throttled)."
    ]


# ------------------------------------------------------------ pages
def test_pages_are_followed_within_the_budget_and_counted():
    c = cs.client()
    stub = Stubber(c)
    stub.add_response("list_cost_allocation_tags", cs.tag_list(), {"TagKeys": cs.KEYS})
    cs.expect_usage(stub, "DIMENSION", "SERVICE", cs.usage(cs.SERVICES[:1], token="p2"))
    cs.expect_usage(stub, "DIMENSION", "LINKED_ACCOUNT", cs.usage(cs.ACCOUNTS))
    cs.expect_usage(
        stub, "DIMENSION", "SERVICE", cs.usage(cs.SERVICES[1:], token="p3"), token="p2"
    )
    cs.expect_usage(stub, "DIMENSION", "SERVICE", cs.usage([]), token="p3")
    with stub:
        found = read(c)
        calls(stub)
    assert found["requests"] == 5
    assert found["tables"]["service"]["status"] == "read"
    assert [r["name"] for r in found["tables"]["service"]["rows"]] == [
        "Amazon Simple Storage Service",
        "AmazonCloudWatch",
    ]


def test_at_most_3_pages_per_grouping_then_incomplete():
    c = cs.client()
    stub = Stubber(c)
    stub.add_response("list_cost_allocation_tags", cs.tag_list(), {"TagKeys": cs.KEYS})
    cs.expect_usage(stub, "DIMENSION", "SERVICE", cs.usage(cs.SERVICES, token="t1"))
    cs.expect_usage(stub, "DIMENSION", "LINKED_ACCOUNT", cs.usage(cs.ACCOUNTS))
    for n in (1, 2, 3):
        cs.expect_usage(
            stub, "DIMENSION", "SERVICE", cs.usage([], token=f"t{n + 1}"), token=f"t{n}"
        )
    with stub:
        found = read(c)
        calls(stub)
    assert found["requests"] == 6
    assert found["tables"]["service"]["status"] == "incomplete"


def test_with_4_active_keys_a_next_page_is_not_requested():
    c = cs.client()
    stub = Stubber(c)
    stub.add_response(
        "list_cost_allocation_tags", cs.tag_list(cs.KEYS), {"TagKeys": cs.KEYS}
    )
    # The SERVICE answer says there is more; no request is left for it.
    cs.expect_usage(stub, "DIMENSION", "SERVICE", cs.usage(cs.SERVICES, token="more"))
    cs.expect_usage(stub, "DIMENSION", "LINKED_ACCOUNT", cs.usage(cs.ACCOUNTS))
    for key in cs.KEYS:
        cs.expect_usage(stub, "TAG", key, cs.usage(cs.tag_groups(key)))
    with stub:
        found = read(c)
        calls(stub)
    assert found["requests"] == 7
    assert found["tables"]["service"]["status"] == "incomplete"


# ------------------------------------------------------------ outputs
def test_result_sorts_accounts_and_snapshot_totals_hold_tables_only():
    a = {
        "account": "2",
        "period": {"start": "s", "end": "e"},
        "metric": "UnblendedCost",
        "requests": 3,
        "tag_keys": [],
        "tables": {"service": {"status": "read", "currency": "USD", "rows": []}},
        "failed": [],
    }
    b = dict(a, account="1")
    costs = ca.result([a, b])
    assert [x["account"] for x in costs["accounts"]] == ["1", "2"]
    totals = ca.snapshot_totals(costs)
    assert totals == {
        "schema_version": 1,
        "metric": "UnblendedCost",
        "accounts": [
            {
                "account": n,
                "period": {"start": "s", "end": "e"},
                "tables": {
                    "service": {"status": "read", "currency": "USD", "rows": []}
                },
            }
            for n in ("1", "2")
        ],
    }
    assert ca.for_account(costs, "2")["accounts"] == [a]
