"""A call blocked by the read-only guard must not be hidden (A-04, WO-5).

In v1.2.0 a block inside a listing was caught by discovery like any other
error (ledger outcome ``error``): the run said "successful", exit 0, nothing
in the report. A block in the state stage (S3 G1e) only made the snapshot
fail. A blocked call is a defect in InvenTag itself.

Now the run notes (report, ``results["run_notes"]``, console) name each
blocked operation and say it is a defect to report, and one ERROR summary
line says the same. The ledger outcome stays ``error`` and the exit code
stays 0 (exit 5 or 1 for a guard block is owner decision O11).
"""

import json
import logging

import boto3
import botocore.client

from inventag.state import StateManager
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    aws,
    empty_aws,
    reports,
    run_cli,
)
from tests.unit.test_snapshot_not_poisoned import result_spy, run_notes

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]
DEFECT = "defect in InvenTag"


def summary_errors(caplog):
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.ERROR and DEFECT in r.getMessage()
    ]


def test_a_blocked_call_inside_a_listing_is_named_as_a_defect(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """The SQS listing calls sqs:CreateQueue first (a write: blocked)."""
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)
    original = botocore.client.BaseClient._make_api_call
    active = [True]

    def call(client, operation_name, api_params):
        service = client.meta.service_model.service_name
        if active[0] and service == "sqs" and operation_name == "ListQueues":
            client.create_queue(QueueName="must-never-be-created")
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)
    assert run_cli(*ARGS, "--fail-on-account-error") == 0  # as in v1.2.0

    notes = run_notes(reports(tmp_path / "out")[0])
    assert any("sqs:CreateQueue" in n and DEFECT in n for n in notes), notes
    assert any("sqs:CreateQueue" in n for n in results[-1]["run_notes"])
    errors = summary_errors(caplog)
    assert len(errors) == 1 and "sqs:CreateQueue" in errors[0], errors
    # The queue was not created.
    active[0] = False
    assert "must-never-be-created" not in str(
        boto3.client("sqs", region_name="us-east-1").list_queues()
    )
    # The ledger outcome of the listing stays "error" (as in v1.2.0), so the
    # coverage_summary of the snapshot counts it as an error, not "denied".
    snapshot = sorted((tmp_path / "out" / "state").glob("state_*.json"))[-1]
    summary = json.loads(snapshot.read_text())["metadata"]["tags"]["coverage_summary"]
    counts = next(iter(summary.values()))
    assert counts.get("error", 0) >= 1 and "denied" not in counts


def test_a_blocked_call_in_the_state_stage_is_named_as_a_defect(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """S3 G1e: saving the snapshot calls s3:PutObject (blocked)."""
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)
    original = StateManager.save_state

    def save_state(self, *args, **kwargs):
        boto3.client("s3", region_name="us-east-1").put_object(
            Bucket="nowhere", Key="state.json", Body=b"{}"
        )
        return original(self, *args, **kwargs)

    monkeypatch.setattr(StateManager, "save_state", save_state)
    assert run_cli(*ARGS) == 0  # as in v1.2.0
    assert any(
        "s3:PutObject" in n and DEFECT in n for n in results[-1]["run_notes"]
    ), results[-1]["run_notes"]
    errors = summary_errors(caplog)
    assert len(errors) == 1 and "s3:PutObject" in errors[0], errors


def test_a_run_without_a_block_has_no_guard_note(aws, tmp_path, caplog):  # noqa: F811
    caplog.set_level(logging.INFO)
    assert run_cli(*ARGS) == 0
    assert summary_errors(caplog) == []
    assert run_notes(reports(tmp_path / "out")[0]) == []
