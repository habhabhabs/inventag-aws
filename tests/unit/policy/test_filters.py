"""inventag.policy.filters: one filter entry on one row (spec 2.2, 9.1, 9.2)."""

import datetime as dt

import pytest

from inventag.policy import filters
from inventag.policy.filters import FALSE, TRUE, UNKNOWN

NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)
ROW = {
    "service": "EC2",
    "resource_type": "Instance",
    "resource_id": "i-1",
    "resource_name": "web-1",
    "arn": "arn:aws:ec2:us-east-1:111111111111:instance/i-1",
    "region": "us-east-1",
    "source_account_id": "111111111111",
    "detail_level": "full",
    "tags": [{"Key": "Owner", "Value": "platform"}, {"Key": "Env", "Value": ""}],
    "raw_data": {
        "State": {"Name": "running"},
        "Count": 3,
        "Text": "12",
        "Flag": True,
        "Zero": 0,
        "Items": ["a", "b"],
        "Empty": [],
        "Null": None,
        "Long": "x" * 5000,
        "Masked": "***REDACTED***",
        "Started": "2026-11-10T12:00:00Z",
        "Epoch": 1763164800,
    },
}


def ev(entry, row=ROW, tags_unknown=False):
    ctx = filters.Context(now=NOW, tags_unknown=lambda row: tags_unknown)
    return filters.evaluate(filters.compile_entry(entry), row, ctx)


def value(key, val=None, **kw):
    entry = {"type": "value", "key": key, **kw}
    if val is not None or "value" not in kw:
        entry["value"] = val
    return entry


@pytest.mark.parametrize(
    "entry, expected",
    [
        (value("raw_data.State.Name", "running"), TRUE),
        (value("raw_data.State.Name", "Running"), FALSE),
        (value("raw_data.Count", 3), TRUE),
        (value("raw_data.Count", "3"), FALSE),  # a string never equals a number
        (value("raw_data.Text", 12), FALSE),
        (value("raw_data.Flag", True), TRUE),
        (value("raw_data.Zero", False), FALSE),  # booleans are not numbers
        (value("raw_data.Nope", "x"), FALSE),
        (value("raw_data.Nope", "x", op="ne"), TRUE),
        (value("raw_data.Nope", ["x"], op="not-in"), TRUE),
        (value("raw_data.Nope", ["x"], op="in"), FALSE),
        (value("raw_data.State.Name", ["stopped", "running"], op="in"), TRUE),
        (value("raw_data.Items", "a", op="contains"), TRUE),
        (value("resource_name", "web", op="contains"), TRUE),
        (value("raw_data.Count", "3", op="contains"), FALSE),
        (value("resource_name", "web-*", op="glob"), TRUE),
        (value("resource_name", "WEB-*", op="glob"), FALSE),
        (value("resource_name", "WEB", op="regex"), TRUE),
        (value("resource_name", "1", op="regex"), FALSE),  # anchored at the start
        (value("resource_name", "WEB", op="regex-case"), FALSE),
        (value("raw_data.Count", 2, op="gt"), TRUE),
        (value("raw_data.Count", 3, op="ge"), TRUE),
        (value("raw_data.Count", 3, op="lt"), FALSE),
        (value("raw_data.Count", 3, op="le"), TRUE),
        (value("raw_data.Nope", 3, op="gt"), FALSE),
    ],
)
def test_operators(entry, expected):
    assert ev(entry)[0] is expected


@pytest.mark.parametrize(
    "key, special, expected",
    [
        ("raw_data.Nope", "absent", TRUE),
        ("raw_data.Null", "absent", TRUE),
        ("raw_data.Count", "absent", FALSE),
        ("raw_data.Null", "present", FALSE),
        ("raw_data.Masked", "present", TRUE),
        ("raw_data.Zero", "not-null", TRUE),
        ("raw_data.Empty", "empty", TRUE),
        ("raw_data.Nope", "empty", TRUE),
        ("tags.Env", "empty", TRUE),
        ("raw_data.Items", "empty", FALSE),
    ],
)
def test_special_values(key, special, expected):
    assert ev(value(key, special))[0] is expected


def test_value_type_text_switches_the_special_words_off():
    assert ev(value("raw_data.Masked", "present", value_type="text"))[0] is FALSE
    row = dict(ROW, raw_data=dict(ROW["raw_data"], Word="absent"))
    assert ev(value("raw_data.Word", "absent", value_type="text"), row)[0] is TRUE


@pytest.mark.parametrize(
    "entry, expected",
    [
        (value("raw_data.Text", 12, value_type="integer"), TRUE),
        (value("raw_data.Items", 2, value_type="size"), TRUE),
        (value("raw_data.Items", 1, value_type="size", op="gt"), TRUE),
        (value("resource_name", "WEB-1 ", value_type="normalize"), TRUE),
        (
            value("raw_data.State.Name", ["RUNNING"], value_type="normalize", op="in"),
            TRUE,
        ),
        (value("raw_data.Started", 9.5, value_type="age"), TRUE),  # fractions kept
        (value("raw_data.Started", 9, value_type="age", op="gt"), TRUE),
        (value("raw_data.Epoch", 6, value_type="age", op="ge"), TRUE),
        (value("raw_data.Started", -9.5, value_type="expiration"), TRUE),
    ],
)
def test_value_types(entry, expected):
    assert ev(entry)[0] is expected


@pytest.mark.parametrize(
    "entry, reason",
    [
        (value("raw_data.State.Name", 1, op="gt"), "not_comparable"),
        (value("raw_data.Flag", 1, op="gt"), "not_comparable"),
        (value("raw_data.State.Name", 1, value_type="integer"), "not_convertible"),
        (value("raw_data.Flag", 1, value_type="size"), "not_convertible"),
        (value("raw_data.State.Name", 1, value_type="age"), "not_convertible"),
        (value("raw_data.Long", "x*", op="glob"), "value_too_long"),
        (value("raw_data.Long", "x", op="regex"), "value_too_long"),
    ],
)
def test_unknown_reasons(entry, reason):
    assert ev(entry) == (UNKNOWN, reason)


def test_identity_only_row_and_raw_data():
    row = dict(ROW, detail_level="identity")
    assert ev(value("raw_data.State.Name", "running"), row) == (
        UNKNOWN,
        "identity_only",
    )
    assert ev(value("resource_name", "web-1"), row)[0] is TRUE


def test_tags_not_read_only_for_tag_keys():
    assert ev({"tag:Owner": "platform"}, tags_unknown=True) == (
        UNKNOWN,
        "tags_not_read",
    )
    assert ev(value("tags.Owner", "present"), tags_unknown=True) == (
        UNKNOWN,
        "tags_not_read",
    )
    assert ev(value("resource_name", "web-1"), tags_unknown=True)[0] is TRUE


def test_tag_shorthand_and_tag_keys_with_odd_characters():
    assert ev({"tag:Owner": "platform"})[0] is TRUE
    assert ev({"tag:Owner": "present"})[0] is TRUE
    row = dict(ROW, tags={"aws:cloudformation:stack-name": "s"})
    assert ev({"tag:aws:cloudformation:stack-name": "s"}, row)[0] is TRUE
    assert ev(value("tags.aws:cloudformation:stack-name", "s"), row)[0] is TRUE


@pytest.mark.parametrize(
    "a, b, op, expected",
    [
        (TRUE, UNKNOWN, "and", UNKNOWN),
        (FALSE, UNKNOWN, "and", FALSE),
        (TRUE, UNKNOWN, "or", TRUE),
        (FALSE, UNKNOWN, "or", UNKNOWN),
        (UNKNOWN, None, "not", UNKNOWN),
        (TRUE, None, "not", FALSE),
    ],
)
def test_kleene(a, b, op, expected):
    def leaf(v):
        if v is TRUE:
            return value("raw_data.Count", 3)
        if v is FALSE:
            return value("raw_data.Count", 4)
        return value("raw_data.State.Name", 1, op="gt")

    entries = [leaf(a)] + ([leaf(b)] if b is not None else [])
    assert ev({op: entries})[0] is expected


def test_the_first_reason_of_the_spec_order_wins():
    entry = {
        "and": [
            value("raw_data.State.Name", 1, op="gt"),  # not_comparable
            {"tag:Owner": "platform"},  # tags_not_read
        ]
    }
    assert ev(entry, tags_unknown=True) == (UNKNOWN, "tags_not_read")


def test_a_masked_value_is_compared_as_its_text():
    assert ev(value("raw_data.Masked", "***REDACTED***"))[0] is TRUE
    assert ev(value("raw_data.Masked", "secret"))[0] is FALSE
