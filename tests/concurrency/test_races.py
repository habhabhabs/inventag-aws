"""A5, plan 2.10 row "Race": chosen interleavings are forced with events and barriers.

No test here waits for time to pass. A request is stopped inside the moto stubber
(``Holds`` in ``tests/concurrency/_child.py``) until another request has started
(an event) or until two requests have both arrived (a barrier). A hold has a
timeout so that a run that cannot reach the interleaving (for example the
sequential run, where nothing else can start while one request is held) still
ends; the stats file says per hold whether it ended by the event or by the
timeout, and the tests that must reach the interleaving assert ``"event"``.

Every forced run is compared with an unforced run of the same estate: whatever
the interleaving, the files are the same (plan 2.4).

Rows that need code of A2 or A3 are expected to fail until then (``needs_*``).

``pytest -m slow tests/concurrency/test_races.py`` (each scan 15 to 25 s).
"""

import pytest

from tests.concurrency import compare
from tests.concurrency.test_equal_outputs import needs_a2

pytestmark = pytest.mark.slow

ESTATE = dict(regions=["us-east-1", "eu-west-1"], accounts=3)
ARGS_BY_MODE = {
    "default": [],
    "concurrency-64": pytest.param(["--concurrency", "64"], marks=needs_a2),
}

needs_a3 = pytest.mark.xfail(
    strict=True,
    reason=(
        "A3: detail calls still run one after the other in v1.3.0 (a held detail request "
        "stops the others, so the hold ends by its timeout, not by the event); remove "
        "this mark when A3 is merged"
    ),
)


def _same(a, b):
    assert a.code == b.code == 0, (a.text[-600:], b.text[-600:])
    assert compare.describe_difference(a.out, b.out) is None
    assert a.calls == b.calls


@pytest.fixture(params=list(ARGS_BY_MODE.values()), ids=list(ARGS_BY_MODE))
def mode(request):
    return request.param


def test_a_late_first_account_changes_nothing(scans, mode):
    """The first configured account is stopped at its first ec2 request until both other
    accounts have started theirs: the accounts finish in the order 2, 3, 1."""
    hold = dict(
        name="late-first-account",
        match=dict(service="ec2", operation="DescribeVpcs", account="first"),
        until=dict(service="ec2", operation="DescribeVpcs", account="other"),
        count=2,
        timeout=20,
    )
    plain = scans(mode, **ESTATE)
    late = scans(mode, holds=[hold], **ESTATE)
    assert late.stats["holds"] == {"late-first-account": "event"}, late.stats["holds"]
    _same(plain, late)


def test_two_listing_tasks_that_end_together_change_nothing(scans, mode):
    """Two listings of the first account meet at a barrier and go on at the same moment."""
    hold = dict(
        name="two-listings-meet",
        meet=[
            dict(
                service="sqs",
                operation="ListQueues",
                account="first",
                region="us-east-1",
            ),
            dict(
                service="sns",
                operation="ListTopics",
                account="first",
                region="us-east-1",
            ),
        ],
        timeout=20,
    )
    plain = scans(mode, **ESTATE)
    together = scans(mode, holds=[hold], **ESTATE)
    assert together.stats["holds"] == {"two-listings-meet": "event"}
    _same(plain, together)


def test_a_late_detail_answer_changes_nothing(scans, mode):
    """The first detail request is held until three other detail requests have started."""
    estate = dict(ESTATE, counts=dict(functions=6, queues=6))
    hold = dict(
        name="late-detail",
        match=dict(service="lambda", operation="GetFunctionConfiguration"),
        until=dict(service="lambda", operation="GetFunctionConfiguration"),
        count=3,
        timeout=8,
    )
    plain = scans(mode, **estate)
    late = scans(mode, holds=[hold], **estate)
    assert "late-detail" in late.stats["holds"]
    _same(plain, late)


@needs_a3
def test_detail_calls_of_one_account_overlap(scans):
    """Plan 2.1: detail calls run in a detail pool, so while one request is held the
    others start: the hold ends by its event."""
    estate = dict(regions=["us-east-1"], accounts=1, counts=dict(functions=6))
    hold = dict(
        name="late-detail",
        match=dict(service="lambda", operation="GetFunctionConfiguration"),
        until=dict(service="lambda", operation="GetFunctionConfiguration"),
        count=3,
        timeout=8,
    )
    scan = scans(holds=[hold], **estate)
    assert scan.code == 0
    assert scan.stats["holds"] == {"late-detail": "event"}


@needs_a2
@needs_a3
def test_at_most_four_detail_calls_of_one_key_are_in_flight(scans):
    """Plan 2.1 and 2.3: at most 4 in flight for one account, service and region."""
    estate = dict(
        regions=["us-east-1"], accounts=1, counts=dict(functions=12), latency_ms=5
    )
    scan = scans(
        ["--concurrency", "64"],
        per_operation={"lambda:GetFunctionConfiguration": 40},
        **estate,
    )
    assert scan.code == 0
    records = [
        r
        for r in scan.stats["records"]
        if (r[0], r[1]) == ("lambda", "GetFunctionConfiguration")
    ]
    from tests.concurrency.test_equal_outputs import _overlap

    assert 1 < _overlap(records) <= 4, _overlap(records)


# -------------------------------------------------------- abandoning an account
LIMIT = 20  # seconds; above the time a whole scan of this size needs, as rows B3 and B5


def _abandon_spec():
    hold = dict(
        name="stuck-detail",
        match=dict(
            service="lambda", operation="GetFunctionConfiguration", account="other"
        ),
        until=dict(service="lambda", operation="NeverCalled"),
        timeout=120,
    )
    return dict(
        regions=["us-east-1"],
        accounts=2,
        counts=dict(functions=4),
        holds=[hold],
    )


@pytest.mark.parametrize(
    "args",
    ["default", pytest.param("concurrency-8", marks=needs_a2)],
)
def test_an_account_abandoned_during_its_detail_calls_ends_the_run_as_today(
    scans, args
):
    """One detail request of the second account never answers. The account's time limit
    ends it: today's message, the first account's rows and the rows the second account
    found before the limit are in the report, and the run ends."""
    extra = ["--account-processing-timeout", str(LIMIT)]
    if args == "concurrency-8":
        extra += ["--concurrency", "8"]
    scan = scans(extra, **_abandon_spec())
    assert scan.code == 0, scan.text[-1500:]
    assert (
        "timed out after 20 seconds (--account-processing-timeout)" in scan.text
    ), scan.text[-1500:]
    assert "Traceback" not in scan.text
    (report,) = scan.files("*.xlsx")
    accounts = {row[5] for row in compare.resource_rows(report)}
    assert "123456789012" in accounts, "the first account's rows are missing"
