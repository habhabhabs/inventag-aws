"""Inputs of the byte-equality golden test for ``--finops-checks`` (v1.5.0 P5).

``cases()`` returns ``{name: (rows, units_not_read, run_started)}``: named
corners first, then seeded scenarios built from a fixed pool of rows. Nothing
here reads a clock or the environment, so the inputs are the same on every run.
The expected outputs in ``golden/checks-v143.json`` were produced by
``inventag.finops.checks.run_checks`` of v1.4.3 (base f5ca9e24) before that
module was changed; they are never regenerated from the engine.
"""

from __future__ import annotations

import datetime as dt
import random
from typing import Any, Dict, List, Optional, Tuple

UTC = dt.timezone.utc
A, B = "111111111111", "222222222222"
T0 = dt.datetime(2026, 11, 20, 0, 0, 0, tzinfo=UTC)
FULL_TAGS = {
    "CostCenter": "CC-1234",
    "Owner": "team",
    "Project": "p",
    "Environment": "prod",
}


def arn(service: str, region: str, account: str, resource: str) -> str:
    return f"arn:aws:{service}:{region}:{account}:{resource}"


def row(
    service: str,
    rtype: str,
    rid: str,
    *,
    resource_arn: Optional[str] = None,
    region: str = "us-east-1",
    account: str = A,
    raw: Any = "unset",
    tags: Any = "full",
    detail: str = "full",
    name: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "service": service,
        "resource_type": rtype,
        "resource_id": rid,
        "resource_name": name,
        "arn": resource_arn if resource_arn is not None else "",
        "region": region,
        "source_account_id": account,
        "detail_level": detail,
        "tags": dict(FULL_TAGS) if tags == "full" else tags,
    }
    if raw != "unset":
        out["raw_data"] = raw
    out.update(extra)
    return out


def unit(service: str, region: str = "us-east-1", account: str = A, **kw: Any):
    out = {
        "account": account,
        "service": service,
        "region": region,
        "source": "service-api",
        "outcome": "throttled",
    }
    out.update(kw)
    return out


def tagging_unit(region: str = "us-east-1", account: str = A, outcome: str = "denied"):
    return unit(
        "resourcegroupstaggingapi",
        region,
        account,
        source="tagging-api",
        outcome=outcome,
    )


LB2 = arn("elasticloadbalancing", "us-east-1", A, "loadbalancer/app/web/1")
LB2B = arn("elasticloadbalancing", "us-east-1", A, "loadbalancer/app/old/2")
LB2C = arn("elasticloadbalancing", "eu-west-1", A, "loadbalancer/app/eu/3")
LBC = arn("elasticloadbalancing", "us-east-1", A, "loadbalancer/classic-a")


def v2(rid, lb_arn=LB2, **kw):
    raw = kw.pop("raw", {"LoadBalancerArn": lb_arn})
    return row(
        "ELBV2", "LoadBalancerV2", rid, resource_arn=lb_arn, raw=raw, name=rid, **kw
    )


def group(rid, arns, **kw):
    raw = kw.pop("raw", {"LoadBalancerArns": arns})
    return row("ELBV2", "TargetGroup", rid, raw=raw, name=rid, **kw)


def classic(rid, instances, **kw):
    raw = kw.pop("raw", {"Instances": instances})
    return row("ELB", "LoadBalancer", rid, resource_arn=LBC, raw=raw, name=rid, **kw)


def volume(rid, state, **kw):
    raw = kw.pop("raw", {"State": state})
    return row("EC2", "Volume", rid, raw=raw, **kw)


def address(rid, public="203.0.113.5", assoc="unset", **kw):
    raw = {"PublicIp": public}
    if assoc != "unset":
        raw["AssociationId"] = assoc
    return row("VPC", "ElasticIP", rid, raw=kw.pop("raw", raw), **kw)


def snapshot(rid, started, **kw):
    return row("EC2", "Snapshot", rid, raw=kw.pop("raw", {"StartTime": started}), **kw)


def instance(rid, state, **kw):
    raw = kw.pop("raw", {"State": state})
    return row("EC2", "Instance", rid, raw=raw, **kw)


def identity(service, rtype, rid, resource_arn, **kw):
    return row(
        service,
        rtype,
        rid,
        resource_arn=resource_arn,
        detail="identity",
        **kw,
    )


def _named() -> Dict[str, Tuple[list, list, Optional[dt.datetime]]]:
    c: Dict[str, Tuple[list, list, Optional[dt.datetime]]] = {}

    c["empty"] = ([], [], T0)
    c["no rows, units only"] = ([], [unit("ec2"), tagging_unit()], T0)
    c["non-dict entries"] = (
        [None, 5, "x", volume("v", "available")],
        [None, "u", unit("ec2")],
        T0,
    )
    # FIN-001
    for label, state in (
        ("available", "available"),
        ("in-use", "in-use"),
        ("empty", ""),
        ("none", None),
        ("creating", "creating"),
    ):
        c[f"fin1 state {label}"] = ([volume("vol-1", state)], [], T0)
    c["fin1 no State key"] = ([volume("vol-1", None, raw={})], [], T0)
    c["fin1 raw_data missing"] = (
        [row("EC2", "Volume", "vol-1", raw="unset")],
        [],
        T0,
    )
    for label, raw in (("none", None), ("list", []), ("text", "x")):
        c[f"fin1 raw_data {label}"] = (
            [row("EC2", "Volume", "vol-1", raw=raw)],
            [],
            T0,
        )
    c["fin1 identity"] = (
        [
            identity(
                "EC2", "Volume", "vol-1", arn("ec2", "us-east-1", A, "volume/vol-1")
            )
        ],
        [],
        T0,
    )
    c["fin1 identity, lower-case label"] = (
        [
            identity(
                "ec2", "volume", "vol-1", arn("ec2", "us-east-1", A, "volume/vol-1")
            )
        ],
        [],
        T0,
    )
    c["fin1 unit ec2 failed"] = (
        [volume("vol-1", "available"), volume("vol-2", "in-use")],
        [unit("ec2")],
        T0,
    )
    c["fin1 named, other account"] = (
        [
            volume("vol-1", "available", account=B, name="named"),
            volume("vol-2", "available", account="", account_id=A),
        ],
        [],
        T0,
    )
    c["fin1 account_id only"] = (
        [
            {
                **volume("vol-1", "available"),
                "source_account_id": None,
                "account_id": B,
            }
        ],
        [],
        T0,
    )
    c["fin1 id fallback"] = (
        [
            {
                **volume("vol-1", "available"),
                "resource_id": None,
                "id": "alt-id",
            }
        ],
        [],
        T0,
    )
    c["fin1 case of labels"] = (
        [
            {
                **volume("vol-1", "available"),
                "service": "ec2",
                "resource_type": "VOLUME",
            },
        ],
        [],
        T0,
    )
    # FIN-002
    for label, assoc in (
        ("absent", "unset"),
        ("empty", ""),
        ("none", None),
        ("set", "eipassoc-1"),
    ):
        c[f"fin2 assoc {label}"] = ([address("eip-1", assoc=assoc)], [], T0)
    for label, public in (("empty", ""), ("none", None)):
        c[f"fin2 public ip {label}"] = (
            [address("eip-1", public=public, assoc="eipassoc-1")],
            [],
            T0,
        )
    c["fin2 raw_data empty"] = ([address("eip-1", raw={})], [], T0)
    c["fin2 identity"] = (
        [
            identity(
                "VPC",
                "ElasticIP",
                "eip-1",
                arn("ec2", "us-east-1", A, "elastic-ip/eipalloc-1"),
            )
        ],
        [],
        T0,
    )
    c["fin2 unit vpc failed"] = (
        [address("eip-1"), address("eip-2", assoc="x")],
        [unit("vpc"), unit("ec2")],
        T0,
    )
    # FIN-003
    day = dt.timedelta(days=1)
    stamps = {
        "exactly 90 days": T0 - 90 * day,
        "90 days and 1 second": T0 - 90 * day - dt.timedelta(seconds=1),
        "89 days": T0 - 89 * day,
        "future": T0 + day,
    }
    for label, stamp in stamps.items():
        c[f"fin3 {label} iso"] = ([snapshot("snap-1", stamp.isoformat())], [], T0)
        c[f"fin3 {label} z"] = (
            [snapshot("snap-1", stamp.isoformat().replace("+00:00", "Z"))],
            [],
            T0,
        )
        c[f"fin3 {label} datetime"] = ([snapshot("snap-1", stamp)], [], T0)
        c[f"fin3 {label} naive"] = (
            [snapshot("snap-1", stamp.replace(tzinfo=None).isoformat())],
            [],
            T0,
        )
    c["fin3 offset zone"] = (
        [snapshot("snap-1", "2026-08-21T23:30:00-02:00")],
        [],
        T0,
    )
    c["fin3 run in another zone"] = (
        [snapshot("snap-1", "2026-08-21T00:00:00+00:00")],
        [],
        dt.datetime(2026, 11, 20, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=8))),
    )
    for label, value in (
        ("epoch", 1_700_000_000),
        ("garbage", "yesterday"),
        ("empty", ""),
        ("none", None),
        ("date only", "2026-01-01"),
        ("padded", " 2026-01-01T00:00:00+00:00 "),
    ):
        c[f"fin3 start {label}"] = ([snapshot("snap-1", value)], [], T0)
    c["fin3 no StartTime"] = ([snapshot("snap-1", None, raw={})], [], T0)
    c["fin3 run without a start time"] = (
        [
            snapshot("snap-1", "2026-01-01T00:00:00+00:00"),
            snapshot("snap-2", None, raw={}),
            identity(
                "EC2",
                "Snapshot",
                "snap-3",
                arn("ec2", "us-east-1", A, "snapshot/snap-3"),
            ),
        ],
        [],
        None,
    )
    c["fin3 identity"] = (
        [
            identity(
                "EC2",
                "Snapshot",
                "snap-3",
                arn("ec2", "us-east-1", A, "snapshot/snap-3"),
            )
        ],
        [],
        T0,
    )
    # FIN-004
    for label, state in (
        ("stopped", {"Name": "stopped"}),
        ("running", {"Name": "running"}),
        ("empty name", {"Name": ""}),
        ("no name", {}),
        ("none", None),
        ("text", "stopped"),
        ("terminated", {"Name": "terminated"}),
    ):
        c[f"fin4 state {label}"] = ([instance("i-1", state)], [], T0)
    c["fin4 raw_data empty"] = ([instance("i-1", None, raw={})], [], T0)
    c["fin4 identity"] = (
        [
            identity(
                "EC2",
                "Instance",
                "i-1",
                arn("ec2", "us-east-1", A, "instance/i-1"),
            )
        ],
        [],
        T0,
    )
    c["fin4 unit ec2 failed"] = (
        [instance("i-1", {"Name": "stopped"}), instance("i-2", {"Name": "running"})],
        [unit("ec2", outcome="denied")],
        T0,
    )
    # FIN-005, v2
    c["fin5 v2 named"] = ([v2("web"), group("tg", [LB2])], [], T0)
    c["fin5 v2 not named"] = ([v2("web"), group("tg", [LB2B])], [], T0)
    c["fin5 v2 no groups"] = ([v2("web")], [], T0)
    c["fin5 v2 group without list"] = (
        [v2("web"), group("tg", None, raw={})],
        [],
        T0,
    )
    c["fin5 v2 group list text"] = (
        [v2("web"), group("tg", None, raw={"LoadBalancerArns": LB2})],
        [],
        T0,
    )
    c["fin5 v2 group list none"] = (
        [v2("web"), group("tg", None, raw={"LoadBalancerArns": None})],
        [],
        T0,
    )
    c["fin5 v2 group empty list"] = ([v2("web"), group("tg", [])], [], T0)
    c["fin5 v2 group raw none"] = ([v2("web"), group("tg", [], raw=None)], [], T0)
    c["fin5 v2 group identity"] = (
        [
            v2("web"),
            identity(
                "ELBV2",
                "TargetGroup",
                "tg",
                arn("elasticloadbalancing", "us-east-1", A, "targetgroup/tg/9"),
            ),
        ],
        [],
        T0,
    )
    c["fin5 v2 named by one of two groups"] = (
        [
            v2("web"),
            group("tg1", [LB2B]),
            group("tg2", None, raw={}),
            group("t3", [LB2]),
        ],
        [],
        T0,
    )
    c["fin5 v2 group in another region"] = (
        [v2("web"), group("tg", [LB2], region="eu-west-1")],
        [],
        T0,
    )
    c["fin5 v2 group in another account"] = (
        [v2("web"), group("tg", [LB2], account=B)],
        [],
        T0,
    )
    c["fin5 v2 group source_account fallback"] = (
        [v2("web"), {**group("tg", [LB2]), "source_account_id": None, "account_id": A}],
        [],
        T0,
    )
    c["fin5 v2 group names several"] = (
        [v2("web"), v2("old", LB2B), group("tg", [LB2, LB2B, 5, None])],
        [],
        T0,
    )
    c["fin5 v2 listing elbv2 failed here"] = (
        [v2("web"), v2("old", LB2B), group("tg", [LB2])],
        [unit("elbv2")],
        T0,
    )
    c["fin5 v2 listing elbv2 failed elsewhere"] = (
        [v2("web"), group("tg", [LB2B])],
        [unit("elbv2", "eu-west-1"), unit("elbv2", account=B)],
        T0,
    )
    c["fin5 v2 listing elb failed only"] = (
        [v2("web"), group("tg", [LB2B])],
        [unit("elb")],
        T0,
    )
    c["fin5 v2 no arn on lb"] = (
        [v2("web", raw={}), group("tg", [LB2])],
        [],
        T0,
    )
    c["fin5 v2 no arn on lb and listing failed"] = (
        [v2("web", raw={}), group("tg", [LB2])],
        [unit("elbv2")],
        T0,
    )
    c["fin5 v2 empty arn on lb"] = (
        [v2("web", raw={"LoadBalancerArn": ""}), group("tg", [LB2])],
        [],
        T0,
    )
    c["fin5 v2 identity"] = (
        [identity("ELBV2", "LoadBalancerV2", "web", LB2)],
        [],
        T0,
    )
    c["fin5 v2 identity and listing failed"] = (
        [identity("ELBV2", "LoadBalancerV2", "web", LB2)],
        [unit("elbv2")],
        T0,
    )
    c["fin5 v2 region mismatch of arn"] = (
        [v2("eu", LB2C, region="eu-west-1"), group("tg", [LB2C], region="us-east-1")],
        [],
        T0,
    )
    # FIN-005, classic
    for label, instances in (
        ("empty", []),
        ("one", [{"InstanceId": "i-1"}]),
        ("none", None),
        ("text", "i-1"),
        ("mapping", {"a": 1}),
    ):
        c[f"fin5 classic instances {label}"] = ([classic("c", instances)], [], T0)
    c["fin5 classic missing"] = ([classic("c", None, raw={})], [], T0)
    c["fin5 classic raw none"] = ([classic("c", None, raw=None)], [], T0)
    c["fin5 classic identity"] = (
        [identity("ELB", "LoadBalancer", "c", LBC)],
        [],
        T0,
    )
    c["fin5 classic unit elb failed"] = (
        [classic("c", []), classic("d", [{"InstanceId": "i-1"}])],
        [unit("elb")],
        T0,
    )
    c["fin5 classic unit elbv2 failed"] = ([classic("c", [])], [unit("elbv2")], T0)
    c["fin5 units both"] = (
        [classic("c", []), v2("web")],
        [unit("elb"), unit("elbv2", outcome="denied")],
        T0,
    )
    # FIN-006 and tags
    odd_tags = {
        "none": None,
        "empty": {},
        "partial": {"Owner": "x"},
        "wrong values": {
            "CostCenter": "bad",
            "Owner": "x",
            "Project": "p",
            "Environment": "unknown",
        },
        "empty values": {
            "CostCenter": "",
            "Owner": "",
            "Project": "",
            "Environment": "",
        },
        "list form": [
            {"Key": "CostCenter", "Value": "CC-1"},
            {"Key": "Owner", "Value": "o"},
        ],
        "list form full": [
            {"Key": "CostCenter", "Value": "CC-1234"},
            {"Key": "Owner", "Value": "o"},
            {"Key": "Project", "Value": "p"},
            {"Key": "Environment", "Value": "dev"},
        ],
        "other case": {
            "costcenter": "CC-1234",
            "owner": "o",
            "project": "p",
            "environment": "prod",
        },
        "extra keys": {**FULL_TAGS, "Name": "n"},
    }
    for label, tags in odd_tags.items():
        c[f"fin6 tags {label}"] = (
            [
                row("S3", "Bucket", "b", resource_arn="arn:aws:s3:::b", tags=tags),
                volume("vol-1", "in-use", tags=tags),
            ],
            [],
            T0,
        )
    c["fin6 billing source"] = (
        [
            row("Billing", "Service", "s", tags={}, source="billing"),
            row("S3", "Bucket", "b", tags={}, source="other"),
            row("S3", "Bucket", "c", tags={}, source=None),
        ],
        [],
        T0,
    )
    c["fin6 kms alias"] = (
        [
            row("KMS", "Alias", "alias/x", tags={}),
            row("KMS", "Key", "k", tags={}),
        ],
        [],
        T0,
    )
    c["fin6 rows without service"] = (
        [{"resource_id": "x", "tags": {}}, {"tags": {}}, {}],
        [],
        T0,
    )
    c["fin6 sorting of ties"] = (
        [
            row("S3", "Bucket", "same", tags={}),
            row("SQS", "Queue", "same", tags={}),
            row("S3", "Bucket", "same", tags={"Owner": "x"}),
            row("S3", "Bucket", "same", tags={}, region="eu-west-1"),
            row("S3", "Bucket", "same", tags={}, account=B),
        ],
        [],
        T0,
    )
    # tags not read
    c["tags unit, row in the region, keys missing"] = (
        [volume("vol-1", "in-use", tags={})],
        [tagging_unit()],
        T0,
    )
    c["tags unit, row in the region, keys present"] = (
        [volume("vol-1", "in-use")],
        [tagging_unit()],
        T0,
    )
    c["tags unit, row in the region, one key missing"] = (
        [volume("vol-1", "in-use", tags={"Owner": "x", "Project": "p"})],
        [tagging_unit()],
        T0,
    )
    c["tags unit, other region"] = (
        [volume("vol-1", "in-use", tags={}, region="eu-west-1")],
        [tagging_unit()],
        T0,
    )
    c["tags unit, other account"] = (
        [volume("vol-1", "in-use", tags={}, account=B)],
        [tagging_unit(account=A)],
        T0,
    )
    c["tags unit, global row, keys missing"] = (
        [
            row(
                "S3",
                "Bucket",
                "b",
                resource_arn="arn:aws:s3:::b",
                region="global",
                tags={},
            )
        ],
        [tagging_unit("eu-west-1")],
        T0,
    )
    c["tags unit, global row, keys present"] = (
        [row("IAM", "Role", "r", region="global")],
        [tagging_unit("eu-west-1")],
        T0,
    )
    c["tags unit, global row, other account"] = (
        [row("IAM", "Role", "r", region="global", tags={}, account=B)],
        [tagging_unit("eu-west-1", A)],
        T0,
    )
    c["tags unit, global row, unit of global"] = (
        [row("IAM", "Role", "r", region="global", tags={})],
        [tagging_unit("global")],
        T0,
    )
    c["tags unit, global row, none"] = (
        [row("IAM", "Role", "r", region="global", tags={})],
        [],
        T0,
    )
    c["tags unit, identity row, keys missing"] = (
        [
            identity(
                "EC2",
                "Volume",
                "vol-1",
                arn("ec2", "us-east-1", A, "volume/vol-1"),
                tags={},
            )
        ],
        [tagging_unit()],
        T0,
    )
    c["tags unit, mixed accounts"] = (
        [
            volume("vol-1", "in-use", tags={}),
            volume("vol-2", "in-use", tags={}, account=B),
            volume("vol-3", "in-use", tags={}, region="us-west-2"),
            volume("vol-4", "in-use", tags={"Owner": "o"}, region="us-west-2"),
        ],
        [tagging_unit("us-east-1", A), tagging_unit("us-west-2", B)],
        T0,
    )
    c["tags unit, tagging units twice"] = (
        [volume("vol-1", "in-use", tags={})],
        [tagging_unit(outcome="denied"), tagging_unit(outcome="throttled")],
        T0,
    )
    c["tags unit, tagging unit as service-api"] = (
        [volume("vol-1", "in-use", tags={})],
        [unit("resourcegroupstaggingapi")],
        T0,
    )
    # units alone
    c["units, every kind"] = (
        [],
        [
            unit("ec2"),
            unit("vpc", "eu-west-1"),
            unit("elb", account=B),
            unit("elbv2", "ap-southeast-1", outcome="denied"),
            unit("lambda"),
            unit("s3", "global"),
            tagging_unit("eu-west-1"),
        ],
        T0,
    )
    c["units, duplicates"] = (
        [],
        [unit("ec2"), unit("ec2"), unit("ec2", outcome="denied")],
        T0,
    )
    c["units, missing fields"] = (
        [],
        [{}, {"source": "service-api"}, {"service": "ec2"}, {"source": "tagging-api"}],
        T0,
    )
    c["units, upper-case and label services"] = (
        [volume("vol-1", "available")],
        [unit("EC2"), unit("Elbv2"), unit("ELB")],
        T0,
    )
    c["units, ordering"] = (
        [],
        [
            unit("vpc", "b-region", "2"),
            unit("ec2", "a-region", "2"),
            unit("ec2", "b-region", "1"),
            unit("ec2", "a-region", "1"),
            unit("elb", "a-region", "1"),
        ],
        T0,
    )
    c["units, no source"] = (
        [],
        [{"account": A, "service": "ec2", "region": "us-east-1", "outcome": "x"}],
        T0,
    )
    c["units, no outcome"] = (
        [],
        [
            {
                "account": A,
                "service": "ec2",
                "region": "us-east-1",
                "source": "service-api",
            }
        ],
        T0,
    )
    c["units, wafv2 cloudfront and long names"] = (
        [],
        [unit("wafv2-cloudfront", "us-east-1"), unit("efs"), unit("cognito")],
        T0,
    )
    # labels and ARNs that do not agree
    c["labels: lb v2 and group in lower case"] = (
        [
            {**v2("web"), "service": "elbv2", "resource_type": "loadbalancerv2"},
            {**group("tg", [LB2B]), "service": "ELBV2", "resource_type": "TARGETGROUP"},
        ],
        [],
        T0,
    )
    c["labels: classic in upper case"] = (
        [{**classic("c", []), "service": "elb", "resource_type": "LOADBALANCER"}],
        [],
        T0,
    )
    c["labels: identity row labelled for another service"] = (
        [
            identity("S3", "Bucket", "x", arn("ec2", "us-east-1", A, "volume/vol-9")),
            identity("S3", "Bucket", "y", LB2),
            identity("S3", "Bucket", "z", LBC),
            identity("SQS", "Queue", "w", arn("ec2", "us-east-1", A, "instance/i-9")),
        ],
        [],
        T0,
    )
    c["labels: identity row labelled for another kind"] = (
        [
            identity("EC2", "Volume", "x", arn("ec2", "us-east-1", A, "instance/i-9")),
            identity(
                "EC2", "Instance", "y", arn("ec2", "us-east-1", A, "snapshot/s-9")
            ),
            identity("ELB", "LoadBalancer", "z", LB2),
            identity("ELBV2", "LoadBalancerV2", "w", LBC),
        ],
        [],
        T0,
    )
    c["labels: identity row with an arn of no kind"] = (
        [
            identity("EC2", "Volume", "x", "not-an-arn"),
            identity("EC2", "Instance", "y", ""),
            identity("EC2", "Snapshot", "z", arn("ec2", "us-east-1", A, "image/ami-1")),
            identity("VPC", "ElasticIP", "w", arn("ec2", "us-east-1", A, "volume2/v")),
            identity(
                "ELBV2",
                "TargetGroup",
                "t",
                arn("elasticloadbalancing", "us-east-1", A, "targetgroup/tg/9"),
            ),
        ],
        [],
        T0,
    )
    c["labels: full row whose arn is of another kind"] = (
        [
            volume(
                "vol-1",
                "available",
                resource_arn=arn("ec2", "us-east-1", A, "instance/i-1"),
            ),
            instance("i-1", {"Name": "stopped"}, resource_arn=LB2),
        ],
        [],
        T0,
    )
    c["labels: identity group in lower case beside a load balancer"] = (
        [
            v2("web"),
            {
                **identity(
                    "elbv2",
                    "targetgroup",
                    "tg",
                    arn("elasticloadbalancing", "us-east-1", A, "targetgroup/tg/9"),
                ),
            },
        ],
        [],
        T0,
    )
    c["labels: other partition and other account arns"] = (
        [
            identity(
                "EC2", "Volume", "x", "arn:aws-cn:ec2:cn-north-1:333333333333:volume/v"
            ),
            identity("EC2", "Instance", "y", "arn:aws:ec2:::instance/i-1"),
            identity(
                "ELBV2",
                "LoadBalancerV2",
                "z",
                "arn:aws:elasticloadbalancing:us-east-1:111111111111:loadbalancer/net/n/1",
            ),
        ],
        [],
        T0,
    )
    # bad run_started
    c["run_started none"] = ([volume("v", "available")], [], None)
    return c


def _pool() -> List[Dict[str, Any]]:
    pool: List[Dict[str, Any]] = []
    for region in ("us-east-1", "eu-west-1"):
        for account in (A, B):
            kw = {"region": region, "account": account}
            for tags in ("full", {}, {"Owner": "o"}):
                pool.append(volume(f"vol-{len(pool)}", "available", tags=tags, **kw))
            pool.append(volume(f"vol-{len(pool)}", "in-use", **kw))
            pool.append(volume(f"vol-{len(pool)}", None, raw={}, **kw))
            pool.append(address(f"eip-{len(pool)}", **kw))
            pool.append(address(f"eip-{len(pool)}", assoc="x", **kw))
            pool.append(address(f"eip-{len(pool)}", assoc="", tags={}, **kw))
            pool.append(
                snapshot(f"snap-{len(pool)}", "2026-05-01T00:00:00+00:00", **kw)
            )
            pool.append(snapshot(f"snap-{len(pool)}", "2026-11-01T00:00:00Z", **kw))
            pool.append(snapshot(f"snap-{len(pool)}", None, raw={}, **kw))
            pool.append(instance(f"i-{len(pool)}", {"Name": "stopped"}, **kw))
            pool.append(instance(f"i-{len(pool)}", {"Name": "running"}, tags={}, **kw))
            lb = arn("elasticloadbalancing", region, account, "loadbalancer/app/a/1")
            lb2 = arn("elasticloadbalancing", region, account, "loadbalancer/app/b/2")
            pool.append(v2(f"lb-{len(pool)}", lb, **kw))
            pool.append(v2(f"lb-{len(pool)}", lb2, **kw))
            pool.append(group(f"tg-{len(pool)}", [lb], **kw))
            pool.append(group(f"tg-{len(pool)}", None, raw={}, **kw))
            pool.append(classic(f"c-{len(pool)}", [], **kw))
            pool.append(classic(f"c-{len(pool)}", [{"InstanceId": "i"}], **kw))
            pool.append(
                identity(
                    "EC2",
                    "Volume",
                    f"vol-{len(pool)}",
                    arn("ec2", region, account, "volume/vol-x"),
                    **kw,
                )
            )
            pool.append(
                identity(
                    "ELBV2",
                    "LoadBalancerV2",
                    f"lb-{len(pool)}",
                    lb,
                    **kw,
                )
            )
            pool.append(row("S3", "Bucket", f"b-{len(pool)}", tags={}, **kw))
            pool.append(row("SQS", "Queue", f"q-{len(pool)}", **kw))
        pool.append(row("IAM", "Role", f"r-{len(pool)}", region="global", tags={}))
        pool.append(row("IAM", "Role", f"r-{len(pool)}", region="global", account=B))
    return pool


def _scenarios(count: int = 160) -> Dict[str, Tuple[list, list, Optional[dt.datetime]]]:
    rnd = random.Random(150)
    pool = _pool()
    units = [
        unit(s, r, a)
        for s in ("ec2", "vpc", "elb", "elbv2")
        for r in ("us-east-1", "eu-west-1")
        for a in (A, B)
    ] + [
        tagging_unit(r, a) for r in ("us-east-1", "eu-west-1", "global") for a in (A, B)
    ]
    starts = [None, T0, T0 + dt.timedelta(days=100), T0 - dt.timedelta(days=100)]
    out = {}
    for number in range(count):
        rows = rnd.sample(pool, rnd.randint(4, 18))
        chosen = rnd.sample(units, rnd.choice((0, 0, 1, 2, 3, 5)))
        out[f"scenario {number:03d}"] = (rows, chosen, rnd.choice(starts))
    return out


def cases() -> Dict[str, Tuple[list, list, Optional[dt.datetime]]]:
    found = _named()
    found.update(_scenarios())
    return found
