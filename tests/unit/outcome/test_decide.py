"""exit_codes.decide(): design 4.2 table, precedence, and every Policy field
under both values (each is an owner decision)."""

from dataclasses import fields, replace

import pytest

from inventag import exit_codes as ec
from inventag.exit_codes import (
    POLICY_1X,
    POLICY_2_0,
    POLICY_V1_2,
    Gates,
    Policy,
    decide,
)
from inventag.outcome.model import (
    AccountOutcome,
    Category,
    Findings,
    OutputOutcome,
    RunOutcome,
    State,
)

C = Category


def ok(i="1"):
    return AccountOutcome(f"{i}" * 12, state=State.COMPLETE)


def no_session(i="2"):
    return AccountOutcome(
        f"{i}" * 12, state=State.FAILED, account_issue=True, category=C.CREDENTIALS
    )


def partial(i="3", **kw):
    return AccountOutcome(f"{i}" * 12, state=State.PARTIAL, **kw)


def all_denied(i="4"):
    return AccountOutcome(
        f"{i}" * 12,
        state=State.FAILED,
        derived_failure=True,
        category=C.PERMISSION_DENIED,
    )


def timed_out(i="5", resources=10):
    return AccountOutcome(
        f"{i}" * 12,
        state=State.PARTIAL if resources else State.FAILED,
        account_issue=True,
        category=C.TIMEOUT,
        resources=resources,
    )


def expired(i="6"):
    return AccountOutcome(
        f"{i}" * 12,
        state=State.PARTIAL,
        account_issue=True,
        derived_failure=True,
        category=C.CREDENTIALS,
        resources=3,
    )


def run(accounts, reported=5, **kw):
    return RunOutcome(accounts=accounts, resources_reported=reported, **kw)


def test_policy_defaults_are_the_owner_answers():
    """Owner answer of 14 Nov 2026: every recommendation of plan (e) accepted."""
    assert Policy() == POLICY_1X
    assert POLICY_1X.derived_failure_fails_run is True  # O1
    assert POLICY_1X.empty_upload_exits_zero is True  # O3
    assert POLICY_1X.guard_block_fails_run is False  # O11: 1 only from 2.0.0
    assert POLICY_1X.auxiliary_output_fails_run is False  # O11
    assert POLICY_1X.signal_exit_codes is True  # O12
    assert all(getattr(POLICY_2_0, f.name) is True for f in fields(Policy))
    assert all(getattr(POLICY_V1_2, f.name) is False for f in fields(Policy))


def test_existing_names_and_values_are_unchanged():
    assert (
        ec.EXIT_OK,
        ec.EXIT_ERROR,
        ec.EXIT_USAGE,
        ec.EXIT_TAG_VIOLATIONS,
        ec.EXIT_RISK_THRESHOLD,
        ec.EXIT_ACCOUNT_FAILED,
        ec.EXIT_NO_RESOURCES,
    ) == (0, 1, 2, 3, 4, 5, 6)
    assert ec.EXIT_INCOMPLETE == ec.EXIT_ACCOUNT_FAILED


GATE_ACCOUNT = Gates(fail_on_account_error=True)
GATE_INCOMPLETE = Gates(fail_on_incomplete=True)
GATE_EMPTY = Gates(fail_if_empty=True)
NO_GATE = Gates()

# Design 4.2 "combined cases", with the policy each row depends on.
# (name, outcome, gates, policy, expected code)
TABLE = [
    ("P1 1 of 2 no session", run([ok(), no_session()]), NO_GATE, POLICY_1X, 0),
    ("P1 with flag", run([ok(), no_session()]), GATE_ACCOUNT, POLICY_1X, 5),
    (
        "B2 all no session",
        run([no_session("2"), no_session("3")], 0),
        NO_GATE,
        POLICY_1X,
        1,
    ),
    (
        "B2 with flag",
        run([no_session("2"), no_session("3")], 0),
        GATE_ACCOUNT,
        POLICY_1X,
        1,
    ),
    ("P3 one service denied", run([partial()]), NO_GATE, POLICY_1X, 0),
    ("P3 incomplete flag", run([partial()]), GATE_INCOMPLETE, POLICY_1X, 5),
    ("P3 account flag", run([partial()]), GATE_ACCOUNT, POLICY_1X, 0),
    ("B3 one timed out", run([ok(), timed_out()]), NO_GATE, POLICY_1X, 0),
    ("B3 with flag", run([ok(), timed_out()]), GATE_ACCOUNT, POLICY_1X, 5),
    (
        "every account timed out",
        run([timed_out("5"), timed_out("7")]),
        NO_GATE,
        POLICY_1X,
        1,
    ),
    # F3 / X6: everything denied, single account (O1)
    ("F3 O1 yes", run([all_denied()], 0), NO_GATE, POLICY_1X, 1),
    ("F3 O1 no", run([all_denied()], 0), NO_GATE, POLICY_V1_2, 0),
    ("F3 O1 no, empty gate", run([all_denied()], 0), GATE_EMPTY, POLICY_V1_2, 6),
    ("F3 O1 no, account gate", run([all_denied()], 0), GATE_ACCOUNT, POLICY_V1_2, 5),
    (
        "F3 O1 no, incomplete gate",
        run([all_denied()], 0),
        GATE_INCOMPLETE,
        POLICY_V1_2,
        5,
    ),
    ("F3 2.0", run([all_denied()], 0), NO_GATE, POLICY_2_0, 1),
    ("denied in 1 of 2", run([ok(), all_denied()]), NO_GATE, POLICY_1X, 0),
    ("denied in 1 of 2, flag", run([ok(), all_denied()]), GATE_ACCOUNT, POLICY_1X, 5),
    # X4: session expired in every account (O1)
    ("X4 O1 yes", run([expired()]), NO_GATE, POLICY_1X, 1),
    ("X4 O1 no", run([expired()]), NO_GATE, POLICY_V1_2, 0),
    # derived + classic failure mixed: v1.2.0 exits 0, O1 exits 1
    ("mixed O1 yes", run([all_denied(), no_session()], 0), NO_GATE, POLICY_1X, 1),
    ("mixed O1 no", run([all_denied(), no_session()], 0), NO_GATE, POLICY_V1_2, 0),
    ("F1 truly empty", run([ok()], 0), NO_GATE, POLICY_1X, 0),
    ("F1 with flag", run([ok()], 0), GATE_EMPTY, POLICY_1X, 6),
    (
        "P7 a report format failed",
        run([ok()], outputs=[OutputOutcome("excel", True, State.FAILED)]),
        NO_GATE,
        POLICY_1X,
        1,
    ),
    (
        "J2 snapshot failed",
        run([ok()], outputs=[OutputOutcome("state-snapshot", False, State.FAILED)]),
        NO_GATE,
        POLICY_1X,
        0,
    ),
    (
        "J2 incomplete flag",
        run([ok()], outputs=[OutputOutcome("state-snapshot", False, State.FAILED)]),
        GATE_INCOMPLETE,
        POLICY_1X,
        5,
    ),
    (
        "J2 2.0",
        run([ok()], outputs=[OutputOutcome("state-snapshot", False, State.FAILED)]),
        NO_GATE,
        POLICY_2_0,
        1,
    ),
    ("G1 guard block", run([ok()], guard_blocks=1), NO_GATE, POLICY_1X, 0),
    ("G1 incomplete flag", run([ok()], guard_blocks=1), GATE_INCOMPLETE, POLICY_1X, 5),
    ("G1 2.0", run([ok()], guard_blocks=1), NO_GATE, POLICY_2_0, 1),
    (
        "account failed and tag violations",
        run([ok(), no_session()], findings=Findings(tag_violations=2)),
        Gates(fail_on_tag_violations=True),
        POLICY_1X,
        3,
    ),
    (
        "plus account flag",
        run([ok(), no_session()], findings=Findings(tag_violations=2)),
        Gates(fail_on_tag_violations=True, fail_on_account_error=True),
        POLICY_1X,
        5,
    ),
    (
        "empty and an account failed, both flags",
        run([ok(), no_session()], 0),
        Gates(fail_if_empty=True, fail_on_account_error=True),
        POLICY_1X,
        5,
    ),
    (
        "tag and risk, both gates",
        run([ok()], findings=Findings(tag_violations=1, risk_findings=1)),
        Gates(fail_on_tag_violations=True, risk_threshold=True),
        POLICY_1X,
        3,
    ),
    (
        "tag and risk, risk gate only",
        run([ok()], findings=Findings(tag_violations=1, risk_findings=1)),
        Gates(risk_threshold=True),
        POLICY_1X,
        4,
    ),
    (
        "findings without gates",
        run([ok()], findings=Findings(tag_violations=1, risk_findings=1)),
        NO_GATE,
        POLICY_1X,
        0,
    ),
    (
        "Ctrl-C, any flags",
        run([no_session()], 0, cancelled_by=2),
        GATE_ACCOUNT,
        POLICY_1X,
        130,
    ),
    ("Ctrl-C O12 no", run([ok()], cancelled_by=2), NO_GATE, POLICY_V1_2, 1),
    (
        "SIGTERM while an output was failing",
        run(
            [ok()],
            cancelled_by=15,
            outputs=[OutputOutcome("excel", True, State.FAILED)],
        ),
        NO_GATE,
        POLICY_1X,
        143,
    ),
    ("SIGTERM O12 no", run([ok()], cancelled_by=15), NO_GATE, POLICY_V1_2, 143),
    ("usage error", run([], usage_error=True), NO_GATE, POLICY_1X, 2),
    ("run error", run([ok()], run_error=C.NETWORK), GATE_EMPTY, POLICY_1X, 1),
    ("no accounts at all", run([], 0), NO_GATE, POLICY_1X, 0),
]


@pytest.mark.parametrize(
    "name,outcome,gates,policy,expected", TABLE, ids=[r[0] for r in TABLE]
)
def test_design_table(name, outcome, gates, policy, expected):
    code, reason = decide(outcome, gates, policy)
    assert code == expected
    assert reason in ec.REASONS or reason.startswith("run_error:")


# ---------------------------------------------------------- O3, both values
def _empty_upload():
    return run([ok()], 0, outputs=[OutputOutcome("s3-upload", True, State.SKIPPED)])


@pytest.mark.parametrize(
    "policy,gates,expected",
    [
        (POLICY_1X, NO_GATE, (0, "ok")),  # O3 accepted
        (POLICY_1X, GATE_EMPTY, (6, "empty")),
        (POLICY_V1_2, NO_GATE, (1, "output_failed")),  # v1.2.0 (T10)
        (POLICY_V1_2, GATE_EMPTY, (1, "output_failed")),
    ],
)
def test_o3_empty_result_with_upload(policy, gates, expected):
    assert decide(_empty_upload(), gates, policy) == expected


def test_o3_does_not_apply_when_there_was_something_to_upload():
    outcome = run([ok()], 3, outputs=[OutputOutcome("s3-upload", True, State.SKIPPED)])
    assert decide(outcome, NO_GATE, POLICY_V1_2) == (0, "ok")


# ---------------------------------------------------------- each field flips
CASES_PER_FIELD = {
    "derived_failure_fails_run": (run([all_denied()], 0), 1, 0),
    "guard_block_fails_run": (run([ok()], guard_blocks=2), 1, 0),
    "auxiliary_output_fails_run": (
        run([ok()], outputs=[OutputOutcome("changelog", False, State.FAILED)]),
        1,
        0,
    ),
    "empty_upload_exits_zero": (_empty_upload(), 0, 1),
    "signal_exit_codes": (run([ok()], cancelled_by=2), 130, 1),
}


def test_every_policy_field_has_a_case():
    assert set(CASES_PER_FIELD) == {f.name for f in fields(Policy)}


@pytest.mark.parametrize("name", sorted(CASES_PER_FIELD))
@pytest.mark.parametrize("value", [True, False])
def test_each_policy_field_alone(name, value):
    outcome, when_true, when_false = CASES_PER_FIELD[name]
    base = POLICY_V1_2 if value else POLICY_2_0
    policy = replace(base, **{name: value})
    code, _ = decide(outcome, NO_GATE, policy)
    assert code == (when_true if value else when_false)


# ---------------------------------------------------------- precedence
def test_precedence_signal_usage_error_incomplete_empty_tag_risk():
    """130/143 > 2 > 1 > 5 > 6 > 3 > 4 > 0, peeled one level at a time."""
    everything = Gates(
        fail_on_account_error=True,
        fail_if_empty=True,
        fail_on_tag_violations=True,
        risk_threshold=True,
    )
    outcome = run(
        [ok(), no_session()],
        0,
        outputs=[OutputOutcome("excel", True, State.FAILED)],
        findings=Findings(tag_violations=1, risk_findings=1),
        cancelled_by=2,
        usage_error=True,
    )
    expected = [130, 2, 1, 5, 6, 3, 4, 0]
    peel = [
        lambda o: replace(o, cancelled_by=None),
        lambda o: replace(o, usage_error=False),
        lambda o: replace(o, outputs=[]),
        lambda o: replace(o, accounts=[ok()]),
        lambda o: replace(o, resources_reported=5),
        lambda o: replace(o, findings=Findings(risk_findings=1)),
        lambda o: replace(o, findings=Findings()),
    ]
    got = [decide(outcome, everything)[0]]
    for step in peel:
        outcome = step(outcome)
        got.append(decide(outcome, everything)[0])
    assert got == expected


def test_decide_is_pure():
    outcome = run([ok(), no_session()])
    before = repr(outcome)
    assert decide(outcome, GATE_ACCOUNT) == decide(outcome, GATE_ACCOUNT)
    assert repr(outcome) == before


def test_skipped_accounts_are_not_counted():
    skipped = AccountOutcome("9" * 12, state=State.SKIPPED)
    assert decide(run([skipped, ok()]), GATE_ACCOUNT) == (0, "ok")
    assert decide(run([skipped, no_session()], 0))[0] == 1
