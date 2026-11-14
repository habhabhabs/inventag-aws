"""Shared pytest fixtures."""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def temp_workspace(tmp_path):
    """Per-test scratch directory (never the repository tree)."""
    return tmp_path


@pytest.fixture
def repo_root():
    return REPO_ROOT


@pytest.fixture(autouse=True, scope="session")
def _moto_without_default_images():
    """Switch off moto's ~1,300 default AMIs and snapshots for the whole session.

    moto reads ``MOTO_EC2_LOAD_DEFAULT_AMIS`` when it builds an EC2 backend, and
    it rebuilds its backends when ``mock_aws`` exits, which is before a per-test
    ``monkeypatch`` puts the variable back. A test that set it per test
    therefore left the next test with no default AMIs, depending on the order
    of the files (review-behaviour T1: ``test_integration_row_sources.py``
    followed by a test that reads ``describe_images``). The
    variable is set here once, before the first test, and no test sets it
    again. Child processes (the e2e runs) inherit it.
    """
    patch = pytest.MonkeyPatch()
    patch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")
    yield
    patch.undo()


_moto_warmed = False


@pytest.fixture(autouse=True)
def _moto_modules_loaded_before_threads():
    """When a test run uses moto, import all of moto's service modules once, in the
    main thread, before the first test (see ``tests/moto_warmup.py``: a first call
    from many threads at once can raise "deadlock detected by _ModuleLock").

    Only runs that collected a moto-using file pay the 4 s; a run of pure unit
    tests does not import moto at all.
    """
    global _moto_warmed
    if not _moto_warmed and "moto" in sys.modules:
        from tests.moto_warmup import warm_moto_modules

        warm_moto_modules()
        _moto_warmed = True
    yield


@pytest.fixture(autouse=True)
def _no_real_aws(monkeypatch):
    """Tests must never reach real AWS or the instance metadata service.

    Credentials are always replaced with fakes, even when the developer's shell
    has real ones: a test that slipped past moto would otherwise call AWS with
    them. Proxy variables are removed so that a stray connection goes to its real
    destination, where ``_no_outbound_network`` refuses it, instead of to a
    local proxy address that looks harmless.
    """
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    for var in (
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_ROLE_ARN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    ):
        monkeypatch.delenv(var, raising=False)
    for var in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-tests-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch, tmp_path_factory):
    """Tests never read or write the real home directory.

    ``Path.home()``, ``~``, ``XDG_CONFIG_HOME`` (user templates, Google token
    cache) and the AWS shared config files all point into a scratch directory.
    """
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv(
        "AWS_SHARED_CREDENTIALS_FILE", str(home / ".aws" / "credentials")
    )
    monkeypatch.setenv("AWS_CONFIG_FILE", str(home / ".aws" / "config"))
    yield home


@pytest.fixture(autouse=True, scope="session")
def _keep_log_files_out_of_the_repository(tmp_path_factory):
    """Send the ``inventag_*.log`` files that the compliance modules open in the
    current directory to a scratch directory.

    ``production_monitor`` and ``security_validator`` call
    ``logging.FileHandler("inventag_production.log")`` and similar with a bare
    file name, so a test run used to leave about 3 MB of logs in the repository
    root. Absolute paths and other file names are left alone.
    """
    import logging

    target = tmp_path_factory.mktemp("inventag-logs")
    original = logging.FileHandler.__init__

    def redirected(self, filename, *args, **kwargs):
        name = os.fspath(filename)
        base = os.path.basename(name)
        if (
            not os.path.isabs(name)
            and os.path.dirname(name) == ""
            and base.startswith("inventag_")
            and base.endswith(".log")
        ):
            filename = str(target / base)
        original(self, filename, *args, **kwargs)

    logging.FileHandler.__init__ = redirected
    yield target
    logging.FileHandler.__init__ = original


def stop_stray_monitor_threads() -> int:
    """Clear the running flag of every ``ProductionSafetyMonitor`` loop. Returns how many."""
    import threading

    stopped = 0
    for thread in threading.enumerate():
        target = getattr(thread, "_target", None)
        owner = getattr(target, "__self__", None)
        if getattr(
            target, "__name__", ""
        ) == "_performance_monitoring_loop" and hasattr(owner, "monitoring_active"):
            if owner.monitoring_active:
                owner.monitoring_active = False
                stopped += 1
    return stopped


@pytest.fixture(autouse=True)
def _stop_stray_monitor_threads():
    """Stop ``ProductionSafetyMonitor`` loops that a test started and forgot.

    ``ComplianceManager`` creates a monitor with a daemon thread that samples
    the CPU every second and logs a warning each time. Without this, every such
    thread keeps running (and logging) for the rest of the session.
    """
    yield
    stop_stray_monitor_threads()


@pytest.fixture(autouse=True)
def _no_outbound_network(monkeypatch):
    """Fail any test that opens a socket to a non-local address.

    moto answers inside the process and the HTTP libraries are mocked where the
    tests need them, so no test should ever reach out. Unix sockets and
    loopback addresses are allowed. A test that does connect gets an OSError
    that names the address, instead of hanging on a timeout.
    """
    import ipaddress
    import socket

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def is_local(sock, address) -> bool:
        if sock.family == getattr(socket, "AF_UNIX", None):
            return True
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, bytes):
            host = host.decode()
        if host in ("localhost", ""):
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def guarded_connect(self, address):
        if not is_local(self, address):
            raise OSError(
                f"blocked by tests/conftest.py: outbound connection to {address!r}"
            )
        return real_connect(self, address)

    def guarded_connect_ex(self, address):
        if not is_local(self, address):
            raise OSError(
                f"blocked by tests/conftest.py: outbound connection to {address!r}"
            )
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
