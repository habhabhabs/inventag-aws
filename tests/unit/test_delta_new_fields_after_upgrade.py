"""Fields new only because InvenTag reads more are not "modified" after an upgrade.

Work order: retry-backoff-memo.md section 8.2. Every snapshot records
``metadata.tags.inventag_version``. When a ``raw_data`` field is present now
but absent from every row of the same service and type in the previous
snapshot, and that snapshot has no version or an older one, the field is not
compared, and the change report says so once. Everything else is compared as
before: a changed or removed field, a field some previous row of that type
already had, and any new field when both snapshots come from the same version.
"""

import json

import pytest

from inventag._version import __version__
from inventag.state import ChangelogGenerator, DeltaDetector, StateManager
from inventag.state.state_manager import SNAPSHOT_VERSION

ACC = "111111111111"
REG = "us-east-1"
CONFIG = {"subnetIds": ["subnet-1", "subnet-2"], "securityGroupIds": ["sg-1"]}


def _cluster(name, **raw):
    return {
        "service": "EKS",
        "type": "Cluster",
        "id": name,
        "arn": f"arn:aws:eks:{REG}:{ACC}:cluster/{name}",
        "region": REG,
        "account_id": ACC,
        "source_account_id": ACC,
        "source": "service-api",
        "tags": {"Name": name},
        "raw_data": {"name": name, **raw},
    }


def _compare(tmp_path, old, new, previous_version="absent"):
    sm = StateManager(state_dir=str(tmp_path))
    tags = {}
    if previous_version != "absent":
        tags["inventag_version"] = previous_version
    first = sm.save_state(old, account_id=ACC, regions=[REG], tags=tags)
    if previous_version == "absent":
        # A snapshot of v1.2.1 or older: no version key.
        path = sm._state_path(first)
        data = json.loads(path.read_text())
        data["metadata"]["tags"].pop("inventag_version", None)
        path.write_text(json.dumps(data))
    second = sm.save_state(new, account_id=ACC, regions=[REG])
    report = DeltaDetector().detect_changes_by_state_id(sm, first, second)
    markdown = ChangelogGenerator().generate_changelog(report).to_markdown()
    return report, markdown


def _line(n, written_by):
    return (
        f"{n} field(s) that this InvenTag version reads for the first time were "
        f"not compared (snapshot written by {written_by})."
    )


def test_every_snapshot_records_the_inventag_version(tmp_path):
    sm = StateManager(state_dir=str(tmp_path))
    state_id = sm.save_state([], account_id=ACC, regions=[REG])
    snapshot = sm.load_state(state_id, strict=True)
    assert snapshot.metadata.tags["inventag_version"] == __version__
    assert snapshot.metadata.version == SNAPSHOT_VERSION == "1.1"


def test_a_snapshot_without_the_key_new_eks_field_is_not_modified(tmp_path):
    old = [_cluster("c1"), _cluster("c2")]
    new = [
        _cluster("c1", resourcesVpcConfig=CONFIG),
        _cluster("c2", resourcesVpcConfig=CONFIG),
    ]
    report, markdown = _compare(tmp_path, old, new)
    assert report.summary["modified_count"] == 0
    assert report.summary["unchanged_count"] == 2
    line = _line(1, "an earlier version")
    assert report.change_statistics["new_fields_not_compared"] == line
    assert f"- **new_fields_not_compared:** {line}" in markdown


def test_an_older_version_names_it(tmp_path):
    old = [_cluster("c1")]
    new = [_cluster("c1", resourcesVpcConfig=CONFIG)]
    report, _ = _compare(tmp_path, old, new, previous_version="1.2.0")
    assert report.summary["modified_count"] == 0
    assert report.change_statistics["new_fields_not_compared"] == _line(1, "1.2.0")


def test_same_version_the_new_field_is_a_modification(tmp_path):
    old = [_cluster("c1")]
    new = [_cluster("c1", resourcesVpcConfig=CONFIG)]
    report, markdown = _compare(tmp_path, old, new, previous_version=__version__)
    assert report.summary["modified_count"] == 1
    assert "new_fields_not_compared" not in report.change_statistics
    assert "new_fields_not_compared" not in markdown


def test_a_field_some_previous_row_of_that_type_had_is_compared(tmp_path):
    old = [_cluster("c1"), _cluster("c2", resourcesVpcConfig=CONFIG)]
    new = [
        _cluster("c1", resourcesVpcConfig=CONFIG),
        _cluster("c2", resourcesVpcConfig=CONFIG),
    ]
    report, _ = _compare(tmp_path, old, new, previous_version="1.2.0")
    assert [c.resource_id for c in report.modified_resources] == ["c1"]
    assert "new_fields_not_compared" not in report.change_statistics


@pytest.mark.parametrize("previous_version", ["absent", "1.2.0", __version__])
def test_a_changed_or_removed_field_is_always_reported(tmp_path, previous_version):
    old = [_cluster("c1", version="1.29"), _cluster("c2", version="1.29")]
    new = [
        _cluster("c1", version="1.30", resourcesVpcConfig=CONFIG),
        _cluster("c2", resourcesVpcConfig=CONFIG),
    ]
    report, _ = _compare(tmp_path, old, new, previous_version)
    paths = {
        c.resource_id: sorted(a.attribute_path for a in c.attribute_changes)
        for c in report.modified_resources
    }
    assert "raw_data.version" in paths["c1"]
    assert "raw_data.version" in paths["c2"]
    new_field_compared = previous_version == __version__
    assert ("raw_data.resourcesVpcConfig" in paths["c1"]) is new_field_compared


@pytest.mark.parametrize("bad", ["", "next", "1.x", None, 12, ["1", "2"]])
def test_an_unparsable_version_counts_as_absent(tmp_path, bad):
    report, _ = _compare(
        tmp_path, [_cluster("c1")], [_cluster("c1", resourcesVpcConfig=CONFIG)], bad
    )
    assert report.summary["modified_count"] == 0
    assert report.change_statistics["new_fields_not_compared"] == _line(
        1, "an earlier version"
    )


def test_other_types_are_not_affected(tmp_path):
    other = dict(_cluster("c1"), service="SQS", type="Queue")
    other["arn"] = f"arn:aws:sqs:{REG}:{ACC}:q1"
    new_other = dict(other, raw_data={"name": "c1", "Policy": "x"})
    old = [other, _cluster("c9", Policy="y")]
    new = [new_other, _cluster("c9", Policy="y")]
    report, _ = _compare(tmp_path, old, new)
    # The queue type never had "Policy" in the previous snapshot: new field.
    assert report.summary["modified_count"] == 0


def test_same_version_complete_run_is_unchanged(tmp_path):
    old = [_cluster("c1", version="1.29")]
    report, markdown = _compare(tmp_path, old, old, previous_version=__version__)
    assert report.summary["total_changes"] == 0
    assert "new_fields_not_compared" not in markdown
