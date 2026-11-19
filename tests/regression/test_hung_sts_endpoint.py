"""A hung STS endpoint (T-08; the behaviour review's "not checked").

A local socket accepts the connection and never answers, so STS is "hung" for
real (no moto, no stub): the client's own timeout decides. The run must end
within the time ``--credential-timeout`` allows, say what happened and what to
do, and never print a traceback.
"""

import importlib
import logging
import sys
import time

import pytest

cli_main = importlib.import_module("inventag.cli.main")

# --credential-timeout 1: one attempt of one second, plus start-up. A hang that
# ignored the timeout would run into the pytest limit instead.
LIMIT_SECONDS = 30


def run_cli(*args):
    old_argv = sys.argv
    sys.argv = ["inventag", *args]
    try:
        cli_main.main()
        return 0
    except SystemExit as exit_:
        code = exit_.code
        return code if isinstance(code, int) else (0 if code is None else 1)
    finally:
        sys.argv = old_argv


@pytest.fixture
def hung_sts(monkeypatch, tmp_path, never_answering_endpoint):
    monkeypatch.setenv("AWS_ENDPOINT_URL_STS", never_answering_endpoint)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-creds"))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    yield never_answering_endpoint
    for name in ("inventag", "botocore", "boto3", "urllib3"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def test_default_credentials_check_gives_up_at_the_credential_timeout(
    hung_sts, capsys, caplog
):
    caplog.set_level(logging.ERROR)
    started = time.monotonic()
    code = run_cli(
        "--create-excel",
        "--account-regions",
        "us-east-1",
        "--no-billing-validation",
        "--credential-timeout",
        "1",
    )
    elapsed = time.monotonic() - started
    text = (lambda c: c.err + c.out)(capsys.readouterr()) + caplog.text
    assert code == 1
    assert elapsed < LIMIT_SECONDS
    assert "AWS did not answer in time" in caplog.text
    assert "--credential-timeout" in caplog.text
    assert "Traceback" not in text


def test_the_early_credential_check_returns_false_and_names_the_timeout_flag(
    hung_sts, caplog
):
    caplog.set_level(logging.ERROR)
    started = time.monotonic()
    assert cli_main.validate_aws_credentials_early(1) is False
    assert time.monotonic() - started < LIMIT_SECONDS
    assert "Read timeout on endpoint URL" in caplog.text
    assert "Raise --credential-timeout" in caplog.text
