"""Exit codes of the ``inventag`` command. The one list; every module uses it.

====  =========================================================================
Code  Meaning
====  =========================================================================
0     Success (also when an account failed or nothing was found, unless one
      of the opt-in flags below is given).
1     Error: the run failed, a report format could not be written, or a
      configuration file or template is not valid.
2     Invalid or conflicting options, or ``--compliance-standard`` (not
      implemented).
3     Tag policy violations, when the config template sets
      ``fail_on_tag_violations``.
4     A security group rule at or above ``--risk-threshold``.
5     An account could not be scanned (or only partly), with
      ``--fail-on-account-error``.
6     No resources to report, with ``--fail-if-empty``.
====  =========================================================================

5 and 6 take precedence over 3 and 4, because the data behind 3 and 4 is
incomplete. Reports are written in all cases from 3 to 6.

:func:`decide` (below) computes the code of a whole run from its outcome. It
is not used by the command yet.
"""

from dataclasses import dataclass
from typing import Tuple

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_TAG_VIOLATIONS = 3
EXIT_RISK_THRESHOLD = 4
EXIT_ACCOUNT_FAILED = 5
EXIT_NO_RESOURCES = 6

# ---------------------------------------------------------------------------
# One exit decision for a whole run (failure model, design section 4).
#
# Not wired into the CLI yet: ``main()`` still decides with its own branches.
# The names below are pure and have no effect until a caller uses them.

#: The same number as :data:`EXIT_ACCOUNT_FAILED`: "the run finished but is
#: incomplete", with ``--fail-on-account-error`` or ``--fail-on-incomplete``.
EXIT_INCOMPLETE = EXIT_ACCOUNT_FAILED

#: Added to the signal number for a cancelled run (130 SIGINT, 143 SIGTERM).
SIGNAL_EXIT_BASE = 128
_SIGINT = 2
_SIGTERM = 15


@dataclass(frozen=True)
class Gates:
    """What the user asked for: flags and template settings that set a code."""

    fail_on_account_error: bool = False  # --fail-on-account-error   -> 5
    fail_on_incomplete: bool = False  # --fail-on-incomplete        -> 5
    fail_if_empty: bool = False  # --fail-if-empty              -> 6
    fail_on_tag_violations: bool = False  # config template          -> 3
    risk_threshold: bool = False  # --risk-threshold given        -> 4


@dataclass(frozen=True)
class Policy:
    """Release constants, not flags. Each field is one owner decision.

    The defaults are the owner's answers of 14 Nov 2026 (CLI clean-up plan,
    section (e) and "Owner answer": every recommendation accepted).
    :data:`POLICY_V1_2` reproduces v1.2.0 (the plan's "safe default if
    unanswered"); :data:`POLICY_2_0` is the policy planned for 2.0.0.
    """

    # O1 (OF-1): a run that read nothing (everything denied, no region
    # answered, session expired in every account) exits 1. Accepted: yes.
    derived_failure_fails_run: bool = True
    # O11 (OF-2): a guard block exits 1. Accepted: not in 1.x (0; 5 with
    # --fail-on-incomplete), 1 from 2.0.0.
    guard_block_fails_run: bool = False
    # O11 (OF-2): an output that was not asked for (state snapshot, change
    # log, checkpoints) failing exits 1. Accepted: not in 1.x, 1 from 2.0.0.
    auxiliary_output_fails_run: bool = False
    # O3 (OF-3): an empty result with --s3-bucket exits 0 like any empty
    # result (the upload is "skipped"). Accepted: yes. False keeps v1.2.0's 1.
    empty_upload_exits_zero: bool = True
    # O12: Ctrl-C exits 130 and SIGTERM 143. Accepted: yes. When False,
    # Ctrl-C exits 1 (as in v1.2.0) and SIGTERM 143 (what a shell reports for
    # a process killed by SIGTERM).
    signal_exit_codes: bool = True


#: The accepted 1.x policy (the owner's answers).
POLICY_1X = Policy()
#: v1.2.0 behaviour: every open decision at its "safe default if unanswered".
POLICY_V1_2 = Policy(
    derived_failure_fails_run=False,
    guard_block_fails_run=False,
    auxiliary_output_fails_run=False,
    empty_upload_exits_zero=False,
    signal_exit_codes=False,
)
POLICY_2_0 = Policy(
    derived_failure_fails_run=True,
    guard_block_fails_run=True,
    auxiliary_output_fails_run=True,
    empty_upload_exits_zero=True,
    signal_exit_codes=True,
)

#: Every reason :func:`decide` can return (``run_error:<category>`` aside).
REASONS = (
    "ok",
    "cancelled",
    "usage",
    "all_accounts_failed",
    "no_account_complete",
    "output_failed",
    "guard_block",
    "auxiliary_output_failed",
    "account_failed",
    "incomplete",
    "empty",
    "tag_violations",
    "risk_threshold",
)


def _signal_exit(signum: int, policy: Policy) -> int:
    if policy.signal_exit_codes:
        return SIGNAL_EXIT_BASE + signum
    if signum == _SIGINT:
        return EXIT_ERROR
    return SIGNAL_EXIT_BASE + signum


def decide(
    outcome, gates: Gates = Gates(), policy: Policy = POLICY_1X
) -> Tuple[int, str]:
    """``(exit code, reason)`` of a run. Pure: no I/O, no logging, no globals.

    ``outcome`` is an :class:`inventag.outcome.model.RunOutcome`.
    Precedence: 130/143 > 2 > 1 > 5 > 6 > 3 > 4 > 0.
    """
    from inventag.outcome.model import State

    o, g, p = outcome, gates, policy
    if o.cancelled_by is not None:
        return _signal_exit(o.cancelled_by, p), "cancelled"
    if o.usage_error:
        return EXIT_USAGE, "usage"
    if o.run_error is not None:
        return EXIT_ERROR, f"run_error:{getattr(o.run_error, 'value', o.run_error)}"

    def counts_as_failed(a) -> bool:
        # A derived failure (O1) fails the run only under that policy.
        return p.derived_failure_fails_run or not a.derived_failure

    scanned = [a for a in o.accounts if a.state is not State.SKIPPED]
    hard = [a for a in scanned if a.state is State.FAILED and counts_as_failed(a)]
    if scanned and len(hard) == len(scanned):
        return EXIT_ERROR, "all_accounts_failed"
    if (
        scanned
        and not any(a.state is State.COMPLETE for a in scanned)
        and all(
            (a.state is State.FAILED or a.account_issue) and counts_as_failed(a)
            for a in scanned
        )
    ):
        return EXIT_ERROR, "no_account_complete"
    if any(out.required and out.state is State.FAILED for out in o.outputs):
        return EXIT_ERROR, "output_failed"
    if (
        not p.empty_upload_exits_zero
        and o.empty
        and any(
            out.name == "s3-upload" and out.required and out.state is State.SKIPPED
            for out in o.outputs
        )
    ):
        return EXIT_ERROR, "output_failed"
    if p.guard_block_fails_run and o.guard_blocks:
        return EXIT_ERROR, "guard_block"
    if p.auxiliary_output_fails_run and any(
        out.state is State.FAILED for out in o.outputs
    ):
        return EXIT_ERROR, "auxiliary_output_failed"
    if g.fail_on_account_error and any(
        a.state is State.FAILED or a.account_issue for a in scanned
    ):
        return EXIT_INCOMPLETE, "account_failed"
    if g.fail_on_incomplete and o.state is not State.COMPLETE:
        return EXIT_INCOMPLETE, "incomplete"
    if g.fail_if_empty and o.empty:
        return EXIT_NO_RESOURCES, "empty"
    if g.fail_on_tag_violations and o.findings.tag_violations:
        return EXIT_TAG_VIOLATIONS, "tag_violations"
    if g.risk_threshold and o.findings.risk_findings:
        return EXIT_RISK_THRESHOLD, "risk_threshold"
    return EXIT_OK, "ok"
