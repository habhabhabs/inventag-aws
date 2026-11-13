"""Tag rules of the legacy ComprehensiveTagComplianceChecker (moto, no network)."""

import csv
import json
import logging

import boto3
import pytest
from moto import mock_aws

from inventag.compliance import ComprehensiveTagComplianceChecker
from inventag.compliance.checker import user_tags

SUMMARY_KEYS = {
    "total_resources",
    "compliant_resources",
    "non_compliant_resources",
    "untagged_resources",
    "compliance_percentage",
    "ignored_policy_fields",
    "check_timestamp",
}


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


def make(required, **kwargs):
    return ComprehensiveTagComplianceChecker(
        regions=["us-east-1"], policy={"required_tags": required}, **kwargs
    )


def res(tags, arn="arn:aws:s3:::b"):
    return {"service": "S3", "type": "Bucket", "id": "b", "arn": arn, "tags": tags}


# ---------------------------------------------------------------- tag rules
def test_required_keys_are_case_sensitive():
    c = make(["Owner"])
    out = c.check_compliance([res({"owner": "a"}), res({"Owner": "a"}, arn="x")])
    assert [r["missing_tags"] for r in out["non_compliant"]] == [["Owner"]]
    assert len(out["compliant"]) == 1


def test_values_are_not_checked_and_empty_value_counts_as_present():
    c = make(["Owner"])
    out = c.check_compliance([res({"Owner": ""}), res({"Owner": "  "}, arn="y")])
    assert len(out["compliant"]) == 2


def test_key_whitespace_is_not_trimmed():
    c = make(["Owner"])
    out = c.check_compliance([res({" Owner": "a"})])
    assert out["non_compliant"][0]["missing_tags"] == ["Owner"]


def test_aws_system_tags_are_not_user_tags():
    c = make(["Owner"])
    only_system = res({"aws:cloudformation:stack-name": "s", "AWS:Foo": "x"})
    out = c.check_compliance([only_system])
    assert len(out["untagged"]) == 1 and not out["non_compliant"]
    assert only_system["tags"]  # input resource is not modified
    mixed = res({"aws:createdBy": "x", "Owner": "a"})
    assert len(make(["Owner"]).check_compliance([mixed])["compliant"]) == 1


def test_resource_without_tags_is_untagged():
    out = make(["Owner"]).check_compliance([res({}), res(None, arn="n")])
    assert len(out["untagged"]) == 2


def test_list_form_tags_are_understood():
    r = res([{"Key": "Owner", "Value": "a"}, {"Key": "aws:x", "Value": "1"}])
    assert user_tags(r) == {"Owner": "a"}
    assert len(make(["Owner"]).check_compliance([r])["compliant"]) == 1


def test_duplicate_required_keys_reported_once():
    out = make(["Owner", "Owner", {"key": "Owner"}]).check_compliance([res({"A": "1"})])
    assert out["non_compliant"][0]["missing_tags"] == ["Owner"]


# --------------------------------------------------------- policy validation
@pytest.mark.parametrize(
    "bad",
    [
        [{"allowed_values": ["a"]}],
        [""],
        [{"key": "  "}],
        [42],
        ["aws:foo"],
        [{"key": "AWS:x"}],
    ],
)
def test_invalid_required_tag_entries_raise(bad):
    with pytest.raises(ValueError):
        make(bad)


def test_unsupported_policy_fields_are_reported_not_silent(caplog):
    policy = {
        "required_tags": ["Owner", {"key": "Env", "allowed_values": ["prod"]}],
        "service_specific": {"EC2": {}},
    }
    with caplog.at_level(logging.WARNING):
        c = ComprehensiveTagComplianceChecker(regions=["us-east-1"], policy=policy)
    assert c.ignored_policy_fields == [
        "required_tags[Env].allowed_values",
        "service_specific",
    ]
    assert "Not enforced" in caplog.text
    out = c.check_compliance([res({"Owner": "a", "Env": "dev"})])
    assert out["summary"]["ignored_policy_fields"] == c.ignored_policy_fields
    assert len(out["compliant"]) == 1  # the value rule is NOT enforced


def test_strict_policy_rejects_unsupported_fields():
    with pytest.raises(ValueError, match="allowed_values"):
        make([{"key": "Env", "allowed_values": ["prod"]}], strict_policy=True)


# ------------------------------------------------------- percentage and JSON
def test_percentage_zero_resources_is_zero():
    assert make(["Owner"]).check_compliance([])["summary"]["compliance_percentage"] == 0


def test_percentage_denominator_includes_untagged_and_rounds_to_two_places():
    c = make(["Owner"])
    out = c.check_compliance(
        [res({"Owner": "a"}, "1"), res({}, "2"), res({"A": "b"}, "3")]
    )
    s = out["summary"]
    assert (s["total_resources"], s["compliant_resources"]) == (3, 1)
    assert (s["non_compliant_resources"], s["untagged_resources"]) == (1, 1)
    assert s["compliance_percentage"] == 33.33


def test_summary_and_result_schema_is_stable(tmp_path):
    c = make(["Owner"])
    out = c.check_compliance([res({"Owner": "a"})])
    assert set(out) == {
        "compliant",
        "non_compliant",
        "untagged",
        "summary",
        "all_discovered_resources",
    }
    assert set(out["summary"]) == SUMMARY_KEYS
    path = tmp_path / "r.json"
    c.save_results(str(path))
    assert set(json.loads(path.read_text())["summary"]) == SUMMARY_KEYS


def test_malformed_entries_are_skipped():
    out = make(["Owner"]).check_compliance(["junk", None, res({"Owner": "a"})])
    assert out["summary"]["total_resources"] == 1


# ------------------------------------------------------------ moto discovery
@mock_aws
def test_discovery_maps_tags_and_arn_parts():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="tagged-bucket")
    s3.put_bucket_tagging(
        Bucket="tagged-bucket",
        Tagging={"TagSet": [{"Key": "Owner", "Value": "a"}]},
    )
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ec2.run_instances(
        ImageId="ami-12345678",
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[
            {"ResourceType": "instance", "Tags": [{"Key": "owner", "Value": "a"}]}
        ],
    )
    c = make(["Owner"])
    found = {r["service"]: r for r in c.discover_all_resources()}
    assert found["S3"]["type"] == "Bucket" and found["S3"]["id"] == "tagged-bucket"
    assert found["EC2"]["type"] == "Instance"
    out = c.check_compliance()
    assert [r["service"] for r in out["compliant"]] == ["S3"]
    assert [r["service"] for r in out["non_compliant"]] == ["EC2"]
    assert out["untagged"] == []


@mock_aws
def test_discovery_does_not_see_resources_that_never_had_tags():
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="bare-bucket")
    assert make(["Owner"]).discover_all_resources() == []


def test_arn_with_colon_separated_resource(monkeypatch):
    arn = "arn:aws:lambda:us-east-1:123456789012:function:my-fn"

    class Pager:
        def paginate(self):
            yield {"ResourceTagMappingList": [{"ResourceARN": arn, "Tags": []}]}

    class Client:
        def get_paginator(self, name):
            return Pager()

    c = make(["Owner"])
    monkeypatch.setattr(c.session, "client", lambda *a, **k: Client())
    (r,) = c.discover_all_resources()
    assert (r["type"], r["id"], r["account_id"]) == (
        "Function",
        "my-fn",
        "123456789012",
    )


# ------------------------------------------------------- BOM status columns
def test_bom_csv_has_real_compliance_status(tmp_path):
    c = make(["Owner"])
    resources = [
        {**res({"Owner": "a"}, "arn:aws:s3:::ok"), "id": "ok"},
        {**res({"X": "1"}, "arn:aws:s3:::bad"), "id": "bad"},
        {**res({}, "arn:aws:s3:::none"), "id": "none"},
    ]
    c.check_compliance(resources)
    result = c.generate_bom_documents(
        output_formats=["csv"],
        output_directory=str(tmp_path),
        enable_vpc_enrichment=False,
        enable_security_analysis=False,
        enable_network_analysis=False,
    )
    with open(result["generated_files"][0], newline="") as f:
        status = {row["id"]: row["compliance_status"] for row in csv.DictReader(f)}
    assert status == {"ok": "Compliant", "bad": "Non-Compliant", "none": "Untagged"}


# ------------------------------------------------------------------ S3 write
@mock_aws
def test_upload_to_s3_refuses_by_default():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="out-bucket")
    c = make(["Owner"])
    c.check_compliance([res({"Owner": "a"})])
    with pytest.raises(PermissionError):
        c.upload_to_s3("out-bucket", "r.json")
    assert "Contents" not in s3.list_objects_v2(Bucket="out-bucket")


@mock_aws
def test_upload_to_s3_with_explicit_opt_in():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="out-bucket")
    c = make(["Owner"])
    c.check_compliance([res({"Owner": "a"})])
    c.upload_to_s3("out-bucket", "r.json", allow_write=True)
    body = s3.get_object(Bucket="out-bucket", Key="r.json")["Body"].read()
    assert json.loads(body)["summary"]["total_resources"] == 1
