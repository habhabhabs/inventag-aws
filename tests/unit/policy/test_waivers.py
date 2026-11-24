"""Waivers (spec 2.5, package P2): ``inventag.policy.waivers.apply``."""

import copy
import datetime as dt

import pytest

from inventag.policy import model, waivers

NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)
A = "111111111111"
ARN = f"arn:aws:rds:eu-west-1:{A}:db:db-orders"


def apply(findings, ws, now, known_policies=("RDS-001", "RDS-002")):
    return waivers.apply(findings, ws, now, known_policies)


def finding(policy="RDS-001", result="fail", resource=ARN, account=A, **extra):
    return {
        "policy": policy,
        "result": result,
        "severity": "high",
        "account": account,
        "region": "eu-west-1",
        "service": "RDS",
        "resource_type": "DBInstance",
        "resource": resource,
        "name": "db-orders",
        "message": f"{policy}: x",
        **extra,
    }


def waiver(expires="2026-12-31", policy="RDS-001", resource=ARN, **extra):
    return model.Waiver(
        policy=policy,
        resource=resource,
        reason="A reason that is long enough.",
        approved_by="platform-lead",
        expires=dt.date.fromisoformat(expires),
        file=extra.pop("file", "w.yaml"),
        **extra,
    )


def test_a_valid_waiver_turns_fail_into_waived_and_carries_the_waiver():
    found, unused = apply([finding()], [waiver()], NOW)
    assert found[0]["result"] == "waived"
    assert found[0]["waiver"] == {
        "reason": "A reason that is long enough.",
        "approved_by": "platform-lead",
        "expires": "2026-12-31",
        "file": "w.yaml",
    }
    assert "waiver_expired" not in found[0]
    assert unused == []


def test_pass_and_not_evaluated_are_never_touched():
    rows = [
        finding(result="pass", resource="r1"),
        finding(result="not_evaluated", resource="r2", reason="identity_only"),
    ]
    found, unused = apply(rows, [waiver(resource="*r*")], NOW)
    assert found == rows
    assert [u["why"] for u in unused] == ["no match"]


def test_input_is_not_changed():
    rows = [finding()]
    before = copy.deepcopy(rows)
    apply(rows, [waiver()], NOW)
    assert rows == before


def test_expires_is_valid_through_the_end_of_that_utc_day():
    last = dt.datetime(2026, 11, 20, 23, 59, 59, tzinfo=dt.timezone.utc)
    next_day = dt.datetime(2026, 11, 21, 0, 0, 0, tzinfo=dt.timezone.utc)
    found, _ = apply([finding()], [waiver("2026-11-20")], last)
    assert found[0]["result"] == "waived"
    found, unused = apply([finding()], [waiver("2026-11-20")], next_day)
    assert found[0]["result"] == "fail"
    assert found[0]["waiver_expired"] == "2026-11-20"
    assert [(u["why"], u["expires"]) for u in unused] == [("expired", "2026-11-20")]


def test_the_day_is_the_utc_day_of_now():
    # 23:30 on 20 Nov in UTC-5 is 04:30 on 21 Nov in UTC: expired.
    west = dt.timezone(dt.timedelta(hours=-5))
    now = dt.datetime(2026, 11, 20, 23, 30, tzinfo=west)
    found, _ = apply([finding()], [waiver("2026-11-20")], now)
    assert found[0]["result"] == "fail"


def test_expired_waiver_leaves_fail_and_sets_waiver_expired():
    found, unused = apply([finding()], [waiver("2026-11-19")], NOW)
    assert found[0]["result"] == "fail"
    assert found[0]["waiver_expired"] == "2026-11-19"
    assert "waiver" not in found[0]
    assert unused[0]["why"] == "expired"


def test_glob_with_star_and_question_mark_needs_the_account():
    star = waiver(resource="arn:aws:rds:*:*:db:db-*", account=A)
    found, unused = apply([finding()], [star], NOW)
    assert found[0]["result"] == "waived" and unused == []
    one = waiver(resource="arn:aws:rds:eu-west-1:" + A + ":db:db-order?", account=A)
    found, _ = apply([finding()], [one], NOW)
    assert found[0]["result"] == "waived"
    other = waiver(resource="arn:aws:rds:*:*:db:db-*", account="222222222222")
    found, unused = apply([finding()], [other], NOW)
    assert found[0]["result"] == "fail"
    assert [u["why"] for u in unused] == ["no match"]
    assert unused[0]["account"] == "222222222222"


def test_glob_is_case_sensitive():
    found, _ = apply([finding()], [waiver(resource="ARN:AWS:RDS:*", account=A)], NOW)
    assert found[0]["result"] == "fail"


def test_an_exact_resource_is_compared_exactly_and_waiver_policy_must_match():
    found, unused = apply(
        [finding()],
        [waiver(resource=ARN + "x"), waiver(policy="RDS-002")],
        NOW,
        known_policies={"RDS-001", "RDS-002"},
    )
    assert found[0]["result"] == "fail"
    assert [u["why"] for u in unused] == ["no match", "no match"]


def test_an_exact_resource_with_an_account_must_agree_on_the_account():
    found, _ = apply([finding()], [waiver(account="222222222222")], NOW)
    assert found[0]["result"] == "fail"


def test_the_latest_expires_wins_and_ties_go_to_file_order():
    early = waiver("2026-12-01", file="early.yaml")
    late = waiver("2027-01-15", file="late.yaml")
    found, unused = apply([finding()], [early, late], NOW)
    assert found[0]["waiver"]["file"] == "late.yaml"
    assert [u["file"] for u in unused] == ["early.yaml"]
    first = waiver("2026-12-01", file="first.yaml")
    second = waiver("2026-12-01", file="second.yaml")
    found, _ = apply([finding()], [first, second], NOW)
    assert found[0]["waiver"]["file"] == "first.yaml"


def test_a_valid_waiver_beats_an_expired_one_and_the_expired_is_unused():
    found, unused = apply(
        [finding()], [waiver("2026-11-01"), waiver("2026-12-31")], NOW
    )
    assert found[0]["result"] == "waived"
    assert "waiver_expired" not in found[0]
    assert [u["why"] for u in unused] == ["expired"]


def test_unknown_policy_is_named_when_the_loaded_ids_are_given():
    w = waiver(policy="NOPE-001", resource="*x*", account=A)
    found, unused = apply([finding()], [w], NOW, known_policies={"RDS-001"})
    assert found[0]["result"] == "fail"
    assert [u["why"] for u in unused] == ["unknown policy"]
    # a loaded policy with no row is "no match", not "unknown policy"
    w = waiver(policy="RDS-009")
    _, unused = apply([finding()], [w], NOW, known_policies={"RDS-009"})
    assert [u["why"] for u in unused] == ["no match"]


def test_unused_entry_has_exactly_the_schema_fields():
    _, unused = apply([], [waiver()], NOW, known_policies={"RDS-001"})
    assert unused == [
        {
            "policy": "RDS-001",
            "resource": ARN,
            "expires": "2026-12-31",
            "why": "no match",
            "file": "w.yaml",
        }
    ]


def test_a_baseline_finding_can_be_waived_by_its_identity():
    row = finding(resource="arn:aws:s3:::old-exports", **{"from": "baseline"})
    w = waiver(resource="arn:aws:s3:::old-exports")
    found, _ = apply([row], [w], NOW)
    assert found[0]["result"] == "waived" and found[0]["from"] == "baseline"


def test_the_module_reads_no_clock():
    import inspect

    source = inspect.getsource(waivers)
    for word in ("datetime.now", "date.today", "time.time", "utcnow"):
        assert word not in source


def test_known_policies_is_required():
    with pytest.raises(TypeError):
        waivers.apply([finding()], [waiver()], NOW)


def test_a_valid_matching_waiver_that_lost_to_a_later_one_is_superseded():
    a = waiver("2026-12-31", file="a.yaml")
    b = waiver("2027-01-31", file="b.yaml")
    found, unused = apply([finding()], [a, b], NOW)
    assert found[0]["waiver"]["file"] == "b.yaml"
    assert unused == [
        {
            "policy": "RDS-001",
            "resource": ARN,
            "expires": "2026-12-31",
            "why": "superseded",
            "by": "b.yaml",
            "file": "a.yaml",
        }
    ]


def test_a_waiver_used_for_some_rows_is_not_unused():
    other = ARN + "2"
    a = waiver("2026-12-31", resource="arn:aws:rds:*", account=A, file="a.yaml")
    b = waiver("2027-01-31", resource=ARN, file="b.yaml")
    rows = [finding(), finding(resource=other)]
    found, unused = apply(rows, [a, b], NOW)
    assert [f["waiver"]["file"] for f in found] == ["b.yaml", "a.yaml"]
    assert unused == []


def test_superseded_needs_a_failing_row_and_a_valid_waiver():
    found, unused = apply(
        [finding(result="pass")], [waiver(), waiver("2027-01-01")], NOW
    )
    assert [u["why"] for u in unused] == ["no match", "no match"]
    # an expired waiver is expired, not superseded
    found, unused = apply([finding()], [waiver("2026-11-01"), waiver()], NOW)
    assert [(u["why"], "by" in u) for u in unused] == [("expired", False)]


def test_ties_name_the_first_waiver_as_the_one_that_was_used():
    first = waiver("2026-12-31", file="first.yaml")
    second = waiver("2026-12-31", file="second.yaml")
    _, unused = apply([finding()], [first, second], NOW)
    assert [(u["file"], u["why"], u["by"]) for u in unused] == [
        ("second.yaml", "superseded", "first.yaml")
    ]
