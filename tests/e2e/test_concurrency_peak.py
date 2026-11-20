"""A2 acceptance (plan 2.9, cases B5 and B6): ``--concurrency`` bounds the AWS
requests in flight for the whole run, counted by the latency harness
(tests/latency.py) under moto. Smaller estates and delay than the weekly
benchmark; the peak rule is the same.

Not verified against real AWS: any speed-up. The numbers come from a simulated
AWS with a fixed delay per request.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_scan.py"


def run_case(tmp_path, *args):
    out = tmp_path / "result.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--json", str(out)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    return json.loads(out.read_text())


def test_b5_concurrency_1_sends_one_request_at_a_time(tmp_path):
    result = run_case(tmp_path, "--case", "B5", "--scale", "0.1", "--latency-ms", "10")
    assert result["requests"]["peak_in_flight"] == 1
    assert result["requests"]["total"] >= result["api_calls"]["total"] > 20


def test_b6_concurrency_8_keeps_four_accounts_at_8_or_fewer(tmp_path):
    result = run_case(
        tmp_path,
        "--case",
        "B6",
        "--scale",
        "0.1",
        "--regions",
        "2",
        "--latency-ms",
        "10",
    )
    assert result["accounts"] == 4
    assert 2 <= result["requests"]["peak_in_flight"] <= 8
