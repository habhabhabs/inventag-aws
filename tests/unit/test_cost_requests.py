"""F1b (architect rulings 3 and 5): the run says how many Cost Explorer
requests it will make, once, before discovery; and a run with several accounts
says whose bill the cost trend read (A-80).

Billing validation makes one request for each account; --enable-cost-analysis
makes one more for the whole run, with the first account's credentials.
"""

import dataclasses

import botocore.client
import pytest

from inventag.core import cost_requests
from tests.regression import scenarios
from tests.regression.checks import evaluate
from tests.regression.runner import run_in_process

PREFIX = "Cost Explorer: up to "


def line(total, billing, trend):
    return (
        f"Cost Explorer: up to {total} request(s) in this run "
        f"(billing validation: {billing}; cost trend: {trend}). AWS charges for each."
    )


TREND_NOTE = (
    "Cost trend: read once, with the credentials of account 111111111111. "
    "Its figures are that account's Cost Explorer view, not each account's own."
)


# --- the count (pure) -------------------------------------------------------


@pytest.mark.parametrize(
    "accounts, billing, cost, total, parts",
    [
        (1, True, False, 1, (("billing validation", 1), ("cost trend", 0))),
        (1, True, True, 2, (("billing validation", 1), ("cost trend", 1))),
        (1, False, True, 1, (("billing validation", 0), ("cost trend", 1))),
        (1, False, False, 0, (("billing validation", 0), ("cost trend", 0))),
        (3, True, False, 3, (("billing validation", 3), ("cost trend", 0))),
        (3, True, True, 4, (("billing validation", 3), ("cost trend", 1))),
        (3, False, True, 1, (("billing validation", 0), ("cost trend", 1))),
        (0, True, True, 0, (("billing validation", 0), ("cost trend", 0))),
    ],
)
def test_planned_counts(accounts, billing, cost, total, parts):
    assert cost_requests.planned(accounts, billing, cost) == (total, parts)


def test_the_line_golden():
    assert cost_requests.announcement(*cost_requests.planned(3, True, True)) == line(
        4, 3, 1
    )


def test_no_line_when_nothing_is_planned():
    assert cost_requests.announcement(0, ()) is None


def test_trend_note_golden():
    assert cost_requests.trend_note("111111111111") == TREND_NOTE


# --- the whole CLI against moto ---------------------------------------------


def _run(tmp_path, monkeypatch, billing, args=(), accounts=()):
    order = []
    real_call = botocore.client.BaseClient._make_api_call
    real_announcement = cost_requests.announcement

    def spy_call(client, operation, params):
        if operation == "GetCostAndUsage":
            order.append("request")
        return real_call(client, operation, params)

    def spy_announcement(*a):
        text = real_announcement(*a)
        if text:
            order.append("line")
        return text

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", spy_call)
    monkeypatch.setattr(cost_requests, "announcement", spy_announcement)
    base = scenarios.BY_ID["S1-E-cost-analysis-calls-cost-explorer"]
    sc = dataclasses.replace(
        base, billing=billing, args=tuple(args), accounts=tuple(accounts), faults=()
    )
    outcome = run_in_process(sc, tmp_path, monkeypatch)
    return outcome, order


def _lines(outcome):
    return [
        text[text.index(PREFIX) :]
        for text in outcome.text.splitlines()
        if PREFIX in text
    ]


def test_one_account_billing_and_cost_analysis_says_2_before_the_first_request(
    tmp_path, monkeypatch
):
    outcome, order = _run(tmp_path, monkeypatch, True, ("--enable-cost-analysis",))
    assert outcome.code == 0
    assert _lines(outcome) == [line(2, 1, 1)]
    assert order[0] == "line"
    assert order.count("line") == 1
    assert order.count("request") == 2


def test_one_account_billing_only_says_1(tmp_path, monkeypatch):
    outcome, order = _run(tmp_path, monkeypatch, True)
    assert outcome.code == 0
    assert _lines(outcome) == [line(1, 1, 0)]
    assert order[0] == "line"


def test_no_cost_explorer_request_no_line(tmp_path, monkeypatch):
    outcome, order = _run(tmp_path, monkeypatch, False)
    assert outcome.code == 0
    assert _lines(outcome) == []
    assert order == []


def test_one_account_has_no_trend_note(tmp_path, monkeypatch):
    outcome, _ = _run(tmp_path, monkeypatch, False, ("--enable-cost-analysis",))
    assert outcome.code == 0
    assert "Cost trend: read once" not in outcome.text
    assert evaluate(("report_text", "Cost trend: read once"), outcome) is not None


def test_three_accounts_say_4_and_name_the_trend_account(tmp_path, monkeypatch):
    outcome, order = _run(
        tmp_path,
        monkeypatch,
        True,
        ("--enable-cost-analysis",),
        accounts=("A", "B", "C"),
    )
    assert outcome.code == 0
    assert _lines(outcome) == [line(4, 3, 1)]
    assert order[0] == "line"
    # billing validation once for each account, the cost trend once
    assert order.count("request") == 4
    # one WARNING line on the console (the run notes do not repeat it)
    assert outcome.text.count(TREND_NOTE) == 1
    # and the report's run notes say it
    assert evaluate(("report_text", TREND_NOTE), outcome) is None
