"""A5, plan 2.10 row "Throttling": a throttle injected by operation name.

Faults are chosen by service and operation (``tests/latency.py``), never by "after
N calls". The SDK's wait between retries is recorded, not slept (``_child.py``).
Today's behaviour (v1.3.0, the SDK's retry is the only retry mechanism) is
pinned by the first rows; the rows for the limiter's reaction need A2 (and A3
for the detail calls) and are expected to fail until then.

``pytest -m slow tests/concurrency/test_throttling.py``
"""

import json
import re

import pytest

from tests.concurrency import compare
from tests.concurrency.test_equal_outputs import _overlap, needs_a2

pytestmark = pytest.mark.slow

ONE = dict(accounts=1, regions=["us-east-1"])
SQS_ATTEMPTS_TODAY = 10  # attempts of one request that is throttled every time


def _messages(text):
    found = []
    for line in text.replace("\r", "\n").split("\n"):
        match = re.search(r"\b(?:INFO|WARNING|ERROR) - (.*)$", line)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return sorted(found)


def _attempts(scan, operation):
    return [r[2] for r in scan.stats["records"] if r[1] == operation]


def test_a_transient_throttle_is_retried_by_the_sdk_and_the_result_is_complete(scans):
    """The first two attempts of ``sqs:ListQueues`` get ``Throttling``, the third passes:
    the SDK retries, nothing else does, and the files equal those of a run without throttle.
    """
    clean = scans(**ONE)
    throttled = scans(throttle={"sqs:ListQueues": 2}, **ONE)
    assert throttled.code == 0
    assert _attempts(throttled, "ListQueues") == [1, 2, 3]
    assert [r[3] for r in throttled.stats["records"] if r[1] == "ListQueues"] == [
        "Throttling",
        "Throttling",
        None,
    ]
    assert len(throttled.stats["sdk_backoffs"]) == 2
    assert compare.describe_difference(clean.out, throttled.out) is None


def test_a_permanent_throttle_gives_todays_warning_note_and_coverage_entry(scans):
    scan = scans(throttle={"sqs:ListQueues": None}, **ONE)
    assert scan.code == 0
    assert len(_attempts(scan, "ListQueues")) == SQS_ATTEMPTS_TODAY
    messages = _messages(scan.text)
    assert (
        "sqs list_queues in us-east-1 failed (Throttling); its resources there may be incomplete."
        in messages
    )
    assert (
        "  - Not read in account 123456789012, so the report is partial there: "
        "sqs in us-east-1 (throttled)." in messages
    )
    (snapshot,) = sorted((scan.out / "state").glob("state_*.json"))
    tags = json.loads(snapshot.read_text())["metadata"]["tags"]
    assert tags["coverage_summary"]["123456789012"]["throttled"] == 1
    assert tags["units_not_read"], "the unit that was not read is not in the snapshot"


@needs_a2
def test_a_permanent_throttle_under_the_limiter_gives_the_same_files_and_the_same_attempts(
    scans,
):
    """Plan 2.3: the limiter only shapes how many requests run; the SDK's ``standard``
    retry stays the only retry mechanism, so the attempts, the warning, the note and
    the coverage entry are those of the run without ``--concurrency``."""
    today = scans(throttle={"sqs:ListQueues": None}, **ONE)
    limited = scans(["--concurrency", "8"], throttle={"sqs:ListQueues": None}, **ONE)
    assert limited.code == 0
    assert len(_attempts(limited, "ListQueues")) == SQS_ATTEMPTS_TODAY
    assert _messages(limited.text) == _messages(today.text)
    assert compare.describe_difference(today.out, limited.out) is None


@needs_a2
def test_a_transient_throttle_under_the_limiter_gives_the_result_of_a_clean_run(scans):
    clean = scans(["--concurrency", "8"], **ONE)
    throttled = scans(["--concurrency", "8"], throttle={"sqs:ListQueues": 2}, **ONE)
    assert throttled.code == 0
    assert _attempts(throttled, "ListQueues") == [1, 2, 3]
    assert compare.describe_difference(clean.out, throttled.out) is None


@needs_a2
def test_a_throttle_halves_only_the_limit_of_its_own_key(scans):
    """Detail calls of ``lambda`` (cap 4) are throttled once each. After the first throttled
    answer no more than 2 requests of that key are in flight at once; the throttled
    requests are retried by the SDK and the result equals that of a run without throttle.
    """
    estate = dict(ONE, counts=dict(functions=12, queues=12), latency_ms=5)
    slow = {"lambda:GetFunctionConfiguration": 30, "sqs:GetQueueAttributes": 30}
    clean = scans(["--concurrency", "64"], per_operation=slow, **estate)
    throttled = scans(
        ["--concurrency", "64"],
        per_operation=slow,
        throttle={"lambda:GetFunctionConfiguration": 1},
        **estate,
    )
    assert throttled.code == 0
    lam = [r for r in throttled.stats["records"] if r[1] == "GetFunctionConfiguration"]
    first_throttle_end = min(r[5] for r in lam if r[3] == "Throttling")
    after = [r for r in lam if r[4] >= first_throttle_end]
    assert after and _overlap(after) <= 2, _overlap(after)
    assert compare.describe_difference(clean.out, throttled.out) is None
