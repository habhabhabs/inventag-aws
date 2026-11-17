"""A service outside the run's service filter is outside the scope, not "not read".

Senior D's ledger (fix3/track-d): a service the ``--account-services`` filter
(or a template's ``services``) leaves out gets one entry ``source="service-api",
region="global", outcome="out_of_scope"``. Its resources missing from this run
are "not compared" with the scope reason, never "removed" and never a failed
listing; an ``out_of_scope`` unit in ``units_not_read`` is not a failure.
"""

from inventag.state import DeltaDetector, StateManager

ACC = "111111111111"
REG = "us-east-1"


def _queue(name, source="service-api"):
    return {
        "service": "SQS",
        "type": "Queue",
        "id": name,
        "arn": f"arn:aws:sqs:{REG}:{ACC}:{name}",
        "region": REG,
        "account_id": ACC,
        "source_account_id": ACC,
        "source": source,
        "sources": "service-api+tagging-api",
        "tags": {"Name": name},
    }


def _entry(service, outcome, region=REG, source="service-api"):
    return {
        "account_id": ACC,
        "region": region,
        "source": source,
        "service": service,
        "resource_type": "",
        "operation": "",
        "outcome": outcome,
        "count": 0,
        "error_code": "",
    }


def test_out_of_scope_service_is_not_compared_with_the_scope_reason():
    run = {
        # No "services" given: the ledger entry alone says it.
        "coverage": [
            _entry("sqs", "out_of_scope", region="global"),
            _entry("resourcegroupstaggingapi", "ok", source="tagging-api"),
        ],
        "regions": {ACC: [REG]},
    }
    report = DeltaDetector().detect_changes(
        [_queue("q1")], [], "s1", "s2", current_run=run
    )
    assert report.summary["removed_count"] == 0
    assert report.change_statistics["not_compared"] == {
        f"service SQS of account {ACC} was not in this run's services": 1
    }


def test_out_of_scope_in_units_not_read_is_not_a_failure(tmp_path):
    sm = StateManager(state_dir=str(tmp_path))
    unit = {
        "account": ACC,
        "service": "sqs",
        "region": "global",
        "source": "service-api",
        "outcome": "out_of_scope",
    }
    first = sm.save_state(
        [], account_id=ACC, regions=[REG], tags={"units_not_read": [unit]}
    )
    second = sm.save_state([_queue("q1")], account_id=ACC, regions=[REG])
    report = DeltaDetector().detect_changes_by_state_id(sm, first, second)
    assert [c.resource_id for c in report.added_resources] == ["q1"]
    assert "previous_run_incomplete" not in report.change_statistics


def test_the_row_s_own_service_decides_before_the_arn_service():
    vpc = {
        "service": "VPC",
        "type": "VPC",
        "id": "vpc-1",
        "arn": f"arn:aws:ec2:{REG}:{ACC}:vpc/vpc-1",
        "region": REG,
        "account_id": ACC,
        "source_account_id": ACC,
        "source": "service-api",
        "tags": {},
    }
    run = {
        "coverage": [
            _entry("ec2", "out_of_scope", region="global"),
            _entry("vpc", "ok"),
        ],
        "regions": {ACC: [REG]},
    }
    report = DeltaDetector().detect_changes([vpc], [], "s1", "s2", current_run=run)
    assert [c.resource_id for c in report.removed_resources] == ["vpc-1"]
