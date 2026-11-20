"""Run independent tasks in a daemon pool; take the answers in input order.

Analyses read AWS once per region (or once per resource). The tasks run at the
same time, but the caller must see the same result whatever order they finish
in. So no task writes to shared state: each returns its answer, and the
calling thread reads the answers in the order of the input (rule T1, plan 2.4).

The workers are daemon threads (``DaemonThreadPool``): when the caller is
stopped, queued tasks are cancelled and a task that still waits on the network
is cut off at exit instead of keeping the process alive.
"""

import contextvars
from concurrent.futures import Future
from typing import Any, Callable, Iterable, List, Optional, Tuple


def _result_of(future: Future) -> Any:
    return future.result()


def run_ordered(
    fn: Callable[[Any], Any],
    items: Iterable[Any],
    max_workers: int,
    name: str = "inventag-analysis",
) -> List[Tuple[Any, Optional[BaseException]]]:
    """``(value, error)`` of ``fn(item)`` for each item, in the order of ``items``.

    An ``Exception`` raised by ``fn`` is returned at its place and does not stop
    the other tasks; the caller decides what it means. Anything else (an
    interrupt of the calling thread) cancels the queued tasks and propagates.
    Each task runs in a copy of the caller's context, so the account name in
    the log lines reaches the workers.
    """
    # Imported here: inventag.core imports the reporting package, which
    # imports the analyzers, which import this module.
    from ..core.daemon_pool import DaemonThreadPool

    items = list(items)
    if not items:
        return []
    pool = DaemonThreadPool(min(max(1, int(max_workers)), len(items)), name)
    try:
        futures = [
            pool.submit(contextvars.copy_context().run, fn, item) for item in items
        ]
        answers: List[Tuple[Any, Optional[BaseException]]] = []
        for future in futures:
            try:
                answers.append((_result_of(future), None))
            except Exception as error:  # silent-ok: handed back to the caller
                answers.append((None, error))
    except BaseException:
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    return answers
