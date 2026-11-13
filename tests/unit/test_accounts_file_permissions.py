"""An accounts file holding access keys should be private."""

import json
import os

import pytest

from inventag.cli.config_validator import ConfigValidator

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")


def write(tmp_path, account, mode):
    path = tmp_path / "accounts.json"
    path.write_text(json.dumps({"accounts": [account]}))
    os.chmod(path, mode)
    return str(path)


KEYS = {
    "account_id": "123456789012",
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "not-a-real-secret-value",
}


def test_readable_file_with_keys_warns(tmp_path):
    result = ConfigValidator().validate_accounts_file(write(tmp_path, KEYS, 0o644))
    assert result.is_valid
    assert any("chmod 600" in w and "0644" in w for w in result.warnings)
    assert not any("not-a-real-secret-value" in w for w in result.warnings)


def test_private_file_with_keys_does_not_warn(tmp_path):
    result = ConfigValidator().validate_accounts_file(write(tmp_path, KEYS, 0o600))
    assert not any("chmod" in w for w in result.warnings)


def test_readable_file_without_keys_does_not_warn(tmp_path):
    account = {"account_id": "123456789012", "profile_name": "p"}
    result = ConfigValidator().validate_accounts_file(write(tmp_path, account, 0o644))
    assert not any("chmod" in w for w in result.warnings)
