"""Units the previous run did not read are not compared (A-05, A-68; decision 6).

A snapshot may record the listings its run did not read in
``metadata.tags.units_not_read``: a list of ``{account, service, region,
source, outcome}`` (written by the generator, WO-A8). When the PREVIOUS
snapshot holds such a unit:

* a resource of that unit that appears now is "not compared", not "added";
* a resource that only the Tagging API can see appears now and the previous
  Tagging API failed in its region: "not compared";
* tag changes of a resource in a region where the previous Tagging API
  failed are not compared;
* the change report carries one line that names the units.

A snapshot without the key (v1.2.1 and older) gives the v1.2.1 result, and so
does an empty list. The schema version stays 1.1.
"""

import json
from dataclasses import asdict

import pytest

from inventag.state import ChangelogGenerator, DeltaDetector, StateManager
from inventag.state.state_manager import SNAPSHOT_VERSION

ACC = "111111111111"
OTHER = "222222222222"
REG = "us-east-1"


def _row(service, name, arn, account=ACC, region=REG, source="service-api", **kw):
    row = {
        "service": service,
        "type": "T",
        "id": name,
        "arn": arn,
        "region": region,
        "account_id": account,
        "source_account_id": account,
        "source": source,
        "tags": {"Name": name},
    }
    row.update(kw)
    return row


def _queue(name, account=ACC, **kw):
    return _row("SQS", name, f"arn:aws:sqs:{REG}:{account}:{name}", account, **kw)


def _vpc(name, **kw):
    return _row("VPC", name, f"arn:aws:ec2:{REG}:{ACC}:vpc/{name}", **kw)


def _unit(service, outcome="throttled", source="service-api", account=ACC, region=REG):
    return {
        "account": account,
        "service": service,
        "region": region,
        "source": source,
        "outcome": outcome,
    }


def _compare(tmp_path, old, new, units=None, accounts=(ACC,)):
    sm = StateManager(state_dir=str(tmp_path))
    tags = {"coverage_summary": {}}
    if units is not None:
        tags["units_not_read"] = units
    first = sm.save_state(
        old, account_id=ACC, regions=[REG], tags=tags, accounts_scanned=list(accounts)
    )
    second = sm.save_state(
        new,
        account_id=ACC,
        regions=[REG],
        tags={"coverage_summary": {}},
        accounts_scanned=list(accounts),
    )
    report = DeltaDetector().detect_changes_by_state_id(sm, first, second)
    return report


def _frozen(report):
    report.timestamp = "t"
    for change in (
        report.added_resources
        + report.removed_resources
        + report.modified_resources
        + report.unchanged_resources
    ):
        change.timestamp = "t"
    data = json.dumps(asdict(report), default=str)
    changelog = ChangelogGenerator().generate_changelog(report, title="T")
    changelog.generation_timestamp = "t"
    return data, changelog.to_markdown()


def _added(report):
    return sorted(c.resource_id for c in report.added_resources)


def test_resources_of_a_listing_the_previous_run_did_not_read_are_not_added(
    tmp_path,
):
    old = [_vpc("vpc-1")]  # run 1: SQS throttled, no queue listed
    new = [_vpc("vpc-1"), _queue("q1"), _queue("q2")]
    report = _compare(tmp_path, old, new, [_unit("sqs")])
    assert _added(report) == []
    assert report.summary["not_compared_count"] == 2
    assert report.change_statistics["not_compared"] == {
        f"sqs in {REG} of account {ACC} was not read by the previous run "
        "(throttled)": 2
    }


def test_the_change_report_names_the_units_the_previous_run_did_not_read(
    tmp_path,
):
    report = _compare(
        tmp_path,
        [_vpc("vpc-1")],
        [_vpc("vpc-1"), _queue("q1")],
        [_unit("sqs"), _unit("dynamodb", "denied")],
    )
    line = (
        f"The previous run did not read dynamodb in {REG} of account {ACC} "
        f"(denied); sqs in {REG} of account {ACC} (throttled). Resources found "
        "there in this run are not compared."
    )
    assert report.change_statistics["previous_run_incomplete"] == line
    _, markdown = _frozen(report)
    assert f"- **previous_run_incomplete:** {line}" in markdown


def test_tagging_only_run_then_full_run_adds_nothing(tmp_path):
    """Run 1: every service listing denied, only the Tagging API answered."""
    old = [_queue("q1", source="tagging-api")]
    new = [_queue("q1"), _queue("q2"), _vpc("vpc-1")]
    units = [_unit("sqs", "denied"), _unit("vpc", "denied")]
    report = _compare(tmp_path, old, new, units)
    assert _added(report) == []
    assert report.summary["not_compared_count"] == 2


def test_previous_tagging_failure_hides_tag_only_resources_and_tag_changes(
    tmp_path,
):
    old = [_queue("q1", tags={})]
    new = [
        _queue("q1", tags={"Env": "prod"}),
        _row("X", "x1", f"arn:aws:x:{REG}:{ACC}:thing/x1", source="tagging-api"),
    ]
    units = [_unit("resourcegroupstaggingapi", source="tagging-api")]
    report = _compare(tmp_path, old, new, units)
    assert _added(report) == []
    assert report.summary["modified_count"] == 0
    assert report.summary["not_compared_count"] == 2


def test_a_unit_that_was_read_still_reports_added(tmp_path):
    report = _compare(
        tmp_path, [_vpc("vpc-1")], [_vpc("vpc-1"), _queue("q1")], [_unit("dynamodb")]
    )
    assert _added(report) == ["q1"]


def test_other_accounts_and_regions_are_not_affected(tmp_path):
    new = [_queue("q1", account=OTHER), _vpc("vpc-1")]
    units = [_unit("sqs"), _unit("vpc", region="eu-west-1")]
    report = _compare(tmp_path, [], new, units, accounts=(ACC, OTHER))
    assert _added(report) == ["q1", "vpc-1"]


@pytest.mark.parametrize("units", [None, []])
def test_no_key_or_an_empty_list_gives_the_v121_report(tmp_path, units):
    old = [_vpc("vpc-1"), _queue("gone")]
    new = [_vpc("vpc-1", tags={"Name": "x"}), _queue("q1")]
    with_key = _compare(tmp_path / "a", old, new, units)
    without = _compare(tmp_path / "b", old, new, None)
    assert _frozen(with_key) == _frozen(without)
    assert _added(with_key) == ["q1"]
    assert "previous_run_incomplete" not in _frozen(with_key)[1]


def test_malformed_entries_are_ignored(tmp_path):
    units = ["sqs", {"service": "sqs"}, None, _unit("sqs")]
    report = _compare(tmp_path, [], [_queue("q1")], units)
    assert _added(report) == []
    report = _compare(tmp_path / "s", [], [_queue("q1")], "not a list")
    assert _added(report) == ["q1"]


def test_snapshot_version_is_unchanged():
    assert SNAPSHOT_VERSION == "1.1"
