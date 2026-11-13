"""Fixtures for end-to-end CLI tests.

Two ways to run the CLI, both against moto's in-memory AWS:

* ``run_cli(argv)``: calls ``inventag.cli.main.main()`` in this process.
  Fast; process-wide state the CLI changes (umask, read-only guard, log
  record factory, log handlers) is restored afterwards.
* ``run_cli_subprocess(argv)``: starts ``tests/e2e/_moto_runner.py`` in a new
  interpreter. It seeds moto and runs ``python -m inventag``. Slower; proves
  the real entry point, exit codes and stdout/stderr split.

moto's HTTP server mode is not used because it needs Flask, which is not a
dependency of this project.
"""

import logging
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pytest
from moto import mock_aws

from .estate import seed_estate

RUNNER = Path(__file__).with_name("_moto_runner.py")
REPO_ROOT = Path(__file__).resolve().parents[2]
# Keeps a scan to one region and makes no Cost Explorer call.
FAST_SCAN = ["--account-regions", "us-east-1", "--no-billing-validation"]


@dataclass
class CliResult:
    code: int
    stdout: str
    stderr: str
    output_dir: Optional[Path] = None

    @property
    def text(self) -> str:
        return self.stdout + self.stderr

    def files(self, suffix: str) -> List[Path]:
        if self.output_dir is None:
            return []
        return sorted(self.output_dir.glob(f"*{suffix}"))


@contextmanager
def restored_process_state():
    """Undo what ``main()`` changes in the process (guard, umask, logging)."""
    from inventag.security import redaction
    from inventag.security.read_only_guard import (
        get_installed_guard,
        uninstall_global_guard,
    )

    guard_was_installed = get_installed_guard() is not None
    umask = os.umask(0o022)
    os.umask(umask)
    factory = logging.getLogRecordFactory()
    package_logger = logging.getLogger("inventag")
    handlers = list(package_logger.handlers)
    propagate = package_logger.propagate
    level = package_logger.level
    try:
        yield
    finally:
        os.umask(umask)
        redaction.uninstall_log_record_redaction()
        logging.setLogRecordFactory(factory)
        if not guard_was_installed:
            uninstall_global_guard()
        package_logger.handlers[:] = handlers
        package_logger.propagate = propagate
        package_logger.setLevel(level)


def run_main(argv, capsys, monkeypatch, output_dir: Optional[Path] = None):
    """Run ``main()`` with ``argv`` and return the exit code and output."""
    from inventag.cli.main import main

    monkeypatch.setattr(sys, "argv", ["inventag", *argv])
    code = 0
    with restored_process_state():
        try:
            main()
        except SystemExit as exc:
            code = 0 if exc.code is None else exc.code
    captured = capsys.readouterr()
    return CliResult(code, captured.out, captured.err, output_dir)


@pytest.fixture(autouse=True)
def _small_moto(monkeypatch):
    # moto ships ~1300 default AMIs and snapshots; they only slow the scan down.
    monkeypatch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")


@pytest.fixture
def estate(_small_moto):
    """moto AWS with the standard e2e estate in us-east-1."""
    with mock_aws():
        yield seed_estate()


@pytest.fixture
def empty_aws(_small_moto):
    with mock_aws():
        yield


@pytest.fixture
def run_cli(capsys, monkeypatch, tmp_path):
    """Run the CLI in process; reports go to ``tmp_path/out``."""

    def _run(*argv, with_output_dir=True, fast=True):
        args = list(argv)
        out = tmp_path / "out"
        if with_output_dir:
            args += ["--output-directory", str(out)]
        if fast:
            args += FAST_SCAN
        return run_main(args, capsys, monkeypatch, out if with_output_dir else None)

    return _run


@pytest.fixture
def run_cli_subprocess(tmp_path):
    """Run ``python -m inventag`` in a child process inside moto."""

    def _run(*argv, empty=False, timeout=300):
        out = tmp_path / "out"
        env = dict(os.environ)
        env["INVENTAG_E2E_EMPTY"] = "1" if empty else "0"
        env["HOME"] = str(tmp_path / "home")
        (tmp_path / "home").mkdir(exist_ok=True)
        # Keep the child away from real credentials and the network.
        for name in ("AWS_PROFILE", "AWS_SESSION_TOKEN", "AWS_SHARED_CREDENTIALS_FILE"):
            env.pop(name, None)
        proc = subprocess.run(
            [sys.executable, str(RUNNER), *argv],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(tmp_path),
        )
        return CliResult(proc.returncode, proc.stdout, proc.stderr, out)

    return _run
