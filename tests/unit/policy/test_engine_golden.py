"""Whole result files (golden) and the result's shape against spec 3.3 with the
reasons of amendment 1 (9.1)."""

import datetime as dt
import json
import re
from pathlib import Path

import jsonschema
import pytest

from inventag.policy import engine, loader

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden"
NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)

CASES = {
    "result-ex05-s1.json": (["ex05.yaml"], "s1.json", {"fail_on": "medium"}),
    "result-ex09-ex10-s1.json": (
        ["ex09.yaml", "ex10.yaml"],
        "s1.json",
        {"fail_on": "low", "fail_on_not_evaluated": True},
    ),
    "result-fin005-s2.json": (["fin-005.yaml"], "s2.json", {"fail_on": "low"}),
}


def result_of(policies, snap, options):
    loaded = loader.load([GOLDEN / "policies" / p for p in policies], root=GOLDEN)
    data = json.loads((GOLDEN / snap).read_text())
    return engine.evaluate(
        data,
        loaded.policies,
        now=NOW,
        snapshot_file=snap,
        snapshot_sha256="0" * 64,
        inventag_version="1.5.0",
        **options,
    )


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden_result(name):
    text = engine.dumps(result_of(*CASES[name]))
    assert text == (GOLDEN / name).read_text()


# Spec 3.3, with the two reasons of amendment 1 (9.1) in the finding's enum.
FINDINGS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "inventag_version",
        "now",
        "snapshot",
        "baseline",
        "policies",
        "summary",
        "findings",
        "not_evaluated_units",
        "not_evaluated_policies",
        "unused_waivers",
    ],
    "properties": {
        "schema_version": {"const": "1.0"},
        "inventag_version": {"type": "string"},
        "now": {"type": "string", "pattern": r"^\d{4}-\d\d-\d\d$"},
        "snapshot": {"$ref": "#/$defs/snapshot"},
        "baseline": {"oneOf": [{"type": "null"}, {"$ref": "#/$defs/snapshot"}]},
        "policies": {"type": "array", "items": {"$ref": "#/$defs/policy"}},
        "summary": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rows", "by_result", "fail_by_severity", "exit_code"],
            "properties": {
                "rows": {"type": "integer"},
                "by_result": {"$ref": "#/$defs/counts"},
                "fail_by_severity": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                },
                "exit_code": {"enum": [0, 7, 8]},
            },
        },
        "findings": {"type": "array", "items": {"$ref": "#/$defs/finding"}},
        "not_evaluated_units": {"type": "array", "items": {"$ref": "#/$defs/unit"}},
        "not_evaluated_policies": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["policy", "reason"],
                "properties": {
                    "policy": {"type": "string"},
                    "reason": {"enum": ["no_baseline"]},
                },
            },
        },
        "unused_waivers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["policy", "resource", "expires", "why", "file"],
                "properties": {
                    "policy": {"type": "string"},
                    "resource": {"type": "string"},
                    "account": {"type": "string"},
                    "expires": {"type": "string"},
                    "why": {
                        "enum": ["no match", "expired", "unknown policy", "superseded"]
                    },
                    "by": {"type": "string"},
                    "file": {"type": "string"},
                },
            },
        },
    },
    "$defs": {
        "snapshot": {
            "type": "object",
            "additionalProperties": False,
            "required": ["file", "sha256", "timestamp"],
            "properties": {
                "file": {"type": "string"},
                "sha256": {"type": "string"},
                "timestamp": {"type": "string"},
                "inventag_version": {"type": "string"},
            },
        },
        "counts": {
            "type": "object",
            "additionalProperties": False,
            "required": ["pass", "fail", "waived", "not_evaluated", "out_of_scope"],
            "properties": {
                k: {"type": "integer"}
                for k in ("pass", "fail", "waived", "not_evaluated", "out_of_scope")
            },
        },
        "policy": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "id",
                "name",
                "severity",
                "version",
                "file",
                "sha256",
                "counts",
            ],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "severity": {"enum": ["info", "low", "medium", "high", "critical"]},
                "severity_overridden_by": {"type": "string"},
                "line": {"type": "integer", "minimum": 1},
                "version": {"type": "integer"},
                "file": {"type": "string"},
                "sha256": {"type": "string"},
                "references": {"type": "array", "items": {"type": "string"}},
                "counts": {"$ref": "#/$defs/counts"},
            },
        },
        "finding": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "policy",
                "result",
                "severity",
                "account",
                "region",
                "service",
                "resource_type",
                "resource",
                "message",
            ],
            "properties": {
                "policy": {"type": "string"},
                "result": {"enum": ["pass", "fail", "waived", "not_evaluated"]},
                "severity": {"enum": ["info", "low", "medium", "high", "critical"]},
                "account": {"type": "string"},
                "region": {"type": "string"},
                "service": {"type": "string"},
                "resource_type": {"type": "string"},
                "resource": {"type": "string"},
                "name": {"type": "string"},
                "message": {"type": "string"},
                "reason": {
                    "enum": [
                        "identity_only",
                        "listing_not_read",
                        "field_missing",
                        "tags_not_read",
                        "not_comparable",
                        "not_convertible",
                        "value_too_long",
                    ]
                },
                "from": {"const": "baseline"},
                "details": {"type": "array", "items": {"type": "object"}},
                "waiver": {"type": "object"},
                "waiver_expired": {"type": "string"},
            },
        },
        "unit": {
            "type": "object",
            "additionalProperties": False,
            "required": ["policy", "account", "service", "region", "reason", "outcome"],
            "properties": {
                "policy": {"type": "string"},
                "account": {"type": "string"},
                "service": {"type": "string"},
                "region": {"type": "string"},
                "reason": {"const": "listing_not_read"},
                "outcome": {"type": "string"},
                "from": {"const": "baseline"},
            },
        },
    },
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_result_matches_the_spec_schema(name):
    policies, snap, options = CASES[name]
    jsonschema.validate(
        result_of(policies, snap, dict(options, include_pass=True)), FINDINGS_SCHEMA
    )


def test_every_example_policy_gives_a_valid_result():
    files = sorted(p.name for p in (GOLDEN / "policies").glob("*.yaml"))
    for snap in ("s1.json", "s2.json"):
        jsonschema.validate(
            result_of(files, snap, {"include_pass": True}), FINDINGS_SCHEMA
        )


def test_no_absolute_path_in_a_golden_file():
    for path in GOLDEN.glob("result-*.json"):
        text = path.read_text()
        assert not re.search(r'"/(home|tmp|Users)/', text), path


def test_the_schema_s_waiver_words_are_the_model_s():
    from inventag.policy import model

    items = FINDINGS_SCHEMA["properties"]["unused_waivers"]["items"]
    assert tuple(items["properties"]["why"]["enum"]) == model.UNUSED_WHY
