"""F1 (v1.4.1): --enable-cost-analysis makes one Cost Explorer request.

Until v1.4.0 the cost trend asked Cost Explorer once per service that has
resources (a real run on a 21-service account made 21 requests), and AWS
charges for each request. Every one of those requests asked for the same
thing: two months, grouped by SERVICE. Now the trend asks once and reads
every service from that one answer, so the numbers per service do not change.
The run also says how many requests it will make before it makes them.
"""

import dataclasses
import json
import logging
from decimal import Decimal
from unittest import mock

from botocore.exceptions import ClientError

from inventag.discovery.cost_analyzer import CostAnalyzer
from tests.regression import scenarios
from tests.regression.faults import Fault
from tests.regression.runner import run_in_process

# F1b (architect ruling 5): the run says it once, in the generator, before
# discovery; the analyzer says nothing of its own.
ANNOUNCEMENT = (
    "Cost Explorer: up to 2 request(s) in this run "
    "(billing validation: 0; cost trend: 2). AWS charges for each."
)


def _group(name, amount):
    return {"Keys": [name], "Metrics": {"BlendedCost": {"Amount": amount}}}


# Three monthly periods, as Cost Explorer answers a 60-day window.
ANSWER = {
    "ResultsByTime": [
        {"Groups": [_group("AWS Lambda", "4"), _group("EC2 - Other", "1")]},
        {
            "Groups": [
                _group("AWS Lambda", "10"),
                _group("Amazon DynamoDB", "0"),
                _group("EC2 - Other", "6"),
                _group("Amazon EC2 Container Registry (ECR)", "2"),
            ]
        },
        {
            "Groups": [
                _group("AWS Lambda", "12"),
                _group("Amazon DynamoDB", "3"),
                _group("EC2 - Other", "8"),
                _group("Amazon EC2 Container Registry (ECR)", "1"),
                _group("Amazon Simple Notification Service", "5"),
            ]
        },
    ]
}

# Five services with resources; two EC2 rows share the EC2 figure.
RESOURCES = [
    {"id": "i-1", "service": "EC2"},
    {"id": "i-2", "service": "EC2"},
    {"id": "fn-1", "service": "Lambda"},
    {"id": "tbl-1", "service": "DynamoDB"},
    {"id": "bucket-1", "service": "S3"},
    {"id": "queue-1", "service": "SQS"},
]


class CostExplorer:
    def __init__(self, outcome, log=None):
        self.outcome = outcome
        self.calls = []
        self.log = log

    def get_cost_and_usage(self, **kwargs):
        self.calls.append((kwargs, list(self.log) if self.log is not None else None))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class Lines(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append((record.levelno, record.getMessage()))


def _analyzer(ce):
    analyzer = CostAnalyzer(session=mock.MagicMock())
    analyzer.cost_explorer_client = ce
    return analyzer


def _logged(analyzer):
    handler = Lines()
    analyzer.logger.addHandler(handler)
    return handler


# --- the analyzer -----------------------------------------------------------


def test_five_services_are_one_request():
    ce = CostExplorer(ANSWER)
    _analyzer(ce).analyze_cost_trends(RESOURCES)
    assert len(ce.calls) == 1


def test_the_request_is_two_months_grouped_by_service():
    ce = CostExplorer(ANSWER)
    _analyzer(ce).analyze_cost_trends(RESOURCES)
    kwargs = ce.calls[0][0]
    assert kwargs["Granularity"] == "MONTHLY"
    assert kwargs["Metrics"] == ["BlendedCost"]
    assert kwargs["GroupBy"] == [{"Type": "DIMENSION", "Key": "SERVICE"}]
    assert set(kwargs["TimePeriod"]) == {"Start", "End"}


def test_the_analyzer_does_not_announce_the_run_does():
    ce = CostExplorer(ANSWER)
    analyzer = _analyzer(ce)
    handler = _logged(analyzer)
    analyzer.analyze_cost_trends(RESOURCES)
    assert not [m for _, m in handler.lines if m.startswith("Cost Explorer:")]


def test_a_denied_request_is_one_request_and_one_warning():
    error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "secret-detail"}},
        "GetCostAndUsage",
    )
    ce = CostExplorer(error)
    analyzer = _analyzer(ce)
    handler = _logged(analyzer)
    assert analyzer.analyze_cost_trends(RESOURCES) == []
    assert len(ce.calls) == 1
    warnings = [m for level, m in handler.lines if level >= logging.WARNING]
    assert warnings == [
        "Cost analysis: access to the cost-explorer API was denied "
        "(AccessDeniedException). Cost and activity data from it will be missing."
    ]
    assert analyzer.permission_denials() == [
        ("ce", "GetCostAndUsage", "AccessDeniedException")
    ]


def test_no_resources_no_request_and_no_announcement():
    ce = CostExplorer(ANSWER)
    analyzer = _analyzer(ce)
    handler = _logged(analyzer)
    assert analyzer.analyze_cost_trends([]) == []
    assert ce.calls == []
    assert not [m for _, m in handler.lines if m.startswith("Cost Explorer:")]


# --- the whole CLI against moto ---------------------------------------------


def _cli(tmp_path, monkeypatch, billing):
    base = scenarios.BY_ID["S1-E-cost-analysis-calls-cost-explorer"]
    audit = tmp_path / "audit.json"
    sc = dataclasses.replace(
        base,
        billing=billing,
        args=("--enable-cost-analysis", "--audit-output", str(audit)),
        faults=(Fault(service="ce", op="GetCostAndUsage", replace=ANSWER),),
    )
    outcome = run_in_process(sc, tmp_path, monkeypatch)
    guard = json.loads(audit.read_text())
    counted = sum(
        op["count"]
        for op in guard["operations"]
        if (op["service"], op["operation"]) == ("ce", "GetCostAndUsage")
    )
    return outcome, counted


def _services(outcome):
    return {
        c["service"]
        for c in outcome.calls
        if c["service"] not in ("sts", "ce", "pricing", "cloudwatch")
    }


def test_cli_without_billing_validation_makes_one_request(tmp_path, monkeypatch):
    outcome, counted = _cli(tmp_path, monkeypatch, billing=False)
    assert outcome.code == 0
    assert len(_services(outcome)) >= 5
    assert counted == 1
    assert sum(1 for c in outcome.calls if c["service"] == "ce") == 1
    assert outcome.text.count(ANNOUNCEMENT) == 1


def test_cli_with_billing_validation_adds_only_the_billing_request(
    tmp_path, monkeypatch
):
    # The billing request asks for another period (from 30 days before the
    # first of the month) than the trend (60 days), so it is not reused.
    outcome, counted = _cli(tmp_path, monkeypatch, billing=True)
    assert outcome.code == 0
    assert counted == 2


# --- the help text ----------------------------------------------------------


def test_the_help_of_enable_cost_analysis_says_the_number_of_requests():
    from inventag.cli.main import create_parser

    (action,) = [
        a
        for a in create_parser()._actions
        if "--enable-cost-analysis" in a.option_strings
    ]
    text = " ".join(action.help.split())
    assert "at most one more Cost Explorer request for the whole run" in text
    # security review v1.4.1 finding 2: retries are requests too
    assert "each retry of a throttled request is one more request" in text
    assert "AWS charges for each request" in text
