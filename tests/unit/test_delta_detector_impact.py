"""Characterisation tests for change impact analysis in DeltaDetector.

These pin what ``_analyze_change_impact``, ``_find_related_resources`` and
``_resources_are_related`` return today (v1.2.0), and through them the
``related_resources`` lists and ``impact_analysis`` of ``detect_changes``:
which resources count as related, in which order, with duplicates, and the
fields of every impact entry. They describe present behaviour, including its
oddities, so that a change to how the lookup is done cannot change the output.

The rules the code follows (delta_detector.py, v1.2.0):

* Only a change whose service is a key of ``dependency_patterns`` is
  analysed: "EC2", "RDS", "Lambda", "S3", "VPC" and "SecurityGroup", compared
  without regard to case (A-48; before, Lambda and SecurityGroup never
  matched an upper-cased service).
* Pass 1 walks every other row of the NEW snapshot whose upper-cased service
  is a key and whose ``depends_on`` list holds the changed service: in
  practice a VPC change and EC2, RDS, Lambda or SecurityGroup rows.
* Pass 2 walks every other row of the NEW snapshot whose upper-cased service
  is in the changed service's ``affects`` list: EC2 -> ELB, EBS; RDS -> EC2;
  S3 -> EC2; VPC -> EC2, RDS, ELB, NAT, and the mixed-case entries (Lambda,
  AutoScalingGroup, CloudFront, ...) without regard to case.
* A row found by both passes is listed twice, pass 1 first. Each pass keeps the
  order of the new snapshot.
* The changed resource's own data comes from the new snapshot, else the old
  one (a removed resource); without either, nothing is related.
* Two rows are related when one of ``vpc_id``, ``subnet_id``,
  ``security_groups``, ``iam_role``, ``kms_key_id`` (checked in that order) is
  truthy on both and: both lists share an element; or one list contains the
  other value; or the two values are equal.
* Impact entries: ``high_impact_changes`` for CRITICAL or HIGH changes with
  related rows; ``dependency_impacts`` per upper-cased service; cascade risks
  for rows related to more than one change ("high" above two).
"""

import hashlib
import json
from dataclasses import asdict

import pytest

from inventag.state.changelog_generator import ChangelogGenerator
from inventag.state.delta_detector import (
    ChangeSeverity,
    ChangeType,
    DeltaDetector,
    ResourceChange,
)

ACC = "123456789012"
REG = "us-east-1"


def _ec2(kind, rid):
    return f"arn:aws:ec2:{REG}:{ACC}:{kind}/{rid}"


VPC = _ec2("vpc", "vpc-a")
VPC_B = _ec2("vpc", "vpc-b")
I1 = _ec2("instance", "i-1")
I2 = _ec2("instance", "i-2")
I3 = _ec2("instance", "i-3")
I_NEW = _ec2("instance", "i-new")
GONE = _ec2("instance", "i-gone")
DB = f"arn:aws:rds:{REG}:{ACC}:db:db-1"
LB = f"arn:aws:elasticloadbalancing:{REG}:{ACC}:loadbalancer/app/lb-1/1"
VOL = _ec2("volume", "vol-1")
NAT = _ec2("natgateway", "nat-1")
FN = f"arn:aws:lambda:{REG}:{ACC}:function:fn-1"
ASG = f"arn:aws:autoscaling:{REG}:{ACC}:autoScalingGroup:x:autoScalingGroupName/asg-1"
BKT = "arn:aws:s3:::bkt-1"
SG = _ec2("security-group", "sg-1")
KEY = f"arn:aws:kms:{REG}:{ACC}:key/k1"
ROLE = f"arn:aws:iam::{ACC}:role/app"


def _row(arn, service, type_, **fields):
    rid = arn.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return {
        "arn": arn,
        "id": rid,
        "service": service,
        "type": type_,
        "region": REG,
        "tags": {"Name": rid},
        **fields,
    }


def old_rows():
    return [
        _row(VPC, "VPC", "VPC", vpc_id="vpc-a"),
        _row(VPC_B, "VPC", "VPC", vpc_id="vpc-b"),
        _row(
            I1,
            "EC2",
            "Instance",
            vpc_id="vpc-a",
            subnet_id="subnet-1",
            security_groups=["sg-1", "sg-2"],
            iam_role=ROLE,
        ),
        _row(I2, "ec2", "Instance", vpc_id="vpc-b", security_groups=["", "sg-9"]),
        _row(I3, "EC2", "Instance", vpc_id="", subnet_id=["subnet-1"], kms_key_id=KEY),
        _row(
            DB,
            "RDS",
            "DBInstance",
            vpc_id="vpc-a",
            subnet_id="subnet-2",
            security_groups="sg-2",
            kms_key_id=KEY,
        ),
        _row(LB, "ELB", "LoadBalancer", vpc_id="vpc-a", security_groups=["sg-1"]),
        _row(VOL, "EBS", "Volume", kms_key_id=KEY, subnet_id=None),
        _row(NAT, "NAT", "NatGateway", vpc_id="vpc-a"),
        _row(FN, "Lambda", "Function", vpc_id="vpc-a", iam_role=ROLE),
        _row(ASG, "AutoScalingGroup", "AutoScalingGroup", vpc_id="vpc-a"),
        _row(BKT, "S3", "Bucket", kms_key_id=KEY, iam_role=[ROLE]),
        _row(SG, "SecurityGroup", "SecurityGroup", vpc_id="vpc-a"),
        _row(GONE, "EC2", "Instance", vpc_id="vpc-a", subnet_id="subnet-9"),
    ]


def new_rows():
    rows = [dict(r, tags=dict(r["tags"])) for r in old_rows() if r["arn"] != GONE]
    by_arn = {r["arn"]: r for r in rows}
    for arn in (VPC, I1, DB, BKT, FN, SG, I2):
        by_arn[arn]["tags"]["Env"] = "changed"
    rows.append(
        _row(I_NEW, "EC2", "Instance", vpc_id="vpc-b", security_groups=["sg-9"])
    )
    return rows


@pytest.fixture
def detector():
    return DeltaDetector()


@pytest.fixture
def report(detector):
    return detector.detect_changes(old_rows(), new_rows(), "s1", "s2")


def _all_changes(report):
    return report.added_resources + report.removed_resources + report.modified_resources


# ----------------------------------------------------------- detect_changes


def test_related_resources_of_every_change_in_order(report):
    got = [
        (
            c.change_type.value,
            c.service,
            c.severity.value,
            c.resource_arn,
            c.related_resources,
        )
        for c in _all_changes(report)
    ]
    assert got == [
        ("added", "EC2", "high", I_NEW, []),
        # EC2 affects ELB, AutoScalingGroup and EBS: the load balancer and
        # the ASG share vpc-a.
        ("removed", "EC2", "high", GONE, [LB, ASG]),
        # VPC: pass 1 (EC2, RDS, Lambda, SecurityGroup rows depend on VPC),
        # then pass 2 (EC2, RDS, Lambda, ELB, NAT rows).
        ("modified", "VPC", "medium", VPC, [I1, DB, FN, SG, I1, DB, LB, NAT, FN]),
        ("modified", "EC2", "medium", I1, [LB, ASG]),
        ("modified", "ec2", "medium", I2, []),
        # RDS affects Lambda and EC2: i-1 by vpc_id, i-3 by kms_key_id (its
        # vpc_id is ""), fn-1 by vpc_id.
        ("modified", "RDS", "medium", DB, [I1, I3, FN]),
        # Lambda affects S3: the bucket shares its iam_role.
        ("modified", "Lambda", "medium", FN, [BKT]),
        # S3 affects Lambda and EC2: i-1 and fn-1 by iam_role, i-3 by kms.
        ("modified", "S3", "medium", BKT, [I1, I3, FN]),
        # SecurityGroup depends on VPC and affects EC2, RDS, Lambda, ELB.
        ("modified", "SecurityGroup", "medium", SG, [I1, DB, FN, I1, DB, LB, FN]),
    ]


EXPECTED_IMPACT = {
    "high_impact_changes": [
        {
            "resource_arn": GONE,
            "service": "EC2",
            "change_type": "removed",
            "severity": "high",
            "related_resources": [LB, ASG],
            "potential_impact": "Changes to EC2 may affect 2 related resources",
        }
    ],
    "dependency_impacts": {
        "EC2": [
            {"changed_resource": GONE, "affected_resources": [LB, ASG]},
            {"changed_resource": I1, "affected_resources": [LB, ASG]},
        ],
        "VPC": [
            {
                "changed_resource": VPC,
                "affected_resources": [I1, DB, FN, SG, I1, DB, LB, NAT, FN],
            }
        ],
        "RDS": [{"changed_resource": DB, "affected_resources": [I1, I3, FN]}],
        "LAMBDA": [{"changed_resource": FN, "affected_resources": [BKT]}],
        "S3": [{"changed_resource": BKT, "affected_resources": [I1, I3, FN]}],
        "SECURITYGROUP": [
            {
                "changed_resource": SG,
                "affected_resources": [I1, DB, FN, I1, DB, LB, FN],
            }
        ],
    },
    "cascade_risks": [
        {
            "resource_arn": LB,
            "service": "ELB",
            "type": "LoadBalancer",
            "affecting_changes": [GONE, VPC, I1, SG],
            "risk_level": "high",
            "description": "Resource depends on 4 resources that have changed",
        },
        {
            "resource_arn": ASG,
            "service": "AutoScalingGroup",
            "type": "AutoScalingGroup",
            "affecting_changes": [GONE, I1],
            "risk_level": "medium",
            "description": "Resource depends on 2 resources that have changed",
        },
        {
            "resource_arn": I1,
            "service": "EC2",
            "type": "Instance",
            "affecting_changes": [VPC, VPC, DB, BKT, SG, SG],
            "risk_level": "high",
            "description": "Resource depends on 6 resources that have changed",
        },
        {
            "resource_arn": DB,
            "service": "RDS",
            "type": "DBInstance",
            "affecting_changes": [VPC, VPC, SG, SG],
            "risk_level": "high",
            "description": "Resource depends on 4 resources that have changed",
        },
        {
            "resource_arn": FN,
            "service": "Lambda",
            "type": "Function",
            "affecting_changes": [VPC, VPC, DB, BKT, SG, SG],
            "risk_level": "high",
            "description": "Resource depends on 6 resources that have changed",
        },
        {
            "resource_arn": I3,
            "service": "EC2",
            "type": "Instance",
            "affecting_changes": [DB, BKT],
            "risk_level": "medium",
            "description": "Resource depends on 2 resources that have changed",
        },
    ],
}


def test_impact_analysis_of_detect_changes(report):
    assert report.impact_analysis == EXPECTED_IMPACT
    # Key order is part of the JSON output.
    assert list(report.impact_analysis["dependency_impacts"]) == [
        "EC2",
        "VPC",
        "RDS",
        "LAMBDA",
        "S3",
        "SECURITYGROUP",
    ]
    assert json.dumps(report.impact_analysis) == json.dumps(EXPECTED_IMPACT)


def test_change_record_and_impact_entry_share_one_list(report):
    vpc_change = [c for c in report.modified_resources if c.resource_arn == VPC][0]
    entry = report.impact_analysis["dependency_impacts"]["VPC"][0]
    assert entry["affected_resources"] is vpc_change.related_resources


def test_changelog_counts_related_resources(report):
    markdown = ChangelogGenerator().generate_changelog(report).to_markdown()
    for count in (1, 2, 3, 7, 9):
        assert f"This change may affect {count} related resource(s)." in markdown


REPORT_SHA256 = "75cccc0cb94e1261b4b4ef7abf03c3528ce1a15a7fae82c171decd6c35981d4a"


def test_delta_report_json_without_clocks(report):
    data = asdict(report)
    data.pop("timestamp")
    for key in (
        "added_resources",
        "removed_resources",
        "modified_resources",
        "unchanged_resources",
    ):
        for change in data[key]:
            change.pop("timestamp")
    text = json.dumps(data, default=str, sort_keys=False)
    related = {
        c["resource_arn"]: c["related_resources"] for c in data["modified_resources"]
    }
    assert related[VPC] == [I1, DB, FN, SG, I1, DB, LB, NAT, FN]
    # The whole report, byte for byte (recorded on v1.2.0).
    assert hashlib.sha256(text.encode()).hexdigest() == REPORT_SHA256


def test_row_with_service_none_stops_impact_analysis(detector):
    """A row whose service is None (in both runs, unchanged) breaks the scan.

    ``resource.get("service", "").upper()`` raises when a changed EC2, RDS,
    S3 or VPC resource is analysed. Pinned as present behaviour.
    """
    odd = {"arn": "arn:odd", "id": "odd", "service": None, "type": "X", "region": REG}
    old = old_rows() + [dict(odd)]
    new = new_rows() + [dict(odd)]
    with pytest.raises(
        AttributeError, match="'NoneType' object has no attribute 'upper'"
    ):
        detector.detect_changes(old, new, "s1", "s2")


def test_row_with_service_none_is_harmless_without_analysed_changes(detector):
    odd = {"arn": "arn:odd", "id": "odd", "service": None, "type": "X", "region": REG}
    queue = f"arn:aws:sqs:{REG}:{ACC}:q1"
    old = [_row(queue, "SQS", "Queue", vpc_id="vpc-a"), dict(odd)]
    new = [_row(queue, "SQS", "Queue", vpc_id="vpc-b"), dict(odd)]
    report = detector.detect_changes(old, new, "s1", "s2")
    assert report.summary["modified_count"] == 1
    assert report.impact_analysis == {
        "high_impact_changes": [],
        "dependency_impacts": {},
        "cascade_risks": [],
    }


def test_unhashable_list_elements_stop_impact_analysis(detector):
    """Lists of dicts on both sides make ``set()`` raise. Pinned."""
    old = [
        _row(VPC, "VPC", "VPC", security_groups=[{"id": "sg-1"}]),
        _row(I1, "EC2", "Instance", security_groups=[{"id": "sg-1"}]),
    ]
    new = [dict(r, tags={"Env": "x"}) for r in old]
    with pytest.raises(TypeError, match="unhashable type: 'dict'"):
        detector.detect_changes(old, new, "s1", "s2")


def test_high_impact_only_for_critical_or_high(detector):
    old = [
        _row(VPC, "VPC", "VPC", vpc_id="vpc-a"),
        _row(I1, "EC2", "Instance", vpc_id="vpc-a"),
    ]
    new = [old[1]]  # the VPC is removed: HIGH severity
    report = detector.detect_changes(old, new, "s1", "s2")
    assert report.removed_resources[0].related_resources == [I1, I1]
    assert report.impact_analysis["high_impact_changes"] == [
        {
            "resource_arn": VPC,
            "service": "VPC",
            "change_type": "removed",
            "severity": "high",
            "related_resources": [I1, I1],
            "potential_impact": "Changes to VPC may affect 2 related resources",
        }
    ]
    # Related twice to one change: one affecting change counted twice.
    assert report.impact_analysis["cascade_risks"][0]["affecting_changes"] == [
        VPC,
        VPC,
    ]


# ----------------------------------------------- _analyze_change_impact direct


def _change(arn, service, severity=ChangeSeverity.MEDIUM, kind=ChangeType.MODIFIED):
    return ResourceChange(
        resource_arn=arn,
        resource_id=arn,
        service=service,
        resource_type="",
        region=REG,
        change_type=kind,
        severity=severity,
    )


def _maps():
    old = {r["arn"]: r for r in old_rows()}
    new = {r["arn"]: r for r in new_rows()}
    return old, new


def test_analyze_change_impact_direct(detector):
    old, new = _maps()
    changes = [
        _change(VPC, "vpc", ChangeSeverity.CRITICAL),
        _change(BKT, "S3"),
        _change(FN, "LAMBDA"),
    ]
    impact = detector._analyze_change_impact(changes, old, new)
    assert changes[0].related_resources == [I1, DB, FN, SG, I1, DB, LB, NAT, FN]
    assert changes[1].related_resources == [I1, I3, FN]
    assert changes[2].related_resources == [BKT]
    assert impact == {
        "high_impact_changes": [
            {
                "resource_arn": VPC,
                "service": "vpc",
                "change_type": "modified",
                "severity": "critical",
                "related_resources": [I1, DB, FN, SG, I1, DB, LB, NAT, FN],
                "potential_impact": "Changes to VPC may affect 9 related resources",
            }
        ],
        "dependency_impacts": {
            "VPC": [
                {
                    "changed_resource": VPC,
                    "affected_resources": [I1, DB, FN, SG, I1, DB, LB, NAT, FN],
                }
            ],
            "S3": [{"changed_resource": BKT, "affected_resources": [I1, I3, FN]}],
            "LAMBDA": [{"changed_resource": FN, "affected_resources": [BKT]}],
        },
        "cascade_risks": [
            {
                "resource_arn": I1,
                "service": "EC2",
                "type": "Instance",
                "affecting_changes": [VPC, VPC, BKT],
                "risk_level": "high",
                "description": "Resource depends on 3 resources that have changed",
            },
            {
                "resource_arn": DB,
                "service": "RDS",
                "type": "DBInstance",
                "affecting_changes": [VPC, VPC],
                "risk_level": "medium",
                "description": "Resource depends on 2 resources that have changed",
            },
            {
                "resource_arn": FN,
                "service": "Lambda",
                "type": "Function",
                "affecting_changes": [VPC, VPC, BKT],
                "risk_level": "high",
                "description": "Resource depends on 3 resources that have changed",
            },
        ],
    }


def test_analyze_change_impact_reads_patterns_at_call_time(detector):
    old, new = _maps()
    detector.dependency_patterns["LAMBDA"] = {"depends_on": [], "affects": ["EC2"]}
    change = _change(FN, "Lambda")
    detector._analyze_change_impact([change], old, new)
    # i-1 shares vpc_id and iam_role; i-2 and i-new are in vpc-b.
    assert change.related_resources == [I1]


def test_changed_resource_known_to_neither_snapshot(detector):
    old, new = _maps()
    change = _change("arn:aws:ec2:us-east-1:1:instance/i-x", "EC2")
    assert (
        detector._find_related_resources(
            change, detector.dependency_patterns["EC2"], old, new
        )
        == []
    )


def test_removed_resource_uses_old_data_and_new_candidates(detector):
    old, new = _maps()
    change = _change(GONE, "EC2", kind=ChangeType.REMOVED)
    assert detector._find_related_resources(
        change, detector.dependency_patterns["EC2"], old, new
    ) == [LB, ASG]


def test_affects_comes_from_the_argument_depends_on_from_the_detector(detector):
    old, new = _maps()
    change = _change(VPC, "VPC")
    got = detector._find_related_resources(change, {"affects": ["NAT"]}, old, new)
    assert got == [I1, DB, FN, SG, NAT]
    got = detector._find_related_resources(change, {}, old, new)
    assert got == [I1, DB, FN, SG]


def test_new_data_wins_over_old_data(detector):
    old, new = _maps()
    new[I1] = dict(new[I1], vpc_id="vpc-b", security_groups=["sg-9"])
    change = _change(I1, "EC2")
    # The load balancer is in vpc-a with sg-1: no longer related.
    assert (
        detector._find_related_resources(
            change, detector.dependency_patterns["EC2"], old, new
        )
        == []
    )


def test_order_follows_the_new_snapshot(detector):
    old, new = _maps()
    reordered = dict(reversed(list(new.items())))
    change = _change(VPC, "VPC")
    got = detector._find_related_resources(
        change, detector.dependency_patterns["VPC"], old, reordered
    )
    assert got == [SG, FN, DB, I1, FN, NAT, LB, DB, I1]


# ------------------------------------------------ _resources_are_related rules


@pytest.mark.parametrize(
    "one, two, related",
    [
        ({"vpc_id": "v"}, {"vpc_id": "v"}, True),
        ({"vpc_id": "v"}, {"vpc_id": "w"}, False),
        ({"vpc_id": ""}, {"vpc_id": ""}, False),
        ({"vpc_id": None}, {"vpc_id": None}, False),
        ({"vpc_id": "v"}, {}, False),
        ({"security_groups": ["a", "b"]}, {"security_groups": ["b", "c"]}, True),
        ({"security_groups": ["a"]}, {"security_groups": ["c"]}, False),
        # An empty list is falsy; a list holding "" is not, and "" can match.
        ({"security_groups": []}, {"security_groups": []}, False),
        ({"security_groups": ["", "a"]}, {"security_groups": ["", "b"]}, True),
        ({"security_groups": ["", "a"]}, {"security_groups": ""}, False),
        ({"security_groups": ["a", "b"]}, {"security_groups": "b"}, True),
        ({"security_groups": "b"}, {"security_groups": ["a", "b"]}, True),
        ({"subnet_id": "s"}, {"subnet_id": ["t"]}, False),
        # Tuples are not lists: compared whole.
        ({"vpc_id": ("a",)}, {"vpc_id": ["a"]}, False),
        ({"vpc_id": ("a",)}, {"vpc_id": ("a",)}, True),
        # Dicts: equal, or contained in a list.
        ({"vpc_id": {"k": 1}}, {"vpc_id": {"k": 1}}, True),
        ({"vpc_id": {"k": 1}}, {"vpc_id": [{"k": 1}]}, True),
        ({"vpc_id": [{"k": 1}]}, {"vpc_id": {"k": 2}}, False),
        # Numbers compare by value.
        ({"vpc_id": 1}, {"vpc_id": [1.0]}, True),
        ({"iam_role": "r"}, {"iam_role": "r"}, True),
        ({"kms_key_id": "k"}, {"kms_key_id": "k"}, True),
        # Any one field is enough.
        ({"vpc_id": "v", "kms_key_id": "k"}, {"vpc_id": "w", "kms_key_id": "k"}, True),
        # Fields outside the five never count.
        ({"VpcId": "v", "role": "r"}, {"VpcId": "v", "role": "r"}, False),
    ],
)
def test_relationship_rules(detector, one, two, related):
    assert detector._resources_are_related(one, two) is related


def test_earlier_field_match_returns_before_an_unhashable_list(detector):
    one = {"vpc_id": "v", "security_groups": [{"a": 1}]}
    assert detector._resources_are_related(one, dict(one)) is True


def test_two_lists_of_dicts_raise(detector):
    one = {"security_groups": [{"a": 1}]}
    with pytest.raises(TypeError, match="unhashable type: 'dict'"):
        detector._resources_are_related(one, dict(one))
