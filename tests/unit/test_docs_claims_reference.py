"""Docs claim check for docs/reference/*.md (claims audit, group "reference").

Part A: the page equals the code (parser, IAM policy, exit codes).
Part B: behaviours the pages state, run for real under moto.
A test whose docstring says FALSE asserts what the code really does, so the
page can be corrected (or the code fixed) later without losing the evidence.
"""

import importlib
import json
import logging
import re
import sys
from pathlib import Path

import pytest
import yaml
from moto import mock_aws

from inventag import exit_codes
from inventag.security import iam_policy, redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "reference"


# ------------------------------------------------------------------ helpers
@pytest.fixture
def empty_aws(monkeypatch, tmp_path):
    monkeypatch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-creds"))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        yield
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def run_cli(*args):
    uninstall_global_guard()  # each run starts like a new process (own audit)
    old_argv = sys.argv
    sys.argv = ["inventag", *args]
    try:
        cli_main.main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old_argv


def table_rows(text):
    """Cells of every table row of a markdown page (header and rule rows too)."""
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            yield number, cells


def documented_flags():
    """{flag: (line, default cell, status cell)} of the flag tables of cli.md."""
    found = {}
    text = (DOCS / "cli.md").read_text()
    for number, cells in table_rows(text):
        if len(cells) != 4 or not cells[0].startswith("`-"):
            continue
        for chunk in re.findall(r"`(-[^`]*)`", cells[0]):
            for part in chunk.split("/"):
                match = re.match(r"\s*(--?[\w-]+)", part)
                if match:
                    found[match.group(1)] = (number, cells[1], cells[2])
    return found


# ======================================================= A. page equals code
def test_cli_page_flags_equal_parser():
    parser = cli_main.create_parser()
    in_parser = {o for a in parser._actions for o in a.option_strings}
    on_page = set(documented_flags())
    assert on_page - in_parser == set()  # flags on the page that the parser lacks
    # --version is shown in the Commands block, -h/--help is standard
    assert in_parser - on_page == {"--version", "-h", "--help"}


# page default cell -> what the parser holds; the text defaults are checked
# by hand in the ledger (they describe behaviour, not the parser default)
TEXT_DEFAULTS = {
    "--create-excel",  # "on if no other output flag"
    "--account-regions",  # "every enabled region"
    "--account-services",  # "all"
    "--google-title",  # "dated name"
    "--s3-key-prefix",  # parser None, code uses bom-reports/ (main.py)
    "--enable-delta-detection",  # row covers the pair; see below
    "--disable-delta-detection",
    "--disable-state-management",
}


def test_cli_page_defaults_equal_parser():
    parser = cli_main.create_parser()
    actions = {o: a for a in parser._actions for o in a.option_strings}
    bad = []
    for flag, (line, default, _status) in documented_flags().items():
        if flag in TEXT_DEFAULTS:
            continue
        action = actions[flag]
        value = action.default
        if default == "none":
            ok = value in (None, [])
        elif default == "off":
            ok = value is False
        elif default == "on":
            ok = value is True
        else:
            ok = str(value) in (default.strip("`"), default.strip("`") + ".0")
        if not ok:
            bad.append((line, flag, default, value))
    assert bad == []


def test_cli_page_s3_prefix_default_is_applied_by_the_code():
    parser = cli_main.create_parser()
    assert parser.parse_args(["--s3-bucket", "b"]).s3_key_prefix is None
    source = (ROOT / "inventag" / "cli" / "main.py").read_text()
    assert 'args.s3_key_prefix or "bom-reports/"' in source


def test_exit_codes_zero_to_six_in_page_order():
    assert [
        exit_codes.EXIT_OK,
        exit_codes.EXIT_ERROR,
        exit_codes.EXIT_USAGE,
        exit_codes.EXIT_TAG_VIOLATIONS,
        exit_codes.EXIT_RISK_THRESHOLD,
        exit_codes.EXIT_ACCOUNT_FAILED,
        exit_codes.EXIT_NO_RESOURCES,
    ] == [0, 1, 2, 3, 4, 5, 6]
    table = {
        int(cells[0]): cells[1]
        for _n, cells in table_rows((DOCS / "cli.md").read_text())
        if len(cells) == 2 and cells[0].isdigit()
    }
    assert sorted(table) == [0, 1, 2, 3, 4, 5, 6]
    glossary = (DOCS / "glossary.md").read_text()
    positions = [glossary.index(f"`{n}` for") for n in range(1, 7) if n != 2]
    assert positions == sorted(positions)
    assert "5 comes first, then 6, then 3, then 4" in glossary


def _policy_actions():
    policy = json.loads(
        (ROOT / "config/defaults/iam-policy-read-only.json").read_text()
    )
    by_sid = {}
    for statement in policy["Statement"]:
        actions = statement["Action"]
        by_sid[statement["Sid"]] = [actions] if isinstance(actions, str) else actions
    return policy, by_sid


def test_iam_page_equals_policy_file():
    policy, by_sid = _policy_actions()
    page = (DOCS / "iam-permissions.md").read_text()
    discovery = by_sid["InvenTagReadOnlyDiscovery"]
    assert len(discovery) == 122  # "an explicit list of 122 read actions"
    assert set(discovery) == set(iam_policy.READ_ONLY_ACTIONS)
    assert by_sid["InvenTagApiGatewayMetadata"] == ["apigateway:GET"]
    assert set(by_sid["OptionalS3ReportUpload"]) == {"s3:PutObject"}
    # every action the page names (outside the 17 added) is in the policy
    added = re.search(r"17 actions.*?:\s*(.*?)\. It also", page, re.S).group(1)
    added = re.findall(r"`([^`]+)`", added)
    assert len(added) == 17 and set(added) <= set(discovery)
    for named in (
        "tag:GetResources",
        "ce:GetCostAndUsage",
        "pricing:GetProducts",
        "lambda:GetFunctionConfiguration",
        "cloudwatch:GetMetricStatistics",
        "ec2:DescribeRegions",
        "account:ListRegions",
        "s3:ListAllMyBuckets",
        "s3:GetBucketTagging",
        "lambda:ListFunctions",
        "dynamodb:ListTables",
    ):
        assert named in discovery
    assert "cloudtrail:LookupEvents" not in discovery
    assert "sts:GetCallerIdentity" not in discovery  # page: need not be granted
    api = [
        r.split("::")[1]
        for s in policy["Statement"]
        if s["Sid"] == "InvenTagApiGatewayMetadata"
        for r in s["Resource"]
    ]
    assert api == ["/restapis", "/domainnames", "/usageplans"]
    upload = [s for s in policy["Statement"] if s["Sid"] == "OptionalS3ReportUpload"][0]
    assert upload["Condition"] == {"Null": {"s3:x-amz-server-side-encryption": "false"}}
    assert "YOUR-REPORTS-BUCKET-NAME" in upload["Resource"][0]
    assert "YOUR-REPORTS-BUCKET-NAME" in page and "OptionalS3ReportUpload" in page


# ---------------------------------- B1. flags that stop before any AWS call
@pytest.mark.parametrize(
    "argv",
    [
        ["--accounts-file", "a.json", "--accounts-prompt"],
        [
            "--cross-account-role",
            "arn:aws:iam::123456789012:role/R",
            "--accounts-file",
            "a.json",
        ],
        [
            "--cross-account-role",
            "arn:aws:iam::123456789012:role/R",
            "--accounts-prompt",
        ],
        ["--cross-account-role", "RoleName"],
        ["--word-template", "x.yaml"],
        ["--excel-template", "x.yaml", "--create-word"],
        ["--validate-templates"],
        ["--resume", "--disable-state-management"],
        ["--s3-bucket", "bucket-1", "--s3-kms-key-id", "k"],
        ["--risk-threshold", "HIGH"],
        ["--compliance-standard", "soc2"],
        ["--disable-production-safety"],
        ["--create-google-docs"],
    ],
)
def test_flags_that_stop_with_exit_2(empty_aws, argv):
    assert run_cli(*argv) == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["--max-concurrent-accounts", "0"],
        ["--account-processing-timeout", "59"],
        ["--resume-max-age-hours", "169"],
    ],
)
def test_out_of_range_numbers_stop_with_exit_1_not_2(empty_aws, argv):
    """The page says "at least 1", "at least 60", "at most 168" and lists
    invalid arguments under exit code 1; a value out of range is exit 1."""
    assert run_cli(*argv, "--validate-credentials") == 1


def test_state_limits_accept_zero_and_none_and_reject_negative(empty_aws):
    for flag in ("--state-retention-days", "--state-max-snapshots"):
        for value in ("0", "none"):
            assert run_cli(flag, value, "--validate-credentials") == 0
        assert run_cli(flag, "-1", "--validate-credentials") == 2


def test_validate_operations_exit_codes_and_lines(empty_aws, capsys):
    assert run_cli("--validate-operations", "ec2:DescribeInstances") == 0
    assert (
        run_cli(
            "--validate-operations",
            "ec2:DescribeInstances",
            "s3:PutObject",
            "secretsmanager:GetSecretValue",
        )
        == 1
    )
    out = capsys.readouterr().out
    assert "ALLOWED  ec2:DescribeInstances (read-only prefix)" in out
    assert "BLOCKED  s3:PutObject (operation is not on the read-only allowlist)" in out


def test_print_default_template_exits_0(empty_aws, capsys):
    for kind in ("word", "excel"):
        assert run_cli("--print-default-template", kind) == 0
        assert capsys.readouterr().out.strip()


def test_validate_config_only_checks_named_files_and_makes_no_aws_call(
    empty_aws, tmp_path
):
    (tmp_path / "bad.yaml").write_text("accounts:\n  - account_id: 123456789012\n")
    (tmp_path / "ok.yaml").write_text(
        "accounts:\n  - account_id: '123456789012'\n    regions: [us-east-1]\n"
    )
    flags = ["--validate-config-only", "--skip-credential-validation"]
    assert run_cli("--accounts-file", "ok.yaml", *flags) == 0
    assert run_cli("--accounts-file", "bad.yaml", *flags) == 1


def test_validate_config_only_does_not_check_bom_config_FALSE(empty_aws, tmp_path):
    """Page: "Check only the files you name". A --bom-config file with a value of
    the wrong type is accepted by --validate-config-only (exit 0) although a real
    run stops with exit 1 on the same file: the check skips --bom-config."""
    (tmp_path / "bom.yaml").write_text("max_worker_threads: many\n")
    flags = ["--validate-config-only", "--skip-credential-validation"]
    assert run_cli("--bom-config", "bom.yaml", *flags) == 0


# ================================================== B2. runs under moto
import os
import re as _re
import stat
import time

import boto3
import openpyxl

BASE = ["--no-billing-validation", "--account-regions", "us-east-1"]


@pytest.fixture
def estate(empty_aws):
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="acme-logs")
    boto3.client("s3", region_name="us-east-1").put_bucket_tagging(
        Bucket="acme-logs",
        Tagging={"TagSet": [{"Key": "Owner", "Value": "platform"}]},
    )
    sqs = boto3.client("sqs", region_name="us-east-1")
    sqs.create_queue(QueueName="tagged-queue", tags={"Owner": "platform"})
    sqs.create_queue(QueueName="plain-queue")
    return None


def files(folder):
    return sorted(
        str(p.relative_to(folder)) for p in Path(folder).rglob("*") if p.is_file()
    )


def sheets(path):
    wb = openpyxl.load_workbook(path)
    return {ws.title: list(ws.iter_rows(values_only=True)) for ws in wb}


def only(folder, pattern):
    found = sorted(Path(folder).glob(pattern))
    assert len(found) == 1, (pattern, files(folder))
    return found[0]


def test_default_run_files_names_modes_columns_and_audit(estate, tmp_path):
    assert (
        run_cli(*BASE, "--output-directory", "o", "--audit-output", "audit.json") == 0
    )
    out = tmp_path / "o"
    xlsx = only(out, "multi_account_bom_*.xlsx")  # "--create-excel, or no output flag"
    assert _re.fullmatch(r"multi_account_bom_\d{8}_\d{6}\.xlsx", xlsx.name)
    assert not list(out.glob("*.docx"))
    names = files(out)
    state = [n for n in names if n.startswith("state/state_")]
    assert len(state) == 1 and _re.fullmatch(r"state/state_\d{8}_\d{6}\.json", state[0])
    assert "state/metadata.json" in names
    assert not [n for n in names if n.startswith("changelog_")]  # first run
    # owner-only files and folders
    assert stat.S_IMODE(os.stat(xlsx).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(out).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(out / "state").st_mode) == 0o700
    assert stat.S_IMODE(os.stat(tmp_path / "audit.json").st_mode) == 0o600
    # metadata.json: time, account, regions, resource count, checksum
    meta = json.loads((out / "state/metadata.json").read_text())
    entry = next(iter(meta.values()))["metadata"]
    assert {"timestamp", "account_id", "regions", "resource_count", "checksum"} <= set(
        entry
    )
    # snapshot top level, and the coverage summary statuses
    snap = json.loads((out / state[0]).read_text())
    assert set(snap) == {
        "compliance_data",
        "metadata",
        "network_analysis",
        "resources",
        "security_analysis",
    }
    coverage = snap["metadata"]["tags"]["coverage_summary"]["123456789012"]
    assert set(coverage) <= {"ok", "empty", "denied", "throttled", "error", "timeout"}
    # Excel: Summary columns, sheets sorted, source columns, flattened columns
    book = sheets(xlsx)
    assert list(book)[0] == "Summary"
    assert list(book["Summary"][0]) == ["Service", "Resource Count", "Percentage"]
    assert str(book["Summary"][-1][0]).upper() == "TOTAL"
    services = list(book)[1:]
    assert services == sorted(services)
    header = list(book["SQS"][0])
    assert {"source", "sources", "detail_level"} <= set(header)
    assert any(h.startswith("tags.") for h in header)
    assert any(h.startswith("raw_data.") for h in header)
    # audit JSON keys
    audit = json.loads((tmp_path / "audit.json").read_text())
    assert list(audit) == [
        "read_only_enforced",
        "started_at",
        "generated_at",
        "allowed_prefixes",
        "total_calls",
        "allowed_calls",
        "blocked_calls",
        "operations",
        "blocked",
    ]
    assert audit["allowed_prefixes"] == [
        "List",
        "Describe",
        "Get",
        "Head",
        "Lookup",
        "Search",
        "BatchGet",
    ]


def test_ce_calls_and_region_check_counts_in_the_audit(estate, tmp_path):
    """IAM page: two ce:GetCostAndUsage per account in a default run;
    ec2:DescribeRegions once per scanned region; sts:GetCallerIdentity is called."""
    audit = tmp_path / "audit.json"
    assert (
        run_cli(
            "--account-regions",
            "us-east-1,eu-west-1",
            "--output-directory",
            "o",
            "--audit-output",
            str(audit),
        )
        == 0
    )
    count = {
        (o["service"], o["operation"]): o["count"]
        for o in json.loads(audit.read_text())["operations"]
    }
    assert count[("ce", "GetCostAndUsage")] == 2
    assert count[("ec2", "DescribeRegions")] == 2
    assert ("sts", "GetCallerIdentity") in count
    assert ("account", "ListRegions") not in count  # only when ec2 fails
    assert ("tag", "GetResources") in count or (
        "resourcegroupstaggingapi",
        "GetResources",
    ) in count
    audit2 = tmp_path / "audit2.json"
    assert (
        run_cli(*BASE, "--output-directory", "o2", "--audit-output", str(audit2)) == 0
    )
    count2 = {
        (o["service"], o["operation"])
        for o in json.loads(audit2.read_text())["operations"]
    }
    assert ("ce", "GetCostAndUsage") not in count2  # --no-billing-validation


def test_word_only_and_per_account_names(estate, tmp_path):
    assert run_cli(*BASE, "--create-word", "--output-directory", "w") == 0
    assert [n for n in files(tmp_path / "w") if "/" not in n] == [
        only(tmp_path / "w", "multi_account_bom_*.docx").name
    ]
    assert (
        run_cli(
            *BASE,
            "--create-excel",
            "--create-word",
            "--per-account-reports",
            "--output-directory",
            "p",
        )
        == 0
    )
    top = [n for n in files(tmp_path / "p") if "/" not in n]
    assert sorted(_re.sub(r"\d{8}_\d{6}", "TS", n) for n in top) == [
        "123456789012_bom_TS.docx",
        "123456789012_bom_TS.xlsx",
    ]


def test_second_run_changelog_and_switches(estate, tmp_path):
    def changelogs(folder):
        return [n for n in files(tmp_path / folder) if n.startswith("changelog_")]

    run_cli(*BASE, "--output-directory", "c")
    time.sleep(1.1)
    run_cli(*BASE, "--output-directory", "c")
    assert len(changelogs("c")) == 1
    assert _re.fullmatch(r"changelog_\d{8}_\d{6}\.md", changelogs("c")[0])
    for folder, flag in (
        ("n", "--no-generate-changelog"),
        ("d", "--disable-delta-detection"),
    ):
        run_cli(*BASE, "--output-directory", folder)
        time.sleep(1.1)
        run_cli(*BASE, "--output-directory", folder, flag)
        assert changelogs(folder) == []
    run_cli(*BASE, "--output-directory", "s", "--disable-state-management")
    run_cli(*BASE, "--output-directory", "s", "--disable-state-management")
    assert not (tmp_path / "s" / "state").exists()
    assert changelogs("s") == []


def test_service_and_tag_filters(estate, tmp_path):
    assert (
        run_cli(*BASE, "--output-directory", "a", "--account-services", "S3,SQS") == 0
    )
    book = sheets(only(tmp_path / "a", "*.xlsx"))
    assert [r[0] for r in book["Summary"][1:-1]] == ["S3", "SQS"]
    assert (
        run_cli(
            *BASE, "--output-directory", "b", "--account-tags", '{"Owner":"platform"}'
        )
        == 0
    )
    book = sheets(only(tmp_path / "b", "*.xlsx"))
    assert {r[0]: r[1] for r in book["Summary"][1:-1]} == {"S3": 1, "SQS": 1}


def test_tag_mappings_service_descriptions_and_bom_config(estate, tmp_path):
    (tmp_path / "tm.yaml").write_text(
        "tag_mappings:\n  - tag: Owner\n    name: Team Owner\n"
        "    default_value: Unknown\n    required: false\n    case_sensitive: false\n"
    )
    (tmp_path / "sd.yaml").write_text(
        "service_descriptions:\n  S3:\n    default:\n      description: Object bucket\n"
        "  SQS:\n    Queue:\n      description: Plain text\n      template: qt\n"
        "templates:\n  qt:\n    template: 'Queue {resource_id} in {region}'\n"
    )
    (tmp_path / "bc.yaml").write_text("enable_network_analysis: true\nbogus_key: 1\n")
    assert (
        run_cli(
            *BASE,
            "--output-directory",
            "t",
            "--tag-mappings",
            "tm.yaml",
            "--service-descriptions",
            "sd.yaml",
            "--bom-config",
            "bc.yaml",
        )
        == 0
    )
    book = sheets(only(tmp_path / "t", "*.xlsx"))
    sqs = book["SQS"]
    head = list(sqs[0])
    owners = {r[head.index("id")]: r[head.index("Team Owner")] for r in sqs[1:]}
    assert sorted(owners.values()) == ["Unknown", "platform"]  # default value
    descs = {r[head.index("service_description")] for r in sqs[1:]}
    assert {d.rsplit("/", 1)[-1] for d in descs} == {
        "plain-queue in us-east-1",
        "tagged-queue in us-east-1",
    }  # {resource_id} of an SQS queue is its URL
    s3 = book["S3"]
    assert s3[1][list(s3[0]).index("service_description")] == "Object bucket"


def test_tag_mappings_not_shown_with_a_report_template(estate, tmp_path, caplog):
    (tmp_path / "tm.yaml").write_text(
        "tag_mappings:\n  - tag: Owner\n    name: Team Owner\n"
    )
    caplog.set_level(logging.WARNING)
    code = run_cli(
        *BASE,
        "--output-directory",
        "t",
        "--template",
        "standard-bom",
        "--tag-mappings",
        "tm.yaml",
    )
    assert code == 0
    book = sheets(only(tmp_path / "t", "*.xlsx"))
    assert not any("Team Owner" in str(c) for r in book.get("SQS", []) for c in r)
    assert "tag_columns" in caplog.text


def test_word_report_shows_at_most_50_resources_per_service(empty_aws, tmp_path):
    import docx

    sqs = boto3.client("sqs", region_name="us-east-1")
    for i in range(55):
        sqs.create_queue(QueueName=f"q-{i:02d}")
    assert (
        run_cli(
            *BASE,
            "--create-word",
            "--account-services",
            "SQS",
            "--output-directory",
            "w",
        )
        == 0
    )
    document = docx.Document(str(only(tmp_path / "w", "*.docx")))
    rows = [len(t.rows) - 1 for t in document.tables if len(t.columns) == 6]
    assert rows == [50]  # 55 queues, 50 shown (header row not counted)
    assert [c.text for c in document.tables[-1].rows[0].cells] == [
        "Name",
        "Id",
        "Type",
        "Region",
        "Tags",
        "Service",
    ]


def test_s3_upload_keys_encryption_and_failure_exit_1(estate, tmp_path):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="reports-bucket")
    assert (
        run_cli(
            *BASE,
            "--create-excel",
            "--create-word",
            "--s3-bucket",
            "reports-bucket",
            "--output-directory",
            "o",
        )
        == 0
    )
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket="reports-bucket")["Contents"]]
    assert len(keys) == 2
    for key in keys:  # default prefix bom-reports/, then <UTC timestamp>/<file>
        assert _re.fullmatch(
            r"bom-reports/\d{8}_\d{6}/multi_account_bom_\d{8}_\d{6}\.(xlsx|docx)", key
        )
        head = s3.head_object(Bucket="reports-bucket", Key=key)
        assert head["ServerSideEncryption"] == "AES256"
    # a bucket that does not exist: the run exits 1
    assert (
        run_cli(
            *BASE,
            "--create-excel",
            "--s3-bucket",
            "no-such-bucket-xyz",
            "--output-directory",
            "o2",
        )
        == 1
    )


def test_s3_kms_encryption_without_key_id_uses_aws_kms(estate, tmp_path):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="reports-bucket")
    assert (
        run_cli(
            *BASE,
            "--s3-bucket",
            "reports-bucket",
            "--s3-encryption",
            "aws:kms",
            "--s3-key-prefix",
            "mine/",
            "--output-directory",
            "o",
        )
        == 0
    )
    [key] = [o["Key"] for o in s3.list_objects_v2(Bucket="reports-bucket")["Contents"]]
    assert key.startswith("mine/")
    assert (
        s3.head_object(Bucket="reports-bucket", Key=key)["ServerSideEncryption"]
        == "aws:kms"
    )


def test_template_run_writes_tag_compliance_json_and_wrote_lines(
    estate, tmp_path, capsys
):
    assert (
        run_cli(
            *BASE,
            "--template",
            "finops-cost-report",
            "--template",
            "finops-cost-allocation",
            "--output-directory",
            "o",
        )
        == 0
    )
    out = tmp_path / "o"
    tag_json = only(out, "tag_compliance_*.json")
    assert _re.fullmatch(r"tag_compliance_\d{8}_\d{6}\.json", tag_json.name)
    data = json.loads(tag_json.read_text())
    assert list(data) == ["policy", "description", "summary", "non_compliant_resources"]
    assert set(data["summary"]) == {
        "checked",
        "compliant",
        "non_compliant",
        "out_of_scope",
        "percent_compliant",
        "missing_by_key",
        "invalid_by_key",
    }
    first = data["non_compliant_resources"][0]
    assert list(first) == [
        "account",
        "service",
        "resource_type",
        "resource_id",
        "arn",
        "region",
        "missing",
        "invalid",
    ]
    text = capsys.readouterr().out
    assert _re.search(r"Wrote \S*o/multi_account_bom_\d{8}_\d{6}\.xlsx\n", text)
    assert _re.search(r"Wrote \S*o/tag_compliance_\d{8}_\d{6}\.json\n", text)
    assert _re.search(
        r"^Tag policy 'finops-cost-allocation': \d+ of \d+ resources compliant",
        text,
        _re.M,
    )


def test_partial_results_folder_after_a_partly_failed_run(
    empty_aws, tmp_path, monkeypatch
):
    cbg = importlib.import_module("inventag.core.cloud_bom_generator")
    from botocore.exceptions import ClientError

    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="acme-logs")
    original = cbg.CloudBOMGenerator._assume_role_session
    bad = "222222222222"

    def assume(self, role_arn, account_id, external_id=None):
        if str(account_id) == bad:
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "no"}}, "AssumeRole"
            )
        return original(self, role_arn, account_id, external_id)

    monkeypatch.setattr(cbg.CloudBOMGenerator, "_assume_role_session", assume)
    accounts = {
        "accounts": [
            {"account_id": "123456789012", "regions": ["us-east-1"]},
            {
                "account_id": bad,
                "role_arn": f"arn:aws:iam::{bad}:role/R",
                "regions": ["us-east-1"],
            },
        ]
    }
    (tmp_path / "acc.json").write_text(json.dumps(accounts))
    args = [
        "--accounts-file",
        "acc.json",
        "--no-billing-validation",
        "--output-directory",
        "o",
    ]
    assert run_cli(*args) == 0
    partial = list((tmp_path / "o/state/partial").glob("*/*.json"))
    assert [p.name for p in partial] == ["123456789012.json"]  # <key>/<account-id>.json
    monkeypatch.setattr(cbg.CloudBOMGenerator, "_assume_role_session", original)
    assert run_cli(*args, "--resume") == 0
    assert not list(
        (tmp_path / "o/state/partial").glob("*/*.json")
    )  # removed after a complete run


# ============================================ B3. configuration-files.md
def page_yaml_blocks(name):
    """The ```yaml blocks of a reference page, loaded."""
    text = (DOCS / name).read_text()
    return [
        yaml.safe_load(block)
        for block in _re.findall(r"```yaml\n(.*?)```", text, _re.S)
    ]


def test_yaml_examples_of_the_configuration_page_pass_the_validators(tmp_path):
    from inventag.cli.config_validator import ConfigValidator

    accounts, tag_mappings, service_descriptions, bom = page_yaml_blocks(
        "configuration-files.md"
    )
    validator = ConfigValidator()
    for data, method in (
        (accounts, "validate_accounts_file"),
        (tag_mappings, "validate_tag_mappings_file"),
        (service_descriptions, "validate_service_descriptions_file"),
    ):
        path = tmp_path / f"{method}.yaml"
        path.write_text(yaml.safe_dump(data))
        result = getattr(validator, method)(str(path))
        assert result.errors == [], method
    from inventag.reporting.bom_processor import BOMProcessingConfig
    from inventag.reporting.settings_loader import apply_bom_settings

    assert apply_bom_settings(BOMProcessingConfig(), bom) == []  # no ignored keys


def test_repository_example_accounts_files_named_on_the_page_validate():
    from inventag.cli.config_validator import ConfigValidator

    for name in ("accounts_cross_account_roles.json", "accounts_with_profiles.json"):
        result = ConfigValidator().validate_accounts_file(str(ROOT / "examples" / name))
        assert result.errors == [], name


@pytest.mark.parametrize(
    "flag, label",
    [
        ("--accounts-file", "accounts file"),
        ("--tag-mappings", "tag mappings file"),
        ("--service-descriptions", "service descriptions file"),
    ],
)
@pytest.mark.parametrize(
    "content, word",
    [
        ("", "empty"),
        ("a: 1\na: 2\n", "a"),  # key written twice
        ("- a\n- b\n", "mapping"),  # top level is not a mapping
    ],
)
def test_bad_config_files_stop_the_run_with_exit_1_naming_the_file(
    empty_aws, tmp_path, caplog, flag, label, content, word
):
    (tmp_path / "f.yaml").write_text(content)
    caplog.set_level(logging.ERROR)
    args = [flag, "f.yaml"]
    if flag != "--accounts-file":
        args += ["--skip-credential-validation"]
    assert run_cli(*args, *BASE) == 1
    assert "f.yaml" in caplog.text and word in caplog.text


def test_byte_order_mark_is_read(empty_aws, tmp_path):
    (tmp_path / "a.json").write_bytes(
        b"\xef\xbb\xbf"
        + json.dumps({"accounts": [{"account_id": "123456789012"}]}).encode()
    )
    assert (
        run_cli(
            "--accounts-file",
            "a.json",
            "--validate-config-only",
            "--skip-credential-validation",
        )
        == 0
    )


def test_account_without_credentials_is_valid_with_a_warning_FALSE(tmp_path):
    """Page: "Each account needs one way to get credentials". The validator
    accepts an account with none (a warning only): InvenTag then uses the
    current credentials if they belong to that account, otherwise it tries to
    assume the role InvenTagCrossAccountRole (or the --cross-account-role name)."""
    from inventag.cli.config_validator import ConfigValidator

    path = tmp_path / "a.json"
    path.write_text(json.dumps({"accounts": [{"account_id": "123456789012"}]}))
    result = ConfigValidator().validate_accounts_file(str(path))
    assert result.errors == []
    assert any("no credentials given" in w for w in result.warnings)
    assert any("InvenTagCrossAccountRole" in w for w in result.warnings)


def test_settings_in_the_accounts_file_override_the_flags(tmp_path):
    (tmp_path / "a.json").write_text(
        json.dumps(
            {
                "accounts": [{"account_id": "123456789012", "services": ["S3"]}],
                "settings": {
                    "max_concurrent_accounts": 2,
                    "account_processing_timeout": 90,
                    "output_directory": "from_file",
                },
            }
        )
    )
    args = cli_main.create_parser().parse_args(
        [
            "--accounts-file",
            str(tmp_path / "a.json"),
            "--max-concurrent-accounts",
            "7",
            "--account-processing-timeout",
            "600",
            "--output-directory",
            "from_flag",
        ]
    )
    config = cli_main.create_multi_account_config(args)
    assert config.max_concurrent_accounts == 2
    assert config.account_processing_timeout == 90
    assert config.output_directory == "from_file"
    assert config.accounts[0].services == ["S3"]
    assert config.accounts[0].regions == []  # empty: the scan asks the account


def test_accounts_file_services_filter_and_empty_regions_mean_every_enabled_region(
    estate, tmp_path
):
    from inventag.discovery.regions import discover_regions

    regions, source = discover_regions(boto3.Session())
    assert source == "ec2" and "us-east-1" in regions and len(regions) > 1
    (tmp_path / "a.json").write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "123456789012",
                        "regions": ["us-east-1"],
                        "services": ["S3"],
                    }
                ]
            }
        )
    )
    assert (
        run_cli(
            "--accounts-file",
            "a.json",
            "--no-billing-validation",
            "--output-directory",
            "o",
        )
        == 0
    )
    book = sheets(only(tmp_path / "o", "*.xlsx"))
    assert [r[0] for r in book["Summary"][1:-1]] == ["S3"]


def test_service_descriptions_file_without_the_required_key_is_accepted_FALSE(
    tmp_path, caplog
):
    """Page: "The top-level key service_descriptions is required" and "each
    resource type (or default) needs a description". The loader does refuse such
    a file, but only with an ERROR line in the log: --validate-config-only and
    the run accept it (exit 0) and use the built-in descriptions."""
    from inventag.cli.config_validator import ConfigValidator
    from inventag.discovery.service_descriptions import ServiceDescriptionManager

    wrong = tmp_path / "sd.yaml"
    wrong.write_text("S3:\n  default:\n    description: Mine\n")
    assert ConfigValidator().validate_service_descriptions_file(str(wrong)).errors == []
    no_text = tmp_path / "sd2.yaml"
    no_text.write_text(
        "service_descriptions:\n  S3:\n    default:\n      template: x\n"
    )
    assert (
        ConfigValidator().validate_service_descriptions_file(str(no_text)).errors == []
    )
    caplog.set_level(logging.ERROR)
    assert ServiceDescriptionManager(str(wrong)).descriptions.get("S3") is None
    assert "must contain 'service_descriptions' key" in caplog.text
    assert (
        ServiceDescriptionManager(str(no_text)).load_descriptions_from_file(
            str(no_text)
        )
        is False
    )


def test_failing_template_warns_and_uses_fallback_text(caplog):
    from inventag.discovery.service_descriptions import ServiceDescriptionManager

    caplog.set_level(logging.WARNING)
    text = ServiceDescriptionManager(None).get_dynamic_description(
        {
            "service": "VPC",
            "type": "VPC",
            "id": "vpc-1",
            "region": "us-east-1",
            "account_id": "1",
        }
    )
    assert "Failed to render template vpc_vpc: 'cidr_block'" in caplog.text
    assert text == "Amazon VPC VPC (vpc-1) in us-east-1"
    ec2 = ServiceDescriptionManager(None).get_dynamic_description(
        {
            "service": "EC2",
            "type": "Instance",
            "id": "i-0abc1234def567890",
            "region": "us-east-1",
            "account_id": "1",
        }
    )
    assert (
        ec2 == "Amazon EC2 Instance (i-0abc1234def567890) in us-east-1"
    )  # page sample


# ======================================================== B4. iam-permissions
def deny(monkeypatch, service, operation, when):
    import botocore.client
    from botocore.exceptions import ClientError

    original = botocore.client.BaseClient._make_api_call
    seen = []

    def call(client, operation_name, api_params):
        if (
            client.meta.service_model.service_name == service
            and operation_name == operation
            and when(client, api_params)
        ):
            seen.append(api_params)
            raise ClientError(
                {"Error": {"Code": "UnauthorizedOperation", "Message": "denied"}},
                operation_name,
            )
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)
    return seen


def test_a_region_that_fails_the_region_check_is_skipped_with_a_warning(
    estate, tmp_path, monkeypatch, caplog
):
    seen = deny(
        monkeypatch,
        "ec2",
        "DescribeRegions",
        lambda c, p: p.get("RegionNames") == ["eu-west-1"],
    )
    caplog.set_level(logging.WARNING)
    assert (
        run_cli(
            "--account-regions",
            "us-east-1,eu-west-1",
            "--no-billing-validation",
            "--account-services",
            "S3",
            "--output-directory",
            "o",
        )
        == 0
    )
    assert seen and "No access to region eu-west-1" in caplog.text
    book = sheets(only(tmp_path / "o", "*.xlsx"))
    assert {
        c for r in book["S3"][1:] for c in r if c in ("us-east-1", "eu-west-1")
    } == {"us-east-1"}


def test_region_check_denied_everywhere_scans_all_regions(
    estate, tmp_path, monkeypatch, caplog
):
    deny(monkeypatch, "ec2", "DescribeRegions", lambda c, p: bool(p.get("RegionNames")))
    caplog.set_level(logging.WARNING)
    assert (
        run_cli(
            "--account-regions",
            "us-east-1,eu-west-1",
            "--no-billing-validation",
            "--account-services",
            "S3",
            "--output-directory",
            "o",
        )
        == 0
    )
    assert "ec2:DescribeRegions is denied in every region" in caplog.text
    assert "scanning all 2 regions" in caplog.text


def test_account_list_regions_is_the_fallback_when_ec2_describe_regions_fails(
    estate, monkeypatch, caplog
):
    from inventag.discovery.regions import discover_regions

    deny(monkeypatch, "ec2", "DescribeRegions", lambda c, p: True)
    caplog.set_level(logging.INFO)
    regions, source = discover_regions(boto3.Session())
    assert source in ("account", "botocore")  # moto may not serve account:ListRegions
    assert "trying account:ListRegions instead" in caplog.text


# ================================================== B5. analysis flags, misc
def test_templates_must_be_the_first_word(empty_aws, capsys):
    assert run_cli("templates", "list") == 0
    assert run_cli("--verbose", "templates", "list") == 2  # parsed as a scan: refused


def test_templates_validate_exit_codes(empty_aws, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("kind: report\nname: [\n")
    assert run_cli("templates", "validate", "standard-bom") == 0
    assert run_cli("templates", "validate", "standard-bom", str(bad)) == 1


def test_analysis_flags_with_and_without_a_template(empty_aws, tmp_path):
    from tests.e2e.estate import seed_estate

    seed_estate()
    boto3.client("ec2", region_name="us-east-1").run_instances(
        ImageId="ami-12345678", MinCount=1, MaxCount=1, InstanceType="t2.micro"
    )
    flags = [
        "--account-regions",
        "us-east-1",
        "--no-billing-validation",
        "--enable-network-analysis",
        "--enable-security-analysis",
        "--enable-cost-analysis",
        "--disable-state-management",
    ]
    assert run_cli(*flags, "--output-directory", "d", "--audit-output", "au.json") == 0
    ops = {
        (o["service"], o["operation"])
        for o in json.loads((tmp_path / "au.json").read_text())["operations"]
    }
    # cost analysis calls Cost Explorer, Pricing and CloudWatch, also with --no-billing-validation
    assert {
        ("ce", "GetCostAndUsage"),
        ("pricing", "GetProducts"),
        ("cloudwatch", "GetMetricStatistics"),
    } <= ops
    book = sheets(only(tmp_path / "d", "*.xlsx"))
    assert {"Network Analysis", "Security Analysis", "Cost Analysis"} <= set(book)
    wanted = {
        "forgotten_analysis.days_since_last_activity",
        "forgotten_analysis.risk_level",
        "forgotten_analysis.is_potentially_forgotten",
        "forgotten_analysis.recommendations",
    }
    columns = {c for rows in book.values() for c in (rows[0] if rows else ()) if c}
    cost_cols = {c for c in columns if str(c).startswith("forgotten_analysis.")}
    # the page names four forgotten_analysis.* columns; record what a workbook has
    assert cost_cols == wanted
    assert run_cli(*flags, "--template", "standard-bom", "--output-directory", "t") == 0
    templated = sheets(only(tmp_path / "t", "*.xlsx"))
    assert not {"Network Analysis", "Security Analysis", "Cost Analysis"} & set(
        templated
    )


def test_per_account_reports_make_a_report_only_for_accounts_with_resources():
    import dataclasses
    from types import SimpleNamespace

    from inventag.core.cloud_bom_generator import CloudBOMGenerator
    from inventag.reporting.bom_processor import BOMData

    data = BOMData(resources=[])
    data = dataclasses.replace(
        data,
        resources=[
            {"source_account_id": "111111111111"},
            {"source_account_id": "222222222222"},
            {"source_account_id": "222222222222"},
        ],
    )
    stub = SimpleNamespace(config=SimpleNamespace(generate_per_account_reports=True))
    scopes = CloudBOMGenerator._report_scopes(stub, data)
    assert [(s[0], len(s[2].resources)) for s in scopes] == [
        ("111111111111_bom", 1),
        ("222222222222_bom", 2),
    ]


# ================================================ C. claims3: reference TEST rows
def test_version_flag_prints_the_version_and_exits_0(empty_aws, capsys):
    """cli.md Commands block: `inventag --version` prints the version and exits."""
    version = json.loads((ROOT / "version.json").read_text())["version"]
    assert run_cli("--version") == 0
    assert capsys.readouterr().out.strip() == f"inventag {version}"


def _cells(path):
    return {str(c) for rows in sheets(path).values() for r in rows for c in r}


@pytest.fixture
def estate_with_log_group(estate):
    # CloudWatch Logs has no discovery code of its own, so a tagged log group
    # reaches the report only through the Resource Groups Tagging API.
    boto3.client("logs", region_name="us-east-1").create_log_group(
        logGroupName="tagging-only-logs", tags={"Owner": "platform"}
    )


@pytest.mark.parametrize(
    "extra, shown",
    [
        ([], True),  # default is auto
        (["--fallback-display", "auto"], True),
        (["--fallback-display", "always"], True),
        (["--fallback-display", "never"], False),
        (["--hide-fallback-resources"], False),  # same as never
    ],
)
def test_fallback_display_and_the_deprecated_hide_flag(
    estate_with_log_group, tmp_path, extra, shown
):
    """cli.md: auto/always/never; --hide-fallback-resources = never."""
    assert run_cli(*BASE, "--output-directory", "o", *extra) == 0
    cells = _cells(only(tmp_path / "o", "*.xlsx"))
    assert any("tagging-only-logs" in c for c in cells) is shown
    assert any("tagged-queue" in c for c in cells)  # own discovery: always there


def test_fallback_auto_shows_tagging_only_resources_only_for_uncovered_services():
    """cli.md: `auto` shows them only for services with no results of their own."""
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    discovery = ComprehensiveAWSDiscovery(
        regions=["us-east-1"], fallback_display_mode="auto"
    )
    discovery.services_with_primary_resources = {"s3"}
    bucket = "arn:aws:s3:::acme-logs"
    log_group = "arn:aws:logs:us-east-1:123456789012:log-group:g"
    assert discovery._should_show_fallback(bucket) is False  # S3 has own results
    assert discovery._should_show_fallback(log_group) is True  # logs has none
    discovery.fallback_display_mode = "always"
    assert discovery._should_show_fallback(bucket) is True
    discovery.fallback_display_mode = "never"
    assert discovery._should_show_fallback(log_group) is False


class _CountingInventory:
    """Fake discovery that records how many accounts run at the same time."""

    lock = None
    running = 0
    peak = 0

    def __init__(self, session, regions, **kwargs):
        self.session = session

    def discover_all_resources(self):
        import threading  # noqa: F401

        cls = _CountingInventory
        with cls.lock:
            cls.running += 1
            cls.peak = max(cls.peak, cls.running)
        time.sleep(0.4)
        with cls.lock:
            cls.running -= 1
        return [{"id": "r", "service": "S3", "type": "Bucket", "region": "us-east-1"}]


def _peak_concurrency(tmp_path, argv):
    import threading
    from unittest.mock import patch

    from inventag.core.cloud_bom_generator import AccountContext, AccountCredentials

    _CountingInventory.lock = threading.Lock()
    _CountingInventory.running = 0
    _CountingInventory.peak = 0
    args = cli_main.create_parser().parse_args(
        [*argv, "--output-directory", str(tmp_path / "o")]
    )
    config = cli_main.create_multi_account_config(args)
    ids = ["111111111111", "222222222222", "333333333333"]
    contexts = {
        i: AccountContext(
            credentials=AccountCredentials(account_id=i, account_name=f"a-{i}"),
            session=boto3.Session(),
            caller_identity={"Account": i},
            accessible_regions=["us-east-1"],
        )
        for i in ids
    }
    generator = cli_main.CloudBOMGenerator(config)
    generator.account_contexts.update(contexts)
    generator._establish_account_contexts = lambda: contexts
    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", _CountingInventory
    ):
        generator.generate_comprehensive_bom(output_formats=[])
    return _CountingInventory.peak


def test_max_concurrent_accounts_limits_accounts_at_the_same_time(empty_aws, tmp_path):
    """cli.md: `--max-concurrent-accounts N` accounts scanned at the same time."""
    assert _peak_concurrency(tmp_path, ["--max-concurrent-accounts", "2"]) == 2
    assert _peak_concurrency(tmp_path, ["--max-concurrent-accounts", "3"]) == 3


def test_disable_parallel_processing_scans_one_account_at_a_time(empty_aws, tmp_path):
    """cli.md: `--disable-parallel-processing` scans one account at a time."""
    assert _peak_concurrency(tmp_path, ["--disable-parallel-processing"]) == 1


def test_validate_credentials_exits_1_when_an_account_fails_and_0_when_all_work(
    empty_aws, tmp_path
):
    """cli.md: `--validate-credentials` exits 0 if all work, 1 if not."""
    good = {"account_id": "123456789012"}  # moto's account; default credentials
    wrong = {"account_id": "999999999999"}  # not the account of the credentials
    (tmp_path / "good.json").write_text(json.dumps({"accounts": [good]}))
    (tmp_path / "mixed.json").write_text(json.dumps({"accounts": [good, wrong]}))
    assert run_cli("--accounts-file", "good.json", "--validate-credentials") == 0
    assert run_cli("--accounts-file", "mixed.json", "--validate-credentials") == 1


def test_tag_mapping_matches_keys_case_insensitively_unless_case_sensitive(tmp_path):
    """glossary: a tag mapping matches keys case-insensitively unless
    `case_sensitive: true`."""
    from inventag.discovery.tag_mapping import TagMappingEngine

    path = tmp_path / "m.yaml"
    path.write_text(
        "tag_mappings:\n"
        "  - {tag: Owner, name: Owner Mapped}\n"
        "  - {tag: Team, name: Team Mapped, case_sensitive: true}\n"
    )
    engine = TagMappingEngine(str(path))
    result = engine.extract_custom_attributes(
        {"id": "r", "tags": {"owner": "alex", "team": "core"}}
    )
    assert result.mapped_attributes["Owner Mapped"] == "alex"  # matched "owner"
    assert result.mapped_attributes["Team Mapped"] != "core"  # "team" is not "Team"
    exact = engine.extract_custom_attributes({"id": "r", "tags": {"Team": "core"}})
    assert exact.mapped_attributes["Team Mapped"] == "core"


def _word_headers(tmp_path, resources):
    import docx

    from inventag.reporting.converter import BOMConverter

    out = tmp_path / "w.docx"
    BOMConverter().generate_word_bom(resources, str(out))
    document = docx.Document(str(out))
    return [
        [c.text for c in t.rows[0].cells]
        for t in document.tables
        if len(t.columns) == 6
    ]


def test_word_report_six_columns_name_or_source_account_name(tmp_path):
    """outputs.md: six columns. Name when a resource of the service has a name,
    otherwise Source Account Name takes the sixth place."""
    base = {
        "service": "SQS",
        "type": "Queue",
        "region": "us-east-1",
        "tags": {"Owner": "x"},
        "account_id": "123456789012",
        "source_account_name": "prod",
    }
    named = [dict(base, id="q1", name="orders")]
    unnamed = [dict(base, id="q2")]
    assert _word_headers(tmp_path, named)[-1] == [
        "Name",
        "Id",
        "Type",
        "Region",
        "Tags",
        "Service",
    ]
    assert _word_headers(tmp_path, unnamed)[-1] == [
        "Id",
        "Type",
        "Region",
        "Tags",
        "Service",
        "Source Account Name",
    ]


def test_config_template_gives_the_same_accounts_as_an_accounts_file(
    empty_aws, tmp_path
):
    """configuration-files.md: a config template does what an accounts file does
    (here: the same two accounts) and cannot hold keys."""
    import logging as _logging

    from inventag.templating.errors import TemplateError
    from inventag.templating.runner import apply_config, load_templates

    accounts = [
        {
            "account_id": "111111111111",
            "account_name": "prod",
            "profile_name": "prod-profile",
            "regions": ["us-east-1"],
            "services": ["S3"],
        },
        {
            "account_id": "222222222222",
            "account_name": "dev",
            "role_arn": "arn:aws:iam::222222222222:role/InvenTagReadOnly",
            "external_id": "abc",
            "regions": ["eu-west-1"],
        },
    ]
    (tmp_path / "a.json").write_text(json.dumps({"accounts": accounts}))
    (tmp_path / "c.yaml").write_text(
        yaml.safe_dump({"kind": "config", "name": "c", "spec": {"accounts": accounts}})
    )
    file_args = cli_main.create_parser().parse_args(["--accounts-file", "a.json"])
    from_file = cli_main.create_multi_account_config(file_args).accounts
    tmpl_args = cli_main.create_parser().parse_args(["--template", "c.yaml"])
    run = load_templates(tmpl_args.template)
    apply_config(run, tmpl_args, set(), _logging.getLogger("t"))
    try:
        from_template = cli_main.create_multi_account_config(tmpl_args).accounts
    finally:
        run.cleanup()
    assert from_template == from_file and len(from_file) == 2
    # a template with a key field is refused
    (tmp_path / "k.yaml").write_text(
        yaml.safe_dump(
            {
                "kind": "config",
                "name": "k",
                "spec": {
                    "accounts": [
                        {"account_id": "111111111111", "access_key_id": "AKIAEXAMPLE"}
                    ]
                },
            }
        )
    )
    with pytest.raises(TemplateError):
        load_templates(["k.yaml"])


def test_profile_name_selects_the_aws_cli_profile(empty_aws, tmp_path, monkeypatch):
    """configuration-files.md: `profile_name` selects the AWS CLI profile."""
    (tmp_path / "config").write_text("[profile acme]\nregion = us-east-1\n")
    (tmp_path / "creds").write_text(
        "[acme]\naws_access_key_id = AKIAPROFILEEXAMPLE1\n"
        "aws_secret_access_key = fake-profile-secret-for-moto\n"
    )
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "creds"))
    from inventag.core.cloud_bom_generator import AccountCredentials, CloudBOMGenerator
    from inventag.core.cloud_bom_generator import MultiAccountConfig

    generator = CloudBOMGenerator(MultiAccountConfig(accounts=[]))
    session = generator._create_account_session(
        AccountCredentials(account_id="123456789012", profile_name="acme")
    )
    assert session.profile_name == "acme"
    assert session.get_credentials().access_key == "AKIAPROFILEEXAMPLE1"


def test_default_run_prints_data_exported_and_a_template_run_prints_wrote(
    estate, tmp_path, capsys
):
    """outputs.md Terminal output: `Data exported to <path>` for the default
    (Excel) report without a template, `Wrote <path>` with one."""
    assert (
        run_cli(*BASE, "--create-excel", "--create-word", "--output-directory", "o")
        == 0
    )
    out = capsys.readouterr().out
    assert _re.search(
        r"^Data exported to \S*o/multi_account_bom_\d{8}_\d{6}\.xlsx$", out, _re.M
    )
    # the Word report has its own line
    assert _re.search(
        r"Word document saved: \S*o/multi_account_bom_\d{8}_\d{6}\.docx$", out, _re.M
    )
    assert run_cli(*BASE, "--template", "standard-bom", "--output-directory", "t") == 0
    out = capsys.readouterr().out
    assert "Data exported to" not in out and "Wrote " in out


def test_file_name_timestamps_local_time_for_reports_and_tag_json_utc_for_the_rest(
    estate, tmp_path, monkeypatch
):
    """Observed: report, Word, changelog AND the tag compliance JSON of a template
    run are named with the computer's local time; the state snapshot and the S3
    folder are named with UTC (the docs sheet said the tag file is UTC: it is not)."""
    from datetime import datetime

    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="acme-reports")
    monkeypatch.setenv("TZ", "Asia/Singapore")  # UTC+8, no daylight saving
    time.tzset()
    try:
        argv = [*BASE, "--create-excel", "--create-word", "--output-directory", "o"]
        assert run_cli(*argv, "--s3-bucket", "acme-reports") == 0
        time.sleep(1.1)
        assert run_cli(*argv) == 0  # second run: changelog
        assert (
            run_cli(
                *BASE,
                "--template",
                "finops-cost-report",
                "--template",
                "finops-cost-allocation",
                "--output-directory",
                "t",
            )
            == 0
        )
    finally:
        now_local, now_utc = datetime.now(), datetime.utcnow()
        monkeypatch.delenv("TZ")
        time.tzset()

    def stamp(name):
        match = _re.search(r"(\d{8})_(\d{6})", name)
        return datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")

    out = tmp_path / "o"
    local = stamp(sorted(out.glob("multi_account_bom_*.xlsx"))[-1].name)
    word = stamp(sorted(out.glob("multi_account_bom_*.docx"))[-1].name)
    changelog = stamp(only(out, "changelog_*.md").name)
    snapshot = stamp(sorted((out / "state").glob("state_*.json"))[-1].name)
    tag_json = stamp(only(tmp_path / "t", "tag_compliance_*.json").name)
    keys = [
        o["Key"]
        for o in boto3.client("s3", region_name="us-east-1").list_objects_v2(
            Bucket="acme-reports"
        )["Contents"]
    ]
    s3_folder = stamp(keys[0].split("/")[1])
    eight_hours = 8 * 3600

    def seconds(a, b):
        return (a - b).total_seconds()

    # the six names: report, Word, changelog and tag compliance carry local time
    for local_name in (local, word, changelog, tag_json):
        assert abs(seconds(local_name, now_local)) < 300, local_name
    # the snapshot and the S3 folder carry UTC
    for utc_name in (snapshot, s3_folder):
        assert abs(seconds(utc_name, now_utc)) < 300, utc_name
    for utc in (snapshot, s3_folder):
        assert abs(seconds(local, utc) - eight_hours) < 120, (local, utc)


def test_failing_template_in_your_own_file_uses_that_entrys_description(
    tmp_path, caplog
):
    """configuration-files.md: a template that cannot be filled in logs a warning;
    for a template in your own file the entry's `description` is used."""
    from inventag.discovery.service_descriptions import ServiceDescriptionManager

    path = tmp_path / "sd.yaml"
    path.write_text(
        "service_descriptions:\n"
        "  EC2:\n"
        "    Volume:\n"
        "      description: Block storage\n"
        "      template: volume_text\n"
        "templates:\n"
        "  volume_text:\n"
        "    template: 'Disk {no_such_variable} in {region}'\n"
    )
    caplog.set_level(logging.WARNING)
    text = ServiceDescriptionManager(str(path)).get_dynamic_description(
        {
            "service": "EC2",
            "type": "Volume",
            "id": "vol-1",
            "region": "us-east-1",
            "account_id": "1",
        }
    )
    assert text == "Block storage"
    assert "Failed to render template" in caplog.text


def test_account_with_neither_profile_nor_role_is_refused_in_a_template_only(
    tmp_path,
):
    """configuration-files.md: a config template account needs `profile_name` or
    `role_arn`; an accounts-file account with neither is accepted."""
    from inventag.cli.config_validator import ConfigValidator
    from inventag.templating.errors import TemplateError
    from inventag.templating.runner import load_templates

    account = {"account_id": "111111111111"}
    (tmp_path / "a.json").write_text(json.dumps({"accounts": [account]}))
    assert (
        ConfigValidator().validate_accounts_file(str(tmp_path / "a.json")).errors == []
    )
    (tmp_path / "c.yaml").write_text(
        yaml.safe_dump({"kind": "config", "name": "c", "spec": {"accounts": [account]}})
    )
    with pytest.raises(TemplateError) as error:
        load_templates([str(tmp_path / "c.yaml")])
    assert "each account needs profile_name or role_arn" in str(error.value.issues)
