"""Every output row comes from a real AWS API answer.

The discovery branch removed the "AI prediction" rows and left the optimized
engine making no AWS call. This checks the result over a whole moto estate:
every row says which source returned it, service-API rows name a listing
operation of the discovery table, and no row carries prediction fields.
"""

import boto3
import pytest
from moto import mock_aws

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

SOURCES = {"service-api", "tagging-api", "billing"}


def _table_operations():
    # The table is built in __init__ (no AWS call is needed for it).
    with mock_aws():
        engine = ComprehensiveAWSDiscovery(
            session=boto3.Session(region_name="us-east-1"), regions=["us-east-1"]
        )
    ops = set()
    for spec in engine.service_discovery_patterns.values():
        for op in spec.get("operations", []):
            ops.add(op[0] if isinstance(op, (tuple, list)) else op.get("op"))
    return ops


@pytest.fixture
def estate(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        iam = boto3.client("iam")
        role = iam.create_role(RoleName="exec-role", AssumeRolePolicyDocument="{}")
        import io
        import zipfile

        code = io.BytesIO()
        with zipfile.ZipFile(code, "w") as z:
            z.writestr("h.py", "def h(e, c):\n    return 1\n")
        # A Lambda function and no log group: the removed prediction code
        # would have added a "/aws/lambda/fn" log group and an "fn-role" role.
        boto3.client("lambda").create_function(
            FunctionName="fn",
            Runtime="python3.12",
            Role=role["Role"]["Arn"],
            Handler="h.h",
            Code={"ZipFile": code.getvalue()},
        )
        boto3.client("s3").create_bucket(Bucket="b-1")
        boto3.client("sqs").create_queue(QueueName="q-1")
        boto3.client("dynamodb").create_table(
            TableName="t-1",
            KeySchema=[{"AttributeName": "k", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "k", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        boto3.client("ec2").run_instances(
            ImageId="ami-12c6146b", MinCount=1, MaxCount=1
        )
        yield


def test_every_row_has_a_real_api_source(estate):
    from inventag.discovery.inventory import AWSResourceInventory

    resources = AWSResourceInventory(
        regions=["us-east-1"], enable_billing_validation=True
    ).discover_resources()
    assert resources
    table_ops = _table_operations()
    for row in resources:
        assert row.get("source") in SOURCES, row
        assert not {"predicted", "confidence", "prediction_confidence"} & set(row)
        via = str(row.get("discovered_via", ""))
        if row["source"] == "service-api":
            assert via.startswith("ServiceAPI:"), row
            operation = via.split(":", 1)[1]
            assert operation in table_ops or operation.startswith(
                ("list_", "describe_", "get_")
            ), via
        assert row.get("arn") or row.get("id"), row
    names = {str(r.get("id")) for r in resources}
    assert "fn" in names
    # Nothing that no API returned
    assert "/aws/lambda/fn" not in names and "fn-role" not in names
    assert not any("fn-errors" in str(r.get("id")) for r in resources)
