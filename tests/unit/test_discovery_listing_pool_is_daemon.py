"""A-25 (discovery part): the listing pool does not keep the process alive.

Lead A's ``inventag/core/daemon_pool.py`` provides ``DaemonThreadPool``. Discovery
uses it for its listing pool and its per-region Tagging API pool, so a listing
still waiting on the network after the account's limit does not hold the
process at exit (harness row B10).
"""

from unittest import mock

from inventag.discovery import comprehensive_discovery as cd


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


def test_the_listing_pool_is_a_daemon_pool(monkeypatch):
    seen, _ = _run_and_get_pool_types(monkeypatch)
    assert seen == ["DaemonThreadPool"]
