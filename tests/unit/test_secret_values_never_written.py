"""Secret values must not reach reports, state snapshots, logs or the console."""

import importlib
import io
import json
import logging
import os
import sys
import zipfile

import boto3
import pytest
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard
from inventag.security.redaction import REDACTED, redact
from inventag.security.secret_values import mask_secret_values as scrub_secret_values

cli_main = importlib.import_module("inventag.cli.main")

LAMBDA_SECRET = "LambdaEnvPasswordValue-XYZ-98765"
ACCOUNTS_FILE_SECRET = "AccountsFileSecretValue0123456789abcdef"


# ------------------------------------------------------------- log redaction
@pytest.mark.parametrize(
    "text, secret",
    [
        (
            'Response body: b\'{"Environment": {"Variables": '
            '{"DB_PASSWORD": "pw-1234567", "J": "{\\"a\\": \\"}\\"}"}}}\'',
            "pw-1234567",
        ),
        ("{'Environment': {'Variables': {'K': 'pw-1234567'}}}", "pw-1234567"),
        (
            "Action=AssumeRoleWithWebIdentity&WebIdentityToken=eyJhbGciOi.payload.sig"
            "&Version=2011-06-15",
            "eyJhbGciOi.payload.sig",
        ),
        ('{"clientSecret": "cs-1234567", "refreshToken": "rt-1234567"}', "cs-1234567"),
        ('{"clientSecret": "cs-1234567", "refreshToken": "rt-1234567"}', "rt-1234567"),
        ('{"idToken": "id-1234567"}', "id-1234567"),
    ],
)
def test_redact_removes_new_secret_patterns(text, secret):
    assert secret not in redact(text)


def test_redact_keeps_environment_variable_names():
    out = redact('{"Variables": {"DB_PASSWORD": "pw-1234567"}}')
    assert "DB_PASSWORD" in out and REDACTED in out


# ------------------------------------------------------ resource data scrubber
def test_scrub_secret_values():
    resource = {
        "service": "Lambda",
        "environment": "prod",  # InvenTag's own tag-derived field stays
        "raw_data": {
            "Environment": {"Variables": {"DB_PASSWORD": "x", "MODE": "y"}},
            "containerDefinitions": [
                {"environment": [{"name": "TOKEN", "value": "z"}], "image": "i"}
            ],
            "PendingModifiedValues": {"MasterUserPassword": "p"},
            "UserData": "IyEvYmluL2Jhc2g=",
            "Tags": [{"Key": "Owner", "Value": "team"}],
            "AuthTokenEnabled": True,
        },
    }
    scrubbed = scrub_secret_values(resource)
    raw = scrubbed["raw_data"]
    assert raw["Environment"]["Variables"] == {
        "DB_PASSWORD": REDACTED,
        "MODE": REDACTED,
    }
    assert raw["containerDefinitions"][0]["environment"] == [
        {"name": "TOKEN", "value": REDACTED}
    ]
    assert raw["containerDefinitions"][0]["image"] == "i"
    assert raw["PendingModifiedValues"]["MasterUserPassword"] == REDACTED
    assert raw["UserData"] == REDACTED
    assert raw["Tags"] == [{"Key": "Owner", "Value": "team"}]
    assert raw["AuthTokenEnabled"] is True
    assert scrubbed["environment"] == "prod"
    # The input is not modified.
    assert resource["raw_data"]["Environment"]["Variables"]["DB_PASSWORD"] == "x"


# --------------------------------------------------------------- end to end
@pytest.fixture
def aws(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        yield
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    redaction.clear_registered_secrets()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def _readable(path):
    data = path.read_bytes()
    if path.suffix in (".xlsx", ".docx"):
        with zipfile.ZipFile(path) as z:
            data = b"".join(z.read(n) for n in z.namelist())
    return data


def test_lambda_environment_and_account_keys_are_never_written(
    aws, tmp_path, monkeypatch, capsys
):
    iam = boto3.client("iam")
    role = iam.create_role(RoleName="r", AssumeRolePolicyDocument="{}")["Role"]["Arn"]
    code = io.BytesIO()
    with zipfile.ZipFile(code, "w") as z:
        z.writestr("h.py", "def h(e, c):\n    return 1\n")
    boto3.client("lambda").create_function(
        FunctionName="fn",
        Runtime="python3.12",
        Role=role,
        Handler="h.h",
        Code={"ZipFile": code.getvalue()},
        Environment={"Variables": {"DB_PASSWORD": LAMBDA_SECRET}},
    )
    (tmp_path / "accounts.json").write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "123456789012",
                        "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                        "secret_access_key": ACCOUNTS_FILE_SECRET,
                        "regions": ["us-east-1"],
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "inventag",
            "--accounts-file",
            "accounts.json",
            "--create-excel",
            "--debug",
            "--log-file",
            "logs/run.log",
            "--no-billing-validation",
        ],
    )
    try:
        cli_main.main()
    except SystemExit as e:
        assert e.code in (0, None)
    console = capsys.readouterr()

    written = [
        p for p in tmp_path.rglob("*") if p.is_file() and p.name != "accounts.json"
    ]
    assert any(p.suffix == ".xlsx" for p in written)
    assert any(p.parent.name == "state" for p in written)
    for path in written:
        data = _readable(path)
        assert LAMBDA_SECRET.encode() not in data, path
        assert ACCOUNTS_FILE_SECRET.encode() not in data, path
    for stream in (console.out, console.err):
        assert LAMBDA_SECRET not in stream
        assert ACCOUNTS_FILE_SECRET not in stream
    # The variable name is still in the report: it is inventory, not a secret.
    report = next(p for p in written if p.suffix == ".xlsx")
    assert b"DB_PASSWORD" in _readable(report)
    assert os.path.exists(tmp_path / "logs" / "run.log")
