"""The change report says why an account was not compared, truthfully (A-64).

An account in a snapshot's ``accounts_failed`` whose rows are in that same
snapshot was read in part (for example its session expired during the scan):
the report says "read it only in part". An account with no rows in the
snapshot could not be scanned: the report keeps the v1.2.0 text.
"""

from inventag.state import ChangelogGenerator, DeltaDetector, StateManager

A = "111111111111"
B = "222222222222"


def _row(account, name):
    return {
        "service": "SQS",
        "type": "Queue",
        "id": name,
        "arn": f"arn:aws:sqs:us-east-1:{account}:{name}",
        "region": "us-east-1",
        "account_id": account,
        "source_account_id": account,
        "tags": {},
    }


def _report(tmp_path, old, new, old_failed=(), new_failed=()):
    sm = StateManager(state_dir=str(tmp_path))
    first = sm.save_state(
        old,
        account_id=A,
        regions=["us-east-1"],
        accounts_scanned=[A, B],
        accounts_failed=list(old_failed),
    )
    second = sm.save_state(
        new,
        account_id=A,
        regions=["us-east-1"],
        accounts_scanned=[A, B],
        accounts_failed=list(new_failed),
    )
    report = DeltaDetector().detect_changes_by_state_id(sm, first, second)
    markdown = ChangelogGenerator().generate_changelog(report).to_markdown()
    return report, markdown


def test_account_read_in_part_in_the_current_run(tmp_path):
    old = [_row(A, "a1"), _row(A, "a2"), _row(B, "b1")]
    new = [_row(A, "a1"), _row(B, "b1")]  # A's session expired after one listing
    report, markdown = _report(tmp_path, old, new, new_failed=[A])
    assert report.skipped_accounts == {A: "the current run read it only in part"}
    assert (
        f"- **accounts_not_compared:** {A} (the current run read it only in part)"
        in markdown
    )
    assert report.summary["removed_count"] == 0


def test_account_read_in_part_in_the_previous_run(tmp_path):
    old = [_row(A, "a1"), _row(B, "b1")]
    new = [_row(A, "a1"), _row(A, "a2"), _row(B, "b1")]
    report, _ = _report(tmp_path, old, new, old_failed=[A])
    assert report.skipped_accounts == {A: "the previous run read it only in part"}


def test_account_with_no_rows_keeps_the_could_not_scan_text(tmp_path):
    old = [_row(A, "a1"), _row(B, "b1")]
    new = [_row(B, "b1")]
    report, markdown = _report(tmp_path, old, new, new_failed=[A])
    assert report.skipped_accounts == {A: "the current run could not scan it"}
    assert f"{A} (the current run could not scan it)" in markdown
    report, _ = _report(tmp_path / "p", new, old, old_failed=[A])
    assert report.skipped_accounts == {A: "the previous run could not scan it"}
