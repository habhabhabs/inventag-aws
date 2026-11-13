"""First change report after upgrading from v1.1.4: rows differ only in how
they were found (new source columns, Tagging API row now a service API row),
and that is not a change of the resource."""

import copy

import pytest

from inventag.state.delta_detector import DeltaDetector

ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:flow"


def _v114_tagging_row(tags):
    return {
        "service": "STATES",
        "resource_type": "Unknown",
        "type": "Unknown",
        "id": "flow",
        "resource_id": "flow",
        "arn": ARN,
        "region": "us-east-1",
        "account_id": "123456789012",
        "tags": dict(tags),
        "raw_data": {"arn": ARN},
        "discovered_via": "ResourceGroupsTaggingAPI:Fallback",
        "priority": "fallback",
    }


def _v120_service_row(tags):
    return {
        "service": "STATES",
        "resource_type": "StateMachine",
        "type": "StateMachine",
        "id": "flow",
        "resource_id": "flow",
        "arn": ARN,
        "region": "us-east-1",
        "account_id": "123456789012",
        "tags": dict(tags),
        "raw_data": {"name": "flow", "stateMachineArn": ARN, "type": "STANDARD"},
        "discovered_via": "ServiceAPI:list_state_machines",
        "priority": "primary",
        "source": "service-api",
        "sources": "service-api+tagging-api",
        "detail_level": "full",
    }


def _report(old, new):
    return DeltaDetector().detect_changes([old], [new], "s1", "s2")


def test_tagging_row_then_service_row_is_unchanged():
    report = _report(
        _v114_tagging_row({"Owner": "a"}), _v120_service_row({"Owner": "a"})
    )
    assert not report.modified_resources
    assert not report.added_resources and not report.removed_resources


def test_a_tag_change_is_still_reported_across_the_route_change():
    report = _report(
        _v114_tagging_row({"Owner": "a"}), _v120_service_row({"Owner": "b"})
    )
    assert len(report.modified_resources) == 1
    paths = [c.attribute_path for c in report.modified_resources[0].attribute_changes]
    assert any(p.startswith("tags") for p in paths), paths


def test_new_source_columns_alone_are_not_a_change():
    old = _v120_service_row({"Owner": "a"})
    for key in ("source", "sources", "detail_level"):
        old.pop(key)
    report = _report(old, _v120_service_row({"Owner": "a"}))
    assert not report.modified_resources


def test_same_route_raw_data_change_is_reported():
    old = _v120_service_row({"Owner": "a"})
    new = copy.deepcopy(old)
    new["raw_data"]["type"] = "EXPRESS"
    report = _report(old, new)
    assert len(report.modified_resources) == 1


def _fn(layers, policies=None, behaviors=None):
    row = _v120_service_row({})
    row["raw_data"] = {
        "Layers": [{"Arn": a} for a in layers],
        "TerminationPolicies": policies or [],
        "CacheBehaviors": {"Quantity": 2, "Items": behaviors or []},
        "SecurityGroups": ["sg-1", "sg-2"],
    }
    return row


def test_order_of_lambda_layers_is_a_change():
    report = _report(_fn(["l1", "l2"]), _fn(["l2", "l1"]))
    assert len(report.modified_resources) == 1


def test_order_of_termination_policies_and_cache_behaviors_is_a_change():
    a = _fn(
        [], ["OldestInstance", "Default"], [{"PathPattern": "/a"}, {"PathPattern": "*"}]
    )
    b = _fn(
        [], ["Default", "OldestInstance"], [{"PathPattern": "/a"}, {"PathPattern": "*"}]
    )
    assert len(_report(a, b).modified_resources) == 1
    c = _fn([], [], [{"PathPattern": "*"}, {"PathPattern": "/a"}])
    d = _fn([], [], [{"PathPattern": "/a"}, {"PathPattern": "*"}])
    assert len(_report(c, d).modified_resources) == 1


def test_other_lists_stay_unordered():
    a, b = _fn(["l1"]), _fn(["l1"])
    b["raw_data"]["SecurityGroups"] = ["sg-2", "sg-1"]
    assert not _report(a, b).modified_resources


@pytest.mark.parametrize(
    "field,old,new",
    [
        ("SizeInBytes", {"Value": 6144}, {"Value": 8192}),
        ("LastAccessedDate", "2026-11-01", "2026-11-14"),
        ("NumberOfRecoveryPoints", 3, 4),
        ("NormalizedInstanceHours", 10, 12),
        ("LatestRestorableTime", "2026-11-14T06:00", "2026-11-14T06:05"),
    ],
)
def test_usage_counters_of_new_services_are_not_changes(field, old, new):
    a, b = _v120_service_row({}), _v120_service_row({})
    a["raw_data"][field], b["raw_data"][field] = old, new
    assert not _report(a, b).modified_resources
