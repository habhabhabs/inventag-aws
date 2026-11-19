"""A run-wide bound on AWS requests in flight (plan v1.4.0, section 2.3).

One :class:`InFlightLimiter` per run is attached to every boto3 session the
run creates (:meth:`InFlightLimiter.attach`). It acts on botocore's events:

* ``before-send.<service>.<operation>`` fires before each HTTP attempt. The
  limiter's handler is registered first and takes a slot there.
* ``response-received.<service>.<operation>`` fires after each attempt, also
  when the attempt raised. The handler gives the slot back there.

So a call that waits in the SDK's retry backoff holds no slot, and the count
is of real requests in flight. A call that the read-only guard refuses (in
``before-call``) never reaches ``before-send`` and takes no slot. Which slot a
thread holds is kept per thread: a handler that raises before the limiter's
leaves nothing to give back, and nothing that was not taken is given back.

Three caps must all have room: the run (``limit``, ``--concurrency``), the
account (:data:`ACCOUNT_LIMIT`) and the key (account, service, region)
(:data:`KEY_LIMIT`). Waiters are served in arrival order, skipping a waiter
whose account or key is full, so one account cannot starve another.

Throttle feedback: a throttled answer (an error code from botocore's own
throttling table, or HTTP 429) halves the key's limit, not below 1, and no
new request of that key starts before a short pause. After
:data:`GROWTH_AFTER` answers without a throttle the key's limit grows by one,
up to :data:`KEY_LIMIT`. The limiter never retries: the SDK's ``standard``
retry stays the only retry mechanism.

Waiting counts against the account's time limit: the wait ends with the
deadline's own :class:`AccountTimeoutError`. :meth:`InFlightLimiter.stop`
makes every waiter raise :class:`LimiterStopped` and refuses new requests.

Clock, wait and random source are injected, so tests run without real time.
No correctness rests on the GIL: all shared state is read and written under
one condition lock.
"""

import functools
import random
import threading
import time
from collections import defaultdict, deque
from typing import Callable, Optional, Tuple

DEFAULT_LIMIT = 64
ACCOUNT_LIMIT = 16
KEY_LIMIT = 4
GROWTH_AFTER = 10
THROTTLE_PAUSE_SECONDS = 1.0
# A waiter with a time limit looks at it at least this often, so an account
# that the main thread abandons stops waiting without a wake-up call.
DEADLINE_CHECK_SECONDS = 1.0

_THROTTLE_STATUS = 429

Key = Tuple[str, str, Optional[str]]


class LimiterStopped(Exception):
    """The run was stopped; no new AWS request is started."""


def is_throttle(parsed_response, response_dict) -> bool:
    """True when an answer is throttling, by botocore's own table or HTTP 429."""
    from botocore.retries.standard import RetryContext, ThrottledRetryableChecker

    parsed = parsed_response if isinstance(parsed_response, dict) else {}
    if parsed.get("Error"):
        checker = ThrottledRetryableChecker()
        context = RetryContext(attempt_number=1, parsed_response=parsed)
        if checker.is_retryable(context):
            return True
    status = (parsed.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    if status is None and isinstance(response_dict, dict):
        status = response_dict.get("status_code")
    return status == _THROTTLE_STATUS


class _Slot:
    __slots__ = ("account", "key", "released")

    def __init__(self, account: str, key: Key):
        self.account = account
        self.key = key
        self.released = False


class _Waiter:
    __slots__ = ("account", "key")

    def __init__(self, account: str, key: Key):
        self.account = account
        self.key = key


def _condition_wait(condition: threading.Condition, timeout: Optional[float]) -> None:
    condition.wait(timeout)


class InFlightLimiter:
    """Bounds AWS requests in flight for the run, per account and per key."""

    UNIQUE_ID = "inventag-in-flight-limiter"

    def __init__(
        self,
        limit: int = DEFAULT_LIMIT,
        *,
        clock: Callable[[], float] = time.monotonic,
        wait: Callable[[threading.Condition, Optional[float]], None] = _condition_wait,
        rand: Callable[[], float] = random.random,
    ):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError(f"limit must be an integer of at least 1, not {limit!r}")
        self.limit = limit
        self._clock = clock
        self._wait = wait
        self._rand = rand
        self._condition = threading.Condition(threading.Lock())
        self._queue: deque = deque()
        self._total = 0
        self._per_account: dict = defaultdict(int)
        self._per_key: dict = defaultdict(int)
        self._key_limit: dict = {}
        self._good_answers: dict = defaultdict(int)
        self._paused_until: dict = {}
        self._stopped = False
        self._local = threading.local()

    # -- counts -------------------------------------------------------------

    def in_flight(
        self, account: Optional[str] = None, key: Optional[Key] = None
    ) -> int:
        """Slots held now: for the run, one account or one key."""
        with self._condition:
            if key is not None:
                return self._per_key.get(tuple(key), 0)
            if account is not None:
                return self._per_account.get(account, 0)
            return self._total

    def key_limit(self, key: Key) -> int:
        """The current limit of one (account, service, region) key."""
        with self._condition:
            return self._key_limit.get(tuple(key), KEY_LIMIT)

    @property
    def stopped(self) -> bool:
        with self._condition:
            return self._stopped

    # -- taking and giving back slots ----------------------------------------

    def _admissible(self, waiter: _Waiter, now: float) -> bool:
        return (
            self._per_account[waiter.account] < ACCOUNT_LIMIT
            and self._per_key[waiter.key] < self._key_limit.get(waiter.key, KEY_LIMIT)
            and now >= self._paused_until.get(waiter.key, now)
        )

    def _may_go(self, waiter: _Waiter, now: float) -> bool:
        """Room in all three caps, and no earlier waiter that could go first."""
        if self._total >= self.limit:
            return False
        for earlier in self._queue:
            if earlier is waiter:
                return self._admissible(waiter, now)
            if self._admissible(earlier, now):
                return False
        return False  # pragma: no cover - the waiter is always in the queue

    def _timeout(self, key: Key, deadline, now: float) -> Optional[float]:
        timeouts = []
        paused_until = self._paused_until.get(key)
        if paused_until is not None and paused_until > now:
            timeouts.append(paused_until - now)
        if deadline is not None and getattr(deadline, "active", False):
            remaining = deadline.remaining()
            if remaining > 0:
                timeouts.append(min(remaining, DEADLINE_CHECK_SECONDS))
            else:
                timeouts.append(DEADLINE_CHECK_SECONDS)
        return min(timeouts) if timeouts else None

    def acquire(
        self, account: str, service: str, region: Optional[str], deadline=None
    ) -> _Slot:
        """Wait for a slot; return it. ``deadline`` is the account's time limit.

        Raises :class:`LimiterStopped` after :meth:`stop`, and the deadline's
        own error (``AccountTimeoutError``) when the account reaches its limit
        or is abandoned while waiting.
        """
        key: Key = (account, service, region)
        waiter = _Waiter(account, key)
        with self._condition:
            self._queue.append(waiter)
            try:
                while True:
                    if self._stopped:
                        raise LimiterStopped(
                            "The run was stopped; no new AWS request is started."
                        )
                    if deadline is not None:
                        deadline.before_call()  # raises at the limit or when abandoned
                    now = self._clock()
                    if self._may_go(waiter, now):
                        self._total += 1
                        self._per_account[account] += 1
                        self._per_key[key] += 1
                        return _Slot(account, key)
                    self._wait(self._condition, self._timeout(key, deadline, now))
            finally:
                self._queue.remove(waiter)
                self._condition.notify_all()

    def release(
        self, slot: _Slot, throttled: bool = False, answered: bool = True
    ) -> None:
        """Give a slot back; ``throttled`` and ``answered`` drive the key's limit."""
        with self._condition:
            if slot.released:
                return
            slot.released = True
            self._total -= 1
            self._per_account[slot.account] -= 1
            self._per_key[slot.key] -= 1
            if throttled:
                self._on_throttle(slot.key)
            elif answered:
                self._on_good_answer(slot.key)
            self._condition.notify_all()

    def _on_throttle(self, key: Key) -> None:
        self._key_limit[key] = max(1, self._key_limit.get(key, KEY_LIMIT) // 2)
        self._good_answers[key] = 0
        pause = THROTTLE_PAUSE_SECONDS * (0.5 + 0.5 * self._rand())
        self._paused_until[key] = self._clock() + pause

    def _on_good_answer(self, key: Key) -> None:
        current = self._key_limit.get(key, KEY_LIMIT)
        if current >= KEY_LIMIT:
            return
        self._good_answers[key] += 1
        if self._good_answers[key] >= GROWTH_AFTER:
            self._key_limit[key] = current + 1
            self._good_answers[key] = 0

    def stop(self) -> None:
        """Every waiter raises :class:`LimiterStopped`; no new request starts."""
        with self._condition:
            self._stopped = True
            self._condition.notify_all()

    # -- botocore events ------------------------------------------------------

    def _hook_id(self, account_id: str, event: str) -> str:
        return f"{self.UNIQUE_ID}-{event}-{id(self)}-{account_id}"

    def attach(self, session, account_id: str, deadline=None) -> None:
        """Register the limiter on a session. Affects clients created later."""
        events = session.events
        events.register_first(
            "before-send",
            functools.partial(self._on_before_send, account_id, deadline),
            unique_id=self._hook_id(account_id, "send"),
        )
        events.register_first(
            "response-received",
            self._on_response_received,
            unique_id=self._hook_id(account_id, "response"),
        )

    def detach(self, session, account_id: str) -> None:
        events = session.events
        events.unregister("before-send", unique_id=self._hook_id(account_id, "send"))
        events.unregister(
            "response-received", unique_id=self._hook_id(account_id, "response")
        )

    def _on_before_send(
        self, account_id, deadline, request=None, event_name="", **kwargs
    ):
        # A slot left by a request that a BaseException (Ctrl-C) cut off
        # between the two events: this thread is no longer using it.
        self._give_back_held(throttled=False, answered=False)
        parts = (event_name or "").split(".")
        service = parts[1] if len(parts) > 1 else ""
        context = getattr(request, "context", None) or {}
        region = context.get("client_region")
        self._local.slot = self.acquire(account_id, service, region, deadline)

    def _on_response_received(
        self, parsed_response=None, response_dict=None, exception=None, **kwargs
    ):
        answered = parsed_response is not None or response_dict is not None
        self._give_back_held(
            throttled=answered and is_throttle(parsed_response, response_dict),
            answered=answered,
        )

    def _give_back_held(self, throttled: bool, answered: bool) -> None:
        slot = getattr(self._local, "slot", None)
        if slot is None:
            return
        self._local.slot = None
        self.release(slot, throttled=throttled, answered=answered)
