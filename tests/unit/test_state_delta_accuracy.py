"""Delta and changelog accuracy: only real changes are reported."""

import copy
import subprocess
import sys

import pytest

from inventag.state import ChangelogGenerator, DeltaDetector, StateManager
from inventag.state.state_manager import StateLoadError


def _lam(**extra):
    r = {
        "service": "Lambda",
        "resource_type": "Function",
        "resource_id": "fn1",
        "type": "Function",
        "id": "fn1",
        "arn": "arn:aws:lambda:us-east-1:111111111111:function:fn1",
        "region": "us-east-1",
        "source_account_id": "111111111111",
        "tags": {"Owner": "a", "Env": "prod"},
        "raw_data": {
            "Runtime": "python3.12",
            "Layers": ["l1", "l2"],
            "SecurityGroupIds": ["sg-1", "sg-2"],
        },
        "discovered_via": "ServiceAPI:list_functions",
        "discovered_at": "2026-01-01T00:00:00+00:00",
    }
    r.update(extra)
    return r


def _detect(old, new, **kw):
    return DeltaDetector().detect_changes(old, new, "old", "new", **kw)


def _ids(changes):
    return sorted(c.resource_id for c in changes)


def test_added_removed_and_tag_changes():
    old = [
        _lam(),
        _lam(id="gone", arn="arn:aws:lambda:us-east-1:111111111111:function:gone"),
    ]
    new = [
        _lam(tags={"Owner": "b", "Env": "prod", "New": "x"}),
        _lam(id="new", arn="arn:aws:lambda:us-east-1:111111111111:function:new"),
    ]
    report = _detect(old, new)
    assert _ids(report.added_resources) == ["new"]
    assert _ids(report.removed_resources) == ["gone"]
    (modified,) = report.modified_resources
    paths = {c.attribute_path for c in modified.attribute_changes}
    assert {"tags", "tags.Owner", "tags.New"} <= paths
    assert report.summary["total_changes"] == 3


def test_list_order_only_is_not_a_change():
    new = _lam()
    new["raw_data"] = {
        "Runtime": "python3.12",
        # Layers keep their order (Lambda applies them in order); see
        # test_delta_upgrade_noise.py::test_order_of_lambda_layers_is_a_change
        "Layers": ["l1", "l2"],
        "SecurityGroupIds": ["sg-2", "sg-1"],
    }
    report = _detect([_lam()], [new])
    assert report.summary["total_changes"] == 0
    assert report.summary["unchanged_count"] == 1


def test_order_of_dict_lists_is_not_a_change_but_content_is():
    rules_a = [{"Port": 22, "Cidr": "10.0.0.0/8"}, {"Port": 443, "Cidr": "0.0.0.0/0"}]
    old = _lam(raw_data={"Rules": rules_a})
    same = _lam(raw_data={"Rules": list(reversed(rules_a))})
    assert _detect([old], [same]).summary["total_changes"] == 0
    changed = _lam(
        raw_data={"Rules": [rules_a[0], {"Port": 443, "Cidr": "1.1.1.1/32"}]}
    )
    assert _detect([old], [changed]).summary["modified_count"] == 1


def test_tag_list_and_tag_map_forms_are_the_same():
    old = _lam(tags={"Owner": "a", "Env": "prod"})
    new = _lam(tags=[{"Key": "Env", "Value": "prod"}, {"Key": "Owner", "Value": "a"}])
    assert _detect([old], [new]).summary["total_changes"] == 0


def test_volatile_fields_are_not_changes():
    old = _lam(
        raw_data={"ItemCount": 1, "TableSizeBytes": 10, "Runtime": "x"},
        monthly_spend=1.5,
        billing_cost_30d=3.0,
        data_sources=["a", "b"],
    )
    new = _lam(
        raw_data={"ItemCount": 99, "TableSizeBytes": 5000, "Runtime": "x"},
        monthly_spend=9.9,
        billing_cost_30d=4.0,
        data_sources=["b", "a", "c"],
        discovered_via="ResourceGroupsTaggingAPI",
        discovered_at="2027-01-01T00:00:00+00:00",
        discovery_timestamp="2027-01-01T00:00:00+00:00",
    )
    assert _detect([old], [new]).summary["total_changes"] == 0


def test_volatile_fields_can_be_turned_off():
    old = _lam(monthly_spend=1.0)
    new = _lam(monthly_spend=2.0)
    report = DeltaDetector(volatile_fields=[]).detect_changes([old], [new], "o", "n")
    assert report.summary["modified_count"] == 1


def test_real_change_next_to_noise_is_still_reported():
    new = _lam()
    new["raw_data"]["Runtime"] = "python3.13"
    new["raw_data"]["Layers"] = ["l2", "l1"]
    report = _detect([_lam()], [new])
    (modified,) = report.modified_resources
    assert any(
        "Runtime" in c.attribute_path or c.attribute_path == "raw_data"
        for c in modified.attribute_changes
    )


def test_resource_moving_between_tagging_and_service_path_is_not_removed_plus_added():
    service_path = _lam()
    # Tagging API route: same ARN with another spelling, no raw_data, other id form
    tagging_path = {
        "service": "lambda",
        "type": "function",
        "id": "function:fn1",
        "arn": "arn:aws:lambda:us-east-1:111111111111:function/fn1",
        "region": "us-east-1",
        "source_account_id": "111111111111",
        "tags": {"Owner": "a", "Env": "prod"},
        "discovered_via": "ResourceGroupsTaggingAPI",
    }
    for old, new in [
        ([service_path], [tagging_path]),
        ([tagging_path], [service_path]),
    ]:
        report = _detect(old, new)
        assert report.summary["added_count"] == 0
        assert report.summary["removed_count"] == 0
        assert report.summary["total_changes"] == 0


def test_resource_with_arn_in_one_run_and_none_in_the_other_is_the_same_resource():
    with_arn = _lam()
    no_arn = _lam(arn="")
    report = _detect([no_arn], [with_arn])
    assert report.summary["added_count"] == 0 and report.summary["removed_count"] == 0
    assert report.summary["total_changes"] == 0


def test_two_different_arns_are_never_merged():
    a = _lam()
    b = _lam(
        arn="arn:aws:lambda:eu-west-1:111111111111:function:fn1", region="eu-west-1"
    )
    report = _detect([a], [b])
    assert report.summary["added_count"] == 1 and report.summary["removed_count"] == 1


def test_resources_without_arn_or_id_have_a_key_that_is_stable_across_processes():
    code = (
        "import json,sys;from inventag.state import DeltaDetector;"
        "m=DeltaDetector()._create_resource_map([{'service':'X','type':'Y','region':'r','n':1}]);"
        "print(list(m)[0])"
    )
    keys = {
        subprocess.run(
            [sys.executable, "-c", code],
            env={"PYTHONHASHSEED": seed, "PATH": "", "PYTHONPATH": ":".join(sys.path)},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for seed in ("1", "2", "3")
    }
    assert len(keys) == 1


def test_resources_are_not_modified_by_the_comparison():
    old, new = [_lam()], [_lam(tags={"Owner": "z"})]
    before = copy.deepcopy((old, new))
    _detect(old, new)
    assert (old, new) == before


# --------------------------------------------------------------- account scope
def _acct(account, n, **extra):
    return _lam(
        id=f"fn{n}",
        arn=f"arn:aws:lambda:us-east-1:{account}:function:fn{n}",
        source_account_id=account,
        **extra,
    )


def test_skipped_account_resources_are_not_reported_removed():
    old = [_acct("111", 1), _acct("222", 1), _acct("222", 2)]
    new = [_acct("111", 1)]
    report = _detect(old, new, skip_accounts={"222": "failed"})
    assert report.summary["total_changes"] == 0
    assert report.skipped_accounts == {"222": "failed"}
    # without the skip they all look removed
    assert _detect(old, new).summary["removed_count"] == 2


def _state_manager(tmp_path):
    return StateManager(str(tmp_path / "s"), retention_days=None, max_snapshots=None)


def _save(manager, resources, **kw):
    return manager.save_state(resources, "111", ["us-east-1"], **kw)


def test_failed_account_in_the_new_run_is_left_out(tmp_path):
    manager = _state_manager(tmp_path)
    first = _save(manager, [_acct("111", 1), _acct("222", 1)])
    second = _save(manager, [_acct("111", 1), _acct("111", 2)], accounts_failed=["222"])
    report = DeltaDetector().detect_changes_by_state_id(manager, first, second)
    assert _ids(report.added_resources) == ["fn2"]
    assert report.removed_resources == []
    assert "222" in report.skipped_accounts
    assert "could not scan" in report.skipped_accounts["222"]


def test_failed_account_in_the_previous_run_is_left_out(tmp_path):
    manager = _state_manager(tmp_path)
    first = _save(manager, [_acct("111", 1)], accounts_failed=["222"])
    second = _save(manager, [_acct("111", 1), _acct("222", 1), _acct("222", 2)])
    report = DeltaDetector().detect_changes_by_state_id(manager, first, second)
    assert report.added_resources == []  # not "2 added"
    assert "previous run" in report.skipped_accounts["222"]


def test_scope_is_derived_when_the_caller_passes_no_account_lists(tmp_path):
    """Callers that do not pass accounts_failed still avoid mass removal."""
    manager = _state_manager(tmp_path)
    first = _save(manager, [_acct("111", 1), _acct("222", 1)])
    second = _save(manager, [_acct("111", 1)])  # account 222 produced nothing
    report = DeltaDetector().detect_changes_by_state_id(manager, first, second)
    assert report.removed_resources == []
    assert "222" in report.skipped_accounts


def test_removed_resource_in_a_scanned_account_is_still_reported(tmp_path):
    manager = _state_manager(tmp_path)
    first = _save(manager, [_acct("111", 1), _acct("111", 2), _acct("222", 1)])
    second = _save(manager, [_acct("111", 1), _acct("222", 1)])
    report = DeltaDetector().detect_changes_by_state_id(manager, first, second)
    assert _ids(report.removed_resources) == ["fn2"]
    assert report.skipped_accounts == {}


def test_changelog_names_the_accounts_that_were_not_compared(tmp_path):
    report = _detect(
        [_acct("222", 1)], [_acct("111", 1)], skip_accounts={"222": "it failed"}
    )
    changelog = ChangelogGenerator(output_dir=str(tmp_path / "c")).generate_changelog(
        report
    )
    assert "222 (it failed)" in changelog.to_markdown()
    assert not (tmp_path / "c").exists()  # nothing is created until a file is written


# ------------------------------------------------------- first run / bad input
def test_first_run_has_nothing_to_compare(tmp_path):
    manager = _state_manager(tmp_path)
    first = _save(manager, [_acct("111", 1)])
    assert manager.find_previous_state(first) == (None, [])
    assert len(manager.list_states()) == 1


def test_unreadable_previous_snapshot_raises_a_clear_error_not_a_type_error(tmp_path):
    manager = _state_manager(tmp_path)
    first = _save(manager, [_acct("111", 1)])
    second = _save(manager, [_acct("111", 1)])
    (tmp_path / "s" / f"state_{first}.json").write_text('{"metadata": {')
    with pytest.raises(StateLoadError, match="corrupt or truncated"):
        DeltaDetector().detect_changes_by_state_id(manager, first, second)
    with pytest.raises(StateLoadError, match="no comparison was made"):
        DeltaDetector().detect_changes_by_state_id(manager, "19990101_000000", second)
