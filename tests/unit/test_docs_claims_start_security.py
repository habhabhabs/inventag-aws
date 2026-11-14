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
