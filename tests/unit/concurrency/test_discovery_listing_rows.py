"""A3 (plan 2.4 rule 1, 2.5): listing workers hand their rows to the
coordinating thread, which merges them in task submission order.

The completion order is forced with events, not with sleeps: task 3 ends first,
then task 2, then task 1. The rows must still come out as task 1, 2, 3.
"""

import threading
from unittest import mock

from inventag.discovery import coverage as coverage_mod
from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

R = "us-east-1"
WAIT = 10  # an upper bound for a test that would otherwise hang, never a pause


class _Client:
    """A client whose one list call answers from a script."""

    def __init__(self, script):
        self.script = script
        self.meta = mock.MagicMock()
        self.meta.method_to_api_mapping = {}

    def can_paginate(self, name):
        return False

    def __getattr__(self, name):
        if name.startswith("list_"):
            return self.script
        raise AttributeError(name)


def _disc(services, **kwargs):
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(),
        regions=[R],
        enable_billing_validation=False,
        **kwargs,
    )
    disc.service_discovery_patterns = {
        name: {"operations": [("list_things", "Things", "Thing")], "regional": True}
        for name in services
    }
    return disc


def _names(disc):
    return [r["resource_id"] for r in disc.resources]


def test_rows_are_merged_in_task_order_not_completion_order():
    names = ["svc_a", "svc_b", "svc_c"]
    disc = _disc(names)
    finished = {n: threading.Event() for n in names}
    waits_for = {"svc_a": "svc_b", "svc_b": "svc_c", "svc_c": None}

    def client_for(service, region=None):
        def listing(**kwargs):
            other = waits_for[service]
            if other:
                assert finished[other].wait(WAIT)
            return {"Things": [{"Name": f"{service}-1"}, {"Name": f"{service}-2"}]}

        return _Client(listing)

    disc._client = client_for
    real = disc._discover_service_in_region

    def wrapped(task):
        try:
            return real(task)
        finally:
            finished[task["service"]].set()

    with mock.patch.object(disc, "_discover_service_in_region", side_effect=wrapped):
        disc._discover_all_service_resources(max_workers=3)

    assert _names(disc) == [
        "svc_a-1",
        "svc_a-2",
        "svc_b-1",
        "svc_b-2",
        "svc_c-1",
        "svc_c-2",
    ]
    assert disc.services_with_primary_resources == set(names)
    assert disc.discovered_services == set(names)


def test_workers_do_not_write_the_shared_list():
    """While a task runs, its rows are not in ``resources``: the second
    listing of the task looks, after the first listing added a row."""
    disc = _disc(["svc_a"])
    disc.service_discovery_patterns["svc_a"]["operations"] = [
        ("list_things", "Things", "Thing"),
        ("list_others", "Others", "Other"),
    ]
    seen = []

    def client_for(service, region=None):
        class Two(_Client):
            def __getattr__(self, name):
                if name == "list_things":
                    return lambda **kw: {"Things": [{"Name": "one"}]}
                if name == "list_others":

                    def others(**kw):
                        seen.append(len(disc.resources))
                        return {"Others": [{"Name": "two"}]}

                    return others
                raise AttributeError(name)

        return Two(None)

    disc._client = client_for
    disc._discover_all_service_resources(max_workers=1)
    assert seen == [0]
    assert _names(disc) == ["one", "two"]


def test_rows_found_before_the_time_limit_are_kept_and_later_ones_are_not():
    disc = _disc(["fast", "slow"], discovery_timeout=0.2)
    release = threading.Event()
    slow_done = threading.Event()

    def client_for(service, region=None):
        def listing(**kwargs):
            if service == "slow":
                assert release.wait(WAIT)
            return {"Things": [{"Name": f"{service}-row"}]}

        return _Client(listing)

    disc._client = client_for
    real = disc._discover_service_in_region

    def wrapped(task):
        try:
            return real(task)
        finally:
            if task["service"] == "slow":
                slow_done.set()

    try:
        with mock.patch.object(
            disc, "_discover_service_in_region", side_effect=wrapped
        ):
            disc._discover_all_service_resources(max_workers=2)
        at_the_limit = [
            e.service
            for e in disc.coverage.entries
            if e.outcome == coverage_mod.TIMEOUT
        ]
    finally:
        release.set()
    assert slow_done.wait(WAIT)
    assert at_the_limit == ["slow"]
    # the slow worker ended after the limit and added nothing
    assert _names(disc) == ["fast-row"]
