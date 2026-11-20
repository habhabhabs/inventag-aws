"""A4: the network analysis reads each region in its own task.

The tasks run at the same time; their answers are merged in sorted region
order, so one worker and many workers give the same analysis, whatever order
the regions finish in (plan 2.4, 2.5).
"""

import copy
import json
import threading
from dataclasses import asdict

import pytest

from inventag.discovery import network_analyzer as mod
from inventag.discovery.network_analyzer import NetworkAnalyzer

REGIONS = ["us-east-1", "eu-west-1", "ap-southeast-1"]  # not in sorted order

KEYS = {
    "describe_vpcs": "Vpcs",
    "describe_subnets": "Subnets",
    "describe_internet_gateways": "InternetGateways",
    "describe_nat_gateways": "NatGateways",
    "describe_vpc_endpoints": "VpcEndpoints",
    "describe_vpc_peering_connections": "VpcPeeringConnections",
    "describe_transit_gateway_attachments": "TransitGatewayAttachments",
    "describe_route_tables": "RouteTables",
    "describe_network_interfaces": "NetworkInterfaces",
}
VPC = {"us-east-1": "vpc-a", "eu-west-1": "vpc-b", "ap-southeast-1": "vpc-c"}


def _peering(pcx, one, two):
    return {
        "VpcPeeringConnectionId": pcx,
        "Status": {"Code": "active"},
        "AccepterVpcInfo": {"VpcId": VPC[one]},
        "RequesterVpcInfo": {"VpcId": VPC[two]},
    }


def _estate():
    estate = {}
    for n, region in enumerate(REGIONS):
        vpc = VPC[region]
        estate[region] = {
            "describe_vpcs": [
                {
                    "VpcId": vpc,
                    "CidrBlock": f"10.{n}.0.0/16",
                    "Tags": [{"Key": "Name", "Value": f"name-{vpc}"}],
                }
            ],
            "describe_subnets": [
                {
                    "SubnetId": f"subnet-{vpc}-{k}",
                    "VpcId": vpc,
                    "CidrBlock": f"10.{n}.{k}.0/24",
                    "AvailabilityZone": f"{region}a",
                    "AvailableIpAddressCount": 200 - k,
                }
                for k in range(3)
            ],
            "describe_nat_gateways": [
                {"NatGatewayId": f"nat-{vpc}", "VpcId": vpc, "State": "available"}
            ],
        }
    # A cross-region connection is listed in both of its regions; us-east-1
    # also has a second one to ap-southeast-1.
    for region in ("us-east-1", "eu-west-1"):
        estate[region].setdefault("describe_vpc_peering_connections", []).append(
            _peering("pcx-1", "us-east-1", "eu-west-1")
        )
    for region in ("us-east-1", "ap-southeast-1"):
        estate[region].setdefault("describe_vpc_peering_connections", []).append(
            _peering("pcx-2", "us-east-1", "ap-southeast-1")
        )
    return estate


class _FakeEc2:
    def __init__(self, region, estate, hook):
        self._region, self._estate, self._hook = region, estate, hook

    def __getattr__(self, operation):
        if operation not in KEYS:
            raise AttributeError(operation)

        def call(**kwargs):
            self._hook(self._region, operation)
            rows = self._estate[self._region].get(operation, [])
            return {KEYS[operation]: copy.deepcopy(rows)}

        return call


def _install(monkeypatch, hook=lambda region, operation: None, estate=None):
    estate = estate or _estate()

    def create_client(session, service, region=None, **kwargs):
        assert service == "ec2"
        return _FakeEc2(region, estate, hook)

    monkeypatch.setattr(mod, "create_client", create_client)


def _rows():
    return [{"id": f"i-{r}", "region": r, "service": "EC2"} for r in REGIONS]


def _analyze(workers=None):
    kwargs = {} if workers is None else {"max_workers": workers}
    analyzer = NetworkAnalyzer(session=object(), **kwargs)
    analyzer.analyze_vpc_resources(_rows())
    return analyzer


def _snapshot(analyzer):
    return json.dumps(
        {
            "vpcs": [(k, asdict(v)) for k, v in analyzer.vpc_cache.items()],
            "subnets": [(k, asdict(v)) for k, v in analyzer.subnet_cache.items()],
            "clients": list(analyzer.region_clients),
        },
        default=str,
    )


def _reverse_finish_hook():
    """Start all regions together; region i finishes only after region i+1."""
    ordered = sorted(REGIONS, reverse=True)
    started = threading.Barrier(len(REGIONS))
    done = {region: threading.Event() for region in REGIONS}
    first = set()
    lock = threading.Lock()

    def hook(region, operation):
        with lock:
            fresh = region not in first
            first.add(region)
        if fresh:
            started.wait(timeout=10)
        if operation == "describe_network_interfaces":
            index = ordered.index(region)
            if index + 1 < len(ordered):
                assert done[ordered[index + 1]].wait(timeout=10)
            done[region].set()

    return hook


def test_regions_are_read_at_the_same_time(monkeypatch):
    started = threading.Barrier(len(REGIONS), timeout=2)
    seen = set()

    def hook(region, operation):
        if region not in seen:
            seen.add(region)
            started.wait()

    _install(monkeypatch, hook)
    analyzer = _analyze()
    assert sorted(v.vpc_id for v in analyzer.vpc_cache.values()) == [
        "vpc-a",
        "vpc-b",
        "vpc-c",
    ]
    assert all(v.subnets for v in analyzer.vpc_cache.values())


def test_answers_are_merged_in_sorted_region_order_whatever_finishes_first(monkeypatch):
    _install(monkeypatch, _reverse_finish_hook())
    analyzer = _analyze()
    assert list(analyzer.vpc_cache) == ["vpc-c", "vpc-b", "vpc-a"]
    assert list(analyzer.region_clients) == sorted(REGIONS)
    assert [s.split("-")[2] for s in analyzer.subnet_cache] == (
        ["c"] * 3 + ["b"] * 3 + ["a"] * 3
    )


def test_one_worker_and_many_workers_give_the_same_analysis(monkeypatch):
    _install(monkeypatch)
    one = _snapshot(_analyze(workers=1))
    many = _snapshot(_analyze(workers=8))
    default = _snapshot(_analyze())
    assert one == many == default


def test_a_cross_region_peering_connection_is_on_each_vpc_once(monkeypatch):
    _install(monkeypatch)
    for workers in (1, 8):
        cache = _analyze(workers=workers).vpc_cache
        assert cache["vpc-a"].peering_connections == ["pcx-1", "pcx-2"]
        assert cache["vpc-b"].peering_connections == ["pcx-1"]
        assert cache["vpc-c"].peering_connections == ["pcx-2"]


def test_a_failing_region_raises_the_error_of_the_first_region_in_sorted_order(
    monkeypatch,
):
    # A client that cannot be made is not a ClientError, so (as in v1.3.0) the
    # analysis stops; with many failing regions the first in sorted order wins.
    _install(monkeypatch)
    original = mod.create_client

    def create_client(session, service, region=None, **kwargs):
        if region in ("eu-west-1", "us-east-1"):
            raise RuntimeError(region)
        return original(session, service, region, **kwargs)

    monkeypatch.setattr(mod, "create_client", create_client)
    with pytest.raises(RuntimeError, match="eu-west-1"):
        _analyze(workers=8)


def _cache_rows(regions):
    rows = []
    for region in regions:
        rows.append(
            {
                "id": f"cache-{region}",
                "service": "ELASTICACHE",
                "type": "CacheCluster",
                "region": region,
                "account_id": "111111111111",
                "raw_data": {"CacheSubnetGroupName": "grp"},
            }
        )
    return rows


def _install_cache(monkeypatch, denied=(), hook=lambda region: None):
    from botocore.exceptions import ClientError

    ec2 = mod.create_client

    class Cache:
        def __init__(self, region):
            self.region = region

        def describe_cache_subnet_groups(self, **params):
            hook(self.region)
            if self.region in denied:
                raise ClientError(
                    {"Error": {"Code": "AccessDenied", "Message": "no"}},
                    "DescribeCacheSubnetGroups",
                )
            return {
                "CacheSubnetGroups": [
                    {
                        "ARN": "arn:aws:elasticache:x:111111111111:subnetgroup:grp",
                        "CacheSubnetGroupName": "grp",
                        "VpcId": f"vpc-{self.region}",
                        "Subnets": [{"SubnetIdentifier": f"subnet-{self.region}"}],
                    }
                ]
            }

    def create_client(session, service, region=None, **kwargs):
        if service == "elasticache":
            return Cache(region)
        return ec2(session, service, region, **kwargs)

    monkeypatch.setattr(mod, "create_client", create_client)


def test_cache_subnet_groups_are_read_per_region_at_the_same_time(monkeypatch):
    _install(monkeypatch)
    regions = ["us-east-1", "eu-west-1", "ap-southeast-1"]
    started = threading.Barrier(len(regions), timeout=2)
    _install_cache(monkeypatch, hook=lambda region: started.wait())
    analyzer = NetworkAnalyzer(session=object())
    groups = analyzer._read_cache_subnet_groups(_cache_rows(regions))
    assert sorted(key[1] for key in groups) == sorted(regions)
    assert analyzer.unread_cache_regions == {}


def test_cache_subnet_group_failures_are_the_same_with_one_and_many_workers(
    monkeypatch,
):
    _install(monkeypatch)
    _install_cache(monkeypatch, denied=("eu-west-1", "us-east-1"))
    out = []
    for workers in (1, 8):
        analyzer = NetworkAnalyzer(session=object(), max_workers=workers)
        groups = analyzer._read_cache_subnet_groups(_cache_rows(REGIONS))
        out.append(
            (groups, analyzer.unread_cache_regions, analyzer.cache_group_notes())
        )
    assert out[0] == out[1]
    assert list(out[0][0]) == [("111111111111", "ap-southeast-1", "grp")]
    assert list(out[0][1]) == ["eu-west-1", "us-east-1"]
