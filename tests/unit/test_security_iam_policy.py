"""The least-privilege IAM policy must be explicit, read-only and real."""

import json
from pathlib import Path

import botocore.session
import pytest

from inventag.security.iam_policy import (
    READ_ONLY_ACTIONS,
    all_policy_actions,
    build_read_only_policy,
    build_s3_upload_statement,
)
from inventag.security.read_only_guard import READ_ONLY_PREFIXES, ReadOnlyGuard

REPO_ROOT = Path(__file__).resolve().parents[2]
_session = botocore.session.get_session()


def test_no_wildcards_and_no_known_dangerous_grants():
    actions = all_policy_actions()
    assert all("*" not in action for action in actions)
    for forbidden in (
        "config:*",
        "resource-groups:*",
        "lambda:GetFunction",
        "secretsmanager:GetSecretValue",
        "s3:GetObject",
        "iam:Get*",
    ):
        assert forbidden not in actions


@pytest.mark.parametrize("action, target", sorted(READ_ONLY_ACTIONS.items()))
def test_each_action_maps_to_a_real_read_only_api_operation(action, target):
    service, operation = target
    model = _session.get_service_model(service)
    assert operation in model.operation_names, f"{service} has no {operation}"
    assert operation.startswith(READ_ONLY_PREFIXES)
    allowed, _ = ReadOnlyGuard().evaluate(service, operation)
    assert allowed, f"{action} would be blocked by the read-only guard"
    # IAM action name equals the API name except for documented S3 cases.
    iam_name = action.split(":", 1)[1]
    if iam_name != operation:
        assert action in {"s3:ListAllMyBuckets", "s3:GetEncryptionConfiguration"}


def test_apigateway_statement_excludes_api_keys():
    statement = build_read_only_policy()["Statement"][1]
    assert statement["Action"] == ["apigateway:GET"]
    assert not any("apikeys" in r for r in statement["Resource"])


def test_partition_is_applied():
    statement = build_read_only_policy("aws-us-gov")["Statement"][1]
    assert all(r.startswith("arn:aws-us-gov:") for r in statement["Resource"])


def test_upload_statement_requires_encryption_header():
    statement = build_s3_upload_statement("reports", "bom/")
    assert statement["Resource"] == ["arn:aws:s3:::reports/bom/*"]
    assert statement["Condition"] == {
        "Null": {"s3:x-amz-server-side-encryption": "false"}
    }


def test_shipped_policy_file_matches_module():
    shipped = json.loads(
        (REPO_ROOT / "config" / "defaults" / "iam-policy-read-only.json").read_text()
    )
    expected = build_read_only_policy()
    upload = build_s3_upload_statement("YOUR-REPORTS-BUCKET-NAME", "bom-reports")
    upload["Sid"] = "OptionalS3ReportUpload"
    expected["Statement"].append(upload)
    assert shipped == expected


def test_setup_cross_account_roles_uses_least_privilege_policy(monkeypatch):
    from moto import mock_aws

    from inventag.core.cloud_bom_generator import AccountCredentials
    from inventag.core.credential_manager import CredentialManager

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        import boto3

        manager = CredentialManager(use_keyring=False)
        results = manager.setup_cross_account_roles(
            [AccountCredentials(account_id="123456789012")],
            role_name="InvenTagReadOnly",
            trusted_account_id="210987654321",
            external_id="ext-id-123",
            allow_iam_writes=True,
        )
        assert results["123456789012"]["success"], results
        assert (
            results["123456789012"]["role_arn"]
            == "arn:aws:iam::123456789012:role/InvenTagReadOnly"
        )
        iam = boto3.client("iam")
        policy_arn = results["123456789012"]["policy_arn"]
        version = iam.get_policy(PolicyArn=policy_arn)["Policy"]["DefaultVersionId"]
        document = iam.get_policy_version(PolicyArn=policy_arn, VersionId=version)[
            "PolicyVersion"
        ]["Document"]
        if isinstance(document, str):
            document = json.loads(document)
        assert document == build_read_only_policy()
        trust = iam.get_role(RoleName="InvenTagReadOnly")["Role"][
            "AssumeRolePolicyDocument"
        ]
        if isinstance(trust, str):
            trust = json.loads(trust)
        statement = trust["Statement"][0]
        assert statement["Principal"]["AWS"] == "arn:aws:iam::210987654321:root"
        assert statement["Condition"] == {
            "StringEquals": {"sts:ExternalId": "ext-id-123"}
        }


def test_setup_cross_account_roles_rejects_bad_input():
    from inventag.core.credential_manager import CredentialManager
    from inventag.security.arn import InvalidRoleError

    manager = CredentialManager(use_keyring=False)
    with pytest.raises(InvalidRoleError):
        manager.setup_cross_account_roles(
            [],
            role_name="bad name!",
            trusted_account_id="123456789012",
            allow_iam_writes=True,
        )
    with pytest.raises(ValueError):
        manager.setup_cross_account_roles(
            [], role_name="Ok", trusted_account_id="12345", allow_iam_writes=True
        )
