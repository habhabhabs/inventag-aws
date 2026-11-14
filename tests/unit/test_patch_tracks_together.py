"""The cross-track pairs of the first v1.2.x patch, each run with both sides on
the branch (debt register section 8.2).

Each fix branch tested its half alone, with a double or a feature check for the
other half. These tests run the real generator (lead A), the real console
printer (senior C), the real template writers (senior E), the real change
report (lead B) and the real uploader and guard (senior G) together, under moto.
Pair 4 (the skipped upload) is ``test_upload_skipped_after_a_failed_format_is_logged``
in test_s3_upload_reports_outcome.py; pair 6 (``DENIED_PARAMETERS``) is
test_validate_operations_output.py. The moto CLI runs take 5 to 15 s each.
"""

import botocore.client
from botocore.exceptions import ClientError

from inventag.core import cloud_bom_generator as cbg
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
    workbook_text,
)
from tests.unit.test_snapshot_not_poisoned import DenyEverything, result_spy

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]
DEFECT = "defect in InvenTag"
READ_NOTHING = f"Every service listing of account {GOOD_ID}"


def console_lines(capsys, text):
    """Lines of the console (stdout and stderr) that contain ``text``."""
    out = capsys.readouterr()
    return [line for line in (out.out + out.err).splitlines() if text in line]


def block_create_queue(monkeypatch):
    """The SQS listing makes a write first: the read-only guard blocks it."""
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        service = client.meta.service_model.service_name
        if service == "sqs" and operation_name == "ListQueues":
            client.create_queue(QueueName="must-never-be-created")
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)


# ------------------------------------------- pair 1: run notes on the console
def test_an_expired_session_is_named_once_on_the_console(
    aws, tmp_path, monkeypatch, capsys  # noqa: F811
):
    Expiry(monkeypatch, allow=20)
    path = accounts_file(tmp_path, [GOOD])
    assert run_cli("--accounts-file", path, *BASE, "--output-directory", "out") == 0
    lines = console_lines(capsys, "expired during the scan")
    assert len(lines) == 1 and GOOD_ID in lines[0], lines


def test_an_account_that_read_nothing_is_named_once_on_the_console(
    aws, tmp_path, monkeypatch, capsys  # noqa: F811
):
    deny = DenyEverything(monkeypatch)
    deny.on = True
    assert run_cli(*ARGS) == 0
    lines = console_lines(capsys, READ_NOTHING)
    assert len(lines) == 1, lines


def test_a_listing_that_was_not_read_is_printed_once_on_the_console(
    aws, tmp_path, monkeypatch, capsys  # noqa: F811
):
    """A note the generator does not log itself (A-28) is printed by the CLI."""
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        if (
            client.meta.service_model.service_name == "dynamodb"
            and operation_name == "ListTables"
        ):
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "no"}}, operation_name
            )
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)
    assert run_cli(*ARGS) == 0
    lines = console_lines(capsys, "dynamodb in us-east-1 (denied)")
    assert len(lines) == 1, lines


# ---------------------------------------------- pair 2: notes in template reports
def test_a_template_report_carries_the_generators_note(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    deny = DenyEverything(monkeypatch)
    deny.on = True
    assert run_cli(*ARGS, "--template", "standard-bom") == 0
    files = reports(tmp_path / "out")
    assert len(files) == 1
    assert READ_NOTHING in workbook_text(files[0])


# -------------------------------------- pair 3: the change report gets the run
def test_a_listing_denied_in_the_current_run_is_not_compared_instead_of_removed(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    """Good run, then a run where the SQS listing and the Tagging API are denied
    (so nothing returns the queue): the queue is not reported as removed."""
    results = result_spy(monkeypatch)
    assert run_cli(*ARGS) == 0
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        service = client.meta.service_model.service_name
        if (service, operation_name) in (
            ("sqs", "ListQueues"),
            ("resourcegroupstaggingapi", "GetResources"),
        ):
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "no"}}, operation_name
            )
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)
    assert run_cli(*ARGS) == 0
    delta = results[-1]["state_management"]["delta_detection"]
    summary = delta["summary"].summary
    assert summary.get("not_compared_count", 0) >= 1, summary
    removed = [r.get("service") for r in delta["summary"].removed_resources]
    assert "SQS" not in removed, removed


# ------------------------------- pair 5: the cause on the --accounts-file path
def test_an_account_whose_session_cannot_be_made_names_the_error_type(
    aws, tmp_path, monkeypatch, capsys  # noqa: F811
):
    """An exception without a message (EOFError: an MFA prompt with no terminal)
    on the --accounts-file path: the "all accounts failed" summary gives the
    cause per account (senior C) and the cause is not empty (lead A)."""

    def no_session(self, credentials):
        raise EOFError()

    monkeypatch.setattr(cbg.CloudBOMGenerator, "_create_account_session", no_session)
    path = accounts_file(tmp_path, [GOOD])
    assert run_cli("--accounts-file", path, *BASE, "--output-directory", "out") == 1
    lines = console_lines(capsys, "Context establishment failed")
    assert lines and all("EOFError" in line for line in lines), lines


# --------------------------------------------- pair 7: the guard-block note
def test_a_guard_block_is_named_once_on_the_console_and_in_the_template_report(
    aws, tmp_path, monkeypatch, capsys  # noqa: F811
):
    block_create_queue(monkeypatch)
    assert run_cli(*ARGS, "--template", "standard-bom") == 0
    lines = console_lines(capsys, DEFECT)
    assert len(lines) == 1 and "sqs:CreateQueue" in lines[0], lines
    files = reports(tmp_path / "out")
    assert len(files) == 1
    text = workbook_text(files[0])
    assert "sqs:CreateQueue" in text and DEFECT in text
