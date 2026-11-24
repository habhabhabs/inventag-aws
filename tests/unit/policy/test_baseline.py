"""Baseline checks (spec 2.3.1, package P2): ``inventag.policy.baseline``."""

import copy
import datetime as dt
import json
from pathlib import Path

import pytest

from inventag.policy import engine, loader
from inventag.policy.schema import PolicyError

GOLDEN = Path(__file__).resolve().parent / "golden"
NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)
A = "111111111111"


def snap(name):
    return json.loads((GOLDEN / name).read_text())


def run(tmp_path, spec, baseline="s0.json", snapshot=None, **options):
    path = tmp_path / "p.yaml"
    path.write_text(
        "format_version: 1\nkind: policy\nname: p\nspec: " + json.dumps(spec) + "\n"
    )
    loaded = loader.load([path], root=tmp_path)
    return engine.evaluate(
        snapshot if snapshot is not None else snap("s1.json"),
        loaded.policies,
        baseline=snap(baseline) if isinstance(baseline, str) else baseline,
        now=NOW,
        include_pass=True,
        **options,
    )


def base(change, **extra):
    return {"type": "baseline", "change": change, **extra}


def policy(check, services=("S3", "EC2", "LAMBDA", "RDS"), **extra):
    return {
        "id": "DRF-9",
        "severity": "medium",
        "resource": {"services": list(services)},
        "check": check,
        **extra,
    }


def table(result):
    out = {}
    for f in result["findings"]:
        key = f["resource"].rsplit(":", 1)[-1].rsplit("/", 1)[-1]
        out[key + (" (baseline)" if f.get("from") == "baseline" else "")] = f["result"]
    return out


def test_added_and_removed_use_the_baseline_identity(tmp_path):
    r = run(tmp_path, policy([base(["added", "removed"])], ["S3", "EC2", "LAMBDA"]))
    assert table(r) == {
        "public-site-assets": "fail",
        "i-0bbb": "fail",
        "i-0ccc": "fail",
        "old-exports (baseline)": "fail",
        "logs-prod": "pass",
        "i-0aaa": "pass",
        "fn-report": "pass",
    }


def test_a_removed_finding_carries_the_baseline_row_and_from_baseline(tmp_path):
    r = run(tmp_path, policy([base(["removed"])], ["S3"]))
    (f,) = [f for f in r["findings"] if f["result"] == "fail"]
    assert f["from"] == "baseline"
    assert f["resource"] == "arn:aws:s3:::old-exports"
    assert (f["account"], f["region"], f["service"]) == (A, "us-east-1", "S3")
    assert f["details"] == [{"check": 0, "type": "baseline", "problem": "removed"}]


def test_a_removed_row_of_an_unread_unit_is_not_reported(tmp_path):
    r = run(tmp_path, policy([base(["removed"])], ["LAMBDA"]))
    assert [f for f in r["findings"] if f["result"] == "fail"] == []
    assert [u["service"] for u in r["not_evaluated_units"]] == ["lambda"]


def test_removed_only_when_the_policy_selects_the_baseline_row(tmp_path):
    r = run(tmp_path, policy([base(["removed"])], ["EC2"]))
    assert "old-exports (baseline)" not in table(r)


def test_removed_follows_the_resource_filters_on_the_baseline_row(tmp_path):
    spec = policy([base(["removed"])], ["S3"])
    spec["resource"]["filters"] = [
        {"type": "value", "key": "resource_name", "value": "logs-prod"}
    ]
    assert "old-exports (baseline)" not in table(run(tmp_path, spec))
    spec["resource"]["filters"][0]["value"] = "old-exports"
    assert table(run(tmp_path, spec))["old-exports (baseline)"] == "fail"


def test_no_removed_finding_unless_removed_is_listed(tmp_path):
    r = run(tmp_path, policy([base(["added"])], ["S3"]))
    assert table(r) == {"public-site-assets": "fail", "logs-prod": "pass"}


def test_modified_without_attributes_uses_the_change_report(tmp_path):
    r = run(tmp_path, policy([base(["modified"])], ["RDS"]))
    assert table(r) == {"db-orders": "fail", "db-audit": "pass"}


def test_modified_with_attributes_counts_only_those_keys(tmp_path):
    other = policy([base(["modified"], attributes=["raw_data.AllocatedStorage"])])
    assert (
        table(
            run(
                tmp_path,
                other,
            )
        )["db-orders"]
        == "pass"
    )
    hit = policy([base(["modified"], attributes=["raw_data.StorageEncrypted"])])
    assert table(run(tmp_path, hit))["db-orders"] == "fail"


def test_modified_details_name_the_key_and_not_the_values(tmp_path):
    spec = policy(
        [base(["modified"], attributes=["raw_data.StorageEncrypted", "tags.Owner"])],
        ["RDS"],
    )
    r = run(tmp_path, spec)
    (f,) = [f for f in r["findings"] if f["result"] == "fail"]
    assert f["details"] == [
        {
            "check": 0,
            "type": "baseline",
            "key": "raw_data.StorageEncrypted",
            "problem": "modified",
        }
    ]
    assert "true" not in json.dumps(f).lower().replace("modified", "")


def test_a_row_that_no_listed_change_applies_to_passes(tmp_path):
    r = run(tmp_path, policy([base(["removed"])], ["RDS"]))
    assert table(r) == {"db-orders": "pass", "db-audit": "pass"}


def test_mixed_with_other_checks_keeps_the_check_index_and_ands_the_verdicts(tmp_path):
    spec = policy(
        [
            {"type": "value", "key": "region", "value": "us-east-1"},
            base(["added", "removed"]),
        ],
        ["S3"],
    )
    r = run(tmp_path, spec)
    assert table(r) == {
        "logs-prod": "pass",
        "public-site-assets": "fail",
        "old-exports (baseline)": "fail",
    }
    (added,) = [f for f in r["findings"] if f["resource"].endswith("assets")]
    assert [(d["check"], d["problem"]) for d in added["details"]] == [
        (0, "condition not met"),
        (1, "added"),
    ]
    (gone,) = [f for f in r["findings"] if f.get("from") == "baseline"]
    assert [d["check"] for d in gone["details"]] == [1]  # only the baseline entry


def test_a_failed_other_check_fails_even_when_the_baseline_entry_is_true(tmp_path):
    spec = policy(
        [{"type": "value", "key": "region", "value": "eu-west-1"}, base(["added"])],
        ["S3"],
    )
    r = run(tmp_path, spec)
    assert table(r) == {"logs-prod": "fail", "public-site-assets": "fail"}
    (logs,) = [f for f in r["findings"] if f["resource"].endswith("logs-prod")]
    assert [d["check"] for d in logs["details"]] == [0]


def test_counts_include_the_removed_findings(tmp_path):
    r = run(tmp_path, policy([base(["added", "removed"])], ["S3", "EC2", "LAMBDA"]))
    (p,) = r["policies"]
    assert (p["counts"]["fail"], p["counts"]["pass"]) == (4, 3)
    assert r["summary"]["by_result"]["fail"] == 4
    assert r["summary"]["fail_by_severity"]["medium"] == 4


def test_an_identity_only_row_is_compared_by_identity(tmp_path):
    r = run(tmp_path, policy([base(["added"])], ["SQS"]))
    assert table(r) == {"orders-dlq": "pass"}


def test_a_row_without_a_partner_is_added_even_when_the_account_differs(tmp_path):
    changed = snap("s0.json")
    for row in changed["resources"]:
        if row["resource_id"] == "i-0aaa":
            row["arn"] = row["arn"].replace(A, "999999999999")
    r = run(tmp_path, policy([base(["added", "removed"])], ["EC2"]), baseline=changed)
    assert table(r)["i-0aaa"] == "fail"
    assert table(r)["i-0aaa (baseline)"] == "fail"


def test_the_inputs_are_not_changed(tmp_path):
    s1, s0 = snap("s1.json"), snap("s0.json")
    before = copy.deepcopy((s1, s0))
    run(tmp_path, policy([base(["added", "removed", "modified"])]), s0, s1)
    assert (s1, s0) == before


def test_the_result_is_byte_equal_on_a_second_run(tmp_path):
    spec = policy([base(["added", "removed", "modified"])])
    assert engine.dumps(run(tmp_path, spec)) == engine.dumps(run(tmp_path, spec))


def test_a_baseline_entry_inside_and_or_not_is_refused(tmp_path):
    spec = policy([{"not": [base(["added"])]}], ["S3"])
    with pytest.raises(PolicyError) as caught:
        run(tmp_path, spec)
    assert "top-level" in str(caught.value)


def test_a_removed_row_whose_selection_is_unknown_is_not_evaluated(tmp_path):
    spec = policy([base(["removed"])], ["S3"])
    spec["resource"]["filters"] = [
        {"type": "value", "key": "raw_data.Missing.Key", "value": "x"}
    ]
    old = snap("s0.json")
    for row in old["resources"]:
        if row["resource_id"] == "old-exports":
            row["detail_level"] = "identity"
            del row["raw_data"]
    r = run(tmp_path, spec, baseline=old)
    gone = [f for f in r["findings"] if f.get("from") == "baseline"]
    assert [(f["result"], f["reason"]) for f in gone] == [
        ("not_evaluated", "identity_only")
    ]
