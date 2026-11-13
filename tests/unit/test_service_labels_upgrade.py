"""Services v1.1.4 already reported keep their `service` value and sheet name.

v1.1.4 found EFS file systems, Step Functions state machines, Cognito user
pools, EMR and MSK clusters and OpenSearch domains only through the Resource
Groups Tagging API, which names a row after the ARN service code
(ELASTICFILESYSTEM, STATES, ...). The table-driven listings added in v1.2.0
must give the same name, so a resource lands on one sheet whichever path found
it (the service API, or the Tagging API when the new List action is denied).
"""

import json

import boto3
import pytest
from moto import mock_aws

from inventag.discovery.comprehensive_discovery import (
    TABLE_DRIVEN_SERVICES,
    ComprehensiveAWSDiscovery,
)

R = "us-east-1"


@pytest.mark.parametrize("key", sorted(TABLE_DRIVEN_SERVICES))
def test_table_label_is_the_arn_service_name(key):
    spec = TABLE_DRIVEN_SERVICES[key]
    label = (spec.get("label") or key).upper()
    assert label == (spec.get("arn_service") or key).upper()


def test_v114_names_are_kept():
    names = {
        k: (TABLE_DRIVEN_SERVICES[k].get("label") or k).upper()
        for k in ("efs", "stepfunctions", "cognito", "emr", "msk", "opensearch")
    }
    assert names == {
        "efs": "ELASTICFILESYSTEM",
        "stepfunctions": "STATES",
        "cognito": "COGNITO-IDP",
        "emr": "ELASTICMAPREDUCE",
        "msk": "KAFKA",
        "opensearch": "ES",
    }


@pytest.fixture
def estate(monkeypatch):
    for key, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": R,
    }.items():
        monkeypatch.setenv(key, value)
    with mock_aws():
        iam = boto3.client("iam")
        role = iam.create_role(RoleName="sfn", AssumeRolePolicyDocument="{}")["Role"][
            "Arn"
        ]
        fs = boto3.client("efs", region_name=R).create_file_system(
            CreationToken="fs-1", Tags=[{"Key": "Owner", "Value": "data"}]
        )["FileSystemArn"]
        sm = boto3.client("stepfunctions", region_name=R).create_state_machine(
            name="flow",
            roleArn=role,
            definition=json.dumps(
                {"StartAt": "A", "States": {"A": {"Type": "Pass", "End": True}}}
            ),
            tags=[{"key": "Owner", "value": "platform"}],
        )["stateMachineArn"]
        yield {fs: "ELASTICFILESYSTEM", sm: "STATES"}


def _rows(patterns):
    disc = ComprehensiveAWSDiscovery(
        regions=[R], enable_billing_validation=False, fallback_display_mode="always"
    )
    disc.service_discovery_patterns = patterns
    return disc.discover_all_resources()


def test_service_api_and_tagging_api_give_one_row_with_one_name(estate):
    both = _rows(dict(TABLE_DRIVEN_SERVICES))
    for arn, service in estate.items():
        rows = [r for r in both if r.get("arn") == arn]
        assert len(rows) == 1, rows
        assert rows[0]["service"] == service
        assert rows[0]["source"] == "service-api"
        assert "tagging-api" in rows[0]["sources"]

    # The List action denied (no table entry): the Tagging API row has the
    # same service name, so the resource stays on the same sheet.
    tagging_only = _rows({})
    for arn, service in estate.items():
        rows = [r for r in tagging_only if r.get("arn") == arn]
        assert len(rows) == 1, rows
        assert rows[0]["service"] == service
        assert rows[0]["source"] == "tagging-api"
