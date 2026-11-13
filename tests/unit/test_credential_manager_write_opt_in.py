"""setup_cross_account_roles() writes to IAM: it needs an explicit opt-in."""

import boto3
import pytest
from moto import mock_aws

from inventag.core.cloud_bom_generator import AccountCredentials
from inventag.core.credential_manager import CredentialManager
from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    install_global_guard,
    uninstall_global_guard,
)


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    uninstall_global_guard()
    with mock_aws():
        yield
    uninstall_global_guard()


ACCOUNT = [AccountCredentials(account_id="123456789012")]


@pytest.mark.parametrize("value", [None, False, "yes", 1])
def test_refuses_without_the_opt_in_and_makes_no_call(aws, value):
    kwargs = {} if value is None else {"allow_iam_writes": value}
    with pytest.raises(ReadOnlyViolationError, match="allow_iam_writes=True"):
        CredentialManager(use_keyring=False).setup_cross_account_roles(
            ACCOUNT, trusted_account_id="210987654321", **kwargs
        )
    assert boto3.client("iam").list_roles()["Roles"] == []


def test_opt_in_must_be_a_keyword(aws):
    with pytest.raises(TypeError):
        CredentialManager(use_keyring=False).setup_cross_account_roles(
            ACCOUNT, "R", "210987654321", None, True
        )


def test_guard_still_blocks_it_with_the_opt_in(aws):
    guard = install_global_guard(ReadOnlyGuard())
    results = CredentialManager(use_keyring=False).setup_cross_account_roles(
        ACCOUNT, trusted_account_id="210987654321", allow_iam_writes=True
    )
    assert results["123456789012"]["success"] is False
    assert "iam:CreateRole" in results["123456789012"]["error"]
    assert guard.audit_report()["blocked_calls"] >= 1
    uninstall_global_guard()
    assert boto3.client("iam").list_roles()["Roles"] == []


def test_cli_never_calls_it():
    import inspect

    from inventag.cli import main

    assert "setup_cross_account_roles" not in inspect.getsource(main)
