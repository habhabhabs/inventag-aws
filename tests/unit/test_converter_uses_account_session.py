"""The Network and Security sheets of an account are read with that account's session.

When the converter does not reuse the BOM processor's analysis (a plain list,
one account of several with ``--per-account-reports``), it builds its own
analyzers. They used the default boto3 session, so in a multi-account run the
sheets of account B could be read from the default (or first) account.

Two accounts are stood for by two session stubs on one moto estate: a session
returns only the VPCs, subnets and security groups of its own account.
"""

import boto3
import pytest
from moto import mock_aws
from openpyxl import load_workbook

from inventag.reporting.converter import BOMConverter

R = "us-east-1"


class _AccountClient:
    """An EC2 client that shows one account's VPCs, subnets and groups only."""

    _KEYS = {
        "describe_vpcs": "Vpcs",
        "describe_subnets": "Subnets",
        "describe_security_groups": "SecurityGroups",
    }

    def __init__(self, real, vpc_id):
        self._real = real
        self._vpc_id = vpc_id

    def __getattr__(self, name):
        method = getattr(self._real, name)
        key = self._KEYS.get(name)
        if key is None:
            return method

        def filtered(*args, **kwargs):
            response = method(*args, **kwargs)
            response[key] = [
                item for item in response[key] if item.get("VpcId") == self._vpc_id
            ]
            return response

        return filtered


class _AccountSession:
    """Stands for the credentials of one account."""

    def __init__(self, vpc_id):
        self.vpc_id = vpc_id
        self.calls = 0

    def client(self, service, region_name=None, **kwargs):
        self.calls += 1
        return _AccountClient(
            boto3.client(service, region_name=region_name), self.vpc_id
        )


@pytest.fixture
def two_accounts():
    with mock_aws():
        ec2 = boto3.client("ec2", region_name=R)
        accounts = {}
        for name, cidr in (("A", "10.1.0.0/16"), ("B", "10.2.0.0/16")):
            vpc = ec2.create_vpc(CidrBlock=cidr)["Vpc"]
            subnet = ec2.create_subnet(
                VpcId=vpc["VpcId"], CidrBlock=cidr.replace("0.0/16", "1.0/24")
            )["Subnet"]
            group = ec2.create_security_group(
                GroupName=f"group-{name}", Description="d", VpcId=vpc["VpcId"]
            )["GroupId"]
            group_data = ec2.describe_security_groups(GroupIds=[group])[
                "SecurityGroups"
            ][0]
            rows = [
                {
                    "service": "VPC",
                    "type": "VPC",
                    "id": vpc["VpcId"],
                    "region": R,
                    "source_account_id": name,
                    "raw_data": vpc,
                },
                {
                    "service": "VPC",
                    "type": "Subnet",
                    "id": subnet["SubnetId"],
                    "region": R,
                    "source_account_id": name,
                    "raw_data": subnet,
                },
                {
                    "service": "VPC",
                    "type": "SecurityGroup",
                    "id": group,
                    "region": R,
                    "source_account_id": name,
                    "raw_data": group_data,
                },
            ]
            accounts[name] = {
                "vpc": vpc["VpcId"],
                "subnet": subnet["SubnetId"],
                "group": group,
                "rows": rows,
                "session": _AccountSession(vpc["VpcId"]),
            }
        yield accounts


def _first_column(path, sheet):
    rows = list(load_workbook(path)[sheet].iter_rows(values_only=True))
    return {row[0] for row in rows if row and row[0]}


def test_account_b_workbook_holds_only_b_vpcs_and_security_groups(
    two_accounts, tmp_path
):
    a, b = two_accounts["A"], two_accounts["B"]
    converter = BOMConverter(session=b["session"])
    converter.analyze_network = True
    converter.analyze_security = True
    path = tmp_path / "b.xlsx"
    converter.generate_excel_bom(list(b["rows"]), str(path))

    network = _first_column(path, "Network Analysis")
    security = _first_column(path, "Security Analysis")
    assert b["vpc"] in network and b["subnet"] in network
    assert a["vpc"] not in network and a["subnet"] not in network
    assert b["group"] in security
    assert a["group"] not in security
    assert b["session"].calls > 0  # the account's own session did the reading
    assert a["session"].calls == 0


def test_account_a_workbook_is_unchanged_by_account_b(two_accounts, tmp_path):
    a, b = two_accounts["A"], two_accounts["B"]
    converter = BOMConverter(session=a["session"])
    converter.analyze_network = True
    converter.analyze_security = True
    path = tmp_path / "a.xlsx"
    converter.generate_excel_bom(list(a["rows"]), str(path))
    assert b["vpc"] not in _first_column(path, "Network Analysis")
    assert b["group"] not in _first_column(path, "Security Analysis")


def test_without_a_session_the_default_session_is_used_as_before(
    two_accounts, tmp_path
):
    """No session given: the analyzers read with the default boto3 session."""
    a = two_accounts["A"]
    converter = BOMConverter(enrich_vpc_info=False)
    assert converter.session is None
    converter.analyze_network = True
    converter.analyze_security = True
    path = tmp_path / "default.xlsx"
    converter.generate_excel_bom(list(a["rows"]), str(path))
    assert a["vpc"] in _first_column(path, "Network Analysis")
    assert a["group"] in _first_column(path, "Security Analysis")
