"""A4: security groups and NACLs are read in one task per region.

Same rules as the network analysis: tasks run together, answers are merged in
sorted region order, one worker and many workers give the same analysis.
"""

import copy
import json
import threading
from dataclasses import asdict

import pytest

from inventag.discovery import security_analyzer as mod
from inventag.discovery.security_analyzer import SecurityAnalyzer

REGIONS = ["us-east-1", "eu-west-1", "ap-southeast-1"]  # not in sorted order
KEYS = {
    "describe_security_groups": "SecurityGroups",
    "describe_network_interfaces": "NetworkInterfaces",
    "describe_network_acls": "NetworkAcls",
}


def _estate():
    estate = {}
    for n, region in enumerate(REGIONS):
        vpc = f"vpc-{n}"
        groups = [
            {
                "GroupId": f"sg-{n}-{k}",
                "GroupName": f"g{k}",
                "Description": "d",
                "VpcId": vpc,
                "IpPermissions": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    }
                ],
                "IpPermissionsEgress": [],
            }
            for k in range(2)
        ]
        estate[region] = {
            "describe_security_groups": groups,
            "describe_network_interfaces": [
                {
                    "NetworkInterfaceId": f"eni-{n}",
                    "Groups": [{"GroupId": f"sg-{n}-0"}],
                }
            ],
            "describe_network_acls": [
                {
                    "NetworkAclId": f"acl-{n}",
                    "IsDefault": True,
                    "VpcId": vpc,
                    "Associations": [{"SubnetId": f"subnet-{n}"}],
                    "Entries": [
                        {
                            "RuleNumber": 100,
                            "Protocol": "-1",
                            "RuleAction": "allow",
                            "Egress": False,
                            "CidrBlock": "0.0.0.0/0",
                        }
                    ],
                }
            ],
        }
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


def _install(monkeypatch, hook=lambda region, operation: None):
    estate = _estate()

    def create_client(session, service, region=None, **kwargs):
        return _FakeEc2(region, estate, hook)

    monkeypatch.setattr(mod, "create_client", create_client)


def _rows():
    return [{"id": f"x-{r}", "region": r} for r in REGIONS]


def _analyzer(workers=None):
    kwargs = {} if workers is None else {"max_workers": workers}
    return SecurityAnalyzer(session=object(), **kwargs)


def _snapshot(analyzer):
    return json.dumps(
        {
            "sg": [(k, asdict(v)) for k, v in analyzer.sg_cache.items()],
            "nacl": [(k, asdict(v)) for k, v in analyzer.nacl_cache.items()],
            "clients": list(analyzer.region_clients),
        },
        default=str,
    )


def _together_then_reverse(operation_last):
    ordered = sorted(REGIONS, reverse=True)
    started = threading.Barrier(len(REGIONS))
    done = {region: threading.Event() for region in REGIONS}
    seen = set()
    lock = threading.Lock()

    def hook(region, operation):
        with lock:
            fresh = region not in seen
            seen.add(region)
        if fresh:
            started.wait(timeout=10)
        if operation == operation_last:
            index = ordered.index(region)
            if index + 1 < len(ordered):
                assert done[ordered[index + 1]].wait(timeout=10)
            done[region].set()

    return hook


def test_groups_merge_in_sorted_region_order_whatever_finishes_first(monkeypatch):
    _install(monkeypatch, _together_then_reverse("describe_network_interfaces"))
    analyzer = _analyzer()
    analyzer.analyze_security_groups(_rows())
    assert list(analyzer.sg_cache) == [
        "sg-2-0",
        "sg-2-1",
        "sg-1-0",
        "sg-1-1",
        "sg-0-0",
        "sg-0-1",
    ]
    assert list(analyzer.region_clients) == sorted(REGIONS)
    assert analyzer.sg_cache["sg-1-0"].network_interfaces == ["eni-1"]


def test_nacls_merge_in_sorted_region_order_whatever_finishes_first(monkeypatch):
    _install(monkeypatch, _together_then_reverse("describe_network_acls"))
    analyzer = _analyzer()
    analyzer.analyze_nacls(_rows())
    assert list(analyzer.nacl_cache) == ["acl-2", "acl-1", "acl-0"]


def test_one_worker_and_many_workers_give_the_same_analysis(monkeypatch):
    _install(monkeypatch)
    out = []
    for workers in (1, 8, None):
        analyzer = _analyzer(workers)
        analyzer.analyze_security_groups(_rows())
        analyzer.analyze_nacls(_rows())
        out.append(_snapshot(analyzer))
    assert out[0] == out[1] == out[2]


def test_a_region_that_cannot_be_read_is_skipped_and_the_others_are_kept(
    monkeypatch,
):
    _install(monkeypatch)
    original = mod.create_client

    def create_client(session, service, region=None, **kwargs):
        if region in ("eu-west-1", "us-east-1"):
            raise KeyError(region)
        return original(session, service, region, **kwargs)

    monkeypatch.setattr(mod, "create_client", create_client)
    # The region function catches every error and warns, so nothing is raised
    # and the other regions are still read (as in v1.3.0).
    analyzer = _analyzer(8)
    analyzer.analyze_security_groups(_rows())
    assert list(analyzer.region_clients) == ["ap-southeast-1"]


def test_an_error_that_leaves_the_task_stops_the_analysis(monkeypatch):
    _install(monkeypatch)

    def broken(self, region):
        raise MemoryError(region)

    monkeypatch.setattr(SecurityAnalyzer, "_cache_security_group_info", broken)
    with pytest.raises(MemoryError):
        _analyzer(8).analyze_security_groups(_rows())
