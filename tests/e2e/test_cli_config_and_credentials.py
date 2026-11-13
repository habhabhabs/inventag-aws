"""Configuration-file validation and credential failures, through ``main()``.

None of these runs needs AWS: they check what the CLI says, and the exit code
(1 for an invalid file or bad credentials), before any scan starts.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
)

pytestmark = pytest.mark.e2e

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def offline(run_cli, *args):
    # --verbose: the confirmation lines are INFO messages.
    return run_cli("--verbose", *args, with_output_dir=False, fast=False)


class TestValidateConfigOnly:
    def test_the_shipped_examples_are_valid(self, run_cli):
        result = offline(
            run_cli,
            "--validate-config-only",
            "--service-descriptions",
            str(EXAMPLES / "service-descriptions-example.yaml"),
            "--tag-mappings",
            str(EXAMPLES / "tag-mappings-example.yaml"),
            "--accounts-file",
            str(EXAMPLES / "accounts_basic.json"),
        )
        assert result.code == 0, result.text
        assert "All specified configuration files are valid" in result.text
        assert "No AWS call was made" in result.text

    @pytest.mark.parametrize(
        "flag", ["--service-descriptions", "--tag-mappings", "--accounts-file"]
    )
    def test_a_missing_file_is_exit_1(self, run_cli, flag):
        result = offline(
            run_cli, "--validate-config-only", flag, "/nonexistent/file.yaml"
        )
        assert result.code == 1
        assert "not found" in result.text.lower() or "invalid" in result.text.lower()

    def test_service_descriptions_that_are_a_list_are_exit_1(self, run_cli, tmp_path):
        bad = tmp_path / "descriptions.json"
        bad.write_text(json.dumps(["not", "a", "dict"]))
        result = offline(
            run_cli, "--validate-config-only", "--service-descriptions", str(bad)
        )
        assert result.code == 1
        assert "must be a dictionary" in result.text

    def test_service_descriptions_with_a_non_string_description_are_exit_1(
        self, run_cli, tmp_path
    ):
        bad = tmp_path / "descriptions.json"
        bad.write_text(json.dumps({"S3": {"default_description": 42}}))
        result = offline(
            run_cli, "--validate-config-only", "--service-descriptions", str(bad)
        )
        assert result.code == 1
        assert "default_description must be a string" in result.text

    def test_an_unsupported_file_type_is_exit_1(self, run_cli, tmp_path):
        bad = tmp_path / "descriptions.txt"
        bad.write_text("S3: x")
        result = offline(
            run_cli, "--validate-config-only", "--service-descriptions", str(bad)
        )
        assert result.code == 1
        assert "Unsupported file format" in result.text

    def test_an_accounts_file_without_accounts_is_exit_1(self, run_cli, tmp_path):
        bad = tmp_path / "accounts.json"
        bad.write_text(json.dumps({"settings": {}}))
        result = offline(run_cli, "--validate-config-only", "--accounts-file", str(bad))
        assert result.code == 1

    def test_unparseable_yaml_is_exit_1(self, run_cli, tmp_path):
        bad = tmp_path / "mappings.yaml"
        bad.write_text("a: [unclosed")
        result = offline(run_cli, "--validate-config-only", "--tag-mappings", str(bad))
        assert result.code == 1


class FailingSts:
    """Stands in for ``boto3.Session`` so the early credential check fails."""

    def __init__(self, error):
        self.error = error

    def __call__(self, *args, **kwargs):
        session = MagicMock()
        session.client.return_value.get_caller_identity.side_effect = self.error
        return session


def client_error(code):
    return ClientError({"Error": {"Code": code, "Message": f"{code} message"}}, "x")


class TestCredentialFailure:
    @pytest.mark.parametrize(
        "error, expected",
        [
            (client_error("InvalidClientTokenId"), "Invalid or expired security token"),
            (client_error("SignatureDoesNotMatch"), "Invalid AWS Secret Access Key"),
            (client_error("AccessDenied"), "don't have sufficient permissions"),
            (client_error("TokenRefreshRequired"), "aws sso login"),
            (client_error("ExpiredToken"), "Error Code: ExpiredToken"),
            (NoCredentialsError(), "No AWS credentials found"),
            (
                EndpointConnectionError(endpoint_url="https://sts.example"),
                "Unexpected error validating credentials",
            ),
        ],
        ids=lambda v: (
            type(v).__name__
            + getattr(v, "response", {}).get("Error", {}).get("Code", "")
            if not isinstance(v, str)
            else ""
        ),
    )
    def test_bad_credentials_stop_the_run_with_exit_1_and_advice(
        self, run_cli, error, expected
    ):
        with (
            patch("inventag.cli.main.boto3.Session", FailingSts(error)),
            patch("inventag.cli.main.CloudBOMGenerator") as generator,
        ):
            result = run_cli("--create-excel", fast=False)
        assert result.code == 1
        assert expected in result.text
        assert "Cannot proceed with invalid AWS credentials" in result.text
        generator.assert_not_called()  # nothing was scanned

    def test_validate_config_only_does_not_check_credentials(self, run_cli):
        with patch("inventag.cli.main.boto3.Session", FailingSts(NoCredentialsError())):
            result = offline(
                run_cli,
                "--validate-config-only",
                "--service-descriptions",
                str(EXAMPLES / "service-descriptions-example.yaml"),
            )
        # --validate-config-only never checks credentials: it is an offline check.
        assert result.code == 0, result.text
        assert "No AWS call was made" in result.text
