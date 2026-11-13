"""reduce: states of service, region, account and run (design 2.2)."""

import threading

import pytest

from inventag.outcome.model import (
    AccountOutcome,
    Category,
    Issue,
    IssueLog,
    OutputOutcome,
    RunOutcome,
    Scope,
    State,
    merge_issues,
    severity_of,
)
from inventag.outcome.reduce import (
    entry_category,
    entry_issue,
    fold_expired_session,
    guard_issues,
    reduce_account,
    reduce_region,
    reduce_run,
    reduce_service,
)
from tests.unit.outcome.helpers import entry

C = Category
ACCT = "111111111111"


# ------------------------------------------------------------ ledger entries
@pytest.mark.parametrize(
    "fields,expected",
    [
        (dict(outcome="ok", count=3), None),
        (dict(outcome="empty"), None),
        # ed91cd6 records OptInRequired as "denied" (T4): the code wins
        (dict(outcome="denied", error_code="OptInRequired"), C.NOT_ENABLED),
        (dict(outcome="denied", error_code="AccessDenied"), C.PERMISSION_DENIED),
        (dict(outcome="denied", error_code="WeirdDenied"), C.PERMISSION_DENIED),
        (dict(outcome="throttled", error_code="Throttling"), C.THROTTLED),
        (dict(outcome="throttled", error_code="NewThrottleCode"), C.THROTTLED),
        (dict(outcome="timeout"), C.TIMEOUT),
        # T15: the account deadline inside a listing thread is a timeout
        (dict(outcome="error", error_code="AccountTimeoutError"), C.TIMEOUT),
        # T3: a guard block inside a listing
        (dict(outcome="error", error_code="ReadOnlyViolationError"), C.GUARD_BLOCK),
        (dict(outcome="error", error_code="EndpointConnectionError"), C.NETWORK),
        (dict(outcome="error", error_code="ExpiredToken"), C.CREDENTIALS),
        (dict(outcome="error", error_code="KeyError"), C.INTERNAL_ERROR),
        (dict(outcome="error", error_code="TimeoutError"), C.TIMEOUT),
        (dict(outcome="error", error_code="ConnectionResetError"), C.NETWORK),
        (dict(outcome="error", error_code="NotAClassName"), C.SERVICE_ERROR),
        (dict(outcome="error"), C.SERVICE_ERROR),
        (dict(outcome="skipped"), C.NOT_ENABLED),
        (dict(outcome="blocked"), C.GUARD_BLOCK),
        (dict(outcome="denied", category="not_available"), C.NOT_AVAILABLE),
        (
            dict(
                outcome="denied",
                source="billing",
                service="ce",
                error_code="DataUnavailableException",
            ),
            C.NOT_ENABLED,
        ),
    ],
)
def test_entry_category(fields, expected):
    assert entry_category(entry(**fields)) is expected


def test_entry_category_reads_objects_too():
    from inventag.discovery.coverage import CoverageEntry

    obj = CoverageEntry(**entry("denied", error_code="AccessDenied"))
    assert entry_category(obj) is C.PERMISSION_DENIED


def test_entry_issue():
    issue = entry_issue(entry("denied", error_code="AccessDenied", region="eu-west-1"))
    assert issue.scope is Scope.SERVICE
    assert (issue.account, issue.service, issue.operation, issue.code) == (
        ACCT,
        "sqs",
        "ListQueues",
        "AccessDenied",
    )
    assert issue.regions == ("eu-west-1",)
    assert entry_issue(entry("ok")) is None


# ------------------------------------------------------------ service unit
@pytest.mark.parametrize(
    "entries,state,category",
    [
        ([entry("ok", count=2), entry("empty")], State.COMPLETE, None),
        # a benign failure of one call next to a good one
        (
            [entry("ok", count=1), entry("denied", error_code="OptInRequired")],
            State.COMPLETE,
            None,
        ),
        ([entry("denied", error_code="OptInRequired")], State.SKIPPED, C.NOT_ENABLED),
        (
            [entry("error", error_code="UnknownEndpointError")],
            State.SKIPPED,
            C.NOT_AVAILABLE,
        ),
        (
            [entry("denied", error_code="AccessDenied")],
            State.FAILED,
            C.PERMISSION_DENIED,
        ),
        # D3: failed when no page was read ...
        ([entry("throttled", error_code="Throttling")], State.FAILED, C.THROTTLED),
        # ... partial when pages were kept before the failure
        (
            [entry("throttled", error_code="Throttling", count=5)],
            State.PARTIAL,
            C.THROTTLED,
        ),
        (
            [entry("ok", count=3), entry("denied", error_code="AccessDenied")],
            State.PARTIAL,
            C.PERMISSION_DENIED,
        ),
        (
            [
                entry("denied", error_code="OptInRequired"),
                entry("denied", error_code="AccessDenied"),
            ],
            State.FAILED,
            C.PERMISSION_DENIED,
        ),
        (
            [entry("error", error_code="ReadOnlyViolationError")],
            State.FAILED,
            C.GUARD_BLOCK,
        ),
    ],
)
def test_service_unit_states(entries, state, category):
    unit = reduce_service(entries)
    assert unit.state is state
    assert unit.category is category


def test_service_unit_counts():
    unit = reduce_service(
        [
            entry("ok", count=2, seconds=1.5),
            entry("throttled", error_code="Throttling", count=1),
        ]
    )
    assert (unit.resources, unit.calls_ok, unit.calls_failed) == (3, 1, 1)
    assert unit.seconds == 1.5


def test_service_unit_needs_entries():
    with pytest.raises(ValueError):
        reduce_service([])


# ------------------------------------------------------------ region
def _unit(state_entries):
    return reduce_service(state_entries)


def test_region_states():
    ok = _unit([entry("ok", count=1)])
    skipped = _unit([entry("denied", error_code="OptInRequired", service="x")])
    failed = _unit([entry("denied", error_code="AccessDenied", service="y")])
    assert reduce_region("r", [ok, skipped]).state is State.COMPLETE
    assert reduce_region("r", [skipped]).state is State.SKIPPED
    assert reduce_region("r", [ok, failed]).state is State.PARTIAL
    assert reduce_region("r", [failed, skipped]).state is State.FAILED
    assert reduce_region("r", []).state is State.COMPLETE
    assert reduce_region("r", [ok, failed]).category is C.PERMISSION_DENIED


def test_region_check_decides_the_region():
    benign = Issue(scope=Scope.REGION, category=C.NOT_ENABLED, region="ap-east-1")
    bad = Issue(scope=Scope.REGION, category=C.NETWORK, region="ap-east-1")
    assert reduce_region("ap-east-1", [], benign).state is State.SKIPPED
    assert reduce_region("ap-east-1", [], bad).state is State.FAILED


# ------------------------------------------------------------ account
def test_account_complete():
    acct, issues = reduce_account(ACCT, [entry("ok", count=4)], resources=4)
    assert acct.state is State.COMPLETE
    assert not acct.account_issue and not acct.derived_failure
    assert issues == []


def test_one_service_denied_makes_the_account_partial_without_account_issue():
    entries = [
        entry("ok", count=4, service="ec2", operation="DescribeInstances"),
        entry("denied", error_code="AccessDenied"),
        entry("denied", error_code="AccessDenied", region="eu-west-1"),
        entry("ok", region="eu-west-1", service="ec2", operation="DescribeInstances"),
    ]
    acct, issues = reduce_account(ACCT, entries, resources=4)
    assert acct.state is State.PARTIAL
    assert not acct.account_issue
    assert acct.category is C.PERMISSION_DENIED
    assert len(issues) == 1  # 2 regions merged into one issue
    assert issues[0].count == 2
    assert issues[0].regions == ("eu-west-1", "us-east-1")


def test_opt_in_service_does_not_make_the_account_partial():
    """D6: not_enabled is info, the unit is skipped, the account complete."""
    entries = [
        entry("ok", count=1, service="ec2"),
        entry("denied", error_code="OptInRequired"),
    ]
    acct, issues = reduce_account(ACCT, entries, resources=1)
    assert acct.state is State.COMPLETE
    assert [i.severity for i in issues] == ["info"]


def test_everything_denied_is_a_derived_failure():
    """F3 / I8: nothing read because everything was denied."""
    entries = [
        entry("denied", error_code="AccessDenied", service=s, region=r)
        for s in ("sqs", "ec2")
        for r in ("us-east-1", "eu-west-1")
    ]
    acct, _ = reduce_account(ACCT, entries)
    assert acct.state is State.FAILED
    assert acct.derived_failure is True
    assert acct.account_issue is False


def test_truly_empty_account_is_complete():
    acct, issues = reduce_account(ACCT, [entry("empty"), entry("empty", service="ec2")])
    assert acct.state is State.COMPLETE and issues == []


def test_every_region_failed_its_check_is_a_derived_failure():
    """C7: no region answered the access check."""
    checks = [
        Issue(
            scope=Scope.REGION,
            category=C.NETWORK,
            account=ACCT,
            region=r,
            phase="region_check",
        )
        for r in ("us-east-1", "eu-west-1")
    ]
    acct, _ = reduce_account(ACCT, [], checks, regions=["us-east-1", "eu-west-1"])
    assert acct.state is State.FAILED and acct.derived_failure


def test_disabled_region_is_skipped_and_the_account_complete():
    """A10: a credential-looking error from one region only."""
    check = Issue(
        scope=Scope.REGION,
        category=C.NOT_ENABLED,
        account=ACCT,
        region="ap-east-1",
        phase="region_check",
    )
    acct, issues = reduce_account(ACCT, [entry("ok", count=1)], [check], resources=1)
    assert acct.regions["ap-east-1"].state is State.SKIPPED
    assert acct.state is State.COMPLETE
    assert issues[0].severity == "warning"  # a region not scanned is always shown


def test_session_expired_is_one_account_issue():
    """A3 / T6: 42 warnings become one account-scope issue."""
    entries = [entry("ok", count=3, service="ec2")] + [
        entry("error", error_code="ExpiredToken", service=f"svc{i}") for i in range(42)
    ]
    acct, issues = reduce_account(ACCT, entries, resources=3)
    assert acct.account_issue is True
    assert acct.state is State.PARTIAL
    assert acct.derived_failure is True  # an O1 case (X4)
    assert len(issues) == 1
    assert issues[0].scope is Scope.ACCOUNT and issues[0].count == 42


def test_session_expired_with_nothing_kept_is_failed():
    acct, _ = reduce_account(ACCT, [entry("error", error_code="ExpiredTokenException")])
    assert acct.state is State.FAILED and acct.account_issue and acct.derived_failure


def test_fold_expired_session_leaves_other_issues():
    other = Issue(scope=Scope.SERVICE, category=C.PERMISSION_DENIED, account=ACCT)
    expired = Issue(
        scope=Scope.SERVICE, category=C.CREDENTIALS, code="RequestExpired", account=ACCT
    )
    rest, folded = fold_expired_session([other, expired], ACCT)
    assert rest == [other]
    assert folded.scope is Scope.ACCOUNT and folded.code == "RequestExpired"
    assert fold_expired_session([other], ACCT) == ([other], None)


@pytest.mark.parametrize("resources,state", [(10, State.PARTIAL), (0, State.FAILED)])
def test_account_time_limit(resources, state):
    """B3: partial results kept and labelled; account_issue set."""
    limit = Issue(
        scope=Scope.ACCOUNT,
        category=C.TIMEOUT,
        account=ACCT,
        code="AccountTimeoutError",
    )
    acct, issues = reduce_account(ACCT, [], [limit], resources=resources)
    assert acct.state is state
    assert acct.account_issue and not acct.derived_failure
    assert acct.category is C.TIMEOUT


def test_no_session_is_a_failed_account_not_derived():
    """P1 / A4."""
    issue = Issue(
        scope=Scope.ACCOUNT,
        category=C.PERMISSION_DENIED,
        account=ACCT,
        phase="assume_role",
        code="AccessDenied",
    )
    acct, _ = reduce_account(ACCT, [], [issue])
    assert acct.state is State.FAILED
    assert acct.account_issue and not acct.derived_failure


def test_service_budget_timeout_is_not_an_account_issue():
    entries = [entry("ok", count=1, service="ec2"), entry("timeout", service="logs")]
    acct, _ = reduce_account(ACCT, entries, resources=1)
    assert acct.state is State.PARTIAL and not acct.account_issue


def test_resource_scope_issues_do_not_change_the_state():
    detail = Issue(
        scope=Scope.RESOURCE,
        category=C.PERMISSION_DENIED,
        account=ACCT,
        service="s3",
        operation="GetBucketLocation",
    )
    acct, issues = reduce_account(
        ACCT, [entry("ok", count=1, service="s3")], [detail], resources=1
    )
    assert acct.state is State.COMPLETE
    assert issues == [detail]


def test_reused_account_is_complete_and_keeps_its_issues():
    """B8."""
    old = Issue(
        scope=Scope.SERVICE, category=C.PERMISSION_DENIED, account=ACCT, service="sqs"
    )
    acct, issues = reduce_account(
        ACCT, [], [old], reused_from="2026-11-13T14:00:00Z", resources=5
    )
    assert acct.state is State.COMPLETE and acct.reused_from
    assert issues == [old]


def test_account_not_attempted_is_skipped():
    acct, _ = reduce_account(ACCT, attempted=False)
    assert acct.state is State.SKIPPED


def test_issues_of_other_accounts_are_ignored():
    other = Issue(scope=Scope.ACCOUNT, category=C.TIMEOUT, account="999999999999")
    acct, issues = reduce_account(ACCT, [entry("ok", count=1)], [other], resources=1)
    assert acct.state is State.COMPLETE and issues == []


# ------------------------------------------------------------ merge, IssueLog
def test_merge_by_key_counts_regions_and_examples():
    issues = [
        Issue(
            scope=Scope.RESOURCE,
            category=C.PERMISSION_DENIED,
            account=ACCT,
            service="s3",
            operation="GetBucketLocation",
            code="AccessDenied",
            region=r,
            examples=(f"bucket-{i}",),
        )
        for i, r in enumerate(["us-east-1"] * 3 + ["eu-west-1"] * 34)
    ]
    merged = merge_issues(issues)
    assert len(merged) == 1
    m = merged[0]
    assert m.count == 37
    assert m.regions == ("eu-west-1", "us-east-1")
    assert m.region == ""
    assert m.examples == ("bucket-0", "bucket-1", "bucket-2")


def test_merge_rejects_different_keys():
    a = Issue(scope=Scope.SERVICE, category=C.THROTTLED, service="a")
    b = Issue(scope=Scope.SERVICE, category=C.THROTTLED, service="b")
    with pytest.raises(ValueError):
        a.merged_with(b)
    assert len(merge_issues([a, b])) == 2


def test_issue_log_is_thread_safe():
    log = IssueLog()

    def work(region):
        for _ in range(200):
            log.add(
                Issue(
                    scope=Scope.SERVICE,
                    category=C.THROTTLED,
                    service="sqs",
                    region=region,
                )
            )

    threads = [threading.Thread(target=work, args=(f"r{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    (issue,) = log.issues()
    assert issue.count == 1600
    assert len(issue.regions) == 8
    assert len(log) == 1


def test_issue_order_is_deterministic():
    a = Issue(
        scope=Scope.SERVICE, category=C.PERMISSION_DENIED, account="2", service="b"
    )
    b = Issue(scope=Scope.ACCOUNT, category=C.CREDENTIALS, account="3")
    c = Issue(scope=Scope.SERVICE, category=C.NOT_ENABLED, account="1", service="a")
    assert IssueLog([c, a, b]).issues() == [b, a, c]


@pytest.mark.parametrize(
    "scope,category,expected",
    [
        (Scope.RUN, C.NOT_ENABLED, "error"),
        (Scope.OUTPUT, C.CANCELLED, "error"),
        (Scope.ACCOUNT, C.PERMISSION_DENIED, "error"),
        (Scope.REGION, C.NOT_ENABLED, "warning"),
        (Scope.REGION, C.CREDENTIALS, "error"),
        (Scope.SERVICE, C.NOT_AVAILABLE, "info"),
        (Scope.SERVICE, C.PERMISSION_DENIED, "warning"),
        (Scope.SERVICE, C.GUARD_BLOCK, "error"),
        (Scope.RESOURCE, C.INTERNAL_ERROR, "warning"),
        (Scope.RESOURCE, C.GUARD_BLOCK, "error"),
        (Scope.RESOURCE, C.NOT_FOUND, "info"),
    ],
)
def test_severity_by_scope(scope, category, expected):
    assert severity_of(scope, category) == expected


def test_category_set_is_closed():
    assert [c.value for c in Category] == [
        "credentials",
        "permission_denied",
        "not_enabled",
        "not_available",
        "not_found",
        "throttled",
        "timeout",
        "network",
        "service_error",
        "guard_block",
        "invalid_input",
        "output_failure",
        "cancelled",
        "internal_error",
    ]


# ------------------------------------------------------------ guard, run
def test_guard_issues_add_only_unreported_blocks():
    """G5: a block swallowed by an except still surfaces."""
    reported = Issue(
        scope=Scope.SERVICE,
        category=C.GUARD_BLOCK,
        account=ACCT,
        service="sqs",
        operation="CreateQueue",
    )
    blocked = [
        {"service": "sqs", "operation": "CreateQueue", "region": "us-east-1"},
        {"service": "sns", "operation": "Publish", "region": "us-east-1"},
        {"service": "sns", "operation": "Publish", "region": "eu-west-1"},
    ]
    found = guard_issues(blocked, [reported])
    assert [(i.service, i.operation, i.count) for i in found] == [("sns", "Publish", 2)]
    assert found[0].severity == "error"


def test_reduce_run_counts_guard_blocks_and_merges():
    run = reduce_run(
        [AccountOutcome(ACCT)],
        issues=[Issue(scope=Scope.RUN, category=C.NETWORK)] * 2,
        guard_blocked=[{"service": "sqs", "operation": "CreateQueue"}],
        resources_reported=1,
    )
    assert run.guard_blocks == 1
    assert [i.count for i in run.issues if i.category is C.NETWORK] == [2]
    assert run.state is State.PARTIAL


def _acct(state, **kw):
    return AccountOutcome("1", state=state, **kw)


@pytest.mark.parametrize(
    "run,expected",
    [
        (RunOutcome([_acct(State.COMPLETE)]), State.COMPLETE),
        (RunOutcome([]), State.COMPLETE),
        (RunOutcome([_acct(State.COMPLETE), _acct(State.PARTIAL)]), State.PARTIAL),
        (RunOutcome([_acct(State.COMPLETE), _acct(State.FAILED)]), State.PARTIAL),
        (RunOutcome([_acct(State.FAILED), _acct(State.FAILED)]), State.FAILED),
        (RunOutcome([_acct(State.FAILED, derived_failure=True)]), State.FAILED),
        (RunOutcome([_acct(State.COMPLETE)], guard_blocks=1), State.PARTIAL),
        (RunOutcome([_acct(State.COMPLETE)], cancelled_by=2), State.FAILED),
        (RunOutcome([_acct(State.COMPLETE)], run_error=C.NETWORK), State.FAILED),
        (
            RunOutcome(
                [_acct(State.COMPLETE)],
                outputs=[OutputOutcome("excel", True, State.FAILED)],
            ),
            State.FAILED,
        ),
        (
            RunOutcome(
                [_acct(State.COMPLETE)],
                outputs=[OutputOutcome("state-snapshot", False, State.FAILED)],
            ),
            State.PARTIAL,
        ),
        (
            RunOutcome(
                [_acct(State.COMPLETE)],
                outputs=[OutputOutcome("s3-upload", True, State.SKIPPED)],
            ),
            State.COMPLETE,
        ),
    ],
)
def test_run_state(run, expected):
    assert run.state is expected


def test_state_words():
    assert RunOutcome([_acct(State.COMPLETE)]).state_word == "COMPLETE"
    assert RunOutcome([_acct(State.PARTIAL)]).state_word == "INCOMPLETE"
    assert RunOutcome([_acct(State.FAILED)]).state_word == "FAILED"
    assert (
        RunOutcome([_acct(State.COMPLETE)], cancelled_by=15).state_word == "CANCELLED"
    )
