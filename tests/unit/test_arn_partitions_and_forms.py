"""ARN forms for global services, odd resource parts and the GovCloud and China partitions."""

import boto3
import pytest
from moto import mock_aws

from inventag.discovery.arn_utils import (
    ResourceArnIndex,
    build_arn,
    dedupe_key,
    id_tail,
    normalize_arn,
    parse_arn,
    partition_for_region,
    sqs_arn_from_url,
)
from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

ACCT = "123456789012"
TAGS = [{"Key": "Owner", "Value": "alex"}]


@pytest.mark.parametrize(
    "region,partition",
    [
        ("us-east-1", "aws"),
        ("eu-west-2", "aws"),
        ("cn-north-1", "aws-cn"),
        ("cn-northwest-1", "aws-cn"),
        ("us-gov-west-1", "aws-us-gov"),
        ("us-gov-east-1", "aws-us-gov"),
        ("us-iso-east-1", "aws-iso"),
        ("us-isob-east-1", "aws-iso-b"),
        ("eu-isoe-west-1", "aws-iso-e"),
        ("us-isof-south-1", "aws-iso-f"),
        ("eusc-de-east-1", "aws-eusc"),
        ("", "aws"),
        (None, "aws"),
    ],
)
def test_partition_for_region(region, partition):
    assert partition_for_region(region) == partition


@pytest.mark.parametrize(
    "region,partition",
    [("cn-north-1", "aws-cn"), ("us-gov-west-1", "aws-us-gov"), ("us-east-1", "aws")],
)
def test_built_arns_use_the_regions_partition(region, partition):
    p = f"arn:{partition}:"
    assert build_arn("s3", "Bucket", "my.bucket-1", region, None) == (
        f"{p}s3:::my.bucket-1"
    )
    assert build_arn("iam", "Role", "r", region, ACCT) == f"{p}iam::{ACCT}:role/r"
    assert build_arn("iam", "User", "u", region, ACCT) == f"{p}iam::{ACCT}:user/u"
    assert build_arn("iam", "Policy", "pol", region, ACCT) == (
        f"{p}iam::{ACCT}:policy/pol"
    )
    assert build_arn("route53", "HostedZone", "Z123", region, ACCT) == (
        f"{p}route53:::hostedzone/Z123"
    )
    assert build_arn("cloudfront", "Distribution", "E1ABC", region, ACCT) == (
        f"{p}cloudfront::{ACCT}:distribution/E1ABC"
    )
    assert build_arn("lambda", "Function", "f", region, ACCT) == (
        f"{p}lambda:{region}:{ACCT}:function:f"
    )
    assert build_arn("ec2", "Snapshot", "snap-1", region, ACCT) == (
        f"{p}ec2:{region}::snapshot/snap-1"
    )
    assert build_arn("vpc", "SecurityGroup", "sg-1", region, ACCT) == (
        f"{p}ec2:{region}:{ACCT}:security-group/sg-1"
    )
    assert build_arn("dynamodb", "Table", "t", region, ACCT) == (
        f"{p}dynamodb:{region}:{ACCT}:table/t"
    )


def test_route53_zone_id_with_path_prefix_gives_one_clean_arn():
    assert build_arn(
        "route53", "HostedZone", "/hostedzone/Z123", "us-east-1", ACCT
    ) == ("arn:aws:route53:::hostedzone/Z123")


def test_arn_from_the_list_call_always_wins_including_paths():
    role = f"arn:aws:iam::{ACCT}:role/service-role/my-role"
    assert build_arn("iam", "Role", "my-role", "us-east-1", ACCT, {"Arn": role}) == role
    dist = f"arn:aws:cloudfront::{ACCT}:distribution/E1"
    assert (
        build_arn("cloudfront", "Distribution", "E1", "us-east-1", ACCT, {"ARN": dist})
        == dist
    )
    gov = "arn:aws-us-gov:s3:::b"
    assert build_arn("s3", "Bucket", "b", "us-east-1", None, {"Arn": gov}) == gov


def test_sqs_url_in_china_and_govcloud():
    cn = f"https://sqs.cn-north-1.amazonaws.com.cn/{ACCT}/q"
    assert sqs_arn_from_url(cn, "cn-north-1", ACCT) == (
        f"arn:aws-cn:sqs:cn-north-1:{ACCT}:q"
    )
    gov = f"https://sqs.us-gov-west-1.amazonaws.com/{ACCT}/q"
    assert sqs_arn_from_url(gov, "us-gov-west-1", ACCT) == (
        f"arn:aws-us-gov:sqs:us-gov-west-1:{ACCT}:q"
    )


def test_parse_arn_keeps_colons_and_slashes_in_the_resource_part():
    arn = f"arn:aws:logs:us-east-1:{ACCT}:log-group:/aws/lambda/fn:*"
    assert parse_arn(arn)["resource"] == "log-group:/aws/lambda/fn:*"
    assert parse_arn("arn:aws:s3:::bucket/folder/key.txt")["resource"] == (
        "bucket/folder/key.txt"
    )
    assert parse_arn("not-an-arn") is None
    assert parse_arn("arn:aws:s3") is None


def test_id_tail_for_resource_parts_with_colon_and_slash():
    assert id_tail(f"arn:aws:iam::{ACCT}:role/service-role/my-role") == "my-role"
    assert id_tail(f"arn:aws:lambda:us-east-1:{ACCT}:function:fn") == "fn"
    assert id_tail(f"arn:aws:states:us-east-1:{ACCT}:stateMachine:sm") == "sm"


def test_lambda_alias_and_function_stay_distinct():
    fn = f"arn:aws:lambda:us-east-1:{ACCT}:function:fn"
    alias = f"arn:aws:lambda:us-east-1:{ACCT}:function:fn:live"
    assert normalize_arn(fn) != normalize_arn(alias)


def test_partition_is_ignored_when_matching_but_account_and_region_are_not():
    assert normalize_arn(f"arn:aws-us-gov:sqs:us-gov-west-1:{ACCT}:q") == (
        normalize_arn(f"arn:aws:sqs:us-gov-west-1:{ACCT}:q")
    )
    assert normalize_arn(f"arn:aws:sqs:us-east-1:{ACCT}:q") != normalize_arn(
        f"arn:aws:sqs:us-west-2:{ACCT}:q"
    )
    assert normalize_arn(f"arn:aws:sqs:us-east-1:{ACCT}:q") != normalize_arn(
        f"arn:aws:sqs:us-east-1:999999999999:q"
    )


def test_bucket_names_that_differ_only_in_case_are_not_merged_by_id():
    # S3 names are lower case, but the index must not invent matches for IDs
    # that merely look alike in other services.
    resources = [
        {
            "service": "S3",
            "resource_type": "Bucket",
            "resource_id": "b1",
            "arn": "arn:aws:s3:::b1",
            "region": "us-east-1",
        }
    ]
    index = ResourceArnIndex(resources)
    assert index.find("arn:aws:s3:::b1") is resources[0]
    assert index.find("arn:aws:s3:::b2") is None


def test_iam_role_with_path_is_found_by_tagging_api_arn():
    arn = f"arn:aws:iam::{ACCT}:role/service-role/my-role"
    resources = [
        {
            "service": "IAM",
            "resource_type": "Role",
            "resource_id": "my-role",
            "arn": arn,
            "region": "global",
        }
    ]
    assert ResourceArnIndex(resources).find(arn) is resources[0]


def test_dedupe_key_treats_partition_variants_as_one_resource():
    a = {"arn": "arn:aws:s3:::b"}
    b = {"arn": "arn:aws-cn:s3:::b"}
    assert dedupe_key(a) == dedupe_key(b)


@pytest.fixture(scope="module", params=["us-gov-west-1", "cn-north-1"])
def partition_world(request):
    region = request.param
    partition = partition_for_region(region)
    with mock_aws():
        boto3.client("dynamodb", region_name=region).create_table(
            TableName="tbl1",
            KeySchema=[{"AttributeName": "k", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "k", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
            Tags=TAGS,
        )
        boto3.client("sqs", region_name=region).create_queue(
            QueueName="q1", tags={"Owner": "alex"}
        )
        boto3.client("sns", region_name=region).create_topic(Name="t1", Tags=TAGS)
        ec2 = boto3.client("ec2", region_name=region)
        ec2.create_vpc(
            CidrBlock="10.0.0.0/16",
            TagSpecifications=[{"ResourceType": "vpc", "Tags": TAGS}],
        )
        found = ComprehensiveAWSDiscovery(
            regions=[region],
            fallback_display_mode="always",
            enable_billing_validation=False,
        ).discover_all_resources()
        reference = []
        client = boto3.client("resourcegroupstaggingapi", region_name=region)
        for page in client.get_paginator("get_resources").paginate():
            reference.extend(page["ResourceTagMappingList"])
        yield region, partition, found, reference


def test_partition_arns_from_service_path_match_the_tagging_api(partition_world):
    region, partition, found, reference = partition_world
    assert reference, "moto returned no tagged resources"
    by_key = {}
    for resource in found:
        by_key.setdefault(normalize_arn(resource["arn"]), []).append(resource)
    for item in reference:
        arn = item["ResourceARN"]
        assert arn.startswith(f"arn:{partition}:"), arn
        hits = by_key.get(normalize_arn(arn), [])
        assert len(hits) == 1, (arn, [h["arn"] for h in hits])
        assert hits[0]["tags"].get("Owner") == "alex", arn
        assert hits[0]["arn"].startswith(f"arn:{partition}:"), hits[0]["arn"]


def test_every_discovered_arn_in_a_partition_region_uses_that_partition(
    partition_world,
):
    region, partition, found, _ = partition_world
    for resource in found:
        if resource["service"] in ("IAM", "ROUTE53", "CLOUDFRONT"):
            continue
        assert resource["arn"].startswith(f"arn:{partition}:"), resource["arn"]
