"""Docs claims for docs/guides/*.md that were only read in code before (v1.2.0 docs).

Each test runs the real CLI under moto, like tests/unit/test_docs_claims_v120.py.
"""

import json
import logging

import pytest

from tests.unit.test_docs_claims_v120 import (  # noqa: F401  (fixtures + helpers)
    BASE,
    GOOD,
    GOOD_ID,
    OTHER,
    OTHER_ID,
    RoleControl,
    accounts_file,
    aws,
    empty_aws,
    logged,
    reports,
    run_cli,
    seed_account,
)


# ------------------------------------------------ option ranges (run-a-scan, troubleshooting)
@pytest.mark.parametrize(
    "flag,value,text",
    [
        ("--max-concurrent-accounts", "0", "must be a positive integer"),
        ("--account-processing-timeout", "59", "must be at least 60 seconds"),
        ("--resume-max-age-hours", "169", "must be above 0 and at most 168"),
        ("--resume-max-age-hours", "0", "must be above 0 and at most 168"),
    ],
)
def test_range_errors_name_the_option_and_exit_code(
    flag, value, text, empty_aws, capsys, caplog
):
    code = run_cli(flag, value, "--resume", "--validate-config-only", *BASE)
    out = capsys.readouterr().err + "\n".join(logged(caplog))
    assert text in out
    assert code == 1  # docs: "stops with exit code 1"


@pytest.mark.parametrize("flag", ["--state-retention-days", "--state-max-snapshots"])
def test_state_limits_not_a_number_exit_2(flag, empty_aws, capsys):
    assert run_cli(flag, "abc", *BASE) == 2
    assert "expected a whole number or 'none'" in capsys.readouterr().err


def test_resume_with_disabled_state_management_exit_2(empty_aws, capsys):
    assert run_cli("--resume", "--disable-state-management", *BASE) == 2
    assert "--resume: needs state management" in capsys.readouterr().err


def test_accounts_file_with_prompt_and_role_arn_with_file_exit_2(
    empty_aws, tmp_path, capsys
):
    path = accounts_file(tmp_path, [GOOD])
    assert run_cli("--accounts-file", path, "--accounts-prompt", *BASE) == 2
    assert "give one of them, not both" in capsys.readouterr().err
    arn = f"arn:aws:iam::{GOOD_ID}:role/R"
    assert run_cli("--accounts-file", path, "--cross-account-role", arn, *BASE) == 2
    assert "a full role ARN names one account" in capsys.readouterr().err


# ------------------------------------------------ track changes (CLI level)
def _run(tmp_path, *extra):
    return run_cli(
        *BASE, "--account-regions", "us-east-1", "--output-directory", "out", *extra
    )


def _state(tmp_path):
    return sorted((tmp_path / "out" / "state").glob("state_*.json"))


def test_first_run_no_changelog_second_run_writes_one(aws, tmp_path):
    import time

    assert _run(tmp_path) == 0
    out = tmp_path / "out"
    assert len(_state(tmp_path)) == 1
    assert not list(out.glob("changelog_*.md"))
    assert (out / "state" / "metadata.json").exists()
    time.sleep(1.1)
    assert _run(tmp_path) == 0
    assert len(_state(tmp_path)) == 2
    assert len(list(out.glob("changelog_*.md"))) == 1
    snap = json.loads(_state(tmp_path)[-1].read_text())
    assert {"resources", "metadata"} <= set(snap)
    meta = snap["metadata"]
    assert meta["version"] == "1.1" or meta.get("snapshot_version") == "1.1"
    assert "accounts_scanned" in meta and "accounts_failed" in meta


@pytest.mark.parametrize(
    "flags,changelog,snapshots",
    [
        (["--no-generate-changelog"], False, True),
        (["--disable-delta-detection"], False, True),
        (["--disable-state-management"], False, False),
    ],
)
def test_flags_that_stop_the_change_report(aws, tmp_path, flags, changelog, snapshots):
    import time

    assert _run(tmp_path) == 0
    time.sleep(1.1)
    assert _run(tmp_path, *flags) == 0
    out = tmp_path / "out"
    assert bool(list(out.glob("changelog_*.md"))) is changelog
    if snapshots:
        assert len(_state(tmp_path)) == 2
    else:
        assert len(_state(tmp_path)) == 1  # nothing new was saved


def test_state_max_snapshots_one_leaves_two_files(aws, tmp_path):
    import time

    for _ in range(3):
        assert _run(tmp_path, "--state-max-snapshots", "1") == 0
        time.sleep(1.1)
    assert len(_state(tmp_path)) == 2


# ------------------------------------------------ a role that cannot be assumed
def test_role_name_failure_does_not_scan_the_account_with_default_credentials(
    aws, tmp_path, monkeypatch, caplog
):
    seed_account(OTHER_ID, OTHER["role_arn"])
    caplog.set_level(logging.INFO)
    RoleControl(monkeypatch, failing={OTHER_ID})
    path = accounts_file(
        tmp_path, [GOOD, {"account_id": OTHER_ID, "regions": ["us-east-1"]}]
    )
    code = run_cli(
        "--accounts-file",
        path,
        "--cross-account-role",
        "InvenTagReadOnly",
        *BASE,
        "--output-directory",
        "out",
    )
    assert code == 0
    files = reports(tmp_path / "out")
    assert len(files) == 1
    from tests.unit.test_docs_claims_v120 import workbook_text

    text = workbook_text(files[0])
    assert f"acct-{OTHER_ID}" not in text  # no resources of the other account
    assert OTHER_ID in text  # but the Run notes name it
    assert any("were not scanned" in m for m in logged(caplog))


# ------------------------------------------------ security analysis risk rules (network-and-security-analysis.md)
def test_wide_private_source_is_medium_and_outbound_is_always_low():
    import boto3
    from moto import mock_aws

    from inventag.discovery.security_analyzer import SecurityAnalyzer

    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
        g = ec2.create_security_group(GroupName="wide", Description="d", VpcId=vpc)[
            "GroupId"
        ]
        ec2.authorize_security_group_ingress(
            GroupId=g,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "10.0.0.0/8"}],
                }
            ],
        )
        ec2.authorize_security_group_egress(
            GroupId=g,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                }
            ],
        )
        analyzer = SecurityAnalyzer(boto3.Session(region_name="us-east-1"))
        analyzer.analyze_security_groups([{"id": "x", "region": "us-east-1"}])
        info = analyzer.sg_cache[g]
        assert [r.risk_assessment for r in info.inbound_rules] == ["medium"]
        assert {r.risk_assessment for r in info.outbound_rules} == {"low"}


def test_template_validate_catches_role_arn_of_another_account(
    empty_aws, tmp_path, capsys
):
    folder = tmp_path / ".inventag" / "templates"
    folder.mkdir(parents=True)
    (folder / "bad.yaml").write_text(
        "format_version: 1\nkind: config\nname: bad\nspec:\n  accounts:\n"
        '    - account_id: "123456789012"\n'
        "      role_arn: arn:aws:iam::999999999999:role/X\n  regions: [us-east-1]\n"
    )
    assert run_cli("templates", "validate", "bad") == 1
    out = capsys.readouterr()
    assert "role is in account 999999999999 but account_id is 123456789012" in (
        out.out + out.err
    )


# ------------------------------------------------ exit code 5 for a timed-out account (Ruling R1)
def test_timed_out_account_gives_exit_5(empty_aws, tmp_path):
    import argparse
    import threading
    from unittest.mock import patch

    from inventag.cli.main import _opt_in_exit_code
    from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
    from tests.unit.test_account_time_limit_and_failures import (
        FakeClock,
        SlowOrFastInventory,
        _contexts,
    )

    clock = FakeClock()
    SlowOrFastInventory.clock = clock
    SlowOrFastInventory.fast_done = threading.Event()
    SlowOrFastInventory.calls_after_limit = 0
    g = CloudBOMGenerator(
        MultiAccountConfig(
            accounts=[],
            output_directory=str(tmp_path),
            account_processing_timeout=60,
            parallel_account_processing=False,
        )
    )
    g._clock = clock
    g._poll_seconds = 0.01
    c = _contexts(["111111111111", "222222222222"])
    c["222222222222"].session._slow = True
    g.account_contexts.update(c)
    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", SlowOrFastInventory
    ):
        g._sequential_account_discovery(c)
    failed = g._failed_accounts()
    assert [f["account_id"] for f in failed] == ["222222222222"]
    args = argparse.Namespace(fail_on_account_error=True, fail_if_empty=False)
    code = _opt_in_exit_code(args, {"failed_accounts": failed}, logging.getLogger("x"))
    assert code == 5


# ------------------------------------------------ the time limit (run-a-scan, troubleshooting)
def test_discovery_stops_300_seconds_or_20_percent_early_and_later_steps_still_run():
    from unittest import mock

    from inventag.core.cloud_bom_generator import (
        CloudBOMGenerator,
        _AccountDeadline,
    )
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    def limit(timeout):
        deadline = _AccountDeadline("1", timeout, clock=lambda: 0.0)
        deadline.start()
        return CloudBOMGenerator._discovery_time_limit(deadline)

    # The smaller of 300 seconds and 20% of the limit is kept back.
    assert limit(600) == pytest.approx(480)  # 20% = 120 s
    assert limit(1800) == pytest.approx(1500)  # 20% = 360 s, so 300 s
    assert limit(3000) == pytest.approx(2700)

    # When the listings run out of time, tags and billing are still read.
    import threading

    release = threading.Event()
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(),
        regions=["us-east-1"],
        enable_billing_validation=True,
        discovery_timeout=0.2,
    )
    disc.service_discovery_patterns = {"slow": {"operations": [], "regional": True}}

    def slow(task):
        release.wait(5)
        return 0

    try:
        with (
            mock.patch.object(disc, "_discover_billing_services"),
            mock.patch.object(disc, "_discover_service_in_region", side_effect=slow),
            mock.patch.object(disc, "_enrich_with_tagging_api") as tags,
            mock.patch.object(disc, "_validate_with_billing") as billing,
            mock.patch.object(disc, "_add_billing_fallback_resources"),
            mock.patch.object(disc, "_post_process_resources"),
        ):
            disc.discover_all_resources()
    finally:
        release.set()
    assert tags.called and billing.called


def test_every_account_timing_out_writes_a_report_and_exits_1(
    empty_aws, tmp_path, monkeypatch, caplog
):
    from tests.unit.test_account_time_limit_and_failures import FakeClock

    clock = FakeClock()
    original = cbg_module().CloudBOMGenerator.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self._clock = clock
        self._poll_seconds = 0.01

    class TimesOut:
        def __init__(self, session, regions, **kwargs):
            self.session = session

        def discover_all_resources(self):
            self.session.client("ec2", region_name="us-east-1").describe_regions()
            clock.now += 10_000  # past the limit
            try:  # real discovery code catches errors per service and carries on
                self.session.client("ec2", region_name="us-east-1").describe_vpcs()
            except Exception:
                pass
            return [{"id": "r1", "service": "EC2", "type": "Instance", "region": "x"}]

    monkeypatch.setattr(cbg_module().CloudBOMGenerator, "__init__", init)
    monkeypatch.setattr(cbg_module(), "AWSResourceInventory", TimesOut)
    caplog.set_level(logging.INFO)
    path = accounts_file(tmp_path, [GOOD])
    code = run_cli(
        "--accounts-file",
        path,
        "--account-processing-timeout",
        "60",
        "--disable-parallel-processing",
        "--output-directory",
        "out",
        *BASE,
    )
    assert code == 1
    assert len(reports(tmp_path / "out")) == 1  # the report of what was found
    assert any(
        "No account finished within its time limit" in m
        for m in logged(caplog, logging.ERROR)
    )


def cbg_module():
    import importlib

    return importlib.import_module("inventag.core.cloud_bom_generator")


# ------------------------------------------------ flags you type win over a config template
def test_a_typed_region_flag_wins_over_the_regions_of_a_config_template(
    aws, tmp_path, monkeypatch
):
    folder = tmp_path / ".inventag" / "templates"
    folder.mkdir(parents=True)
    (folder / "my-scan.yaml").write_text(
        "format_version: 1\nkind: config\nname: my-scan\n"
        "spec:\n  regions: [us-east-1]\n  outputs: [excel]\n"
    )
    seen = []
    cbg = cbg_module()
    original = cbg.CloudBOMGenerator._discover_account_resources_inner

    def spy(self, account_id, context):
        seen.append(sorted(context.accessible_regions))
        return original(self, account_id, context)

    monkeypatch.setattr(cbg.CloudBOMGenerator, "_discover_account_resources_inner", spy)
    code = run_cli(
        "--template",
        "my-scan",
        "--account-regions",
        "eu-west-1",
        "--no-billing-validation",
    )
    assert code == 0
    assert seen == [["eu-west-1"]]


# ------------------------------------------------ the accounts file (scan-multiple-accounts, troubleshooting)
@pytest.mark.parametrize(
    "name,content,text",
    [
        ("a.yaml", "", "the file is empty"),
        ("b.yaml", "accounts: []\naccounts: []\n", "duplicate key 'accounts'"),
        (
            "c.yaml",
            "- account_id: '123456789012'\n",
            "the top level must be a mapping of key: value pairs, but the file holds a list",
        ),
        (
            "d.txt",
            "accounts: []\n",
            "unsupported file type '.txt'. Use .json, .yaml or .yml",
        ),
        (
            "big.yaml",
            "# " + "x" * (1024 * 1024) + "\naccounts: []\n",
            "the maximum is 1048576 bytes",
        ),
        ("missing.yaml", None, "Accounts file not found"),
    ],
)
def test_each_accounts_file_error_of_the_table_exits_1_with_its_text(
    empty_aws, tmp_path, capsys, caplog, name, content, text
):
    if content is not None:
        (tmp_path / name).write_text(content)
    caplog.set_level(logging.ERROR)
    assert run_cli("--accounts-file", name, *BASE) == 1
    out = capsys.readouterr()
    assert text in out.err + out.out + caplog.text


def test_an_accounts_file_of_exactly_1_mib_is_read_and_one_byte_more_is_not(
    empty_aws, tmp_path, caplog
):
    caplog.set_level(logging.ERROR)
    body = '{"accounts": [{"account_id": "123456789012"}]}'
    exact = body + " " * (1024 * 1024 - len(body))
    assert len(exact.encode()) == 1024 * 1024
    (tmp_path / "ok.json").write_text(exact)
    (tmp_path / "big.json").write_text(exact + " ")
    check = ["--validate-config-only", "--skip-credential-validation"]
    assert run_cli("--accounts-file", "ok.json", *check) == 0
    assert run_cli("--accounts-file", "big.json", *check) == 1
    assert "the maximum is 1048576 bytes" in caplog.text


# ------------------------------------------------ the guard blocks the named operations (read-only-access)
@pytest.mark.parametrize(
    "operation",
    [
        "secretsmanager:GetSecretValue",
        "ssm:GetParameter",
        "s3:GetObject",
        "dynamodb:GetItem",
        "lambda:GetFunction",
        "cloudformation:GetTemplate",
        "ec2:GetLaunchTemplateData",
        "glue:GetConnection",
        "athena:GetQueryResults",
    ],
)
def test_the_guard_blocks_the_nine_operations_of_the_read_only_page(operation, capsys):
    assert run_cli("--validate-operations", operation) == 1
    assert capsys.readouterr().out.startswith(
        f"BLOCKED  {operation} (operation returns secrets, signed URLs or customer data)"
    )


# ------------------------------------------------ track changes: the first run after the upgrade
def test_a_masked_value_shows_as_a_change_against_a_snapshot_with_the_raw_value():
    from inventag.state.delta_detector import DeltaDetector

    arn = "arn:aws:lambda:us-east-1:123456789012:function:f"
    old = [
        {
            "service": "Lambda",
            "type": "Function",
            "id": "f",
            "arn": arn,
            "region": "us-east-1",
            "environment": {"Variables": {"DB_PASSWORD": "hunter2"}},
        }
    ]
    new = [
        {
            **old[0],
            "environment": {"Variables": {"DB_PASSWORD": "***REDACTED***"}},
        }
    ]
    report = DeltaDetector().detect_changes(old, new, "old", "new")
    assert report.summary["modified_count"] == 1
    # The same masked value in two runs is no change.
    again = DeltaDetector().detect_changes(new, new, "a", "b")
    assert again.summary["modified_count"] == 0


# ------------------------------------------------ Google output with a mocked client (google-sheets-and-docs)
def _fake_google(monkeypatch):
    from inventag.reporting import google_output as go
    from tests.unit.test_google_output import fake_services

    log = []
    monkeypatch.setattr(go, "load_credentials", lambda options: object())
    monkeypatch.setattr(go, "build_services", lambda creds: fake_services(log))
    return go, log


def _two_account_google_run(tmp_path, monkeypatch, capsys):
    seed_account(OTHER_ID, OTHER["role_arn"])
    RoleControl(monkeypatch)
    go, log = _fake_google(monkeypatch)
    path = accounts_file(tmp_path, [GOOD, OTHER])
    code = run_cli(
        "--accounts-file",
        path,
        "--per-account-reports",
        "--create-google-sheets",
        "--create-google-docs",
        "--google-title",
        "AWS inventory",
        "--no-billing-validation",
    )
    return code, log, capsys.readouterr().out


def test_per_account_reports_make_two_pairs_of_google_files_with_the_account_in_the_title(
    aws, tmp_path, monkeypatch, capsys
):
    code, log, _ = _two_account_google_run(tmp_path, monkeypatch, capsys)
    assert code == 0
    sheets = [
        kw["body"]["properties"]["title"] for n, kw in log if n == "spreadsheets.create"
    ]
    docs = [kw["body"]["title"] for n, kw in log if n == "documents.create"]
    assert sorted(sheets) == [
        f"AWS inventory - {GOOD_ID}",
        f"AWS inventory - {OTHER_ID}",
    ]
    assert sorted(docs) == sorted(sheets)


@pytest.mark.xfail(
    strict=True,
    reason="the URL line is 'Google Sheet: [<id>] <url>': the line starts with "
    "'Google Sheet:', and the page says each URL line starts with [<id>]",
)
def test_per_account_url_lines_start_with_the_account_id_in_brackets(
    aws, tmp_path, monkeypatch, capsys
):
    code, _, out = _two_account_google_run(tmp_path, monkeypatch, capsys)
    assert code == 0
    lines = [l for l in out.splitlines() if "docs.google.com" in l]
    assert len(lines) == 4
    assert all(
        l.startswith(f"[{GOOD_ID}]") or l.startswith(f"[{OTHER_ID}]") for l in lines
    )


def test_no_resources_means_no_google_file(aws, tmp_path, monkeypatch, capsys):
    go, log = _fake_google(monkeypatch)
    monkeypatch.setattr(
        cbg_module().CloudBOMGenerator,
        "_discover_account_resources_inner",
        lambda self, account_id, context: [],
    )
    code = run_cli(
        "--create-google-sheets",
        "--create-google-docs",
        "--account-regions",
        "us-east-1",
        "--no-billing-validation",
    )
    assert code == 0
    assert not [n for n, _ in log if n.endswith(".create")]
    assert "docs.google.com" not in capsys.readouterr().out


def test_a_report_too_big_for_google_creates_nothing_exits_1_and_keeps_excel(
    aws, tmp_path, monkeypatch, capsys
):
    go, log = _fake_google(monkeypatch)
    monkeypatch.setattr(go, "MAX_SPREADSHEET_CELLS", 10)
    code = run_cli(
        "--account-regions",
        "us-east-1",
        "--create-excel",
        "--create-google-sheets",
        "--no-billing-validation",
        "--output-directory",
        "out",
    )
    assert code == 1
    assert not [n for n, _ in log if n.endswith(".create")]
    assert len(reports(tmp_path / "out")) == 1
