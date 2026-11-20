"""A thread pool whose threads the interpreter does not wait for at exit (A-25).

``concurrent.futures.ThreadPoolExecutor`` threads are joined when the
interpreter exits. InvenTag abandons an account at its time limit and
ignores whatever its worker returns later; with a ThreadPoolExecutor a
worker that still waits on a network call keeps the whole process alive
after the summary (harness row B10). The threads here are daemon threads:
at exit the process ends, and an abandoned call is cut off. They are only
for read-only work whose result may be dropped.

Same interface as the parts of ThreadPoolExecutor that InvenTag uses:
``submit``, ``shutdown(wait, cancel_futures)``, use as a context manager.
Work is taken in submission order; at most ``max_workers`` run at once.
Each task runs in a copy of the submitter's context (``contextvars``), so a
worker logs with the account of the scan that submitted it
(``core/log_context.py``); what a task changes in it stays in that task.
"""

import contextvars
import itertools
import queue
import threading
from concurrent.futures import Future
from typing import Any, Callable, List, Optional

_names = itertools.count()


class DaemonThreadPool:
    def __init__(self, max_workers: int, thread_name_prefix: str = "inventag"):
        self._max_workers = max(1, int(max_workers or 1))
        self._prefix = f"{thread_name_prefix}-{next(_names)}"
        self._work: "queue.SimpleQueue[Optional[tuple]]" = queue.SimpleQueue()
        self._threads: List[threading.Thread] = []
        self._idle = threading.Semaphore(0)
        self._lock = threading.Lock()
        self._shut = False

    def submit(self, fn: Callable[..., Any], *args, **kwargs) -> Future:
        future: Future = Future()
        with self._lock:
            if self._shut:
                raise RuntimeError("cannot schedule new futures after shutdown")
            context = contextvars.copy_context()
            self._work.put((future, context.run, (fn, *args), kwargs))
            if not self._idle.acquire(blocking=False) and (
                len(self._threads) < self._max_workers
            ):
                thread = threading.Thread(
                    target=self._run,
                    name=f"{self._prefix}_{len(self._threads)}",
                    daemon=True,
                )
                self._threads.append(thread)
                thread.start()
        return future

    def _run(self) -> None:
        while True:
            item = self._work.get()
            if item is None:
                return
            future, fn, args, kwargs = item
            if future.set_running_or_notify_cancel():
                try:
                    result = fn(*args, **kwargs)
                except BaseException as error:  # handed to the caller
                    future.set_exception(error)
                else:
                    future.set_result(result)
            self._idle.release()

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        with self._lock:
            self._shut = True
            threads = list(self._threads)
        if cancel_futures:
            pending = []
            while True:
                try:
                    item = self._work.get_nowait()
                except queue.Empty:
                    break
                if item is not None:
                    pending.append(item[0])
            for future in pending:
                future.cancel()
        for _ in threads:
            self._work.put(None)
        if wait:
            for thread in threads:
                thread.join()

    def __enter__(self) -> "DaemonThreadPool":
        return self

    def __exit__(self, *exc) -> None:
        self.shutdown(wait=True)
