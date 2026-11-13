"""--credential-timeout bounds the sign-in calls (AssumeRole, identity checks)."""

from unittest.mock import MagicMock, patch

from inventag.core.cloud_bom_generator import (
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from inventag.core.credential_manager import CredentialManager

ROLE = "arn:aws:iam::123456789012:role/R"
TEMP = {
    "Credentials": {
        "AccessKeyId": "ASIAEXAMPLE",
        "SecretAccessKey": "secret-value-123456",
        "SessionToken": "token-value-123456",
    }
}


def test_generator_assume_role_uses_the_timeout(tmp_path):
    generator = CloudBOMGenerator(
        MultiAccountConfig(
            output_directory=str(tmp_path), credential_validation_timeout=7
        )
    )
    with patch("inventag.core.cloud_bom_generator.boto3.Session") as session_class:
        sts = session_class.return_value.client.return_value
        sts.assume_role.return_value = TEMP
        generator._assume_role_session(ROLE, "123456789012")
    config = session_class.return_value.client.call_args.kwargs["config"]
    assert (config.connect_timeout, config.read_timeout) == (7, 7)


def test_credential_manager_assume_role_uses_the_timeout():
    manager = CredentialManager(use_keyring=False)
    with patch("inventag.core.credential_manager.boto3.Session") as session_class:
        client = MagicMock()
        client.assume_role.return_value = TEMP
        client.get_caller_identity.return_value = {"Account": "123456789012"}
        session_class.return_value.client.return_value = client
        manager.validate_account_credentials(
            AccountCredentials(account_id="123456789012", role_arn=ROLE),
            test_regions=False,
            test_services=False,
            timeout=9,
        )
    configs = [
        c.kwargs.get("config") for c in session_class.return_value.client.call_args_list
    ]
    assert configs and all(c is not None and c.connect_timeout == 9 for c in configs)
