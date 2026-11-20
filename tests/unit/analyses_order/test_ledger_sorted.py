"""A4: the coverage ledger is read in one fixed order (plan 2.4, rule 4).

Threads record entries as they finish, so the insertion order depends on
timing. A reader sees the entries sorted by (account, region, source,
service, resource type, operation, outcome, error code, count).
"""

import itertools
import threading

from inventag.discovery.coverage import CoverageLedger


def _entry(ledger, **over):
    fields = dict(
        region="us-east-1",
        source="service-api",
        service="ec2",
        resource_type="Instance",
        operation="DescribeInstances",
        outcome="ok",
        count=1,
    )
    fields.update(over)
    return ledger.record(**fields)


def _make():
    return [
        dict(account_id="222", region="eu-west-1"),
        dict(account_id="111", region="us-west-2"),
        dict(account_id="111", region="eu-west-1", source="tagging-api"),
        dict(account_id="111", region="eu-west-1", service="s3"),
        dict(account_id="111", region="eu-west-1", operation="DescribeVolumes"),
        dict(account_id="111", region="eu-west-1", outcome="denied", error_code="B"),
        dict(account_id="111", region="eu-west-1", outcome="denied", error_code="A"),
        dict(account_id="111", region="eu-west-1", resource_type="Volume"),
        dict(account_id="111", region="eu-west-1", count=0, outcome="empty"),
    ]


def _keys(ledger):
    return [
        (
            e.account_id,
            e.region,
            e.source,
            e.service,
            e.resource_type,
            e.operation,
            e.outcome,
            e.error_code,
            e.count,
        )
        for e in ledger.entries
    ]


def test_entries_are_sorted_whatever_the_recording_order():
    keys = None
    for order in itertools.islice(itertools.permutations(_make()), 0, 400, 37):
        ledger = CoverageLedger()
        for fields in order:
            _entry(ledger, **fields)
        got = _keys(ledger)
        assert got == sorted(got)
        keys = keys or got
        assert got == keys


def test_to_dict_and_failed_units_follow_the_sorted_order():
    ledger = CoverageLedger()
    for fields in _make():
        _entry(ledger, **fields)
    assert [d["account_id"] for d in ledger.to_dict()] == sorted(
        d["account_id"] for d in ledger.to_dict()
    )
    failed = ledger.failed_units()
    assert [e.error_code for e in failed] == ["A", "B"]


def test_threads_recording_at_once_give_one_order():
    def run(order):
        ledger = CoverageLedger()
        barrier = threading.Barrier(len(order))

        def work(fields):
            barrier.wait(timeout=10)
            _entry(ledger, **fields)

        threads = [threading.Thread(target=work, args=(f,)) for f in order]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return _keys(ledger)

    base = _make()
    assert run(base) == run(list(reversed(base)))


def test_seconds_is_not_a_sort_key():
    ledger = CoverageLedger()
    _entry(ledger, seconds=9.0)
    _entry(ledger, seconds=1.0)
    assert [e.seconds for e in ledger.entries] == [9.0, 1.0]
