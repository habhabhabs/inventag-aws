"""A3 (plan 2.5, rule T1): the account id is read once, also when listing
workers ask for it at the same time.

The race is forced: the first two callers of ``get_caller_identity`` meet at a
barrier inside the call. Without a lock both are inside; with one, the second
waits outside, the barrier breaks after its bound, and one call is made.
"""

import threading
from unittest import mock

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery


class _Sts:
    def __init__(self):
        self.calls = 0
        self._lock = threading.Lock()
        self.barrier = threading.Barrier(2, timeout=0.5)

    def get_caller_identity(self):
        with self._lock:
            self.calls += 1
        try:
            self.barrier.wait()
        except threading.BrokenBarrierError:
            pass  # the other caller was held out by a lock: that is the fix
        return {"Account": "111122223333"}


def test_two_threads_ask_for_the_account_id_and_one_call_is_made():
    sts = _Sts()
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=["us-east-1"], enable_billing_validation=False
    )
    disc._client = lambda *a, **k: sts
    start = threading.Barrier(2)
    answers = []

    def go():
        start.wait()
        answers.append(disc._get_account_id())

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert answers == ["111122223333", "111122223333"]
    assert sts.calls == 1
