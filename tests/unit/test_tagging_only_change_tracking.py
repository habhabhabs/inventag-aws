"""Tagging-API-only runs keep their change tracking (review finding M2).

v1.2.0: when every service-API listing is denied but ``tag:GetResources``
works, the report holds the tagged resources and the change report is right
(a deleted queue is "removed", a changed tag is "modified"). The first patch
(A-01) left such an account out of every comparison: 0 changes. Ruling: an
account is left out of change tracking, and gets no snapshot, only when the
run read nothing for it (no resource from any source). Otherwise it is
compared, and the units whose service listing failed are "not compared"
(A-05), so a full-access run followed by a tagging-only run still does not
show the untagged resources as removed.

Real CLI runs under moto with the regression harness's fault injector.
"""

import json
import logging
from pathlib import Path

import boto3

from inventag.security.read_only_guard import uninstall_global_guard
from tests.regression.faults import FaultInjector, deny_everything
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD_ID,
    aws,
    empty_aws,
    logged,
    reports,
    run_cli,
)
from tests.unit.test_snapshot_not_poisoned import result_spy, run_notes

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]
QUEUE = "e2e-queue"  # tagged queue of the e2e estate
TOPIC = "e2e-topic"  # tagged topic of the e2e estate
UNTAGGED = "untagged-queue"


def tagging_only():
    """Every call AccessDenied except STS, DescribeRegions and the Tagging API."""
    return deny_everything(keep=("sts", "resourcegroupstaggingapi"))


def run(results, faults=()):
    """One CLI run with the given faults; returns (exit code, result dict)."""
    with FaultInjector(faults) as injector:
        injector.arm()
        code = run_cli(*ARGS)
    return code, results[-1]


def delta(result):
    d = (result.get("state_management") or {}).get("delta_detection") or {}
    return d.get("summary")


def arns(changes):
    return {c.resource_arn for c in changes}


def snapshot_files(tmp_path):
    return sorted((tmp_path / "out" / "state").glob("state_*.json"))


def topic_arn():
    sns = boto3.client("sns", region_name="us-east-1")
    return next(
        t["TopicArn"] for t in sns.list_topics()["Topics"] if TOPIC in t["TopicArn"]
    )


def queue_url(name):
    return boto3.client("sqs", region_name="us-east-1").get_queue_url(QueueName=name)[
        "QueueUrl"
    ]


# (a) ---------------------------------------------------------------------
def test_a_tagging_only_account_keeps_its_change_report(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)
    code1, first = run(results, [tagging_only()])
    assert code1 == 0
    queue_arn = next(
        r["arn"]
        for r in json.loads(snapshot_files(tmp_path)[-1].read_text())["resources"]
        if QUEUE in str(r.get("arn", ""))
    )

    uninstall_global_guard()  # the test changes the estate between runs
    boto3.client("sqs", region_name="us-east-1").delete_queue(QueueUrl=queue_url(QUEUE))
    boto3.client("sns", region_name="us-east-1").tag_resource(
        ResourceArn=topic_arn(), Tags=[{"Key": "Owner", "Value": "someone-else"}]
    )
    caplog.clear()
    code2, second = run(results, [tagging_only()])
    assert code2 == 0  # exit codes as in v1.2.0
    assert second["failed_accounts"] == []

    report = delta(second)
    assert report is not None, second["state_management"]
    assert queue_arn in arns(report.removed_resources)
    assert topic_arn() in arns(report.modified_resources)

    # The snapshot lists the account as scanned, as in v1.2.0.
    meta = json.loads(snapshot_files(tmp_path)[-1].read_text())["metadata"]
    assert meta["accounts_scanned"] == [GOOD_ID]
    assert not meta["accounts_failed"]

    # A true note: the service APIs were not read, the Tagging API was.
    notes = run_notes(reports(tmp_path / "out")[-1])
    mine = [n for n in notes if GOOD_ID in n and not n.startswith("Permissions:")]
    assert len(mine) == 1, notes
    assert "Tagging API" in mine[0]
    assert "left out of change tracking" not in mine[0]


# (b) ---------------------------------------------------------------------
def test_full_access_then_tagging_only_shows_no_false_removal(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    boto3.client("sqs", region_name="us-east-1").create_queue(QueueName=UNTAGGED)
    untagged_arn = f"arn:aws:sqs:us-east-1:{GOOD_ID}:{UNTAGGED}"  # moto's ARN form
    results = result_spy(monkeypatch)
    code1, first = run(results)
    assert code1 == 0
    first_arns = {
        r.get("arn")
        for r in json.loads(snapshot_files(tmp_path)[-1].read_text())["resources"]
    }
    assert untagged_arn in first_arns

    code2, second = run(results, [tagging_only()])
    assert code2 == 0
    report = delta(second)
    assert report is not None, second["state_management"]
    # The untagged queue was not read this time: "not compared", not removed.
    assert untagged_arn not in arns(report.removed_resources)
    assert report.removed_resources == []
    assert report.summary.get("not_compared_count", 0) > 0
    # Tagged resources the Tagging API returned are compared (not left out).
    compared = arns(report.unchanged_resources) | arns(report.modified_resources)
    assert topic_arn() in compared


# (c) ---------------------------------------------------------------------
def test_an_account_that_read_nothing_is_still_left_out(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)
    assert run(results)[0] == 0
    before = snapshot_files(tmp_path)
    caplog.clear()
    code, result = run(results, [deny_everything()])
    assert code == 0
    assert snapshot_files(tmp_path) == before  # no snapshot
    assert any(
        GOOD_ID in m and "left out of change tracking" in m for m in logged(caplog)
    )
    assert run(results)[0] == 0
    report = delta(results[-1])
    assert report.removed_resources == [] and report.added_resources == []


# (d) ---------------------------------------------------------------------
def test_a_clean_run_has_no_note_and_compares_everything(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    results = result_spy(monkeypatch)
    assert run(results)[0] == 0
    assert run(results)[0] == 0
    assert run_notes(reports(tmp_path / "out")[-1]) == []
    report = delta(results[-1])
    assert report.summary.get("not_compared_count", 0) == 0
    assert report.removed_resources == [] and report.added_resources == []
    assert Path(snapshot_files(tmp_path)[-1]).exists()
