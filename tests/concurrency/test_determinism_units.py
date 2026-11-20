"""A5, plan 2.4 and 2.5: the small rules of determinism, as fast in-process tests.

Each test forces one interleaving with events and a barrier (no sleep) and asks
for the rule of the plan. They are written before the code of A3 and A4 exists:
a row that v1.3.0 breaks is expected to fail, with the work order that fixes it
in its reason; ``strict`` makes it fail loudly when it starts to pass, so that
the mark is removed in the same change.
"""

import threading

import pytest

from tests.concurrency import harness  # noqa: F401  (the package must import)


class _Log:
    def __init__(self):
        self.warnings, self.debugs = [], []

    def warning(self, message, *a, **k):
        self.warnings.append(message)

    def debug(self, message, *a, **k):
        self.debugs.append(message)

    def info(self, *a, **k):
        pass


class _BarrierSet(set):
    """A set whose membership test waits until both threads have asked.

    Both threads then see "not there yet" before either adds the key: the
    interleaving a check-then-add without a lock cannot survive. The wait ends by
    its timeout if the code under test lets only one thread in at a time (a
    lock), and the set then answers truthfully.
    """

    def __init__(self):
        super().__init__()
        self.barrier = threading.Barrier(2, timeout=1.0)

    def __contains__(self, item):
        answer = super().__contains__(item)
        try:
            self.barrier.wait()
        except threading.BrokenBarrierError:
            return super().__contains__(item)
        return answer


@pytest.mark.xfail(
    strict=True,
    reason=(
        "A3: inventag/discovery/comprehensive_discovery.py:1982 _warn_once checks and adds "
        "to _warned_keys without a lock (plan 2.5: 'a lock'), so two threads that ask for "
        "the same key at the same moment both warn. Remove this mark when A3 is merged"
    ),
)
def test_warn_once_warns_once_when_two_threads_ask_for_the_same_key_together():
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    discovery = ComprehensiveAWSDiscovery(
        regions=["us-east-1"], enable_billing_validation=False
    )
    discovery.logger = _Log()
    discovery._warned_keys = _BarrierSet()
    threads = [
        threading.Thread(
            target=discovery._warn_once, args=("sqs:us-east-1", "sqs failed")
        )
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert discovery.logger.warnings == ["sqs failed"]
    assert discovery.logger.debugs == ["sqs failed"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "A4: inventag/discovery/coverage.py:110 CoverageLedger.entries returns the entries "
        "in the order they were recorded (plan 2.4 item 4: sorted by account, region, "
        "source, service, resource type, operation, outcome, error code). Remove this mark "
        "when A4 is merged"
    ),
)
def test_the_ledger_lists_its_entries_in_sorted_order_whoever_recorded_first():
    from inventag.discovery.coverage import CoverageLedger

    ledger = CoverageLedger("111111111111")
    first_recorded = threading.Event()
    second_recorded = threading.Event()

    def late():
        first_recorded.wait()
        ledger.record(
            region="us-east-1",
            source="service-api",
            service="ec2",
            resource_type="",
            operation="DescribeVpcs",
            outcome="ok",
            count=1,
        )
        second_recorded.set()

    def early():
        ledger.record(
            region="us-west-2",
            source="service-api",
            service="sqs",
            resource_type="",
            operation="ListQueues",
            outcome="ok",
            count=1,
        )
        first_recorded.set()
        second_recorded.wait()
        ledger.record(
            region="eu-west-1",
            source="service-api",
            service="ec2",
            resource_type="",
            operation="DescribeVpcs",
            outcome="throttled",
            count=0,
            error_code="Throttling",
        )

    threads = [threading.Thread(target=late), threading.Thread(target=early)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    entries = ledger.entries
    assert [e.region for e in entries] == ["eu-west-1", "us-east-1", "us-west-2"]
    keys = [
        (
            e.account_id,
            e.region,
            e.source,
            e.service,
            e.resource_type,
            e.operation,
            e.outcome,
            e.error_code,
        )
        for e in entries
    ]
    assert keys == sorted(keys)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "A4: inventag/reporting/document_generator.py:525 _parallel_document_generation "
        "returns the results in the order the formats finish (as_completed); plan 2.4 item "
        "6: the order of the requested formats. Remove this mark when A4 is merged"
    ),
)
def test_document_results_follow_the_order_of_the_requested_formats():
    from inventag.reporting.document_generator import (
        DocumentConfig,
        DocumentGenerationResult,
        DocumentGenerator,
    )

    generator = DocumentGenerator(
        DocumentConfig(max_worker_threads=2, generation_timeout=30)
    )
    excel_done = threading.Event()

    def generate(bom_data, fmt):
        if fmt == "word":
            assert excel_done.wait(30)  # word ends after excel
        result = DocumentGenerationResult(
            format_type=fmt, filename=f"x.{fmt}", success=True
        )
        if fmt == "excel":
            excel_done.set()
        return result

    generator._generate_single_document = generate
    results = generator._parallel_document_generation(None, ["word", "excel"])
    assert [r.format_type for r in results] == ["word", "excel"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "A3: inventag/discovery/inventory.py:774 sorts by (arn, service, type, id, region); "
        "rows that are equal on all five keep the order they arrived in, so workers that "
        "finish in another order give another file. Plan 2.4 item 3: a last key, a digest "
        "of the row's canonical JSON. Remove this mark when A3 is merged"
    ),
)
def test_rows_with_equal_sort_keys_come_out_in_one_order_whatever_came_in_first():
    from inventag.discovery.inventory import AWSResourceInventory

    def row(label):
        return {
            "arn": "",
            "service": "SQS",
            "type": "Queue",
            "id": "q",
            "region": "us-east-1",
            "tags": {"label": label},
        }

    def ordered(rows):
        inventory = AWSResourceInventory(
            regions=["us-east-1"], enable_billing_validation=False
        )
        inventory.ensure_consistent_results = True
        inventory.resources = rows
        inventory._ensure_consistent_results()
        return [r["tags"]["label"] for r in inventory.resources]

    assert ordered([row("a"), row("b")]) == ordered([row("b"), row("a")])
