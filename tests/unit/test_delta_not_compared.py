"""A resource the current run could not have seen is "not compared", not "removed".

Register row A-05 (plan section 4.1, order 6). The current run tells the
comparison what it read (``current_run``: the discovery coverage ledger, and
the regions and services of each account). A resource of the previous
snapshot that is missing now is left out of "removed" when:

* its account, service and region had a listing that was not ok in the
  current run (denied, throttled, error, timeout), or
* its region or service lies outside what the current run scanned, or
* it was found only through the Tagging API and that API failed in its region.

A resource that is still there but came back only through the Tagging API
because its service listing failed is "not compared", not "modified" (S1 D14).

When the previous snapshot's ``coverage_summary`` counts denied, throttled,
error or timeout listings, the change report carries one caveat line.

A run with complete coverage gives the same report as before, byte for byte.
"""

import json
from dataclasses import asdict

import pytest

from inventag.state import ChangelogGenerator, DeltaDetector, StateManager

ACC = "111111111111"
REG = "us-east-1"


def _row(service, rid, arn, region=REG, source="service-api", **extra):
    r = {
        "service": service,
        "type": "T",
        "id": rid,
        "arn": arn,
        "region": region,
        "account_id": ACC,
        "source_account_id": ACC,
        "source": source,
        "tags": {"Name": rid},
        "raw_data": {"Id": rid, "Detail": "full"},
    }
    r.update(extra)
    return r


def _queue(name="q1", **extra):
    return _row("SQS", name, f"arn:aws:sqs:{REG}:{ACC}:{name}", **extra)


def _vpc(vid="vpc-1", region=REG):
    return _row("VPC", vid, f"arn:aws:ec2:{region}:{ACC}:vpc/{vid}", region=region)


def _bucket(name, region):
    return _row("S3", name, f"arn:aws:s3:::{name}", region=region)


def _entry(service, outcome, region=REG, source="service-api", account=ACC):
    return {
        "account_id": account,
        "region": region,
        "source": source,
        "service": service,
        "resource_type": "",
        "operation": "List",
        "outcome": outcome,
        "count": 0,
        "error_code": "",
        "seconds": 0.0,
    }


def _run(entries, regions=None, services=None):
    return {
        "coverage": entries,
        "regions": {ACC: regions if regions is not None else [REG]},
        "services": {ACC: services or []},
    }


def _detect(old, new, current_run=None):
    return DeltaDetector().detect_changes(
        old, new, "old", "new", current_run=current_run
    )


def _removed(report):
    return sorted(c.resource_id for c in report.removed_resources)


def _without_clocks(report):
    data = asdict(report)
    data.pop("timestamp")
    for key in (
        "added_resources",
        "removed_resources",
        "modified_resources",
        "unchanged_resources",
    ):
        for change in data[key]:
            change.pop("timestamp")
    return json.dumps(data, default=str)


def _markdown(report):
    report.timestamp = "frozen"
    for change in (
        report.added_resources + report.removed_resources + report.modified_resources
    ):
        change.timestamp = "frozen"
    changelog = ChangelogGenerator().generate_changelog(report, title="T")
    changelog.generation_timestamp = "frozen"
    return changelog.to_markdown()


# --------------------------------------------------------- failed listings


def test_throttled_listing_makes_its_resources_not_compared():
    old = [_queue("q1"), _queue("q2"), _vpc()]
    new = [_vpc()]
    run = _run([_entry("sqs", "throttled"), _entry("vpc", "ok")])
    report = _detect(old, new, run)
    assert _removed(report) == []
    assert report.summary["removed_count"] == 0
    assert report.summary["not_compared_count"] == 2
    assert report.change_statistics["not_compared"] == {
        f"sqs in {REG} of account {ACC}: throttled": 2
    }
    markdown = _markdown(report)
    assert (
        f"- **resources_not_compared:** 2 (sqs in {REG} of account {ACC}: "
        "throttled: 2)" in markdown
    )


@pytest.mark.parametrize("outcome", ["denied", "error", "timeout"])
def test_every_failed_outcome_counts(outcome):
    report = _detect([_queue()], [], _run([_entry("sqs", outcome)]))
    assert _removed(report) == []
    assert report.summary["not_compared_count"] == 1


@pytest.mark.parametrize("outcome", ["ok", "empty"])
def test_a_read_listing_still_reports_removed(outcome):
    report = _detect([_queue()], [], _run([_entry("sqs", outcome)]))
    assert _removed(report) == ["q1"]
    assert "not_compared_count" not in report.summary
    assert "not_compared" not in report.change_statistics


def test_other_regions_and_accounts_are_not_affected():
    old = [_queue("q1"), _row("SQS", "q9", f"arn:aws:sqs:eu-west-1:{ACC}:q9")]
    old[1]["region"] = "eu-west-1"
    run = _run([_entry("sqs", "throttled")], regions=[REG, "eu-west-1"])
    run["coverage"].append(_entry("sqs", "ok", region="eu-west-1"))
    run["coverage"].append(_entry("sqs", "throttled", account="222222222222"))
    report = _detect(old, [], run)
    assert _removed(report) == ["q9"]


def test_service_name_decides_before_the_arn_service():
    # VPC rows have ec2 ARNs; the vpc listing was read, an ec2 one failed.
    run = _run([_entry("vpc", "ok"), _entry("ec2", "throttled")])
    report = _detect([_vpc()], [], run)
    assert _removed(report) == ["vpc-1"]


def test_arn_service_is_used_when_the_service_name_has_no_listing():
    old = [_row("ELB", "lb-1", f"arn:aws:elasticloadbalancing:{REG}:{ACC}:lb/x")]
    report = _detect(old, [], _run([_entry("elbv2", "denied")]))
    assert _removed(report) == []


def test_global_listing_covers_resources_in_any_region():
    old = [_bucket("b-east", REG), _bucket("b-west", "eu-west-1")]
    report = _detect(old, [], _run([_entry("s3", "denied", region="global")]))
    assert _removed(report) == []
    report = _detect(old, [], _run([_entry("s3", "ok", region="global")]))
    assert _removed(report) == ["b-east", "b-west"]


def test_tagging_only_resource_when_the_tagging_api_failed():
    old = [_queue(source="tagging-api")]
    run = _run([_entry("resourcegroupstaggingapi", "denied", source="tagging-api")])
    assert _removed(_detect(old, [], run)) == []
    # A resource the service API found is not affected by the Tagging API.
    assert _removed(_detect([_queue()], [], run)) == ["q1"]


def test_route_only_change_after_a_failed_listing_is_not_modified():
    """S1 D14: run 2's SQS listing is throttled, the Tagging API still returns the queue."""
    # The Tagging API row has no service-specific fields (here: the queue's
    # visibility timeout), so without the ledger it reads as modified.
    old = [_queue(visibility_timeout=30)]
    new = [_queue(source="tagging-api", raw_data={"ResourceARN": "x"})]
    assert _detect(old, new).summary["modified_count"] == 1
    report = _detect(old, new, _run([_entry("sqs", "throttled")]))
    assert report.summary["modified_count"] == 0
    assert report.summary["unchanged_count"] == 0
    assert report.summary["not_compared_count"] == 1


# ------------------------------------------------------------------- scope


def test_region_outside_the_current_run_is_not_compared():
    old = [_queue(), _vpc("vpc-w", region="eu-west-1")]
    run = _run([_entry("sqs", "ok"), _entry("vpc", "ok")], regions=[REG])
    report = _detect(old, [], run)
    assert _removed(report) == ["q1"]
    assert report.change_statistics["not_compared"] == {
        f"region eu-west-1 of account {ACC} was not scanned in this run": 1
    }


def test_no_region_list_means_no_region_rule():
    report = _detect([_vpc("vpc-w", region="eu-west-1")], [], _run([], regions=[]))
    assert _removed(report) == ["vpc-w"]


def test_service_outside_the_current_run_is_not_compared():
    old = [_queue(), _vpc()]
    run = _run([_entry("sqs", "ok")], services=["SQS"])
    report = _detect(old, [], run)
    assert _removed(report) == ["q1"]
    assert report.change_statistics["not_compared"] == {
        f"service VPC of account {ACC} was not in this run's services": 1
    }


def test_added_resources_are_unchanged_by_the_scope():
    report = _detect([], [_queue()], _run([_entry("sqs", "throttled")]))
    assert [c.resource_id for c in report.added_resources] == ["q1"]


# ----------------------------------------------- complete runs: byte-identical


def _estate():
    old = [_queue("q1"), _queue("q2"), _vpc(), _bucket("b1", REG)]
    new = [_queue("q1", tags={"Name": "q1", "Env": "x"}), _vpc("vpc-2")]
    return old, new


def test_complete_run_gives_the_same_report_and_changelog():
    old, new = _estate()
    run = _run([_entry("sqs", "ok"), _entry("vpc", "ok"), _entry("s3", "empty")])
    before = _detect(old, new)
    after = _detect(old, new, run)
    assert _without_clocks(after) == _without_clocks(before)
    assert _markdown(after) == _markdown(before)


def test_without_current_run_nothing_changes():
    old, new = _estate()
    report = _detect(old, new, None)
    assert _removed(report) == ["b1", "q2", "vpc-1"]
    assert "not_compared_count" not in report.summary


# --------------------------------------------- caveat from the previous run


def _two_snapshots(tmp_path, previous_summary):
    sm = StateManager(state_dir=str(tmp_path))
    old, new = _estate()
    first = sm.save_state(
        old,
        account_id=ACC,
        regions=[REG],
        tags={"coverage_summary": previous_summary},
    )
    second = sm.save_state(
        new, account_id=ACC, regions=[REG], tags={"coverage_summary": {ACC: {"ok": 3}}}
    )
    return sm, first, second


def test_caveat_when_the_previous_run_missed_listings(tmp_path):
    sm, first, second = _two_snapshots(
        tmp_path, {ACC: {"ok": 3, "denied": 2, "throttled": 1}}
    )
    report = DeltaDetector().detect_changes_by_state_id(sm, first, second)
    caveat = (
        f"The previous run could not read every listing (account {ACC}: 2 denied, "
        "1 throttled); resources it missed may show as added."
    )
    assert report.change_statistics["previous_run_incomplete"] == caveat
    assert f"- **previous_run_incomplete:** {caveat}" in _markdown(report)


def test_no_caveat_after_a_complete_previous_run(tmp_path):
    sm, first, second = _two_snapshots(tmp_path, {ACC: {"ok": 3, "empty": 4}})
    report = DeltaDetector().detect_changes_by_state_id(sm, first, second)
    assert "previous_run_incomplete" not in report.change_statistics
    assert "previous_run_incomplete" not in _markdown(report)


def test_by_state_id_passes_the_current_run_on(tmp_path):
    sm, first, second = _two_snapshots(tmp_path, {ACC: {"ok": 3}})
    run = _run([_entry("sqs", "throttled"), _entry("vpc", "ok")])
    report = DeltaDetector().detect_changes_by_state_id(
        sm, first, second, current_run=run
    )
    assert _removed(report) == ["b1", "vpc-1"]
    assert report.summary["not_compared_count"] == 1
