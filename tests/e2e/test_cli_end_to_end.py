"""End-to-end CLI tests: real ``main()`` against moto, files read back from disk.

Every test here runs a whole scan. Assertions look at what a user gets: the
exit code, the files written, and the rows inside them.
"""

import json

import pytest
from openpyxl import load_workbook

from .conftest import FAST_SCAN

pytestmark = pytest.mark.e2e


def sheet_rows(path, sheet):
    wb = load_workbook(path, read_only=True)
    try:
        rows = list(wb[sheet].iter_rows(values_only=True))
    finally:
        wb.close()
    header = list(rows[0])
    return [dict(zip(header, row)) for row in rows[1:]]


def all_resource_rows(path):
    wb = load_workbook(path, read_only=True)
    try:
        names = [n for n in wb.sheetnames if n.isupper()]
    finally:
        wb.close()
    rows = []
    for name in names:
        rows.extend(sheet_rows(path, name))
    return rows


class TestDefaultRun:
    def test_default_run_writes_one_excel_report_with_the_estate(self, estate, run_cli):
        result = run_cli()

        assert result.code == 0, result.text
        reports = result.files(".xlsx")
        assert len(reports) == 1
        assert result.files(".docx") == []
        rows = all_resource_rows(reports[0])
        ids = " ".join(str(r.get("id")) + " " + str(r.get("arn")) for r in rows)
        for expected in (
            estate["vpc_id"],
            estate["subnet_id"],
            estate["sg_id"],
            estate["bucket"],
            "e2e-queue",
            "e2e-topic",
            estate["table"],
        ):
            assert expected in ids, f"{expected} missing from the report"
        assert {r["service"] for r in rows} >= {"VPC", "S3", "SQS", "SNS", "DYNAMODB"}

    def test_summary_sheet_counts_match_the_resource_sheets(self, estate, run_cli):
        result = run_cli()
        report = result.files(".xlsx")[0]

        summary = {
            row["Service"]: row["Resource Count"]
            for row in sheet_rows(report, "Summary")
            if row["Service"] != "TOTAL"
        }
        per_service = {}
        for row in all_resource_rows(report):
            per_service[row["service"]] = per_service.get(row["service"], 0) + 1
        assert summary == per_service
        assert summary["S3"] == 1

    def test_tags_reach_the_report(self, estate, run_cli):
        result = run_cli()
        rows = all_resource_rows(result.files(".xlsx")[0])
        bucket = next(r for r in rows if r["service"] == "S3")
        flat = json.dumps(bucket, default=str)
        assert "platform" in flat and "prod" in flat

    def test_state_snapshot_is_written_next_to_the_report(self, estate, run_cli):
        result = run_cli()
        state_files = list((result.output_dir / "state").glob("state_*.json"))
        assert len(state_files) == 1
        data = json.loads(state_files[0].read_text())
        assert data["metadata"]["resource_count"] >= 7
        assert data["metadata"]["regions"] == ["us-east-1"]


class TestOutputFormats:
    def test_word_only_writes_a_docx_and_no_xlsx(self, estate, run_cli):
        from docx import Document

        result = run_cli("--create-word")
        assert result.code == 0, result.text
        docs = result.files(".docx")
        assert len(docs) == 1
        assert result.files(".xlsx") == []
        text = "\n".join(p.text for p in Document(str(docs[0])).paragraphs)
        assert "AWS Resource Inventory" in text
        assert "S3 Resources (1)" in text

    def test_word_and_excel_together_hold_the_same_total(self, estate, run_cli):
        from docx import Document

        result = run_cli("--create-word", "--create-excel")
        assert result.code == 0, result.text
        xlsx = result.files(".xlsx")[0]
        docx = result.files(".docx")[0]
        total = len(all_resource_rows(xlsx))
        text = "\n".join(p.text for p in Document(str(docx)).paragraphs)
        assert f"Total Resources: {total}" in text

    def test_service_filter_keeps_only_the_named_service(self, estate, run_cli):
        result = run_cli("--create-excel", "--account-services", "S3")
        assert result.code == 0, result.text
        rows = all_resource_rows(result.files(".xlsx")[0])
        assert rows and {r["service"] for r in rows} == {"S3"}

    def test_no_resources_found_writes_no_report_and_exits_zero(
        self, empty_aws, run_cli
    ):
        result = run_cli("--create-excel", "--account-services", "NOSUCHSERVICE")
        assert result.code == 0, result.text
        assert result.files(".xlsx") == []


class TestAnalysisFlags:
    def test_network_and_security_analysis_add_sheets(self, estate, run_cli):
        result = run_cli("--enable-network-analysis", "--enable-security-analysis")
        assert result.code == 0, result.text
        report = result.files(".xlsx")[0]
        network = sheet_rows(report, "Network Analysis")
        security = sheet_rows(report, "Security Analysis")
        assert network, "network sheet is empty"
        assert any(estate["vpc_id"] in json.dumps(r, default=str) for r in network)
        flat = json.dumps(security, default=str)
        assert estate["sg_id"] in flat
        assert "0.0.0.0/0" in flat

    def test_without_the_flags_there_are_no_analysis_sheets(self, estate, run_cli):
        result = run_cli()
        wb = load_workbook(result.files(".xlsx")[0], read_only=True)
        try:
            assert "Network Analysis" not in wb.sheetnames
            assert "Security Analysis" not in wb.sheetnames
        finally:
            wb.close()

    def test_cost_analysis_runs_offline_and_adds_the_columns(self, estate, run_cli):
        result = run_cli("--enable-cost-analysis")
        # Cost Explorer, Pricing and CloudWatch are not all available in moto.
        # The run must still finish and write the report.
        assert result.code == 0, result.text
        report = result.files(".xlsx")[0]
        rows = all_resource_rows(report)
        assert rows
        assert any(k.startswith("forgotten_analysis") for k in rows[0])

    def test_fallback_display_never_runs(self, estate, run_cli):
        result = run_cli("--fallback-display", "never")
        assert result.code == 0, result.text
        assert result.files(".xlsx")


class TestMultiAccount:
    @pytest.fixture
    def accounts_file(self, tmp_path):
        path = tmp_path / "accounts.json"
        path.write_text(
            json.dumps(
                {
                    "accounts": [
                        {
                            "account_id": "123456789012",
                            "account_name": "prod",
                            "regions": ["us-east-1"],
                        },
                        {
                            "account_id": "210987654321",
                            "account_name": "dev",
                            "regions": ["us-east-1"],
                        },
                    ],
                    "settings": {"max_concurrent_accounts": 1},
                }
            )
        )
        return path

    def test_accounts_file_scans_every_account(self, estate, run_cli, accounts_file):
        result = run_cli(
            "--accounts-file",
            str(accounts_file),
            "--no-billing-validation",
            fast=False,
        )
        assert result.code == 0, result.text
        report = result.files(".xlsx")[0]
        rows = all_resource_rows(report)
        assert rows
        names = {r.get("source_account_name") for r in rows}
        assert "prod" in names

    def test_per_account_reports_write_one_file_per_account(
        self, estate, run_cli, accounts_file
    ):
        result = run_cli(
            "--accounts-file",
            str(accounts_file),
            "--no-billing-validation",
            "--per-account-reports",
            fast=False,
        )
        assert result.code == 0, result.text
        per_account = [p for p in result.files(".xlsx") if "_bom_" in p.name]
        assert any(p.name.startswith("123456789012_bom_") for p in per_account)

    def test_validate_credentials_passes_when_the_id_matches(
        self, estate, run_cli, tmp_path
    ):
        one = tmp_path / "one.json"
        one.write_text(
            json.dumps({"accounts": [{"account_id": "123456789012", "regions": []}]})
        )
        result = run_cli(
            "--accounts-file",
            str(one),
            "--validate-credentials",
            with_output_dir=False,
            fast=False,
        )
        assert result.code == 0, result.text


class TestChangeTracking:
    def test_second_run_reports_the_new_resource_in_the_changelog(
        self, estate, run_cli, tmp_path
    ):
        import boto3

        first = run_cli()
        assert first.code == 0, first.text
        boto3.client("sqs", region_name="us-east-1").create_queue(
            QueueName="added-after-first-scan"
        )
        second = run_cli()
        assert second.code == 0, second.text
        produced = [
            p
            for p in second.output_dir.rglob("*")
            if p.is_file() and "changelog" in p.name.lower()
        ]
        assert produced, sorted(p.name for p in second.output_dir.rglob("*"))
        combined = "\n".join(p.read_text(errors="ignore") for p in produced)
        assert "added-after-first-scan" in combined

    def test_disabling_state_management_writes_no_state_files(self, estate, run_cli):
        result = run_cli("--disable-state-management")
        assert result.code == 0, result.text
        assert not list((result.output_dir / "state").glob("state_*.json"))


class TestAuditOutput:
    def test_audit_file_lists_only_allowed_calls(self, estate, run_cli, tmp_path):
        audit = tmp_path / "audit" / "calls.json"
        result = run_cli("--audit-output", str(audit))
        assert result.code == 0, result.text
        report = json.loads(audit.read_text())
        assert report["read_only_enforced"] is True
        assert report["blocked_calls"] == 0
        assert report["allowed_calls"] > 20
        operations = {(o["service"], o["operation"]) for o in report["operations"]}
        assert ("ec2", "DescribeVpcs") in operations
        assert ("s3", "ListBuckets") in operations
        for service, operation in operations:
            assert operation.startswith(
                ("List", "Describe", "Get", "Head", "Lookup", "Search", "BatchGet")
            ) or (service, operation) == ("sts", "AssumeRole"), (service, operation)
        assert oct(audit.stat().st_mode & 0o777) == "0o600"


class TestExitCodes:
    """The documented codes: 0, 1, 2, 3 and 4 (docs/reference/cli.md)."""

    def test_0_on_success(self, estate, run_cli):
        assert run_cli().code == 0

    def test_1_for_an_accounts_file_that_does_not_exist(self, estate, run_cli):
        result = run_cli("--accounts-file", "/nonexistent/accounts.json")
        assert result.code == 1

    def test_1_for_an_unreadable_config_value(self, estate, run_cli, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        result = run_cli("--accounts-file", str(bad))
        assert result.code == 1

    def test_1_when_every_account_fails(self, estate, run_cli, tmp_path):
        broken = tmp_path / "broken.json"
        broken.write_text(
            json.dumps(
                {
                    "accounts": [
                        {
                            "account_id": "210987654321",
                            "profile_name": "no-such-profile",
                            "regions": ["us-east-1"],
                        }
                    ]
                }
            )
        )
        result = run_cli(
            "--accounts-file", str(broken), "--no-billing-validation", fast=False
        )
        assert result.code == 1, result.text
        assert result.files(".xlsx") == []

    def test_1_when_the_s3_upload_fails(self, estate, run_cli):
        result = run_cli("--s3-bucket", "bucket-that-does-not-exist")
        assert result.code == 1, result.text
        assert "upload" in result.text.lower()

    def test_2_for_a_role_name_without_an_accounts_file(self, empty_aws, run_cli):
        result = run_cli("--cross-account-role", "MyRole", with_output_dir=False)
        assert result.code == 2, result.text

    def test_2_for_compliance_standard(self, run_cli):
        result = run_cli("--compliance-standard", "soc2", with_output_dir=False)
        assert result.code == 2
        assert "not implemented" in result.stderr

    def test_2_for_disabling_the_guard(self, run_cli):
        result = run_cli("--disable-production-safety", with_output_dir=False)
        assert result.code == 2
        assert "cannot be disabled" in result.stderr

    def test_2_for_risk_threshold_without_security_analysis(self, run_cli):
        result = run_cli("--risk-threshold", "HIGH", with_output_dir=False)
        assert result.code == 2

    def test_2_for_unknown_option(self, run_cli):
        result = run_cli("--no-such-flag", with_output_dir=False)
        assert result.code == 2

    def test_3_when_the_tag_policy_in_ci_pipeline_is_violated(self, estate, run_cli):
        result = run_cli("--template", "ci-pipeline")
        assert result.code == 3, result.text
        assert result.files(".xlsx")

    def test_4_when_a_rule_reaches_the_risk_threshold(self, estate, run_cli):
        result = run_cli("--enable-security-analysis", "--risk-threshold", "HIGH")
        assert result.code == 4, result.text
        assert result.files(".xlsx"), "reports are written before the exit code"
        assert estate["sg_id"] in result.text

    def test_0_when_no_rule_reaches_a_threshold_above_every_finding(
        self, empty_aws, run_cli
    ):
        result = run_cli("--enable-security-analysis", "--risk-threshold", "CRITICAL")
        assert result.code == 0, result.text


def test_fast_scan_constant_limits_the_scan_to_one_region():
    assert "us-east-1" in FAST_SCAN and "--no-billing-validation" in FAST_SCAN
