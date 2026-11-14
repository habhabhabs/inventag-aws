"""The run notes name the listings that were not read, and the regions the
access check skipped (A-28, the note content of register 4.1 row 5).

Before: a listing that was throttled, denied or failed was one log line; the
report (Summary sheet 100.0 %) did not say that anything was missing
(harness rows D3, D4). A region dropped by the region check
(``ec2:DescribeRegions`` denied there) was one log line too.

Now each account with such listings gets one note, grouped by service and
region with the reason, capped with "and N more"; skipped regions get one
note. A clean run has no note (its report is unchanged). Exit codes are
unchanged.
"""

import logging

import boto3
import botocore.client
from botocore.exceptions import ClientError

from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from tests.unit.test_checkpoint_only_complete_accounts import _entry
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD_ID,
    aws,
    empty_aws,
    reports,
    run_cli,
)
from tests.unit.test_snapshot_not_poisoned import result_spy, run_notes


def fail_calls(monkeypatch, should_fail, code):
    """Every call for which ``should_fail(service, operation, region)`` is
    true raises ``code`` (above botocore's retries)."""
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        service = client.meta.service_model.service_name
        if should_fail(service, operation_name, client.meta.region_name):
            raise ClientError(
                {"Error": {"Code": code, "Message": "injected"}}, operation_name
            )
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)


# ------------------------------------------------- end to end (CLI, moto)
def test_a_throttled_listing_is_named_in_the_report(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)
    fail_calls(
        monkeypatch,
        lambda s, op, r: s == "dynamodb" and op == "ListTables",
        "ThrottlingException",
    )
    args = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]
    assert run_cli(*args, "--fail-on-account-error") == 0  # as in v1.2.0
    notes = run_notes(reports(tmp_path / "out")[0])
    wanted = (
        f"Not read in account {GOOD_ID}, so the report is partial there: "
        "dynamodb in us-east-1 (throttled)"
    )
    assert any(n.startswith(wanted) for n in notes), notes
    assert results[-1]["failed_accounts"] == []


def test_a_region_skipped_by_the_access_check_is_named_in_the_report(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    fail_calls(
        monkeypatch,
        lambda s, op, r: s == "ec2" and op == "DescribeRegions" and r == "eu-west-1",
        "UnauthorizedOperation",
    )
    args = [*BASE, "--account-regions", "us-east-1,eu-west-1"]
    assert run_cli(*args, "--output-directory", "out") == 0
    notes = run_notes(reports(tmp_path / "out")[0])
    assert any(
        GOOD_ID in n and "skipped" in n and "eu-west-1" in n for n in notes
    ), notes


def test_a_clean_run_has_no_run_notes(aws, tmp_path):  # noqa: F811
    """Services moto does not implement answer 404 in every moto run; such a
    run must still look like a clean run (no Run notes block)."""
    args = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]
    assert run_cli(*args) == 0
    assert run_notes(reports(tmp_path / "out")[0]) == []


# ---------------------------------------------------- unit (ledger only)
def _generator(tmp_path, accounts):
    """A generator whose account contexts hold the given ledger entries."""
    generator = CloudBOMGenerator(
        MultiAccountConfig(accounts=[], output_directory=str(tmp_path))
    )
    for account_id, entries in accounts.items():
        generator.account_contexts[account_id] = AccountContext(
            credentials=AccountCredentials(account_id=account_id),
            session=boto3.Session(region_name="us-east-1"),
            caller_identity={"Account": account_id},
            accessible_regions=["us-east-1"],
            coverage=[dict(e, account_id=account_id) for e in entries],
        )
    return generator


def _at(entry, region):
    return dict(entry, region=region)


def test_listings_are_grouped_by_service_and_region_with_their_reasons(tmp_path):
    generator = _generator(
        tmp_path,
        {
            "111111111111": [
                _entry("ok", count=3, service="s3"),
                _entry("throttled", "Throttling", service="dynamodb"),
                _entry("denied", "AccessDenied", service="sqs"),
                _at(_entry("denied", "AccessDenied", service="sqs"), "eu-west-1"),
                _entry("error", "InternalError", service="sqs"),
            ]
        },
    )
    notes = generator._run_notes()
    assert notes == [
        "Not read in account 111111111111, so the report is partial there: "
        "dynamodb in us-east-1 (throttled); "
        "sqs in eu-west-1 (denied); sqs in us-east-1 (denied, error)."
    ]


def test_a_long_list_is_capped(tmp_path):
    entries = [_entry("ok", count=1, service="s3")] + [
        _entry("denied", "AccessDenied", service=f"svc{i:02d}") for i in range(14)
    ]
    notes = _generator(tmp_path, {"111111111111": entries})._run_notes()
    assert len(notes) == 1
    assert notes[0].count(" (denied)") == 10
    assert notes[0].endswith(", and 4 more.")


def test_a_clean_ledger_and_moto_404_give_no_note(tmp_path):
    generator = _generator(
        tmp_path,
        {
            "111111111111": [
                _entry("ok", count=3, service="s3"),
                _entry("empty", service="sqs"),
                _entry("error", "404", service="workmail"),
            ]
        },
    )
    assert generator._run_notes() == []


def test_accounts_with_their_own_note_are_not_listed_again(tmp_path):
    """An account that read nothing (A-01) or whose session expired (A-02)
    already has a note; its failed listings are not listed one by one."""
    generator = _generator(
        tmp_path,
        {
            "111111111111": [_entry("denied", "AccessDenied", service="sqs")],
            "222222222222": [
                _entry("ok", count=1, service="s3"),
                _entry("error", "ExpiredToken", service="sqs"),
            ],
        },
    )
    notes = generator._run_notes()
    assert len(notes) == 2
    assert not any(n.startswith("Not read") for n in notes)
