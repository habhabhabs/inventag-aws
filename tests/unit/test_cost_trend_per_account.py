"""P7 (v1.5.0, plan decisions 6 and 7): the cost trend per account and service.

A-80: one Cost Explorer request per account, with that account's session.
A-81: a service is found in the bill by the billing-name table of discovery (S3,
SQS and SNS get a trend, "EC2" does not take ECR's figure); a full month is
compared with the full month before it; ``NextPageToken`` is followed within a
stated count; the trend is one entry per account and service, not a service
total divided over its resources.
A-83 (a): a failed trend request is one WARNING.
"""

import dataclasses
import datetime as dt
import json
import logging
from decimal import Decimal
from unittest import mock

import pytest
from botocore.exceptions import ClientError
from openpyxl import Workbook

from inventag.core import cost_requests
from inventag.discovery import cost_analyzer as cost_module
from inventag.discovery.cost_analyzer import CostAnalyzer
from inventag.reporting.converter import BOMConverter
from tests.regression import scenarios
from tests.regression.faults import Fault
from tests.regression.runner import run_in_process

NOW = dt.datetime(2026, 11, 24, 9, 30, tzinfo=dt.timezone.utc)
SEPT, OCT = "2026-09-01", "2026-10-01"


def _group(name, amount, unit="USD"):
    return {
        "Keys": [name],
        "Metrics": {"BlendedCost": {"Amount": str(amount), "Unit": unit}},
    }


def _period(start, end, groups):
    return {"TimePeriod": {"Start": start, "End": end}, "Groups": groups}


def bill(sept, octo, token=None):
    """A Cost Explorer answer for September and October 2026."""
    answer = {
        "ResultsByTime": [
            _period(SEPT, OCT, [_group(n, a) for n, a in sept.items()]),
            _period(OCT, "2026-11-01", [_group(n, a) for n, a in octo.items()]),
        ]
    }
    if token:
        answer["NextPageToken"] = token
    return answer


BILL_A = bill(
    {
        "Amazon Elastic Compute Cloud - Compute": 100,
        "Amazon EC2 Container Registry (ECR)": 7,
        "Amazon Simple Storage Service": 10,
        "Amazon Simple Queue Service": 2,
        "Amazon Simple Notification Service": 4,
    },
    {
        "Amazon Elastic Compute Cloud - Compute": 120,
        "Amazon EC2 Container Registry (ECR)": 9,
        "Amazon Simple Storage Service": 10,
        "Amazon Simple Queue Service": 3,
        "Amazon Simple Notification Service": 1,
    },
)
BILL_B = bill(
    {"Amazon Elastic Compute Cloud - Compute": 5, "Amazon Simple Storage Service": 1},
    {"Amazon Elastic Compute Cloud - Compute": 6, "Amazon Simple Storage Service": 4},
)

ROWS = [
    {"id": "i-a1", "service": "EC2", "source_account_id": "111111111111"},
    {"id": "i-a2", "service": "EC2", "source_account_id": "111111111111"},
    {"id": "b-a", "service": "S3", "source_account_id": "111111111111"},
    {"id": "q-a", "service": "SQS", "source_account_id": "111111111111"},
    {"id": "t-a", "service": "sns", "source_account_id": "111111111111"},
    {"id": "i-b", "service": "EC2", "source_account_id": "222222222222"},
    {"id": "b-b", "service": "s3", "source_account_id": "222222222222"},
]


class CostExplorer:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def get_cost_and_usage(self, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


class Lines(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append((record.levelno, record.getMessage()))


def _setup(monkeypatch, clients):
    """``clients``: session -> CostExplorer stub. Returns (analyzer, sessions, log)."""
    made = []

    def create_client(session, service, *a, **k):
        assert service == "ce"
        made.append(session)
        return clients[session]

    monkeypatch.setattr(cost_module, "create_client", create_client)
    analyzer = CostAnalyzer(session=mock.MagicMock(name="processor-session"))
    log = Lines()
    analyzer.logger.addHandler(log)
    analyzer.made_with = made
    return analyzer, log


def _two_accounts(monkeypatch, a=BILL_A, b=BILL_B):
    sa, sb = mock.MagicMock(name="session-a"), mock.MagicMock(name="session-b")
    ce_a, ce_b = CostExplorer(a), CostExplorer(b)
    analyzer, log = _setup(monkeypatch, {sa: ce_a, sb: ce_b})
    sessions = {"111111111111": sa, "222222222222": sb}
    return analyzer, log, sessions, ce_a, ce_b


def _by_key(trends):
    return {(t.account_id, t.service): t for t in trends}


# --- A-80: one request per account, with that account's session -------------


def test_each_account_is_read_once_with_its_own_session(monkeypatch):
    analyzer, _, sessions, ce_a, ce_b = _two_accounts(monkeypatch)
    analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    assert len(ce_a.calls) == 1 and len(ce_b.calls) == 1
    assert analyzer.made_with == [sessions["111111111111"], sessions["222222222222"]]


def test_each_accounts_trend_is_its_own(monkeypatch):
    analyzer, _, sessions, _, _ = _two_accounts(monkeypatch)
    trends = _by_key(
        analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    )
    ec2_a = trends[("111111111111", "EC2")]
    ec2_b = trends[("222222222222", "EC2")]
    assert (ec2_a.previous_monthly_cost, ec2_a.current_monthly_cost) == (
        Decimal("100"),
        Decimal("120"),
    )
    assert (ec2_b.previous_monthly_cost, ec2_b.current_monthly_cost) == (
        Decimal("5"),
        Decimal("6"),
    )
    s3_b = trends[("222222222222", "s3")]
    assert s3_b.cost_change_percentage == 300.0
    assert s3_b.trend_direction == "increasing"


def test_an_account_without_a_session_is_not_read_with_another_ones(monkeypatch):
    analyzer, _, sessions, ce_a, ce_b = _two_accounts(monkeypatch)
    del sessions["222222222222"]
    trends = analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    assert len(ce_a.calls) == 1 and ce_b.calls == []
    assert {t.account_id for t in trends} == {"111111111111"}


# --- A-81: billing names, whole months, pages ------------------------------


def test_s3_sqs_and_sns_get_a_trend(monkeypatch):
    analyzer, _, sessions, _, _ = _two_accounts(monkeypatch)
    trends = _by_key(
        analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    )
    assert trends[("111111111111", "S3")].current_monthly_cost == Decimal("10")
    assert trends[("111111111111", "SQS")].current_monthly_cost == Decimal("3")
    assert trends[("111111111111", "sns")].current_monthly_cost == Decimal("1")


def test_ec2_does_not_take_ecrs_figure(monkeypatch):
    analyzer, _, sessions, _, _ = _two_accounts(monkeypatch)
    ec2 = _by_key(
        analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    )[("111111111111", "EC2")]
    assert ec2.current_monthly_cost == Decimal("120")
    assert ec2.billing_names == ("Amazon Elastic Compute Cloud - Compute",)


def test_the_request_is_the_two_full_months_before_the_run(monkeypatch):
    analyzer, _, sessions, ce_a, _ = _two_accounts(monkeypatch)
    analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    (call,) = ce_a.calls
    assert call["TimePeriod"] == {"Start": SEPT, "End": "2026-11-01"}
    assert call["Granularity"] == "MONTHLY"
    assert call["GroupBy"] == [{"Type": "DIMENSION", "Key": "SERVICE"}]


def test_months_are_matched_by_their_dates_not_their_place(monkeypatch):
    shuffled = bill(
        {"Amazon Simple Storage Service": 8}, {"Amazon Simple Storage Service": 2}
    )
    shuffled["ResultsByTime"].reverse()
    analyzer, _, sessions, _, _ = _two_accounts(monkeypatch, a=shuffled)
    s3 = _by_key(
        analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    )[("111111111111", "S3")]
    assert (s3.previous_month, s3.current_month) == ("2026-09", "2026-10")
    assert (s3.previous_monthly_cost, s3.current_monthly_cost) == (
        Decimal("8"),
        Decimal("2"),
    )


def test_a_second_page_is_read_and_merged(monkeypatch):
    first = bill({"Amazon Simple Storage Service": 1}, {}, token="page-2")
    second = bill({}, {"Amazon Simple Storage Service": 5})
    analyzer, _, sessions, ce_a, _ = _two_accounts(monkeypatch, a=None)
    ce_a.answers = [first, second]
    s3 = _by_key(
        analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    )[("111111111111", "S3")]
    assert [c.get("NextPageToken") for c in ce_a.calls] == [None, "page-2"]
    assert (s3.previous_monthly_cost, s3.current_monthly_cost) == (
        Decimal("1"),
        Decimal("5"),
    )


def test_pages_stop_at_the_stated_count_with_one_warning(monkeypatch):
    endless = bill({"Amazon Simple Storage Service": 1}, {}, token="more")
    analyzer, log, sessions, ce_a, _ = _two_accounts(monkeypatch, a=endless)
    analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    assert len(ce_a.calls) == cost_module.TREND_PAGES_PER_ACCOUNT == 2
    warnings = [m for level, m in log.lines if level >= logging.WARNING]
    assert warnings == [
        "Cost analysis: the cost trend of an account has more than 2 "
        "page(s); the services on later pages have no trend in this report."
    ]


# --- A-83 (a): a failed request is one warning -------------------------------


def test_a_throttled_request_is_one_warning(monkeypatch):
    error = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "secret-detail"}},
        "GetCostAndUsage",
    )
    analyzer, log, sessions, ce_a, _ = _two_accounts(monkeypatch, a=error)
    trends = analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    assert len(ce_a.calls) == 1
    assert {t.account_id for t in trends} == {"222222222222"}
    warnings = [m for level, m in log.lines if level >= logging.WARNING]
    assert warnings == [
        "Cost analysis: the cost trend request of an account failed "
        "(ThrottlingException); that account has no trend. Run with --debug for "
        "the detail."
    ]


def test_a_denied_request_is_one_warning_and_a_permissions_entry(monkeypatch):
    error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no"}},
        "GetCostAndUsage",
    )
    analyzer, log, sessions, _, _ = _two_accounts(monkeypatch, a=error, b=error)
    assert analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW) == []
    warnings = [m for level, m in log.lines if level >= logging.WARNING]
    assert warnings == [
        "Cost analysis: access to the cost-explorer API was denied "
        "(AccessDeniedException). Cost and activity data from it will be missing."
    ]
    assert analyzer.permission_denials() == [
        ("ce", "GetCostAndUsage", "AccessDeniedException")
    ]


# --- the shape: per account and service, not per resource -------------------


def test_one_entry_per_account_and_service_with_the_whole_figure(monkeypatch):
    analyzer, _, sessions, _, _ = _two_accounts(monkeypatch)
    trends = analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    keys = [(t.account_id, t.service) for t in trends]
    assert keys == sorted(set(keys))
    assert len(keys) == 6  # 4 services of account A, 2 of account B
    ec2 = _by_key(trends)[("111111111111", "EC2")]
    assert ec2.resource_count == 2
    assert not hasattr(ec2, "resource_id")


def test_one_account_without_account_sessions_uses_the_analyzers_session(monkeypatch):
    ce = CostExplorer(BILL_A)
    analyzer, _ = _setup(monkeypatch, {})
    analyzer.cost_explorer_client = ce
    rows = [r for r in ROWS if r["source_account_id"] == "111111111111"]
    trends = analyzer.analyze_cost_trends(rows, now=NOW)
    assert len(ce.calls) == 1
    assert {t.account_id for t in trends} == {"111111111111"}


def test_the_processor_hands_over_the_account_sessions(monkeypatch):
    from inventag.reporting.bom_processor import BOMDataProcessor, BOMProcessingConfig

    sessions = {"111111111111": mock.MagicMock(), "222222222222": mock.MagicMock()}
    processor = BOMDataProcessor(
        BOMProcessingConfig(enable_cost_analysis=True),
        session=mock.MagicMock(),
        account_sessions=sessions,
    )
    seen = {}
    trend = cost_module.CostTrendAnalysis(
        account_id="111111111111",
        service="EC2",
        current_monthly_cost=Decimal("120"),
        previous_monthly_cost=Decimal("100"),
        cost_change_percentage=20.0,
        trend_direction="increasing",
        current_month="2026-10",
        previous_month="2026-09",
        resource_count=2,
        billing_names=("Amazon Elastic Compute Cloud - Compute",),
        unit="USD",
    )

    def analyze(resources, account_sessions=None, now=None):
        seen["sessions"] = account_sessions
        return [trend]

    analyzer = processor.cost_analyzer
    monkeypatch.setattr(analyzer, "estimate_resource_costs", lambda r: [])
    monkeypatch.setattr(analyzer, "detect_forgotten_resources", lambda r: [])
    monkeypatch.setattr(analyzer, "analyze_cost_trends", analyze)
    result = processor._generate_cost_analysis(ROWS)
    assert seen["sessions"] == sessions
    assert result["cost_trends"] == [
        {
            "account_id": "111111111111",
            "service": "EC2",
            "billing_names": ["Amazon Elastic Compute Cloud - Compute"],
            "resource_count": 2,
            "previous_month": "2026-09",
            "current_month": "2026-10",
            "previous_monthly_cost": 100.0,
            "current_monthly_cost": 120.0,
            "cost_change_percentage": 20.0,
            "trend_direction": "increasing",
            "alert_triggered": False,
            "unit": "USD",
        }
    ]


def test_the_cost_sheet_shows_the_trend_per_account_and_service():
    converter = BOMConverter()
    converter.cost_analysis = {
        "summary": {},
        "cost_trends": [
            {
                "account_id": "111111111111",
                "service": "EC2",
                "billing_names": ["Amazon Elastic Compute Cloud - Compute"],
                "resource_count": 2,
                "previous_month": "2026-09",
                "current_month": "2026-10",
                "previous_monthly_cost": 100.0,
                "current_monthly_cost": 120.0,
                "cost_change_percentage": 20.0,
                "trend_direction": "increasing",
                "alert_triggered": False,
                "unit": "USD",
            }
        ],
    }
    wb = Workbook()
    converter._create_cost_analysis_sheet(wb)
    rows = [list(r) for r in wb["Cost Analysis"].iter_rows(values_only=True)]
    title = [
        "Billed cost by account and service, last two full months (Cost "
        "Explorer; a service total, not a resource's cost)"
    ]
    at = [r[:1] for r in rows].index(title)
    assert rows[at + 1][:10] == [
        "Account",
        "Service",
        "Resources",
        "Earlier month",
        "Billed (USD)",
        "Later month",
        "Billed (USD)",
        "Change %",
        "Direction",
        "Billing names counted",
    ]
    assert rows[at + 2][:10] == [
        "111111111111",
        "EC2",
        2,
        "2026-09",
        100.0,
        "2026-10",
        120.0,
        20.0,
        "increasing",
        "Amazon Elastic Compute Cloud - Compute",
    ]


# --- the stated count ---------------------------------------------------------


@pytest.mark.parametrize("accounts, trend", [(1, 2), (3, 6), (0, 0)])
def test_the_count_states_the_trend_pages_of_each_account(accounts, trend):
    total, parts = cost_requests.planned(accounts, False, True)
    assert dict(parts)["cost trend"] == trend
    assert total == trend


# --- the whole CLI against moto: two accounts, two bills -------------------------


def test_cli_two_accounts_one_trend_request_each(tmp_path, monkeypatch):
    base = scenarios.BY_ID["S1-E-cost-analysis-calls-cost-explorer"]
    keys = {k: scenarios.ACCOUNTS[k][1] for k in ("A", "B")}
    audit = tmp_path / "audit.json"
    sc = dataclasses.replace(
        base,
        accounts=("A", "B"),
        args=("--enable-cost-analysis", "--audit-output", str(audit)),
        faults=(
            Fault(service="ce", op="GetCostAndUsage", key=keys["A"], replace=BILL_A),
            Fault(service="ce", op="GetCostAndUsage", key=keys["B"], replace=BILL_B),
        ),
    )
    outcome = run_in_process(sc, tmp_path, monkeypatch)
    assert outcome.code == 0
    per_key = {}
    for call in outcome.calls:
        if (call["service"], call["op"]) == ("ce", "GetCostAndUsage"):
            per_key[call["key"]] = per_key.get(call["key"], 0) + 1
    assert per_key == {keys["A"]: 1, keys["B"]: 1}
    guard = json.loads(audit.read_text())
    assert (
        sum(
            op["count"]
            for op in guard["operations"]
            if (op["service"], op["operation"]) == ("ce", "GetCostAndUsage")
        )
        == 2
    )


def test_the_stated_page_count_is_the_analyzers():
    assert cost_requests.TREND_PAGES_PER_ACCOUNT == cost_module.TREND_PAGES_PER_ACCOUNT


# --- P7b (architect rulings): unit, library path, the billing table ----------


def _trend_entry(account, service, unit, names=("n",)):
    return {
        "account_id": account,
        "service": service,
        "billing_names": list(names),
        "resource_count": 1,
        "previous_month": "2026-09",
        "current_month": "2026-10",
        "previous_monthly_cost": 1.0,
        "current_monthly_cost": 2.0,
        "cost_change_percentage": 100.0,
        "trend_direction": "increasing",
        "alert_triggered": True,
        "unit": unit,
    }


def _sheet_rows(trends):
    converter = BOMConverter()
    converter.cost_analysis = {"summary": {}, "cost_trends": trends}
    wb = Workbook()
    converter._create_cost_analysis_sheet(wb)
    rows = [list(r) for r in wb["Cost Analysis"].iter_rows(values_only=True)]
    at = [r[1:2] for r in rows].index(["Service"])
    return rows[at], rows[at + 1 :]


def test_the_unit_comes_from_the_answer(monkeypatch):
    eur = bill(
        {"Amazon Simple Storage Service": 3}, {"Amazon Simple Storage Service": 4}
    )
    for period in eur["ResultsByTime"]:
        for group in period["Groups"]:
            group["Metrics"]["BlendedCost"]["Unit"] = "EUR"
    analyzer, _, sessions, _, _ = _two_accounts(monkeypatch, a=eur)
    s3 = _by_key(
        analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    )[("111111111111", "S3")]
    assert s3.unit == "EUR"
    heading, body = _sheet_rows([_trend_entry("111111111111", "S3", "EUR")])
    assert heading[4] == heading[6] == "Billed (EUR)"
    assert body[0][4] == 1.0


def test_units_that_disagree_are_shown_in_each_cell():
    heading, body = _sheet_rows(
        [
            _trend_entry("111111111111", "S3", "EUR"),
            _trend_entry("222222222222", "S3", "USD"),
        ]
    )
    assert heading[4] == heading[6] == "Billed (unit as returned)"
    assert [r[4] for r in body[:2]] == ["1.0 EUR", "1.0 USD"]


def test_a_service_whose_groups_disagree_on_the_unit_has_no_single_unit(monkeypatch):
    mixed = bill(
        {"Amazon Simple Storage Service": 3}, {"Amazon Simple Storage Service": 4}
    )
    mixed["ResultsByTime"][1]["Groups"][0]["Metrics"]["BlendedCost"]["Unit"] = "EUR"
    analyzer, _, sessions, _, _ = _two_accounts(monkeypatch, a=mixed)
    s3 = _by_key(
        analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    )[("111111111111", "S3")]
    assert s3.unit == ""
    heading, body = _sheet_rows([_trend_entry("111111111111", "S3", "")])
    assert heading[4] == "Billed (unit as returned)"
    assert body[0][4] == "1.0 (units differ)"


def test_the_library_path_with_several_accounts_warns_once(monkeypatch):
    ce = CostExplorer(BILL_A)
    analyzer, log = _setup(monkeypatch, {})
    analyzer.cost_explorer_client = ce
    analyzer.analyze_cost_trends(ROWS, now=NOW)
    warnings = [m for level, m in log.lines if level >= logging.WARNING]
    assert warnings == [
        "Cost trend: read once, with one session, for 2 accounts; pass "
        "account_sessions to read each account's own bill."
    ]


def test_an_account_without_a_session_gives_a_warning(monkeypatch):
    analyzer, log, sessions, _, _ = _two_accounts(monkeypatch)
    del sessions["222222222222"]
    analyzer.analyze_cost_trends(ROWS, account_sessions=sessions, now=NOW)
    warnings = [m for level, m in log.lines if level >= logging.WARNING]
    assert warnings == [
        "Cost analysis: an account has no session, so its cost trend is not read."
    ]


def test_the_billing_table_is_a_staticmethod():
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    raw = ComprehensiveAWSDiscovery.__dict__["_normalize_billing_service_name"]
    assert isinstance(raw, staticmethod)
    assert (
        ComprehensiveAWSDiscovery._normalize_billing_service_name(
            "Amazon Simple Storage Service"
        )
        == "s3"
    )
    assert cost_module._billing_key("Amazon EC2 Container Registry (ECR)") == (
        "ec2containerregistryecr"
    )
