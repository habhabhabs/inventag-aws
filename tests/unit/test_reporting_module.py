#!/usr/bin/env python3
"""
Unit Tests for inventag.reporting Module

Unit tests for BOMConverter (inventag/reporting/converter.py): loading the
inventory and compliance input formats, the standardisation pipeline that
load_data runs, CSV and Excel export, VPC/subnet name enrichment and error
handling.

The exports are written to a temporary directory and read back (csv module,
openpyxl), so the tests assert what a user would find in the files. No test
reaches AWS: enrichment tests use a mocked boto3 session.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import csv
import json
import os
import stat
import sys
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from openpyxl import load_workbook

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from inventag.reporting import BOMConverter  # noqa: E402


# --------------------------------------------------------------- fixtures
@pytest.fixture
def sample_inventory_data() -> List[Dict[str, Any]]:
    """Sample inventory data in the shape the discovery module produces"""
    return [
        {
            "service": "S3",
            "type": "Bucket",
            "region": "us-east-1",
            "id": "example-bucket",
            "name": "example-bucket",
            "arn": "arn:aws:s3:::example-bucket",
            "account_id": "123456789012",
            "tags": {"Environment": "production", "Owner": "data-team"},
            "discovered_via": "ResourceGroupsTaggingAPI",
        },
        {
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "id": "i-1234567890abcdef0",
            "name": "web-server-01",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "account_id": "123456789012",
            "tags": {
                "Name": "web-server-01",
                "Environment": "production",
                "Role": "webserver",
            },
            "discovered_via": "EC2API",
        },
        {
            "service": "RDS",
            "type": "DBInstance",
            "region": "us-west-2",
            "id": "prod-database",
            "name": "prod-database",
            "arn": "arn:aws:rds:us-west-2:123456789012:db:prod-database",
            "account_id": "123456789012",
            "tags": {
                "Environment": "production",
                "Role": "database",
                "Owner": "backend-team",
            },
            "discovered_via": "RDSAPI",
        },
    ]


@pytest.fixture
def sample_compliance_data() -> Dict[str, Any]:
    """Sample tag compliance report (output of the compliance checker)"""
    return {
        "summary": {
            "total_resources": 3,
            "compliant_resources": 2,
            "non_compliant_resources": 1,
            "untagged_resources": 0,
            "compliance_percentage": 66.67,
        },
        "compliant_resources": [
            {
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "id": "i-1234567890abcdef0",
                "name": "web-server-01",
                "tags": {
                    "Name": "web-server-01",
                    "Environment": "production",
                    "Role": "webserver",
                },
                "compliance_status": "compliant",
            },
            {
                "service": "RDS",
                "type": "DBInstance",
                "region": "us-west-2",
                "id": "prod-database",
                "name": "prod-database",
                "tags": {
                    "Environment": "production",
                    "Role": "database",
                    "Owner": "backend-team",
                },
                "compliance_status": "compliant",
            },
        ],
        "non_compliant_resources": [
            {
                "service": "S3",
                "type": "Bucket",
                "region": "us-east-1",
                "id": "example-bucket",
                "name": "example-bucket",
                "tags": {"Environment": "production", "Owner": "data-team"},
                "compliance_status": "non_compliant",
                "violations": ["Missing required tag: Role"],
            }
        ],
        "untagged_resources": [],
    }


@pytest.fixture
def loaded_converter(sample_inventory_data):
    """Converter with data assigned directly (no file, no AWS session)"""
    converter = BOMConverter(enrich_vpc_info=False)
    converter.data = sample_inventory_data
    return converter


def _write_json(tmp_path, payload, name="input.json") -> str:
    path = tmp_path / name
    path.write_text(json.dumps(payload))
    return str(path)


def _read_csv(path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _summary_rows(workbook) -> Dict[str, Any]:
    """Return the Summary sheet as {service: resource count}."""
    rows = list(workbook["Summary"].iter_rows(min_row=2, values_only=True))
    return {row[0]: row[1] for row in rows}


def _sheet_records(worksheet) -> List[Dict[str, Any]]:
    rows = list(worksheet.iter_rows(values_only=True))
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]


# ------------------------------------------------------------------ core
class TestBOMConverterCore:
    """Test core functionality of BOMConverter"""

    def test_initialization_default(self):
        """Test default initialization"""
        converter = BOMConverter()
        assert converter.enrich_vpc_info is True
        assert converter.enable_advanced_analysis is False
        assert converter.data == []
        assert converter.session is not None

    def test_initialization_no_vpc_enrichment(self):
        """Without VPC enrichment no boto3 session is created"""
        converter = BOMConverter(enrich_vpc_info=False)
        assert converter.enrich_vpc_info is False
        assert converter.session is None

    def test_load_data_json_inventory(self, tmp_path, sample_inventory_data):
        """Test loading JSON inventory data"""
        input_file = _write_json(
            tmp_path, {"all_discovered_resources": sample_inventory_data}
        )

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(input_file)

        assert isinstance(data, list)
        assert [r["service"] for r in data] == ["S3", "EC2", "RDS"]
        assert converter.data is data

    def test_load_data_json_compliance(self, tmp_path, sample_compliance_data):
        """A compliance report contributes all of its resource arrays"""
        input_file = _write_json(tmp_path, sample_compliance_data)

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(input_file)

        assert len(data) == 3  # 2 compliant + 1 non-compliant + 0 untagged
        statuses = sorted(r["compliance_status"] for r in data)
        assert statuses == ["compliant", "compliant", "non_compliant"]

    def test_load_data_direct_list(self, tmp_path, sample_inventory_data):
        """Test loading data that's already a list"""
        input_file = _write_json(tmp_path, sample_inventory_data)

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(input_file)

        assert isinstance(data, list)
        assert len(data) == 3

    def test_load_data_yaml(self, tmp_path, sample_inventory_data):
        """YAML input is parsed with the safe loader"""
        import yaml

        path = tmp_path / "inventory.yaml"
        path.write_text(
            yaml.safe_dump({"all_discovered_resources": sample_inventory_data})
        )

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(str(path))

        assert [r["id"] for r in data] == [
            "example-bucket",
            "i-1234567890abcdef0",
            "prod-database",
        ]

    def test_load_data_collects_flattened_headers(
        self, tmp_path, sample_inventory_data
    ):
        """Nested keys (tags) are collected as dotted headers"""
        input_file = _write_json(tmp_path, sample_inventory_data)

        converter = BOMConverter(enrich_vpc_info=False)
        converter.load_data(input_file)

        assert {"service", "type", "id", "arn", "tags.Environment", "tags.Owner"} <= (
            converter.headers
        )
        assert "tags" not in converter.headers

    def test_load_data_nonexistent_file(self, tmp_path):
        """Test loading non-existent file"""
        converter = BOMConverter(enrich_vpc_info=False)
        with pytest.raises(FileNotFoundError):
            converter.load_data(str(tmp_path / "nonexistent_file.json"))

    def test_load_data_invalid_json(self, tmp_path):
        """Test loading invalid JSON file"""
        path = tmp_path / "broken.json"
        path.write_text('{"invalid": json content}')

        converter = BOMConverter(enrich_vpc_info=False)
        with pytest.raises(json.JSONDecodeError):
            converter.load_data(str(path))


# ------------------------------------------------------------ processing
class TestDataProcessing:
    """Test the standardisation pipeline that load_data runs"""

    def test_vpc_resources_are_reclassified(self, tmp_path):
        """EC2-namespace network resources move to the VPC service"""
        resources = [
            {
                "service": "EC2",
                "type": "Instance",
                "region": "ap-southeast-1",
                "id": "i-0abc1234def567890",
                "arn": "arn:aws:ec2:ap-southeast-1:123456789012:instance/i-0abc1234def567890",
            },
            {
                "service": "EC2",
                "type": "SecurityGroup",
                "region": "ap-southeast-1",
                "id": "sg-0a1b2c3d4e5f67890",
                "arn": "arn:aws:ec2:ap-southeast-1:123456789012:security-group/sg-0a1b2c3d4e5f67890",
            },
            {
                "service": "EC2",
                "type": "Subnet",
                "region": "ap-southeast-1",
                "id": "subnet-0a1b2c3d4e5f67890",
                "arn": "arn:aws:ec2:ap-southeast-1:123456789012:subnet/subnet-0a1b2c3d4e5f67890",
            },
        ]
        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(_write_json(tmp_path, resources))

        by_type = {r["type"]: r["service"] for r in data}
        assert by_type == {"Instance": "EC2", "SecurityGroup": "VPC", "Subnet": "VPC"}

    def test_service_names_are_standardized(self, tmp_path):
        """Mixed-case service names collapse to one spelling"""
        resources = [
            {
                "service": "Lambda",
                "type": "Function",
                "region": "us-east-1",
                "id": "orders-handler",
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:orders-handler",
            },
            {
                "service": "CloudFormation",
                "type": "Stack",
                "region": "us-east-1",
                "id": "network-stack",
                "arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/network-stack/abc",
            },
        ]
        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(_write_json(tmp_path, resources))

        assert [r["service"] for r in data] == ["LAMBDA", "CLOUDFORMATION"]

    def test_duplicates_are_removed_by_arn(self, tmp_path, sample_inventory_data):
        """The same ARN reported by two discovery paths is kept once"""
        duplicate = dict(sample_inventory_data[0], discovered_via="S3API")
        input_file = _write_json(tmp_path, sample_inventory_data + [duplicate])

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(input_file)

        assert len(data) == 3
        s3 = [r for r in data if r["service"] == "S3"]
        assert len(s3) == 1
        # The first occurrence wins
        assert s3[0]["discovered_via"] == "ResourceGroupsTaggingAPI"

    def test_duplicates_without_arn_use_service_id_region(self, tmp_path):
        """Without an ARN the key is service + id + region"""
        resources = [
            {
                "service": "EC2",
                "type": "Instance",
                "id": "i-0123",
                "region": "us-east-1",
            },
            {
                "service": "EC2",
                "type": "Instance",
                "id": "i-0123",
                "region": "us-east-1",
            },
            {
                "service": "EC2",
                "type": "Instance",
                "id": "i-0123",
                "region": "us-west-2",
            },
        ]
        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(_write_json(tmp_path, resources))

        assert [r["region"] for r in data] == ["us-east-1", "us-west-2"]

    def test_get_tag_value(self):
        """Tag lookup on AWS-format tag lists ([{'Key': ..., 'Value': ...}])"""
        converter = BOMConverter(enrich_vpc_info=False)
        tags = [
            {"Key": "Environment", "Value": "production"},
            {"Key": "Owner", "Value": "team-a"},
        ]

        assert converter._get_tag_value(tags, "Environment") == "production"
        assert converter._get_tag_value(tags, "Owner") == "team-a"
        assert converter._get_tag_value(tags, "NonExistent") is None

    def test_get_tag_value_empty_tags(self):
        """Tag lookup with empty/None tags (untagged resources omit 'Tags')"""
        converter = BOMConverter(enrich_vpc_info=False)

        assert converter._get_tag_value([], "Environment") is None
        assert converter._get_tag_value(None, "Environment") is None

    def test_flatten_dict(self):
        """Nested dicts become dotted keys; lists become comma-separated text"""
        converter = BOMConverter(enrich_vpc_info=False)
        flattened = converter._flatten_dict(
            {
                "id": "i-1234567890abcdef0",
                "tags": {"Environment": "production"},
                "security_groups": ["sg-0a1b2c3d", "sg-4e5f6a7b"],
                "encryption": {"enabled": True, "kms": {"key_id": "alias/aws/ebs"}},
            }
        )

        assert flattened == {
            "id": "i-1234567890abcdef0",
            "tags.Environment": "production",
            "security_groups": "sg-0a1b2c3d, sg-4e5f6a7b",
            "encryption.enabled": True,
            "encryption.kms.key_id": "alias/aws/ebs",
        }

    def test_logical_column_order(self):
        """Core identity columns come first and tag columns last"""
        converter = BOMConverter(enrich_vpc_info=False)
        ordered = converter._get_logical_column_order(
            {
                "tags.Owner",
                "region",
                "arn",
                "id",
                "service",
                "zzz_custom",
                "type",
                "name",
            }
        )

        assert ordered[:5] == ["service", "type", "id", "name", "arn"]
        assert ordered[-1] == "tags.Owner"
        assert sorted(ordered) == sorted(
            [
                "tags.Owner",
                "region",
                "arn",
                "id",
                "service",
                "zzz_custom",
                "type",
                "name",
            ]
        )


# ------------------------------------------------------------------- CSV
class TestCSVExport:
    """Test CSV export functionality"""

    def test_export_to_csv(self, loaded_converter, tmp_path):
        """Test CSV export"""
        output_file = tmp_path / "bom.csv"

        loaded_converter.export_to_csv(str(output_file))

        rows = _read_csv(output_file)
        assert len(rows) == 3
        assert [row["service"] for row in rows] == ["S3", "EC2", "RDS"]

    def test_csv_file_is_owner_only(self, loaded_converter, tmp_path):
        """Reports contain account IDs and ARNs, so they are written 0600"""
        output_file = tmp_path / "bom.csv"

        loaded_converter.export_to_csv(str(output_file))

        if os.name == "posix":
            assert stat.S_IMODE(output_file.stat().st_mode) == 0o600

    def test_csv_column_headers(self, loaded_converter, tmp_path):
        """Headers are the flattened resource keys in logical order"""
        output_file = tmp_path / "bom.csv"

        loaded_converter.export_to_csv(str(output_file))

        with open(output_file, newline="", encoding="utf-8") as handle:
            headers = next(csv.reader(handle))

        assert headers[:5] == ["service", "type", "id", "name", "arn"]
        for column in (
            "account_id",
            "region",
            "discovered_via",
            "tags.Environment",
            "tags.Owner",
            "tags.Role",
            "tags.Name",
        ):
            assert column in headers
        # Tags are flattened, never written as one nested column
        assert "tags" not in headers
        assert len(headers) == len(set(headers))

    def test_csv_data_integrity(self, loaded_converter, tmp_path):
        """Test CSV data integrity"""
        output_file = tmp_path / "bom.csv"

        loaded_converter.export_to_csv(str(output_file))

        rows = {row["service"]: row for row in _read_csv(output_file)}

        s3_row = rows["S3"]
        assert s3_row["type"] == "Bucket"
        assert s3_row["id"] == "example-bucket"
        assert s3_row["arn"] == "arn:aws:s3:::example-bucket"
        assert s3_row["account_id"] == "123456789012"
        assert s3_row["tags.Environment"] == "production"
        # The bucket has no Role tag: the cell is empty, not "None"
        assert s3_row["tags.Role"] == ""

        ec2_row = rows["EC2"]
        assert ec2_row["type"] == "Instance"
        assert ec2_row["id"] == "i-1234567890abcdef0"
        assert ec2_row["name"] == "web-server-01"
        assert ec2_row["tags.Role"] == "webserver"

        assert rows["RDS"]["region"] == "us-west-2"

    def test_csv_neutralizes_formula_values(self, tmp_path):
        """A tag value from the scanned account must not run as a formula"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = [
            {
                "service": "EC2",
                "type": "Instance",
                "id": "i-0123456789abcdef0",
                "region": "us-east-1",
                "tags": {"Name": '=HYPERLINK("http://attacker.example","click")'},
            }
        ]
        output_file = tmp_path / "bom.csv"

        converter.export_to_csv(str(output_file))

        (row,) = _read_csv(output_file)
        assert row["tags.Name"].startswith("'=")

    def test_csv_export_without_data_writes_nothing(self, tmp_path):
        """No data: no file is created"""
        converter = BOMConverter(enrich_vpc_info=False)
        output_file = tmp_path / "empty.csv"

        converter.export_to_csv(str(output_file))

        assert not output_file.exists()


# ----------------------------------------------------------------- Excel
class TestExcelExport:
    """Test Excel export functionality (workbook is written and read back)"""

    def test_export_to_excel(self, loaded_converter, tmp_path):
        """Test Excel export"""
        output_file = tmp_path / "bom.xlsx"

        loaded_converter.export_to_excel(str(output_file))

        assert output_file.exists()
        workbook = load_workbook(output_file)
        assert workbook.sheetnames[0] == "Summary"
        if os.name == "posix":
            assert stat.S_IMODE(output_file.stat().st_mode) == 0o600

    def test_excel_sheet_creation(self, loaded_converter, tmp_path):
        """One summary sheet plus one sheet per service"""
        output_file = tmp_path / "bom.xlsx"

        loaded_converter.export_to_excel(str(output_file))

        workbook = load_workbook(output_file)
        assert workbook.sheetnames == ["Summary", "S3", "EC2", "RDS"]
        # The default empty sheet is removed
        assert "Sheet" not in workbook.sheetnames

    def test_excel_summary_sheet_data(self, loaded_converter, tmp_path):
        """Summary sheet lists each service with its count and a total"""
        output_file = tmp_path / "bom.xlsx"

        loaded_converter.export_to_excel(str(output_file))

        worksheet = load_workbook(output_file)["Summary"]
        rows = list(worksheet.iter_rows(values_only=True))

        assert rows[0] == ("Service", "Resource Count", "Percentage")
        # Services are sorted alphabetically, then the total row
        assert rows[1:] == [
            ("EC2", 1, "33.3%"),
            ("RDS", 1, "33.3%"),
            ("S3", 1, "33.3%"),
            ("TOTAL", 3, "100.0%"),
        ]

    def test_excel_service_sheets_data(self, loaded_converter, tmp_path):
        """Each service sheet holds only that service's resources"""
        output_file = tmp_path / "bom.xlsx"

        loaded_converter.export_to_excel(str(output_file))

        workbook = load_workbook(output_file)

        (s3,) = _sheet_records(workbook["S3"])
        assert s3["type"] == "Bucket"
        assert s3["id"] == "example-bucket"
        assert s3["tags.Owner"] == "data-team"

        (ec2,) = _sheet_records(workbook["EC2"])
        assert ec2["type"] == "Instance"
        assert ec2["id"] == "i-1234567890abcdef0"
        assert ec2["arn"] == (
            "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
        )

        (rds,) = _sheet_records(workbook["RDS"])
        assert rds["type"] == "DBInstance"
        assert rds["region"] == "us-west-2"

        # Column order: identity columns first
        ec2_headers = [cell.value for cell in workbook["EC2"][1]]
        assert ec2_headers[:5] == ["service", "type", "id", "name", "arn"]

    def test_excel_export_without_data_writes_nothing(self, tmp_path):
        """No data: no workbook is created"""
        converter = BOMConverter(enrich_vpc_info=False)
        output_file = tmp_path / "empty.xlsx"

        converter.export_to_excel(str(output_file))

        assert not output_file.exists()

    def test_generate_excel_bom_from_resource_list(
        self, sample_inventory_data, tmp_path
    ):
        """generate_excel_bom accepts a plain list of resources"""
        converter = BOMConverter(enrich_vpc_info=False)
        output_file = tmp_path / "generated.xlsx"

        result = converter.generate_excel_bom(sample_inventory_data, str(output_file))

        assert result == str(output_file)
        assert _summary_rows(load_workbook(output_file))["TOTAL"] == 3


# ------------------------------------------------------------------- VPC
class TestVPCEnrichment:
    """Test VPC/subnet name enrichment with a mocked boto3 session"""

    @pytest.fixture
    def mock_session(self):
        """Session whose EC2 client returns one VPC and one subnet"""
        ec2 = Mock()
        ec2.describe_vpcs.return_value = {
            "Vpcs": [
                {
                    "VpcId": "vpc-0a1b2c3d4e5f67890",
                    "CidrBlock": "10.0.0.0/16",
                    "Tags": [{"Key": "Name", "Value": "production-vpc"}],
                }
            ]
        }
        ec2.describe_subnets.return_value = {
            "Subnets": [
                {
                    "SubnetId": "subnet-0123456789abcdef0",
                    "VpcId": "vpc-0a1b2c3d4e5f67890",
                    "CidrBlock": "10.0.1.0/24",
                    "AvailabilityZone": "us-east-1a",
                    # No Tags key: AWS omits it for untagged subnets
                }
            ]
        }
        session = Mock()
        session.client.return_value = ec2
        session.ec2 = ec2
        return session

    def test_vpc_enrichment_initialization(self, mock_session):
        """A supplied session is used as-is"""
        converter = BOMConverter(enrich_vpc_info=True, session=mock_session)

        assert converter.enrich_vpc_info is True
        assert converter.session is mock_session
        assert converter.vpc_cache == {}

    def test_enrich_with_vpc_info(self, mock_session, tmp_path):
        """Resources gain vpc_name/subnet_name from describe_vpcs/describe_subnets"""
        resources = [
            {
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "id": "i-1234567890abcdef0",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
                "vpc_id": "vpc-0a1b2c3d4e5f67890",
                "subnet_id": "subnet-0123456789abcdef0",
            },
            {
                "service": "S3",
                "type": "Bucket",
                "region": "global",
                "id": "example-bucket",
                "arn": "arn:aws:s3:::example-bucket",
            },
        ]
        converter = BOMConverter(enrich_vpc_info=True, session=mock_session)

        data = converter.load_data(_write_json(tmp_path, resources))

        instance, bucket = data
        assert instance["vpc_name"] == "production-vpc"
        # Untagged subnet: the name falls back to the subnet ID
        assert instance["subnet_name"] == "subnet-0123456789abcdef0"
        assert "vpc_name" not in bucket
        assert "subnet_name" not in bucket

        # Only the real region is queried; "global" is skipped
        mock_session.client.assert_called_once_with("ec2", region_name="us-east-1")
        assert converter.vpc_cache["subnet-0123456789abcdef0"]["availability_zone"] == (
            "us-east-1a"
        )

    def test_vpc_enrichment_survives_access_denied(self, mock_session, tmp_path):
        """A read-only role without ec2:DescribeVpcs still produces a BOM"""
        mock_session.ec2.describe_vpcs.side_effect = ClientError(
            {"Error": {"Code": "UnauthorizedOperation", "Message": "not authorized"}},
            "DescribeVpcs",
        )
        resources = [
            {
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "id": "i-1234567890abcdef0",
                "vpc_id": "vpc-0a1b2c3d4e5f67890",
            }
        ]
        converter = BOMConverter(enrich_vpc_info=True, session=mock_session)

        data = converter.load_data(_write_json(tmp_path, resources))

        assert len(data) == 1
        assert "vpc_name" not in data[0]

    def test_vpc_enrichment_disabled(
        self, mock_session, sample_inventory_data, tmp_path
    ):
        """With enrichment off, no EC2 client is ever created"""
        converter = BOMConverter(enrich_vpc_info=False, session=mock_session)

        converter.load_data(_write_json(tmp_path, sample_inventory_data))

        mock_session.client.assert_not_called()
        assert converter.vpc_cache == {}


# ---------------------------------------------------------------- errors
class TestErrorHandling:
    """Test error handling scenarios"""

    def test_empty_data_handling(self, tmp_path):
        """An inventory with no resources loads as an empty list"""
        converter = BOMConverter(enrich_vpc_info=False)

        data = converter.load_data(
            _write_json(tmp_path, {"all_discovered_resources": []})
        )

        assert data == []
        assert converter.headers == set()

    def test_unrecognised_structure_yields_no_resources(self, tmp_path):
        """A dict with no resource arrays and no resource fields is not a resource"""
        converter = BOMConverter(enrich_vpc_info=False)

        data = converter.load_data(_write_json(tmp_path, {"metadata": {"total": 2}}))

        assert data == []

    def test_malformed_data_handling(self, tmp_path):
        """Resources with missing fields still export; no service means 'Unknown'"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = [
            {"service": "EC2"},  # Missing every other field
            {"id": "i-0123456789abcdef0"},  # Missing service
            {},  # Empty resource
        ]

        csv_file = tmp_path / "malformed.csv"
        converter.export_to_csv(str(csv_file))
        rows = _read_csv(csv_file)
        assert len(rows) == 3
        assert rows[0] == {"service": "EC2", "id": ""}
        assert rows[1] == {"service": "", "id": "i-0123456789abcdef0"}

        xlsx_file = tmp_path / "malformed.xlsx"
        converter.export_to_excel(str(xlsx_file))
        assert _summary_rows(load_workbook(xlsx_file)) == {
            "EC2": 1,
            "Unknown": 2,
            "TOTAL": 3,
        }

    def test_missing_tags_handling(self, tmp_path):
        """A resource without a tags field exports without tag columns"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = [
            {
                "service": "EC2",
                "type": "Instance",
                "id": "i-0123456789abcdef0",
                "name": "test-instance",
                # Missing tags field
            }
        ]
        output_file = tmp_path / "untagged.csv"

        converter.export_to_csv(str(output_file))

        (row,) = _read_csv(output_file)
        assert row == {
            "service": "EC2",
            "type": "Instance",
            "id": "i-0123456789abcdef0",
            "name": "test-instance",
        }

    def test_file_write_error_handling(self, tmp_path):
        """Test handling of file write errors"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = [{"service": "EC2", "type": "Instance", "id": "i-123"}]

        # The parent directory does not exist
        with pytest.raises(OSError):
            converter.export_to_csv(str(tmp_path / "missing-dir" / "file.csv"))


# ----------------------------------------------------------- large inputs
class TestPerformanceScenarios:
    """Test behaviour with large datasets"""

    @pytest.fixture
    def large_dataset(self):
        """Generate 1000 EC2 instances"""
        resources = []
        for i in range(1000):
            resource = {
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "id": f"i-{i:010d}abcdef",
                "name": f"instance-{i}",
                "arn": f"arn:aws:ec2:us-east-1:123456789012:instance/i-{i:010d}abcdef",
                "account_id": "123456789012",
                "tags": {
                    "Name": f"instance-{i}",
                    "Environment": "test" if i % 2 == 0 else "production",
                    "Owner": f"team-{i % 5}",
                },
                "discovered_via": "EC2API",
            }
            resources.append(resource)

        return resources

    def test_large_dataset_csv_export(self, large_dataset, tmp_path):
        """Test CSV export with large dataset (1000 resources)"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = large_dataset
        output_file = tmp_path / "large.csv"

        converter.export_to_csv(str(output_file))

        rows = _read_csv(output_file)
        assert len(rows) == 1000
        assert rows[0]["id"] == "i-0000000000abcdef"
        assert rows[999]["tags.Owner"] == "team-4"

    def test_large_dataset_excel_export(self, large_dataset, tmp_path):
        """Test Excel export with large dataset"""
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = large_dataset
        output_file = tmp_path / "large.xlsx"

        converter.export_to_excel(str(output_file))

        workbook = load_workbook(output_file, read_only=True)
        assert workbook.sheetnames == ["Summary", "EC2"]
        assert _summary_rows(workbook) == {"EC2": 1000, "TOTAL": 1000}
        # Header row + 1000 resources
        assert sum(1 for _ in workbook["EC2"].iter_rows()) == 1001

    def test_memory_efficiency_large_dataset(self, large_dataset, tmp_path):
        """Loading and deduplicating 1000 resources stays within 50 MB"""
        import psutil

        input_file = _write_json(tmp_path, {"all_discovered_resources": large_dataset})

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(input_file)

        memory_increase = process.memory_info().rss - initial_memory

        assert memory_increase < 50 * 1024 * 1024  # 50MB
        assert len(data) == 1000


# ---------------------------------------------------------- input formats
class TestDataFormatCompatibility:
    """Test compatibility with different data formats"""

    def test_inventory_format_compatibility(self, tmp_path, sample_inventory_data):
        """Test compatibility with inventory format"""
        input_file = _write_json(
            tmp_path, {"all_discovered_resources": sample_inventory_data}
        )

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(input_file)

        assert len(data) == 3
        assert all("service" in resource for resource in data)

    def test_all_discovered_resources_takes_precedence(
        self, tmp_path, sample_inventory_data, sample_compliance_data
    ):
        """When both are present only all_discovered_resources is read"""
        combined = dict(sample_compliance_data)
        combined["all_discovered_resources"] = sample_inventory_data[:1]

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(_write_json(tmp_path, combined))

        assert [r["id"] for r in data] == ["example-bucket"]

    def test_compliance_format_compatibility(self, tmp_path, sample_compliance_data):
        """Test compatibility with compliance format"""
        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(_write_json(tmp_path, sample_compliance_data))

        # Should extract all resources from compliance data
        assert len(data) == 3  # 2 compliant + 1 non-compliant
        (non_compliant,) = [
            r for r in data if r["compliance_status"] == "non_compliant"
        ]
        assert non_compliant["violations"] == ["Missing required tag: Role"]

    def test_mixed_format_compatibility(self, tmp_path):
        """The generic 'resources' key is recognised; metadata is ignored"""
        mixed_format = {
            "resources": [
                {"service": "S3", "type": "Bucket", "id": "bucket-1"},
                {"service": "EC2", "type": "Instance", "id": "i-123"},
            ],
            "metadata": {"total": 2},
        }

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(_write_json(tmp_path, mixed_format))

        assert [r["id"] for r in data] == ["bucket-1", "i-123"]

    def test_single_resource_document(self, tmp_path):
        """A dict that looks like one resource is treated as one resource"""
        resource = {
            "service": "DynamoDB",
            "type": "Table",
            "id": "orders",
            "region": "eu-west-1",
            "arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/orders",
        }

        converter = BOMConverter(enrich_vpc_info=False)
        data = converter.load_data(_write_json(tmp_path, resource))

        assert data == [resource]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
