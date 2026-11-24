"""Unit and tag lookups of the engine reuse the change report's rule (spec 1, 8.1).

The first test lists every discovery table entry whose key and row label
differ (spec section 1 asks for that list), and proves that each unit key
reaches its rows' label."""

import boto3

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.discovery.service_filter import canonical_service
from inventag.policy import engine

KEY_AND_LABEL_DIFFER = [
    ("cognito", "COGNITO-IDP"),
    ("efs", "ELASTICFILESYSTEM"),
    ("emr", "ELASTICMAPREDUCE"),
    ("msk", "KAFKA"),
    ("opensearch", "ES"),
    ("stepfunctions", "STATES"),
    ("wafv2-cloudfront", "WAFV2"),
]


def table():
    session = boto3.Session(
        region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y"
    )
    found = ComprehensiveAWSDiscovery(session=session, regions=["us-east-1"])
    return found.service_discovery_patterns


def test_the_entries_whose_key_and_label_differ():
    differ = [
        (key, (cfg.get("label") or key).upper())
        for key, cfg in sorted(table().items())
        if (cfg.get("label") or key).lower() != key.lower()
    ]
    assert differ == KEY_AND_LABEL_DIFFER


def test_every_unit_key_reaches_the_label_of_its_rows():
    for key, cfg in table().items():
        label = (cfg.get("label") or key).upper()
        assert engine.unit_service(key) == canonical_service(label), key


def snapshot(units, rows):
    return {"metadata": {"tags": {"units_not_read": units}}, "resources": rows}


def test_tags_unknown_uses_the_change_reports_account_and_region():
    unit = {
        "account": "111111111111",
        "service": "resourcegroupstaggingapi",
        "region": "us-east-1",
        "source": "tagging-api",
        "outcome": "denied",
    }
    snap = engine._Snapshot(snapshot([unit], []))
    row = {
        "source_account_id": "111111111111",
        "region": "us-east-1",
        "arn": "arn:aws:sqs:us-east-1:111111111111:q",
    }
    assert snap.tags_unknown(row) is True
    assert snap.tags_unknown(dict(row, region="eu-west-1")) is False
    assert snap.tags_unknown(dict(row, source_account_id="222222222222")) is False
    # a global row: the tagging unit of a region does not make its tags unknown
    assert snap.tags_unknown(dict(row, region="global")) is False


def test_an_entry_with_an_outcome_that_is_not_a_failure_is_ignored():
    unit = {
        "account": "111111111111",
        "service": "lambda",
        "region": "us-east-1",
        "source": "service-api",
        "outcome": "ok",
    }
    snap = engine._Snapshot(snapshot([unit], []))
    assert snap.units == []
    assert snap.unit_unread("111111111111", "lambda", "us-east-1") is False
