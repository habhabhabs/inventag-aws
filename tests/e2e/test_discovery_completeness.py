"""Completeness of discovery, checked through the report a scan writes.

Added after a mutation check: changing the discovery call to read only the
first page of every list response was not caught by any existing test.
"""

import boto3
import pytest

from .test_cli_end_to_end import all_resource_rows

pytestmark = pytest.mark.e2e


def test_every_page_of_a_paginated_list_call_is_read(estate, run_cli):
    """DynamoDB lists 100 table names per page; 105 tables need two pages."""
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    for i in range(105):
        ddb.create_table(
            TableName=f"paged-{i:03d}",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

    result = run_cli("--account-services", "DYNAMODB")

    assert result.code == 0, result.text
    tables = {
        r["id"]
        for r in all_resource_rows(result.files(".xlsx")[0])
        if r["service"] == "DYNAMODB"
    }
    assert len(tables) == 106  # 105 plus the table of the standard estate
    assert "paged-104" in tables and "paged-000" in tables


def test_more_than_1000_sqs_queues_in_one_region_are_all_reported(estate, run_cli):
    sqs = boto3.client("sqs", region_name="us-east-1")
    for i in range(1005):
        sqs.create_queue(QueueName=f"many-{i:05d}")

    result = run_cli("--account-services", "SQS")

    assert result.code == 0, result.text
    queues = [
        r for r in all_resource_rows(result.files(".xlsx")[0]) if r["service"] == "SQS"
    ]
    assert len(queues) == 1006  # the 1005 above and the one of the standard estate
