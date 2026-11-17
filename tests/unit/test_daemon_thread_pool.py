"""The daemon thread pool behaves like the ThreadPoolExecutor parts InvenTag
uses (A-25): results, exceptions, the worker limit, submission order,
cancelled pending work, and no submit after shutdown."""

import threading
import time

import pytest

from inventag.core.daemon_pool import DaemonThreadPool


def test_results_and_exceptions_reach_the_futures():
    with DaemonThreadPool(2) as pool:
        ok = pool.submit(lambda a, b=0: a + b, 2, b=3)
        bad = pool.submit(lambda: 1 / 0)
        assert ok.result(timeout=5) == 5
        with pytest.raises(ZeroDivisionError):
            bad.result(timeout=5)


def test_threads_are_daemon_and_at_most_max_workers_run():
    running = []
    peak = []
    lock = threading.Lock()
    gate = threading.Event()

    def work():
        with lock:
            running.append(threading.current_thread())
            peak.append(len(running))
        gate.wait(5)
        with lock:
            running.remove(threading.current_thread())
        return threading.current_thread().daemon

    pool = DaemonThreadPool(2)
    futures = [pool.submit(work) for _ in range(5)]
    time.sleep(0.2)
    gate.set()
    assert all(f.result(timeout=5) for f in futures)
    assert max(peak) <= 2
    pool.shutdown(wait=True)


def test_one_worker_takes_work_in_submission_order():
    order = []
    with DaemonThreadPool(1) as pool:
        for i in range(5):
            pool.submit(order.append, i)
    assert order == [0, 1, 2, 3, 4]


def test_shutdown_cancels_pending_work_and_refuses_new_work():
    gate = threading.Event()
    pool = DaemonThreadPool(1)
    first = pool.submit(gate.wait, 5)
    pending = pool.submit(lambda: "never")
    time.sleep(0.1)
    pool.shutdown(wait=False, cancel_futures=True)
    assert pending.cancelled()
    with pytest.raises(RuntimeError):
        pool.submit(lambda: None)
    gate.set()
    assert first.result(timeout=5) is True
