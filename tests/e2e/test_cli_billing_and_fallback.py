"""Billing validation (Cost Explorer) and Resource Groups Tagging API fallback, end to end.

Both are on by default and neither had a test that ran the whole CLI:
the first needs Cost Explorer answers, the second needs a service that
InvenTag has no discovery code for.
"""

import json

import boto3
import pytest
import requests

from .test_cli_end_to_end import all_resource_rows

pytestmark = pytest.mark.e2e

SECRET_VALUE = "TOPSECRET-VALUE-123"
ONE_REGION = ["--account-regions", "us-east-1"]  # billing validation stays on


def queue_cost_explorer_answer(*services):
    """Tell moto what the next ``GetCostAndUsage`` call returns: (service, dollars)."""
    groups = [
        {
            "Keys": [name],
            "Metrics": {
                "BlendedCost": {"Amount": str(cost), "Unit": "USD"},
                "UsageQuantity": {"Amount": "5", "Unit": "N/A"},
            },
        }
        for name, cost in services
    ]
    answer = {
        "results": [
            {
                "ResultsByTime": [
                    {
                        "TimePeriod": {"Start": "2026-10-01", "End": "2026-11-01"},
                        "Total": {},
                        "Groups": groups,
                        "Estimated": False,
                    }
                ],
                "DimensionValueAttributes": [],
            }
        ]
    }
    response = requests.post(
        "http://motoapi.amazonaws.com/moto-api/static/ce/cost-and-usage-results",
        json=answer,
    )
    assert response.status_code == 201


def audit_operations(path):
    report = json.loads(path.read_text())
    return {(o["service"], o["operation"]): o["count"] for o in report["operations"]}


class TestBillingValidation:
    def test_billed_services_are_marked_and_bill_only_services_are_added(
        self, estate, run_cli
    ):
        queue_cost_explorer_answer(
            ("Amazon Simple Storage Service", 1.5),
            ("Amazon Kinesis", 2.0),
            ("Tax", 0.3),
        )

        result = run_cli("--billing-validation", *ONE_REGION, fast=False)
        assert result.code == 0, result.text
        rows = all_resource_rows(result.files(".xlsx")[0])

        bucket = next(r for r in rows if r["service"] == "S3")
        assert bucket["billing_validated"] == "True"
        assert float(bucket["service_monthly_spend"]) == pytest.approx(1.5)
        queue = next(r for r in rows if r["service"] == "SQS")
        assert queue["billing_validated"] == "False"
        kinesis = [r for r in rows if r["service"] == "KINESIS"]
        assert (
            len(kinesis) == 1
        ), "a service on the bill with no resources is listed once"
        assert kinesis[0]["priority"] == "fallback"
        assert kinesis[0]["billing_validated"] == "True"
        assert not [r for r in rows if r["service"] == "TAX"]

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "DEFECT (P2): the report has two spend columns. service_monthly_spend "
            "(inventory.py:1236) carries the billed amount; monthly_spend "
            "(comprehensive_discovery.py:1310) is 0.0 for every row because it "
            "reads self.billing_spend, which is empty when the Cost Explorer "
            "query runs in AWSResourceInventory instead. A user who reads "
            "monthly_spend sees $0 for a billed service."
        ),
    )
    def test_monthly_spend_column_matches_the_billed_amount(self, estate, run_cli):
        queue_cost_explorer_answer(("Amazon Simple Storage Service", 1.5))
        result = run_cli("--billing-validation", *ONE_REGION, fast=False)
        rows = all_resource_rows(result.files(".xlsx")[0])
        bucket = next(r for r in rows if r["service"] == "S3")
        assert float(bucket["monthly_spend"]) == pytest.approx(1.5)

    def test_default_run_calls_cost_explorer_and_no_billing_flag_does_not(
        self, estate, run_cli, tmp_path
    ):
        with_billing = tmp_path / "with.json"
        without = tmp_path / "without.json"
        queue_cost_explorer_answer(("Amazon Simple Storage Service", 1.5))

        first = run_cli("--audit-output", str(with_billing), *ONE_REGION, fast=False)
        assert first.code == 0, first.text
        calls = audit_operations(with_billing)
        assert calls.get(("ce", "GetCostAndUsage"), 0) >= 1

        second = run_cli(
            "--audit-output",
            str(without),
            "--no-billing-validation",
            *ONE_REGION,
            fast=False,
        )
        assert second.code == 0, second.text
        assert [k for k in audit_operations(without) if k[0] == "ce"] == []


class TestTaggingApiFallback:
    @pytest.fixture
    def secret(self, estate):
        boto3.client("secretsmanager", region_name="us-east-1").create_secret(
            Name="e2e-secret",
            SecretString=SECRET_VALUE,
            Tags=[{"Key": "Owner", "Value": "platform"}],
        )

    def services(self, result):
        rows = all_resource_rows(result.files(".xlsx")[0])
        return {(r["service"], r["priority"]) for r in rows}

    def test_a_service_without_discovery_code_appears_through_the_tagging_api(
        self, secret, run_cli
    ):
        result = run_cli()
        assert result.code == 0, result.text
        assert ("SECRETSMANAGER", "fallback") in self.services(result)

    def test_fallback_display_never_hides_it(self, secret, run_cli):
        result = run_cli("--fallback-display", "never")
        assert result.code == 0, result.text
        assert not [s for s in self.services(result) if s[1] == "fallback"]

    def test_the_secret_value_is_never_read_or_written_anywhere(
        self, secret, run_cli, tmp_path
    ):
        audit = tmp_path / "audit.json"
        result = run_cli("--audit-output", str(audit), "--create-word")
        assert result.code == 0, result.text

        assert [k for k in audit_operations(audit) if k[0] == "secretsmanager"] == []
        produced = [p for p in result.output_dir.rglob("*") if p.is_file()]
        assert produced
        for path in produced:
            if path.suffix in (".xlsx", ".docx"):
                import zipfile

                with zipfile.ZipFile(path) as archive:
                    content = b"".join(archive.read(n) for n in archive.namelist())
            else:
                content = path.read_bytes()
            assert SECRET_VALUE.encode() not in content, path.name
        assert SECRET_VALUE not in result.text
