"""A resource that sits in several subnets is counted in each of them.

Network analysis used to put a resource in the first subnet its data names
and ignored the subnets of a load balancer (``AvailabilityZones[].SubnetId``),
so an ALB in two subnets counted for neither and a Lambda function in two
subnets for one. The VPC count was right and stays right.
"""

import boto3
import pytest
from moto import mock_aws

from inventag.discovery.network_analyzer import NetworkAnalyzer

R = "us-east-1"


@pytest.fixture
def estate():
    with mock_aws():
        ec2 = boto3.client("ec2", region_name=R)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
        subnets = [
            ec2.create_subnet(
                VpcId=vpc, CidrBlock=f"10.0.{n}.0/24", AvailabilityZone=f"{R}{az}"
            )["Subnet"]["SubnetId"]
            for n, az in ((1, "a"), (2, "b"), (3, "c"))
        ]
        yield vpc, subnets


def _analyze(resources):
    analyzer = NetworkAnalyzer(boto3.Session(region_name=R))
    analyzer.analyze_vpc_resources(resources)
    return analyzer


def _counts(analyzer, subnets):
    return [sorted(analyzer.subnet_cache[s].associated_resources) for s in subnets]


def _alb(vpc, subnet_ids):
    return {
        "id": "alb1",
        "service": "ELBV2",
        "type": "LoadBalancerV2",
        "region": R,
        "raw_data": {
            "VpcId": vpc,
            "AvailabilityZones": [{"ZoneName": R, "SubnetId": s} for s in subnet_ids],
        },
    }


def _function(vpc, subnet_ids):
    return {
        "id": "fn",
        "service": "LAMBDA",
        "type": "Function",
        "region": R,
        "raw_data": {"VpcConfig": {"VpcId": vpc, "SubnetIds": subnet_ids}},
    }


def test_load_balancer_in_two_subnets_counts_once_in_each(estate):
    vpc, (a, b, c) = estate
    analyzer = _analyze([_alb(vpc, [a, b])])
    assert _counts(analyzer, (a, b, c)) == [["alb1"], ["alb1"], []]
    assert analyzer.vpc_cache[vpc].associated_resources == ["alb1"]


def test_lambda_function_in_two_subnets_counts_once_in_each(estate):
    vpc, (a, b, c) = estate
    analyzer = _analyze([_function(vpc, [a, b])])
    assert _counts(analyzer, (a, b, c)) == [["fn"], ["fn"], []]
    assert analyzer.vpc_cache[vpc].associated_resources == ["fn"]


def test_vpc_count_is_one_per_resource_however_many_subnets(estate):
    vpc, (a, b, c) = estate
    analyzer = _analyze([_alb(vpc, [a, b, c]), _function(vpc, [b, c])])
    assert _counts(analyzer, (a, b, c)) == [
        ["alb1"],
        ["alb1", "fn"],
        ["alb1", "fn"],
    ]
    assert sorted(analyzer.vpc_cache[vpc].associated_resources) == ["alb1", "fn"]


def test_database_subnet_group_counts_every_subnet(estate):
    vpc, (a, b, c) = estate
    database = {
        "id": "db1",
        "service": "RDS",
        "type": "DBInstance",
        "region": R,
        "raw_data": {
            "DBSubnetGroup": {
                "VpcId": vpc,
                "Subnets": [{"SubnetIdentifier": a}, {"SubnetIdentifier": c}],
            }
        },
    }
    analyzer = _analyze([database])
    assert _counts(analyzer, (a, b, c)) == [["db1"], [], ["db1"]]


def test_a_subnet_named_twice_in_the_data_counts_the_resource_once(estate):
    vpc, (a, b, c) = estate
    function = _function(vpc, [a, a, b])
    function["raw_data"]["SubnetId"] = a
    analyzer = _analyze([function])
    assert _counts(analyzer, (a, b, c)) == [["fn"], ["fn"], []]


def test_single_subnet_resource_is_counted_once(estate):
    vpc, (a, b, c) = estate
    instance = {
        "id": "i-1",
        "service": "EC2",
        "type": "Instance",
        "region": R,
        "raw_data": {"VpcId": vpc, "SubnetId": b},
    }
    analyzer = _analyze([instance])
    assert _counts(analyzer, (a, b, c)) == [[], ["i-1"], []]
    assert analyzer.vpc_cache[vpc].associated_resources == ["i-1"]


def test_row_columns_still_name_the_first_subnet_only(estate):
    """The per-resource subnet columns are report rows; they do not change."""
    vpc, (a, b, c) = estate
    function = _function(vpc, [c, a])
    analyzer = _analyze([function])
    rows = analyzer.map_resources_to_network([function])
    assert rows[0]["subnet_id"] == c
