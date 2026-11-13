"""Under the CLI every log line is printed once, with the CLI's format, and
discovery warnings reach --log-file.

Before: constructing the inventory called logging.basicConfig() (a second,
root handler on stderr), so every later message was printed twice; and the
comprehensive discovery logger did not propagate, so its warnings went to
Python's last-resort handler (unformatted, not in the log file)."""

import logging
from unittest import mock

import pytest

from inventag.cli.logging_setup import setup_logging


@pytest.fixture
def clean_logging():
    root = logging.getLogger()
    saved_root = list(root.handlers)
    names = [
        "inventag",
        "inventag.discovery.inventory",
        "inventag.discovery.comprehensive_discovery",
        "inventag.compliance.checker",
    ]
    saved = {
        n: (list(logging.getLogger(n).handlers), logging.getLogger(n).propagate)
        for n in names
    }
    yield
    root.handlers[:] = saved_root
    for n, (handlers, propagate) in saved.items():
        logging.getLogger(n).handlers[:] = handlers
        logging.getLogger(n).propagate = propagate


def test_one_line_per_message_and_discovery_warnings_in_the_log_file(
    clean_logging, tmp_path, capsys
):
    logging.getLogger().handlers.clear()
    log_file = tmp_path / "run.log"
    setup_logging(verbose=True, log_file=str(log_file))

    from inventag.compliance.checker import ComprehensiveTagComplianceChecker
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
    from inventag.discovery.inventory import AWSResourceInventory

    AWSResourceInventory(regions=["us-east-1"], session=mock.MagicMock())
    ComprehensiveAWSDiscovery(session=mock.MagicMock(), regions=["us-east-1"])
    ComprehensiveTagComplianceChecker(
        regions=["us-east-1"],
        session=mock.MagicMock(),
        policy={"required_tags": ["Owner"]},
    )
    assert logging.getLogger().handlers == []

    logging.getLogger("inventag.state.delta_detector").warning("delta-marker")
    logging.getLogger("inventag.discovery.comprehensive_discovery").warning(
        "listing-marker failed (404)"
    )

    captured = capsys.readouterr()
    console = captured.out + captured.err
    assert console.count("delta-marker") == 1
    assert console.count("listing-marker") == 1
    assert (
        "inventag.discovery.comprehensive_discovery - WARNING - listing-marker"
        in console
    )
    assert "listing-marker" in log_file.read_text()
