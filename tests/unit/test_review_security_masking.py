"""Release-gate review: masking rules added for v1.2.0 (deny-list and logs)."""

import json

import pytest

from inventag.security.redaction import redact
from inventag.security.secret_values import MASK, mask_resource, mask_secret_values

S = "planted-review-secret-7f3a"


@pytest.mark.parametrize(
    "data",
    [
        {"Actions": [{"JobName": "j", "Arguments": {"--jdbc_url": S}}]},
        {"JobRuns": [{"Arguments": {"--x": S}}]},
        {"Outputs": [{"OutputKey": "AccessKeySecret", "OutputValue": S}]},
        {"StackSet": {"TemplateBody": S}},
        {"Endpoint": {"ConnectionString": S}},
        {"Input": json.dumps({"db": {"Password": S}})},
        {"Input": "  " + json.dumps([{"name": "n", "AuthToken": S}])},
        {"Nested": {"Deeper": [{"Payload": json.dumps({"Variables": {"A": S}})}]}},
    ],
)
def test_new_secret_shapes_are_masked(data):
    masked, count = mask_resource(data)
    assert count >= 1
    assert S not in json.dumps(masked)
    assert S in json.dumps(data), "input must not be changed"


def test_names_and_plain_json_text_stay():
    data = {
        "Actions": [{"JobName": "j", "Arguments": {"--jdbc_url": S}}],
        "Outputs": [{"OutputKey": "Endpoint", "OutputValue": S}],
        "Policy": json.dumps({"Version": "2012-10-17", "Statement": []}),
        "Description": "[not json",
    }
    masked = mask_secret_values(data)
    assert masked["Actions"][0]["Arguments"] == {"--jdbc_url": MASK}
    assert masked["Outputs"][0]["OutputKey"] == "Endpoint"
    assert masked["Policy"] is data["Policy"]  # unchanged text is not rewritten
    assert masked["Description"] == "[not json"


def test_tags_named_like_secrets_stay_visible():
    data = {
        "Tags": [{"Key": "password", "Value": "visible"}],
        "TagSet": [{"Key": "api_key", "Value": "visible"}],
        "tags": {"db_password": "visible"},
    }
    assert mask_resource(data) == (data, 0)


def test_unknown_keys_pass_and_deep_nesting_fails_closed():
    assert mask_secret_values({"SomeNewField": S}) == {"SomeNewField": S}
    deep = cur = {}
    for _ in range(250):
        cur["n"] = {}
        cur = cur["n"]
    cur["leaf"] = S
    assert S not in json.dumps(mask_secret_values(deep))


@pytest.mark.parametrize(
    "text",
    [
        json.dumps({"Arguments": {"--jdbc_url": S}}),
        repr(json.dumps({"Arguments": {"--jdbc_url": S}}).encode()),
        "<Outputs><member><OutputKey>K</OutputKey><OutputValue>%s</OutputValue>"
        "</member></Outputs>" % S,
        json.dumps({"Input": json.dumps({"ApiPassword": S})}),
        repr(json.dumps({"Input": json.dumps({"ApiPassword": S})}).encode()),
        json.dumps({"TemplateBody": S}),
    ],
)
def test_log_redaction_covers_the_new_fields(text):
    out = redact(text)
    assert S not in out
    assert "REDACTED" in out
