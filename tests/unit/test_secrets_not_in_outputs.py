"""A secret planted in a mocked AWS account must not reach any file the CLI writes."""

import io
import json
import os
import zipfile

import pytest

from tests.integration.templating.test_report_templates import run_inventag

SECRET = "S3CR3T-PLANTED-VALUE-123"


@pytest.fixture
def secret_account(monkeypatch):
    moto = pytest.importorskip("moto")
    for key in ("AWS_PROFILE", "AWS_ENDPOINT_URL", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")
    from inventag.security.read_only_guard import uninstall_global_guard

    uninstall_global_guard()
    with moto.mock_aws():
        import boto3

        role = boto3.client("iam").create_role(
            RoleName="r", AssumeRolePolicyDocument="{}"
        )["Role"]["Arn"]
        code = io.BytesIO()
        with zipfile.ZipFile(code, "w") as z:
            z.writestr("a.py", "def h(e, c): pass")
        boto3.client("lambda").create_function(
            FunctionName="fn",
            Runtime="python3.12",
            Role=role,
            Handler="a.h",
            Code={"ZipFile": code.getvalue()},
            Environment={"Variables": {"DB_PASSWORD": SECRET}},
        )
        boto3.client("cloudformation").create_stack(
            StackName="st",
            TemplateBody=json.dumps(
                {
                    "Parameters": {"P": {"Type": "String"}},
                    "Resources": {"B": {"Type": "AWS::S3::Bucket"}},
                }
            ),
            Parameters=[{"ParameterKey": "P", "ParameterValue": SECRET}],
        )
        boto3.client("glue").create_connection(
            ConnectionInput={
                "Name": "gc",
                "ConnectionType": "JDBC",
                "ConnectionProperties": {"PASSWORD": SECRET},
            }
        )
        yield
    uninstall_global_guard()


def blobs(folder):
    for root, _, files in os.walk(folder):
        for name in files:
            path = os.path.join(root, name)
            if name.endswith((".xlsx", ".docx")):
                with zipfile.ZipFile(path) as z:
                    yield path, b"".join(z.read(n) for n in z.namelist())
            else:
                with open(path, "rb") as handle:
                    yield path, handle.read()


@pytest.mark.parametrize("extra", [[], ["--template", "standard-bom"]])
def test_secret_values_are_not_in_report_files(
    secret_account, monkeypatch, tmp_path, extra
):
    code = run_inventag(
        monkeypatch,
        tmp_path,
        "--create-excel",
        "--create-word",
        "--account-regions",
        "us-east-1",
        "--disable-state-management",
        *extra,
    )
    assert code == 0
    found = list(blobs(tmp_path / "bom_output"))
    assert any(p.endswith(".xlsx") for p, _ in found)
    leaked = [p for p, data in found if SECRET.encode() in data]
    assert leaked == []


def test_names_of_the_variables_are_still_listed(secret_account, monkeypatch, tmp_path):
    run_inventag(
        monkeypatch,
        tmp_path,
        "--create-excel",
        "--account-regions",
        "us-east-1",
        "--disable-state-management",
    )
    data = b"".join(d for p, d in blobs(tmp_path / "bom_output") if p.endswith("xlsx"))
    assert b"DB_PASSWORD" in data
