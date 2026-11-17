"""Tags are not compared where the current run's Tagging API did not answer (A-66).

When the Tagging API failed (throttled, denied, error, timeout) in a region
of an account in the current run, the rows of that region come back without
the tags it adds. The change report must not show those as "tags modified":
the resource is not compared for tags. Other attribute changes still show.
"""

import pytest

from inventag.state import DeltaDetector

ACC = "111111111111"
REG = "us-east-1"


def _queue(name="q1", tags=None, **extra):
    row = {
        "service": "SQS",
        "type": "Queue",
        "id": name,
        "arn": f"arn:aws:sqs:{REG}:{ACC}:{name}",
        "region": REG,
        "account_id": ACC,
        "source_account_id": ACC,
        "source": "service-api",
        "tags": {"Env": "prod", "Owner": "a"} if tags is None else tags,
    }
    row.update(extra)
    return row


def _run(tagging_outcome, region=REG):
    return {
        "coverage": [
            {
                "account_id": ACC,
                "region": REG,
                "source": "service-api",
                "service": "sqs",
                "outcome": "ok",
            },
            {
                "account_id": ACC,
                "region": region,
                "source": "tagging-api",
                "service": "resourcegroupstaggingapi",
                "outcome": tagging_outcome,
            },
        ],
        "regions": {ACC: [REG]},
        "services": {ACC: []},
    }


def _detect(old, new, run):
    return DeltaDetector().detect_changes(old, new, "s1", "s2", current_run=run)


@pytest.mark.parametrize("outcome", ["throttled", "denied", "error", "timeout"])
def test_lost_tags_after_a_failed_tagging_api_are_not_a_change(outcome):
    old = [_queue("q1"), _queue("q2")]
    new = [_queue("q1", tags={}), _queue("q2", tags={})]
    report = _detect(old, new, _run(outcome))
    assert report.summary["modified_count"] == 0
    assert report.summary["not_compared_count"] == 2
    assert report.change_statistics["not_compared"] == {
        f"tagging API in {REG} of account {ACC}: {outcome}": 2
    }


def test_other_changes_still_show_without_the_tag_changes():
    old = [_queue(visibility_timeout=30)]
    new = [_queue(tags={}, visibility_timeout=60)]
    report = _detect(old, new, _run("throttled"))
    (change,) = report.modified_resources
    paths = [c.attribute_path for c in change.attribute_changes]
    assert paths == ["visibility_timeout"]
    assert "not_compared_count" not in report.summary


def test_tags_are_compared_when_the_tagging_api_answered():
    old = [_queue()]
    new = [_queue(tags={})]
    report = _detect(old, new, _run("ok"))
    (change,) = report.modified_resources
    assert {c.attribute_path for c in change.attribute_changes} >= {"tags"}


def test_a_failure_in_another_region_does_not_matter():
    report = _detect([_queue()], [_queue(tags={})], _run("throttled", "eu-west-1"))
    assert report.summary["modified_count"] == 1


def test_without_current_run_tags_are_compared_as_before():
    report = DeltaDetector().detect_changes([_queue()], [_queue(tags={})], "s1", "s2")
    assert report.summary["modified_count"] == 1
