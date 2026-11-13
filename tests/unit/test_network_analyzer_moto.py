"""NetworkAnalyzer findings against moto: public subnets, utilisation, unused VPCs."""

from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from inventag.discovery.network_analyzer import NetworkAnalyzer, _collect

R = "us-east-1"


@pytest.fixture
def ec2():
    with mock_aws():
        yield boto3.client("ec2", region_name=R)


def _analyze(resources=None):
    analyzer = NetworkAnalyzer(boto3.Session(region_name=R))
    resources = resources if resources is not None else [{"id": "x", "region": R}]
    analyzer.analyze_vpc_resources(resources)
    return analyzer


def _vpc_with_subnets(ec2):
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    igw = ec2.create_internet_gateway()["InternetGateway"]["InternetGatewayId"]
    ec2.attach_internet_gateway(InternetGatewayId=igw, VpcId=vpc)
    pub = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.1.0/24")["Subnet"]["SubnetId"]
    priv = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.2.0/24")["Subnet"]["SubnetId"]
    rtb = ec2.create_route_table(VpcId=vpc)["RouteTable"]["RouteTableId"]
    ec2.create_route(RouteTableId=rtb, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw)
    ec2.associate_route_table(RouteTableId=rtb, SubnetId=pub)
    return vpc, igw, pub, priv


def test_igw_alone_does_not_make_subnets_public(ec2):
    vpc, igw, pub, priv = _vpc_with_subnets(ec2)
    analyzer = _analyze()
    assert analyzer.subnet_cache[pub].is_public is True
    # The VPC has an internet gateway, but this subnet uses the main route
    # table, which has no route to it.
    assert analyzer.subnet_cache[priv].is_public is False
    assert analyzer.vpc_cache[vpc].internet_gateway_id == igw


def test_main_route_table_with_igw_route_makes_unassociated_subnets_public(ec2):
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    igw = ec2.create_internet_gateway()["InternetGateway"]["InternetGatewayId"]
    ec2.attach_internet_gateway(InternetGatewayId=igw, VpcId=vpc)
    subnet = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.1.0/24")["Subnet"]["SubnetId"]
    main = [
        t
        for t in ec2.describe_route_tables()["RouteTables"]
        if t["VpcId"] == vpc and any(a.get("Main") for a in t.get("Associations", []))
    ][0]["RouteTableId"]
    ec2.create_route(RouteTableId=main, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw)
    assert _analyze().subnet_cache[subnet].is_public is True


def test_route_to_nat_gateway_is_not_public():
    analyzer = NetworkAnalyzer(MagicMock())
    table = {
        "RouteTableId": "rtb-1",
        "Routes": [{"DestinationCidrBlock": "0.0.0.0/0", "NatGatewayId": "nat-1"}],
    }
    assert analyzer._has_internet_route(table) is False


def test_ipv6_default_route_to_igw_is_public_but_blackhole_is_not():
    analyzer = NetworkAnalyzer(MagicMock())
    live = {"Routes": [{"DestinationIpv6CidrBlock": "::/0", "GatewayId": "igw-1"}]}
    dead = {
        "Routes": [
            {
                "DestinationCidrBlock": "0.0.0.0/0",
                "GatewayId": "igw-1",
                "State": "blackhole",
            }
        ]
    }
    egress_only = {
        "Routes": [{"DestinationIpv6CidrBlock": "::/0", "GatewayId": "eigw-1"}]
    }
    assert analyzer._has_internet_route(live) is True
    assert analyzer._has_internet_route(dead) is False
    assert analyzer._has_internet_route(egress_only) is False


def test_subnet_utilisation_counts_aws_reserved_addresses(ec2):
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.1.0/24")["Subnet"]["SubnetId"]
    ec2.create_network_interface(SubnetId=subnet)
    analyzer = _analyze()
    result = analyzer.subnet_cache[subnet]
    assert result.total_ips == 251  # 256 less the 5 AWS reserves
    assert result.available_ips == 250
    assert result.utilization_percentage == pytest.approx(1 / 251 * 100)
    assert analyzer.vpc_cache[vpc].utilization_percentage == pytest.approx(
        1 / 251 * 100
    )


def test_slash_28_subnet_maths(ec2):
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.9.0/28")["Subnet"]["SubnetId"]
    assert _analyze().subnet_cache[subnet].total_ips == 11


def test_empty_vpc_is_reported_and_vpc_with_interface_is_not(ec2):
    empty = ec2.create_vpc(CidrBlock="10.1.0.0/16")["Vpc"]["VpcId"]
    used = ec2.create_vpc(CidrBlock="10.2.0.0/16")["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=used, CidrBlock="10.2.1.0/24")["Subnet"][
        "SubnetId"
    ]
    ec2.create_network_interface(SubnetId=subnet)
    # What the BOM run passes in: only the VPC and subnet resources themselves.
    resources = [
        {"id": empty, "region": R, "service": "VPC", "type": "VPC"},
        {"id": used, "region": R, "service": "VPC", "type": "VPC"},
        {"id": subnet, "region": R, "service": "VPC", "type": "Subnet", "vpc_id": used},
    ]
    analyzer = _analyze(resources)
    notes = analyzer._generate_optimization_recommendations(analyzer.vpc_cache)
    assert any(empty in note and "no associated resources" in note for note in notes)
    assert not any(used in note and "no associated resources" in note for note in notes)


def test_vpc_with_unreadable_interfaces_is_not_called_unused():
    analyzer = NetworkAnalyzer(MagicMock())
    client = MagicMock()
    client.describe_network_interfaces.side_effect = Exception("AccessDenied")
    analyzer._cache_network_interface_counts(client, R)
    from inventag.discovery.network_analyzer import VPCAnalysis

    vpc = VPCAnalysis(vpc_id="vpc-1", vpc_name="v", cidr_block="10.0.0.0/16")
    assert analyzer._generate_optimization_recommendations({"vpc-1": vpc}) == []


def test_private_subnets_without_nat_are_flagged_public_only_vpc_is_not(ec2):
    vpc, igw, pub, priv = _vpc_with_subnets(ec2)
    analyzer = _analyze()
    notes = analyzer._generate_optimization_recommendations(analyzer.vpc_cache)
    assert any(f"VPC {vpc} has 1 private subnet(s)" in n for n in notes)


def test_ipv6_only_subnet_does_not_stop_the_other_subnets():
    analyzer = NetworkAnalyzer(MagicMock())
    from inventag.discovery.network_analyzer import VPCAnalysis

    analyzer.vpc_cache["vpc-1"] = VPCAnalysis(
        vpc_id="vpc-1", vpc_name="v", cidr_block="10.0.0.0/16"
    )
    client = MagicMock()
    client.describe_subnets.return_value = {
        "Subnets": [
            {
                "SubnetId": "subnet-v6",
                "VpcId": "vpc-1",
                "AvailabilityZone": "us-east-1a",
                "AvailableIpAddressCount": 0,
                "Ipv6Native": True,
                "Ipv6CidrBlockAssociationSet": [{"Ipv6CidrBlock": "2600::/64"}],
            },
            {
                "SubnetId": "subnet-v4",
                "VpcId": "vpc-1",
                "CidrBlock": "10.0.1.0/24",
                "AvailabilityZone": "us-east-1a",
                "AvailableIpAddressCount": 251,
            },
        ]
    }
    analyzer._cache_subnet_info(client, R)
    assert analyzer.subnet_cache["subnet-v6"].total_ips == 0
    assert analyzer.subnet_cache["subnet-v6"].utilization_percentage == 0
    assert analyzer.subnet_cache["subnet-v4"].total_ips == 251


def test_collect_follows_next_token():
    client = MagicMock()
    client.describe_subnets.side_effect = [
        {"Subnets": [{"SubnetId": "a"}], "NextToken": "t1"},
        {"Subnets": [{"SubnetId": "b"}]},
    ]
    items = _collect(client, "describe_subnets", "Subnets")
    assert [i["SubnetId"] for i in items] == ["a", "b"]
    assert client.describe_subnets.call_args_list[1].kwargs == {"NextToken": "t1"}


def test_deleted_nat_gateway_and_failed_peering_are_ignored():
    from inventag.discovery.network_analyzer import VPCAnalysis

    analyzer = NetworkAnalyzer(MagicMock())
    analyzer.vpc_cache["vpc-1"] = VPCAnalysis(
        vpc_id="vpc-1", vpc_name="v", cidr_block="10.0.0.0/16", region=R
    )
    client = MagicMock()
    client.describe_internet_gateways.return_value = {"InternetGateways": []}
    client.describe_nat_gateways.return_value = {
        "NatGateways": [
            {"NatGatewayId": "nat-gone", "VpcId": "vpc-1", "State": "deleted"},
            {"NatGatewayId": "nat-ok", "VpcId": "vpc-1", "State": "available"},
        ]
    }
    client.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}
    client.describe_vpc_peering_connections.return_value = {
        "VpcPeeringConnections": [
            {
                "VpcPeeringConnectionId": "pcx-dead",
                "Status": {"Code": "rejected"},
                "AccepterVpcInfo": {"VpcId": "vpc-1"},
                "RequesterVpcInfo": {"VpcId": "vpc-1"},
            },
            {
                "VpcPeeringConnectionId": "pcx-ok",
                "Status": {"Code": "active"},
                "AccepterVpcInfo": {"VpcId": "vpc-1"},
                "RequesterVpcInfo": {"VpcId": "vpc-1"},
            },
        ]
    }
    client.describe_transit_gateway_attachments.return_value = {
        "TransitGatewayAttachments": []
    }
    client.describe_route_tables.return_value = {"RouteTables": []}
    client.describe_network_interfaces.return_value = {"NetworkInterfaces": []}
    analyzer._cache_network_components(client, R)
    vpc = analyzer.vpc_cache["vpc-1"]
    assert vpc.nat_gateways == ["nat-ok"]
    assert vpc.peering_connections == ["pcx-ok"]  # once, not once per side
