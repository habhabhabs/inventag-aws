"""A4: cost estimates are listed in the order of the resources, from a daemon pool."""

import threading
from unittest.mock import Mock

from inventag.discovery.cost_analyzer import CostAnalyzer, ResourceCostEstimate
from decimal import Decimal


def _resources(n=6):
    return [
        {"service": "EC2", "type": "Instance", "id": f"i-{k}", "region": "us-east-1"}
        for k in range(n)
    ]


def _estimate(resource):
    return ResourceCostEstimate(
        resource_id=resource["id"],
        resource_type=resource["type"],
        service=resource["service"],
        region=resource["region"],
        estimated_monthly_cost=Decimal("1.00"),
        cost_breakdown={},
        pricing_model="on-demand",
        cost_factors={},
        confidence_level="high",
    )


def _analyzer():
    return CostAnalyzer(session=Mock())


def test_estimates_follow_the_resource_order_when_workers_finish_in_reverse():
    resources = _resources()
    done = {r["id"]: threading.Event() for r in resources}
    barrier = threading.Barrier(len(resources))
    analyzer = _analyzer()

    def fake(resource):
        barrier.wait(timeout=10)
        index = int(resource["id"].split("-")[1])
        if index + 1 < len(resources):
            assert done[f"i-{index + 1}"].wait(timeout=10)
        done[resource["id"]].set()
        return _estimate(resource)

    analyzer._estimate_single_resource_cost = fake
    got = analyzer.estimate_resource_costs(resources)
    assert [e.resource_id for e in got] == [r["id"] for r in resources]


def test_a_resource_without_an_estimate_or_with_an_error_is_left_out_in_place():
    resources = _resources(5)
    analyzer = _analyzer()

    def fake(resource):
        if resource["id"] == "i-1":
            return None
        if resource["id"] == "i-3":
            raise RuntimeError("no price")
        return _estimate(resource)

    analyzer._estimate_single_resource_cost = fake
    got = analyzer.estimate_resource_costs(resources)
    assert [e.resource_id for e in got] == ["i-0", "i-2", "i-4"]


def test_workers_are_daemon_threads_and_at_most_ten_run_at_once():
    analyzer = _analyzer()
    threads = set()
    lock = threading.Lock()
    now = [0, 0]

    def fake(resource):
        with lock:
            threads.add(threading.current_thread())
            now[0] += 1
            now[1] = max(now[1], now[0])
        with lock:
            now[0] -= 1
        return _estimate(resource)

    analyzer._estimate_single_resource_cost = fake
    analyzer.estimate_resource_costs(_resources(60))
    assert threads and all(t.daemon for t in threads)
    assert len(threads) <= 10 and now[1] <= 10


def test_one_estimate_list_whatever_the_worker_count(monkeypatch):
    import inventag.discovery.cost_analyzer as mod

    resources = _resources(30)
    outputs = []
    for workers in (1, 10):
        analyzer = _analyzer()
        analyzer._estimate_single_resource_cost = _estimate
        monkeypatch.setattr(mod, "_COST_WORKERS", workers)
        outputs.append(
            [e.resource_id for e in analyzer.estimate_resource_costs(resources)]
        )
    assert outputs[0] == outputs[1] == [r["id"] for r in resources]
