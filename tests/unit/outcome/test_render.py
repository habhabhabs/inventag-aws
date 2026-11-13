"""render: the four outputs carry the same issues (invariant I4)."""

import json
import logging

import pytest

from inventag.exit_codes import POLICY_1X, POLICY_V1_2, Gates, decide
from inventag.outcome import render
from inventag.outcome.model import (
    AccountOutcome,
    Category,
    Findings,
    Issue,
    OutputOutcome,
    RunOutcome,
    Scope,
    State,
)
from inventag.outcome.reduce import reduce_account, reduce_run
from tests.unit.outcome.helpers import entry

C = Category
DEV = "222222222222"
SANDBOX = "333333333333"
PROD = "444444444444"


def sample_run(**kw) -> RunOutcome:
    """The run of design 5.3: one complete, one partial, one failed account."""
    dev_entries = [
        entry("ok", account_id=DEV, region=r, service="ec2", count=40)
        for r in ("us-east-1", "eu-west-1", "ap-southeast-1")
    ]
    dev_entries += [
        entry("denied", account_id=DEV, region=r, error_code="AccessDenied")
        for r in ("us-east-1", "eu-west-1", "ap-southeast-1")
    ]
    dev_entries += [
        entry(
            "throttled",
            account_id=DEV,
            region="eu-west-1",
            service="resourcegroupstaggingapi",
            source="tagging-api",
            operation="GetResources",
            error_code="ThrottledException",
        ),
        entry(
            "denied", account_id=DEV, service="sagemaker", error_code="OptInRequired"
        ),
    ]
    dev_issues = [
        Issue(
            scope=Scope.REGION,
            category=C.NOT_ENABLED,
            account=DEV,
            region="ap-east-1",
            phase="region_check",
            code="AuthFailure",
        ),
        Issue(
            scope=Scope.RESOURCE,
            category=C.PERMISSION_DENIED,
            account=DEV,
            region="us-east-1",
            service="s3",
            operation="GetBucketLocation",
            code="AccessDenied",
            phase="detail",
            examples=("bucket-a",),
        ),
        Issue(
            scope=Scope.RESOURCE,
            category=C.PERMISSION_DENIED,
            account=DEV,
            region="us-east-1",
            service="s3",
            operation="GetBucketLocation",
            code="AccessDenied",
            phase="detail",
            examples=("bucket-b",),
        ),
    ]
    dev, dev_all = reduce_account(
        DEV, dev_entries, dev_issues, account_name="dev", resources=120
    )
    sandbox_issue = Issue(
        scope=Scope.ACCOUNT,
        category=C.PERMISSION_DENIED,
        account=SANDBOX,
        service="sts",
        operation="AssumeRole",
        code="AccessDenied",
        phase="assume_role",
        aws_message="User: arn:aws:iam::111111111111:user/ci is not authorized",
    )
    sandbox, sandbox_all = reduce_account(
        SANDBOX, [], [sandbox_issue], account_name="sandbox"
    )
    prod, prod_all = reduce_account(
        PROD,
        [entry("ok", account_id=PROD, count=300)],
        account_name="prod",
        resources=300,
    )
    defaults = dict(
        outputs=[
            OutputOutcome("excel", True, files=("bom_output/bom.xlsx",)),
            OutputOutcome(
                "state-snapshot", False, State.FAILED, category=C.OUTPUT_FAILURE
            ),
        ],
        resources_found=420,
        resources_reported=420,
    )
    defaults.update(kw)
    state_issue = Issue(
        scope=Scope.OUTPUT,
        category=C.OUTPUT_FAILURE,
        service="state-snapshot",
        operation="write",
        code="EACCES",
        phase="state",
    )
    return reduce_run(
        [prod, dev, sandbox],
        issues=dev_all + sandbox_all + prod_all + [state_issue],
        **defaults,
    )


def _lines_of_logs(outcome):
    logger = logging.getLogger("inventag.test.render")
    lines = []
    for account in outcome.accounts:
        lines += render.log_account(account, outcome.issues, logger)
    lines += render.log_run(outcome, logger)
    return lines


def test_sample_has_every_severity():
    outcome = sample_run()
    severities = {i.severity for i in outcome.issues}
    assert severities == {"error", "warning", "info"}
    assert outcome.state is State.PARTIAL


def test_four_outputs_carry_the_same_visible_issues():
    """I4: the issue lines of severity warning or error are the same set in
    the log, the summary, the report block and run_summary.json."""
    outcome = sample_run()
    expected = {render.issue_line(i) for i in render.visible(outcome.issues)}
    assert len(expected) >= 5

    log = {text for level, text in _lines_of_logs(outcome) if level >= logging.WARNING}
    summary = set(render.summary_lines(outcome))
    block = render.report_block(outcome)
    in_notes = set(block.notes)
    in_rows = {
        f"{r[2] + ': ' if r[2] else ''}{r[8]}. Instead: {r[9]}" for r in block.rows
    }
    payload = render.summary_json(outcome)
    in_json = {
        i["line"] for i in payload["issues"] if i["severity"] in ("error", "warning")
    }

    assert log == expected
    assert expected <= summary
    assert expected <= in_notes
    assert in_rows == expected
    assert in_json == expected


def test_info_issues_are_only_in_the_json_and_the_debug_log():
    outcome = sample_run()
    info = [i for i in render.worded(outcome.issues) if i.severity == "info"]
    assert info
    line = render.issue_line(info[0])
    assert line not in render.summary_lines(outcome)
    assert line not in render.report_block(outcome).notes
    assert line in {i["line"] for i in render.summary_json(outcome)["issues"]}
    assert (logging.DEBUG, line) in _lines_of_logs(outcome)


def test_log_account_logs_once_per_key_and_at_the_right_level(caplog):
    outcome = sample_run()
    dev = next(a for a in outcome.accounts if a.account_id == DEV)
    logger = logging.getLogger("inventag.test.render2")
    with caplog.at_level(logging.DEBUG, logger="inventag.test.render2"):
        render.log_account(dev, outcome.issues, logger)
    sqs = [r for r in caplog.records if "No permission for sqs" in r.getMessage()]
    assert len(sqs) == 1 and sqs[0].levelno == logging.WARNING
    assert sqs[0].getMessage().startswith(f"{DEV}: No permission for sqs in 3 regions")


def test_summary_lines():
    outcome = sample_run()
    lines = render.summary_lines(outcome, Gates(), POLICY_1X)
    assert lines[0] == (
        "Run status: INCOMPLETE. 420 resources from 1 complete, 1 partial and "
        "1 failed account(s); 6 issue(s)."
    )
    assert f"{SANDBOX} (sandbox): failed, 0 resources" in lines
    assert any(
        line.startswith(f"{DEV} (dev): partial, 120 resources") for line in lines
    )
    assert "Not written: state-snapshot (failed: output_failure)" in lines
    assert "Written: bom_output/bom.xlsx" in lines
    assert lines[-1].startswith("Exit code 0 (ok).")
    assert "With --fail-on-incomplete this run exits 5." in lines[-1]
    assert "From v2.0.0 this run exits 1 (auxiliary_output_failed)." in lines[-1]
    # every visible issue line is followed by its More: link
    for i, line in enumerate(lines):
        if ". Instead: " in line:
            assert lines[i + 1].startswith("  More: https://")


def test_exit_line_matches_decide_for_both_policies():
    outcome = sample_run()
    for policy in (POLICY_1X, POLICY_V1_2):
        code, reason = decide(outcome, Gates(), policy)
        assert render.exit_line(outcome, Gates(), policy).startswith(
            f"Exit code {code} ({reason})."
        )


def test_report_block_notes_keep_the_v120_account_wording():
    block = render.report_block(sample_run())
    assert block.notes[0] == (
        "1 of 3 account(s) were not scanned, so this report does not include them:"
    )
    assert block.notes[1].startswith(f"{SANDBOX} (sandbox): Could not assume the role")
    assert block.columns[0] == "Severity" and len(block.columns) == 10
    assert all(len(row) == 10 for row in block.rows)


def test_report_block_of_a_clean_run_has_no_notes():
    outcome = RunOutcome(
        accounts=[AccountOutcome(PROD, "prod", resources=3)], resources_reported=3
    )
    block = render.report_block(outcome)
    assert block.notes == [] and block.rows == []
    assert block.status_line == (
        "Run status: COMPLETE. 3 resources from 1 complete account(s); 0 issue(s)."
    )


@pytest.mark.parametrize(
    "partial_category,expected",
    [
        (
            C.TIMEOUT,
            "1 of 1 account(s) were only partly scanned (time limit); the resources "
            "found are included, others may be missing:",
        ),
        (
            C.CREDENTIALS,
            "1 of 1 account(s) were only partly scanned; the resources found are "
            "included, others may be missing:",
        ),
    ],
)
def test_report_block_partial_accounts(partial_category, expected):
    account = AccountOutcome(
        DEV, "dev", State.PARTIAL, partial_category, account_issue=True, resources=4
    )
    block = render.report_block(RunOutcome([account], resources_reported=4))
    assert block.notes[0] == expected


def test_report_block_reused_accounts():
    account = AccountOutcome(DEV, "dev", reused_from="2026-11-13T14:00:00Z")
    block = render.report_block(RunOutcome([account], resources_reported=1))
    assert block.notes == [
        "1 account(s) were not scanned again: their results come from an earlier "
        "run of the same command (--resume), scanned at:",
        f"{DEV}: 2026-11-13T14:00:00Z",
    ]


def test_summary_json_shape():
    outcome = sample_run(findings=Findings(tag_violations=2))
    meta = {
        "inventag_version": "1.2.0",
        "started_at": "2026-11-13T14:08:31Z",
        "finished_at": "2026-11-13T14:15:03Z",
        "duration_seconds": 392.1,
        "command": {"accounts_requested": 3},
    }
    payload = render.summary_json(outcome, Gates(), meta)
    json.dumps(payload)  # serialisable
    for key in (
        "schema_version",
        "inventag_version",
        "started_at",
        "finished_at",
        "state",
        "empty",
        "exit",
        "counts",
        "accounts",
        "issues",
        "outputs",
        "findings",
    ):
        assert key in payload
    assert payload["schema_version"] == 1
    assert payload["state"] == "partial"
    assert payload["exit"] == {
        "code": 0,
        "reason": "ok",
        "code_in_2_0": 1,
        "reason_in_2_0": "auxiliary_output_failed",
    }
    assert payload["counts"]["accounts"] == {
        "complete": 1,
        "partial": 1,
        "skipped": 0,
        "failed": 1,
    }
    assert payload["counts"]["issues"] == {"error": 2, "warning": 4, "info": 1}
    dev = next(a for a in payload["accounts"] if a["account_id"] == DEV)
    assert dev["regions"]["ap-east-1"] == {
        "state": "skipped",
        "category": "not_enabled",
        "not_complete": [],
    }
    assert {u["service"] for u in dev["regions"]["eu-west-1"]["not_complete"]} == {
        "sqs",
        "resourcegroupstaggingapi",
    }
    for issue in payload["issues"]:
        assert issue["next_step"] and issue["more"].startswith("https://")
    assert payload["findings"] == {"tag_violations": 2, "risk_findings": 0}


def test_summary_json_exit_code_equals_decide():
    """I3: exit.code is what decide returns for the same outcome and gates."""
    outcome = sample_run()
    for gates in (Gates(), Gates(fail_on_incomplete=True), Gates(fail_if_empty=True)):
        payload = render.summary_json(outcome, gates)
        assert (payload["exit"]["code"], payload["exit"]["reason"]) == decide(
            outcome, gates
        )


def test_summary_json_of_a_cancelled_run():
    payload = render.summary_json(RunOutcome([], cancelled_by=15))
    assert payload["state"] == "cancelled"
    assert payload["exit"]["code"] == 143


def test_rendering_is_deterministic():
    a, b = sample_run(), sample_run()
    assert render.summary_lines(a) == render.summary_lines(b)
    assert render.summary_json(a) == render.summary_json(b)
