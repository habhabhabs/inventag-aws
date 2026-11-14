"""Message texts only (A-20, A-27, A-41): the cause, the next step, the error
type. Every exit code is asserted and equals v1.2.0 (S2 catalogue cases A1,
A4, A6, A7, D1, D2, D8, F01, K3, K4). Offline; no AWS call is made."""

import importlib
import logging
import sys
import traceback

import botocore.client
import botocore.exceptions
import pytest

from inventag.cli.config_validator import ConfigValidator
from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")


@pytest.fixture
def env(monkeypatch, tmp_path):
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-creds"))
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def run_cli(capsys, *args):
    old = sys.argv
    sys.argv = ["inventag", *args]
    code, extra = 0, ""
    try:
        cli_main.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception:
        code, extra = 1, traceback.format_exc()
    finally:
        sys.argv = old
    captured = capsys.readouterr()
    return code, captured.out + captured.err + extra


def api_call_raises(monkeypatch, error):
    def fake(self, operation_name, api_params):
        raise error

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", fake)


# ------------------------------------------------ A-41: the two refusals (D1, D2)
def test_compliance_standard_refusal_offers_an_alternative_exit_2(env, capsys):
    code, text = run_cli(capsys, "--compliance-standard", "hipaa", "--create-excel")
    assert code == 2
    assert "Compliance-standard enforcement is not implemented yet" in text
    assert "inventag --template security-baseline --create-excel" in text


def test_disable_production_safety_refusal_says_what_to_do_exit_2(env, capsys):
    code, text = run_cli(capsys, "--disable-production-safety", "--create-excel")
    assert code == 2
    assert "non-read AWS calls are always blocked" in text
    assert "Remove this option" in text
    assert "inventag --validate-operations ec2:DescribeInstances" in text


# ------------------------------------------------ A-20: credential check (A1, A7, K3)
def test_no_credentials_text_names_sso_login_and_aws_profile_exit_1(env, capsys):
    code, text = run_cli(capsys, "--create-excel", "--account-regions", "us-east-1")
    assert code == 1
    assert "No AWS credentials found" in text
    assert "aws sso login --profile <name>" in text
    assert "AWS_PROFILE" in text


def test_unreachable_endpoint_says_network_and_proxy_exit_1(env, capsys, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-tests-only")
    api_call_raises(
        monkeypatch,
        botocore.exceptions.EndpointConnectionError(
            endpoint_url="https://sts.us-east-1.amazonaws.com/"
        ),
    )
    code, text = run_cli(capsys, "--create-excel", "--account-regions", "us-east-1")
    assert code == 1
    assert "Could not connect to the endpoint URL" in text  # the old text stays
    assert "network" in text and "HTTPS_PROXY" in text


def test_timeout_names_the_option_to_raise_exit_1(env, capsys, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-tests-only")
    api_call_raises(
        monkeypatch,
        botocore.exceptions.ReadTimeoutError(endpoint_url="https://sts/"),
    )
    code, text = run_cli(capsys, "--create-excel", "--account-regions", "us-east-1")
    assert code == 1
    assert "--credential-timeout" in text


def test_other_credential_check_failure_names_the_error_type_exit_1(
    env, capsys, monkeypatch
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-tests-only")
    api_call_raises(monkeypatch, RuntimeError("synthetic"))
    code, text = run_cli(capsys, "--create-excel", "--account-regions", "us-east-1")
    assert code == 1
    assert "RuntimeError: synthetic" in text


# ------------------------------------------------ A-20: run failures (D8, K4, F01)
def fake_generator(result=None, error=None):
    class Fake:
        def __init__(self, config):
            pass

        def generate_comprehensive_bom(self, **kwargs):
            if error:
                raise error
            return result

    return Fake


def run_with_generator(env, capsys, monkeypatch, generator, *extra):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-tests-only")
    monkeypatch.setattr(cli_main, "CloudBOMGenerator", generator)
    monkeypatch.setattr(cli_main, "validate_aws_credentials_early", lambda t: True)
    return run_cli(capsys, "--create-excel", "--no-billing-validation", *extra)


def test_all_accounts_failed_summary_gives_the_cause_per_account_exit_1(
    env, capsys, monkeypatch
):
    result = {
        "success": False,
        "error": "Resource discovery failed for all 1 configured account(s)",
        "failed_accounts": [],
        "account_contexts": {
            "222222222222": {
                "error_count": 1,
                "errors": ["Context establishment failed: AccessDenied sts:AssumeRole"],
            }
        },
    }
    code, text = run_with_generator(env, capsys, monkeypatch, fake_generator(result))
    assert code == 1
    assert "222222222222: 1 errors" in text or "222222222222: 1 error" in text
    assert "AccessDenied sts:AssumeRole" in text


def test_unexpected_error_names_the_type_and_the_traceback_option_exit_1(
    env, capsys, monkeypatch
):
    code, text = run_with_generator(
        env, capsys, monkeypatch, fake_generator(error=ValueError("synthetic"))
    )
    assert code == 1
    assert "Unexpected error: ValueError: synthetic" in text
    assert "--debug" in text


# ------------------------------------------------ A-27: accounts file warnings
def validate(tmp_path, text):
    path = tmp_path / "accounts.yaml"
    path.write_text(text)
    path.chmod(0o600)
    return ConfigValidator().validate_accounts_file(str(path))


def test_duplicate_account_id_is_warned(tmp_path):
    result = validate(
        tmp_path,
        "accounts:\n"
        "  - {account_id: '111111111111', profile_name: a}\n"
        "  - {account_id: '111111111111', profile_name: b}\n",
    )
    assert result.is_valid is True  # exit codes do not change
    assert any(
        "111111111111" in w and "Account 1" in w and "Account 2" in w
        for w in result.warnings
    )


def test_unknown_keys_are_warned_with_the_valid_ones(tmp_path):
    result = validate(
        tmp_path,
        "accounts:\n  - {account_id: '111111111111', profil_name: a}\n"
        "settngs: {}\n"
        "settings: {max_concurent_accounts: 2}\n",
    )
    assert result.is_valid is True
    text = "\n".join(result.warnings)
    assert "profil_name" in text and "profile_name" in text
    assert "settngs" in text
    assert "max_concurent_accounts" in text


def test_a_clean_accounts_file_has_no_warning(tmp_path):
    result = validate(
        tmp_path,
        "accounts:\n  - {account_id: '111111111111', profile_name: a, regions: [x]}\n"
        "settings: {max_concurrent_accounts: 2}\n",
    )
    assert result.is_valid is True and result.warnings == []
