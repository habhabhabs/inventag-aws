"""A session that expires during the scan must be visible (A-02).

In v1.2.0 an account whose session expired part-way counted as complete: the
report had no note, the snapshot listed the account as scanned (so the next
change report showed the unread resources as removed), and only the
per-listing warnings said anything. Now the report's Run notes say the
account is incomplete, one ERROR line names it, and the snapshot lists it
under the existing ``accounts_failed``.

The exit code stays 0, also with ``--fail-on-account-error``: exit 5 for an
expired session is owner decision 2 of the debt register (not made).
"""

import json
import logging

import pytest

from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD,
    GOOD_ID,
    Expiry,
    accounts_file,
    aws,
    empty_aws,
    reports,
    run_cli,
    total_resources,
    workbook,
)
from tests.unit.test_snapshot_not_poisoned import changes, result_spy, run_notes

FLAG = "--fail-on-account-error"


def expiry_errors(caplog):
    """ERROR records that report an expired session."""
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.ERROR and "expired" in r.getMessage().lower()
    ]


def snapshot_files(tmp_path, out):
    return sorted((tmp_path / out / "state").glob("state_*.json"))


@pytest.mark.parametrize(
    "code, flag",
    [
        ("ExpiredToken", [FLAG]),
        ("ExpiredTokenException", []),
        ("RequestExpired", [FLAG]),
    ],
)
def test_an_expired_session_is_named_in_the_report_log_and_snapshot(
    aws, tmp_path, monkeypatch, caplog, code, flag  # noqa: F811
):
    caplog.set_level(logging.INFO)
    expiry = Expiry(monkeypatch, allow=20, code=code)
    path = accounts_file(tmp_path, [GOOD])
    exit_code = run_cli(
        "--accounts-file", path, *BASE, *flag, "--output-directory", "out"
    )
    assert expiry.raised > 1  # many listings failed
    # Exit code as in v1.2.0, with and without the flag (owner decision 2).
    assert exit_code == 0

    files = reports(tmp_path / "out")
    assert len(files) == 1
    assert total_resources(files[0]) > 0  # what was read before the expiry
    notes = run_notes(files[0])
    assert any(
        GOOD_ID in n and "expired" in n and "incomplete" in n for n in notes
    ), notes

    # One ERROR line for the account, not one per failed listing.
    errors = expiry_errors(caplog)
    assert len(errors) == 1, errors
    assert GOOD_ID in errors[0]

    data = json.loads(snapshot_files(tmp_path, "out")[-1].read_text())
    assert data["metadata"]["accounts_failed"] == [GOOD_ID]
    assert data["metadata"]["accounts_scanned"] == []


def test_the_run_after_an_expired_session_reports_nothing_removed(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """Good run, run whose session expires after 20 calls, good run: no
    resource is reported as removed or added."""
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)
    path = accounts_file(tmp_path, [GOOD])
    args = ["--accounts-file", path, *BASE, "--output-directory", "out"]

    assert run_cli(*args) == 0
    expiry = Expiry(monkeypatch, allow=20)
    assert run_cli(*args) == 0
    assert expiry.raised > 0
    assert results[-1]["failed_accounts"] == []  # unchanged: drives exit 5
    assert changes(results[-1]) == (0, 0)

    expiry.allow = 10**9  # the session works again
    assert run_cli(*args) == 0
    assert changes(results[-1]) == (0, 0)
