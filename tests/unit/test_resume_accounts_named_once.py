"""With --resume, a reused account is named once on the console (I4): the
generator's "reusing results" warning is enough; the run-notes block does not
repeat it. When the generator did not log it, the notes still say it."""

import importlib
import logging

cli_main = importlib.import_module("inventag.cli.main")

HEADER = (
    "1 account(s) were not scanned again: their results come from an earlier "
    "run of the same command (--resume), scanned at:"
)
LINE = "111111111111: 2026-11-15 01:00 UTC"
LOGGED = "111111111111: reusing results scanned 2026-11-15 01:00 UTC (--resume)"
OTHER = "Not read: sqs in us-east-1 (throttled)."


def printed(caplog, results, already_logged):
    logger = logging.getLogger("inventag")
    with caplog.at_level(logging.WARNING, logger="inventag"):
        cli_main._log_run_notes(results, logger, already_logged)
    return [r.getMessage() for r in caplog.records]


def results():
    return {
        "reused_accounts": {"111111111111": "2026-11-15 01:00 UTC"},
        "run_notes": [HEADER, LINE, OTHER],
    }


def test_reused_account_already_logged_is_not_named_again(caplog):
    lines = printed(caplog, results(), {LOGGED})
    assert lines == ["Notes about this run:", f"  - {OTHER}"]


def test_reused_account_not_logged_by_the_generator_is_still_told_once(caplog):
    lines = printed(caplog, results(), set())
    assert lines.count(f"  - {LINE}") == 1
    assert f"  - {HEADER}" in lines


def test_only_reused_notes_and_already_logged_prints_nothing(caplog):
    only = {
        "reused_accounts": {"111111111111": "2026-11-15 01:00 UTC"},
        "run_notes": [HEADER, LINE],
    }
    assert printed(caplog, only, {LOGGED}) == []
