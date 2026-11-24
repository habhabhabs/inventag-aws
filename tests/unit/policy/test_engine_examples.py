"""The worked examples of v15-policy-spec.md (section 7 and 9.5), run through the
loader and the engine on the fixtures in ``golden/``.

Examples 16 to 20 need waivers and the baseline (package P2); they are marked
``xfail(strict=True)`` until P2's modules exist, so a pass is noticed."""

import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

from inventag.policy import engine, loader

GOLDEN = Path(__file__).resolve().parent / "golden"
NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)

A, B = "111111111111", "222222222222"
SHORT = {
    "arn:aws:s3:::logs-prod": "R1",
    "arn:aws:s3:::public-site-assets": "R2",
    f"arn:aws:ec2:us-east-1:{A}:instance/i-0aaa": "R3",
    f"arn:aws:ec2:us-east-1:{A}:instance/i-0bbb": "R4",
    f"arn:aws:rds:eu-west-1:{A}:db:db-orders": "R5",
    f"arn:aws:rds:eu-west-1:{A}:db:db-audit": "R6",
    f"arn:aws:lambda:us-east-1:{A}:function:fn-report": "R7",
    f"arn:aws:sqs:us-east-1:{A}:orders-dlq": "R8",
    f"arn:aws:ec2:ap-southeast-1:{B}:instance/i-0ccc": "R9",
    f"arn:aws:ec2:ap-southeast-3:{B}:security-group/sg-0ddd": "R10",
    "arn:aws:s3:::old-exports": "R11",
    f"arn:aws:lambda:eu-west-1:{A}:function:fn-eu": "R12",
}
ELB = f"arn:aws:elasticloadbalancing:us-east-1:{A}:"
SHORT.update(
    {
        ELB + "loadbalancer/app/web/1": "L1",
        ELB + "loadbalancer/app/old/2": "L2",
        ELB + "loadbalancer/classic-a": "L3",
        ELB + "loadbalancer/classic-b": "L4",
        ELB + "targetgroup/tg-web/9": "T1",
    }
)
U1 = {
    "account": A,
    "service": "lambda",
    "region": "eu-west-1",
    "reason": "listing_not_read",
    "outcome": "throttled",
}

needs_p2 = pytest.mark.xfail(
    importlib.util.find_spec("inventag.policy.waivers") is None
    or importlib.util.find_spec("inventag.policy.baseline") is None,
    reason="waivers and baseline are package P2 (inventag/policy/waivers.py, baseline.py)",
    strict=True,
)


def snapshot(name="s1.json"):
    return json.loads((GOLDEN / name).read_text())


def run(*policy_files, snap=None, now=NOW, waivers=(), baseline=None, **options):
    loaded = loader.load([GOLDEN / "policies" / f for f in policy_files], root=GOLDEN)
    waiver_list = loader.load_waivers([GOLDEN / "waivers" / w for w in waivers], now)
    return engine.evaluate(
        snap if snap is not None else snapshot(),
        loaded.policies,
        waivers=waiver_list,
        baseline=baseline,
        now=now,
        include_pass=True,
        **options,
    )


def table(result, policy=None):
    """{short: result or (result, reason)} of the findings (passes included)."""
    found = {}
    for f in result["findings"]:
        if policy and f["policy"] != policy:
            continue
        key = SHORT.get(f["resource"], f["resource"])
        if f.get("from") == "baseline":
            key += " (baseline)"
        found[key] = (f["result"], f["reason"]) if "reason" in f else f["result"]
    return found


def out_of_scope(result, policy):
    (p,) = [p for p in result["policies"] if p["id"] == policy]
    return p["counts"]["out_of_scope"]


def units(result):
    return [
        {k: v for k, v in u.items() if k != "policy"}
        for u in result["not_evaluated_units"]
    ]


def code(result, fail_on=None, nev=False):
    return engine.exit_code(result, fail_on=fail_on, fail_on_not_evaluated=nev)


def details(result, short):
    (f,) = [f for f in result["findings"] if SHORT.get(f["resource"]) == short]
    return f.get("details")


# ----------------------------------------------------------------- 1 to 15
def test_01_boolean_value():
    r = run("ex01.yaml")
    assert table(r) == {"R5": "fail", "R6": "pass"}
    assert out_of_scope(r, "RDS-001") == 8
    assert units(r) == []
    assert code(r, "high") == 7


def test_02_filter_selects_and_absent():
    r = run("ex02.yaml")
    assert table(r) == {"R3": "fail", "R9": "pass"}
    assert out_of_scope(r, "EC2-001") == 8  # R4 is stopped
    assert code(r, "high") == 7


def test_03_identity_only_row_and_raw_data():
    r = run("ex03.yaml")
    assert table(r) == {"R8": ("not_evaluated", "identity_only")}
    assert code(r, "low", nev=True) == 8
    assert code(r, "low") == 0


def test_04_identity_only_row_and_tags():
    r = run("ex04.yaml")
    assert table(r) == {"R8": "pass"}
    assert code(r, "low") == 0


def test_05_required_tags():
    r = run("ex05.yaml")
    assert table(r) == {
        "R1": "pass",
        "R2": "pass",
        "R3": "pass",
        "R5": "pass",
        "R6": "pass",
        "R4": "fail",
        "R7": "fail",
        "R9": ("not_evaluated", "tags_not_read"),
    }
    assert details(r, "R4") == [
        {"check": 0, "type": "required-tags", "key": "Owner", "problem": "missing tag"},
        {
            "check": 0,
            "type": "required-tags",
            "key": "Environment",
            "problem": "missing tag",
        },
    ]
    assert details(r, "R7") == [
        {
            "check": 0,
            "type": "required-tags",
            "key": "Environment",
            "problem": "missing tag",
        }
    ]
    assert units(r) == [U1]
    assert out_of_scope(r, "TAG-002") == 2  # R8, R10
    assert code(r, "medium") == 7
    assert code(r, "medium", nev=True) == 8


def test_06_tag_pattern():
    r = run("ex06.yaml")
    assert table(r) == {"R5": "pass", "R6": "fail"}
    assert details(r, "R6") == [
        {
            "check": 0,
            "type": "required-tags",
            "key": "CostCenter",
            "problem": "CostCenter: '1234' does not match CC-\\d{4}",
        }
    ]
    assert code(r, "low") == 7


def test_07_allowed_regions():
    r = run("ex07.yaml")
    assert table(r) == {"R3": "pass", "R4": "pass", "R9": "fail", "R10": "fail"}
    assert details(r, "R10") == [
        {"check": 0, "type": "allowed-regions", "problem": "region not allowed"}
    ]
    assert code(r, "critical") == 0


def test_08_name_pattern_on_raw_data_hides_the_value():
    r = run("ex08.yaml")
    assert table(r) == {"R10": "fail"}
    assert details(r, "R10") == [
        {
            "check": 0,
            "type": "name-pattern",
            "key": "raw_data.GroupName",
            "problem": "pattern not matched",
        }
    ]
    assert "launch-wizard" not in json.dumps(r["findings"])
    assert code(r, "medium") == 7


def test_09_or_true_wins_over_unknown():
    r = run("ex09.yaml")
    assert table(r) == {"R3": "pass", "R4": "fail", "R9": "pass"}
    assert code(r, "low", nev=True) == 7


def test_10_and_unknown_stays_false_wins():
    r = run("ex10.yaml")
    assert table(r) == {
        "R3": "pass",
        "R4": "fail",
        "R9": ("not_evaluated", "tags_not_read"),
    }
    assert code(r, "low", nev=True) == 8


def test_11_age_in_days():
    r = run("ex11.yaml")
    assert table(r) == {"R3": "fail", "R4": "pass", "R9": "pass"}
    assert code(r, "info") == 7


def test_12_a_masked_value_is_present():
    r = run("ex12.yaml")
    assert table(r) == {"R7": "fail"}
    assert details(r, "R7") == [
        {
            "check": 0,
            "type": "value",
            "key": "raw_data.Environment.Variables.API_KEY",
            "problem": "condition not met",
        }
    ]
    assert units(r) == []
    shown = run("ex12.yaml", show_values=True)
    assert details(shown, "R7")[0]["value"] == "***REDACTED***"
    assert code(r, "high") == 7


def test_13_number_comparison():
    r = run("ex13.yaml")
    assert table(r) == {"R5": "pass", "R6": "fail"}
    assert code(r, "low") == 7


def test_14_regex_ignores_case_and_anchors_at_the_start():
    r = run("ex14.yaml")
    assert table(r) == {"R1": "pass", "R2": "fail"}
    assert code(r, "low") == 7


def test_15_regex_case():
    r = run("ex15.yaml")
    assert table(r) == {"R1": "fail", "R2": "fail"}
    assert code(r, "low") == 7


# ----------------------------------------------------------------- 16 to 20
@needs_p2
def test_16_a_valid_waiver():
    r = run("ex01.yaml", waivers=["w16.yaml"])
    assert table(r) == {"R5": "waived", "R6": "pass"}
    assert r["unused_waivers"] == []
    assert code(r, "high") == 0


@needs_p2
@pytest.mark.parametrize(
    "file, now, expected, exit_code",
    [
        ("w17-2026-11-19.yaml", NOW, "fail", 7),
        ("w17-2026-11-20.yaml", NOW, "waived", 0),
        ("w17-2026-11-20.yaml", NOW + dt.timedelta(days=1), "fail", 7),
    ],
)
def test_17_expiry_and_the_day_border(file, now, expected, exit_code):
    r = run("ex01.yaml", waivers=[file], now=now)
    assert table(r)["R5"] == expected
    assert code(r, "high") == exit_code


@needs_p2
def test_18_a_glob_waiver_that_matches_nothing():
    r = run("ex02.yaml", waivers=["w18.yaml"])
    assert table(r) == {"R3": "fail", "R9": "pass"}
    assert [w["why"] for w in r["unused_waivers"]] == ["no match"]
    assert [code(r, x) for x in ("critical", "high", "medium", None)] == [0, 7, 7, 0]


@needs_p2
def test_19_baseline_added_and_removed():
    r = run("ex19.yaml", baseline=snapshot("s0.json"))
    assert table(r) == {
        "R2": "fail",
        "R4": "fail",
        "R9": "fail",
        "R11 (baseline)": "fail",
        "R1": "pass",
        "R3": "pass",
        "R7": "pass",
    }
    assert units(r) == [U1]
    assert code(r, "medium") == 7
    assert code(r, "medium", nev=True) == 8


@needs_p2
def test_20_baseline_modified_no_baseline_and_8_over_7():
    r = run("ex20.yaml", baseline=snapshot("s0.json"))
    assert table(r) == {"R5": "fail", "R6": "pass"}
    assert code(r, "critical") == 7
    r = run("ex20.yaml")
    assert r["findings"] == []
    assert r["not_evaluated_policies"] == [
        {"policy": "DRF-002", "reason": "no_baseline"}
    ]
    assert code(r, "critical") == 0
    assert code(r, "critical", nev=True) == 8
    r = run("ex01.yaml", "ex03.yaml")
    assert table(r) == {
        "R5": "fail",
        "R6": "pass",
        "R8": ("not_evaluated", "identity_only"),
    }
    assert code(r, "high", nev=True) == 8


def test_20b_no_baseline_is_a_not_evaluated_policy():
    # The engine's own part of example 20 (b) and (c): no row finding.
    r = run("ex20.yaml")
    assert r["findings"] == []
    assert r["not_evaluated_policies"] == [
        {"policy": "DRF-002", "reason": "no_baseline"}
    ]
    assert code(r, "critical") == 0
    assert code(r, "critical", nev=True) == 8


def test_20d_two_policies_8_over_7():
    r = run("ex01.yaml", "ex03.yaml")
    assert table(r) == {
        "R5": "fail",
        "R6": "pass",
        "R8": ("not_evaluated", "identity_only"),
    }
    assert code(r, "high", nev=True) == 8


# ----------------------------------------------------------------- 21 to 24
def s2(edit=None):
    data = snapshot("s2.json")
    if edit:
        edit(data)
    return data


def rows_of(data):
    return {SHORT[r["arn"]]: r for r in data["resources"]}


def test_21_related_pass_and_fail():
    r = run("fin-005.yaml", snap=s2())
    assert table(r) == {"L1": "pass", "L2": "fail", "L3": "fail", "L4": "pass"}
    assert details(r, "L2") == [
        {"check": 0, "type": "related", "problem": "no related row names it"}
    ]
    assert details(r, "L3") == [
        {
            "check": 0,
            "type": "value",
            "key": "raw_data.Instances",
            "problem": "condition not met",
        }
    ]
    assert out_of_scope(r, "FIN-005") == 1  # T1
    assert units(r) == []
    assert code(r, "low") == 7


def test_22_the_target_group_listing_was_not_read():
    def edit(data):
        data["metadata"]["tags"]["units_not_read"] = [
            {
                "account": A,
                "service": "elbv2",
                "region": "us-east-1",
                "source": "service-api",
                "outcome": "throttled",
            }
        ]
        data["resources"] = [
            r for r in data["resources"] if "targetgroup" not in r["arn"]
        ]

    r = run("fin-005.yaml", snap=s2(edit))
    assert table(r) == {
        "L1": ("not_evaluated", "listing_not_read"),
        "L2": ("not_evaluated", "listing_not_read"),
        "L3": "fail",
        "L4": "pass",
    }
    assert r["not_evaluated_units"] == [
        {
            "policy": "FIN-005",
            "account": A,
            "service": "elbv2",
            "region": "us-east-1",
            "reason": "listing_not_read",
            "outcome": "throttled",
        }
    ]
    assert code(r, "low") == 7
    assert code(r, "low", nev=True) == 8


def test_23_a_target_group_row_without_its_list():
    def edit(data):
        rows_of(data)["T1"]["raw_data"] = {}

    r = run("fin-005.yaml", snap=s2(edit))
    assert table(r) == {
        "L1": ("not_evaluated", "field_missing"),
        "L2": ("not_evaluated", "field_missing"),
        "L3": "fail",
        "L4": "pass",
    }
    assert code(r, "low") == 7


def test_24a_rows_that_lack_their_own_field():
    def edit(data):
        rows = rows_of(data)
        rows["L2"]["raw_data"] = {}
        rows["L3"]["raw_data"] = {}

    r = run("fin-005.yaml", snap=s2(edit))
    assert table(r) == {
        "L1": "pass",
        "L2": ("not_evaluated", "field_missing"),
        "L3": ("not_evaluated", "field_missing"),
        "L4": "pass",
    }
    assert code(r, "low") == 0
    assert code(r, "low", nev=True) == 8


def test_24b_age_with_a_time():
    def snap_row(rid, raw):
        return {
            "service": "EC2",
            "resource_type": "Snapshot",
            "resource_id": rid,
            "resource_name": rid,
            "arn": f"arn:aws:ec2:us-east-1:{A}:snapshot/{rid}",
            "region": "us-east-1",
            "source_account_id": A,
            "detail_level": "full",
            "tags": {},
            "raw_data": raw,
        }

    data = s2()
    data["resources"] = [
        snap_row("snap-a", {"StartTime": "2026-08-22T00:00:00+00:00"}),
        snap_row("snap-b", {"StartTime": "2026-08-21T23:00:00+00:00"}),
        snap_row("snap-c", {}),
    ]
    r = run("fin-003.yaml", snap=data)
    found = {f["resource"].rsplit("/", 1)[1]: f for f in r["findings"]}
    assert found["snap-a"]["result"] == "pass"
    assert found["snap-b"]["result"] == "fail"
    assert (found["snap-c"]["result"], found["snap-c"]["reason"]) == (
        "not_evaluated",
        "field_missing",
    )
    assert code(r, "low") == 7


# ----------------------------------------------------------------- shape
def test_passes_are_listed_only_with_include_pass():
    loaded = loader.load([GOLDEN / "policies" / "ex01.yaml"], root=GOLDEN)
    r = engine.evaluate(snapshot(), loaded.policies, now=NOW)
    assert [f["result"] for f in r["findings"]] == ["fail"]
    assert r["summary"]["by_result"] == {
        "pass": 1,
        "fail": 1,
        "waived": 0,
        "not_evaluated": 0,
        "out_of_scope": 8,
    }


def test_the_engine_does_not_change_its_input():
    data = snapshot()
    before = copy.deepcopy(data)
    run("ex05.yaml", "ex09.yaml", snap=data)
    assert data == before
