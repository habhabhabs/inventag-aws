"""Release-gate review: credentials never reach logs, files or reprs."""

import json
import logging
import os
import stat

import pytest

from inventag.core.cloud_bom_generator import AccountCredentials
from inventag.core.credential_manager import CredentialManager
from inventag.security import redaction

SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYREVIEWKEY01"
TOKEN = "IQoJb3JpZ2luX2VjEREVIEWSESSIONTOKEN0123456789"


@pytest.fixture(autouse=True)
def _clean():
    redaction.clear_registered_secrets()
    yield
    redaction.clear_registered_secrets()
    redaction.uninstall_log_record_redaction()


def _creds():
    return AccountCredentials(
        account_id="123456789012",
        access_key_id="AKIAREVIEWEXAMPLE",
        secret_access_key=SECRET,
        session_token=TOKEN,
    )


def test_repr_and_str_hide_keys():
    text = repr(_creds()) + str(_creds())
    assert SECRET not in text and TOKEN not in text


def test_session_creation_registers_keys_so_logs_and_tracebacks_hide_them(caplog):
    redaction.install_log_record_redaction()
    CredentialManager(use_keyring=False)._create_session_from_credentials(_creds())
    log = logging.getLogger("inventag.review")
    with caplog.at_level(logging.DEBUG):
        log.debug(f"debug {SECRET} {TOKEN}")
        try:
            raise RuntimeError(f"failed with key {SECRET}")
        except RuntimeError:
            log.exception("boom")
    formatter = redaction.RedactingFormatter(logging.Formatter())
    rendered = "\n".join(formatter.format(r) for r in caplog.records)
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert SECRET not in messages and TOKEN not in messages
    # Tracebacks are redacted by the CLI's handlers (RedactingFormatter).
    assert SECRET not in rendered and TOKEN not in rendered


@pytest.mark.parametrize("encrypt", [True, False])
def test_credential_file_is_owner_only_and_encrypted_when_asked(tmp_path, encrypt):
    manager = CredentialManager(use_keyring=False)
    path = tmp_path / "creds.json"
    manager.create_secure_credential_file(
        [_creds()], str(path), encrypt=encrypt, password="review-password-1"
    )
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    text = path.read_text()
    if encrypt:
        assert SECRET not in text and TOKEN not in text
        assert json.loads(text)["kdf_iterations"] >= 100_000
        loaded = manager.load_credential_file(str(path), password="review-password-1")
        assert loaded[0].secret_access_key == SECRET
    else:
        assert SECRET in text  # plaintext only when the caller asks for it
