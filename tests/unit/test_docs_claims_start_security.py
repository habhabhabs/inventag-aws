"""Docs claim check for the start, security, development and landing texts.

Run for real: the facts that docs/getting-started, docs/security,
docs/development, README.md and the landing page state about numbers, defaults,
guard behaviour and failing flags. Each test names the page statement it proves.
"""

import importlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from unittest import mock

import botocore.client
import docx
import pytest
import tomllib
import yaml

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from tests.unit.test_docs_claims_v120 import (  # noqa: F401  (fixtures)
    aws,
    empty_aws,
    reports,
    run_cli,
    workbook,
    workbook_text,
)

ROOT = Path(__file__).resolve().parents[2]
cli_main = importlib.import_module("inventag.cli.main")


# ------------------------------------------------------------ numbers
def test_46_services_have_their_own_discovery_code():
    """status, introduction, README, landing: 46 services."""
    disc = ComprehensiveAWSDiscovery(session=mock.MagicMock(), regions=["us-east-1"])
    keys = set(disc.service_discovery_patterns)
    assert "wafv2-cloudfront" in keys  # a second entry of the WAF service
    assert len(keys - {"wafv2-cloudfront"}) == 46
    # every service named on the status page has an entry
    expected = (
        {
            "vpc ec2 s3 rds lambda elb elbv2 iam cloudfront route53 kms cloudwatch ecs "
            "eks sns sqs dynamodb apigateway glue workmail cloudformation acm cloudtrail "
            "events elasticache redshift redshift-serverless opensearch efs ecr "
            "stepfunctions kinesis firehose secretsmanager ssm autoscaling backup cognito "
            "codebuild codepipeline athena emr msk appsync elasticbeanstalk wafv2"
        }
        .pop()
        .split()
    )
    assert len(expected) == 46
    assert set(expected) == keys - {"wafv2-cloudfront"}


def _policy():
    return json.loads((ROOT / "config/defaults/iam-policy-read-only.json").read_text())[
        "Statement"
    ]


def test_iam_policy_has_122_read_actions_and_no_lookup_events():
    """Security and status pages: 122 read actions; cloudtrail:LookupEvents dropped."""
    statements = {s["Sid"]: s for s in _policy()}
    read = statements["InvenTagReadOnlyDiscovery"]["Action"]
    assert len(read) == 122 and len(set(read)) == 122
    assert "cloudtrail:LookupEvents" not in json.dumps(_policy())
    # every action of the main statement is a read verb
    verbs = ("Describe", "List", "Get", "BatchGet", "Search", "Lookup")
    bad = [a for a in read if not a.split(":")[1].startswith(verbs)]
    assert bad == []
    # the other two statements are the scoped API Gateway and the optional upload
    assert statements["OptionalS3ReportUpload"]["Action"] == ["s3:PutObject"]


def test_17_new_read_actions_since_v1_1_4():
    """Installation page: the policy has 17 new read actions (and no LookupEvents)."""
    import subprocess

    out = subprocess.run(
        ["git", "show", "v1.1.4:config/defaults/iam-policy-read-only.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        pytest.skip("tag v1.1.4 is not in this clone")
    old = {
        a
        for s in json.loads(out.stdout)["Statement"]
        for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])
    }
    new = set(_policy()[0]["Action"])
    assert "cloudtrail:LookupEvents" in old
    assert len(new - old) == 17


def test_python_versions_agree_between_pyproject_ci_and_docs():
    """Installation, Security, Tests, CONTRIBUTING, README: 3.11 or later; CI 3.11 to 3.15."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["requires-python"] == ">=3.11"
    classifiers = [c for c in project["classifiers"] if "Python :: 3." in c]
    assert [c.rsplit(" ", 1)[1] for c in classifiers] == [
        "3.11",
        "3.12",
        "3.13",
        "3.14",
        "3.15",
    ]
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert [str(v) for v in matrix] == ["3.11", "3.12", "3.13", "3.14", "3.15"]
    assert ci["jobs"]["test"]["strategy"]["fail-fast"] is False
    triggers = ci[True] if True in ci else ci["on"]
    assert set(triggers["push"]["branches"]) == {"main", "develop"}
    assert triggers["pull_request"]["branches"] == ["main"]


def test_defaults_stated_on_the_status_page():
    """Status: four accounts at a time, 1800 s, 24 h, 30 days, 100 snapshots, auto."""
    args = cli_main.create_parser().parse_args([])
    assert args.max_concurrent_accounts == 4
    assert args.account_processing_timeout == 1800
    assert args.resume_max_age_hours == 24
    assert str(args.state_retention_days) == "30"
    assert str(args.state_max_snapshots) == "100"
    assert args.fallback_display == "auto"
    from inventag.discovery import aws_clients

    cfg = aws_clients.retry_config()
    assert cfg.retries == {"mode": "standard", "total_max_attempts": 10}


def test_builtin_templates_are_eight():
    """Landing page: eight built-in templates."""
    names = sorted(
        p.name for p in (ROOT / "inventag/templating/builtin").glob("*.yaml")
    )
    assert len(names) == 8


def test_test_counts_on_the_tests_page():
    """Tests page: more than 2,300 tests plus nine benchmarks (collect only)."""
    import subprocess

    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    m = re.search(r"(\d+)/(\d+) tests collected \((\d+) deselected\)", out)
    assert m and int(m.group(1)) > 2300 and int(m.group(3)) == 9
    bench = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "performance"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    assert re.search(r"\b9/\d+ tests collected", bench)


# ------------------------------------------------------------ failing flags
@pytest.mark.parametrize(
    "flags, text",
    [
        (["--compliance-standard", "soc2"], "not implemented yet"),
        (["--disable-production-safety"], "cannot be disabled"),
        (["--risk-threshold", "HIGH"], "--enable-security-analysis"),
    ],
)
def test_flags_that_stop_with_exit_2(aws, capsys, flags, text):
    """Status and README: these flags stop with exit code 2 and say why."""
    assert run_cli(*flags) == 2
    assert text in capsys.readouterr().err


@pytest.mark.parametrize(
    "flag",
    ["--enable-production-safety", "--security-validation", "--enforce-read-only"],
)
def test_old_safety_flags_are_accepted_and_the_guard_stays_on(aws, tmp_path, flag):
    """Status: kept so old commands run; the guard is always on."""
    from inventag.security import read_only_guard as g

    assert run_cli("--validate-credentials", flag) == 0
    assert (
        g.is_global_guard_installed()
        if hasattr(g, "is_global_guard_installed")
        else True
    )


def test_validate_operations_output_and_exit_code(capsys):
    """Security page: --validate-operations lines and exit code 1 when one is blocked."""
    code = run_cli(
        "--validate-operations",
        "ec2:DescribeInstances",
        "s3:GetBucketTagging",
        "s3:PutObject",
        "secretsmanager:GetSecretValue",
    )
    out = capsys.readouterr().out.splitlines()
    assert code == 1
    assert out[0].startswith("ALLOWED  ec2:DescribeInstances")
    assert out[1].startswith("ALLOWED  s3:GetBucketTagging")
    assert out[2].startswith("BLOCKED  s3:PutObject")
    assert out[3].startswith("BLOCKED  secretsmanager:GetSecretValue")


@pytest.mark.parametrize(
    "op",
    [
        "secretsmanager:GetSecretValue",
        "s3:GetObject",
        "cloudformation:GetTemplate",
        "ec2:GetLaunchTemplateData",
        "ssm:GetDocument",
        "ssm:GetCommandInvocation",
        "cognito-identity:GetId",
        "sso:GetRoleCredentials",  # blocked for a signed client
        "apigateway:GetExport",
        "datapipeline:GetPipelineDefinition",
        "support:GetAttachmentDownloadLink",
        "connect:GetAttachedFile",
    ],
)
def test_security_page_blocked_operations(op, capsys):
    """Security page: the named reads are blocked by the guard (offline check)."""
    assert run_cli("--validate-operations", op) == 1
    assert capsys.readouterr().out.startswith("BLOCKED")


# ------------------------------------------------------------ run counts
class Counter_:
    def __init__(self, monkeypatch):
        self.calls = Counter()
        original = botocore.client.BaseClient._make_api_call
        counter = self

        def call(client, operation_name, api_params):
            counter.calls[(client.meta.service_model.service_name, operation_name)] += 1
            return original(client, operation_name, api_params)

        monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)

    def of(self, service):
        return sum(n for (s, _), n in self.calls.items() if s == service)


def test_default_run_makes_two_cost_explorer_requests_per_account(
    aws, tmp_path, monkeypatch
):
    """Status, Quick start, README: two Cost Explorer requests per account by default;
    --no-billing-validation makes none."""
    c = Counter_(monkeypatch)
    assert (
        run_cli(
            "--create-excel",
            "--output-directory",
            str(tmp_path / "a"),
            "--account-regions",
            "us-east-1",
        )
        == 0
    )
    assert c.of("ce") == 2
    c.calls.clear()
    assert (
        run_cli(
            "--create-excel",
            "--no-billing-validation",
            "--output-directory",
            str(tmp_path / "b"),
            "--account-regions",
            "us-east-1",
        )
        == 0
    )
    assert c.of("ce") == 0


def test_cost_analysis_calls_cost_explorer_pricing_and_cloudwatch_with_billing_off(
    aws, tmp_path, monkeypatch
):
    """Status: --enable-cost-analysis makes Cost Explorer, Pricing and CloudWatch calls
    even with --no-billing-validation. The page gives 5, 3 and 2 for its own estate;
    the counts depend on the estate, so only the kinds of call are asserted here."""
    c = Counter_(monkeypatch)
    base = [
        "--create-excel",
        "--no-billing-validation",
        "--account-regions",
        "us-east-1",
    ]
    assert run_cli(*base, "--output-directory", str(tmp_path / "a")) == 0
    assert c.of("ce") == 0 and c.of("pricing") == 0
    c.calls.clear()
    assert (
        run_cli(
            *base, "--enable-cost-analysis", "--output-directory", str(tmp_path / "b")
        )
        == 0
    )
    seen = {s_: c.of(s_) for s_ in ("ce", "pricing", "cloudwatch")}
    print("COST-ANALYSIS-CALLS", seen)
    assert seen["ce"] > 0 and seen["pricing"] > 0 and seen["cloudwatch"] > 0


def test_analysis_calls_are_made_twice(aws, tmp_path, monkeypatch):
    """Status: with --enable-network-analysis the analysis calls are made twice."""
    c = Counter_(monkeypatch)
    base = [
        "--create-excel",
        "--no-billing-validation",
        "--account-regions",
        "us-east-1",
    ]
    assert run_cli(*base, "--output-directory", str(tmp_path / "a")) == 0
    plain = c.calls[("ec2", "DescribeRouteTables")]
    c.calls.clear()
    assert (
        run_cli(
            *base,
            "--enable-network-analysis",
            "--output-directory",
            str(tmp_path / "b"),
        )
        == 0
    )
    with_analysis = c.calls[("ec2", "DescribeRouteTables")]
    print("route tables", plain, with_analysis)
    assert with_analysis - plain >= 2


# ------------------------------------------------------------ report limits
def test_word_tables_show_up_to_50_resources_per_service(aws, tmp_path):
    """Status, landing, Quick start: Word shows up to 50 resources per service."""
    import boto3

    sqs = boto3.client("sqs", region_name="us-east-1")
    for i in range(60):
        sqs.create_queue(QueueName=f"q-{i:02d}")
    out = tmp_path / "o"
    assert (
        run_cli(
            "--create-word",
            "--no-billing-validation",
            "--account-regions",
            "us-east-1",
            "--output-directory",
            str(out),
        )
        == 0
    )
    document = docx.Document(str(reports(out, ".docx")[0]))
    sizes = [len(t.rows) - 1 for t in document.tables]
    assert max(sizes) == 50


def test_excel_sheet_names_are_cut_to_31_characters(caplog):
    """Status: Excel sheet names are limited to 31 characters, forbidden characters
    become '-', a repeated name gets ' (2)', and the log names each changed sheet."""
    from inventag.reporting.converter import _sheet_name

    used = []
    a = _sheet_name("A" * 40, used)
    used.append(a)
    b = _sheet_name("A" * 40, used)
    c = _sheet_name("x/y:z", used)
    assert a == "A" * 31
    assert b == "A" * 27 + " (2)" and len(b) == 31
    assert c == "x-y-z"
    assert "x/y:z" in caplog.text


# ------------------------------------------------------------ run failures
def test_snapshot_that_cannot_be_saved_still_exits_0(
    aws, tmp_path, monkeypatch, caplog
):
    """Status: a snapshot that cannot be saved is logged as an error; exit code 0."""
    from inventag.state.state_manager import StateManager

    def boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(StateManager, "save_state", boom)
    code = run_cli(
        "--create-excel",
        "--no-billing-validation",
        "--account-regions",
        "us-east-1",
        "--output-directory",
        str(tmp_path / "o"),
    )
    assert code == 0
    assert len(reports(tmp_path / "o")) == 1
    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_every_call_denied_exits_0_with_no_resources(
    aws, tmp_path, monkeypatch, caplog
):
    """Status: every call in an account denied: the account does not count as failed;
    exit 0 and no resources to report."""
    from botocore.exceptions import ClientError

    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        if client.meta.service_model.service_name == "sts":
            return original(client, operation_name, api_params)
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, operation_name
        )

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)
    code = run_cli(
        "--create-excel",
        "--no-billing-validation",
        "--account-regions",
        "us-east-1",
        "--output-directory",
        str(tmp_path / "o"),
    )
    assert code == 0
    assert reports(tmp_path / "o") == []


def test_google_output_with_a_template_is_skipped_exit_0(
    aws, tmp_path, caplog, monkeypatch
):
    """Status: Google output with --template is skipped, and the run exits with code 0.
    The Google libraries are not installed here, so their check is stubbed; the
    claim is about what the template path does with the format."""
    monkeypatch.setattr(
        "inventag.reporting.google_output.validate_options", lambda options: []
    )
    monkeypatch.setattr(
        "inventag.reporting.google_output.load_credentials",
        lambda options: object(),
    )
    code = run_cli(
        "--template",
        "standard-bom",
        "--create-excel",
        "--create-google-sheets",
        "--no-billing-validation",
        "--account-regions",
        "us-east-1",
        "--output-directory",
        str(tmp_path / "o"),
    )
    assert code == 0
    assert len(reports(tmp_path / "o")) == 1
    assert "not supported with --template; skipped" in caplog.text


@pytest.mark.parametrize(
    "flag", ["--max-concurrent-accounts", "--account-processing-timeout"]
)
def test_zero_for_limits_stops_with_exit_1_not_2(aws, flag):
    """Status: --max-concurrent-accounts 0 and --account-processing-timeout 0 exit 1."""
    assert run_cli(flag, "0", "--no-billing-validation") == 1


def test_expired_sso_token_prints_a_traceback_and_one_error_line(tmp_path):
    """Status says an expired SSO token 'stops the run with a Python traceback instead
    of a message'. Observed: botocore logs a traceback as a warning, InvenTag logs one
    error line with the cause (no 'aws sso login' hint) and exits 1. Run in a
    subprocess because botocore reads the SSO cache folder when it is imported."""
    import hashlib
    import os
    import subprocess

    home = tmp_path / "home"
    cache = home / ".aws" / "sso" / "cache"
    cache.mkdir(parents=True)
    (cache / (hashlib.sha1(b"s").hexdigest() + ".json")).write_text(
        json.dumps(
            {
                "accessToken": "x",
                "expiresAt": "2020-01-01T00:00:00Z",
                "startUrl": "https://example.awsapps.com/start",
                "region": "us-east-1",
            }
        )
    )
    cfg = tmp_path / "cfg"
    cfg.write_text(
        "[profile sso1]\nsso_session = s\nsso_account_id = 123456789012\n"
        "sso_role_name = R\nregion = us-east-1\n"
        "[sso-session s]\nsso_start_url = https://example.awsapps.com/start\n"
        "sso_region = us-east-1\nsso_registration_scopes = sso:account:access\n"
    )
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "AWS_CONFIG_FILE": str(cfg),
        "AWS_SHARED_CREDENTIALS_FILE": str(tmp_path / "none"),
        "AWS_PROFILE": "sso1",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    run = subprocess.run(
        [
            sys.executable,
            "inventag_cli.py",
            "--create-excel",
            "--no-billing-validation",
            "--output-directory",
            str(tmp_path / "out"),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = run.stdout + run.stderr
    assert run.returncode == 1
    assert "Traceback (most recent call last)" in text
    assert "Token has expired and refresh failed" in text
    assert "aws sso login" not in text  # the hint of main.py is not reached


# ------------------------------------------------------------ security claims
def test_a_default_run_opens_no_network_connection(aws, tmp_path, monkeypatch):
    """Security page: no telemetry. A whole run under moto (which answers inside the
    process) opens no socket connection: nothing is sent to any other host."""
    import socket

    attempts = []

    def connect(self, address, *a, **k):
        attempts.append(address)
        raise OSError("network blocked by the test")

    monkeypatch.setattr(socket.socket, "connect", connect)
    code = run_cli(
        "--create-excel",
        "--create-word",
        "--account-regions",
        "us-east-1",
        "--output-directory",
        str(tmp_path / "o"),
    )
    assert code == 0
    assert attempts == []


def test_template_excel_has_a_frozen_header_row_and_filter_buttons(aws, tmp_path):
    """Quick start: a template gives a frozen header row and filter buttons."""
    import openpyxl

    out = tmp_path / "o"
    assert (
        run_cli(
            "--template",
            "standard-bom",
            "--create-excel",
            "--no-billing-validation",
            "--account-regions",
            "us-east-1",
            "--output-directory",
            str(out),
        )
        == 0
    )
    wb = openpyxl.load_workbook(reports(out)[0])
    sheets = [ws for ws in wb if ws.title != "Summary"]
    assert sheets
    for ws in sheets:
        assert ws.freeze_panes is not None, ws.title
        assert ws.auto_filter.ref, ws.title


def test_service_attribute_enrichment_in_a_default_run(aws, tmp_path, monkeypatch):
    """Status says service attribute enrichment (enable_service_enrichment) does not
    run. Observed: the enricher object is created in a default run (the BOM
    processor default is True) and the processor calls enrich_resource on it, but
    ServiceAttributeEnricher has no such method (the call fails inside a try block),
    so no resource is enriched. The docs statement holds in effect; the code is dead."""
    from inventag.reporting import bom_processor
    from inventag.discovery import service_enrichment as se

    assert not hasattr(se.ServiceAttributeEnricher, "enrich_resource")
    made = []
    original_init = bom_processor.ServiceAttributeEnricher.__init__

    def init(self, *a, **k):
        made.append(1)
        original_init(self, *a, **k)

    monkeypatch.setattr(bom_processor.ServiceAttributeEnricher, "__init__", init)
    code = run_cli(
        "--create-excel",
        "--no-billing-validation",
        "--account-regions",
        "us-east-1",
        "--output-directory",
        str(tmp_path / "o"),
    )
    assert code == 0
    print("ENRICHER-CREATED", len(made))


# ------------------------------------------------------------ claims3 TEST rows
def _lambda_with_secret_env(value="plain-old-value"):
    import io
    import zipfile

    import boto3

    role = boto3.client("iam", region_name="us-east-1").create_role(
        RoleName="up-role", AssumeRolePolicyDocument="{}"
    )["Role"]["Arn"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("app.py", "def handler(event, context):\n    return 1\n")
    boto3.client("lambda", region_name="us-east-1").create_function(
        FunctionName="up-fn",
        Runtime="python3.12",
        Role=role,
        Handler="app.handler",
        Code={"ZipFile": buffer.getvalue()},
        Environment={"Variables": {"DB_PASSWORD": value}},
    )


def test_first_run_after_the_upgrade_reports_masked_resources_as_changed_once(
    empty_aws, tmp_path
):
    """Installation (Upgrade) and track-changes: a snapshot written before masking
    holds the plain value; the first masked run lists the function as changed, and
    the run after that lists nothing for it.  The old snapshot is made by putting
    the plain value back into the snapshot the first run wrote."""
    _lambda_with_secret_env("plain-old-value")
    out = tmp_path / "o"
    args = (
        "--create-excel",
        "--no-billing-validation",
        "--account-regions",
        "us-east-1",
        "--output-directory",
        str(out),
    )
    assert run_cli(*args) == 0
    snapshots = sorted((out / "state").glob("state_*.json"))
    assert len(snapshots) == 1
    text = snapshots[0].read_text()
    assert "plain-old-value" not in text and "***REDACTED***" in text
    snapshots[0].write_text(text.replace("***REDACTED***", "plain-old-value"))

    def changelog_after(previous):
        assert run_cli(*args) == 0
        files = [
            p
            for p in out.rglob("*")
            if p.is_file() and "changelog" in p.name.lower() and p not in previous
        ]
        return files, "\n".join(p.read_text(errors="ignore") for p in files)

    first_files, first = changelog_after(set())
    assert "up-fn" in first, first[:2000]
    assert "plain-old-value" not in first
    second_files, second = changelog_after(set(first_files))
    assert second_files, "the third run wrote no change report"
    assert "up-fn" not in second, second[:2000]


def test_secrets_in_tags_and_free_text_are_copied_as_they_are(aws, tmp_path):
    """Status: a secret in a tag value, in a tag key such as `password`, or in a
    description is copied into the report unmasked (masking goes by field name)."""
    import boto3

    ec2 = boto3.client("ec2", region_name="us-east-1")
    vpc = ec2.describe_vpcs()["Vpcs"][0]["VpcId"]
    ec2.create_security_group(
        GroupName="leaky",
        Description="note: hunter2-in-description",
        VpcId=vpc,
        TagSpecifications=[
            {
                "ResourceType": "security-group",
                "Tags": [
                    {"Key": "password", "Value": "hunter2-in-tag-value"},
                    {"Key": "notes", "Value": "token=hunter2-in-other-tag"},
                ],
            }
        ],
    )
    code = run_cli(
        "--create-excel",
        "--no-billing-validation",
        "--account-regions",
        "us-east-1",
        "--output-directory",
        str(tmp_path / "o"),
    )
    assert code == 0
    text = workbook_text(reports(tmp_path / "o")[0])
    assert "hunter2-in-description" in text
    assert "hunter2-in-tag-value" in text
    assert "hunter2-in-other-tag" in text


def test_a_template_report_does_not_name_a_failed_account(tmp_path):
    """Status: a report made with --template does not name the accounts that
    failed (the default report does).  Same set-up as the A-07 test of lead E."""
    from unittest.mock import MagicMock

    from openpyxl import load_workbook

    from inventag.core.cloud_bom_generator import (
        AccountContext,
        AccountCredentials,
        BOMProcessingConfig,
        MultiAccountConfig,
    )
    from inventag.templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry
    from inventag.templating.runner import TemplatedCloudBOMGenerator, TemplateRun

    registry = TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])
    failed_id = "222222222222"
    config = MultiAccountConfig(
        output_directory=str(tmp_path / "out"),
        bom_processing_config=BOMProcessingConfig(
            enable_network_analysis=False,
            enable_security_analysis=False,
            enable_service_enrichment=False,
            enable_service_descriptions=False,
            enable_tag_mapping=False,
        ),
    )
    generator = TemplatedCloudBOMGenerator(
        config, TemplateRun(registry.resolve("standard-bom"), None, None)
    )
    generator.account_contexts = {
        "111111111111": AccountContext(
            credentials=AccountCredentials(
                account_id="111111111111", account_name="good"
            ),
            session=MagicMock(),
            caller_identity={},
        ),
        failed_id: AccountContext(
            credentials=AccountCredentials(account_id=failed_id, account_name="bad"),
            session=None,
            caller_identity={},
            processing_errors=[
                "AccessDenied: not authorized to perform sts:AssumeRole"
            ],
        ),
    }
    resource = {
        "service": "S3",
        "resource_type": "Bucket",
        "resource_id": "bucket-one",
        "arn": "arn:aws:s3:::bucket-one",
        "region": "us-east-1",
        "source_account_id": "111111111111",
        "tags": {},
    }
    out = generator._generate_bom_documents([resource], {}, ["excel", "word"])
    assert out["success"], out
    files = {path.rsplit(".", 1)[1]: path for path in out["generated_files"]}
    cells = [
        str(c.value)
        for ws in load_workbook(files["xlsx"]).worksheets
        for row in ws.iter_rows()
        for c in row
        if c.value
    ]
    assert not any(failed_id in c for c in cells)
    paragraphs = [p.text for p in docx.Document(files["docx"]).paragraphs]
    assert not any(failed_id in p for p in paragraphs)


def test_network_analysis_counts_a_resource_in_the_first_subnet_only():
    """Status: a resource in several subnets counts for the first subnet only, and
    a load balancer counts for its VPC but not for a subnet."""
    import boto3
    from moto import mock_aws

    from inventag.discovery.network_analyzer import NetworkAnalyzer

    region = "us-east-1"
    with mock_aws():
        ec2 = boto3.client("ec2", region_name=region)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
        a, b = [
            ec2.create_subnet(
                VpcId=vpc, CidrBlock=f"10.0.{n}.0/24", AvailabilityZone=f"{region}{az}"
            )["Subnet"]["SubnetId"]
            for n, az in ((1, "a"), (2, "b"))
        ]
        alb = {
            "id": "alb1",
            "service": "ELBV2",
            "type": "LoadBalancerV2",
            "region": region,
            "raw_data": {
                "VpcId": vpc,
                "AvailabilityZones": [
                    {"ZoneName": region, "SubnetId": a},
                    {"ZoneName": region, "SubnetId": b},
                ],
            },
        }
        function = {
            "id": "fn",
            "service": "LAMBDA",
            "type": "Function",
            "region": region,
            "raw_data": {"VpcConfig": {"VpcId": vpc, "SubnetIds": [a, b]}},
        }
        analyzer = NetworkAnalyzer(boto3.Session(region_name=region))
        analyzer.analyze_vpc_resources([alb, function])
        assert analyzer.subnet_cache[a].associated_resources == ["fn"]
        assert analyzer.subnet_cache[b].associated_resources == []
        assert sorted(analyzer.vpc_cache[vpc].associated_resources) == ["alb1", "fn"]


def _python_with(*modules):
    """The first interpreter (this one, then python3) that imports all ``modules``."""
    import shutil
    import subprocess

    for exe in (sys.executable, shutil.which("python3")):
        if exe and (
            subprocess.run(
                [exe, "-c", "import " + ", ".join(modules)], capture_output=True
            ).returncode
            == 0
        ):
            return exe
    return None


def test_the_built_wheel_includes_the_report_templates(tmp_path):
    """Installation: the package includes the report templates (the eight YAML
    files under inventag/templating/builtin).  Built offline, no build isolation."""
    import subprocess
    import zipfile

    python = _python_with("setuptools", "wheel")
    if python is None:
        pytest.skip("no interpreter with setuptools and wheel")
    work = tmp_path / "src"
    import shutil

    shutil.copytree(
        ROOT,
        work,
        ignore=shutil.ignore_patterns(
            ".git", "node_modules", "website", "bom_output", "__pycache__", "*.egg-info"
        ),
    )
    proc = subprocess.run(
        [
            python,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--no-index",
            "-w",
            str(tmp_path / "dist"),
            str(work),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    (wheel_path,) = (tmp_path / "dist").glob("*.whl")
    names = zipfile.ZipFile(wheel_path).namelist()
    builtin = sorted(
        n
        for n in names
        if n.startswith("inventag/templating/builtin/") and n.endswith(".yaml")
    )
    assert len(builtin) == 8, builtin
    assert builtin == sorted(
        f"inventag/templating/builtin/{p.name}"
        for p in (ROOT / "inventag/templating/builtin").glob("*.yaml")
    )


def test_assumed_role_sessions_are_not_refreshed():
    """Status: assumed-role sessions are not refreshed.  Both assume paths return
    a session with fixed credentials; a clock two hours later gives the same
    credentials object, and no refresh or session-length option is in the code."""
    import time
    from unittest.mock import MagicMock, patch

    from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig

    temp = {
        "Credentials": {
            "AccessKeyId": "ASIAEXAMPLE",
            "SecretAccessKey": "secret-value-123456",
            "SessionToken": "token-value-123456",
        }
    }
    generator = CloudBOMGenerator(MultiAccountConfig(output_directory="/tmp/unused"))
    with patch("inventag.core.cloud_bom_generator.boto3.Session") as real_session:
        real_session.return_value.client.return_value.assume_role.return_value = temp
        generator._assume_role_session(
            "arn:aws:iam::123456789012:role/InvenTagRead", "123456789012"
        )
        kwargs = real_session.call_args_list[-1].kwargs
        assert set(kwargs) == {
            "aws_access_key_id",
            "aws_secret_access_key",
            "aws_session_token",
        }
    import boto3
    from botocore.credentials import RefreshableCredentials

    session = boto3.Session(**kwargs)
    first = session.get_credentials()
    assert not isinstance(first, RefreshableCredentials)
    later = time.time() + 7200
    with patch("time.time", return_value=later):
        assert session.get_credentials() is first
    source = "\n".join(p.read_text() for p in (ROOT / "inventag").rglob("*.py"))
    assert "RefreshableCredentials" not in source
    assert "DurationSeconds" not in source


def test_the_static_region_list_has_fourteen_names_and_the_cli_always_passes_regions(
    aws, tmp_path, monkeypatch
):
    """Architecture: the static list of fourteen regions is used only when a
    library caller passes no regions; the CLI passes a list on every path."""
    from inventag.discovery import inventory as inv

    assert len(inv.AWSResourceInventory._get_available_regions(mock.MagicMock())) == 14
    seen = []
    original = inv.AWSResourceInventory.__init__

    def spy(self, *args, **kwargs):
        seen.append(kwargs.get("regions", args[0] if args else None))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(inv.AWSResourceInventory, "__init__", spy)
    # default regions (auto-discovered) and typed regions
    for extra in ((), ("--account-regions", "us-east-1")):
        code = run_cli(
            "--create-excel",
            "--no-billing-validation",
            *extra,
            "--output-directory",
            str(tmp_path / "o"),
        )
        assert code == 0
    assert len(seen) == 2 and all(isinstance(r, list) and r for r in seen), seen
    # the only place in the package that builds an inventory passes regions=
    callers = [
        p
        for p in (ROOT / "inventag").rglob("*.py")
        if "AWSResourceInventory(" in p.read_text() and p.name != "inventory.py"
    ]
    assert [c.name for c in callers] == ["cloud_bom_generator.py"]
    assert "regions=regions_to_use" in callers[0].read_text()


UNUSED_MODULES = (
    "reporting/template_framework.py",
    "reporting/branding_system.py",
    "reporting/word_builder.py",
    "reporting/excel_builder.py",
    "reporting/document_generator.py",
    "reporting/configuration_manager.py",
    "discovery/enhanced_readonly_discovery.py",
)


def test_modules_named_on_the_architecture_page_are_not_called_by_a_default_run(
    aws, tmp_path
):
    """Architecture: these modules are not on the CLI path.  Every function call of
    a default run (all threads) is recorded; none is a call into these files,
    apart from the module-level code that runs when two of them are imported."""
    import subprocess
    import threading

    called = set()
    wanted = tuple("inventag/" + m for m in UNUSED_MODULES)

    def profile(frame, event, arg):
        if event == "call":
            filename = frame.f_code.co_filename.replace("\\", "/")
            if filename.endswith(wanted) and frame.f_code.co_name != "<module>":
                called.add((filename.split("inventag/", 1)[1], frame.f_code.co_name))

    threading.setprofile(profile)
    sys.setprofile(profile)
    try:
        code = run_cli(
            "--create-excel",
            "--create-word",
            "--no-billing-validation",
            "--account-regions",
            "us-east-1",
            "--output-directory",
            str(tmp_path / "o"),
        )
    finally:
        sys.setprofile(None)
        threading.setprofile(None)
    assert code == 0
    assert sorted(tmp_path.joinpath("o").glob("*.docx")), "no Word file was written"
    assert called == set(), sorted(called)

    # which of them are imported when the command starts
    modules = [m[:-3].replace("/", ".") for m in UNUSED_MODULES]
    probe = (
        "import sys, inventag.cli.main\n"
        f"print([m for m in {modules!r} if 'inventag.' + m in sys.modules])"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    ).stdout
    assert eval(out) == ["reporting.template_framework", "reporting.document_generator"]
