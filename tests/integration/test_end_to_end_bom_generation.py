#!/usr/bin/env python3
"""
End-to-end integration tests for complete BOM generation workflow

Runs the real pipeline (account context -> discovery result -> BOM processing
-> network/security analysis -> documents -> state snapshot -> delta/changelog)
against moto's in-memory AWS, so no test needs credentials or network access.

Only the resource discovery sweep (AWSResourceInventory) is replaced with a
fixed inventory: it is covered by its own unit tests and would call every
service in every region. The VPC, subnet, security group and bucket in that
inventory really exist in moto, so the analyzers query live (mocked) APIs.
"""

import csv
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws
from openpyxl import load_workbook

from inventag.compliance.checker import ComprehensiveTagComplianceChecker
from inventag.core.cloud_bom_generator import (
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from inventag.discovery.inventory import AWSResourceInventory
from inventag.discovery.service_enrichment import ServiceAttributeEnricher
from inventag.reporting.bom_processor import (
    BOMData,
    BOMDataProcessor,
    BOMProcessingConfig,
)
from inventag.reporting.document_generator import (
    BrandingConfig,
    DocumentConfig,
    DocumentGenerator,
)

ACCOUNT_ID = "123456789012"  # moto's default account
REGION = "us-east-1"


@pytest.fixture
def aws(monkeypatch):
    """In-memory AWS (moto) with fake credentials."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-tests-only")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        yield boto3.Session(region_name=REGION)


@pytest.fixture
def infrastructure(aws):
    """A small VPC with one subnet, one web security group and one bucket."""
    ec2 = aws.client("ec2", region_name=REGION)
    vpc_id = ec2.create_vpc(
        CidrBlock="10.20.0.0/16",
        TagSpecifications=[
            {"ResourceType": "vpc", "Tags": [{"Key": "Name", "Value": "prod-vpc"}]}
        ],
    )["Vpc"]["VpcId"]
    subnet_id = ec2.create_subnet(
        VpcId=vpc_id, CidrBlock="10.20.1.0/24", AvailabilityZone=f"{REGION}a"
    )["Subnet"]["SubnetId"]
    sg_id = ec2.create_security_group(
        GroupName="web-sg", Description="Web tier", VpcId=vpc_id
    )["GroupId"]
    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [
                    {"CidrIp": "0.0.0.0/0", "Description": "SSH from anywhere"}
                ],
            }
        ],
    )
    aws.client("s3", region_name=REGION).create_bucket(Bucket="prod-reports-bucket")

    return {"vpc_id": vpc_id, "subnet_id": subnet_id, "sg_id": sg_id}


@pytest.fixture
def inventory(infrastructure):
    """Discovery output (the shape AWSResourceInventory returns) for the account."""
    vpc_id = infrastructure["vpc_id"]
    subnet_id = infrastructure["subnet_id"]
    sg_id = infrastructure["sg_id"]
    return [
        {
            "service": "EC2",
            "type": "Instance",
            "region": REGION,
            "id": "i-0abc1234def567890",
            "name": "web-server-01",
            "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT_ID}:instance/i-0abc1234def567890",
            "account_id": ACCOUNT_ID,
            "tags": {"Name": "web-server-01", "Environment": "production"},
            "instance_type": "t3.micro",
            "state": "running",
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "security_groups": [sg_id],
        },
        {
            "service": "EC2",
            "type": "VPC",
            "region": REGION,
            "id": vpc_id,
            "name": "prod-vpc",
            "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT_ID}:vpc/{vpc_id}",
            "account_id": ACCOUNT_ID,
            "tags": {"Name": "prod-vpc"},
        },
        {
            "service": "EC2",
            "type": "Subnet",
            "region": REGION,
            "id": subnet_id,
            "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT_ID}:subnet/{subnet_id}",
            "account_id": ACCOUNT_ID,
            "vpc_id": vpc_id,
            "tags": {},
        },
        {
            "service": "EC2",
            "type": "SecurityGroup",
            "region": REGION,
            "id": sg_id,
            "name": "web-sg",
            "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT_ID}:security-group/{sg_id}",
            "account_id": ACCOUNT_ID,
            "vpc_id": vpc_id,
            "tags": {},
        },
        {
            "service": "S3",
            "type": "Bucket",
            "region": REGION,
            "id": "prod-reports-bucket",
            "name": "prod-reports-bucket",
            "arn": "arn:aws:s3:::prod-reports-bucket",
            "account_id": ACCOUNT_ID,
            "tags": {"Environment": "production", "Owner": "data-team"},
        },
    ]


def _config(output_dir, **overrides) -> MultiAccountConfig:
    settings = dict(
        accounts=[
            AccountCredentials(
                account_id=ACCOUNT_ID,
                account_name="Production",
                access_key_id="AKIAIOSFODNN7EXAMPLE",
                secret_access_key="fake-secret-for-tests-only",
                regions=[REGION],
            )
        ],
        output_directory=str(output_dir),
        parallel_account_processing=False,
    )
    settings.update(overrides)
    return MultiAccountConfig(**settings)


def _patched_discovery(resources):
    """Replace the discovery sweep; each call returns fresh copies."""
    patcher = patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", autospec=True
    )
    mock_class = patcher.start()
    mock_class.return_value.discover_all_resources.side_effect = lambda: [
        json.loads(json.dumps(r)) for r in resources
    ]
    return patcher, mock_class


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _only(files, suffix):
    matches = [f for f in files if f.endswith(suffix)]
    assert len(matches) == 1, f"expected one {suffix} file in {files}"
    return matches[0]


class TestEndToEndBOMGeneration:
    """Integration tests for complete BOM generation workflow."""

    def test_public_api_names(self):
        """The classes the workflow is built from keep their import paths."""
        assert callable(AWSResourceInventory.discover_all_resources)
        assert callable(ComprehensiveTagComplianceChecker.check_compliance)

    def test_complete_bom_generation_workflow(self, inventory, tmp_path):
        """Discovery result -> Excel + CSV + JSON documents -> state snapshot."""
        output_dir = tmp_path / "bom_output"
        patcher, inventory_class = _patched_discovery(inventory)
        try:
            generator = CloudBOMGenerator(_config(output_dir))
            result = generator.generate_multi_account_bom(
                output_formats=["excel", "csv", "json"]
            )
        finally:
            patcher.stop()

        assert result["success"] is True, result.get("error")
        stats = result["processing_statistics"]
        assert stats["total_accounts"] == 1
        assert stats["successful_accounts"] == 1
        assert stats["failed_accounts"] == 0
        assert stats["total_resources"] == 5

        # Discovery was asked for exactly the configured account and region
        _, kwargs = inventory_class.call_args
        assert kwargs["regions"] == [REGION]
        assert kwargs["services"] is None
        assert kwargs["enable_billing_validation"] is True

        context = result["account_contexts"][ACCOUNT_ID]
        assert context["account_name"] == "Production"
        assert context["resource_count"] == 5
        assert context["accessible_regions"] == [REGION]
        assert sorted(context["discovered_services"]) == ["EC2", "S3"]
        assert context["error_count"] == 0

        bom = result["bom_generation"]
        assert bom["success"] is True
        assert bom["processing_statistics"]["processed_resources"] == 5
        files = bom["generated_files"]
        assert len(files) == 3
        for name in files:
            assert Path(name).parent == output_dir
            assert Path(name).stat().st_size > 0

        # Excel: summary + one sheet per service, VPC resources reclassified
        workbook = load_workbook(_only(files, ".xlsx"))
        assert workbook.sheetnames[0] == "Summary"
        summary = {
            row[0]: row[1]
            for row in workbook["Summary"].iter_rows(min_row=2, values_only=True)
        }
        assert summary == {"EC2": 1, "S3": 1, "VPC": 3, "TOTAL": 5}

        # CSV: one row per resource, labelled with the source account
        rows = _read_csv(_only(files, ".csv"))
        assert len(rows) == 5
        assert {row["source_account_id"] for row in rows} == {ACCOUNT_ID}
        assert {row["source_account_name"] for row in rows} == {"Production"}
        instance = next(row for row in rows if row["type"] == "Instance")
        assert instance["id"] == "i-0abc1234def567890"
        assert instance["tags.Environment"] == "production"

        # JSON: analysis sections are plain, serialisable dictionaries
        with open(_only(files, ".json")) as handle:
            document = json.load(handle)
        assert len(document["resources"]) == 5
        assert document["metadata"]["multi_account_generation"] is True
        assert document["network_analysis"]["total_vpcs"] >= 1
        assert document["security_analysis"]["total_security_groups"] >= 1

        # First run: a snapshot is saved, there is nothing to compare with yet
        state = result["state_management"]
        assert state["state_saved"] is True
        assert state["delta_detection"]["changes_detected"] is False
        state_file = output_dir / "state" / f"state_{state['state_id']}.json"
        with open(state_file) as handle:
            snapshot = json.load(handle)
        assert snapshot["metadata"]["account_id"] == ACCOUNT_ID
        assert snapshot["metadata"]["resource_count"] == 5
        assert len(snapshot["resources"]) == 5

    def test_second_run_reports_only_real_changes(self, inventory, tmp_path):
        """A second run is compared with the previous snapshot, not with itself."""
        output_dir = tmp_path / "bom_output"
        config = _config(output_dir)
        patcher, _ = _patched_discovery(inventory)
        try:
            first = CloudBOMGenerator(config).generate_multi_account_bom(
                output_formats=["json"]
            )

            # Between runs: one bucket is created and the instance is resized
            inventory.append(
                {
                    "service": "S3",
                    "type": "Bucket",
                    "region": REGION,
                    "id": "prod-archive-bucket",
                    "name": "prod-archive-bucket",
                    "arn": "arn:aws:s3:::prod-archive-bucket",
                    "account_id": ACCOUNT_ID,
                    "tags": {},
                }
            )
            inventory[0]["instance_type"] = "t3.large"
            time.sleep(1.1)  # state IDs have one-second resolution

            second = CloudBOMGenerator(config).generate_multi_account_bom(
                output_formats=["json"]
            )
        finally:
            patcher.stop()

        assert first["success"] is True and second["success"] is True
        first_id = first["state_management"]["state_id"]
        second_id = second["state_management"]["state_id"]
        assert first_id != second_id

        delta = second["state_management"]["delta_detection"]
        assert delta["changes_detected"] is True
        assert delta["previous_state_id"] == first_id
        assert delta["current_state_id"] == second_id

        report = delta["summary"]
        assert report.summary["total_resources_old"] == 5
        assert report.summary["total_resources_new"] == 6
        assert report.summary["added_count"] == 1
        assert report.summary["removed_count"] == 0
        # Only the resized instance is modified: per-run timestamps are ignored
        assert report.summary["modified_count"] == 1
        assert report.summary["unchanged_count"] == 4
        assert [c.resource_id for c in report.added_resources] == [
            "prod-archive-bucket"
        ]
        (modified,) = report.modified_resources
        assert modified.resource_id == "i-0abc1234def567890"
        assert [c.attribute_path for c in modified.attribute_changes] == [
            "instance_type"
        ]
        assert report.change_statistics["service_statistics"]["S3"]["added"] == 1

        # Changelog is written next to the reports
        assert second["state_management"]["changelog_generated"] is True
        changelog = Path(second["state_management"]["changelog_file"]).read_text()
        assert "Multi-Account Infrastructure Changes" in changelog
        assert "prod-archive-bucket" in changelog

    def test_bom_generation_with_network_analysis(self, aws, infrastructure, inventory):
        """Network analysis reads the VPC and subnet and returns a dictionary."""
        config = BOMProcessingConfig(
            enable_security_analysis=False,
            enable_service_enrichment=False,
            enable_parallel_processing=False,
        )
        processor = BOMDataProcessor(config, aws)

        result = processor.process_inventory_data(inventory)

        assert isinstance(result, BOMData)
        assert result.error_summary["has_errors"] is False
        network = result.network_analysis
        assert isinstance(network, dict)
        # moto also has a default VPC in the region
        assert network["total_vpcs"] >= 1
        assert network["total_subnets"] >= 1

        vpc = network["vpc_utilization"][infrastructure["vpc_id"]]
        assert vpc["name"] == "prod-vpc"
        assert vpc["cidr_block"] == "10.20.0.0/16"
        assert vpc["available_ips"] > 0
        assert 0.0 <= vpc["utilization_percentage"] <= 100.0
        assert infrastructure["vpc_id"] in network["vpc_utilization_stats"]
        json.dumps(network)  # must be serialisable for the JSON report

    def test_bom_generation_with_security_analysis(
        self, aws, infrastructure, inventory
    ):
        """SSH open to the internet is reported as an overly permissive rule."""
        config = BOMProcessingConfig(
            enable_network_analysis=False,
            enable_service_enrichment=False,
            enable_parallel_processing=False,
        )
        processor = BOMDataProcessor(config, aws)

        result = processor.process_inventory_data(inventory)

        assert result.error_summary["has_errors"] is False
        security = result.security_analysis
        assert isinstance(security, dict)
        assert security["total_security_groups"] >= 1

        sg_id = infrastructure["sg_id"]
        ssh_rules = [
            rule
            for rule in security["overly_permissive_rules"]
            if rule["group_id"] == sg_id and rule["rule_type"] == "inbound"
        ]
        assert len(ssh_rules) == 1
        (ssh_rule,) = ssh_rules
        assert ssh_rule["rule"] == "inbound tcp 22 0.0.0.0/0"
        assert ssh_rule["common_service"] == "SSH"
        assert ssh_rule["risk_level"] in ("high", "critical")

        assert security["overly_permissive_rule_count"] == len(
            security["overly_permissive_rules"]
        )
        assert security["high_risk_rules"] >= 1
        json.dumps(security)

    def test_bom_generation_with_service_enrichment(self, aws, inventory):
        """Service enrichment adds S3 attributes read from the (mocked) S3 API."""
        s3 = aws.client("s3", region_name=REGION)
        s3.put_bucket_versioning(
            Bucket="prod-reports-bucket", VersioningConfiguration={"Status": "Enabled"}
        )
        bucket = next(r for r in inventory if r["service"] == "S3")

        enricher = ServiceAttributeEnricher(aws)
        (enriched,) = enricher.enrich_resources_with_attributes([bucket])

        assert enriched["id"] == "prod-reports-bucket"
        assert enriched["service_attributes"]["versioning_status"] == "Enabled"
        assert enriched["enrichment_metadata"]["handler_type"] == "S3Handler"
        # Enrichment only reads
        operations = enriched["enrichment_metadata"]["read_only_operations"]
        assert operations
        for operation in operations:
            assert operation.startswith(("get_", "list_", "describe_", "head_"))
        # The input resource is not modified
        assert "service_attributes" not in bucket

        # The enriched resource still flows through BOM processing unchanged
        config = BOMProcessingConfig(
            enable_network_analysis=False,
            enable_security_analysis=False,
            enable_service_enrichment=False,
            enable_parallel_processing=False,
        )
        result = BOMDataProcessor(config, aws).process_inventory_data([enriched])
        (processed,) = result.resources
        assert processed["service_attributes"]["versioning_status"] == "Enabled"
        assert result.processing_statistics["processed_resources"] == 1

    @pytest.mark.parametrize("parallel", [False, True])
    def test_bom_generation_error_handling(self, aws, inventory, tmp_path, parallel):
        """When no account can be scanned the run fails and writes no report."""
        output_dir = tmp_path / "bom_output"
        patcher, inventory_class = _patched_discovery(inventory)
        inventory_class.return_value.discover_all_resources.side_effect = RuntimeError(
            "Discovery failed: AccessDenied on tag:GetResources"
        )
        try:
            generator = CloudBOMGenerator(
                _config(output_dir, parallel_account_processing=parallel)
            )
            result = generator.generate_multi_account_bom(output_formats=["csv"])
        finally:
            patcher.stop()

        assert result["success"] is False
        assert "failed for all 1 configured account(s)" in result["error"]
        stats = result["processing_statistics"]
        assert stats["successful_accounts"] == 0
        assert stats["failed_accounts"] == 1

        context = generator.account_contexts[ACCOUNT_ID]
        assert any("Discovery failed" in error for error in context.processing_errors)
        assert result["account_contexts"][ACCOUNT_ID]["error_count"] >= 1

        # No report and no state snapshot: an empty snapshot would make the
        # next run report every resource as newly added.
        assert "bom_generation" not in result
        assert list(output_dir.glob("multi_account_bom_*")) == []
        assert not (output_dir / "state").exists()

    def test_partial_account_failure_still_reports(self, aws, inventory, tmp_path):
        """One unusable account does not stop the report for the others."""
        config = _config(tmp_path / "bom_output")
        config.accounts.append(
            AccountCredentials(
                account_id="999999999999",
                account_name="Wrong account",
                access_key_id="AKIAIOSFODNN7EXAMPLE",
                secret_access_key="fake-secret-for-tests-only",
                regions=[REGION],
            )
        )
        patcher, _ = _patched_discovery(inventory)
        try:
            generator = CloudBOMGenerator(config)
            result = generator.generate_multi_account_bom(output_formats=["csv"])
        finally:
            patcher.stop()

        assert result["success"] is True
        stats = result["processing_statistics"]
        assert stats["total_accounts"] == 2
        assert stats["successful_accounts"] == 1
        assert stats["failed_accounts"] == 1
        assert result["account_contexts"]["999999999999"]["error_count"] == 1
        rows = _read_csv(_only(result["bom_generation"]["generated_files"], ".csv"))
        assert len(rows) == 5
        assert {row["source_account_id"] for row in rows} == {ACCOUNT_ID}

    def test_wrong_account_is_refused(self, aws, inventory, tmp_path):
        """Credentials that resolve to another account must not be scanned."""
        config = _config(tmp_path / "bom_output")
        config.accounts[0].account_id = "999999999999"
        patcher, inventory_class = _patched_discovery(inventory)
        try:
            generator = CloudBOMGenerator(config)
            result = generator.generate_multi_account_bom(output_formats=["csv"])
        finally:
            patcher.stop()

        inventory_class.assert_not_called()
        assert result["success"] is False
        assert result["processing_statistics"]["failed_accounts"] == 1
        errors = generator.account_contexts["999999999999"].processing_errors
        assert any("refusing to scan the wrong account" in error for error in errors)

    def test_bom_generation_with_large_dataset(self, aws, tmp_path):
        """1000 resources flow through processing and document generation."""
        large_dataset = [
            {
                "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT_ID}:instance/i-{i:017x}",
                "id": f"i-{i:017x}",
                "service": "EC2",
                "type": "Instance",
                "region": REGION,
                "account_id": ACCOUNT_ID,
                "tags": {"Name": f"instance-{i}", "Environment": "test"},
                "instance_type": "t3.micro",
                "state": "running",
            }
            for i in range(1000)
        ]
        # The same instance reported twice (two discovery paths)
        large_dataset.append(dict(large_dataset[0]))

        config = BOMProcessingConfig(
            enable_network_analysis=False,
            enable_security_analysis=False,
            enable_service_enrichment=False,
        )
        start = time.monotonic()
        processor = BOMDataProcessor(config, aws)
        bom_data = processor.process_inventory_data(large_dataset)
        summary = DocumentGenerator(
            DocumentConfig(output_formats=["csv"], output_directory=str(tmp_path))
        ).generate_bom_documents(bom_data)
        elapsed = time.monotonic() - start

        assert len(bom_data.resources) == 1000  # duplicate removed
        assert bom_data.processing_statistics["total_resources"] == 1001
        assert bom_data.processing_statistics["processed_resources"] == 1000
        assert bom_data.processing_statistics["failed_resources"] == 0
        assert summary.successful_formats == 1
        (result,) = summary.results
        assert len(_read_csv(tmp_path / result.filename)) == 1000
        # Generous bound: catches accidental quadratic behaviour, not jitter
        assert elapsed < 60.0

    def test_multi_format_document_generation(self, aws, inventory, tmp_path):
        """Excel, Word and CSV are generated from the same processed BOM."""
        processor = BOMDataProcessor(
            BOMProcessingConfig(
                enable_service_enrichment=False, enable_parallel_processing=False
            ),
            aws,
        )
        bom_data = processor.process_inventory_data(inventory)
        # The document validator rejects analysis sections that are not dicts
        assert isinstance(bom_data.network_analysis, dict) and bom_data.network_analysis
        assert (
            isinstance(bom_data.security_analysis, dict) and bom_data.security_analysis
        )

        doc_config = DocumentConfig(
            output_formats=["excel", "word", "csv"],
            branding=BrandingConfig(company_name="Test Corp"),
            output_directory=str(tmp_path),
            filename_template="e2e_bom_{timestamp}",
        )
        summary = DocumentGenerator(doc_config).generate_bom_documents(bom_data)

        assert summary.errors == []
        assert summary.total_formats == 3
        assert summary.successful_formats == 3
        assert summary.failed_formats == 0
        by_format = {result.format_type: result for result in summary.results}
        assert set(by_format) == {"excel", "word", "csv"}
        for result in by_format.values():
            assert result.success is True
            assert result.file_size_bytes > 0
            # Results carry the file name; the directory is the configured one
            assert os.path.dirname(result.filename) == ""
            assert (tmp_path / result.filename).is_file()

        assert by_format["excel"].filename.endswith(".xlsx")
        assert by_format["word"].filename.endswith(".docx")
        assert by_format["csv"].filename.endswith(".csv")

        # The analysis sections reach the Excel workbook
        workbook = load_workbook(tmp_path / by_format["excel"].filename)
        assert "Network Analysis" in workbook.sheetnames
        assert "Security Analysis" in workbook.sheetnames


if __name__ == "__main__":
    pytest.main([__file__])
