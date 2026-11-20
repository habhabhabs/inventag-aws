"""SEC1 (security P3-1, architect A7 F1): the SIGTERM handler takes no lock.

The handler runs on the main thread between any two bytecodes. The main thread
takes the limiter's lock on every AWS call it makes and a pool's lock on every
submit; a handler that waits for one of those locks waits for itself, and the
process never ends. These rows run a real child process that holds such a lock
on its main thread, send it SIGTERM and look at what it did: it must end by the
signal (as v1.3.x did) within 2 s, with today's one line.

Each row starts a Python process (about 1 s of import time, not counted in the
2 s): the reason for a subprocess is that a hang can only be seen from outside.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MESSAGE = "Terminated (SIGTERM). No report was written."

_CHILD = r"""
import logging, os, sys, time
sys.path.insert(0, sys.argv[1])
import importlib
from inventag.core import cloud_bom_generator as cbg
cli_main = importlib.import_module("inventag.cli.main")

out = os.path.join(sys.argv[2], "out")
generator = cbg.CloudBOMGenerator(cbg.MultiAccountConfig(output_directory=out))
logger = logging.getLogger("sigterm-child")
logger.addHandler(logging.StreamHandler(sys.stderr))
logger.setLevel(logging.INFO)
cli_main._install_sigterm_message(logger, out, 0.0)

if sys.argv[3] == "limiter":
    held = generator.limiter._condition
else:
    import boto3
    from inventag.core.daemon_pool import DaemonThreadPool
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    engine = ComprehensiveAWSDiscovery(
        session=boto3.Session(region_name="us-east-1"), regions=["us-east-1"]
    )
    pool = DaemonThreadPool(1)
    engine._detail_pool = pool
    assert generator._track_engine(engine, None)
    held = pool._lock  # what submit() holds while it queues a call

with held:
    print("ready", flush=True)
    time.sleep(30)
print("not reached", flush=True)
"""


def _sigterm_while_holding(what, tmp_path):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_CONFIG_FILE": str(tmp_path / "none"),
        "AWS_SHARED_CREDENTIALS_FILE": str(tmp_path / "none"),
    }
    child = subprocess.Popen(
        [sys.executable, "-c", _CHILD, str(ROOT), str(tmp_path), what],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    try:
        line = child.stdout.readline()
        assert line.strip() == "ready", child.stderr.read()
        started = time.monotonic()
        child.send_signal(signal.SIGTERM)
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pytest.fail(f"SIGTERM while the main thread holds the {what} lock: hang")
        elapsed = time.monotonic() - started
        return child.returncode, child.stderr.read(), elapsed
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        child.stdout.close()
        child.stderr.close()


@pytest.mark.parametrize("what", ["limiter", "pool"])
def test_sigterm_ends_the_process_while_the_main_thread_holds_a_lock(what, tmp_path):
    code, err, elapsed = _sigterm_while_holding(what, tmp_path)
    assert code == -signal.SIGTERM, err
    assert elapsed < 2
    assert err.strip().splitlines() == [MESSAGE]


# ------------------------------------------- the stop the handler asks for, in-process
class _NoLock:
    """Stands in for a lock: taking it fails the test."""

    def __enter__(self):
        raise AssertionError("a lock was taken")

    def __exit__(self, *exc):
        return False

    acquire = __enter__


def test_a_requested_stop_takes_no_lock_and_refuses_the_next_request():
    from inventag.core.limiter import InFlightLimiter, LimiterStopped

    limiter = InFlightLimiter(4)
    real = limiter._condition
    limiter._condition = _NoLock()
    limiter.request_stop()
    limiter._condition = real
    assert limiter.stopped
    with pytest.raises(LimiterStopped):
        limiter.acquire("111111111111", "ec2", "us-east-1")
    assert limiter.in_flight() == 0


def test_requesting_a_stop_of_the_running_scans_takes_no_lock(tmp_path, monkeypatch):
    from inventag.core import cloud_bom_generator as cbg

    generator = cbg.CloudBOMGenerator(
        cbg.MultiAccountConfig(output_directory=str(tmp_path / "out"))
    )
    calls = []

    class Engine:
        def request_detail_stop(self):
            calls.append("request")

        def stop_detail_calls(self):  # takes the pool's lock: not from the handler
            calls.append("stop")

    engine = Engine()
    assert generator._track_engine(engine, None)
    monkeypatch.setattr(cbg, "_RUNS_LOCK", _NoLock())
    monkeypatch.setattr(generator.limiter, "_condition", _NoLock())
    monkeypatch.setattr(generator, "_engines_lock", _NoLock())
    cbg.request_stop_of_running_scans()
    assert generator.limiter._stop_requested is True
    assert calls == ["request"]


def test_an_engine_without_a_lock_free_stop_is_left_to_the_limiter(tmp_path):
    """Every detail call is an AWS request, which the stopped limiter refuses."""
    from inventag.core import cloud_bom_generator as cbg

    generator = cbg.CloudBOMGenerator(
        cbg.MultiAccountConfig(output_directory=str(tmp_path / "out"))
    )
    calls = []

    class Engine:
        def stop_detail_calls(self):
            calls.append("stop")

    assert generator._track_engine(Engine(), None)
    cbg.request_stop_of_running_scans()
    assert generator.limiter.stopped
    assert calls == []
