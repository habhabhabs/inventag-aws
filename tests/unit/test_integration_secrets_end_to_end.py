"""No planted secret value reaches any file or log of a full CLI run.

Distinct secret strings are planted in a moto account in every place the
shared deny-list (``inventag.security.secret_values``) covers: Lambda
environment, ECS container environment, CodeBuild PLAINTEXT variables, EC2
user data, CloudFormation parameters and Glue connection properties (plus a
Glue job argument). Two full CLI runs then write every artifact InvenTag can
write offline: Excel, Word, the tag-compliance JSON (``--template``), the state
snapshot, the audit output, and a debug-level log file. None may contain any
planted value. The variable names stay (they are inventory).
"""

import importlib
import io
import json
import logging
import sys
import zipfile

import boto3
import pytest
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")

SECRETS = {
    "lambda": "planted-lambda-env-5d1e",
    "ecs": "planted-ecs-env-9a4c",
    "codebuild": "planted-codebuild-var-3b7f",
    "userdata": "planted-ec2-userdata-c2e8",
    "cfn": "planted-cfn-param-71fa",
    "glue_conn": "planted-glue-conn-e04b",
    "glue_job": "planted-glue-job-arg-88d2",
    "glue_trigger": "planted-glue-trigger-arg-4c19",
    "cfn_output": "planted-cfn-output-d6a0",
    "json_text": "planted-json-in-text-0b7e",
}

TEMPLATE = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Parameters": {
        "DbPassword": {"Type": "String"},
        # A NoEcho value passed out through an output (OutputValue).
        "Conn": {"Type": "String", "NoEcho": True},
    },
    "Resources": {"Q": {"Type": "AWS::SQS::Queue"}},
    "Outputs": {"ConnOut": {"Value": {"Ref": "Conn"}}},
}


@pytest.fixture
def estate(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        _plant()
        yield
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    redaction.clear_registered_secrets()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def _plant():
    iam = boto3.client("iam")
    role = iam.create_role(RoleName="r", AssumeRolePolicyDocument="{}")["Role"]["Arn"]
    code = io.BytesIO()
    with zipfile.ZipFile(code, "w") as z:
        z.writestr("h.py", "def h(e, c):\n    return 1\n")
    boto3.client("lambda").create_function(
        FunctionName="fn-secret",
        Runtime="python3.12",
        Role=role,
        Handler="h.h",
        Code={"ZipFile": code.getvalue()},
        Environment={"Variables": {"DB_PASSWORD": SECRETS["lambda"]}},
    )
    ecs = boto3.client("ecs")
    ecs.create_cluster(clusterName="c1")
    ecs.register_task_definition(
        family="td-secret",
        containerDefinitions=[
            {
                "name": "app",
                "image": "nginx",
                "memory": 128,
                "environment": [{"name": "API_TOKEN", "value": SECRETS["ecs"]}],
            }
        ],
    )
    boto3.client("codebuild").create_project(
        name="cb-secret",
        source={"type": "S3", "location": "bucket/src.zip"},
        artifacts={"type": "S3", "location": "bucket"},
        environment={
            "type": "LINUX_CONTAINER",
            "image": "aws/codebuild/standard:7.0",
            "computeType": "BUILD_GENERAL1_SMALL",
            "environmentVariables": [
                {"name": "PW", "value": SECRETS["codebuild"], "type": "PLAINTEXT"}
            ],
        },
        serviceRole=role,
    )
    boto3.client("ec2").run_instances(
        ImageId="ami-12c6146b", MinCount=1, MaxCount=1, UserData=SECRETS["userdata"]
    )
    boto3.client("cloudformation").create_stack(
        StackName="stack-secret",
        TemplateBody=json.dumps(TEMPLATE),
        Parameters=[
            {"ParameterKey": "DbPassword", "ParameterValue": SECRETS["cfn"]},
            {"ParameterKey": "Conn", "ParameterValue": SECRETS["cfn_output"]},
        ],
    )
    glue = boto3.client("glue")
    glue.create_connection(
        ConnectionInput={
            "Name": "conn-secret",
            "ConnectionType": "JDBC",
            "ConnectionProperties": {
                "USERNAME": "admin",
                "PASSWORD": SECRETS["glue_conn"],
                "JDBC_CONNECTION_URL": "jdbc:mysql://db:3306/x",
            },
        }
    )
    glue.create_job(
        Name="job-secret",
        Role=role,
        Command={"Name": "glueetl", "ScriptLocation": "s3://b/s.py"},
        DefaultArguments={"--db-password": SECRETS["glue_job"]},
    )
    # Trigger arguments override job arguments; the name is not secret-like.
    glue.create_trigger(
        Name="trigger-secret",
        Type="ON_DEMAND",
        Actions=[
            {
                "JobName": "job-secret",
                "Arguments": {"--jdbc_url": f"jdbc:x://u:{SECRETS['glue_trigger']}@h"},
            }
        ],
    )
    # JSON kept as text (a Step Functions-like input) with a secret field.
    boto3.client("events").put_rule(
        Name="rule-secret",
        ScheduleExpression="rate(1 day)",
        Description="plain",
    )
    boto3.client("events").put_targets(
        Rule="rule-secret",
        Targets=[
            {
                "Id": "t",
                "Arn": role,
                "Input": json.dumps({"ApiPassword": SECRETS["json_text"]}),
            }
        ],
    )


def _run(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["inventag", *argv])
    try:
        cli_main.main()
    except SystemExit as e:
        return e.code or 0
    return 0


def _blob(path):
    data = path.read_bytes()
    if path.suffix in (".xlsx", ".docx"):
        with zipfile.ZipFile(path) as z:
            data = b"".join(z.read(n) for n in z.namelist())
    return data


def test_no_planted_secret_in_any_artifact_of_a_full_run(
    estate, tmp_path, monkeypatch, capsys, caplog
):
    caplog.set_level(logging.DEBUG)
    common = [
        "--account-regions",
        "us-east-1",
        "--no-billing-validation",
        "--debug",
    ]
    # Run 1: default report (Excel + Word), state snapshot, audit output, log.
    code = _run(
        monkeypatch,
        [
            *common,
            "--create-excel",
            "--create-word",
            "--output-directory",
            "out1",
            "--audit-output",
            "audit1.json",
            "--log-file",
            "logs/run1.log",
        ],
    )
    assert code == 0
    # Run 2: templated report with a tag policy (writes the JSON output).
    code = _run(
        monkeypatch,
        [
            *common,
            "--template",
            "standard-bom",
            "--template",
            "finops-cost-allocation",
            "--create-excel",
            "--output-directory",
            "out2",
            "--log-file",
            "logs/run2.log",
        ],
    )
    assert code in (0, 3)
    console = capsys.readouterr()

    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    suffixes = {p.suffix for p in written}
    assert {".xlsx", ".docx", ".json", ".log"} <= suffixes
    assert any(p.parent.name == "state" for p in written), "no state snapshot"
    assert any(p.name == "audit1.json" for p in written), "no audit output"
    assert any(p.name.startswith("tag_compliance_") for p in written), "no JSON"

    leaks = []
    # The credentials of the run itself (environment variables) too.
    checked = {**SECRETS, "env_secret_key": "fake-secret-for-moto-only"}
    for path in written:
        data = _blob(path)
        for where, secret in checked.items():
            if secret.encode() in data:
                leaks.append(f"{where} in {path.relative_to(tmp_path)}")
    for stream in (console.out, console.err, caplog.text):
        for where, secret in checked.items():
            if secret in stream:
                leaks.append(f"{where} in console/log records")
    assert not leaks, leaks

    # The planted resources were found, and names of variables are kept.
    report = next(p for p in (tmp_path / "out1").glob("*.xlsx"))
    data = _blob(report)
    assert b"fn-secret" in data and b"stack-secret" in data
    assert b"DB_PASSWORD" in data


def test_no_planted_secret_in_json_csv_output_or_resume_checkpoint(estate, tmp_path):
    """Library run: JSON and CSV output, snapshot, and the resume checkpoint.

    A second account that cannot sign in fails, so the finished account's
    checkpoint under ``state/partial/`` is kept and can be inspected.
    """
    from inventag.core.cloud_bom_generator import (
        AccountCredentials,
        CloudBOMGenerator,
        MultiAccountConfig,
    )

    out = tmp_path / "lib"
    config = MultiAccountConfig(
        accounts=[
            AccountCredentials(account_id="123456789012", regions=["us-east-1"]),
            AccountCredentials(
                account_id="999999999999",
                profile_name="inventag-test-profile-that-does-not-exist",
                regions=["us-east-1"],
            ),
        ],
        output_directory=str(out),
        enable_billing_validation=False,
        parallel_account_processing=False,
    )
    result = CloudBOMGenerator(config).generate_multi_account_bom(
        output_formats=["json", "csv"]
    )
    written = [p for p in out.rglob("*") if p.is_file()]
    suffixes = {p.suffix for p in written}
    assert {".json", ".csv"} <= suffixes, (result, written)
    checkpoints = [p for p in written if "partial" in p.parts]
    assert checkpoints, "no resume checkpoint was kept"
    leaks = [
        f"{where} in {path.relative_to(out)}"
        for path in written
        for where, secret in SECRETS.items()
        if secret.encode() in path.read_bytes()
    ]
    assert not leaks, leaks
    report = next(p for p in written if p.suffix == ".json" and "state" not in p.parts)
    assert b"trigger-secret" in report.read_bytes()
    assert b"--jdbc_url" in report.read_bytes()
