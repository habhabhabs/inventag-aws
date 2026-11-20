"""A2 (plan 2.5, A1 finding 5): work submitted to a ``DaemonThreadPool`` runs
in a copy of the submitter's context, so the account of a log line
(``core/log_context.py``, a ``ContextVar``) is the account whose scan
submitted the work. A worker's own changes to the context stay in the worker.
"""

import logging
from contextvars import ContextVar

from inventag.core.daemon_pool import DaemonThreadPool
from inventag.core.log_context import account_log_context, current_account

_marker: ContextVar = ContextVar("a2_test_marker", default="unset")


def test_a_worker_sees_the_context_of_the_submitting_thread():
    with DaemonThreadPool(2) as pool:
        with account_log_context("111111111111", "payments"):
            inside = pool.submit(current_account).result(30)
        outside = pool.submit(current_account).result(30)
    assert inside == {"account_id": "111111111111", "account_name": "payments"}
    assert outside is None


def test_each_task_gets_its_own_copy_and_changes_stay_in_the_worker():
    def change():
        before = _marker.get()
        _marker.set("changed by the worker")
        return before

    with DaemonThreadPool(1) as pool:
        token = _marker.set("first")
        try:
            assert pool.submit(change).result(30) == "first"
            assert _marker.get() == "first"
            _marker.set("second")
            # The same worker thread, a new copy of the submitter's context.
            assert pool.submit(change).result(30) == "second"
        finally:
            _marker.reset(token)


def test_log_lines_of_a_worker_carry_the_account_of_the_scan():
    import io

    from inventag.cli.logging_setup import AccountSpecificFormatter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(AccountSpecificFormatter("%(account_prefix)s%(message)s"))
    logger = logging.getLogger("inventag.test.pool_log_context")
    logger.addHandler(handler)
    logger.propagate = False
    try:
        with DaemonThreadPool(2) as pool:
            with account_log_context("222222222222", "shared"):
                pool.submit(logger.warning, "listing failed").result(30)
    finally:
        logger.removeHandler(handler)
        logger.propagate = True
    assert stream.getvalue() == "[shared] listing failed\n"
