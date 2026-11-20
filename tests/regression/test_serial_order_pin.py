"""A5: what ``--disable-parallel-processing`` writes today (v1.3.0 semantics), pinned.

Plan 2.4: the reference for every later equality test is the sequential run of
v1.3.0. These rows record its output order and its console text BEFORE the
concurrency work (A2, A3, A4) changes the code, so a change in order shows up as
a failing row, not as a surprise.

What is pinned, each as a separate test:

* the sheet order of the workbook and the row order inside each sheet;
* the order of accounts in the state snapshot and in its coverage summary: the
  configured order (the test configures 3, 1, 2, not the sorted order), and the
  order of resources inside one account (arn, service, type, id, region);
* the file names written (the clock is fixed, so the names are exact);
* the console text of a clean run, as a sorted set of messages (the ORDER of
  log lines is not covered by the rule, plan 2.4 item 7);
* the same bytes under three hash seeds, and the same bytes as a run with the
  default parallel account processing.

One scan is about 20 s (moto start, 3 accounts x 2 regions), so the module is
marked ``slow``: ``pytest -m slow tests/regression/test_serial_order_pin.py``.
"""

import itertools
import json
import re
from pathlib import Path

import pytest

from tests.concurrency import compare, harness

pytestmark = pytest.mark.slow

CONFIGURED = ["333333333333", "123456789012", "222222222222"]  # accounts 3, 1, 2
ARGS = ["--enable-network-analysis", "--enable-security-analysis"]
SPEC = dict(accounts=3, account_order=[3, 1, 2], regions=["us-east-1", "eu-west-1"])
GOLDEN = Path(__file__).with_name("golden") / "serial_console_messages.txt"

_RUNS = {}


def _run(tmp_path_factory, seed: str, serial: bool, analyses: bool = True):
    key = (seed, serial, analyses)
    if key not in _RUNS:
        tmp = tmp_path_factory.mktemp(f"serial-{seed}-{int(serial)}-{int(analyses)}")
        args = (["--disable-parallel-processing"] if serial else []) + (
            ARGS if analyses else []
        )
        _RUNS[key] = harness.run_scan(tmp, args, hash_seed=seed, **SPEC)
    return _RUNS[key]


@pytest.fixture(scope="module")
def serial(tmp_path_factory):
    scan = _run(tmp_path_factory, "0", True)
    assert scan.code == 0, scan.text[-2000:]
    return scan


def _snapshot(scan):
    (path,) = sorted((scan.out / "state").glob("state_*.json"))
    return json.loads(path.read_text())


def test_file_names_of_a_serial_run(serial):
    names = sorted(
        str(p.relative_to(serial.out)) for p in serial.out.rglob("*") if p.is_file()
    )
    assert names == [
        "multi_account_bom_20260115_120000.xlsx",
        "state/metadata.json",
        "state/state_20260115_120000.json",
    ]


def test_snapshot_lists_accounts_in_configured_order(serial):
    tags = _snapshot(serial)["metadata"]["tags"]
    assert list(tags["coverage_summary"]) == CONFIGURED
    # S3 buckets have no ``account_id`` field; ``source_account_id`` is always set
    blocks = [
        k
        for k, _ in itertools.groupby(
            r["source_account_id"] for r in _snapshot(serial)["resources"]
        )
    ]
    assert (
        blocks == CONFIGURED
    ), "resources of one account are not one block, or the blocks are not in configured order"


def test_snapshot_resources_inside_an_account_are_sorted_by_arn_service_type_id_region(
    serial,
):
    def key(r):
        return tuple(
            r.get(k, "") or "" for k in ("arn", "service", "type", "id", "region")
        )

    for account, rows in itertools.groupby(
        _snapshot(serial)["resources"], lambda r: r["source_account_id"]
    ):
        keys = [key(r) for r in rows]
        assert keys == sorted(
            keys
        ), f"account {account}: not sorted by arn, service, type, id, region"


def test_workbook_sheet_order_and_row_order(serial):
    (path,) = serial.files("*.xlsx")
    book = compare.workbook(path)
    names = list(book)
    analysis = ["Network Analysis", "Security Analysis"]
    assert names[0] == "Summary"
    assert names[-2:] == analysis, "the analysis sheets come last, network first"
    services = names[1:-2]
    assert services == sorted(
        services, key=str.lower
    ), "service sheets are not in alphabetical order"
    assert services == [
        "ATHENA",
        "DYNAMODB",
        "EC2",
        "EVENTS",
        "IAM",
        "KMS",
        "LAMBDA",
        "S3",
        "SNS",
        "SQS",
        "VPC",
    ]
    for sheet, rows in book.items():
        if sheet == "Summary" or sheet in analysis or not rows:
            continue
        header = [str(c) for c in rows[0]]

        def key(row, header=header):
            def cell(name):
                if name not in header:
                    return ""
                return str(row[header.index(name)] or "").lower()

            return tuple(
                cell(n)
                for n in ("type", "name", "id", "arn", "source_account_id", "region")
            )

        keys = [key(r) for r in rows[1:]]
        assert keys == sorted(
            keys
        ), f"{sheet}: rows are not sorted by type, name, id, arn, account, region"


def _messages(text: str):
    found = set()
    for line in text.replace("\r", "\n").split("\n"):
        match = re.search(r"\b(?:INFO|WARNING|ERROR) - (.*)$", line)
        if match:
            found.add(re.sub(r"/tmp/\S+", "<path>", match.group(1)).strip())
    return sorted(found)


def test_console_messages_of_a_clean_run_are_the_golden_set(serial):
    expected = GOLDEN.read_text(encoding="utf-8").splitlines()
    assert _messages(serial.stderr + serial.stdout) == expected, (
        "the console text of a clean run changed; a change that the plan names is an edit of "
        f"{GOLDEN.name}, anything else is a regression"
    )


@pytest.mark.parametrize(
    "seed",
    [
        "1",
        "2",
        "3",
    ],
)
def test_a_serial_run_gives_the_same_files_under_another_hash_seed(
    serial, tmp_path_factory, seed
):
    other = _run(tmp_path_factory, seed, True)
    assert other.code == 0
    assert (
        compare.describe_difference(serial.out, other.out, compare.LEDGER_ORDER) is None
    )
    assert (serial.work / "audit.json").read_bytes() == (
        other.work / "audit.json"
    ).read_bytes()


def test_default_parallel_accounts_give_the_same_files_as_the_serial_run(
    tmp_path_factory,
):
    """Without the analyses: the sequential run and the default run write the same files."""
    serial = _run(tmp_path_factory, "0", True, analyses=False)
    parallel = _run(tmp_path_factory, "1", False, analyses=False)
    assert serial.code == parallel.code == 0
    assert compare.describe_difference(serial.out, parallel.out) is None
    assert (
        parallel.calls == serial.calls
    ), "the two runs did not make the same AWS calls"


def test_default_parallel_accounts_give_the_same_analysis_sheets_as_the_serial_run(
    serial, tmp_path_factory
):
    parallel = _run(tmp_path_factory, "1", False)
    assert parallel.code == 0
    assert compare.describe_difference(serial.out, parallel.out) is None


def test_snapshot_bytes_do_not_depend_on_the_order_the_listings_ended(
    serial, tmp_path_factory
):
    other = _run(tmp_path_factory, "1", True)
    assert compare.describe_difference(serial.out, other.out) is None


def test_analysis_sheets_do_not_depend_on_the_hash_seed(serial, tmp_path_factory):
    other = _run(tmp_path_factory, "3", True)
    assert (
        compare.describe_difference(serial.out, other.out, compare.LEDGER_ORDER) is None
    )
