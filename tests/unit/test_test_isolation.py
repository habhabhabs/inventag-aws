"""The autouse fixtures in tests/conftest.py keep tests away from the machine they run on."""

import logging
import os
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
