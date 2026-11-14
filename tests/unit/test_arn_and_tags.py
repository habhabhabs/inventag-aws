"""ARNs and tags, service by service, against moto.

The Resource Groups Tagging API returns real ARNs, so it is the reference:
every ARN it returns must match a discovered resource that carries the tags,
and with ``--fallback-display always`` no resource may appear twice.
"""

import io
import json
import zipfile

import boto3
import pytest
from moto import mock_aws

from inventag.discovery.arn_utils import (
    ResourceArnIndex,
    build_arn,
    dedupe_key,
    normalize_arn,
    sqs_arn_from_url,
)
from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

R = "us-east-1"
ACCT = "123456789012"
TAGS = [{"Key": "Owner", "Value": "alex"}]
TAGD = {"Owner": "alex"}


def _try(fn):
    try:
        return fn()
    except Exception:  # a service moto does not implement
        return None


@pytest.fixture(scope="module")
def world():
    with mock_aws():
        ids = {}
        iam = boto3.client("iam")
        role = iam.create_role(RoleName="r", AssumeRolePolicyDocument="{}", Tags=TAGS)
        ids["role"] = role["Role"]["Arn"]
        iam.create_user(UserName="u1", Tags=TAGS)
        ec2 = boto3.client("ec2", region_name=R)
        vpc = ec2.create_vpc(
            CidrBlock="10.0.0.0/16",
            TagSpecifications=[{"ResourceType": "vpc", "Tags": TAGS}],
        )["Vpc"]["VpcId"]
        ids["vpc"] = vpc
        ids["subnet"] = ec2.create_subnet(
            VpcId=vpc,
            CidrBlock="10.0.1.0/24",
            TagSpecifications=[{"ResourceType": "subnet", "Tags": TAGS}],
        )["Subnet"]["SubnetId"]
        ids["sg"] = ec2.create_security_group(
            GroupName="sg1",
            Description="d",
            VpcId=vpc,
            TagSpecifications=[{"ResourceType": "security-group", "Tags": TAGS}],
        )["GroupId"]
        ids["rtb"] = ec2.create_route_table(
            VpcId=vpc, TagSpecifications=[{"ResourceType": "route-table", "Tags": TAGS}]
        )["RouteTable"]["RouteTableId"]
        ids["acl"] = ec2.create_network_acl(
            VpcId=vpc, TagSpecifications=[{"ResourceType": "network-acl", "Tags": TAGS}]
        )["NetworkAcl"]["NetworkAclId"]
        ids["igw"] = ec2.create_internet_gateway(
            TagSpecifications=[{"ResourceType": "internet-gateway", "Tags": TAGS}]
        )["InternetGateway"]["InternetGatewayId"]
        eip = ec2.allocate_address(
            Domain="vpc",
            TagSpecifications=[{"ResourceType": "elastic-ip", "Tags": TAGS}],
        )
        ids["eip"] = eip["AllocationId"]
        ids["nat"] = ec2.create_nat_gateway(
            SubnetId=ids["subnet"],
            AllocationId=ids["eip"],
            TagSpecifications=[{"ResourceType": "natgateway", "Tags": TAGS}],
        )["NatGateway"]["NatGatewayId"]
        ids["keypair"] = ec2.create_key_pair(
            KeyName="kp1",
            TagSpecifications=[{"ResourceType": "key-pair", "Tags": TAGS}],
        )["KeyPairId"]
        ids["vol"] = ec2.create_volume(
            AvailabilityZone="us-east-1a",
            Size=1,
            TagSpecifications=[{"ResourceType": "volume", "Tags": TAGS}],
        )["VolumeId"]
        ids["snap"] = ec2.create_snapshot(
            VolumeId=ids["vol"],
            TagSpecifications=[{"ResourceType": "snapshot", "Tags": TAGS}],
        )["SnapshotId"]
        # A fixed image ID: moto accepts any ID, so the test does not depend on
        # which default AMIs moto has loaded (tests/conftest.py switches them off).
        ids["instance"] = ec2.run_instances(
            ImageId="ami-12c6146b",
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[{"ResourceType": "instance", "Tags": TAGS}],
        )["Instances"][0]["InstanceId"]

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.py", "def h(e, c): pass")
        boto3.client("lambda", region_name=R).create_function(
            FunctionName="fn1",
            Runtime="python3.12",
            Role=ids["role"],
            Handler="a.h",
            Code={"ZipFile": buf.getvalue()},
            Tags=TAGD,
        )
        rds = boto3.client("rds", region_name=R)
        rds.create_db_instance(
            DBInstanceIdentifier="db1",
            DBInstanceClass="db.t3.micro",
            Engine="postgres",
            MasterUsername="u",
            MasterUserPassword="password123",
            AllocatedStorage=20,
            Tags=TAGS,
        )
        _try(
            lambda: rds.create_db_cluster(
                DBClusterIdentifier="cl1",
                Engine="aurora-postgresql",
                MasterUsername="u",
                MasterUserPassword="password123",
                Tags=TAGS,
            )
        )
        _try(
            lambda: rds.create_db_snapshot(
                DBInstanceIdentifier="db1", DBSnapshotIdentifier="snap1", Tags=TAGS
            )
        )
        _try(
            lambda: rds.create_db_parameter_group(
                DBParameterGroupName="pg1",
                DBParameterGroupFamily="postgres13",
                Description="d",
                Tags=TAGS,
            )
        )
        boto3.client("dynamodb", region_name=R).create_table(
            TableName="tbl1",
            KeySchema=[{"AttributeName": "k", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "k", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
            Tags=TAGS,
        )
        boto3.client("sqs", region_name=R).create_queue(QueueName="q1", tags=TAGD)
        boto3.client("sns", region_name=R).create_topic(Name="t1", Tags=TAGS)
        s3 = boto3.client("s3", region_name=R)
        s3.create_bucket(Bucket="bkt1")
        s3.put_bucket_tagging(Bucket="bkt1", Tagging={"TagSet": TAGS})
        _try(
            lambda: boto3.client("elb", region_name=R).create_load_balancer(
                LoadBalancerName="lb1",
                Listeners=[
                    {"Protocol": "http", "LoadBalancerPort": 80, "InstancePort": 80}
                ],
                AvailabilityZones=["us-east-1a"],
                Tags=TAGS,
            )
        )
        elbv2 = boto3.client("elbv2", region_name=R)
        sub2 = ec2.create_subnet(
            VpcId=vpc, CidrBlock="10.0.2.0/24", AvailabilityZone="us-east-1b"
        )["Subnet"]["SubnetId"]
        _try(
            lambda: elbv2.create_load_balancer(
                Name="alb1",
                Subnets=[ids["subnet"], sub2],
                SecurityGroups=[ids["sg"]],
                Tags=TAGS,
            )
        )
        _try(
            lambda: elbv2.create_target_group(
                Name="tg1", Protocol="HTTP", Port=80, VpcId=vpc, Tags=TAGS
            )
        )
        ecs = boto3.client("ecs", region_name=R)
        _try(
            lambda: ecs.create_cluster(
                clusterName="c1", tags=[{"key": "Owner", "value": "alex"}]
            )
        )
        _try(
            lambda: boto3.client("eks", region_name=R).create_cluster(
                name="k1",
                roleArn=ids["role"],
                resourcesVpcConfig={"subnetIds": [ids["subnet"]]},
                tags=TAGD,
            )
        )
        glue = boto3.client("glue", region_name=R)
        _try(lambda: glue.create_database(DatabaseInput={"Name": "gdb1"}, Tags=TAGD))
        _try(
            lambda: glue.create_job(
                Name="gj1",
                Role=ids["role"],
                Command={"Name": "glueetl", "ScriptLocation": "s3://x/y"},
                Tags=TAGD,
            )
        )
        _try(
            lambda: glue.create_crawler(
                Name="gc1",
                Role=ids["role"],
                Targets={"S3Targets": [{"Path": "s3://x"}]},
                Tags=TAGD,
            )
        )
        _try(
            lambda: boto3.client("apigateway", region_name=R).create_rest_api(
                name="api1", tags=TAGD
            )
        )
        template = json.dumps({"Resources": {"Q": {"Type": "AWS::SQS::Queue"}}})
        cfn = boto3.client("cloudformation", region_name=R)
        _try(
            lambda: cfn.create_stack(StackName="stk1", TemplateBody=template, Tags=TAGS)
        )
        _try(
            lambda: boto3.client("acm", region_name=R).request_certificate(
                DomainName="example.com", Tags=TAGS
            )
        )
        s3.create_bucket(Bucket="trailbkt")
        _try(
            lambda: boto3.client("cloudtrail", region_name=R).create_trail(
                Name="tr1", S3BucketName="trailbkt", TagsList=TAGS
            )
        )
        ev = boto3.client("events", region_name=R)
        _try(
            lambda: ev.put_rule(
                Name="rule1", ScheduleExpression="rate(5 minutes)", Tags=TAGS
            )
        )
        _try(lambda: ev.create_event_bus(Name="bus1", Tags=TAGS))
        kms = boto3.client("kms", region_name=R)
        key = _try(
            lambda: kms.create_key(Tags=[{"TagKey": "Owner", "TagValue": "alex"}])
        )
        if key:
            ids["kms"] = key["KeyMetadata"]["KeyId"]
            kms.create_alias(AliasName="alias/mykey", TargetKeyId=ids["kms"])
        hz = _try(
            lambda: boto3.client("route53", region_name=R).create_hosted_zone(
                Name="example.com", CallerReference="x"
            )
        )
        if hz:
            ids["hz"] = hz["HostedZone"]["Id"].split("/")[-1]
        cw = boto3.client("cloudwatch", region_name=R)
        _try(
            lambda: cw.put_metric_alarm(
                AlarmName="al1",
                MetricName="m",
                Namespace="n",
                Statistic="Average",
                Period=60,
                EvaluationPeriods=1,
                Threshold=1.0,
                ComparisonOperator="GreaterThanThreshold",
                Tags=TAGS,
            )
        )
        yield ids


def _discover(regions, mode="auto"):
    disc = ComprehensiveAWSDiscovery(
        regions=regions, fallback_display_mode=mode, enable_billing_validation=False
    )
    return disc.discover_all_resources()


@pytest.fixture(scope="module")
def found(world):
    return _discover([R], "always")


@pytest.fixture(scope="module")
def found_auto(world):
    return _discover([R], "auto")


def _by_arn(resources):
    return {normalize_arn(r["arn"]): r for r in resources}


def test_every_tagging_api_arn_matches_one_tagged_resource(world, found):
    """moto's tagging API is the reference for the real ARN of each service."""
    client = boto3.client("resourcegroupstaggingapi", region_name=R)
    reference = [
        m
        for page in client.get_paginator("get_resources").paginate()
        for m in page["ResourceTagMappingList"]
        if m["Tags"]
    ]
    assert len(reference) >= 20, "the reference list should cover many services"
    by_arn = _by_arn(found)
    problems = []
    for mapping in reference:
        arn = mapping["ResourceARN"]
        res = by_arn.get(normalize_arn(arn))
        if res is None:
            problems.append(f"no resource for {arn}")
            continue
        if res.get("resource_type") == "Unknown":
            problems.append(f"{arn} only found as type Unknown")
        want = {t["Key"]: t["Value"] for t in mapping["Tags"]}
        if any(res["tags"].get(k) != v for k, v in want.items()):
            problems.append(f"{arn} lost its tags: {res['tags']}")
    assert not problems, problems


def test_no_resource_appears_twice_with_always(found):
    keys = [dedupe_key(r) for r in found if r.get("arn")]
    dupes = {k for k in keys if keys.count(k) > 1}
    assert not dupes
    assert not [
        r
        for r in found
        if r["resource_type"] == "Unknown"
        and r["tags"].get("Owner")
        and any(
            f is not r
            and f["resource_id"] == r["resource_id"]
            and f["service"] == r["service"]
            for f in found
        )
    ]


def _expected(world):
    ids = world
    return {
        ("LAMBDA", "Function", "fn1"): f"arn:aws:lambda:{R}:{ACCT}:function:fn1",
        ("RDS", "DBInstance", "db1"): f"arn:aws:rds:{R}:{ACCT}:db:db1",
        ("DYNAMODB", "Table", "tbl1"): f"arn:aws:dynamodb:{R}:{ACCT}:table/tbl1",
        ("SQS", "Queue", None): f"arn:aws:sqs:{R}:{ACCT}:q1",
        ("SNS", "Topic", None): f"arn:aws:sns:{R}:{ACCT}:t1",
        ("VPC", "VPC", ids["vpc"]): f"arn:aws:ec2:{R}:{ACCT}:vpc/{ids['vpc']}",
        (
            "VPC",
            "Subnet",
            ids["subnet"],
        ): f"arn:aws:ec2:{R}:{ACCT}:subnet/{ids['subnet']}",
        (
            "VPC",
            "SecurityGroup",
            ids["sg"],
        ): f"arn:aws:ec2:{R}:{ACCT}:security-group/{ids['sg']}",
        (
            "VPC",
            "RouteTable",
            ids["rtb"],
        ): f"arn:aws:ec2:{R}:{ACCT}:route-table/{ids['rtb']}",
        (
            "VPC",
            "NetworkAcl",
            ids["acl"],
        ): f"arn:aws:ec2:{R}:{ACCT}:network-acl/{ids['acl']}",
        (
            "VPC",
            "InternetGateway",
            ids["igw"],
        ): f"arn:aws:ec2:{R}:{ACCT}:internet-gateway/{ids['igw']}",
        (
            "VPC",
            "NatGateway",
            ids["nat"],
        ): f"arn:aws:ec2:{R}:{ACCT}:natgateway/{ids['nat']}",
        (
            "VPC",
            "ElasticIP",
            ids["eip"],
        ): f"arn:aws:ec2:{R}:{ACCT}:elastic-ip/{ids['eip']}",
        (
            "EC2",
            "Instance",
            ids["instance"],
        ): f"arn:aws:ec2:{R}:{ACCT}:instance/{ids['instance']}",
        ("EC2", "Volume", ids["vol"]): f"arn:aws:ec2:{R}:{ACCT}:volume/{ids['vol']}",
        ("EC2", "Snapshot", ids["snap"]): f"arn:aws:ec2:{R}::snapshot/{ids['snap']}",
        ("EC2", "KeyPair", "kp1"): f"arn:aws:ec2:{R}:{ACCT}:key-pair/{ids['keypair']}",
        ("S3", "Bucket", "bkt1"): "arn:aws:s3:::bkt1",
        ("IAM", "Role", "r"): f"arn:aws:iam::{ACCT}:role/r",
        ("IAM", "User", "u1"): f"arn:aws:iam::{ACCT}:user/u1",
        (
            "ELB",
            "LoadBalancer",
            "lb1",
        ): f"arn:aws:elasticloadbalancing:{R}:{ACCT}:loadbalancer/lb1",
        ("ECS", "Cluster", None): f"arn:aws:ecs:{R}:{ACCT}:cluster/c1",
        ("EKS", "Cluster", "k1"): f"arn:aws:eks:{R}:{ACCT}:cluster/k1",
        ("GLUE", "Database", "gdb1"): f"arn:aws:glue:{R}:{ACCT}:database/gdb1",
        ("GLUE", "Job", "gj1"): f"arn:aws:glue:{R}:{ACCT}:job/gj1",
        ("GLUE", "Crawler", "gc1"): f"arn:aws:glue:{R}:{ACCT}:crawler/gc1",
        ("EVENTS", "Rule", "rule1"): f"arn:aws:events:{R}:{ACCT}:rule/rule1",
        ("EVENTS", "EventBus", "bus1"): f"arn:aws:events:{R}:{ACCT}:event-bus/bus1",
        ("KMS", "Alias", "alias/mykey"): f"arn:aws:kms:{R}:{ACCT}:alias/mykey",
        (
            "ROUTE53",
            "HostedZone",
            None,
        ): f"arn:aws:route53:::hostedzone/{ids.get('hz')}",
        ("CLOUDWATCH", "Alarm", "al1"): f"arn:aws:cloudwatch:{R}:{ACCT}:alarm:al1",
    }


def test_arn_equals_the_real_aws_form_per_service(world, found):
    problems = []
    for (service, rtype, rid), want in _expected(world).items():
        matches = [
            r
            for r in found
            if r["service"] == service
            and r["resource_type"] == rtype
            and (rid is None or rid in (r["resource_id"], r.get("resource_name")))
        ]
        if not matches:
            if service in (
                "ECS",
                "EKS",
                "GLUE",
                "EVENTS",
                "ROUTE53",
                "CLOUDWATCH",
                "ELB",
                "KMS",
            ):
                continue  # moto may not implement every call
            problems.append(f"{service} {rtype} {rid} not discovered")
            continue
        arns = {r["arn"] for r in matches}
        if want not in arns:
            problems.append(f"{service} {rtype} {rid}: {arns} != {want}")
    assert not problems, problems


@pytest.mark.parametrize(
    "service,rtype,rid",
    [
        ("LAMBDA", "Function", "fn1"),
        ("RDS", "DBInstance", "db1"),
        ("DYNAMODB", "Table", "tbl1"),
        ("SQS", "Queue", None),
        ("SNS", "Topic", None),
        ("VPC", "VPC", "vpc"),
        ("VPC", "Subnet", "subnet"),
        ("VPC", "SecurityGroup", "sg"),
        ("VPC", "RouteTable", "rtb"),
        ("VPC", "InternetGateway", "igw"),
        ("VPC", "NatGateway", "nat"),
        ("EC2", "Instance", "instance"),
        ("EC2", "Volume", "vol"),
        ("EC2", "Snapshot", "snap"),
        ("S3", "Bucket", "bkt1"),
    ],
)
def test_tagged_resource_has_its_tags_in_both_fallback_modes(
    world, found, found_auto, service, rtype, rid
):
    for mode in ("auto", "always"):
        resources = found if mode == "always" else found_auto
        want_id = world.get(rid, rid)
        matches = [
            r
            for r in resources
            if r["service"] == service
            and r["resource_type"] == rtype
            and (
                want_id is None or want_id in (r["resource_id"], r.get("resource_name"))
            )
        ]
        assert matches, f"{service} {rtype} missing in {mode} mode"
        assert any(r["tags"].get("Owner") == "alex" for r in matches), (
            service,
            rtype,
            mode,
        )


def test_build_arn_forms_without_a_list_call_arn():
    assert (
        build_arn("lambda", "Function", "f", R, ACCT)
        == f"arn:aws:lambda:{R}:{ACCT}:function:f"
    )
    assert (
        build_arn("rds", "DBCluster", "c", R, ACCT)
        == f"arn:aws:rds:{R}:{ACCT}:cluster:c"
    )
    assert (
        build_arn("rds", "DBSnapshot", "s", R, ACCT)
        == f"arn:aws:rds:{R}:{ACCT}:snapshot:s"
    )
    assert (
        build_arn("vpc", "NatGateway", "nat-1", R, ACCT)
        == f"arn:aws:ec2:{R}:{ACCT}:natgateway/nat-1"
    )
    assert (
        build_arn("ec2", "Snapshot", "snap-1", R, ACCT)
        == f"arn:aws:ec2:{R}::snapshot/snap-1"
    )
    assert build_arn("s3", "Bucket", "b", R, None) == "arn:aws:s3:::b"
    assert build_arn("lambda", "Function", "f", "cn-north-1", ACCT).startswith(
        "arn:aws-cn:"
    )
    url = f"https://sqs.{R}.amazonaws.com/{ACCT}/my-queue"
    assert sqs_arn_from_url(url, R, ACCT) == f"arn:aws:sqs:{R}:{ACCT}:my-queue"
    assert build_arn("sqs", "Queue", url, R, ACCT) == f"arn:aws:sqs:{R}:{ACCT}:my-queue"
    real = f"arn:aws:lambda:{R}:{ACCT}:function:x"
    assert build_arn("lambda", "Function", "x", R, ACCT, {"FunctionArn": real}) == real


@pytest.mark.parametrize(
    "a,b",
    [
        (f"arn:aws:vpc:{R}:{ACCT}:vpc/vpc-1", f"arn:aws:ec2:{R}:{ACCT}:vpc/vpc-1"),
        (
            f"arn:aws:vpc:{R}:{ACCT}:securitygroup/sg-1",
            f"arn:aws:ec2:{R}:{ACCT}:security-group/sg-1",
        ),
        (
            f"arn:aws:lambda:{R}:{ACCT}:function/f",
            f"arn:aws:lambda:{R}:{ACCT}:function:f",
        ),
        (f"arn:aws:rds:{R}:{ACCT}:dbinstance/d", f"arn:aws:rds:{R}:{ACCT}:db:d"),
        (f"arn:aws:ec2:{R}:{ACCT}:snapshot/s", f"arn:aws:ec2:{R}::snapshot/s"),
        (f"arn:aws:SQS:{R}:{ACCT}:q", f"arn:aws:sqs:{R}:{ACCT}:q"),
    ],
)
def test_normalize_arn_ignores_known_spelling_differences(a, b):
    assert normalize_arn(a) == normalize_arn(b)


def test_index_matches_by_service_region_and_name_when_arn_differs():
    resources = [
        {
            "service": "DYNAMODB",
            "resource_type": "Table",
            "resource_id": "tbl1",
            "arn": "tbl1",
            "region": R,
        }
    ]
    index = ResourceArnIndex(resources)
    # The resource's ARN is only a name, but its ID matches the real ARN's tail.
    assert index.find(f"arn:aws:dynamodb:{R}:{ACCT}:table/tbl1") is resources[0]
    assert index.find(f"arn:aws:dynamodb:{R}:{ACCT}:table/other") is None


def test_ambiguous_loose_match_is_not_used():
    resources = [
        {
            "service": "SNS",
            "resource_type": "Topic",
            "resource_id": "t",
            "arn": "x1",
            "region": R,
        },
        {
            "service": "SNS",
            "resource_type": "Topic",
            "resource_id": "t",
            "arn": "x2",
            "region": R,
        },
    ]
    assert ResourceArnIndex(resources).find(f"arn:aws:sns:{R}:{ACCT}:t") is None
