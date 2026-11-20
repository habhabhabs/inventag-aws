"""A3 (plan 2.5): ``_warn_once`` is a check-and-add under a lock (rule T1).

The race is forced, not hoped for: the set that remembers the keys makes its
first two membership tests wait at a barrier after answering. Without a lock
both threads see "not warned" and both warn.
"""

import logging
import threading
from unittest import mock

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery


class _MeetingSet(set):
    """A set whose first two ``in`` tests meet at a barrier after answering."""

    def __init__(self):
        super().__init__()
        self.barrier = threading.Barrier(2, timeout=0.5)
        self._tests = 0
        self._guard = threading.Lock()

    def __contains__(self, item):
        answer = super().__contains__(item)
        with self._guard:
            self._tests += 1
            meets = self._tests <= 2
        if meets:
            try:
                self.barrier.wait()
            except threading.BrokenBarrierError:
                pass  # the other thread was held out by a lock: that is the fix
        return answer


def _disc():
    return ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=["us-east-1"], enable_billing_validation=False
    )


def test_two_threads_with_one_key_warn_once(caplog):
    disc = _disc()
    disc.__dict__["_warned_keys"] = _MeetingSet()
    start = threading.Barrier(2)

    def go():
        start.wait()
        disc._warn_once("denied:s3", "No permission for s3")

    with caplog.at_level(logging.DEBUG, logger=disc.logger.name):
        threads = [threading.Thread(target=go) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    debugs = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert len(warnings) == 1
    assert len(debugs) == 1


def test_different_keys_each_warn_and_a_repeat_is_a_debug_line(caplog):
    disc = _disc()
    with caplog.at_level(logging.DEBUG, logger=disc.logger.name):
        disc._warn_once("a", "first a")
        disc._warn_once("b", "first b")
        disc._warn_once("a", "second a")
    levels = [(r.getMessage(), r.levelno) for r in caplog.records]
    assert levels == [
        ("first a", logging.WARNING),
        ("first b", logging.WARNING),
        ("second a", logging.DEBUG),
    ]
