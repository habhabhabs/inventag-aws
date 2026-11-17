"""Associated Resources for MSK, EKS and EFS (A-08a).

Counted where the discovery row carries the subnets: an MSK cluster (broker
client subnets), an EKS cluster whose row holds ``resourcesVpcConfig``. Not
counted: an EKS row that holds only the cluster name (what ListClusters gives)
and an EFS file system (its listing has no subnets; mount targets need
``elasticfilesystem:DescribeMountTargets``, which the read-only policy lacks).
No call is added to the ones that are made today.
"""

import boto3
import botocore.client
import pytest
from moto import mock_aws

from inventag.discovery.network_analyzer import NetworkAnalyzer

R = "us-east-1"


@pytest.fixture
def estate():
    with mock_aws():
        ec2 = boto3.client("ec2", region_name=R)
        vpc = ec2.create_vpc(CidrBlock="10.40.0.0/16")["Vpc"]
        subnets = [
            ec2.create_subnet(
                VpcId=vpc["VpcId"],
                CidrBlock=f"10.40.{n}.0/24",
                AvailabilityZone=f"{R}{z}",
            )["Subnet"]
            for n, z in ((1, "a"), (2, "b"), (3, "c"))
        ]
        a, b, c = (s["SubnetId"] for s in subnets)
        sg = ec2.create_security_group(
            GroupName="g", Description="d", VpcId=vpc["VpcId"]
        )["GroupId"]
        boto3.client("kafka", region_name=R).create_cluster(
            ClusterName="msk1",
            KafkaVersion="2.8.1",
            NumberOfBrokerNodes=2,
            BrokerNodeGroupInfo={
                "InstanceType": "kafka.m5.large",
                "ClientSubnets": [a, b],
                "SecurityGroups": [sg],
            },
        )
        msk = boto3.client("kafka", region_name=R).list_clusters_v2()["ClusterInfoList"]

        def row(service, kind, rid, raw):
            return {
                "service": service,
                "type": kind,
                "id": rid,
                "region": R,
                "raw_data": raw,
            }

        rows = [row("VPC", "VPC", vpc["VpcId"], vpc)] + [
            row("VPC", "Subnet", s["SubnetId"], s) for s in subnets
        ]
        rows += [row("KAFKA", "Cluster", "msk1", m) for m in msk]
        rows.append(
            row(
                "EKS",
                "Cluster",
                "eks-with-vpc",
                {
                    "name": "eks-with-vpc",
                    "resourcesVpcConfig": {
                        "subnetIds": [a, c],
                        "vpcId": vpc["VpcId"],
                    },
                },
            )
        )
        rows.append(row("EKS", "Cluster", "eks-name-only", {"name": "eks-name-only"}))
        rows.append(
            row(
                "ELASTICFILESYSTEM",
                "FileSystem",
                "fs-1",
                {"FileSystemId": "fs-1", "NumberOfMountTargets": 2},
            )
        )
        yield {"vpc": vpc["VpcId"], "a": a, "b": b, "c": c, "rows": rows}


def _analyse(rows):
    analyzer = NetworkAnalyzer(boto3.Session(region_name=R))
    analyzer.analyze_vpc_resources(rows)
    return analyzer


def test_an_msk_cluster_is_counted_in_its_vpc_and_each_broker_subnet(estate):
    analyzer = _analyse(estate["rows"])
    assert analyzer.vpc_cache[estate["vpc"]].associated_resources.count("msk1") == 1
    assert "msk1" in analyzer.subnet_cache[estate["a"]].associated_resources
    assert "msk1" in analyzer.subnet_cache[estate["b"]].associated_resources
    assert "msk1" not in analyzer.subnet_cache[estate["c"]].associated_resources


def test_a_serverless_msk_cluster_is_counted_through_its_vpc_configs(estate):
    rows = [dict(r) for r in estate["rows"] if r["id"] != "msk1"]
    rows.append(
        {
            "service": "KAFKA",
            "type": "Cluster",
            "id": "msk-sl",
            "region": R,
            "raw_data": {
                "ClusterType": "SERVERLESS",
                "Serverless": {"VpcConfigs": [{"SubnetIds": [estate["c"]]}]},
            },
        }
    )
    analyzer = _analyse(rows)
    assert "msk-sl" in analyzer.subnet_cache[estate["c"]].associated_resources
    assert "msk-sl" in analyzer.vpc_cache[estate["vpc"]].associated_resources


def test_an_eks_cluster_row_with_its_vpc_config_is_counted(estate):
    analyzer = _analyse(estate["rows"])
    assert "eks-with-vpc" in analyzer.vpc_cache[estate["vpc"]].associated_resources
    assert "eks-with-vpc" in analyzer.subnet_cache[estate["a"]].associated_resources
    assert "eks-with-vpc" in analyzer.subnet_cache[estate["c"]].associated_resources
    assert "eks-with-vpc" not in analyzer.subnet_cache[estate["b"]].associated_resources


def test_an_eks_row_with_only_the_name_and_an_efs_file_system_are_not_counted(estate):
    analyzer = _analyse(estate["rows"])
    counted = analyzer.vpc_cache[estate["vpc"]].associated_resources
    assert "eks-name-only" not in counted and "fs-1" not in counted


def test_no_call_is_added_for_these_services(estate, monkeypatch):
    calls = []
    original = botocore.client.BaseClient._make_api_call

    def counting(self, operation_name, api_params):
        calls.append(operation_name)
        return original(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", counting)
    _analyse(estate["rows"])
    assert not [
        c
        for c in calls
        if c
        in (
            "DescribeCluster",
            "DescribeMountTargets",
            "GetClusterV2",
            "DescribeClusterV2",
            "ListClusters",
        )
    ]


def test_the_row_columns_of_these_rows_are_unchanged(estate):
    enriched = _analyse(estate["rows"]).map_resources_to_network(estate["rows"])
    for row in enriched:
        if row["service"] in ("KAFKA", "EKS", "ELASTICFILESYSTEM"):
            assert "subnet_id" not in row and "vpc_id" not in row
