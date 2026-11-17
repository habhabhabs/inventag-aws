"""A-25 (discovery part): the listing pool does not keep the process alive.

Lead A's ``inventag/core/daemon_pool.py`` provides ``DaemonThreadPool``. Discovery
uses it for its listing pool and its per-region Tagging API pool when the module
is there, so a listing still waiting on the network after the account's limit
does not hold the process at exit (harness row B10). Without the module (a
branch that has not got it yet) discovery uses ``ThreadPoolExecutor`` as before.
"""

import importlib.util
import sys
from unittest import mock

import pytest

from inventag.discovery import comprehensive_discovery as cd

HAS_POOL = importlib.util.find_spec("inventag.core.daemon_pool") is not None
NEED_POOL = pytest.mark.skipif(
    not HAS_POOL,
    reason="inventag/core/daemon_pool.py (lead A, A-25) is not on this branch; "
    "the assembly runs this test with it",
)


def _disc():
    return cd.ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=["us-east-1"], enable_billing_validation=False
    )


def _run_and_get_pool_types(monkeypatch):
    seen = []
    disc = _disc()
    monkeypatch.setattr(disc, "_discover_service_in_region", lambda task: 0)
    original = cd.ThreadPoolExecutor
    orig_make = disc._make_pool

    def spy(workers):
        pool = orig_make(workers)
        seen.append(type(pool).__name__)
        return pool

    monkeypatch.setattr(disc, "_make_pool", spy)
    disc._discover_all_service_resources(2)
    return seen, original


@NEED_POOL
def test_the_listing_pool_is_a_daemon_pool(monkeypatch):
    seen, _ = _run_and_get_pool_types(monkeypatch)
    assert seen == ["DaemonThreadPool"]


def test_without_the_module_the_listing_pool_is_a_thread_pool_executor(monkeypatch):
    monkeypatch.setitem(sys.modules, "inventag.core.daemon_pool", None)
    seen, _ = _run_and_get_pool_types(monkeypatch)
    assert seen == ["ThreadPoolExecutor"]
