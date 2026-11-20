"""F3 (A7 review): the delta detector's table of detail fields is tied to discovery.

``inventag.state.delta_detector._DETAIL_FIELDS`` lists, by (service, resource
type), the fields a detail call writes into a row. It is a hand-kept copy of
what ``ComprehensiveAWSDiscovery._enhance_*`` writes. If a detail call later
writes a new field and the table is not updated, a failed detail call brings
back A-78's false "modified" without any test failing.

This test scans one moto estate twice (S3, Lambda, RDS, CloudFormation, EKS):
once as it is, once with every detail call refused (AccessDenied). The fields
that exist or differ in a row only in the first scan are the fields the detail
calls write. They must equal the table, per (service, type).

Slow part: two moto scans of five services (a few seconds).
"""

import io
import json
import zipfile

import boto3
import botocore.client
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.state.delta_detector import _DETAIL_FIELDS

REGION = "us-east-1"
BUCKET_REGION = "us-west-2"
SERVICES = ["s3", "lambda", "rds", "cloudformation", "eks"]
# (service, operation) -> the parameter that marks the call as a detail call
# (the listing calls of RDS and CloudFormation use the same operations without it).
DETAIL_OPERATIONS = {
    ("s3", "GetBucketLocation"): "Bucket",
    ("lambda", "GetFunctionConfiguration"): "FunctionName",
    ("rds", "DescribeDBInstances"): "DBInstanceIdentifier",
    ("cloudformation", "DescribeStacks"): "StackName",
    ("eks", "DescribeCluster"): "name",
}
# Fields whose value is the clock's (moto answers "now"), so two scans differ in
# them whatever the detail calls do. Field names are in the table's spelling.
IGNORED_FIELDS = {"discovered_at", "raw_data.LatestRestorableTime"}


def _build_estate():
    s3 = boto3.client("s3", region_name=BUCKET_REGION)
    s3.create_bucket(
        Bucket="f3-bucket",
        CreateBucketConfiguration={"LocationConstraint": BUCKET_REGION},
    )
    iam = boto3.client("iam", region_name=REGION)
    role = iam.create_role(
        RoleName="f3-role",
        AssumeRolePolicyDocument=json.dumps({"Version": "2012-10-17"}),
    )["Role"]["Arn"]
    code = io.BytesIO()
    with zipfile.ZipFile(code, "w") as archive:
        archive.writestr("index.py", "def handler(event, context):\n    return 1\n")
    boto3.client("lambda", region_name=REGION).create_function(
        FunctionName="f3-fn",
        Runtime="python3.12",
        Role=role,
        Handler="index.handler",
        Code={"ZipFile": code.getvalue()},
    )
    boto3.client("rds", region_name=REGION).create_db_instance(
        DBInstanceIdentifier="f3-db",
        DBInstanceClass="db.t3.micro",
        Engine="postgres",
        MasterUsername="admin",
        MasterUserPassword="not-a-real-password",
        AllocatedStorage=20,
    )
    boto3.client("cloudformation", region_name=REGION).create_stack(
        StackName="f3-stack",
        TemplateBody=json.dumps(
            {
                "Resources": {
                    "Topic": {"Type": "AWS::SNS::Topic", "Properties": {}},
                }
            }
        ),
    )
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.9.0.0/16")["Vpc"]["VpcId"]
    subnets = [
        ec2.create_subnet(VpcId=vpc, CidrBlock=cidr, AvailabilityZone=az)["Subnet"][
            "SubnetId"
        ]
        for cidr, az in (("10.9.1.0/24", "us-east-1a"), ("10.9.2.0/24", "us-east-1b"))
    ]
    boto3.client("eks", region_name=REGION).create_cluster(
        name="f3-eks",
        roleArn=role,
        resourcesVpcConfig={"subnetIds": subnets},
    )


def _scan(monkeypatch, refuse_details):
    if refuse_details:
        original = botocore.client.BaseClient._make_api_call

        def refusing(self, operation, params):
            marker = DETAIL_OPERATIONS.get(
                (self.meta.service_model.service_name, operation)
            )
            if marker and marker in params:
                raise ClientError(
                    {"Error": {"Code": "AccessDenied", "Message": "refused"}},
                    operation,
                )
            return original(self, operation, params)

        monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", refusing)
    discovery = ComprehensiveAWSDiscovery(
        regions=[REGION, BUCKET_REGION],
        enable_billing_validation=False,
        services=SERVICES,
    )
    rows = discovery.discover_all_resources()
    return {
        (
            str(r["service"]).lower(),
            str(r["resource_type"]).lower(),
            r["resource_id"],
        ): r
        for r in rows
    }


def _flatten(row):
    flat = {k: v for k, v in row.items() if k != "raw_data"}
    raw = row.get("raw_data")
    if isinstance(raw, dict):
        flat.update({f"raw_data.{k}": v for k, v in raw.items()})
    return flat


def _written_by_details(full, bare):
    """Fields present in ``full`` and absent or different in ``bare``."""
    a, b = _flatten(full), _flatten(bare)
    return {
        name
        for name, value in a.items()
        if name not in IGNORED_FIELDS and (name not in b or b[name] != value)
    }


@pytest.fixture()
def two_scans(monkeypatch):
    with mock_aws():
        _build_estate()
        full = _scan(monkeypatch, refuse_details=False)
        bare = _scan(monkeypatch, refuse_details=True)
    return full, bare


def test_the_detail_fields_table_equals_what_the_detail_calls_write(two_scans):
    full, bare = two_scans
    seen = {}
    for key, row in full.items():
        service, kind, _ = key
        if (service, kind) not in _DETAIL_FIELDS:
            continue
        assert key in bare, f"{key} is missing from the scan without detail calls"
        seen.setdefault((service, kind), set()).update(
            _written_by_details(row, bare[key])
        )
    assert set(seen) == set(_DETAIL_FIELDS), (
        "the estate lacks a resource of a table entry",
        sorted(set(_DETAIL_FIELDS) - set(seen)),
    )
    for unit, fields in sorted(seen.items()):
        assert fields == set(_DETAIL_FIELDS[unit]), (
            f"{unit}: the detail calls write {sorted(fields)} but the table "
            f"_DETAIL_FIELDS has {sorted(_DETAIL_FIELDS[unit])}"
        )
