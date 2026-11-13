"""First change report after upgrading from v1.1.4: rows differ only in how
they were found (new source columns, Tagging API row now a service API row),
and that is not a change of the resource."""

import copy

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
