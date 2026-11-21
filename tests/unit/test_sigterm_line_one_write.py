"""A-79 (v1.4.1): the SIGTERM line survives a SIGTERM during a stdout write.

The handler runs on the main thread between two bytecodes. When that thread
is inside a write to standard output, a line written through logging and
sys.stdout re-enters that write: a plain lock in the stream waits for itself
(hang), and Python's own buffered writer raises "reentrant call", so logging
prints "--- Logging error ---" and the line is lost (review S2). The handler
now writes its line with one os.write on the stream's file descriptor.

Each row starts a real child process with the CLI's logging setup and a
sys.stdout whose write is stuck when SIGTERM arrives.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LINE_END = " - inventag - WARNING - Terminated (SIGTERM). No report was written."

_CHILD = r"""
import os, sys, threading, time
sys.path.insert(0, sys.argv[1])
import importlib

mode = sys.argv[3]


class StuckStdout:
    # A stdout whose write is stuck in the middle when the signal comes.
    encoding = "utf-8"

    def __init__(self):
        self.lock = threading.Lock()  # plain: not reentrant
        self.busy = False

    def write(self, text):
        if mode == "reentrant":
            if self.busy:
                raise RuntimeError("reentrant call inside StuckStdout")
            self.busy = True
            try:
                return self._write(text)
            finally:
                self.busy = False
        with self.lock:
            return self._write(text)

    def _write(self, text):
        os.write(1, text.encode())
        if "stuck-here" in text:
            os.write(2, b"ready\n")
            time.sleep(30)
        return len(text)

    def flush(self):
        pass

    def fileno(self):
        return 1

    def isatty(self):
        return False


sys.stdout = StuckStdout()
from inventag.cli.logging_setup import setup_logging

cli_main = importlib.import_module("inventag.cli.main")
logger = setup_logging(account_specific=True)
out = os.path.join(sys.argv[2], "out")
cli_main._install_sigterm_message(logger, out, 0.0)
logger.warning("stuck-here")
os.write(2, b"not reached\n")
"""


def _run(mode, tmp_path):
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
        [sys.executable, "-c", _CHILD, str(ROOT), str(tmp_path), mode],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    try:
        ready = child.stderr.readline()
        assert ready.strip() == "ready", ready + child.stderr.read()
        started = time.monotonic()
        child.send_signal(signal.SIGTERM)
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pytest.fail(f"SIGTERM during a stdout write ({mode}): hang")
        elapsed = time.monotonic() - started
        return child.returncode, child.stdout.read(), child.stderr.read(), elapsed
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        child.stdout.close()
        child.stderr.close()


@pytest.mark.parametrize("mode", ["lock", "reentrant"])
def test_sigterm_during_a_stdout_write_still_says_its_line(mode, tmp_path):
    code, out, err, elapsed = _run(mode, tmp_path)
    assert code == -signal.SIGTERM, err
    assert elapsed < 2
    lines = out.splitlines()
    # the stuck line was written up to its end; the SIGTERM line follows it
    assert lines[0].endswith(" - inventag - WARNING - stuck-here"), out
    assert len(lines) == 2, out
    assert lines[1].endswith(LINE_END), out
    assert "Logging error" not in err, err
