"""Network and security analysis read the account once per run.

With ``--enable-network-analysis`` or ``--enable-security-analysis`` the BOM
processor analysed the account, and the workbook converter analysed it again to
fill its own sheets: every analysis call was made twice. The report must be the
same as before; only the calls drop.
"""

import dataclasses
import os
from collections import Counter

import boto3
import botocore.client
import pytest
from moto import mock_aws
from openpyxl import load_workbook

from inventag.reporting.bom_processor import BOMDataProcessor, BOMProcessingConfig
from inventag.reporting.converter import BOMConverter

R = "us-east-1"
ANALYSIS_CALLS = (
    "DescribeVpcs",
    "DescribeSubnets",
    "DescribeRouteTables",
    "DescribeInternetGateways",
    "DescribeNatGateways",
    "DescribeSecurityGroups",
)


@pytest.fixture
def estate(monkeypatch):
    for key, value in {
        "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
        "AWS_SECRET_ACCESS_KEY": "fake-secret-for-moto-only",
        "AWS_DEFAULT_REGION": R,
        "AWS_EC2_METADATA_DISABLED": "true",
    }.items():
        monkeypatch.setenv(key, value)
    with mock_aws():
        ec2 = boto3.client("ec2", region_name=R)
        vpc = ec2.create_vpc(CidrBlock="10.2.0.0/16")["Vpc"]
        subnet = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.2.1.0/24")[
            "Subnet"
        ]
        group = ec2.create_security_group(
            GroupName="open-ssh", Description="d", VpcId=vpc["VpcId"]
        )["GroupId"]
        ec2.authorize_security_group_ingress(
            GroupId=group,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                }
            ],
        )
        group_data = ec2.describe_security_groups(GroupIds=[group])["SecurityGroups"][0]
        instance = {
            "service": "EC2",
            "type": "Instance",
            "id": "i-0123456789abcdef0",
            "region": R,
            "raw_data": {
                "VpcId": vpc["VpcId"],
                "SubnetId": subnet["SubnetId"],
                "SecurityGroups": [{"GroupId": group}],
            },
        }
        resources = [
            {
                "service": "VPC",
                "type": "VPC",
                "id": vpc["VpcId"],
                "region": R,
                "raw_data": vpc,
            },
            {
                "service": "VPC",
                "type": "Subnet",
                "id": subnet["SubnetId"],
                "region": R,
                "raw_data": subnet,
            },
            {
                "service": "VPC",
                "type": "SecurityGroup",
                "id": group,
                "region": R,
                "raw_data": group_data,
            },
            instance,
        ]
        yield {
            "vpc": vpc["VpcId"],
            "subnet": subnet["SubnetId"],
            "group": group,
            "resources": resources,
        }


def _write_workbook(resources, path, network=True, security=True):
    """The calls cloud_bom_generator makes: process, then write the workbook."""
    config = BOMProcessingConfig(
        enable_network_analysis=network,
        enable_security_analysis=security,
        enable_parallel_processing=False,
    )
    session = boto3.Session(region_name=R)
    bom_data = BOMDataProcessor(config, session).process_inventory_data(
        [dict(r) for r in resources]
    )
    converter = BOMConverter(session=session)
    converter.analyze_network = network
    converter.analyze_security = security
    converter.generate_excel_bom(bom_data, str(path))
    return bom_data, converter


def _sheet(path, name):
    rows = list(load_workbook(path)[name].iter_rows(values_only=True))
    return [list(r) for r in rows]


@pytest.fixture
def api_calls(monkeypatch):
    calls = Counter()
    original = botocore.client.BaseClient._make_api_call

    def counting(self, operation_name, api_params):
        calls[operation_name] += 1
        return original(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", counting)
    return calls


def test_sheets_hold_the_analysis_results(estate, tmp_path):
    """Characterisation: what the Network and Security sheets say today."""
    path = tmp_path / "bom.xlsx"
    _write_workbook(estate["resources"], path)
    network = _sheet(path, "Network Analysis")
    vpc_row = next(r for r in network if r[0] == estate["vpc"])
    assert vpc_row[2:4] == ["10.2.0.0/16", 65531]  # CIDR block, Total IPs
    assert vpc_row[6:8] == [1, 1]  # Subnet Count, Associated Resources
    subnet_row = next(r for r in network if r[0] == estate["subnet"])
    assert subnet_row[2] == estate["vpc"]
    assert subnet_row[8] == 1  # the instance
    security = _sheet(path, "Security Analysis")
    group_row = next(r for r in security if r[0] == estate["group"])
    assert group_row[3] == "critical"  # Risk Level
    assert group_row[6] == 1  # Associated Resources
    assert group_row[7] == "Yes"  # Has Permissive Rules


def test_each_analysis_api_is_called_once_per_run(estate, tmp_path, api_calls):
    _write_workbook(estate["resources"], tmp_path / "bom.xlsx")
    made = {name: api_calls[name] for name in ANALYSIS_CALLS if api_calls[name]}
    assert made == {name: 1 for name in made}
    assert made["DescribeVpcs"] == 1 and made["DescribeSecurityGroups"] == 1


def test_one_scope_of_several_is_still_analysed_for_its_own_rows(
    estate, tmp_path, api_calls
):
    """A per-account report counts only its own resources, so it analyses them."""
    session = boto3.Session(region_name=R)
    config = BOMProcessingConfig(
        enable_network_analysis=True,
        enable_security_analysis=True,
        enable_parallel_processing=False,
    )
    bom_data = BOMDataProcessor(config, session).process_inventory_data(
        [dict(r) for r in estate["resources"]]
    )
    without_instance = [r for r in bom_data.resources if r.get("type") != "Instance"]
    scope = dataclasses.replace(bom_data, resources=without_instance)
    converter = BOMConverter(session=session)
    converter.analyze_network = True
    converter.analyze_security = True
    path = tmp_path / "scope.xlsx"
    converter.generate_excel_bom(scope, str(path))
    network = _sheet(path, "Network Analysis")
    subnet_row = next(r for r in network if r[0] == estate["subnet"])
    assert subnet_row[8] == 0  # the instance is not in this report
    security = _sheet(path, "Security Analysis")
    assert next(r for r in security if r[0] == estate["group"])[6] == 0


def test_converter_alone_still_analyses_a_plain_list(estate, tmp_path, api_calls):
    converter = BOMConverter(session=boto3.Session(region_name=R))
    converter.analyze_network = True
    converter.analyze_security = True
    path = tmp_path / "list.xlsx"
    converter.generate_excel_bom([dict(r) for r in estate["resources"]], str(path))
    assert api_calls["DescribeVpcs"] == 1
    assert _sheet(path, "Network Analysis")[0][0] == "VPC ID"
    assert os.path.exists(path)
