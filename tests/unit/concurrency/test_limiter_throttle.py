"""A1 (plan 2.3): throttle feedback. A throttled answer halves the key's limit
(not below 1) and pauses new requests of that key; ten answers without a
throttle grow the limit by one, up to the key cap. Fake clock, no sleep."""

import pytest
from botocore.retries import standard

from inventag.core.limiter import (
    GROWTH_AFTER,
    KEY_LIMIT,
    THROTTLE_PAUSE_SECONDS,
    InFlightLimiter,
    is_throttle,
)

KEY = ("111", "lambda", "us-east-1")


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


class AdvancingWait:
    """Waiting moves the fake clock by the timeout; records each timeout."""

    def __init__(self, clock):
        self.clock = clock
        self.timeouts = []

    def __call__(self, condition, timeout):
        assert timeout is not None and timeout > 0, "would wait forever"
        self.timeouts.append(timeout)
        self.clock.now += timeout


def _limiter(rand=lambda: 1.0):
    clock = FakeClock()
    wait = AdvancingWait(clock)
    return InFlightLimiter(64, clock=clock, wait=wait, rand=rand), clock, wait


def _answer(limiter, throttled):
    slot = limiter.acquire(*KEY)
    limiter.release(slot, throttled=throttled)


def test_a_throttle_halves_the_key_limit_and_never_below_one():
    limiter, clock, _ = _limiter()
    assert limiter.key_limit(KEY) == KEY_LIMIT == 4
    _answer(limiter, throttled=True)
    assert limiter.key_limit(KEY) == 2
    clock.now += 10
    _answer(limiter, throttled=True)
    assert limiter.key_limit(KEY) == 1
    clock.now += 10
    _answer(limiter, throttled=True)
    assert limiter.key_limit(KEY) == 1


def test_a_throttle_changes_only_its_own_key():
    limiter, _, _ = _limiter()
    _answer(limiter, throttled=True)
    assert limiter.key_limit(("111", "lambda", "eu-west-1")) == 4
    assert limiter.key_limit(("111", "s3", "us-east-1")) == 4
    assert limiter.key_limit(("222", "lambda", "us-east-1")) == 4
    # And another key starts at once, without the pause.
    slot = limiter.acquire("111", "s3", "us-east-1")
    limiter.release(slot)


def test_after_a_throttle_no_new_request_of_the_key_starts_before_the_pause():
    limiter, clock, wait = _limiter(rand=lambda: 1.0)
    _answer(limiter, throttled=True)
    start = clock.now
    slot = limiter.acquire(*KEY)
    assert clock.now - start == pytest.approx(THROTTLE_PAUSE_SECONDS)
    assert sum(wait.timeouts) == pytest.approx(THROTTLE_PAUSE_SECONDS)
    limiter.release(slot)


def test_the_pause_has_jitter_from_the_injected_random_source():
    limiter, clock, _ = _limiter(rand=lambda: 0.0)
    _answer(limiter, throttled=True)
    start = clock.now
    limiter.release(limiter.acquire(*KEY))
    assert clock.now - start == pytest.approx(THROTTLE_PAUSE_SECONDS / 2)


def test_ten_answers_without_a_throttle_grow_the_limit_by_one_up_to_the_cap():
    limiter, clock, _ = _limiter()
    _answer(limiter, throttled=True)
    clock.now += 10
    _answer(limiter, throttled=True)
    assert limiter.key_limit(KEY) == 1
    for _ in range(GROWTH_AFTER - 1):
        _answer(limiter, throttled=False)
    assert limiter.key_limit(KEY) == 1
    _answer(limiter, throttled=False)
    assert limiter.key_limit(KEY) == 2
    for _ in range(GROWTH_AFTER * 5):
        _answer(limiter, throttled=False)
    assert limiter.key_limit(KEY) == KEY_LIMIT


def test_a_throttle_resets_the_count_of_good_answers():
    limiter, clock, _ = _limiter()
    _answer(limiter, throttled=True)
    for _ in range(GROWTH_AFTER - 1):
        _answer(limiter, throttled=False)
    clock.now += 10
    _answer(limiter, throttled=True)
    assert limiter.key_limit(KEY) == 1
    for _ in range(GROWTH_AFTER - 1):
        _answer(limiter, throttled=False)
    assert limiter.key_limit(KEY) == 1


def test_a_lowered_key_limit_blocks_the_next_request_of_that_key():
    limiter, clock, _ = _limiter()
    _answer(limiter, throttled=True)
    clock.now += 10
    _answer(limiter, throttled=True)
    held = limiter.acquire(*KEY)
    blocked = []

    def wait(condition, timeout):
        blocked.append(timeout)
        raise RuntimeError("blocked")

    limiter._wait = wait
    with pytest.raises(RuntimeError):
        limiter.acquire(*KEY)
    assert blocked
    limiter.release(held)


@pytest.mark.parametrize(
    "code",
    [
        "Throttling",
        "ThrottlingException",
        "TooManyRequestsException",
        "RequestLimitExceeded",
        "SlowDown",
    ],
)
def test_the_throttle_codes_of_the_plan_are_recognised(code):
    assert is_throttle({"Error": {"Code": code}}, None)


def test_http_429_is_a_throttle_and_other_errors_are_not():
    assert is_throttle({"ResponseMetadata": {"HTTPStatusCode": 429}}, None)
    assert is_throttle(None, {"status_code": 429})
    assert not is_throttle({"Error": {"Code": "AccessDenied"}}, {"status_code": 403})
    assert not is_throttle({"ResponseMetadata": {"HTTPStatusCode": 200}}, None)
    assert not is_throttle(None, None)


def test_the_codes_are_read_from_botocore_at_run_time(monkeypatch):
    """Not a copied list: a code botocore adds is recognised without a change here."""
    assert not is_throttle({"Error": {"Code": "BrandNewThrottle"}}, None)
    monkeypatch.setattr(
        standard.ThrottledRetryableChecker,
        "_THROTTLED_ERROR_CODES",
        standard.ThrottledRetryableChecker._THROTTLED_ERROR_CODES
        + ["BrandNewThrottle"],
    )
    assert is_throttle({"Error": {"Code": "BrandNewThrottle"}}, None)
