"""CodeQL "Clear-text logging of sensitive information" on PR #65: the log calls
that CodeQL named get no value from a scanned resource (bucket names, resource
IDs, service and resource type of a row) and no exception text. They log a
fixed text, a count, an AWS error code or the exception's type.

The calls: comprehensive_discovery._enhance_s3_buckets (two), cost_analyzer
_log_aws_failure, _get_pricing_info, _log_pricing_failure (two) and the
CloudWatch message of _get_activity_metrics, inventory
_validate_discovery_with_billing (the services without billing).
"""

import ast
import inspect
import logging
import textwrap
from unittest.mock import Mock

from botocore.exceptions import ClientError

from inventag.discovery import comprehensive_discovery, inventory
from inventag.discovery.cost_analyzer import CostAnalyzer

# names whose value comes from a scanned row or from an exception
ROW_OR_ERROR = {"bucket_name", "e", "error", "service", "resource_type", "resource_id"}


def _interpolated(function):
    """The names used inside f-string fields of the function's log calls."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    found = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("debug", "info", "warning", "error")
        ):
            for arg in node.args:
                for sub in ast.walk(arg):
                    if isinstance(sub, ast.FormattedValue):
                        found |= {
                            n.id for n in ast.walk(sub.value) if isinstance(n, ast.Name)
                        }
    return found


def test_the_flagged_log_calls_take_no_row_value_and_no_exception_text():
    for function in (
        comprehensive_discovery.ComprehensiveAWSDiscovery._enhance_s3_buckets,
        CostAnalyzer._log_aws_failure,
        CostAnalyzer._get_pricing_info,
        CostAnalyzer._log_pricing_failure,
        CostAnalyzer._get_activity_metrics,
        inventory.AWSResourceInventory._validate_discovery_with_billing,
    ):
        assert not _interpolated(function) & ROW_OR_ERROR, function.__qualname__


def test_no_line_names_each_service_without_billing():
    source = inspect.getsource(
        inventory.AWSResourceInventory._validate_discovery_with_billing
    )
    assert "🆓" not in source
    assert "have discovered resources but no recent billing" in source


def _analyzer(client):
    session = Mock()
    session.client.return_value = client
    return CostAnalyzer(session=session)


class _Records(logging.Handler):
    """Every record of one logger, whatever other tests did to the levels or
    the propagation of the ``inventag`` loggers."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _capture(monkeypatch, logger):
    handler = _Records()
    monkeypatch.setattr(logger, "level", logging.DEBUG)
    monkeypatch.setattr(logger, "disabled", False)
    logger.addHandler(handler)
    return handler


def _rows():
    return [
        {
            "service": "EC2",
            "type": "Instance",
            "id": "i-secret-row",
            "region": "us-east-1",
            "instance_type": "t3.micro",
        }
    ]


def test_a_failed_pricing_lookup_logs_the_code_only(monkeypatch):
    client = Mock()
    client.get_products.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameterException", "Message": "bad filter i-x"}},
        "GetProducts",
    )
    analyzer = _analyzer(client)
    caught = _capture(monkeypatch, analyzer.logger)
    try:
        analyzer.estimate_resource_costs(_rows())
    finally:
        analyzer.logger.removeHandler(caught)
    text = "\n".join(r.getMessage() for r in caught.records)
    assert (
        "Cost analysis: a Pricing API lookup failed (InvalidParameterException); "
        "the same lookup is not repeated in this run. Estimates for it will be "
        "missing." in text
    )
    for leaked in ("bad filter", "i-secret-row", "EC2:Instance", "First seen"):
        assert leaked not in text, leaked


def test_an_aws_failure_at_debug_logs_the_code_not_the_text(monkeypatch):
    analyzer = _analyzer(Mock())
    caught = _capture(monkeypatch, analyzer.logger)
    error = ClientError(
        {"Error": {"Code": "Throttling", "Message": "arn:aws:x:secret"}}, "GetProducts"
    )
    try:
        analyzer._log_aws_failure("pricing", "Pricing API query failed", error)
    finally:
        analyzer.logger.removeHandler(caught)
    (record,) = [r for r in caught.records if r.levelno == logging.DEBUG]
    assert record.getMessage() == "Pricing API query failed (Throttling)"


def test_a_pricing_filter_error_logs_its_type(monkeypatch):
    analyzer = _analyzer(Mock())
    caught = _capture(monkeypatch, analyzer.logger)

    def broken(*args, **kwargs):
        raise ValueError("value from a row")

    monkeypatch.setattr(analyzer, "_build_pricing_filters", broken)
    try:
        assert analyzer._get_pricing_info("EC2", "Instance", "us-east-1", {}) is None
    finally:
        analyzer.logger.removeHandler(caught)
    text = "\n".join(r.getMessage() for r in caught.records)
    assert "Could not build pricing filters (ValueError)" in text
    assert "value from a row" not in text


def test_the_changelog_lists_the_changed_log_lines():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "CHANGELOG.md").read_text()
    start = text.index("## [Unreleased]")
    changed = text[text.index("### Changed", start) : text.index("### Removed", start)]
    flat = " ".join(changed.split())
    assert 'CodeQL "clear-text logging"' in flat
    assert 'ends after "Estimates for it will be missing."' in flat


# Second CodeQL pass (PR #65 at 8c339e2d): billing amounts, Cost Explorer
# service names and resource rows are not logged either; the counts stay. The
# AWS error text of a refused Cost Explorer call stays at DEBUG: the pages
# (status, troubleshooting) say that --debug shows it.
BILLING_VALUES = {
    "spend",
    "cost",
    "billing_cost",
    "total_spend",
    "billed",
    "data",
    "service",
    "resource",
}


def test_no_log_call_takes_a_billing_amount_or_service_name():
    for function in (
        inventory.AWSResourceInventory._discover_services_via_billing,
        inventory.AWSResourceInventory._validate_discovery_with_billing,
        inventory.AWSResourceInventory._discover_missing_billing_services,
        comprehensive_discovery.ComprehensiveAWSDiscovery._validate_with_billing,
        CostAnalyzer.estimate_resource_costs,
    ):
        assert not _interpolated(function) & BILLING_VALUES, function.__qualname__


def test_a_failed_estimate_names_no_resource(monkeypatch):
    analyzer = _analyzer(Mock())

    def broken(resource):
        raise RuntimeError("text with i-secret-row")

    monkeypatch.setattr(analyzer, "_estimate_single_resource_cost", broken)
    caught = _capture(monkeypatch, analyzer.logger)
    try:
        analyzer.estimate_resource_costs(_rows())
    finally:
        analyzer.logger.removeHandler(caught)
    text = "\n".join(r.getMessage() for r in caught.records)
    assert "Cost estimation failed for a resource (RuntimeError)" in text
    assert "i-secret-row" not in text


def test_the_changelog_lists_the_billing_log_lines():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "CHANGELOG.md").read_text()
    start = text.index("## [Unreleased]")
    changed = text[text.index("### Changed", start) : text.index("### Removed", start)]
    flat = " ".join(changed.split())
    assert "shows a billed amount, a count of billed services" in flat


# Third CodeQL pass (PR #65 at 18612070, inventory.py 901): the whole class.
# CodeQL treats names with "billing" as private data and the rows that went
# through mask_secret_values as secret data. In the discovery modules and the
# BOM processor no log call takes a value named like billing data, a row, a
# resource identifier or a per-account trend value, not even inside len().
SWEEP_FILES = (
    "inventag/discovery/inventory.py",
    "inventag/discovery/comprehensive_discovery.py",
    "inventag/discovery/cost_analyzer.py",
    "inventag/reporting/bom_processor.py",
)
DENY = __import__("re").compile(
    r"(?i)(billing|^resource$|resource_id|^arn$|^bucket|table_name|best_resource"
    r"|^forgotten$|^estimate$|services_with|missing_services|unbilled_services"
    r"|matched_services|^account$|failure_text)"
)


def _log_values(tree):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("debug", "info", "warning", "error", "exception")
            and "log" in ast.unparse(node.func.value).lower()
        ):
            for arg in node.args:
                parts = [arg]
                if isinstance(arg, ast.JoinedStr):
                    parts = [
                        v.value for v in arg.values if isinstance(v, ast.FormattedValue)
                    ]
                elif isinstance(arg, ast.Constant):
                    parts = []
                for part in parts:
                    for sub in ast.walk(part):
                        name = (
                            sub.id
                            if isinstance(sub, ast.Name)
                            else sub.attr if isinstance(sub, ast.Attribute) else None
                        )
                        if name and DENY.search(name):
                            yield node.lineno, name


def test_no_log_call_takes_billing_row_or_identifier_values():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    found = []
    for rel in SWEEP_FILES:
        tree = ast.parse((root / rel).read_text())
        found += [f"{rel}:{line}: {name}" for line, name in _log_values(tree)]
    assert found == []


def test_the_changelog_lists_the_third_pass():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "CHANGELOG.md").read_text()
    start = text.index("## [Unreleased]")
    changed = text[text.index("### Changed", start) : text.index("### Removed", start)]
    flat = " ".join(changed.split())
    assert "no log line names a resource, a bucket, a table, an ARN" in flat
