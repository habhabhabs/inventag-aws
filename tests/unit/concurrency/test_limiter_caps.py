"""A1 (plan 2.3): the run, account and key caps of the in-flight limiter.

Fake clock, no sleep. Threads are used only where waiting is the behaviour
under test; they are sequenced with events, never with ``time.sleep``.
"""

import threading

import pytest

from inventag.core.limiter import (
    ACCOUNT_LIMIT,
    DEFAULT_LIMIT,
    KEY_LIMIT,
    InFlightLimiter,
)


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


def _never_wait(condition, timeout):
    raise AssertionError("acquire waited although a slot was free")


def test_the_defaults_are_the_plan_values():
    assert (DEFAULT_LIMIT, ACCOUNT_LIMIT, KEY_LIMIT) == (64, 16, 4)
    limiter = InFlightLimiter()
    assert limiter.limit == 64


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "8", None])
def test_a_limit_below_one_or_not_an_integer_is_refused(bad):
    with pytest.raises(ValueError):
        InFlightLimiter(bad)


def test_a_slot_is_counted_while_held_and_freed_on_release():
    limiter = InFlightLimiter(4, clock=FakeClock(), wait=_never_wait)
    slot = limiter.acquire("111", "s3", "us-east-1")
    assert limiter.in_flight() == 1
    assert limiter.in_flight(account="111") == 1
    assert limiter.in_flight(key=("111", "s3", "us-east-1")) == 1
    limiter.release(slot)
    assert limiter.in_flight() == 0
    assert limiter.in_flight(account="111") == 0


def test_releasing_a_slot_twice_frees_it_once():
    limiter = InFlightLimiter(4, clock=FakeClock(), wait=_never_wait)
    first = limiter.acquire("111", "s3", "us-east-1")
    limiter.acquire("111", "s3", "us-east-1")
    limiter.release(first)
    limiter.release(first)
    assert limiter.in_flight() == 1


def _blocked(limiter, account, service, region):
    """True when acquire would have to wait (the wait raises at once)."""

    class _Blocked(Exception):
        pass

    def wait(condition, timeout):
        raise _Blocked

    saved = limiter._wait
    limiter._wait = wait
    try:
        slot = limiter.acquire(account, service, region)
    except _Blocked:
        return True
    finally:
        limiter._wait = saved
    limiter.release(slot)
    return False


def test_the_run_cap_holds_across_accounts():
    limiter = InFlightLimiter(3, clock=FakeClock(), wait=_never_wait)
    held = [
        limiter.acquire("111", "s3", "us-east-1"),
        limiter.acquire("222", "ec2", "us-east-1"),
        limiter.acquire("333", "rds", "eu-west-1"),
    ]
    assert _blocked(limiter, "444", "lambda", "us-east-1")
    limiter.release(held[0])
    assert not _blocked(limiter, "444", "lambda", "us-east-1")
    assert limiter.in_flight() == 2


def test_the_account_cap_is_16_and_other_accounts_still_get_slots():
    limiter = InFlightLimiter(64, clock=FakeClock(), wait=_never_wait)
    services = [f"svc{i}" for i in range(ACCOUNT_LIMIT)]
    for service in services:
        limiter.acquire("111", service, "us-east-1")
    assert limiter.in_flight(account="111") == 16
    assert _blocked(limiter, "111", "another", "us-east-1")
    assert not _blocked(limiter, "222", "another", "us-east-1")


def test_the_key_cap_is_4_per_account_service_and_region():
    limiter = InFlightLimiter(64, clock=FakeClock(), wait=_never_wait)
    for _ in range(KEY_LIMIT):
        limiter.acquire("111", "s3", "us-east-1")
    assert _blocked(limiter, "111", "s3", "us-east-1")
    assert not _blocked(limiter, "111", "s3", "eu-west-1")
    assert not _blocked(limiter, "111", "lambda", "us-east-1")
    assert not _blocked(limiter, "222", "s3", "us-east-1")


def test_concurrency_one_allows_one_request_in_the_whole_run():
    limiter = InFlightLimiter(1, clock=FakeClock(), wait=_never_wait)
    slot = limiter.acquire("111", "s3", "us-east-1")
    assert _blocked(limiter, "222", "ec2", "eu-west-1")
    limiter.release(slot)
    assert not _blocked(limiter, "222", "ec2", "eu-west-1")


class _Gate:
    """An injected wait that tells the test when a thread starts waiting."""

    def __init__(self):
        self.waiting = {}
        self.lock = threading.Lock()

    def expect(self, name):
        event = threading.Event()
        with self.lock:
            self.waiting[name] = event
        return event

    def __call__(self, condition, timeout):
        name = threading.current_thread().name
        with self.lock:
            event = self.waiting.get(name)
        if event is not None:
            event.set()
        condition.wait(timeout)


def _start(limiter, name, account, service, region, order, ready):
    def run():
        slot = limiter.acquire(account, service, region)
        order.append(name)
        limiter.release(slot)

    thread = threading.Thread(target=run, name=name, daemon=True)
    event = ready.expect(name)
    thread.start()
    assert event.wait(10), f"{name} never waited"
    return thread


def test_waiters_are_served_in_arrival_order():
    gate = _Gate()
    limiter = InFlightLimiter(1, clock=FakeClock(), wait=gate)
    holder = limiter.acquire("111", "s3", "us-east-1")
    order = []
    threads = [
        _start(limiter, f"w{i}", f"{i}{i}{i}", "ec2", "us-east-1", order, gate)
        for i in range(1, 5)
    ]
    limiter.release(holder)
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    assert order == ["w1", "w2", "w3", "w4"]


def test_a_waiter_whose_key_is_full_is_skipped_not_waited_for():
    gate = _Gate()
    limiter = InFlightLimiter(64, clock=FakeClock(), wait=gate)
    held = [limiter.acquire("111", "s3", "us-east-1") for _ in range(KEY_LIMIT)]
    order = []
    blocked = _start(limiter, "same-key", "111", "s3", "us-east-1", order, gate)
    # A later request of another key is not held up by the blocked waiter.
    slot = limiter.acquire("111", "lambda", "us-east-1")
    assert order == []
    limiter.release(slot)
    limiter.release(held[0])
    blocked.join(10)
    assert not blocked.is_alive()
    assert order == ["same-key"]


def test_an_account_at_its_cap_does_not_block_other_accounts_in_the_queue():
    gate = _Gate()
    limiter = InFlightLimiter(17, clock=FakeClock(), wait=gate)
    held = [limiter.acquire("111", f"svc{i}", "us-east-1") for i in range(16)]
    order = []
    first = _start(limiter, "a-111", "111", "more", "us-east-1", order, gate)
    slot = limiter.acquire("222", "s3", "us-east-1")  # the 17th slot of the run
    assert order == []
    limiter.release(slot)
    limiter.release(held[0])
    first.join(10)
    assert order == ["a-111"]
