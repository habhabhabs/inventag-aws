"""Fixtures of the failure regression suite.

The top-level ``tests/conftest.py`` already gives every test fake credentials, a
scratch HOME, no real log files and no outbound network. This file adds:

* ``MOTO_EC2_LOAD_DEFAULT_AMIS=false`` (moto ships ~1300 default AMIs and snapshots)
* moto's service modules imported before any thread starts (a first import from
  15 discovery threads raised "deadlock detected by _ModuleLock" once, and the
  engine recorded it as a failed listing)
* ``moto_estate``, ``fault_injector``, ``never_answering_endpoint``,
  ``closed_port_endpoint``, ``fake_clock``, ``signal_driver``
"""

import os
import socket
import subprocess
import sys
import threading
import time

import boto3
import pytest
from moto import mock_aws

from tests.regression.faults import FaultInjector, faults_to_json

os.environ.setdefault("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")

# Import every moto backend the scan touches, once, on the main thread.
_MOTO_MODULES = (
    "moto.ec2",
    "moto.s3",
    "moto.sqs",
    "moto.sns",
    "moto.dynamodb",
    "moto.kms",
    "moto.awslambda",
    "moto.ecs",
    "moto.iam",
    "moto.rds",
    "moto.events",
    "moto.athena",
    "moto.cloudformation",
    "moto.resourcegroupstaggingapi",
    "moto.ce",
)
for _name in _MOTO_MODULES:
    try:
        __import__(_name)
    except Exception:  # a module that is not in this moto version is not needed
        pass


@pytest.fixture(autouse=True)
def _small_moto(monkeypatch):
    monkeypatch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")


@pytest.fixture
def moto_estate(_small_moto):
    """moto AWS with the standard estate of the e2e tests; yields its ids."""
    from tests.e2e.estate import seed_estate

    with mock_aws():
        boto3.client("lambda", region_name="us-east-1").list_functions()
        yield seed_estate()


@pytest.fixture
def fault_injector():
    """``fault_injector(Fault(...), ..., accounts={key: account_id})`` returns an armed injector.

    Use inside ``mock_aws()`` after seeding. Injectors are removed at the end of the test.
    """
    created = []

    def make(*faults, accounts=None) -> FaultInjector:
        injector = FaultInjector(faults, accounts)
        injector.__enter__()
        injector.arm()
        created.append(injector)
        return injector

    yield make
    for injector in reversed(created):
        injector.__exit__(None, None, None)


@pytest.fixture
def never_answering_endpoint():
    """URL of a local socket that accepts connections and never answers.

    A client with a short read timeout gets a ``ReadTimeoutError``, deterministically
    (an unroutable address answered at once on the build host).
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(16)
    accepted = []
    stop = threading.Event()

    def accept_forever():
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
                accepted.append(conn)  # keep it open, never read, never write
            except OSError:
                continue

    thread = threading.Thread(target=accept_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.getsockname()[1]}"
    stop.set()
    thread.join(timeout=2)
    for conn in accepted:
        conn.close()
    server.close()


@pytest.fixture
def closed_port_endpoint():
    """URL of a local port nothing listens on: the connection is refused at once."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return f"http://127.0.0.1:{port}"


class FakeClock:
    """A clock a test moves by hand (``clock.now += 10``). Callable like ``time.monotonic``."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake_clock():
    return FakeClock()


@pytest.fixture
def signal_driver(tmp_path):
    """Start the CLI in a child process, wait until a slow fault has started, send a signal.

    ``signal_driver(argv, faults=[Fault(sleep=...)], sig=signal.SIGINT)`` returns
    ``(returncode, stdout, stderr)``. The child is ``tests/regression/child.py``.
    """
    import signal as signal_module

    def drive(argv, faults, sig=signal_module.SIGINT, seeds=("estate",), wait=40):
        hit = tmp_path / "hit"
        home = tmp_path / "home"
        home.mkdir(exist_ok=True)
        env = dict(os.environ, HOME=str(home), PYTHONPATH=os.getcwd())
        for name in ("AWS_PROFILE", "HTTPS_PROXY", "https_proxy"):
            env.pop(name, None)
        env.update(
            INVENTAG_REGRESSION_SPEC=faults_to_json(faults),
            INVENTAG_REGRESSION_SEED=",".join(seeds),
            INVENTAG_REGRESSION_HIT=str(hit),
        )
        proc = subprocess.Popen(
            [
                sys.executable,
                str(os.path.join(os.path.dirname(__file__), "child.py")),
                *argv,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        end = time.time() + wait
        while not hit.exists() and time.time() < end and proc.poll() is None:
            time.sleep(0.1)
        time.sleep(0.3)
        if proc.poll() is None:
            proc.send_signal(sig)
        out, err = proc.communicate(timeout=120)
        return proc.returncode, out, err

    return drive
