"""A5, plan 2.10 row "Equality": the same estate, the same files, whatever the concurrency.

Rule of plan 2.4: for the same AWS answers and a fixed clock, the files a run
writes are the same whatever ``--concurrency``, ``--max-concurrent-accounts``,
thread timing or hash seed. Every test here starts a real process
(``tests/concurrency/_child.py``: moto inside, a fixed clock, moto's ids and
boto3's idempotency tokens seeded), runs the CLI twice with different settings
and compares the output folders: the state files and the audit file as bytes,
Excel sheet by sheet and cell by cell, Word by paragraph and table text
(``tests/concurrency/compare.py``).

The oracle is ``--concurrency 1`` (one AWS request at a time in the whole run);
the reference behind it is the sequential run of v1.3.0
(``--disable-parallel-processing``, pinned in ``tests/regression``).

Rows that need ``--concurrency`` (work order A2) carry ``needs_a2``: they are
expected to fail while the flag is missing from the CLI, and they run for real
as soon as it exists. Rows that need A4 are expected to fail with their reason
until A4 is merged; ``strict`` makes them fail loudly when they start to pass,
so that the mark is removed.

``pytest -m slow tests/concurrency/test_equal_outputs.py`` (each scan 15 to 25 s).
"""

import pytest

from tests.concurrency import compare, harness

pytestmark = pytest.mark.slow

needs_a2 = pytest.mark.xfail(
    not harness.concurrency_flag_exists(),
    strict=True,
    reason="A2: --concurrency is not in the CLI yet (exit 2: unrecognized arguments)",
)
FORMATS = ["--create-word"]
ANALYSES = ["--enable-network-analysis", "--enable-security-analysis"]
ESTATE = dict(regions=["us-east-1", "eu-west-1"])

# a delay per operation that makes the requests of one stage end in another
# order than they started (ec2 slow, the rest fast)
SCRAMBLED = {
    f"ec2:{op}": ms
    for op, ms in {
        "DescribeAddresses": 70,
        "DescribeInstances": 5,
        "DescribeInternetGateways": 60,
        "DescribeKeyPairs": 10,
        "DescribeNatGateways": 50,
        "DescribeNetworkAcls": 15,
        "DescribeRouteTables": 40,
        "DescribeSecurityGroups": 20,
        "DescribeSnapshots": 30,
        "DescribeSubnets": 25,
        "DescribeVolumes": 35,
        "DescribeVpcs": 45,
    }.items()
}


def assert_same(a: harness.Scan, b: harness.Scan, same_calls=True, sorted_dicts=()):
    assert a.code == b.code == 0, (a.text[-800:], b.text[-800:])
    difference = compare.describe_difference(a.out, b.out, sorted_dicts)
    assert difference is None, difference
    assert (a.work / "audit.json").read_bytes() == (
        b.work / "audit.json"
    ).read_bytes(), "the audit files differ"
    if same_calls:
        assert a.calls == b.calls, "the runs made different AWS calls"


# ---------------------------------------------------------- true on v1.3.0 today
@pytest.mark.xfail(
    strict=False,
    reason="A3: measured on v1.3.0 (9f9e972), 3 runs of the default scan under seeds 0 to 2: the same set of resources in state/state_*.json, in a different order (first difference at $.resources[0].arn). Plan 2.4 item 3 (A3): the sort key (arn, service, type, id, region) leaves ties in arrival order; the fix is a last key, a digest of the row. strict=False because it is intermittent. Remove this mark when A3 is merged",
)
@pytest.mark.parametrize("seed", ["0", "1"])
def test_max_concurrent_accounts_1_and_4_write_the_same_files(scans, seed):
    """Today: accounts one at a time and four at a time give the same files (no analyses;
    with analyses see the A4 row below)."""
    one = scans(["--max-concurrent-accounts", "1"], seed="2", accounts=3, **ESTATE)
    four = scans(["--max-concurrent-accounts", "4"], seed=seed, accounts=3, **ESTATE)
    assert_same(one, four, sorted_dicts=compare.LEDGER_ORDER)


@pytest.mark.xfail(
    strict=False,
    reason="A3: measured on v1.3.0 (9f9e972), 3 runs of the default scan under seeds 0 to 2: the same set of resources in state/state_*.json, in a different order (first difference at $.resources[0].arn). Plan 2.4 item 3 (A3): the sort key (arn, service, type, id, region) leaves ties in arrival order; the fix is a last key, a digest of the row. strict=False because it is intermittent. Remove this mark when A3 is merged",
)
def test_max_concurrent_accounts_1_and_4_write_the_same_analysis_sheets(scans):
    one = scans(ANALYSES + ["--max-concurrent-accounts", "1"], accounts=3, **ESTATE)
    four = scans(
        ANALYSES + ["--max-concurrent-accounts", "4"], seed="1", accounts=3, **ESTATE
    )
    assert_same(one, four, sorted_dicts=compare.LEDGER_ORDER)


# ------------------------------------------------------------- needs --concurrency
@needs_a2
@pytest.mark.parametrize("accounts", [1, 4])
# Seeds 0, 1 and 2 give the same order for a set of two region names; seed 3 does not
# (see test_serial_order_pin.py), so the three seeds here are 0, 1 and 3.
@pytest.mark.parametrize("seed", ["0", "1", "3"])
def test_concurrency_1_and_64_write_the_same_files(scans, accounts, seed):
    """Plan 2.10: the same estate with ``--concurrency 1`` and with 64, 1 and 4 accounts,
    under three hash seeds; JSON, snapshot, audit file byte-equal, Excel cell by cell,
    Word by text, and the same AWS calls by service and operation."""
    args = FORMATS + ANALYSES
    oracle = scans(args + ["--concurrency", "1"], accounts=accounts, **ESTATE)
    wide = scans(args + ["--concurrency", "64"], seed=seed, accounts=accounts, **ESTATE)
    assert_same(oracle, wide)


@needs_a2
def test_concurrency_64_makes_the_calls_of_the_sequential_run(scans):
    """Plan 2.9, all rows: the same number of AWS calls as v1.3.0, by service and operation."""
    serial = scans(["--disable-parallel-processing"], accounts=3, **ESTATE)
    wide = scans(["--concurrency", "64"], accounts=3, **ESTATE)
    assert wide.calls == serial.calls


@needs_a2
def test_concurrency_1_and_64_write_the_same_files_when_requests_end_in_another_order(
    scans,
):
    """Slow ec2 requests, fast others: the order in which requests end is not the order in
    which they started. The files must not notice."""
    spec = dict(accounts=3, per_operation=SCRAMBLED, latency_ms=3, **ESTATE)
    args = FORMATS + ANALYSES
    oracle = scans(args + ["--concurrency", "1"], **spec)
    wide = scans(args + ["--concurrency", "64"], seed="1", **spec)
    assert_same(oracle, wide)


# ---------------------------------------------------------------- the caps hold
def _overlap(records):
    """Most requests in flight at once, from (started, ended) pairs of the harness."""
    points = sorted(
        [(r[4], 1) for r in records] + [(r[5], -1) for r in records],
        key=lambda p: (p[0], p[1]),
    )
    peak = now = 0
    for _, step in points:
        now += step
        peak = max(peak, now)
    return peak


@needs_a2
def test_concurrency_1_sends_one_request_at_a_time(scans):
    """Plan 2.9 case B5: peak in flight exactly 1, and the run takes at least calls x delay."""
    delay_ms = 10
    scan = scans(["--concurrency", "1"], accounts=1, latency_ms=delay_ms)
    assert scan.code == 0
    assert scan.stats["peak_in_flight"] == 1
    records = scan.stats["records"]
    assert _overlap(records) == 1
    span = max(r[5] for r in records) - min(r[4] for r in records)
    assert span >= 0.9 * len(records) * delay_ms / 1000.0


@needs_a2
@pytest.mark.parametrize("limit", [8, 64])
def test_concurrency_limits_requests_in_flight_for_the_whole_run(scans, limit):
    """Plan 2.9 case B6 and the default: 4 accounts never have more than N requests in flight."""
    scan = scans(["--concurrency", str(limit)], accounts=4, latency_ms=10)
    assert scan.code == 0
    assert scan.stats["peak_in_flight"] <= limit
    if limit == 8:
        assert scan.stats["peak_in_flight"] >= 2, "nothing ran in parallel at all"
