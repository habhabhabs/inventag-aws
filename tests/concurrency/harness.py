"""Helpers of the equality, race, throttling and cancellation tests.

``run_scan`` starts ``tests/concurrency/_child.py`` (a real process, moto inside,
fixed clock) and returns what the run left behind. ``concurrency_flag_exists``
says whether the CLI of this checkout knows ``--concurrency`` (work order A2).
"""

import json
import os
import select
import signal as signal_module
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
CHILD = Path(__file__).with_name("_child.py")
FROZEN = "2026-01-15T12:00:00+00:00"


@dataclass
class Scan:
    code: Optional[int]
    stdout: str
    stderr: str
    out: Path
    work: Path
    stats: Dict = field(default_factory=dict)
    gate_started: bool = False  # the gated request began before the signal was sent
    seconds_after_signal: Optional[float] = None

    @property
    def text(self) -> str:
        return self.stdout + "\n" + self.stderr

    def files(self, pattern: str) -> List[Path]:
        return sorted(self.out.glob(pattern))

    @property
    def calls(self) -> Dict[str, int]:
        return self.stats.get("calls", {})


def concurrency_flag_exists() -> bool:
    """True when ``inventag --help`` of this checkout lists ``--concurrency``."""
    text = (REPO / "inventag" / "cli" / "main.py").read_text(encoding="utf-8")
    return '"--concurrency"' in text


def _spec_file(tmp: Path, spec: dict) -> Path:
    path = tmp / "spec.json"
    path.write_text(json.dumps(spec))
    return path


def _env(tmp: Path, hash_seed: str) -> dict:
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in _DROP}
    env.update(HOME=str(home), PYTHONHASHSEED=str(hash_seed), PYTHONPATH=str(REPO))
    return env


_DROP = (
    "AWS_PROFILE",
    "AWS_SESSION_TOKEN",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_RETRY_MODE",
    "AWS_MAX_ATTEMPTS",
    "HTTPS_PROXY",
    "https_proxy",
)


def base_spec(tmp: Path, **kw) -> dict:
    spec = dict(
        regions=["us-east-1"],
        accounts=1,
        scale=0.1,
        latency_ms=0,
        frozen=FROZEN,
        out=str(tmp / "out"),
        work=str(tmp / "work"),
        stats=str(tmp / "stats.json"),
    )
    spec.update(kw)
    return spec


def run_scan(tmp: Path, args=(), hash_seed="0", timeout=240, **spec_kw) -> Scan:
    """Run one scan to the end. ``spec_kw`` goes into the child's spec."""
    spec = base_spec(tmp, **spec_kw)
    proc = subprocess.run(
        [sys.executable, str(CHILD), str(_spec_file(tmp, spec)), *args],
        capture_output=True,
        text=True,
        env=_env(tmp, hash_seed),
        cwd=str(tmp),
        timeout=timeout,
    )
    return _result(proc.returncode, proc.stdout, proc.stderr, spec)


def _result(code, out, err, spec) -> Scan:
    stats_path = Path(spec["stats"])
    stats = json.loads(stats_path.read_text()) if stats_path.exists() else {}
    return Scan(code, out, err, Path(spec["out"]), Path(spec["work"]), stats)


def run_scan_with_signal(
    tmp: Path,
    gate_operation: str,
    sig=signal_module.SIGINT,
    args=(),
    wait_for_start=90,
    timeout=240,
    **spec_kw,
) -> Scan:
    """Start a scan whose first ``gate_operation`` request ("service:Operation")
    stops until the run ends, wait (blocking read, no sleep) until that request
    has started, send ``sig`` and wait for the process.

    ``Scan.code`` is the return code: negative when the signal killed the process.
    """
    fifo = tmp / "gate"
    os.mkfifo(fifo)
    spec = base_spec(tmp, gate={gate_operation: str(fifo)}, **spec_kw)
    fd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
    proc = subprocess.Popen(
        [sys.executable, str(CHILD), str(_spec_file(tmp, spec)), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_env(tmp, "0"),
        cwd=str(tmp),
    )
    # Drain the pipes while we wait: a full pipe would stop the child.
    outputs: Dict[str, str] = {}

    def drain(name, stream):
        outputs[name] = stream.read()

    readers = [
        threading.Thread(target=drain, args=("out", proc.stdout), daemon=True),
        threading.Thread(target=drain, args=("err", proc.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    started, seconds_after = False, None
    try:
        # a blocking wait on two events: the gated request began (FIFO written) or
        # the process ended (its pidfd becomes readable)
        pidfd = os.pidfd_open(proc.pid)
        try:
            ready, _, _ = select.select([fd, pidfd], [], [], wait_for_start)
        finally:
            os.close(pidfd)
        started = fd in ready and os.read(fd, 1) == b"x"
        sent = None
        if started and proc.poll() is None:
            sent = time.monotonic()
            proc.send_signal(sig)
        try:
            proc.wait(timeout=timeout)
            if sent is not None:
                seconds_after = time.monotonic() - sent
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    finally:
        os.close(fd)
    for reader in readers:
        reader.join(timeout=30)
    scan = _result(
        proc.returncode, outputs.get("out", ""), outputs.get("err", ""), spec
    )
    scan.gate_started = started
    scan.seconds_after_signal = seconds_after
    return scan
