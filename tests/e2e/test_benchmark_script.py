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
