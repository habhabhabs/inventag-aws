"""--enable-network-analysis and --enable-security-analysis, end to end.

The enrichment branch fixed the analyzers, the reporting branch made the BOM
processor call their real mapping methods. This checks the joined result in
the workbook the CLI writes: risk ratings, public/private subnets, and that a
resource (an EC2 instance) is counted in its VPC, its subnet and its group.
"""

import importlib
import logging
import sys

import boto3
import pytest
from moto import mock_aws
from openpyxl import load_workbook

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")


@pytest.fixture
def estate(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        ec2 = boto3.client("ec2")
        vpc = ec2.create_vpc(CidrBlock="10.1.0.0/16")["Vpc"]["VpcId"]
        pub = ec2.create_subnet(VpcId=vpc, CidrBlock="10.1.1.0/24")["Subnet"]
        priv = ec2.create_subnet(VpcId=vpc, CidrBlock="10.1.2.0/24")["Subnet"]
        igw = ec2.create_internet_gateway()["InternetGateway"]["InternetGatewayId"]
        ec2.attach_internet_gateway(InternetGatewayId=igw, VpcId=vpc)
        rt = ec2.create_route_table(VpcId=vpc)["RouteTable"]["RouteTableId"]
        ec2.create_route(
            RouteTableId=rt, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw
        )
        ec2.associate_route_table(RouteTableId=rt, SubnetId=pub["SubnetId"])
        sg = ec2.create_security_group(
            GroupName="open-ssh", Description="d", VpcId=vpc
        )["GroupId"]
        ec2.authorize_security_group_ingress(
            GroupId=sg,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 20,
                    "ToPort": 25,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                }
            ],
        )
        unused = ec2.create_security_group(
            GroupName="unused", Description="d", VpcId=vpc
        )["GroupId"]
        ec2.run_instances(
            ImageId="ami-12c6146b",
            MinCount=1,
            MaxCount=1,
            SubnetId=priv["SubnetId"],
            SecurityGroupIds=[sg],
        )
        yield {
            "vpc": vpc,
            "public": pub["SubnetId"],
            "private": priv["SubnetId"],
            "sg": sg,
            "unused": unused,
        }
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    redaction.clear_registered_secrets()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def _rows(ws):
    return [[c for c in row] for row in ws.iter_rows(values_only=True)]


def _table(rows, first_header):
    start = next(i for i, r in enumerate(rows) if r and r[0] == first_header)
    header = rows[start]
    out = []
    for row in rows[start + 1 :]:
        if not row or row[0] is None:
            break
        out.append(dict(zip(header, row)))
    return out


def test_network_and_security_analysis_join_up(estate, tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "inventag",
            "--account-regions",
            "us-east-1",
            "--no-billing-validation",
            "--create-excel",
            "--enable-network-analysis",
            "--enable-security-analysis",
            "--risk-threshold",
            "CRITICAL",
            "--output-directory",
            "out",
        ],
    )
    with pytest.raises(SystemExit) as exit_info:
        cli_main.main()
    # 20-25 open to the world contains port 22: critical, so exit code 4.
    assert exit_info.value.code == 4

    workbook = load_workbook(next((tmp_path / "out").glob("*.xlsx")), read_only=True)
    network = _rows(workbook["Network Analysis"])
    vpcs = {r["VPC ID"]: r for r in _table(network, "VPC ID")}
    subnets = {r["Subnet ID"]: r for r in _table(network, "Subnet ID")}
    assert vpcs[estate["vpc"]]["Associated Resources"] == 1  # the instance
    assert subnets[estate["private"]]["Associated Resources"] == 1
    assert subnets[estate["public"]]["Associated Resources"] == 0

    security = _rows(workbook["Security Analysis"])
    groups = {r["Security Group ID"]: r for r in _table(security, "Security Group ID")}
    assert groups[estate["sg"]]["Risk Level"] == "critical"
    assert groups[estate["sg"]]["Associated Resources"] == 1
    assert groups[estate["unused"]]["Risk Level"] == "low"  # outbound only
    assert groups[estate["unused"]]["Associated Resources"] == 0


def test_analyzers_read_ids_from_raw_api_data():
    from inventag.discovery.network_analyzer import NetworkAnalyzer
    from inventag.discovery.security_analyzer import SecurityAnalyzer

    network = NetworkAnalyzer.__new__(NetworkAnalyzer)
    security = SecurityAnalyzer.__new__(SecurityAnalyzer)
    instance = {
        "type": "Instance",
        "raw_data": {
            "VpcId": "vpc-1",
            "SubnetId": "subnet-1",
            "SecurityGroups": [{"GroupId": "sg-1", "GroupName": "a"}],
        },
    }
    function = {
        "type": "Function",
        "raw_data": {
            "VpcConfig": {
                "VpcId": "vpc-2",
                "SubnetIds": ["subnet-2", "subnet-3"],
                "SecurityGroupIds": ["sg-2"],
            }
        },
    }
    database = {
        "type": "DBInstance",
        "raw_data": {
            "DBSubnetGroup": {
                "VpcId": "vpc-3",
                "Subnets": [{"SubnetIdentifier": "subnet-4"}],
            },
            "VpcSecurityGroups": [{"VpcSecurityGroupId": "sg-3"}],
        },
    }
    assert network._extract_vpc_id(instance) == "vpc-1"
    assert network._extract_subnet_id(instance) == "subnet-1"
    assert security._extract_security_group_ids(instance) == ["sg-1"]
    assert network._extract_vpc_id(function) == "vpc-2"
    assert network._extract_subnet_id(function) == "subnet-2"
    assert security._extract_security_group_ids(function) == ["sg-2"]
    assert network._extract_vpc_id(database) == "vpc-3"
    assert network._extract_subnet_id(database) == "subnet-4"
    assert security._extract_security_group_ids(database) == ["sg-3"]
    # A security group is not "in" its own group, nor VPC plumbing.
    group = {"type": "SecurityGroup", "raw_data": {"GroupId": "sg-9", "VpcId": "vpc-1"}}
    assert security._extract_security_group_ids(group) == []
    assert network._is_plumbing(group)
