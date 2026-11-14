"""``--validate-config-only`` checks every file it is given (D-REF-1), and a
service descriptions file that the run will ignore is named (D-REF-4).
Offline; no AWS call is made in this mode."""

import importlib
import logging
import sys

import pytest

from inventag.cli.config_validator import ConfigValidator
from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    yield
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def run_cli(capsys, *args):
    old = sys.argv
    sys.argv = ["inventag", *args]
    code = 0
    try:
        cli_main.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_validate_config_only_exits_1_on_a_bom_config_that_a_run_refuses(
    tmp_path, capsys
):
    bad = tmp_path / "bom.yaml"
    bad.write_text("max_worker_threads: many\n")
    code, text = run_cli(capsys, "--validate-config-only", "--bom-config", str(bad))
    assert "max_worker_threads" in text
    assert code == 1  # the real run exits 1 on this file


def test_validate_config_only_accepts_a_good_bom_config(tmp_path, capsys):
    good = tmp_path / "bom.yaml"
    good.write_text("max_worker_threads: 4\n")
    code, text = run_cli(capsys, "--validate-config-only", "--bom-config", str(good))
    assert code == 0
    assert "ERROR" not in text


def test_validate_config_only_warns_about_unknown_bom_config_keys(tmp_path, capsys):
    odd = tmp_path / "bom.yaml"
    odd.write_text("no_such_setting: 1\n")
    code, text = run_cli(capsys, "--validate-config-only", "--bom-config", str(odd))
    assert code == 0  # a warning, as in a real run
    assert "no_such_setting" in text


def test_service_descriptions_file_without_the_key_is_named_as_ignored(tmp_path):
    path = tmp_path / "sd.yaml"
    path.write_text("ec2:\n  default_description: hello\n")
    result = ConfigValidator().validate_service_descriptions_file(str(path))
    assert result.is_valid is True  # exit codes do not change
    assert any("service_descriptions" in w and "ignore" in w for w in result.warnings)


def test_service_descriptions_entry_without_description_is_named(tmp_path):
    path = tmp_path / "sd.yaml"
    path.write_text("service_descriptions:\n  EC2:\n    Instance:\n      note: x\n")
    result = ConfigValidator().validate_service_descriptions_file(str(path))
    assert result.is_valid is True
    assert any("EC2/Instance" in w and "description" in w for w in result.warnings)


def test_a_valid_service_descriptions_file_has_no_warning(tmp_path):
    path = tmp_path / "sd.yaml"
    path.write_text(
        "service_descriptions:\n  EC2:\n    Instance:\n      description: A server\n"
    )
    result = ConfigValidator().validate_service_descriptions_file(str(path))
    assert result.is_valid is True and result.warnings == []


def test_validate_config_only_prints_the_service_descriptions_warning(tmp_path, capsys):
    path = tmp_path / "sd.yaml"
    path.write_text("ec2:\n  default_description: hello\n")
    code, text = run_cli(
        capsys, "--validate-config-only", "--service-descriptions", str(path)
    )
    assert code == 0
    assert "service_descriptions" in text
