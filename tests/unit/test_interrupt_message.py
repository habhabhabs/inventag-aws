"""Ctrl-C and SIGTERM end a run with one visible line (A-17), and the exit
status stays what v1.2.1 gave: 1 for Ctrl-C, death by SIGTERM (status -15 in
Python, 143 in a shell) for SIGTERM. A child process runs the CLI with a
generator that blocks, so the signal always arrives during the scan. Slow
form (about 3 s each): a signal can only be proved on a real process."""

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

CHILD = """
import importlib, sys, time
m = importlib.import_module('inventag.cli.main')

class Blocks:
    def __init__(self, config):
        pass
    def generate_comprehensive_bom(self, **kwargs):
        import os
        if os.path.exists("write_report"):
            os.makedirs("reports", exist_ok=True)
            open("reports/multi_account_bom_x.xlsx", "w").close()
        open("ready", "w").close()
        time.sleep(120)

m.CloudBOMGenerator = Blocks
m.validate_aws_credentials_early = lambda t: True
sys.argv = ["inventag", "--create-excel", "--accounts-file", "accounts.json",
            "--output-directory", "reports"]
m.main()
"""


def run_child(tmp_path, sig):
    (tmp_path / "accounts.json").write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "123456789012",
                        "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                        "secret_access_key": "fake-secret-for-tests-only",
                    }
                ]
            }
        )
    )
    (tmp_path / "accounts.json").chmod(0o600)
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(REPO),
        "HOME": str(tmp_path),
        "AWS_DEFAULT_REGION": "us-east-1",
    }
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + 60
    while not (tmp_path / "ready").exists():
        assert time.time() < deadline and proc.poll() is None, proc.communicate()
        time.sleep(0.1)
    proc.send_signal(sig)
    out, err = proc.communicate(timeout=60)
    return proc.returncode, out + err


def test_ctrl_c_prints_one_visible_line_and_exits_1(tmp_path):
    code, text = run_child(tmp_path, signal.SIGINT)
    assert code == 1
    lines = [x for x in text.splitlines() if "Stopped by the user" in x]
    assert len(lines) == 1, text
    assert "No report was written" in lines[0]
    assert "Traceback" not in text


def test_sigterm_prints_one_visible_line_and_ends_by_the_signal(tmp_path):
    code, text = run_child(tmp_path, signal.SIGTERM)
    assert code == -signal.SIGTERM  # as v1.2.1: killed by the signal
    lines = [x for x in text.splitlines() if "Terminated" in x]
    assert len(lines) == 1, text
    assert "No report was written" in lines[0]


def test_a_report_already_written_is_named(tmp_path):
    (tmp_path / "write_report").write_text("")
    code, text = run_child(tmp_path, signal.SIGINT)
    assert code == 1
    assert "1 report file(s) already written stay in" in text


def test_installing_the_sigterm_message_leaves_ctrl_c_alone():
    import logging

    import importlib

    cli_main = importlib.import_module("inventag.cli.main")

    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM)
    try:
        cli_main._install_sigterm_message(logging.getLogger("x"), "reports", 0.0)
        assert signal.getsignal(signal.SIGINT) is old_int
        assert signal.getsignal(signal.SIGTERM) is not old_term
    finally:
        signal.signal(signal.SIGTERM, old_term)
