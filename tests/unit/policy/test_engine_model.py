"""inventag.policy.model: the shared words, limits and row helpers (spec 1, 2, 9)."""

import dataclasses

from inventag.policy import model


def test_the_words_of_the_spec():
    assert model.SEVERITIES == ("info", "low", "medium", "high", "critical")
    assert model.RESULTS == ("pass", "fail", "waived", "not_evaluated")
    # 9.1: order when several reasons apply to one row
    assert model.REASONS == (
        "identity_only",
        "listing_not_read",
        "field_missing",
        "tags_not_read",
        "not_comparable",
        "not_convertible",
        "value_too_long",
    )
    assert model.CHECK_TYPES == (
        "value",
        "required-tags",
        "allowed-regions",
        "name-pattern",
        "baseline",
        "related",
        "require",
    )
    assert model.OPERATORS == (
        "eq",
        "ne",
        "gt",
        "ge",
        "lt",
        "le",
        "in",
        "not-in",
        "contains",
        "glob",
        "regex",
        "regex-case",
    )
    assert model.VALUE_TYPES == (
        "integer",
        "size",
        "normalize",
        "age",
        "expiration",
        "text",
    )
    assert model.SPECIAL_VALUES == ("absent", "present", "empty", "not-null")


def test_the_limits_of_the_spec():
    limits = model.LIMITS
    assert limits.file_bytes == 256 * 1024
    assert limits.policies_per_run == 500
    assert limits.checks_per_policy == 20
    assert limits.entries_per_group == 20
    assert limits.nesting_depth == 5
    assert limits.key_length == 200
    assert limits.pattern_length == 200
    assert limits.found_string_length == 4096
    assert limits.message_length == 300
    assert limits.references == 10
    assert limits.related_rows_per_place == 50_000
    assert limits.waiver_days_ahead == 366


def test_row_helpers():
    row = {
        "service": "S3",
        "resource_type": "Bucket",
        "resource_id": "b",
        "resource_name": None,
        "arn": "",
        "account_id": "222222222222",
        "detail_level": "full",
        "raw_data": {"Name": "b"},
    }
    assert model.account(row) == "222222222222"
    assert model.account(dict(row, source_account_id="111111111111")) == "111111111111"
    assert model.account({}) == ""
    assert model.resource(row) == "S3/Bucket/b"
    assert model.resource(dict(row, arn="arn:aws:s3:::b")) == "arn:aws:s3:::b"
    assert model.name(row) == "b"
    assert model.name(dict(row, resource_name="nice")) == "nice"
    assert model.identity_only(row) is False
    assert model.identity_only(dict(row, detail_level="identity")) is True
    assert (
        model.identity_only({k: v for k, v in row.items() if k != "raw_data"}) is True
    )
    assert model.identity_only(dict(row, raw_data=["x"])) is True


def test_the_loaded_objects_are_frozen_dataclasses():
    for cls in (model.Policy, model.PolicySet, model.Waiver):
        assert dataclasses.is_dataclass(cls)
        assert cls.__dataclass_params__.frozen
    fields = {f.name for f in dataclasses.fields(model.Policy)}
    assert fields >= {
        "id",
        "name",
        "severity",
        "version",
        "resource",
        "require",
        "check",
        "message",
        "references",
        "enabled",
        "description",
        "file",
        "sha256",
        "id_line",
        "severity_overridden_by",
    }
    assert {f.name for f in dataclasses.fields(model.Waiver)} == {
        "policy",
        "resource",
        "account",
        "reason",
        "approved_by",
        "expires",
        "file",
    }


def test_the_words_of_an_unused_waiver():
    # spec 2.5, 3.3 and amendment 2 (10.1)
    assert model.UNUSED_WHY == ("no match", "expired", "unknown policy", "superseded")
