"""Each FinOps check against a moto scan: one resource that fails and one that
passes, and the field the check reads is on the row the scan made."""

from datetime import timedelta

import pytest

from inventag.finops import checks

pytestmark = pytest.mark.e2e


def findings(scan, policy):
    return [
        f for f in scan.results["finops_checks"]["findings"] if f["policy"] == policy
    ]


def listed(scan, policy):
    return {f["resource"]: f for f in findings(scan, policy)}


def summary(scan, policy):
    return next(
        s for s in scan.results["finops_checks"]["summary"] if s["policy"] == policy
    )


def row(scan, resource_id):
    return next(r for r in scan.rows if r["resource_id"] == resource_id)


def test_the_run_with_the_flag_exits_0(finops_scan):
    assert finops_scan.code == 0, finops_scan.text


def test_fin_001_unattached_volume(finops_scan):
    s, ids = finops_scan, finops_scan.ids
    assert row(s, ids["loose"])["raw_data"]["State"] == "available"
    assert row(s, ids["attached"])["raw_data"]["State"] == "in-use"
    found = listed(s, "FIN-001")
    assert found[ids["loose"]]["result"] == "fail"
    assert found[ids["loose"]]["message"] == "no attachment"
    assert ids["attached"] not in found
    assert summary(s, "FIN-001")["pass"] >= 1


def test_fin_002_unassociated_address(finops_scan):
    s, ids = finops_scan, finops_scan.ids
    assert row(s, ids["associated"])["raw_data"]["AssociationId"]
    assert not row(s, ids["free"])["raw_data"].get("AssociationId")
    found = listed(s, "FIN-002")
    assert found[ids["free"]]["result"] == "fail"
    assert found[ids["free"]]["message"] == "no association"
    assert ids["associated"] not in found
    assert summary(s, "FIN-002")["pass"] == 1


def test_fin_003_snapshot_start_time_is_on_the_row_and_a_new_one_passes(finops_scan):
    s, ids = finops_scan, finops_scan.ids
    assert row(s, ids["snapshot"])["raw_data"]["StartTime"]
    assert ids["snapshot"] not in listed(s, "FIN-003")
    assert summary(s, "FIN-003") == {
        "policy": "FIN-003",
        "check": checks.CHECKS["FIN-003"],
        "fail": 0,
        "not_evaluated": 0,
        "pass": 1,
    }


def test_fin_003_the_same_moto_row_fails_91_days_later(finops_scan):
    s, ids = finops_scan, finops_scan.ids
    snap = row(s, ids["snapshot"])
    started = checks.parse_time(snap["raw_data"]["StartTime"])
    result = checks.run_checks([snap], [], started + timedelta(days=91))
    (found,) = [f for f in result["findings"] if f["policy"] == "FIN-003"]
    assert found["result"] == "fail"
    assert found["resource"] == ids["snapshot"]
    assert found["message"] == f"started {started:%Y-%m-%d}"


def test_fin_004_stopped_instance(finops_scan):
    s, ids = finops_scan, finops_scan.ids
    assert row(s, ids["stopped"])["raw_data"]["State"]["Name"] == "stopped"
    assert row(s, ids["running"])["raw_data"]["State"]["Name"] == "running"
    found = listed(s, "FIN-004")
    assert found[ids["stopped"]]["result"] == "fail"
    assert found[ids["stopped"]]["message"] == "state stopped"
    assert ids["running"] not in found
    assert summary(s, "FIN-004")["pass"] == 1


def test_fin_005_load_balancer_v2_that_no_target_group_names(finops_scan):
    s, ids = finops_scan, finops_scan.ids
    group = row(s, "finops-tg")
    assert group["raw_data"]["LoadBalancerArns"] == [ids["used_lb"]]
    assert row(s, "finops-bare")["raw_data"]["LoadBalancerArn"] == ids["bare_lb"]
    found = listed(s, "FIN-005")
    assert found["finops-bare"]["result"] == "fail"
    assert found["finops-bare"]["message"] == "no target group names it"
    assert "finops-used" not in found


def test_fin_005_classic_load_balancer_without_an_instance(finops_scan):
    s = finops_scan
    assert row(s, "finops-classic-bare")["raw_data"]["Instances"] == []
    assert row(s, "finops-classic-used")["raw_data"]["Instances"]
    found = listed(s, "FIN-005")
    assert found["finops-classic-bare"]["result"] == "fail"
    assert found["finops-classic-bare"]["message"] == "lists no instance"
    assert "finops-classic-used" not in found
    assert summary(s, "FIN-005")["pass"] == 2


def test_fin_006_missing_cost_allocation_tags(finops_scan):
    s, ids = finops_scan, finops_scan.ids
    found = listed(s, "FIN-006")
    assert found[ids["loose"]]["result"] == "fail"
    assert (
        found[ids["loose"]]["message"]
        == "missing: CostCenter, Owner, Project, Environment"
    )
    for tagged in (ids["attached"], ids["running"], ids["snapshot"]):
        assert tagged not in found
    assert summary(s, "FIN-006")["pass"] >= 4


def test_no_finding_is_not_evaluated_on_a_complete_moto_scan(finops_scan):
    found = finops_scan.results["finops_checks"]["findings"]
    assert [f for f in found if f["result"] == "not_evaluated"] == []


def test_every_finding_names_the_account_and_region(finops_scan):
    for f in finops_scan.results["finops_checks"]["findings"]:
        assert f["account"] == "123456789012"
        assert f["region"] == "us-east-1"
