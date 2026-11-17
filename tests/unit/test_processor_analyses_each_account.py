"""The BOM processor analyses each account with that account's session (A-71).

The consolidated report of a multi-account run took its Network and Security
analysis from one analysis made with the first account's session, so the VPCs
and security groups of the other accounts were missing. The generator hands
the processor ``account_sessions``; the processor analyses each account's rows
with that account's session and merges the results. Two accounts are stood for
by two session stubs on one moto estate: a session shows only its own VPCs,
subnets and security groups.
"""

from collections import Counter

import boto3
import pytest
from moto import mock_aws
from openpyxl import load_workbook

from inventag.reporting.bom_processor import BOMDataProcessor, BOMProcessingConfig
from inventag.reporting.converter import BOMConverter

R = "us-east-1"
_FILTERED = {
    "describe_vpcs": "Vpcs",
    "describe_subnets": "Subnets",
    "describe_security_groups": "SecurityGroups",
}


class _AccountClient:
    def __init__(self, real, vpc_id, calls):
        self._real, self._vpc_id, self._calls = real, vpc_id, calls

    def __getattr__(self, name):
        method = getattr(self._real, name)
        if not name.startswith("describe_"):
            return method
        key = _FILTERED.get(name)

        def call(*args, **kwargs):
            self._calls[name] += 1
            response = method(*args, **kwargs)
            if key:
                response[key] = [
                    i for i in response[key] if i.get("VpcId") == self._vpc_id
                ]
            return response

        return call


class _AccountSession:
    def __init__(self, vpc_id):
        self.vpc_id = vpc_id
        self.calls = Counter()

    def client(self, service, region_name=None, **kwargs):
        return _AccountClient(
            boto3.client(service, region_name=region_name), self.vpc_id, self.calls
        )


@pytest.fixture
def accounts():
    with mock_aws():
        ec2 = boto3.client("ec2", region_name=R)
        found = {}
        for name, cidr in (("111111111111", "10.1"), ("222222222222", "10.2")):
            vpc = ec2.create_vpc(CidrBlock=f"{cidr}.0.0/16")["Vpc"]
            subnet = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock=f"{cidr}.1.0/24")[
                "Subnet"
            ]
            group = ec2.create_security_group(
                GroupName=f"g-{name}", Description="d", VpcId=vpc["VpcId"]
            )["GroupId"]
            data = ec2.describe_security_groups(GroupIds=[group])["SecurityGroups"][0]

            def row(kind, rid, raw, service="VPC", name=name):
                return {
                    "service": service,
                    "type": kind,
                    "id": rid,
                    "region": R,
                    "source_account_id": name,
                    "raw_data": raw,
                }

            instance = row(
                "Instance",
                f"i-{name}",
                {
                    "VpcId": vpc["VpcId"],
                    "SubnetId": subnet["SubnetId"],
                    "SecurityGroups": [{"GroupId": group}],
                },
                service="EC2",
            )
            found[name] = {
                "vpc": vpc["VpcId"],
                "subnet": subnet["SubnetId"],
                "group": group,
                "instance": instance["id"],
                "rows": [
                    row("VPC", vpc["VpcId"], vpc),
                    row("Subnet", subnet["SubnetId"], subnet),
                    row("SecurityGroup", group, data),
                    instance,
                ],
                "session": _AccountSession(vpc["VpcId"]),
            }
        yield found


def _config():
    return BOMProcessingConfig(
        enable_network_analysis=True,
        enable_security_analysis=True,
        enable_parallel_processing=False,
    )


def _process(accounts, with_sessions=True):
    first, second = accounts["111111111111"], accounts["222222222222"]
    rows = [dict(r) for a in (first, second) for r in a["rows"]]
    sessions = {k: v["session"] for k, v in accounts.items()} if with_sessions else None
    kwargs = {"account_sessions": sessions} if with_sessions else {}
    processor = BOMDataProcessor(_config(), first["session"], **kwargs)
    return processor.process_inventory_data(rows)


def _column(path, sheet):
    rows = list(load_workbook(path)[sheet].iter_rows(values_only=True))
    return {r[0] for r in rows if r and r[0]}


def test_the_consolidated_sheets_hold_the_vpcs_and_groups_of_every_account(
    accounts, tmp_path
):
    bom_data = _process(accounts)
    converter = BOMConverter(session=accounts["111111111111"]["session"])
    converter.analyze_network = True
    converter.analyze_security = True
    path = tmp_path / "all.xlsx"
    converter.generate_excel_bom(bom_data, str(path))
    network, security = (
        _column(path, "Network Analysis"),
        _column(path, "Security Analysis"),
    )
    for account in accounts.values():
        assert account["vpc"] in network and account["subnet"] in network
        assert account["group"] in security
    assert bom_data.network_analysis["total_vpcs"] == 2
    assert bom_data.security_analysis["total_security_groups"] == 2


def test_each_account_is_read_with_its_own_session_and_the_calls_stay_the_same(
    accounts,
):
    reference = _AccountSession(accounts["111111111111"]["vpc"])
    only_first = BOMDataProcessor(_config(), reference)
    only_first.process_inventory_data(
        [dict(r) for r in accounts["111111111111"]["rows"]]
    )
    assert reference.calls["describe_vpcs"] == 1  # one analysis of one account

    accounts["111111111111"]["session"].calls.clear()
    _process(accounts)
    for account in accounts.values():
        assert account["session"].calls == reference.calls


def test_the_associated_resources_of_each_account_are_its_own(accounts):
    bom_data = _process(accounts)
    vpcs = bom_data.analysis_results.vpcs
    for account in accounts.values():
        assert vpcs[account["vpc"]].associated_resources == [account["instance"]]
    groups = bom_data.analysis_results.security_groups
    for account in accounts.values():
        assert groups[account["group"]].associated_resources == [account["instance"]]


def test_without_account_sessions_the_processor_works_as_before(accounts):
    bom_data = _process(accounts, with_sessions=False)
    # one analysis with the first session: only the first account's VPC
    assert bom_data.network_analysis["total_vpcs"] == 1


def test_a_single_account_gives_the_same_analysis_with_or_without_the_argument(
    accounts,
):
    rows = [dict(r) for r in accounts["111111111111"]["rows"]]
    session = accounts["111111111111"]["session"]
    plain = BOMDataProcessor(_config(), session).process_inventory_data(
        [dict(r) for r in rows]
    )
    handed = BOMDataProcessor(
        _config(), session, account_sessions={"111111111111": session}
    ).process_inventory_data([dict(r) for r in rows])
    assert handed.network_analysis == plain.network_analysis
    assert handed.security_analysis == plain.security_analysis
    assert handed.resources == plain.resources


def test_an_account_whose_analysis_fails_is_named_and_the_others_are_kept(
    accounts, caplog
):
    class Broken:
        def client(self, *args, **kwargs):
            raise RuntimeError("secret-detail")

    accounts["222222222222"]["session"] = Broken()
    bom_data = _process(accounts)
    assert accounts["111111111111"]["vpc"] in bom_data.analysis_results.vpcs
    assert accounts["222222222222"]["vpc"] not in bom_data.analysis_results.vpcs
