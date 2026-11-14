"""The autouse fixtures in tests/conftest.py keep tests away from the machine they run on."""

import ast
import importlib.util
import logging
import os
import re
import socket
from pathlib import Path

import boto3
import pytest


def test_home_and_user_config_point_at_a_scratch_directory(_isolated_home):
    assert Path.home() == _isolated_home
    assert Path(os.path.expanduser("~")) == _isolated_home
    assert os.environ["XDG_CONFIG_HOME"].startswith(str(_isolated_home))
    assert os.environ["AWS_SHARED_CREDENTIALS_FILE"].startswith(str(_isolated_home))
    assert not (_isolated_home / ".aws" / "credentials").exists()


def test_credentials_are_fakes_even_if_the_shell_had_real_ones():
    assert os.environ["AWS_ACCESS_KEY_ID"] == "AKIAIOSFODNN7EXAMPLE"
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == "fake-secret-for-tests-only"
    for var in ("AWS_SESSION_TOKEN", "AWS_PROFILE", "AWS_WEB_IDENTITY_TOKEN_FILE"):
        assert var not in os.environ
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    assert creds.access_key == "AKIAIOSFODNN7EXAMPLE"


def test_proxy_variables_are_removed():
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "ALL_PROXY"):
        assert var not in os.environ


def test_connecting_to_a_public_address_is_refused():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OSError, match="blocked by tests/conftest.py.*203.0.113.7"):
            sock.connect(("203.0.113.7", 443))
        with pytest.raises(OSError, match="blocked by tests/conftest.py"):
            sock.connect_ex(("203.0.113.7", 443))
    finally:
        sock.close()


def test_loopback_connections_still_work():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(server.getsockname())
        conn, _ = server.accept()
        conn.close()
    finally:
        client.close()
        server.close()


def test_an_unmocked_boto3_call_fails_instead_of_reaching_aws():
    from botocore.config import Config

    client = boto3.client(
        "sts",
        region_name="us-east-1",
        config=Config(retries={"max_attempts": 0}, connect_timeout=2),
    )
    with pytest.raises(Exception) as caught:
        client.get_caller_identity()
    assert "Could not connect" in str(caught.value) or "blocked" in str(caught.value)


def test_bare_inventag_log_files_go_to_a_scratch_directory(
    _keep_log_files_out_of_the_repository, tmp_path
):
    handler = logging.FileHandler("inventag_probe.log")
    try:
        assert (
            Path(handler.baseFilename).parent == _keep_log_files_out_of_the_repository
        )
    finally:
        handler.close()
    assert not Path("inventag_probe.log").exists()
    # Absolute paths and other names are untouched.
    other = logging.FileHandler(str(tmp_path / "inventag_other.log"))
    try:
        assert Path(other.baseFilename) == tmp_path / "inventag_other.log"
    finally:
        other.close()


def test_a_monitor_thread_left_running_is_stopped():
    from inventag.compliance.production_monitor import ProductionSafetyMonitor

    from tests.conftest import stop_stray_monitor_threads

    monitor = ProductionSafetyMonitor(
        enable_cloudtrail=False, enable_performance_monitoring=True
    )
    assert monitor.monitoring_active
    assert monitor.monitoring_thread.is_alive()

    assert stop_stray_monitor_threads() >= 1

    assert monitor.monitoring_active is False


# ---------------------------------------------------------------------------
# Guards for test order independence and honest skips (debt register T-03, T-06)
# ---------------------------------------------------------------------------

TESTS_DIR = Path(__file__).resolve().parents[1]
REPO = TESTS_DIR.parent
# Runs in a child process of its own: its environment never reaches the test run.
SUBPROCESS_SCRIPTS = {"_moto_runner.py"}

_ENV_WRITE_CALLS = {
    "os.putenv",
    "os.unsetenv",
    "os.environ.setdefault",
    "os.environ.update",
    "os.environ.pop",
    "os.environ.popitem",
    "os.environ.clear",
}


def _test_files():
    return sorted(
        p
        for p in TESTS_DIR.rglob("*.py")
        if p.name not in SUBPROCESS_SCRIPTS and "__pycache__" not in p.parts
    )


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _where(path, node):
    return f"{path.relative_to(REPO)}:{node.lineno}"


def _required_import_names():
    """Import names of every package in requirements.txt and requirements-dev.txt."""
    aliases = {"python-docx": "docx", "pyyaml": "yaml"}
    names = {"inventag"}
    for name in ("requirements.txt", "requirements-dev.txt"):
        for line in (REPO / name).read_text().splitlines():
            m = re.match(r"([A-Za-z0-9_.-]+)", line.split("#")[0].strip())
            if m:
                dist = m.group(1).lower()
                names.add(aliases.get(dist, dist.replace("-", "_")))
    return names


def test_no_test_module_writes_the_environment_outside_monkeypatch():
    """A raw write to os.environ outlives the test (or runs at import time).

    Use the ``monkeypatch`` fixture, which restores the value.
    """
    found = []
    for path in _test_files():
        for node in ast.walk(_parse(path)):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            elif isinstance(node, ast.Delete):
                targets = node.targets
            for target in targets:
                if isinstance(target, ast.Subscript) and ast.unparse(target.value) in (
                    "os.environ",
                    "environ",
                ):
                    found.append(f"{_where(path, node)}: {ast.unparse(node)}")
            if (
                isinstance(node, ast.Call)
                and ast.unparse(node.func) in _ENV_WRITE_CALLS
            ):
                found.append(f"{_where(path, node)}: {ast.unparse(node)[:80]}")
    assert not found, "raw environment writes in tests:\n" + "\n".join(found)


def test_moto_default_images_are_off_for_every_test_from_one_place():
    """moto reads MOTO_EC2_LOAD_DEFAULT_AMIS when it builds a backend, and keeps the
    backend after a per-test monkeypatch has restored the variable. So the variable
    is set once for the whole session in tests/conftest.py and nowhere else."""
    assert os.environ.get("MOTO_EC2_LOAD_DEFAULT_AMIS") == "false"
    scattered = []
    for path in _test_files():
        if path.name == "test_test_isolation.py":
            continue
        for node in ast.walk(_parse(path)):
            if (
                isinstance(node, ast.Constant)
                and node.value == "MOTO_EC2_LOAD_DEFAULT_AMIS"
                and path != TESTS_DIR / "conftest.py"
            ):
                scattered.append(_where(path, node))
    assert not scattered, "set only in tests/conftest.py:\n" + "\n".join(scattered)


def test_no_module_level_skip():
    """``pytest.skip(..., allow_module_level=True)`` hides a broken import as a skip."""
    found = []
    for path in _test_files():
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Call) and any(
                k.arg == "allow_module_level" for k in node.keywords
            ):
                found.append(_where(path, node))
    assert not found, "module-level skips:\n" + "\n".join(found)


def _try_imports(node):
    """Top-level names imported in the body of a Try node."""
    names = set()
    for stmt in ast.walk(ast.Module(body=node.body, type_ignores=[])):
        if isinstance(stmt, ast.Import):
            names.update(a.name.split(".")[0] for a in stmt.names)
        elif isinstance(stmt, ast.ImportFrom) and stmt.module and not stmt.level:
            names.add(stmt.module.split(".")[0])
    return names


def _catches_import_error(node):
    for handler in node.handlers:
        kinds = ast.walk(handler.type) if handler.type is not None else []
        if handler.type is None or any(
            isinstance(k, ast.Name)
            and k.id in ("ImportError", "ModuleNotFoundError", "Exception")
            for k in kinds
        ):
            return True
    return False


def test_no_silent_fallback_for_an_import_that_must_work():
    """``try: import X / except ImportError`` for a package that requirements.txt or
    requirements-dev.txt installs turns a broken install into a skipped or weaker test.
    """
    required = _required_import_names()
    found = []
    for path in _test_files():
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Try) and _catches_import_error(node):
                hidden = _try_imports(node) & required
                if hidden:
                    found.append(f"{_where(path, node)}: {sorted(hidden)}")
            if (
                isinstance(node, ast.Call)
                and ast.unparse(node.func) == "pytest.importorskip"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and str(node.args[0].value).split(".")[0] in required
            ):
                found.append(
                    f"{_where(path, node)}: importorskip({node.args[0].value!r})"
                )
    assert not found, "silent import fallbacks:\n" + "\n".join(found)


_SKIP_CALLS = {
    "pytest.mark.skipif": ("reason", 1),
    "pytest.mark.skip": ("reason", 0),
    "unittest.skipIf": (None, 1),
    "unittest.skipUnless": (None, 1),
    "unittest.skip": (None, 0),
    "pytest.skip": ("reason", 0),
    "pytest.importorskip": ("reason", None),
}


def test_every_skip_states_a_reason():
    found = []
    for path in _test_files():
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            if name not in _SKIP_CALLS:
                continue
            keyword, position = _SKIP_CALLS[name]
            reason = None
            for k in node.keywords:
                if k.arg == keyword:
                    reason = k.value
            if reason is None and position is not None and len(node.args) > position:
                reason = node.args[position]
            if not (isinstance(reason, ast.Constant) and str(reason.value).strip()):
                found.append(f"{_where(path, node)}: {name}")
    assert not found, "skips with no reason:\n" + "\n".join(found)
