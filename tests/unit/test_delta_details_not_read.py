"""A failed detail call does not make a resource "modified" (register row A-78, order S1).

A detail call adds fields to a row that a listing found (S3 GetBucketLocation,
Lambda GetFunctionConfiguration, RDS DescribeDBInstances, CloudFormation
DescribeStacks, EKS DescribeCluster). When it fails, the row keeps the listing's
fields and the ledger gets one ``service-api-detail`` entry per unit (account,
service, region, resource type, operation, outcome, count). The ledger does not
name the resources, so the rule is per unit:

* a field that the unit's detail call writes is not compared for a resource of
  that unit when the call failed in either of the two runs;
* the current run's failures come from its ledger (``current_run["coverage"]``),
  the previous run's from the snapshot (``metadata.tags.details_not_read``, an
  additive key that the generator writes; see the S1 report);
* denied, throttled, error (a stopped or timed-out detail call is recorded as
  "error") and timeout are treated alike;
* a resource whose only changes are such fields is unchanged (its listing
  fields were compared; the line below says which fields were not), the other
  changes of a resource stay; nothing is counted under ``not_compared``, which
  stays for resources a run did not see (A-05, and A-22's pin in
  ``test_patch2_tracks_together.py``);
* the change report names the units in one line (``details_not_compared``);
* a clean pair of runs gives the same report as before, byte for byte.
"""

import json
from dataclasses import asdict

import pytest

from inventag.state import ChangelogGenerator, DeltaDetector, StateManager

ACC = "111111111111"
OTHER = "222222222222"
REG = "us-east-1"
EU = "eu-west-1"


def _function(name="fn", account=ACC, region=REG, details=True, **raw):
    row = {
        "service": "LAMBDA",
        "resource_type": "Function",
        "type": "Function",
        "id": name,
        "resource_id": name,
        "arn": f"arn:aws:lambda:{region}:{account}:function:{name}",
        "region": region,
        "account_id": account,
        "source_account_id": account,
        "source": "service-api",
        "tags": {"Name": name},
        "raw_data": {"FunctionName": name, "Runtime": "python3.12", **raw},
    }
    if details:
        row["raw_data"].update(
            {
                "boto3_config": {"FunctionName": name, "MemorySize": 128},
                "runtime": "python3.12",
                "memory_size": 128,
                "timeout": 3,
            }
        )
    return row


def _bucket(name="b1", account=ACC, region=REG, details=True):
    row = {
        "service": "S3",
        "resource_type": "Bucket",
        "type": "Bucket",
        "id": name,
        "resource_id": name,
        "arn": f"arn:aws:s3:::{name}",
        # without GetBucketLocation the row keeps the region it was listed in
        "region": region if details else "global",
        "account_id": None,
        "source_account_id": account,
        "source": "service-api",
        "tags": {"Name": name},
        "raw_data": {"Name": name},
    }
    if details:
        row["raw_data"]["boto3_region"] = region
    return row


def _stack(name="st", details=True, status="CREATE_COMPLETE"):
    row = {
        "service": "CLOUDFORMATION",
        "resource_type": "Stack",
        "type": "Stack",
        "id": name,
        "resource_id": name,
        "arn": f"arn:aws:cloudformation:{REG}:{ACC}:stack/{name}/1",
        "region": REG,
        "account_id": ACC,
        "source_account_id": ACC,
        "source": "service-api",
        "tags": {},
        "raw_data": {"StackName": name},
    }
    if details:
        row["raw_data"].update(
            {"boto3_stack": {"StackName": name}, "stack_status": status}
        )
    return row


def _widget(name="w1", details=True, colour="blue"):
    """A service InvenTag has no field list for: the fallback rule applies."""
    row = {
        "service": "WIDGETS",
        "resource_type": "Widget",
        "type": "Widget",
        "id": name,
        "resource_id": name,
        "arn": f"arn:aws:widgets:{REG}:{ACC}:widget/{name}",
        "region": REG,
        "account_id": ACC,
        "source_account_id": ACC,
        "source": "service-api",
        "tags": {},
        "raw_data": {"Name": name, "Colour": colour},
    }
    if details:
        row["raw_data"]["widget_detail"] = {"Size": 3}
    return row


def _detail(
    service,
    resource_type,
    outcome="denied",
    region=REG,
    account=ACC,
    operation="Get",
    code="AccessDenied",
):
    return {
        "account_id": account,
        "region": region,
        "source": "service-api-detail",
        "service": service,
        "resource_type": resource_type,
        "operation": operation,
        "outcome": outcome,
        "count": 1,
        "error_code": code,
        "seconds": 0.0,
    }


def _listing(service, outcome="ok", region=REG, account=ACC):
    return {
        "account_id": account,
        "region": region,
        "source": "service-api",
        "service": service,
        "resource_type": "",
        "operation": "List",
        "outcome": outcome,
        "count": 1,
        "error_code": "",
        "seconds": 0.0,
    }


def _unit(service, resource_type, outcome="denied", region=REG, account=ACC):
    """One entry of the snapshot key ``details_not_read``."""
    return {
        "account": account,
        "service": service,
        "region": region,
        "resource_type": resource_type,
        "operation": "Get",
        "outcome": outcome,
    }


CLEAN = [
    _listing("lambda"),
    _listing("s3", region="global"),
    _listing("cloudformation"),
    _detail("lambda", "Function", "ok", code=""),
]


def _run(entries):
    return {"coverage": entries, "regions": {ACC: [REG]}, "services": {ACC: []}}


def _detect(old, new, current=None, previous=None):
    kwargs = {}
    if previous is not None:
        kwargs["previous_details_not_read"] = previous
    return DeltaDetector().detect_changes(
        old,
        new,
        "old",
        "new",
        current_run=_run(current if current is not None else CLEAN),
        **kwargs,
    )


def _modified(report):
    return {
        c.resource_id: sorted(a.attribute_path for a in c.attribute_changes)
        for c in report.modified_resources
    }


def _frozen(report):
    report.timestamp = "t"
    for change in (
        report.added_resources
        + report.removed_resources
        + report.modified_resources
        + report.unchanged_resources
    ):
        change.timestamp = "t"
    data = json.dumps(asdict(report), default=str, sort_keys=True)
    changelog = ChangelogGenerator().generate_changelog(report, title="T")
    changelog.generation_timestamp = "t"
    changelog.state_comparison["comparison_timestamp"] = "t"
    return data, changelog.to_markdown()


# ------------------------------------------------------------- the defect


def test_a_detail_call_denied_in_this_run_does_not_make_the_function_modified():
    report = _detect(
        [_function()],
        [_function(details=False)],
        CLEAN + [_detail("lambda", "Function")],
    )
    assert _modified(report) == {}
    assert report.summary["modified_count"] == 0
    assert [c.resource_id for c in report.unchanged_resources] == ["fn"]
    assert "not_compared" not in report.change_statistics
    assert "not_compared_count" not in report.summary


def test_a_detail_call_denied_in_the_previous_run_does_not_make_the_function_modified():
    report = _detect(
        [_function(details=False)],
        [_function()],
        previous=[_unit("lambda", "Function")],
    )
    assert _modified(report) == {}
    assert [c.resource_id for c in report.unchanged_resources] == ["fn"]
    assert "not_compared" not in report.change_statistics
    assert "not_compared_count" not in report.summary


def test_the_s3_region_written_by_GetBucketLocation_is_not_compared():
    """Without the location the row keeps the region it was listed in."""
    entry = _detail("s3", "Bucket", region="global", operation="GetBucketLocation")
    report = _detect([_bucket(region=EU)], [_bucket(details=False)], CLEAN + [entry])
    assert _modified(report) == {}
    report = _detect(
        [_bucket(details=False)],
        [_bucket(region=EU)],
        previous=[_unit("s3", "Bucket", region="global")],
    )
    assert _modified(report) == {}


@pytest.mark.parametrize("outcome", ["denied", "throttled", "error", "timeout"])
def test_denied_throttled_error_and_timeout_are_treated_alike(outcome):
    current = _detect(
        [_function()],
        [_function(details=False)],
        CLEAN + [_detail("lambda", "Function", outcome)],
    )
    previous = _detect(
        [_function(details=False)],
        [_function()],
        previous=[_unit("lambda", "Function", outcome)],
    )
    assert _modified(current) == {} == _modified(previous)


def test_a_stopped_detail_call_counts_as_not_read():
    """Discovery records a detail call stopped at the time limit as "error"."""
    entry = _detail("lambda", "Function", "error", code="DetailCallsStopped")
    report = _detect([_function()], [_function(details=False)], CLEAN + [entry])
    assert _modified(report) == {}


# ------------------------------------------------- what stays compared


def test_other_changes_of_the_resource_stay():
    old = [_function()]
    new = [_function(details=False, Runtime="python3.13")]
    new[0]["tags"] = {"Name": "fn", "Env": "prod"}
    report = _detect(old, new, CLEAN + [_detail("lambda", "Function")])
    assert _modified(report) == {
        "fn": ["raw_data", "raw_data.Runtime", "tags", "tags.Env"]
    }
    assert "not_compared" not in report.change_statistics


def test_a_change_of_a_detail_field_is_found_when_both_runs_read_it():
    report = _detect([_stack()], [_stack(status="UPDATE_COMPLETE")])
    assert _modified(report) == {"st": ["raw_data", "raw_data.stack_status"]}


def test_other_units_are_compared():
    """Another region, another account, another type of the same service."""
    old = [
        _function("a"),
        _function("b", region=EU),
        _function("c", account=OTHER),
        _stack(),
    ]
    new = [
        _function("a", details=False),
        _function("b", region=EU, details=False),
        _function("c", account=OTHER, details=False),
        _stack(details=False),
    ]
    report = _detect(old, new, CLEAN + [_detail("lambda", "Function")])
    assert sorted(_modified(report)) == ["b", "c", "st"]


def test_a_unit_whose_detail_call_succeeded_is_compared():
    entry = _detail("lambda", "Function", "ok", code="")
    report = _detect([_function()], [_function(details=False)], CLEAN + [entry])
    assert sorted(_modified(report)) == ["fn"]
    assert "details_not_compared" not in report.change_statistics


def test_a_service_without_a_field_list_leaves_out_only_fields_the_failed_run_lacks():
    """Fallback for a detail call this version has no field list for."""
    old = [_widget()]
    new = [_widget(details=False, colour="red")]
    report = _detect(old, new, CLEAN + [_detail("widgets", "Widget")])
    assert _modified(report) == {"w1": ["raw_data", "raw_data.Colour"]}
    report = _detect(
        [_widget(details=False)], [_widget()], previous=[_unit("widgets", "Widget")]
    )
    assert _modified(report) == {}


def test_previous_units_of_a_skipped_account_are_ignored(tmp_path):
    """An account left out of the comparison is not named in the line."""
    report = _detect([], [], previous=[_unit("lambda", "Function", account=OTHER)])
    report2 = DeltaDetector().detect_changes(
        [],
        [],
        "old",
        "new",
        skip_accounts={OTHER: "it is new"},
        previous_details_not_read=[_unit("lambda", "Function", account=OTHER)],
    )
    assert "details_not_compared" in report.change_statistics
    assert "details_not_compared" not in report2.change_statistics


@pytest.mark.parametrize(
    "units", [None, [], "x", [1, None, {"account": ACC}, {"outcome": "denied"}]]
)
def test_a_missing_or_malformed_snapshot_key_changes_nothing(units):
    old, new = [_function(details=False)], [_function()]
    before = _frozen(_detect(old, new))
    after = _frozen(_detect(old, new, previous=units))
    assert after == before


# --------------------------------------------------------- the one line


def test_the_change_report_names_the_units_in_one_line():
    report = _detect(
        [_function(), _bucket(details=False)],
        [_function(details=False), _bucket()],
        CLEAN
        + [
            _detail("lambda", "Function", "throttled", code="ThrottlingException"),
            _detail("lambda", "Function", "denied"),
        ],
        previous=[_unit("s3", "Bucket", region="global")],
    )
    line = (
        f"Details not read, so the fields they add are not compared: lambda Function "
        f"in {REG} of account {ACC} (this run: throttled); s3 Bucket in global of "
        f"account {ACC} (previous run: denied)."
    )
    assert report.change_statistics["details_not_compared"] == line
    _, markdown = _frozen(report)
    assert f"- **details_not_compared:** {line}" in markdown
    changelog = ChangelogGenerator().generate_changelog(report, title="T")
    assert f"**Note:** {line}" in ChangelogGenerator()._format_as_markdown(changelog)


def test_the_line_is_there_when_no_resource_differs():
    """Both runs failed for the unit: nothing differs, the line still says it."""
    report = _detect(
        [_function(details=False)],
        [_function(details=False)],
        CLEAN + [_detail("lambda", "Function")],
        previous=[_unit("lambda", "Function")],
    )
    assert _modified(report) == {}
    assert "not_compared" not in report.change_statistics
    assert report.change_statistics["details_not_compared"].count("lambda") == 2


# ------------------------------------------------ clean runs: as before


def test_a_clean_pair_gives_the_same_report_as_before():
    old = [_function(), _bucket(), _stack(), _widget()]
    new = [
        _function(Runtime="python3.13"),
        _bucket(region=EU),
        _stack(status="UPDATE_COMPLETE"),
        _widget(colour="red"),
    ]
    without_detail_entries = _detect(old, new, [_listing("lambda")])
    clean = _detect(old, new, CLEAN, previous=[])
    assert _frozen(clean) == _frozen(without_detail_entries)
    assert "details_not_compared" not in clean.change_statistics
    assert "details_not_compared" not in _frozen(clean)[1]


# --------------------------------------------- the previous run's snapshot


def test_by_state_id_reads_the_previous_snapshot_key(tmp_path):
    sm = StateManager(state_dir=str(tmp_path))
    first = sm.save_state(
        [_function(details=False)],
        account_id=ACC,
        regions=[REG],
        tags={"details_not_read": [_unit("lambda", "Function")]},
        accounts_scanned=[ACC],
    )
    second = sm.save_state(
        [_function()], account_id=ACC, regions=[REG], accounts_scanned=[ACC]
    )
    report = DeltaDetector().detect_changes_by_state_id(
        sm, first, second, current_run=_run(CLEAN)
    )
    assert _modified(report) == {}
    assert "previous run: denied" in report.change_statistics["details_not_compared"]


# ------------------------------------- the whole CLI under moto, both orders
# The R5 identity of tests/unit/test_readonlyaccess_only.py: s3:Get* and lambda:Get* are
# denied, so GetBucketLocation and GetFunctionConfiguration fail; the full identity reads
# them. moto's Athena work group "primary" changes between any two runs (its clock).

from tests.unit.test_readonlyaccess_only import (  # noqa: E402,F401 (fixtures)
    MOTO_CLOCK_CHANGE,
    R5_ARGS,
    R5_DENY,
    _changes,
    aws,
    run_as,
)
from tests.policy_sim import read_only_access_actions  # noqa: E402

MOTO_ACCOUNT = "123456789012"
DETAIL_UNITS = (
    f"lambda Function in us-east-1 of account {MOTO_ACCOUNT}",
    f"s3 Bucket in us-east-1 of account {MOTO_ACCOUNT}",
)


def _write_details_not_read(run):
    """What the generator patch of the S1 report adds to the snapshot (emulated).

    ``metadata.tags.details_not_read``: one entry per failed detail unit of the run's
    ledger, written only when there is one.
    """
    rank = {"timeout": 0, "throttled": 1, "error": 2, "denied": 3}
    units = {}
    for e in run.ledger:
        if e.source != "service-api-detail" or e.outcome not in rank:
            continue
        key = (e.account_id or MOTO_ACCOUNT, e.service, e.region, e.resource_type)
        if key not in units or rank[e.outcome] < rank[units[key][1]]:
            units[key] = (e.operation, e.outcome)
    assert units, "the run had no failed detail call"
    path = run.snapshots()[-1]
    data = json.loads(path.read_text())
    data["metadata"].setdefault("tags", {})["details_not_read"] = [
        {
            "account": account,
            "service": service,
            "region": region,
            "resource_type": resource_type,
            "operation": operation,
            "outcome": outcome,
        }
        for (account, service, region, resource_type), (operation, outcome) in sorted(
            units.items()
        )
    ]
    path.write_text(json.dumps(data))


def _two_cli_runs(aws, run_as, first_deny, second_deny, emulate_patch=False):
    import time

    args = R5_ARGS[:2]
    first = run_as(read_only_access_actions(), *args, deny=first_deny)
    if emulate_patch:
        _write_details_not_read(first)
    time.sleep(1.1)  # state files are named by the second
    second = run_as(read_only_access_actions(), *args, deny=second_deny)
    for run in (first, second):
        run.sim.assert_all_mapped()
        assert run.code == 0, run.text
    return _changes(second)


def test_cli_full_run_then_details_denied_lists_no_false_modified(aws, run_as):
    report = _two_cli_runs(aws, run_as, (), R5_DENY)
    assert report["changes"] == MOTO_CLOCK_CHANGE, report["text"]
    for unit in DETAIL_UNITS:
        assert f"{unit} (this run: denied)" in report["text"]


def test_cli_details_denied_then_full_run_lists_no_false_modified(aws, run_as):
    """The other order, with the snapshot key the generator patch writes."""
    report = _two_cli_runs(aws, run_as, R5_DENY, (), emulate_patch=True)
    assert report["changes"] == MOTO_CLOCK_CHANGE, report["text"]
    for unit in DETAIL_UNITS:
        assert f"{unit} (previous run: denied)" in report["text"]


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "A-78, needs from another order: the generator does not yet write the snapshot key "
        "details_not_read (exact patch for inventag/core/cloud_bom_generator.py in "
        "reports/v14-s1-delta.md). Remove this mark when the patch is merged."
    ),
)
def test_cli_details_denied_then_full_run_without_the_emulated_key(aws, run_as):
    report = _two_cli_runs(aws, run_as, R5_DENY, ())
    assert report["changes"] == MOTO_CLOCK_CHANGE, report["text"]


def test_cli_two_clean_runs_list_only_the_moto_clock_change(aws, run_as):
    report = _two_cli_runs(aws, run_as, (), ())
    assert report["changes"] == MOTO_CLOCK_CHANGE, report["text"]
    assert "details_not_compared" not in report["text"]
