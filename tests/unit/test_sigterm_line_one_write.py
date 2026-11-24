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

import logging
import os
import re
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


if mode != "logfile":
    sys.stdout = StuckStdout()
from inventag.cli.logging_setup import setup_logging

cli_main = importlib.import_module("inventag.cli.main")
log_file = os.path.join(sys.argv[2], "run.log") if mode == "logfile" else None
logger = setup_logging(account_specific=True, log_file=log_file)
out = os.path.join(sys.argv[2], "out")
cli_main._install_sigterm_message(logger, out, 0.0)
if mode == "logfile":
    os.write(2, b"ready\n")
    time.sleep(30)
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
    # security review v1.4.1 finding 4: the line holds only its fixed parts
    assert re.fullmatch(
        r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}" + re.escape(LINE_END), lines[1]
    ), lines[1]


def test_the_log_file_line_names_the_handler_and_its_line(tmp_path):
    # behaviour review v1.4.1 finding 2: v1.4.0 wrote "handler:<line>", not 0
    code, out, err, _ = _run("logfile", tmp_path)
    assert code == -signal.SIGTERM, err
    text = (tmp_path / "run.log").read_text("utf-8")
    found = re.findall(
        r"WARNING - handler:(\d+) - Terminated \(SIGTERM\)\. No report was written\.",
        text,
    )
    assert len(found) == 1, text
    assert int(found[0]) > 0


class _Writes:
    def __init__(self, sizes):
        self.sizes = list(sizes)
        self.data = b""
        self.calls = 0

    def __call__(self, fd, data):
        self.calls += 1
        n = min(len(data), self.sizes.pop(0) if self.sizes else len(data))
        self.data += data[:n]
        return n


def _say(monkeypatch, writes):
    import importlib

    cli_main = importlib.import_module("inventag.cli.main")
    monkeypatch.setattr(cli_main.os, "write", writes)
    logger = logging.getLogger("test-sigterm-short-write")
    monkeypatch.setattr(logger, "level", logging.WARNING)
    cli_main._say_sigterm_line(
        logger,
        [(99, logging.Formatter("%(message)s"))],
        "Terminated (SIGTERM). No report was written.",
    )


def test_a_short_first_write_still_gives_the_whole_line(monkeypatch):
    # security review v1.4.1 finding 3 (architect: at most 3 writes)
    writes = _Writes([5])
    _say(monkeypatch, writes)
    assert writes.data == b"Terminated (SIGTERM). No report was written.\n"
    assert writes.calls == 2


def test_the_line_takes_at_most_three_writes(monkeypatch):
    writes = _Writes([1, 1, 1, 1, 1])
    _say(monkeypatch, writes)
    assert writes.calls == 3
    assert writes.data == b"Ter"


_STALLED_CHILD = r"""
import fcntl, os, sys, time
sys.path.insert(0, sys.argv[1])
import importlib
from inventag.cli.logging_setup import setup_logging

cli_main = importlib.import_module("inventag.cli.main")
logger = setup_logging(account_specific=True)
cli_main._install_sigterm_message(logger, os.path.join(sys.argv[2], "out"), 0.0)
# Fill standard output, a pipe nobody reads: the next write blocks.
flags = fcntl.fcntl(1, fcntl.F_GETFL)
fcntl.fcntl(1, fcntl.F_SETFL, flags | os.O_NONBLOCK)
try:
    while True:
        os.write(1, b"x" * 4096)
except BlockingIOError:
    pass
fcntl.fcntl(1, fcntl.F_SETFL, flags)
os.write(2, b"ready\n")
time.sleep(30)
"""


def test_a_second_sigterm_ends_a_process_whose_stdout_is_stalled(tmp_path):
    # security re-check v1.4.1 R1: the first SIGTERM's line blocks on a full
    # pipe; a second SIGTERM must end the process by the signal, as in v1.4.0.
    child = subprocess.Popen(
        [sys.executable, "-c", _STALLED_CHILD, str(ROOT), str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)},
        cwd=str(tmp_path),
    )
    try:
        ready = child.stderr.readline()
        assert ready.strip() == b"ready", ready + child.stderr.read()
        child.send_signal(signal.SIGTERM)
        time.sleep(0.5)
        assert child.poll() is None  # the first SIGTERM waits on the reader
        child.send_signal(signal.SIGTERM)
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pytest.fail("a second SIGTERM did not end the process (stdout stalled)")
        assert child.returncode == -signal.SIGTERM
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        child.stdout.close()
        child.stderr.close()
