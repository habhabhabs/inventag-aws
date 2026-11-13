"""Offline (moto) proof for each feature the status page used to list as working,
and for the flags that were fixed.

Each test names the feature it covers. Features that other test files already
prove are listed in docs/security/tests.md; this file fills the gaps and runs
the real CLI where that is cheap.
"""

import json
import logging
import os
import sys
import zipfile
from pathlib import Path

import boto3
import pytest
import yaml
from docx import Document
from openpyxl import load_workbook

from inventag.cli import logging_setup
from inventag.security.read_only_guard import uninstall_global_guard
from tests.unit.test_cli_security import aws, run_cli as _run_cli  # noqa: F401


def run_cli(*args):
    """Run the CLI, then lift its read-only guard so the test can change moto."""
    try:
        return _run_cli(*args)
    finally:
        uninstall_global_guard()


@pytest.fixture
def estate(aws):  # noqa: F811
    """A small tagged estate in moto."""
    tags = [{"Key": "Owner", "Value": "alex"}, {"Key": "Env", "Value": "dev"}]
    ec2 = boto3.client("ec2", region_name="us-east-1")
    vpc = ec2.create_vpc(
        CidrBlock="10.0.0.0/16",
        TagSpecifications=[{"ResourceType": "vpc", "Tags": tags}],
    )["Vpc"]["VpcId"]
    ec2.create_security_group(
        GroupName="open",
        Description="open to the world",
        VpcId=vpc,
        TagSpecifications=[{"ResourceType": "security-group", "Tags": tags}],
    )
    sg = ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": ["open"]}]
    )["SecurityGroups"][0]["GroupId"]
    ec2.authorize_security_group_ingress(
        GroupId=sg,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            }
        ],
    )
    boto3.client("sqs", region_name="us-east-1").create_queue(
        QueueName="orders", tags={"Owner": "alex"}
    )
    boto3.client("dynamodb", region_name="us-east-1").create_table(
        TableName="tbl",
        KeySchema=[{"AttributeName": "k", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "k", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return vpc


def sheet_rows(path):
    wb = load_workbook(path)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb}


def only(path_glob):
    files = sorted(path_glob)
    assert len(files) == 1, files
    return files[0]


# --- Excel and Word reports, order ------------------------------------------


def test_excel_and_word_reports_are_written(estate, tmp_path):
    assert (
        run_cli("--account-regions", "us-east-1", "--create-excel", "--create-word")
        == 0
    )
    out = tmp_path / "bom_output"
    wb = load_workbook(only(out.glob("multi_account_bom_*.xlsx")))
    assert wb.sheetnames[0] == "Summary"
    doc = Document(str(only(out.glob("multi_account_bom_*.docx"))))
    assert any("Inventory" in p.text or "BOM" in p.text for p in doc.paragraphs)
    assert doc.tables


def test_sheets_and_rows_are_in_the_same_order_on_every_run(estate, tmp_path):
    runs = []
    for index in range(2):
        out = tmp_path / f"run{index}"
        assert (
            run_cli(
                "--account-regions",
                "us-east-1",
                "--create-excel",
                "--output-directory",
                str(out),
                "--disable-state-management",
            )
            == 0
        )
        runs.append(sheet_rows(only(out.glob("*.xlsx"))))
    first, second = runs
    assert list(first) == list(second)
    assert list(first)[0] == "Summary"
    services = list(first)[1:]
    assert services == sorted(services, key=str.lower)
    for name in services:
        header = first[name][0]
        key = header.index("arn") if "arn" in header else header.index("id")
        assert [r[key] for r in first[name][1:]] == [r[key] for r in second[name][1:]]
        rows = [
            (r[header.index("type")], r[header.index("id")]) for r in first[name][1:]
        ]
        assert rows == sorted(rows, key=lambda t: tuple(str(x).lower() for x in t))


# --- templates, tag columns, tag policy -------------------------------------


def test_tag_mappings_make_named_columns_with_a_default(estate, tmp_path):
    mappings = tmp_path / "tag_mappings.yaml"
    mappings.write_text(
        yaml.safe_dump(
            {
                "tag_mappings": [
                    {"tag": "Owner", "name": "Owner Tag", "default_value": "unowned"}
                ]
            }
        )
    )
    assert (
        run_cli(
            "--account-regions",
            "us-east-1",
            "--create-excel",
            "--tag-mappings",
            str(mappings),
            "--disable-state-management",
        )
        == 0
    )
    rows = sheet_rows(only((tmp_path / "bom_output").glob("*.xlsx")))
    column = rows["DYNAMODB"][0].index("Owner Tag")
    assert {r[column] for r in rows["DYNAMODB"][1:]} == {"unowned"}
    column = rows["VPC"][0].index("Owner Tag")
    assert "alex" in {r[column] for r in rows["VPC"][1:]}


def test_tag_policy_template_adds_sheet_word_section_and_json(estate, tmp_path):
    code = run_cli(
        "--account-regions",
        "us-east-1",
        "--create-excel",
        "--create-word",
        "--template",
        "finops-cost-report",
        "--disable-state-management",
    )
    assert code == 0
    out = tmp_path / "bom_output"
    assert "Tag Compliance" in load_workbook(only(out.glob("*.xlsx"))).sheetnames
    assert only(out.glob("tag_compliance_*.json"))
    doc = Document(str(only(out.glob("*.docx"))))
    assert any(
        "Tag Compliance" in p.text or "Tag compliance" in p.text for p in doc.paragraphs
    )


def test_ci_config_fails_the_run_on_tag_violations_with_exit_code_3(estate, tmp_path):
    assert (
        run_cli(
            "--account-regions",
            "us-east-1",
            "--template",
            "ci-pipeline",
            "--disable-state-management",
        )
        == 3
    )


# --- filters ---------------------------------------------------------------


def test_filters_apply_to_every_path(estate, tmp_path):
    assert (
        run_cli(
            "--account-regions",
            "us-east-1",
            "--account-services",
            "sqs",
            "--account-tags",
            '{"Owner": "alex"}',
            "--create-excel",
            "--disable-state-management",
        )
        == 0
    )
    rows = sheet_rows(only((tmp_path / "bom_output").glob("*.xlsx")))
    assert set(rows) == {"SQS", "Summary"}
    assert len(rows["SQS"]) == 2  # header and the one tagged queue


# --- network and security sheets, cost sheet --------------------------------


def test_network_and_security_sheets(estate, tmp_path):
    assert (
        run_cli(
            "--account-regions",
            "us-east-1",
            "--create-excel",
            "--enable-network-analysis",
            "--enable-security-analysis",
            "--disable-state-management",
        )
        == 0
    )
    names = load_workbook(only((tmp_path / "bom_output").glob("*.xlsx"))).sheetnames
    assert "Network Analysis" in names and "Security Analysis" in names


def test_risk_threshold_fails_the_run_on_risky_security_group_rules(estate, tmp_path):
    base = [
        "--account-regions",
        "us-east-1",
        "--create-excel",
        "--enable-security-analysis",
        "--disable-state-management",
    ]
    assert run_cli(*base, "--risk-threshold", "CRITICAL") == 4
    # Nothing in this estate is lower than the rule above, so LOW trips too;
    # an estate without such a rule passes (checked in the unit test below).
    assert run_cli(*base, "--risk-threshold", "LOW") == 4


def test_risk_threshold_passes_when_no_rule_reaches_it():
    from inventag.cli.main import risk_findings_at_or_above

    results = {
        "bom_generation": {
            "security_risk_findings": [
                {"group_id": "sg-1", "rule": "ingress tcp 22", "risk_level": "medium"}
            ]
        }
    }
    assert risk_findings_at_or_above(results, "HIGH") == []
    assert len(risk_findings_at_or_above(results, "MEDIUM")) == 1


def test_cost_analysis_adds_a_cost_sheet(estate, tmp_path):
    assert (
        run_cli(
            "--account-regions",
            "us-east-1",
            "--create-excel",
            "--enable-cost-analysis",
            "--no-billing-validation",
            "--disable-state-management",
        )
        == 0
    )
    rows = sheet_rows(only((tmp_path / "bom_output").glob("*.xlsx")))
    assert "Cost Analysis" in rows
    text = " ".join(str(c) for r in rows["Cost Analysis"] for c in r if c)
    assert "Estimates only" in text and "Summary" in text


# --- changelog between runs; snapshots; no unused folder ---------------------


def test_second_run_writes_a_changelog_and_no_empty_changelogs_folder(estate, tmp_path):
    args = ["--account-regions", "us-east-1", "--create-excel"]
    assert run_cli(*args) == 0
    boto3.client("sqs", region_name="us-east-1").create_queue(QueueName="added")
    assert run_cli(*args) == 0
    out = tmp_path / "bom_output"
    changelog = only(out.glob("changelog_*.md"))
    assert "added" in changelog.read_text()
    assert len(list((out / "state").glob("*.json"))) >= 2
    assert not (out / "changelogs").exists()


# --- credentials and options -------------------------------------------------


def test_credential_timeout_is_applied_to_the_sts_client(estate, monkeypatch):
    from inventag.core import cloud_bom_generator as gen

    seen = []
    real = boto3.Session.client

    def spy(self, service, *a, **kw):
        if service == "sts" and kw.get("config") is not None:
            seen.append((kw["config"].connect_timeout, kw["config"].read_timeout))
        return real(self, service, *a, **kw)

    monkeypatch.setattr(boto3.Session, "client", spy)
    assert (
        run_cli(
            "--account-regions",
            "us-east-1",
            "--credential-timeout",
            "7",
            "--create-excel",
            "--disable-state-management",
        )
        == 0
    )
    # The sign-in and identity checks (the first STS clients) use the
    # timeout. Discovery later makes its own STS client with the shared
    # retry settings; that one is not a credential check.
    assert seen and seen[0] == (7, 7)
    assert gen.BotoConfig is not None


def test_accounts_prompt_builds_the_accounts_from_typed_answers(
    estate, monkeypatch, tmp_path
):
    answers = iter(
        [
            "123456789012",  # account id
            "Prompted",  # name
            "1",  # credential method: profile
            "",  # profile name (empty: default chain)
            "us-east-1",  # regions
            "",  # services
            "",  # finish
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert (
        run_cli(
            "--accounts-prompt",
            "--create-excel",
            "--disable-state-management",
        )
        == 0
    )
    rows = sheet_rows(only((tmp_path / "bom_output").glob("*.xlsx")))
    assert "SQS" in rows


def test_disable_account_logging_removes_the_account_prefix(capsys):
    from inventag.core.log_context import account_log_context

    for disabled, expected in ((False, True), (True, False)):
        logger = logging_setup.setup_logging(
            verbose=True, account_specific=not disabled
        )
        with account_log_context("123456789012", "Prod"):
            logger.info("scanning")
        out = capsys.readouterr().out
        assert ("[Prod] " in out) is expected
        assert "scanning" in out


# --- failed accounts, per-account reports ------------------------------------


@pytest.fixture
def two_accounts(estate, tmp_path):
    """One account that scans, one whose AWS profile does not exist."""
    path = tmp_path / "accounts.json"
    path.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "123456789012",
                        "account_name": "Works",
                        "regions": ["us-east-1"],
                    },
                    {
                        "account_id": "999999999999",
                        "account_name": "Broken",
                        "profile_name": "no-such-profile",
                        "regions": ["us-east-1"],
                    },
                ]
            }
        )
    )
    return path


def test_report_and_run_summary_name_the_account_that_failed(
    two_accounts, tmp_path, capsys
):
    code = run_cli(
        "--accounts-file",
        str(two_accounts),
        "--create-excel",
        "--create-word",
        "--disable-state-management",
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "1 account(s) were not scanned" in out
    assert "999999999999 (Broken)" in out
    rows = sheet_rows(only((tmp_path / "bom_output").glob("*.xlsx")))
    summary = " ".join(str(c) for r in rows["Summary"] for c in r if c)
    assert "Run notes" in summary and "999999999999" in summary
    doc = Document(str(only((tmp_path / "bom_output").glob("*.docx"))))
    assert any("999999999999" in p.text for p in doc.paragraphs)


def test_per_account_reports_write_one_workbook_per_account(estate, tmp_path):
    iam = boto3.client("iam")
    iam.create_role(RoleName="Scan", AssumeRolePolicyDocument="{}")
    accounts = tmp_path / "accounts.json"
    accounts.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "123456789012",
                        "account_name": "One",
                        "regions": ["us-east-1"],
                    }
                ]
            }
        )
    )
    assert (
        run_cli(
            "--accounts-file",
            str(accounts),
            "--create-excel",
            "--per-account-reports",
            "--disable-state-management",
        )
        == 0
    )
    out = tmp_path / "bom_output"
    assert not list(out.glob("multi_account_bom_*.xlsx"))
    report = only(out.glob("123456789012_bom_*.xlsx"))
    assert "SQS" in load_workbook(report).sheetnames


def test_report_scopes_split_resources_by_account(tmp_path):
    from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
    from inventag.reporting.bom_processor import BOMData

    generator = CloudBOMGenerator(
        MultiAccountConfig(
            output_directory=str(tmp_path / "o"), generate_per_account_reports=True
        )
    )
    data = BOMData(
        resources=[
            {"service": "S3", "source_account_id": "111111111111", "id": "a"},
            {"service": "S3", "source_account_id": "222222222222", "id": "b"},
            {"service": "S3", "source_account_id": "111111111111", "id": "c"},
        ]
    )
    scopes = generator._report_scopes(data)
    assert [(p, label, len(d.resources)) for p, label, d in scopes] == [
        ("111111111111_bom", "111111111111", 2),
        ("222222222222_bom", "222222222222", 1),
    ]


# --- validate-config-only, bom-config ---------------------------------------


def test_validate_config_only_makes_no_aws_call(tmp_path, monkeypatch, capsys):
    import botocore.client

    def forbidden(*a, **k):
        raise AssertionError("an AWS call was made")

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", forbidden)
    mappings = tmp_path / "tm.yaml"
    mappings.write_text(
        yaml.safe_dump({"tag_mappings": [{"tag": "Owner", "name": "Owner"}]})
    )
    code = run_cli(
        "--verbose", "--validate-config-only", "--tag-mappings", str(mappings)
    )
    assert code == 0
    assert "No AWS call was made" in capsys.readouterr().out


def test_bom_config_warns_about_ignored_keys(estate, tmp_path, capsys):
    config = tmp_path / "bom.yaml"
    config.write_text(yaml.safe_dump({"max_worker_threads": 2, "not_a_real_key": 1}))
    assert (
        run_cli(
            "--account-regions",
            "us-east-1",
            "--create-excel",
            "--bom-config",
            str(config),
            "--disable-state-management",
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "ignored unknown key(s) not_a_real_key" in out


# --- permission denied is said once -----------------------------------------


def test_permission_denied_is_logged_once_per_service(estate, caplog):
    from botocore.exceptions import ClientError

    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    disc = ComprehensiveAWSDiscovery(
        regions=["us-east-1", "us-west-2"], enable_billing_validation=False
    )

    class Denied:
        def get_paginator(self, name):
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "no"}}, name
            )

        def list_functions(self, **kw):
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "no"}}, "ListFunctions"
            )

    with caplog.at_level(logging.WARNING):
        for region in ("us-east-1", "us-west-2"):
            disc._execute_discovery_operation(
                Denied(), "lambda", region, ("list_functions", "Functions", "Function")
            )
    warnings = [r for r in caplog.records if "No permission for lambda" in r.message]
    assert len(warnings) == 1


def test_cost_explorer_denied_is_a_warning(estate, caplog):
    from botocore.exceptions import ClientError

    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    disc = ComprehensiveAWSDiscovery(
        regions=["us-east-1"], enable_billing_validation=True
    )

    class Session:
        def client(self, *a, **k):
            class CE:
                def get_cost_and_usage(self, **kw):
                    raise ClientError(
                        {"Error": {"Code": "AccessDeniedException", "Message": "x"}},
                        "GetCostAndUsage",
                    )

            return CE()

    disc.session = Session()
    with caplog.at_level(logging.WARNING):
        disc._discover_billing_services()
    assert any(
        "Cost Explorer data is not available" in r.message for r in caplog.records
    )
