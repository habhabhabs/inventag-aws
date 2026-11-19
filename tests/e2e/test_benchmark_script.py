"""scripts/benchmark_scan.py runs, measures, and stops when a limit is crossed."""

import json
import subprocess
import sys
import threading
from pathlib import Path

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError
from moto import mock_aws

from tests import moto_serial
from tests.latency import inject_latency

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
                sqs(
                    config=Config(retries={"total_max_attempts": 3, "mode": "standard"})
                ).list_queues()
    assert caught.value.response["Error"]["Code"] == "Throttling"
    assert harness.total_requests == 3


@pytest.mark.parametrize(
    "make_call",
    [
        pytest.param(
            lambda: boto3.client(
                "sts", region_name="us-east-1", config=NO_RETRY
            ).get_caller_identity(),
            id="sts-query",
        ),
        pytest.param(
            lambda: boto3.client(
                "s3", region_name="us-east-1", config=NO_RETRY
            ).list_buckets(),
            id="s3-rest-xml",
        ),
        pytest.param(
            lambda: boto3.client(
                "dynamodb", region_name="us-east-1", config=NO_RETRY
            ).list_tables(),
            id="dynamodb-json",
        ),
        pytest.param(
            lambda: boto3.client(
                "lambda", region_name="us-east-1", config=NO_RETRY
            ).list_functions(),
            id="lambda-rest-json",
        ),
        pytest.param(
            lambda: boto3.client(
                "ec2", region_name="us-east-1", config=NO_RETRY
            ).describe_vpcs(),
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


# ---------------------------------------------------------------------------
# scripts/benchmark_scan.py: latency, regions, accounts, concurrency, stages
# and the acceptance check of plan 2.9 (A0).
# ---------------------------------------------------------------------------
import importlib.util


@pytest.fixture(scope="module")
def bench():
    """The script as a module. Importing it must not touch the environment."""
    spec = importlib.util.spec_from_file_location("benchmark_scan_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_importing_the_script_leaves_the_environment_alone(monkeypatch):
    import os

    monkeypatch.delenv("MOTO_EC2_LOAD_DEFAULT_AMIS", raising=False)
    before = dict(os.environ)
    spec = importlib.util.spec_from_file_location("benchmark_scan_import", SCRIPT)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    assert dict(os.environ) == before


def test_a_latency_run_reports_requests_peak_and_stages(tmp_path):
    out = tmp_path / "result.json"
    proc = run_benchmark(
        "--scale", "0.1", "--latency-ms", "20", "--json", str(out), timeout=300
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(out.read_text())
    assert result["latency_ms"] == 20
    requests = result["requests"]
    assert requests["total"] >= result["api_calls"]["total"] > 20
    # v1.3.0 and later list with up to 15 threads in one account.
    assert 2 <= requests["peak_in_flight"] <= 15 * result["accounts"]
    stages = result["stages"]
    assert set(stages) == {
        "credentials",
        "listings",
        "tagging",
        "details",
        "analyses",
        "reports",
    }
    assert sum(s["calls"] for k, s in stages.items() if k != "reports") == (
        requests["total"]
    )
    assert stages["listings"]["calls"] > 0 and stages["details"]["calls"] > 0
    assert stages["reports"]["seconds"] >= 0
    assert result["wall_seconds"] == result["scan_seconds"]
    assert "ledger" in result and result["ledger"]["entries"] > 0
    assert sum(result["api_calls"]["by_operation"].values()) == (
        result["api_calls"]["total"]
    )


def test_several_regions_are_built_and_scanned_completely(tmp_path):
    out = tmp_path / "result.json"
    proc = run_benchmark(
        "--scale", "0.1", "--regions", "us-east-1,us-west-2", "--json", str(out)
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(out.read_text())
    assert result["regions"] == ["us-east-1", "us-west-2"]
    assert result["completeness"]["queues"]["created"] == 2 * result["counts"]["queues"]
    assert all(c["complete"] for c in result["completeness"].values())


def test_several_accounts_are_built_and_scanned_completely(tmp_path):
    out = tmp_path / "result.json"
    proc = run_benchmark("--scale", "0.1", "--accounts", "2", "--json", str(out))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(out.read_text())
    assert result["accounts"] == 2
    assert (
        result["completeness"]["buckets"]["created"] == 2 * result["counts"]["buckets"]
    )
    assert all(c["complete"] for c in result["completeness"].values())
    assert result["api_calls"]["by_service"]["sts"] >= 3


def test_the_scan_command_line_adds_concurrency_only_when_asked(bench, tmp_path):
    base = dict(regions=["us-east-1"], accounts_file=None, concurrency=None)
    plain = bench.scan_argv(tmp_path / "o", tmp_path / "a.json", **base)
    assert "--concurrency" not in plain
    asked = bench.scan_argv(
        tmp_path / "o", tmp_path / "a.json", **{**base, "concurrency": 8}
    )
    assert asked[asked.index("--concurrency") + 1] == "8"
    assert asked[asked.index("--account-regions") + 1] == "us-east-1"
    many = bench.scan_argv(
        tmp_path / "o",
        tmp_path / "a.json",
        regions=["us-east-1", "eu-west-1"],
        accounts_file=tmp_path / "accounts.json",
        concurrency=None,
    )
    assert many[many.index("--accounts-file") + 1] == str(tmp_path / "accounts.json")
    assert "--account-regions" not in many


def test_the_cases_of_plan_2_9_are_defined(bench):
    cases = bench.CASES
    assert set(cases) == {f"B{i}" for i in range(1, 9)}
    assert cases["B1"]["latency_ms"] == 50 and cases["B1"]["scale"] == 1
    assert cases["B2"]["scale"] == 5
    assert cases["B3"]["regions"] == 3 and cases["B3"]["latency_ms"] == 200
    assert cases["B4"]["accounts"] == 4 and cases["B4"]["regions"] == 3
    assert cases["B5"]["concurrency"] == 1
    assert cases["B6"]["concurrency"] == 8 and cases["B6"]["accounts"] == 4
    assert cases["B7"]["latency_ms"] == 0
    assert cases["B8"]["scale"] == 5


def result_of(wall, peak=10, memory=500.0, calls=None, total=None, latency=50):
    calls = (
        calls
        if calls is not None
        else {"s3:ListBuckets": 1, "sts:GetCallerIdentity": 2}
    )
    return {
        "scan_seconds": wall,
        "latency_ms": latency,
        "requests": {
            "total": total if total is not None else sum(calls.values()),
            "peak_in_flight": peak,
        },
        "peak_memory_mb": memory,
        "api_calls": {"total": sum(calls.values()), "by_operation": calls},
    }


def verdicts(bench, case, baseline, candidate):
    return {
        name: ok for name, ok, _detail in bench.evaluate_case(case, baseline, candidate)
    }


def test_a_wall_time_ratio_is_the_acceptance_of_b1_to_b4_and_b7(bench):
    base = result_of(10.0)
    assert all(verdicts(bench, "B1", base, result_of(8.5)).values())
    assert not verdicts(bench, "B1", base, result_of(8.6))["wall ratio"]
    assert all(verdicts(bench, "B2", base, result_of(6.0)).values())
    assert not verdicts(bench, "B2", base, result_of(6.1))["wall ratio"]
    assert all(verdicts(bench, "B3", base, result_of(5.5)).values())
    assert all(verdicts(bench, "B7", base, result_of(11.0, latency=0)).values())
    assert not verdicts(bench, "B7", base, result_of(11.1, latency=0))["wall ratio"]


def test_b4_also_limits_the_peak_in_flight(bench):
    base = result_of(10.0)
    assert all(verdicts(bench, "B4", base, result_of(10.0, peak=64)).values())
    assert not verdicts(bench, "B4", base, result_of(10.0, peak=65))["peak in flight"]


def test_b5_and_b6_need_no_baseline(bench):
    # 100 requests at 50 ms, one at a time: at least 5 s.
    one = result_of(5.0, peak=1, total=100, calls={"s3:ListBuckets": 100})
    assert all(verdicts(bench, "B5", None, one).values())
    too_fast = result_of(4.0, peak=1, total=100, calls={"s3:ListBuckets": 100})
    assert not verdicts(bench, "B5", None, too_fast)["wall at least requests x delay"]
    two = result_of(5.0, peak=2, total=100, calls={"s3:ListBuckets": 100})
    assert not verdicts(bench, "B5", None, two)["peak in flight"]
    assert all(verdicts(bench, "B6", None, result_of(5.0, peak=8)).values())
    assert not verdicts(bench, "B6", None, result_of(5.0, peak=9))["peak in flight"]


def test_b8_limits_memory_against_the_baseline_and_the_script_limit(bench):
    base = result_of(10.0, memory=1000.0)
    assert all(verdicts(bench, "B8", base, result_of(10.0, memory=1150.0)).values())
    assert not verdicts(bench, "B8", base, result_of(10.0, memory=1151.0))[
        "memory ratio"
    ]
    small = result_of(10.0, memory=500.0)
    assert not verdicts(bench, "B8", small, result_of(10.0, memory=1401.0))[
        "memory under the limit"
    ]


def test_every_case_needs_the_same_calls_by_operation_as_the_baseline(bench):
    base = result_of(10.0, calls={"s3:ListBuckets": 3})
    same = result_of(5.0, calls={"s3:ListBuckets": 3})
    other = result_of(5.0, calls={"s3:ListBuckets": 4})
    assert verdicts(bench, "B1", base, same)["same calls by operation"]
    assert not verdicts(bench, "B1", base, other)["same calls by operation"]


def test_the_check_command_exits_1_when_a_case_fails(tmp_path):
    base, cand = tmp_path / "base.json", tmp_path / "cand.json"
    base.write_text(json.dumps(result_of(10.0)))
    cand.write_text(json.dumps(result_of(9.0)))
    proc = run_benchmark(
        "--check-case", "B1", "--baseline", str(base), "--candidate", str(cand)
    )
    assert proc.returncode == 1
    assert "wall ratio" in proc.stdout and "FAIL" in proc.stdout
    cand.write_text(json.dumps(result_of(8.0)))
    proc = run_benchmark(
        "--check-case", "B1", "--baseline", str(base), "--candidate", str(cand)
    )
    assert proc.returncode == 0, proc.stdout
