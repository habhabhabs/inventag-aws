"""
ARN building, normalising and matching, shared by every discovery path.

Most list calls return a real ARN. Some return only a name or an ID (EC2,
SQS URLs, EKS names, Route 53 zone IDs, ...). For those, :func:`build_arn`
makes the real ARN form. The Resource Groups Tagging API returns real ARNs, so
a built ARN that differs from the real one means tags never reach the report.

:class:`ResourceArnIndex` matches an ARN from the Tagging API to a discovered
resource even when the two differ in small ways (case, ``vpc`` and ``ec2``
service prefix, ``function/x`` and ``function:x``, account ID in snapshot ARNs).
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Keys in a list/describe response that hold the resource's own ARN.
ARN_KEYS = (
    "Arn",
    "ARN",
    "arn",
    "FunctionArn",
    "DBInstanceArn",
    "DBClusterArn",
    "DBSnapshotArn",
    "DBSubnetGroupArn",
    "DBParameterGroupArn",
    "LoadBalancerArn",
    "TargetGroupArn",
    "CertificateArn",
    "TrailARN",
    "KeyArn",
    "AliasArn",
    "AlarmArn",
    "DashboardArn",
    "TopicArn",
    "LayerArn",
    "StackId",
    "ResourceArn",
    "OrganizationArn",
)

# Service names used by InvenTag that are not the ARN service code.
_ARN_SERVICE = {
    "vpc": "ec2",
    "elb": "elasticloadbalancing",
    "elbv2": "elasticloadbalancing",
    "elasticloadbalancingv2": "elasticloadbalancing",
    "cloudwatch events": "events",
    "eventbridge": "events",
    "states": "states",
    "route 53": "route53",
    "key management service": "kms",
}

# ARN resource-type spellings that mean the same thing.
_TYPE_ALIAS = {
    "dbinstance": "db",
    "dbcluster": "cluster",
    "dbsnapshot": "snapshot",
    "dbsubnetgroup": "subgrp",
    "dbparametergroup": "pg",
    "securitygroup": "securitygroup",
    "routetable": "routetable",
    "networkacl": "networkacl",
    "internetgateway": "internetgateway",
    "natgateway": "natgateway",
    "elasticip": "elasticip",
    "keypair": "keypair",
    "loadbalancer": "loadbalancer",
    "eventbus": "eventbus",
    "restapi": "restapis",
}

_EC2_TYPES = {
    "VPC": "vpc",
    "Subnet": "subnet",
    "SecurityGroup": "security-group",
    "InternetGateway": "internet-gateway",
    "NatGateway": "natgateway",
    "RouteTable": "route-table",
    "NetworkAcl": "network-acl",
    "ElasticIP": "elastic-ip",
    "Instance": "instance",
    "Volume": "volume",
    "KeyPair": "key-pair",
}


def partition_for_region(region: Optional[str]) -> str:
    """AWS partition for a region name."""
    region = region or ""
    if region.startswith("cn-"):
        return "aws-cn"
    if region.startswith("us-gov-"):
        return "aws-us-gov"
    for prefix, partition in (
        ("us-iso-", "aws-iso"),
        ("us-isob-", "aws-iso-b"),
        ("eu-isoe-", "aws-iso-e"),
        ("us-isof-", "aws-iso-f"),
        ("eusc-", "aws-eusc"),
    ):
        if region.startswith(prefix):
            return partition
    return "aws"


def parse_arn(arn: str) -> Optional[Dict[str, str]]:
    """Split an ARN into its parts, or None if it is not an ARN."""
    if not isinstance(arn, str) or not arn.startswith("arn:"):
        return None
    parts = arn.split(":", 5)
    if len(parts) < 6:
        return None
    return {
        "partition": parts[1],
        "service": parts[2],
        "region": parts[3],
        "account": parts[4],
        "resource": parts[5],
    }


def arn_service(service: Optional[str]) -> str:
    """The ARN service code for an InvenTag or boto3 service name."""
    name = (service or "").strip().lower()
    return _ARN_SERVICE.get(name, name)


def _split_resource(resource: str) -> Tuple[str, str]:
    """('type', 'id') from the resource part of an ARN. Type may be empty."""
    for i, ch in enumerate(resource):
        if ch in "/:":
            return resource[:i], resource[i + 1 :]
    return "", resource


def _norm_type(rtype: str) -> str:
    key = re.sub(r"[-_]", "", rtype.lower())
    return _TYPE_ALIAS.get(key, key)


def id_tail(arn: str) -> str:
    """Last segment of the resource part (the name or ID)."""
    parsed = parse_arn(arn)
    if not parsed:
        return ""
    return re.split(r"[/:]", parsed["resource"])[-1]


def normalize_arn(arn: str) -> str:
    """A comparison key for an ARN.

    Ignores the partition, upper/lower case of the service and type, the
    ``vpc`` and ``ec2`` service difference, and spelling of the resource type
    (``db``/``dbinstance``, ``security-group``/``securitygroup``). The account
    ID is ignored for EC2 snapshots, whose real ARN has none. The resource ID
    keeps its case.
    """
    parsed = parse_arn(arn)
    if not parsed:
        return (arn or "").strip().lower()
    service = arn_service(parsed["service"])
    rtype, rid = _split_resource(parsed["resource"])
    account = parsed["account"]
    if service == "ec2" and _norm_type(rtype) == "snapshot":
        account = ""
    return f"{service}|{parsed['region'].lower()}|{account}|{_norm_type(rtype)}|{rid}"


def _loose_keys(service: str, region: str, rid: str) -> List[Tuple]:
    return [("id", service, region.lower(), rid.lower())] if rid else []


def extract_arn(raw: Optional[Dict[str, Any]]) -> Optional[str]:
    """The ARN a list/describe response already holds, if any."""
    if not isinstance(raw, dict):
        return None
    for key in ARN_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value.startswith("arn:"):
            return value
    return None


def build_arn(
    service: str,
    resource_type: str,
    resource_id: str,
    region: str,
    account_id: Optional[str],
    raw: Optional[Dict[str, Any]] = None,
) -> str:
    """The real ARN for a resource, from what a list call returns.

    A real ARN in ``raw`` always wins. Otherwise the ARN is built in the form
    AWS uses, which is what the Resource Groups Tagging API returns.
    """
    raw = raw or {}
    found = extract_arn(raw)
    if found:
        return found

    svc = (service or "").lower()
    rtype = resource_type or ""
    rid = str(resource_id or "")
    region = region or ""
    acct = account_id or "unknown"
    part = partition_for_region(region)

    def arn(svc_code: str, reg: str, account: str, resource: str) -> str:
        return f"arn:{part}:{svc_code}:{reg}:{account}:{resource}"

    if svc == "s3":
        return arn("s3", "", "", rid)

    if svc in ("ec2", "vpc"):
        kind = _EC2_TYPES.get(rtype)
        if rtype == "Snapshot":
            return arn("ec2", region, "", f"snapshot/{rid}")
        if rtype == "KeyPair" and raw.get("KeyPairId"):
            rid = raw["KeyPairId"]
        if rtype == "ElasticIP" and raw.get("AllocationId"):
            rid = raw["AllocationId"]
        if kind:
            return arn("ec2", region, acct, f"{kind}/{rid}")

    if svc == "lambda":
        if rtype == "Layer":
            return arn("lambda", region, acct, f"layer:{rid}")
        return arn("lambda", region, acct, f"function:{rid}")

    if svc == "rds":
        prefix = {
            "DBInstance": "db",
            "DBCluster": "cluster",
            "DBSnapshot": "snapshot",
            "DBSubnetGroup": "subgrp",
            "DBParameterGroup": "pg",
        }.get(rtype, "db")
        return arn("rds", region, acct, f"{prefix}:{rid}")

    if svc == "dynamodb":
        return arn("dynamodb", region, acct, f"table/{rid}")

    if svc == "sqs":
        return sqs_arn_from_url(rid, region, acct) or arn(
            "sqs", region, acct, rid.rsplit("/", 1)[-1]
        )

    if svc == "sns":
        if rid.startswith("arn:"):
            return rid
        return arn("sns", region, acct, rid)

    if svc == "elb":
        return arn("elasticloadbalancing", region, acct, f"loadbalancer/{rid}")

    if svc == "elbv2":
        kind = "targetgroup" if rtype == "TargetGroup" else "loadbalancer"
        return arn("elasticloadbalancing", region, acct, f"{kind}/{rid}")

    if svc == "ecs":
        if rid.startswith("arn:"):
            return rid
        kind = "service" if rtype == "Service" else "cluster"
        return arn("ecs", region, acct, f"{kind}/{rid}")

    if svc == "eks":
        if rid.startswith("arn:"):
            return rid
        return arn("eks", region, acct, f"cluster/{rid}")

    if svc == "glue":
        kind = {
            "Database": "database",
            "Job": "job",
            "Crawler": "crawler",
            "Trigger": "trigger",
        }.get(rtype, rtype.lower())
        return arn("glue", region, acct, f"{kind}/{rid}")

    if svc == "apigateway":
        return arn("apigateway", region, "", f"/restapis/{rid}")

    if svc == "cloudformation":
        if rtype == "StackSet":
            return arn(
                "cloudformation",
                region,
                acct,
                f"stackset/{raw.get('StackSetId') or rid}",
            )
        return arn("cloudformation", region, acct, f"stack/{rid}")

    if svc == "acm":
        return rid if rid.startswith("arn:") else arn("acm", region, acct, rid)

    if svc == "cloudtrail":
        return arn("cloudtrail", region, acct, f"trail/{rid}")

    if svc == "events":
        kind = "event-bus" if rtype == "EventBus" else "rule"
        return arn("events", region, acct, f"{kind}/{rid}")

    if svc == "kms":
        if rtype == "Alias":
            name = rid if rid.startswith("alias/") else f"alias/{rid}"
            return arn("kms", region, acct, name)
        return arn("kms", region, acct, f"key/{rid}")

    if svc == "route53":
        return arn("route53", "", "", f"hostedzone/{rid.rsplit('/', 1)[-1]}")

    if svc == "cloudfront":
        return arn("cloudfront", "", acct, f"distribution/{rid}")

    if svc == "workmail":
        return arn("workmail", region, acct, f"organization/{rid}")

    if svc == "cloudwatch":
        if rtype == "Dashboard":
            return arn("cloudwatch", "", acct, f"dashboard/{rid}")
        return arn("cloudwatch", region, acct, f"alarm:{rid}")

    if svc == "iam":
        kind = {
            "User": "user",
            "Role": "role",
            "Policy": "policy",
            "Group": "group",
            "InstanceProfile": "instance-profile",
        }.get(rtype, rtype.lower())
        return arn("iam", "", acct, f"{kind}/{rid}")

    return arn(svc, region, acct, f"{rtype.lower()}/{rid}")


def sqs_arn_from_url(url: str, region: str, account_id: Optional[str]) -> str:
    """``arn:aws:sqs:<region>:<account>:<name>`` from a queue URL."""
    match = re.match(r"^https?://[^/]+/(\d{12})/([^/]+)/?$", url or "")
    if not match:
        return ""
    host_region = re.match(r"^https?://sqs\.([a-z0-9-]+)\.", url)
    reg = host_region.group(1) if host_region else region
    return (
        f"arn:{partition_for_region(reg)}:sqs:{reg}:{match.group(1)}:{match.group(2)}"
    )


def _resource_fields(resource: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """(service, region, type, id) of a resource dict in either key style."""
    arn = resource.get("arn") or ""
    parsed = parse_arn(arn)
    service = arn_service(parsed["service"]) if parsed else ""
    if not service:
        service = arn_service(resource.get("service"))
    rid = str(resource.get("resource_id") or resource.get("id") or "")
    rtype = resource.get("resource_type") or resource.get("type") or ""
    region = parsed["region"] if parsed else (resource.get("region") or "")
    return service, region, rtype, rid


class ResourceArnIndex:
    """Find a discovered resource from an ARN, tolerating small ARN differences.

    Lookup order: the normalised ARN, then (service, region, name/ID) when it
    names exactly one resource, then the resource's own ID.
    """

    def __init__(self, resources: Iterable[Dict[str, Any]] = ()):
        self._exact: Dict[str, List[Dict[str, Any]]] = {}
        self._loose: Dict[Tuple, List[Dict[str, Any]]] = {}
        for resource in resources:
            self.add(resource)

    def add(self, resource: Dict[str, Any]) -> None:
        arn = resource.get("arn") or ""
        if arn:
            self._exact.setdefault(normalize_arn(arn), []).append(resource)
        service, region, _rtype, rid = _resource_fields(resource)
        keys = []
        if arn:
            keys += _loose_keys(service, region, id_tail(arn))
        keys += _loose_keys(service, region, rid)
        keys += _loose_keys(service, region, rid.rsplit("/", 1)[-1])
        seen = set()
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            self._loose.setdefault(key, []).append(resource)

    def find(self, arn: str) -> Optional[Dict[str, Any]]:
        if not arn:
            return None
        hits = self._exact.get(normalize_arn(arn))
        if hits:
            return hits[0]
        parsed = parse_arn(arn)
        if not parsed:
            return None
        service = arn_service(parsed["service"])
        tail = id_tail(arn)
        hits = self._loose.get(("id", service, parsed["region"].lower(), tail.lower()))
        if hits and len({id(h) for h in hits}) == 1:
            return hits[0]
        return None


def dedupe_key(resource: Dict[str, Any]) -> str:
    """Key for removing duplicates: the normalised ARN, else service/type/id."""
    arn = resource.get("arn") or ""
    if arn:
        return "arn:" + normalize_arn(arn)
    service, region, rtype, rid = _resource_fields(resource)
    return f"{service}:{region}:{rtype}:{rid}"
