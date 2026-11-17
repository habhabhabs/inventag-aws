"""What "Associated Resources" counts for RDS and ElastiCache (A-59, A-60).

Counted: a resource whose API data puts it in the VPC or a subnet (an RDS DB
instance, an ElastiCache cluster through its cache subnet group). Not counted:
a DB subnet group, which is configuration (it names subnets; nothing runs in
it), like the other plumbing the guide lists.
"""

import logging

import boto3
import botocore.client
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from inventag.discovery.network_analyzer import NetworkAnalyzer

R = "us-east-1"


@pytest.fixture
def estate():
    with mock_aws():
        ec2 = boto3.client("ec2", region_name=R)
        vpc = ec2.create_vpc(CidrBlock="10.30.0.0/16")["Vpc"]
        other_vpc = ec2.create_vpc(CidrBlock="10.31.0.0/16")["Vpc"]
        subnets = []
        for number, zone in ((1, "a"), (2, "b"), (3, "c")):
            subnets.append(
                ec2.create_subnet(
                    VpcId=vpc["VpcId"],
                    CidrBlock=f"10.30.{number}.0/24",
                    AvailabilityZone=f"{R}{zone}",
                )["Subnet"]
            )
        other_subnet = ec2.create_subnet(
            VpcId=other_vpc["VpcId"], CidrBlock="10.31.1.0/24"
        )["Subnet"]
        a, b, c = (s["SubnetId"] for s in subnets)
        rds = boto3.client("rds", region_name=R)
        rds.create_db_subnet_group(
            DBSubnetGroupName="dbgrp", DBSubnetGroupDescription="d", SubnetIds=[a, b]
        )
        rds.create_db_instance(
            DBInstanceIdentifier="db1",
            DBInstanceClass="db.t3.micro",
            Engine="postgres",
            MasterUsername="u",
            MasterUserPassword="password123",
            AllocatedStorage=20,
            DBSubnetGroupName="dbgrp",
        )
        rds.create_db_cluster(
            DBClusterIdentifier="cl1",
            Engine="aurora-postgresql",
            MasterUsername="u",
            MasterUserPassword="password123",
            DBSubnetGroupName="dbgrp",
        )
        cache = boto3.client("elasticache", region_name=R)
        cache.create_cache_subnet_group(
            CacheSubnetGroupName="cg1",
            CacheSubnetGroupDescription="d",
            SubnetIds=[a, b],
        )
        cache.create_cache_subnet_group(
            CacheSubnetGroupName="cg2",
            CacheSubnetGroupDescription="d",
            SubnetIds=[other_subnet["SubnetId"]],
        )
        for name, group in (("cache1", "cg1"), ("cache2", "cg2")):
            cache.create_cache_cluster(
                CacheClusterId=name,
                Engine="redis",
                CacheNodeType="cache.t3.micro",
                NumCacheNodes=1,
                CacheSubnetGroupName=group,
            )

        def row(service, kind, rid, raw):
            return {
                "service": service,
                "type": kind,
                "id": rid,
                "region": R,
                "raw_data": raw,
            }

        rows = [
            row("VPC", "VPC", vpc["VpcId"], vpc),
            row("VPC", "VPC", other_vpc["VpcId"], other_vpc),
            row("VPC", "Subnet", other_subnet["SubnetId"], other_subnet),
        ] + [row("VPC", "Subnet", s["SubnetId"], s) for s in subnets]
        rows += [
            row("RDS", "DBInstance", "db1", i)
            for i in rds.describe_db_instances()["DBInstances"]
        ]
        rows += [
            row("RDS", "DBCluster", "cl1", i)
            for i in rds.describe_db_clusters()["DBClusters"]
        ]
        rows += [
            row("RDS", "DBSubnetGroup", g["DBSubnetGroupName"], g)
            for g in rds.describe_db_subnet_groups()["DBSubnetGroups"]
        ]
        rows += [
            row("ELASTICACHE", "CacheCluster", c["CacheClusterId"], c)
            for c in cache.describe_cache_clusters()["CacheClusters"]
        ]
        yield {
            "vpc": vpc["VpcId"],
            "other_vpc": other_vpc["VpcId"],
            "a": a,
            "b": b,
            "c": c,
            "other_subnet": other_subnet["SubnetId"],
            "rows": rows,
        }


def _analyse(rows):
    analyzer = NetworkAnalyzer(boto3.Session(region_name=R))
    analyzer.analyze_vpc_resources(rows)
    return analyzer


def test_a_db_subnet_group_is_not_counted_in_the_vpc_or_a_subnet(estate):
    analyzer = _analyse(estate["rows"])
    counted = analyzer.vpc_cache[estate["vpc"]].associated_resources
    assert "dbgrp" not in counted
    for subnet in (estate["a"], estate["b"], estate["c"]):
        assert "dbgrp" not in analyzer.subnet_cache[subnet].associated_resources


def test_an_rds_db_instance_is_counted_in_its_vpc_and_each_subnet_of_its_group(estate):
    analyzer = _analyse(estate["rows"])
    assert "db1" in analyzer.vpc_cache[estate["vpc"]].associated_resources
    assert "db1" in analyzer.subnet_cache[estate["a"]].associated_resources
    assert "db1" in analyzer.subnet_cache[estate["b"]].associated_resources
    assert "db1" not in analyzer.subnet_cache[estate["c"]].associated_resources


def test_an_rds_cluster_is_not_counted_today(estate):
    """Characterisation, reported to the manager and not changed in this patch.

    The cluster's data holds its subnet group by name only, so it is counted
    in neither the VPC nor a subnet.
    """
    analyzer = _analyse(estate["rows"])
    assert "cl1" not in analyzer.vpc_cache[estate["vpc"]].associated_resources
    assert "cl1" not in analyzer.subnet_cache[estate["a"]].associated_resources


def test_an_elasticache_cluster_is_counted_in_its_vpc_and_each_subnet_of_its_group(
    estate,
):
    analyzer = _analyse(estate["rows"])
    assert "cache1" in analyzer.vpc_cache[estate["vpc"]].associated_resources
    assert "cache1" in analyzer.subnet_cache[estate["a"]].associated_resources
    assert "cache1" in analyzer.subnet_cache[estate["b"]].associated_resources
    assert "cache1" not in analyzer.subnet_cache[estate["c"]].associated_resources


def test_each_cluster_is_counted_only_in_the_vpc_of_its_own_group(estate):
    analyzer = _analyse(estate["rows"])
    other = analyzer.vpc_cache[estate["other_vpc"]].associated_resources
    assert "cache2" in other and "cache1" not in other
    assert "cache2" not in analyzer.vpc_cache[estate["vpc"]].associated_resources
    members = analyzer.subnet_cache[estate["other_subnet"]].associated_resources
    assert members == ["cache2"]


def test_cache_subnet_groups_are_read_once_per_region_and_only_when_needed(
    estate, monkeypatch
):
    calls = []
    original = botocore.client.BaseClient._make_api_call

    def counting(self, operation_name, api_params):
        calls.append(operation_name)
        return original(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", counting)
    _analyse(estate["rows"])
    assert calls.count("DescribeCacheSubnetGroups") == 1  # two clusters, one region
    calls.clear()
    _analyse([r for r in estate["rows"] if r["service"] != "ELASTICACHE"])
    assert "DescribeCacheSubnetGroups" not in calls


def test_a_cluster_whose_group_is_not_listed_is_not_counted(estate):
    rows = [dict(r) for r in estate["rows"]]
    cluster = next(r for r in rows if r["id"] == "cache1")
    cluster["raw_data"] = dict(cluster["raw_data"], CacheSubnetGroupName="gone")
    analyzer = _analyse(rows)
    assert "cache1" not in analyzer.vpc_cache[estate["vpc"]].associated_resources
    assert "cache1" not in analyzer.subnet_cache[estate["a"]].associated_resources


def test_the_row_columns_of_a_cluster_are_unchanged(estate):
    analyzer = _analyse(estate["rows"])
    enriched = analyzer.map_resources_to_network(estate["rows"])
    cluster = next(r for r in enriched if r["id"] == "cache1")
    assert "subnet_id" not in cluster and "vpc_id" not in cluster


def test_unreadable_cache_subnet_groups_say_so_once_and_do_not_stop_the_analysis(
    estate, caplog
):
    real = boto3.Session(region_name=R)

    class Denied:
        def describe_cache_subnet_groups(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "secret-detail"}},
                "DescribeCacheSubnetGroups",
            )

    class Session:
        def client(self, service, region_name=None, **kwargs):
            if service == "elasticache":
                return Denied()
            return real.client(service, region_name=region_name, **kwargs)

    analyzer = NetworkAnalyzer(Session())
    with caplog.at_level(logging.WARNING, logger="inventag.discovery.network_analyzer"):
        analyzer.analyze_vpc_resources(estate["rows"])
    messages = [
        r.getMessage() for r in caplog.records if "ElastiCache" in r.getMessage()
    ]
    assert messages == [
        "Could not read the ElastiCache subnet groups in us-east-1 (AccessDenied), "
        "so ElastiCache clusters there are not counted in a VPC or subnet. "
        "Allow elasticache:DescribeCacheSubnetGroups to count them."
    ]
    assert "db1" in analyzer.vpc_cache[estate["vpc"]].associated_resources


def test_a_cluster_of_another_account_is_not_counted_through_a_group_of_the_same_name(
    estate,
):
    """Review H1: in a consolidated multi-account report the subnet groups are
    read with the first account's session. A cluster of another account whose
    group has the same name (every account has an ElastiCache group called
    "default") must not be counted in the first account's VPC and subnets."""
    rows = [dict(r) for r in estate["rows"]]
    own = next(r for r in rows if r["id"] == "cache1")
    own["account_id"] = "123456789012"  # moto's account: the groups' account
    other = dict(own, id="cacheB", account_id="222222222222")
    other["raw_data"] = dict(
        own["raw_data"],
        CacheClusterId="cacheB",
        ARN="arn:aws:elasticache:us-east-1:222222222222:cluster:cacheB",
    )
    rows.append(other)
    analyzer = _analyse(rows)
    vpc = analyzer.vpc_cache[estate["vpc"]].associated_resources
    assert "cache1" in vpc and "cacheB" not in vpc
    for subnet in (estate["a"], estate["b"]):
        members = analyzer.subnet_cache[subnet].associated_resources
        assert "cache1" in members and "cacheB" not in members


def test_a_cluster_row_without_account_id_uses_the_account_of_its_arn(estate):
    """The account of a cluster row comes from ``account_id``, else from its ARN
    (the row's own or the one in its API data)."""
    rows = [dict(r) for r in estate["rows"]]
    other = dict(next(r for r in rows if r["id"] == "cache1"), id="cacheC")
    other["raw_data"] = dict(
        other["raw_data"],
        ARN="arn:aws:elasticache:us-east-1:333333333333:cluster:cacheC",
    )
    rows.append(other)
    analyzer = _analyse(rows)
    vpc = analyzer.vpc_cache[estate["vpc"]].associated_resources
    assert "cache1" in vpc and "cacheC" not in vpc
