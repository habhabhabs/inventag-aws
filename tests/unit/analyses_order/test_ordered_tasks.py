"""A4: run tasks in a daemon pool, take the answers in submission order."""

import contextvars
import threading

import pytest

from inventag.discovery.ordered_tasks import run_ordered

_var = contextvars.ContextVar("a4_var", default="unset")


def test_answers_follow_the_input_order_not_the_finish_order():
    items = list(range(6))
    done = {i: threading.Event() for i in items}
    barrier = threading.Barrier(len(items))

    def work(i):
        barrier.wait(timeout=10)
        if i + 1 < len(items):
            assert done[i + 1].wait(timeout=10)
        done[i].set()
        return i * 10

    got = run_ordered(work, items, max_workers=len(items))
    assert got == [(i * 10, None) for i in items]


def test_one_worker_and_many_workers_give_the_same_answers():
    def work(i):
        return {"n": i, "sq": i * i}

    items = list(range(25))
    assert run_ordered(work, items, 1) == run_ordered(work, items, 7)


def test_a_failure_stays_at_its_place_and_does_not_stop_the_others():
    def work(i):
        if i == 2:
            raise ValueError("two")
        return i

    got = run_ordered(work, [0, 1, 2, 3], max_workers=2)
    assert [value for value, _ in got] == [0, 1, None, 3]
    assert isinstance(got[2][1], ValueError)
    assert got[0][1] is None


def test_workers_are_daemon_threads_and_at_most_max_workers_run_at_once():
    seen = set()
    lock = threading.Lock()
    running = [0, 0]  # now, peak

    def work(i):
        with lock:
            seen.add(threading.current_thread())
            running[0] += 1
            running[1] = max(running[1], running[0])
        with lock:
            running[0] -= 1

    run_ordered(work, range(40), max_workers=3)
    assert seen and all(t.daemon for t in seen)
    assert len(seen) <= 3
    assert running[1] <= 3


def test_the_log_context_of_the_caller_reaches_the_workers():
    _var.set("account-1")
    got = run_ordered(lambda i: _var.get(), range(4), max_workers=2)
    assert [value for value, _ in got] == ["account-1"] * 4


def test_nothing_to_do_starts_no_thread():
    before = threading.active_count()
    assert run_ordered(lambda i: i, [], max_workers=4) == []
    assert threading.active_count() == before


def test_an_interrupt_while_waiting_cancels_the_queued_tasks(monkeypatch):
    import inventag.discovery.ordered_tasks as mod

    release = threading.Event()
    started = threading.Event()
    ran = []

    def work(i):
        ran.append(i)
        started.set()
        release.wait(timeout=10)
        return i

    class Interrupt(BaseException):
        pass

    def interrupted(future):
        # the coordinating thread is stopped while it waits for the answer
        started.wait(timeout=10)
        raise Interrupt()

    monkeypatch.setattr(mod, "_result_of", interrupted)
    try:
        with pytest.raises(Interrupt):
            run_ordered(work, range(10), max_workers=1)
    finally:
        release.set()
    assert ran == [0]
