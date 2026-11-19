"""A1 (plan 2.3, 2.6): waiting for a slot ends at the account's time limit
with today's AccountTimeoutError, and at once when the run is stopped.
Fake clock, no sleep."""

import threading

import pytest

from inventag.core.cloud_bom_generator import AccountTimeoutError, _AccountDeadline
from inventag.core.limiter import InFlightLimiter, LimiterStopped


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


class AdvancingWait:
    def __init__(self, clock):
        self.clock = clock
        self.timeouts = []

    def __call__(self, condition, timeout):
        assert timeout is not None and timeout > 0
        self.timeouts.append(timeout)
        self.clock.now += timeout


def _full(limiter):
    return limiter.acquire("999", "s3", "us-east-1")


def test_waiting_ends_at_the_deadline_with_todays_time_limit_error():
    clock = FakeClock()
    wait = AdvancingWait(clock)
    limiter = InFlightLimiter(1, clock=clock, wait=wait)
    deadline = _AccountDeadline("111", 30, clock=clock)
    deadline.start()
    clock.now += 25
    held = _full(limiter)
    with pytest.raises(AccountTimeoutError, match="time limit of 30 seconds"):
        limiter.acquire("111", "ec2", "us-east-1", deadline=deadline)
    assert deadline.expired
    assert clock.now - deadline.started_at > 30
    assert clock.now - deadline.started_at <= 31.0 + 1e-9
    # The waiter left the queue and took nothing.
    assert limiter.in_flight() == 1
    limiter.release(held)
    limiter.release(limiter.acquire("222", "ec2", "us-east-1"))


def test_a_waiter_rechecks_the_deadline_at_least_once_a_second():
    """The main thread can abandon an account without waking the limiter."""
    clock = FakeClock()
    calls = []
    deadline = _AccountDeadline("111", 600, clock=clock)
    deadline.start()

    def wait(condition, timeout):
        calls.append(timeout)
        assert timeout <= 1.0
        clock.now += timeout
        if len(calls) == 3:
            deadline.abandon()

    limiter = InFlightLimiter(1, clock=clock, wait=wait)
    held = _full(limiter)
    with pytest.raises(AccountTimeoutError):
        limiter.acquire("111", "ec2", "us-east-1", deadline=deadline)
    assert len(calls) == 3
    limiter.release(held)


def test_an_abandoned_account_gets_no_slot_even_when_one_is_free():
    clock = FakeClock()
    deadline = _AccountDeadline("111", 600, clock=clock)
    deadline.start()
    deadline.abandon()
    limiter = InFlightLimiter(4, clock=clock)
    with pytest.raises(AccountTimeoutError):
        limiter.acquire("111", "ec2", "us-east-1", deadline=deadline)
    assert limiter.in_flight() == 0


def test_a_finished_deadline_does_not_make_the_waiter_spin():
    """After detach the deadline no longer refuses; waiting falls back to no limit."""
    clock = FakeClock()
    deadline = _AccountDeadline("111", 5, clock=clock)
    deadline.start()
    clock.now += 50
    deadline.detach(object())
    limiter = InFlightLimiter(4, clock=clock)
    limiter.release(limiter.acquire("111", "ec2", "us-east-1", deadline=deadline))


def test_stop_makes_every_waiter_raise_at_once():
    limiter = InFlightLimiter(1, clock=FakeClock())
    held = _full(limiter)
    started = threading.Barrier(4)
    errors = []
    original = limiter._wait

    def wait(condition, timeout):
        if not getattr(threading.current_thread(), "counted", False):
            threading.current_thread().counted = True
            # Release the condition's lock while waiting for the others.
            condition.release()
            try:
                started.wait(10)
            finally:
                condition.acquire()
            return  # a wake-up: acquire checks the stop flag again
        original(condition, timeout)

    limiter._wait = wait

    def run(i):
        try:
            limiter.acquire(f"{i}", "ec2", "us-east-1")
        except LimiterStopped as error:
            errors.append(error)

    threads = [threading.Thread(target=run, args=(i,), daemon=True) for i in range(3)]
    for thread in threads:
        thread.start()
    started.wait(10)
    limiter.stop()
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    assert len(errors) == 3
    assert limiter.in_flight() == 1
    limiter.release(held)
    assert limiter.in_flight() == 0


def test_after_stop_no_new_request_starts():
    limiter = InFlightLimiter(4, clock=FakeClock())
    limiter.stop()
    assert limiter.stopped
    with pytest.raises(LimiterStopped, match="stopped"):
        limiter.acquire("111", "ec2", "us-east-1")
    assert limiter.in_flight() == 0
