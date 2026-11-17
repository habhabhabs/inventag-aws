"""D4: handlers that used to log at DEBUG only now warn (golden text, once)."""

import logging
from unittest import mock

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery


def _disc():
    return ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=["us-east-1"], enable_billing_validation=False
    )


def test_unreadable_account_id_is_warned_once_and_keeps_the_placeholder(caplog):
    disc = _disc()

    def boom(*a, **k):
        raise PermissionError("secret-detail")

    disc._client = boom
    with caplog.at_level(logging.WARNING):
        assert disc._get_account_id() == "000000000000"
        assert disc._get_account_id() == "000000000000"
    lines = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert lines == [
        "The account ID could not be read (GetCallerIdentity: PermissionError); "
        "rows without an ARN carry the placeholder 000000000000. Run with "
        "--debug for the detail."
    ]
    assert "secret-detail" not in caplog.text
