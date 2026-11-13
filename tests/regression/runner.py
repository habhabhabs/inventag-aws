"""Run one scenario row: in this process, or as a child process."""

import io
import json
import logging
import os
import re
import signal as signal_module
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from moto import mock_aws

from tests.e2e.conftest import restored_process_state
from tests.regression import estates
from tests.regression.checks import RunOutcome
from tests.regression.faults import FaultInjector, faults_to_json
from tests.regression.scenarios import ACCOUNTS, Scenario

REPO = Path(__file__).resolve().parents[2]
CHILD = Path(__file__).with_name("child.py")


def _accounts_file(sc: Scenario, directory: Path):
    if not sc.accounts:
        return None
    accounts = []
    for key in sc.accounts:
        account_id, access_key = ACCOUNTS[key]
        accounts.append(
            {
                "account_id": account_id,
                "account_name": f"Account {key}",
                "access_key_id": access_key,
                "secret_access_key": "regression-secret-key-0000000000000000",
                "regions": ["us-east-1"],
            }
        )
    path = directory / "accounts.json"
    path.write_text(json.dumps({"version": "1.0", "accounts": accounts}))
    os.chmod(path, 0o600)
    return path


def _argv(sc: Scenario, step: dict, out: Path, accounts_file):
    argv = ["--account-regions", "us-east-1"]
    if not sc.billing:
        argv.append("--no-billing-validation")
    argv += [a.replace("{out}", str(out)) for a in sc.args]
    argv += [a.replace("{out}", str(out)) for a in step.get("args", ())]
    if accounts_file:
        argv += ["--accounts-file", str(accounts_file)]
    argv += ["--output-directory", str(out)]
    return argv


def _accounts_map(sc: Scenario):
    return {ACCOUNTS[k][1]: ACCOUNTS[k][0] for k in sc.accounts}


class _logging_state:
    """Put every ``inventag*`` logger back as it was after a run.

    ``main()`` and the discovery classes attach handlers (bound to the stream of that
    run) and change ``propagate``; in one process, a second run would otherwise write
    into the first run's buffer.
    """

    def __enter__(self):
        self.saved = {
            name: (lg.handlers[:], lg.propagate, lg.level)
            for name, lg in logging.root.manager.loggerDict.items()
            if name.startswith("inventag") and isinstance(lg, logging.Logger)
        }
        return self

    def __exit__(self, *exc):
        for name, lg in list(logging.root.manager.loggerDict.items()):
            if name.startswith("inventag") and isinstance(lg, logging.Logger):
                handlers, propagate, level = self.saved.get(name, ([], True, 0))
                lg.handlers[:] = handlers
                lg.propagate = propagate
                lg.setLevel(level)


def _set_limits(monkeypatch, limits):
    if not limits:
        return
    from inventag.core import cloud_bom_generator as cbg

    original = cbg.CloudBOMGenerator.__init__

    def patched(self, config, *a, **k):
        if limits.get("account_timeout"):
            config.account_processing_timeout = limits["account_timeout"]
        original(self, config, *a, **k)
        if limits.get("grace") is not None:
            self._abandon_grace_seconds = limits["grace"]
        if limits.get("poll"):
            self._poll_seconds = limits["poll"]

    monkeypatch.setattr(cbg.CloudBOMGenerator, "__init__", patched)


def run_in_process(sc: Scenario, tmp_path: Path, monkeypatch) -> RunOutcome:
    """Run the scenario's steps one after another in this process."""
    from inventag.cli.main import main

    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    accounts_file = _accounts_file(sc, tmp_path)
    steps = [dict(args=(), faults=sc.faults)] + [
        dict(args=s.get("args", ()), faults=s.get("faults", sc.faults)) for s in sc.later_runs
    ]
    outcomes = []
    for step in steps:
        argv = _argv(sc, step, out, accounts_file)
        buf_out, buf_err = io.StringIO(), io.StringIO()
        started = time.time()
        code = 0
        # pytest puts its own handler on the root logger. With it in place Python's
        # "last resort" handler (which prints discovery's bare warnings to stderr in a
        # real run) is never used, so take the root handlers off for the run.
        root = logging.getLogger()
        saved_handlers = root.handlers[:]
        root.handlers[:] = []
        with mock_aws():
            estates.seed(sc.seed)
            injector = FaultInjector(step["faults"], _accounts_map(sc))
            with injector:
                injector.arm()
                _set_limits(monkeypatch, sc.limits)
                monkeypatch.setattr(sys, "argv", ["inventag", *argv])
                with restored_process_state(), _logging_state(), redirect_stdout(buf_out), redirect_stderr(buf_err):
                    try:
                        main()
                    except SystemExit as exc:
                        code = 0 if exc.code is None else exc.code
                    finally:
                        root.handlers[:] = saved_handlers
        outcomes.append(
            RunOutcome(
                code=code,
                stdout=buf_out.getvalue(),
                stderr=buf_err.getvalue(),
                out_dir=out,
                calls=list(injector.calls),
                wall_seconds=time.time() - started,
            )
        )
    last = outcomes[-1]
    last.earlier = outcomes[:-1]
    return last


def _summary_age(text: str, ended: float):
    """Seconds between the last "Processing time" log line and ``ended``."""
    stamps = re.findall(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ - inventag - INFO -   - Processing time", text, re.M)
    if not stamps:
        return None
    t = time.mktime(time.strptime(stamps[-1], "%Y-%m-%d %H:%M:%S"))
    return max(ended - t, 0.0)


def run_child(sc: Scenario, tmp_path: Path) -> RunOutcome:
    """Run the scenario as ``python tests/regression/child.py`` (a real process)."""
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    accounts_file = _accounts_file(sc, tmp_path)
    hit = tmp_path / "hit"
    argv = _argv(sc, {}, out, accounts_file)
    env = dict(os.environ)
    for name in ("AWS_PROFILE", "AWS_SESSION_TOKEN", "AWS_SHARED_CREDENTIALS_FILE", "HTTPS_PROXY", "https_proxy"):
        env.pop(name, None)
    env.update(
        HOME=str(home),
        INVENTAG_REGRESSION_SPEC=faults_to_json(sc.faults, _accounts_map(sc)),
        INVENTAG_REGRESSION_SEED=",".join(sc.seed),
        INVENTAG_REGRESSION_LIMITS=json.dumps(sc.limits),
        INVENTAG_REGRESSION_HIT=str(hit),
        PYTHONPATH=str(REPO),
    )
    started = time.time()
    proc = subprocess.Popen(
        [sys.executable, str(CHILD), *argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    if sc.signal:
        # send the signal once the slow call has started (the child writes ``hit``)
        deadline = time.time() + 40
        while not hit.exists() and time.time() < deadline and proc.poll() is None:
            time.sleep(0.1)
        time.sleep(0.5)
        if proc.poll() is None:
            proc.send_signal(getattr(signal_module, sc.signal))
    try:
        stdout, stderr = proc.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        proc.returncode = "TIMEOUT"
    ended = time.time()
    # A process killed by a signal has a negative return code (-15 for SIGTERM).
    # Rows that want "handled, exit 143" compare against the raw code on purpose.
    return RunOutcome(
        code=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        out_dir=out,
        wall_seconds=ended - started,
        seconds_after_summary=_summary_age(stdout + stderr, ended),
    )
