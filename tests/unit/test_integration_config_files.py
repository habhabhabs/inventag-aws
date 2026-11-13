"""--bom-config, --accounts-file, --tag-mappings and --service-descriptions go
through the strict settings loader (reporting/settings_loader.py)."""

import json
import logging

import pytest

from inventag.cli.config_validator import ConfigValidator
from inventag.cli.main import create_multi_account_config, create_parser


def _args(tmp_path, *extra):
    return create_parser().parse_args(
        ["--account-regions", "us-east-1", "--output-directory", str(tmp_path), *extra]
    )


def test_bom_config_wrong_type_stops_with_the_key_named(tmp_path, caplog):
    path = tmp_path / "bom.yaml"
    path.write_text("max_worker_threads: many\n")
    with pytest.raises(SystemExit) as e:
        create_multi_account_config(_args(tmp_path, "--bom-config", str(path)))
    assert e.value.code == 1
    assert "max_worker_threads" in caplog.text


def test_bom_config_values_are_applied_and_unknown_keys_warned(tmp_path, caplog):
    path = tmp_path / "bom.json"
    path.write_bytes(
        b"\xef\xbb\xbf"  # a UTF-8 byte order mark is accepted
        + json.dumps({"max_worker_threads": 3, "colour": "blue"}).encode()
    )
    caplog.set_level(logging.WARNING)
    config = create_multi_account_config(_args(tmp_path, "--bom-config", str(path)))
    assert config.bom_processing_config.max_worker_threads == 3
    assert "ignored unknown key(s) colour" in caplog.text


def test_bom_config_duplicate_key_is_refused(tmp_path, caplog):
    path = tmp_path / "bom.yaml"
    path.write_text("max_worker_threads: 2\nmax_worker_threads: 4\n")
    with pytest.raises(SystemExit):
        create_multi_account_config(_args(tmp_path, "--bom-config", str(path)))
    assert "max_worker_threads" in caplog.text


@pytest.mark.parametrize(
    "method", ["validate_tag_mappings_file", "validate_service_descriptions_file"]
)
def test_empty_and_duplicate_files_give_a_clear_error(tmp_path, method):
    validator = ConfigValidator()
    empty = tmp_path / "empty.yaml"
    empty.write_text("")
    result = getattr(validator, method)(str(empty))
    assert not result.is_valid and "empty" in " ".join(result.errors)
    dup = tmp_path / "dup.yaml"
    dup.write_text("a:\n  x: 1\na:\n  x: 2\n")
    result = getattr(validator, method)(str(dup))
    assert not result.is_valid and "a" in " ".join(result.errors)


def test_accounts_file_with_byte_order_mark_is_read(tmp_path):
    path = tmp_path / "accounts.json"
    data = {"accounts": [{"account_id": "123456789012", "regions": ["us-east-1"]}]}
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(data).encode())
    result = ConfigValidator().validate_accounts_file(str(path))
    assert result.is_valid, result.errors
    assert result.config == data
