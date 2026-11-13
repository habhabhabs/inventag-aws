"""SecurityAnalyzer findings against moto: which rules are flagged, and how badly."""

from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from inventag.cli.main import risk_findings_at_or_above
from inventag.discovery.security_analyzer import SecurityAnalyzer, _collect

R = "us-east-1"
ANY4 = [{"CidrIp": "0.0.0.0/0"}]
ANY6 = [{"CidrIpv6": "::/0"}]


@pytest.fixture
def ec2():
    with mock_aws():
        yield boto3.client("ec2", region_name=R)


def _group(ec2, name, permissions=(), vpc=None):
    vpc = vpc or ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    group = ec2.create_security_group(GroupName=name, Description=name, VpcId=vpc)[
        "GroupId"
    ]
    if permissions:
        ec2.authorize_security_group_ingress(
            GroupId=group, IpPermissions=list(permissions)
        )
    return group


def _analyze(resources=None):
    analyzer = SecurityAnalyzer(boto3.Session(region_name=R))
    analyzer.analyze_security_groups(resources or [{"id": "x", "region": R}])
    return analyzer


def _inbound(analyzer, group):
    return analyzer.sg_cache[group].inbound_rules


def _perm(protocol, low=None, high=None, **targets):
    perm = {"IpProtocol": protocol, **targets}
    if low is not None:
        perm["FromPort"] = low
        perm["ToPort"] = high if high is not None else low
    return perm


RISK_CASES = [
    ("tcp", 22, 22, {"IpRanges": ANY4}, "critical"),
    ("tcp", 3389, 3389, {"Ipv6Ranges": ANY6}, "critical"),
    ("tcp", 20, 25, {"IpRanges": ANY4}, "critical"),  # range includes 22
    ("tcp", 3380, 3400, {"IpRanges": ANY4}, "critical"),  # includes 3389
    ("tcp", 0, 65535, {"IpRanges": ANY4}, "critical"),
    ("udp", 0, 65535, {"Ipv6Ranges": ANY6}, "critical"),
    ("tcp", 3000, 4000, {"IpRanges": ANY4}, "critical"),  # includes 3306
    ("tcp", 80, 80, {"IpRanges": ANY4}, "high"),
    ("tcp", 443, 443, {"Ipv6Ranges": ANY6}, "high"),
    ("tcp", 8000, 9000, {"IpRanges": ANY4}, "medium"),
    ("tcp", 8080, 8080, {"IpRanges": ANY4}, "medium"),
    ("-1", None, None, {"IpRanges": ANY4}, "critical"),  # all traffic
    ("-1", None, None, {"Ipv6Ranges": ANY6}, "critical"),
    ("icmp", -1, -1, {"IpRanges": ANY4}, "medium"),  # ping is not a port
    ("tcp", 22, 22, {"IpRanges": [{"CidrIp": "10.1.2.3/32"}]}, "low"),
    ("tcp", 22, 22, {"IpRanges": [{"CidrIp": "203.0.113.0/24"}]}, "low"),
]


@pytest.fixture(scope="module")
def risk_world():
    with mock_aws():
        client = boto3.client("ec2", region_name=R)
        vpc = client.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
        groups = [
            _group(client, f"case{i}", [_perm(p, lo, hi, **t)], vpc)
            for i, (p, lo, hi, t, _) in enumerate(RISK_CASES)
        ]
        yield groups, _analyze()


@pytest.mark.parametrize("index", range(len(RISK_CASES)))
def test_inbound_rule_risk(risk_world, index):
    groups, analyzer = risk_world
    rules = _inbound(analyzer, groups[index])
    assert [r.risk_assessment for r in rules] == [RISK_CASES[index][4]]


def test_any_address_flag_covers_ipv4_and_ipv6_but_not_private_ranges(ec2):
    group = _group(
        ec2,
        "g",
        [
            _perm("tcp", 22, 22, IpRanges=ANY4),
            _perm("tcp", 22, 22, Ipv6Ranges=ANY6),
            _perm("tcp", 22, 22, IpRanges=[{"CidrIp": "10.0.0.0/8"}]),
        ],
    )
    flags = {r.source_destination: r.is_permissive for r in _inbound(_analyze(), group)}
    assert flags == {"0.0.0.0/0": True, "::/0": True, "10.0.0.0/8": False}


def test_all_traffic_rule_shows_all_ports_and_protocol(ec2):
    group = _group(ec2, "g", [_perm("-1", IpRanges=ANY4)])
    (rule,) = _inbound(_analyze(), group)
    assert (rule.protocol, rule.port_range) == ("All", "All")


def test_icmp_all_types_is_not_shown_as_port_minus_one(ec2):
    group = _group(ec2, "g", [_perm("icmp", -1, -1, IpRanges=ANY4)])
    (rule,) = _inbound(_analyze(), group)
    assert rule.port_range == "All"


def test_security_group_reference_is_low_risk_and_linked(ec2):
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    web = _group(ec2, "web", vpc=vpc)
    db = _group(
        ec2, "db", [_perm("tcp", 3306, 3306, UserIdGroupPairs=[{"GroupId": web}])], vpc
    )
    analyzer = _analyze()
    (rule,) = _inbound(analyzer, db)
    assert rule.source_destination == web  # not "sg-sg-..."
    assert rule.references_security_group and rule.referenced_sg_id == web
    assert rule.risk_assessment == "low" and not rule.is_permissive
    assert analyzer.sg_cache[db].references_other_sgs == [web]
    assert analyzer.sg_cache[web].referenced_by_sgs == [db]


def test_prefix_list_rule_is_kept(ec2):
    analyzer = SecurityAnalyzer(MagicMock())
    rules = analyzer._parse_security_rule(
        {
            "IpProtocol": "tcp",
            "FromPort": 22,
            "ToPort": 22,
            "PrefixListIds": [{"PrefixListId": "pl-123"}],
        },
        "inbound",
    )
    assert [(r.source_destination, r.risk_assessment) for r in rules] == [
        ("pl-123", "low")
    ]


def test_default_open_egress_is_listed_but_low(ec2):
    group = _group(ec2, "g")
    analyzer = _analyze()
    egress = analyzer.sg_cache[group].outbound_rules
    assert egress and all(r.is_permissive for r in egress)
    assert {r.risk_assessment for r in egress} == {"low"}
    assert analyzer.sg_cache[group].risk_level == "low"


def test_unused_groups_come_from_network_interfaces(ec2):
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.1.0/24")["Subnet"]["SubnetId"]
    used = _group(ec2, "used", vpc=vpc)
    lonely = _group(ec2, "lonely", vpc=vpc)
    referenced = _group(ec2, "referenced", vpc=vpc)
    _group(
        ec2,
        "refers",
        [_perm("tcp", 80, 80, UserIdGroupPairs=[{"GroupId": referenced}])],
        vpc,
    )
    ec2.create_network_interface(SubnetId=subnet, Groups=[used])
    # What the BOM run passes in: only the security group resources.
    resources = [
        {"id": used, "region": R, "service": "VPC", "type": "SecurityGroup"},
        {"id": lonely, "region": R, "service": "VPC", "type": "SecurityGroup"},
    ]
    analyzer = _analyze(resources)
    cache = analyzer.sg_cache
    assert cache[used].is_unused is False
    assert cache[lonely].is_unused is True
    assert cache[referenced].is_unused is False  # another group refers to it
    default = [g for g in cache.values() if g.group_name == "default"]
    assert default and not any(g.is_unused for g in default)  # cannot be deleted


def test_group_is_not_called_unused_when_interfaces_cannot_be_read():
    client = MagicMock()
    client.describe_security_groups.return_value = {
        "SecurityGroups": [
            {
                "GroupId": "sg-1",
                "GroupName": "app",
                "Description": "d",
                "VpcId": "vpc-1",
                "IpPermissions": [],
                "IpPermissionsEgress": [],
            }
        ]
    }
    client.describe_network_interfaces.side_effect = Exception("UnauthorizedOperation")
    session = MagicMock()
    session.client.return_value = client
    analyzer = SecurityAnalyzer(session)
    analyzer.analyze_security_groups([{"id": "sg-1", "region": R}])
    assert analyzer.sg_cache["sg-1"].usage_unknown is True
    assert analyzer.sg_cache["sg-1"].is_unused is False


def test_summary_and_threshold_see_the_same_findings(ec2):
    _group(ec2, "open-ssh", [_perm("tcp", 22, 22, IpRanges=ANY4)])
    _group(ec2, "web", [_perm("tcp", 443, 443, IpRanges=ANY4)])
    analyzer = _analyze()
    risks = analyzer.identify_overly_permissive_rules(analyzer.sg_cache)
    mine = {"open-ssh", "web"}
    risks = [r for r in risks if r["security_group_name"] in mine]
    inbound = [r for r in risks if r["rule_type"] == "inbound"]
    assert sorted(r["risk_level"] for r in inbound) == ["critical", "high"]
    findings = [
        {"group_id": r["security_group_id"], "rule": "x", "risk_level": r["risk_level"]}
        for r in risks
    ]
    results = {"bom_generation": {"security_risk_findings": findings}}
    assert len(risk_findings_at_or_above(results, "CRITICAL")) == 1
    # Default egress rules are low, so only the two inbound rules reach HIGH
    assert len(risk_findings_at_or_above(results, "HIGH")) == 2
    assert len(risk_findings_at_or_above(results, "MEDIUM")) == 2


def test_nacl_ipv6_open_rule_is_found_and_default_deny_is_not_a_gap():
    analyzer = SecurityAnalyzer(MagicMock())
    client = MagicMock()
    client.describe_network_acls.return_value = {
        "NetworkAcls": [
            {
                "NetworkAclId": "acl-1",
                "IsDefault": False,
                "VpcId": "vpc-1",
                "Associations": [],
                "Entries": [
                    {
                        "RuleNumber": 100,
                        "Protocol": "6",
                        "RuleAction": "allow",
                        "Ipv6CidrBlock": "::/0",
                        "PortRange": {"From": 22, "To": 22},
                        "Egress": False,
                    },
                    {
                        "RuleNumber": 32767,
                        "Protocol": "-1",
                        "RuleAction": "deny",
                        "CidrBlock": "0.0.0.0/0",
                        "Egress": False,
                    },
                    {
                        "RuleNumber": 100,
                        "Protocol": "-1",
                        "RuleAction": "allow",
                        "CidrBlock": "0.0.0.0/0",
                        "Egress": True,
                    },
                ],
            }
        ]
    }
    analyzer.session.client.return_value = client
    analyzer._cache_nacl_info(R)
    analyzer._analyze_nacl_optimization()
    recs = analyzer.nacl_cache["acl-1"].optimization_recommendations
    assert recs == ["Rule 100 allows TCP 22 from anywhere - consider restricting"]


def test_collect_follows_next_token():
    client = MagicMock()
    client.describe_security_groups.side_effect = [
        {"SecurityGroups": [{"GroupId": "a"}], "NextToken": "t"},
        {"SecurityGroups": [{"GroupId": "b"}]},
    ]
    got = _collect(client, "describe_security_groups", "SecurityGroups")
    assert [g["GroupId"] for g in got] == ["a", "b"]
