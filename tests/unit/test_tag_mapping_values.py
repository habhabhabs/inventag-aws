"""Tag mapping values: lookup, defaults, validation, and tags from both discovery paths."""

import boto3
import pytest
import yaml
from moto import mock_aws

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.discovery.tag_mapping import TagMapping, TagMappingEngine

R = "us-east-1"


def _engine(tmp_path, mappings):
    path = tmp_path / "tags.yaml"
    path.write_text(yaml.safe_dump({"tag_mappings": mappings}))
    engine = TagMappingEngine(str(path))
    assert engine.last_reload is not None
    return engine


ENV = {
    "tag": "Environment",
    "name": "Env",
    "default_value": "Unknown",
    "normalize_function": "lowercase",
    "validation_pattern": r"^(dev|test|prod)$",
}


def test_tag_key_lookup_is_case_insensitive_by_default(tmp_path):
    engine = _engine(tmp_path, [ENV])
    result = engine.extract_custom_attributes({"tags": {"environment": "PROD"}})
    assert result.mapped_attributes == {"Env": "prod"}
    assert result.validation_errors == []


def test_tag_key_lookup_can_be_case_sensitive(tmp_path):
    engine = _engine(tmp_path, [{**ENV, "case_sensitive": True}])
    result = engine.extract_custom_attributes({"tags": {"environment": "prod"}})
    assert result.mapped_attributes == {"Env": "unknown"}


def test_aws_list_form_tags_are_read():
    engine = TagMappingEngine()
    engine.mappings.clear()
    engine.add_mapping(TagMapping(tag="Owner", name="Owner", default_value="-"))
    result = engine.extract_custom_attributes(
        {"tags": [{"Key": "Owner", "Value": "alex"}]}
    )
    assert result.mapped_attributes == {"Owner": "alex"}


def test_missing_tag_uses_default_and_is_not_a_validation_error(tmp_path):
    engine = _engine(tmp_path, [ENV])
    result = engine.extract_custom_attributes({"tags": {}})
    assert result.mapped_attributes == {
        "Env": "unknown"
    }  # the default is normalized too
    assert result.validation_errors == []


def test_bad_value_is_a_validation_error(tmp_path):
    engine = _engine(tmp_path, [ENV])
    result = engine.extract_custom_attributes({"tags": {"Environment": "Sandbox"}})
    assert len(result.validation_errors) == 1
    assert "sandbox" in result.validation_errors[0]


def test_missing_required_tag_is_reported(tmp_path):
    engine = _engine(tmp_path, [{**ENV, "required": True}])
    result = engine.extract_custom_attributes({"tags": {"Environment": "  "}})
    assert result.missing_required_tags == ["Environment"]
    report = engine.generate_validation_report(
        [{"tags": {}}, {"tags": {"Environment": "dev"}}]
    )
    assert report["valid_resources"] == 1 and report["invalid_resources"] == 1


def test_tags_that_are_not_a_mapping_do_not_crash(tmp_path):
    engine = _engine(tmp_path, [ENV])
    assert engine.extract_custom_attributes({"tags": None}).mapped_attributes == {
        "Env": "unknown"
    }
    assert engine.extract_custom_attributes({}).mapped_attributes == {"Env": "unknown"}


@pytest.fixture(scope="module")
def world():
    tags = [{"Key": "Owner", "Value": "alex"}]
    with mock_aws():
        boto3.client("dynamodb", region_name=R).create_table(
            TableName="tbl1",
            KeySchema=[{"AttributeName": "k", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "k", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
            Tags=tags,
        )
        boto3.client("sqs", region_name=R).create_queue(
            QueueName="q1", tags={"Owner": "alex"}
        )
        boto3.client("sns", region_name=R).create_topic(Name="t1", Tags=tags)
        s3 = boto3.client("s3", region_name=R)
        s3.create_bucket(Bucket="bkt1")
        s3.put_bucket_tagging(Bucket="bkt1", Tagging={"TagSet": tags})
        yield


@pytest.mark.parametrize("mode", ["auto", "always"])
def test_mapped_owner_column_is_right_for_tagging_api_and_service_resources(
    world, tmp_path, mode
):
    found = ComprehensiveAWSDiscovery(
        regions=[R], fallback_display_mode=mode, enable_billing_validation=False
    ).discover_all_resources()
    engine = _engine(
        tmp_path, [{"tag": "Owner", "name": "Owner", "default_value": "-"}]
    )
    wanted = {"tbl1", "q1", "t1", "bkt1"}
    seen = {}
    for resource in found:
        name = (resource.get("resource_name") or resource["resource_id"]).split(":")[-1]
        if name in wanted:
            value = engine.extract_custom_attributes(resource).mapped_attributes
            seen.setdefault(name, []).append(
                (value["Owner"], resource["discovered_via"])
            )
    assert set(seen) == wanted
    for name, rows in seen.items():
        assert len(rows) == 1, (name, rows)  # no duplicate from the two paths
        assert rows[0][0] == "alex", (name, rows)
