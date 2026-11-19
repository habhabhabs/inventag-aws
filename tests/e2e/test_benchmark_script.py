"""scripts/benchmark_scan.py runs, measures, and stops when a limit is crossed."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_scan.py"


def run_benchmark(*args, timeout=240):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_small_estate_is_scanned_completely_and_measured(tmp_path):
    out = tmp_path / "result.json"
    proc = run_benchmark("--scale", "0.2", "--json", str(out))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(out.read_text())
    assert result["counts"]["buckets"] == 4
    assert result["scan_exit_code"] == 0
    assert result["scan_seconds"] > 0
    assert result["peak_memory_mb"] >= result["memory_mb_before_scan"] > 0
    assert result["api_calls"]["total"] > 20
    assert result["api_calls"]["blocked"] == 0
    assert set(result["api_calls"]["by_service"]) >= {"s3", "sts"}
    assert all(c["complete"] for c in result["completeness"].values())
    assert result["completeness"]["buckets"] == {
        "created": 4,
        "in_report": 4,
        "complete": True,
    }
    assert "Scan time" in proc.stdout and "Memory" in proc.stdout


def test_explicit_counts_override_the_scale(tmp_path):
    out = tmp_path / "result.json"
    proc = run_benchmark(
        "--scale", "0.2", "--buckets", "3", "--queues", "0", "--json", str(out)
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    counts = json.loads(out.read_text())["counts"]
    assert counts["buckets"] == 3 and counts["queues"] == 0


def test_memory_limit_stops_the_run_with_exit_code_3():
    proc = run_benchmark("--scale", "0.2", "--memory-limit", "1")
    assert proc.returncode == 3
    assert "stopped, memory" in proc.stderr


def test_time_limit_stops_the_run_with_exit_code_3():
    proc = run_benchmark("--scale", "0.2", "--time-limit", "0.5")
    assert proc.returncode == 3
    assert "stopped, time" in proc.stderr


# ---------------------------------------------------------------------------
# The latency harness (tests/latency.py): what the benchmark and the concurrency
# tests of v1.4.0 rely on. In process, against moto, no real sleep.
# ---------------------------------------------------------------------------
import threading

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from moto import mock_aws

from tests import moto_serial
from tests.latency import inject_latency

NO_RETRY = Config(retries={"max_attempts": 1, "mode": "standard"})


class RecordingSleep:
    """A sleep that records its argument and returns at once."""

    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, seconds):
        with self.lock:
            self.calls.append(seconds)


def sqs(**kw):
    return boto3.client("sqs", region_name="us-east-1", **kw)


def test_every_request_is_counted_by_service_and_operation():
    with mock_aws():
        with inject_latency(0, sleep=RecordingSleep()) as harness:
            sqs().list_queues()
            sqs().list_queues()
            boto3.client("sts", region_name="us-east-1").get_caller_identity()
    assert harness.total_requests == 3
    assert harness.calls_by_operation() == {
        "sqs:ListQueues": 2,
        "sts:GetCallerIdentity": 1,
    }


def test_the_delay_is_per_request_and_an_operation_can_have_its_own():
    fake = RecordingSleep()
    with mock_aws():
        with inject_latency(50, per_operation={"sts:GetCallerIdentity": 7}, sleep=fake):
            sqs().list_queues()
            boto3.client("sts", region_name="us-east-1").get_caller_identity()
    assert sorted(fake.calls) == [0.007, 0.05]


def test_the_sleep_is_outside_moto_lock():
    """Otherwise the delays would add up and parallel code could not show a gain."""
    held = []

    def sleep(_seconds):
        got = []

        def probe():
            acquired = moto_serial._LOCK.acquire(blocking=False)
            got.append(acquired)
            if acquired:
                moto_serial._LOCK.release()

        thread = threading.Thread(target=probe)
        thread.start()
        thread.join()
        held.append(got[0])

    with mock_aws():
        with inject_latency(10, sleep=sleep):
            sqs().list_queues()
    assert held == [True]


def test_peak_in_flight_counts_requests_that_wait_at_the_same_time():
    barrier = threading.Barrier(3, timeout=20)

    def sleep(_seconds):
        barrier.wait()

    errors = []

    def call():
        try:
            sqs().list_queues()
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    with mock_aws():
        with inject_latency(1, sleep=sleep) as harness:
            threads = [threading.Thread(target=call) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
    assert errors == []
    assert harness.peak_in_flight == 3
    assert harness.in_flight == 0


def test_one_request_at_a_time_gives_a_peak_of_one():
    with mock_aws():
        with inject_latency(0, sleep=RecordingSleep()) as harness:
            for _ in range(4):
                sqs().list_queues()
    assert harness.peak_in_flight == 1


def test_a_throttle_by_operation_is_retried_by_the_sdk_and_other_operations_pass():
    with mock_aws():
        with inject_latency(
            0, throttle={"sqs:ListQueues": 2}, sleep=RecordingSleep()
        ) as harness:
            assert "QueueUrls" not in sqs().list_queues()
            boto3.client("sts", region_name="us-east-1").get_caller_identity()
    sqs_attempts = [r for r in harness.requests if r.operation == "ListQueues"]
    assert [r.attempt for r in sqs_attempts] == [1, 2, 3]
    assert [r.injected for r in sqs_attempts] == ["Throttling", "Throttling", None]
    sts_attempts = [r for r in harness.requests if r.service == "sts"]
    assert [r.injected for r in sts_attempts] == [None]


def test_a_permanent_throttle_ends_in_the_throttling_error():
    with mock_aws():
        with inject_latency(
            0, throttle={"sqs:ListQueues": None}, sleep=RecordingSleep()
        ) as harness:
            with pytest.raises(ClientError) as caught:
                sqs(config=Config(retries={"max_attempts": 3})).list_queues()
    assert caught.value.response["Error"]["Code"] == "Throttling"
    assert harness.total_requests == 3


@pytest.mark.parametrize(
    "make_call",
    [
        pytest.param(
            lambda: boto3.client("sts", region_name="us-east-1", config=NO_RETRY)
            .get_caller_identity(),
            id="sts-query",
        ),
        pytest.param(
            lambda: boto3.client("s3", region_name="us-east-1", config=NO_RETRY)
            .list_buckets(),
            id="s3-rest-xml",
        ),
        pytest.param(
            lambda: boto3.client("dynamodb", region_name="us-east-1", config=NO_RETRY)
            .list_tables(),
            id="dynamodb-json",
        ),
        pytest.param(
            lambda: boto3.client("lambda", region_name="us-east-1", config=NO_RETRY)
            .list_functions(),
            id="lambda-rest-json",
        ),
        pytest.param(
            lambda: boto3.client("ec2", region_name="us-east-1", config=NO_RETRY)
            .describe_vpcs(),
            id="ec2",
        ),
    ],
)
def test_a_fault_by_operation_gives_that_error_code_in_every_protocol(make_call):
    faults = {
        "sts:GetCallerIdentity": "AccessDenied",
        "s3:ListBuckets": "AccessDenied",
        "dynamodb:ListTables": "AccessDenied",
        "lambda:ListFunctions": "AccessDenied",
        "ec2:DescribeVpcs": "AccessDenied",
    }
    with mock_aws():
        with inject_latency(0, faults=faults, sleep=RecordingSleep()):
            with pytest.raises(ClientError) as caught:
                make_call()
    assert caught.value.response["Error"]["Code"] == "AccessDenied"


def test_a_fault_names_the_service_as_boto3_or_as_the_event_does():
    with mock_aws():
        with inject_latency(
            0,
            faults={"resourcegroupstaggingapi:GetResources": "AccessDenied"},
            sleep=RecordingSleep(),
        ):
            client = boto3.client(
                "resourcegroupstaggingapi", region_name="us-east-1", config=NO_RETRY
            )
            with pytest.raises(ClientError) as caught:
                client.get_resources()
    assert caught.value.response["Error"]["Code"] == "AccessDenied"


def test_the_harness_leaves_moto_as_it_found_it():
    from moto.core.botocore_stubber import BotocoreStubber

    before = BotocoreStubber.__call__
    with mock_aws():
        with inject_latency(0, sleep=RecordingSleep()):
            assert BotocoreStubber.__call__ is not before
    assert BotocoreStubber.__call__ is before
