"""Tests for credential/token redaction in logs (inventag.security.redaction)."""

import io
import logging

import boto3
import pytest
from moto import mock_aws

from inventag.cli.logging_setup import setup_logging
from inventag.core.cloud_bom_generator import AccountCredentials
from inventag.security import redaction
from inventag.security.redaction import REDACTED, redact, register_secret

FAKE_TOKEN = "FAKEtokenFAKEtokenFAKEtoken0123456789"
FAKE_SECRET = "FAKEsecretFAKEsecretFAKEsecret01234567"


@pytest.fixture(autouse=True)
def _reset_redaction():
    redaction.clear_registered_secrets()
    yield
    redaction.clear_registered_secrets()
    redaction.uninstall_log_record_redaction()


@pytest.mark.parametrize(
    "text, secret",
    [
        (f"<SecretAccessKey>{FAKE_SECRET}</SecretAccessKey>", FAKE_SECRET),
        (f"<SessionToken>{FAKE_TOKEN}</SessionToken>", FAKE_TOKEN),
        (f'{{"SecretAccessKey": "{FAKE_SECRET}"}}', FAKE_SECRET),
        (f"{{'aws_session_token': '{FAKE_TOKEN}'}}", FAKE_TOKEN),
        (f"secret_access_key='{FAKE_SECRET}'", FAKE_SECRET),
        (f"{{'X-Amz-Security-Token': b'{FAKE_TOKEN}'}}", FAKE_TOKEN),
        (f"x-amz-security-token:{FAKE_TOKEN}", FAKE_TOKEN),
        (
            "https://b.s3.amazonaws.com/k?X-Amz-Algorithm=AWS4-HMAC-SHA256"
            f"&X-Amz-Credential=AKIAEXAMPLE%2F20261112&X-Amz-Security-Token={FAKE_TOKEN}"
            "&X-Amz-Signature=deadbeefdeadbeef",
            FAKE_TOKEN,
        ),
        (
            "Authorization: AWS4-HMAC-SHA256 Credential=AKIAEXAMPLE/20261112/us-east-1/"
            "sts/aws4_request, SignedHeaders=host;x-amz-date, Signature=abcdef0123456789",
            "abcdef0123456789",
        ),
        (
            "https://hooks.slack.com/services/T000/B000/FAKEslackWEBHOOKsecret",
            "FAKEslackWEBHOOKsecret",
        ),
        (
            "https://example.webhook.office.com/webhookb2/FAKEteamsSECRET@x/IncomingWebhook/abc",
            "FAKEteamsSECRET",
        ),
    ],
)
def test_redact_patterns(text, secret):
    out = redact(text)
    assert secret not in out
    assert REDACTED in out


def test_presigned_url_signature_removed():
    url = (
        "https://b.s3.amazonaws.com/k?X-Amz-Signature=0123456789abcdef"
        "&X-Amz-Credential=AKIAEXAMPLE"
    )
    out = redact(url)
    assert "0123456789abcdef" not in out
    assert "AKIAEXAMPLE" not in out


def test_redact_leaves_ordinary_text_alone():
    text = "Discovered 12 resources in us-east-1 for account 123456789012"
    assert redact(text) == text


def test_registered_secret_is_removed_anywhere():
    register_secret(FAKE_SECRET)
    assert FAKE_SECRET not in redact(f"weird context {FAKE_SECRET} here")


def test_short_values_are_not_registered():
    register_secret("abc")
    assert redact("abc def") == "abc def"


def test_account_credentials_repr_hides_secrets():
    creds = AccountCredentials(
        account_id="123456789012",
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key=FAKE_SECRET,
        session_token=FAKE_TOKEN,
    )
    text = repr(creds) + str(creds)
    assert FAKE_SECRET not in text
    assert FAKE_TOKEN not in text
    # Still accessible to code that needs it
    assert creds.secret_access_key == FAKE_SECRET


def test_debug_logging_never_writes_aws_credentials(tmp_path, monkeypatch):
    """Reproduces the --debug leak: botocore logs request tokens and AssumeRole
    response bodies. With setup_logging(debug=True) nothing secret may reach
    the console or the log file."""
    for var in ("AWS_PROFILE",):
        monkeypatch.delenv(var, raising=False)
    log_file = tmp_path / "logs" / "debug.log"
    console = io.StringIO()
    monkeypatch.setattr("sys.stdout", console)
    logger = setup_logging(debug=True, log_file=str(log_file))
    # A root handler like the one inventory.py may install with basicConfig.
    root_stream = io.StringIO()
    root_handler = logging.StreamHandler(root_stream)
    logging.getLogger().addHandler(root_handler)
    old_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.DEBUG)
    try:
        with mock_aws():
            session = boto3.Session(
                aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
                aws_secret_access_key=FAKE_SECRET,
                aws_session_token=FAKE_TOKEN,
                region_name="us-east-1",
            )
            response = session.client("sts").assume_role(
                RoleArn="arn:aws:iam::123456789012:role/InvenTagReadOnly",
                RoleSessionName="inventag-test",
            )
            assumed = response["Credentials"]
            logger.debug(f"assumed role response {response}")
        for handler in logger.handlers:
            handler.flush()
        outputs = {
            "console": console.getvalue(),
            "root": root_stream.getvalue(),
            "file": log_file.read_text(),
        }
    finally:
        logging.getLogger().removeHandler(root_handler)
        logging.getLogger().setLevel(old_level)
        for name in ("botocore", "boto3", "urllib3", "s3transfer", "inventag"):
            lg = logging.getLogger(name)
            lg.handlers.clear()
            lg.propagate = True
            lg.setLevel(logging.NOTSET)

    # botocore really did log the request at DEBUG (the test is meaningful)
    assert "sts" in outputs["file"].lower()
    assert "Response body" in outputs["file"] or "response body" in outputs["file"]
    for name, text in outputs.items():
        assert FAKE_TOKEN not in text, name
        assert FAKE_SECRET not in text, name
        assert assumed["SecretAccessKey"] not in text, name
        assert assumed["SessionToken"] not in text, name
    assert oct(log_file.stat().st_mode & 0o777) == "0o600"
