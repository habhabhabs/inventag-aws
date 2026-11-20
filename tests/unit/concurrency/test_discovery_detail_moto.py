"""A3 (plan 2.4, 5.2 acceptance): a moto estate gives the same rows in the same
order, and the same detail calls by service and operation, whatever the
latency profile (so whatever finishes first).

Under moto the requests are answered one at a time (``tests/moto_serial.py``),
so this proves equality and order, not speed.
"""

import io
import json
import re
import zipfile

import boto3
from moto import mock_aws

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from tests.latency import inject_latency

REGIONS = ["us-east-1", "eu-west-1"]
SERVICES = ["s3", "lambda", "rds", "cloudformation", "eks"]
RANDOM = re.compile(r"[0-9a-f]{8}-[0-9a-f-]{27}|\b[a-z]{1,9}-[0-9a-f]{8,17}\b")
STAMP = re.compile(r"\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(\.\d+)?(\+00:00)?")


def _estate():
    for region in REGIONS:
        s3 = boto3.client("s3", region_name=region)
        for i in range(3):
            args = (
                {}
                if region == "us-east-1"
                else {"CreateBucketConfiguration": {"LocationConstraint": region}}
            )
            s3.create_bucket(Bucket=f"a3-{region}-{i}", **args)
        iam = boto3.client("iam", region_name=region)
        role = iam.create_role(RoleName=f"a3-{region}", AssumeRolePolicyDocument="{}")[
            "Role"
        ]["Arn"]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                zipfile.ZipInfo("app.py", date_time=(2020, 1, 1, 0, 0, 0)),
                "def h(e, c):\n    return 1\n",
            )
        lam = boto3.client("lambda", region_name=region)
        for i in range(5):
            lam.create_function(
                FunctionName=f"fn-{i}",
                Runtime="python3.12",
                Role=role,
                Handler="app.h",
                Code={"ZipFile": buffer.getvalue()},
            )
        rds = boto3.client("rds", region_name=region)
        for i in range(2):
            rds.create_db_instance(
                DBInstanceIdentifier=f"db-{i}",
                DBInstanceClass="db.t3.micro",
                Engine="postgres",
                MasterUsername="user",
                MasterUserPassword="Password123456",
            )
        cf = boto3.client("cloudformation", region_name=region)
        template = json.dumps({"Resources": {"T": {"Type": "AWS::SNS::Topic"}}})
        cf.create_stack(StackName="st-0", TemplateBody=template)
        ec2 = boto3.client("ec2", region_name=region)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.0.0/24")["Subnet"]
        eks = boto3.client("eks", region_name=region)
        for i in range(2):
            eks.create_cluster(
                name=f"k-{i}",
                roleArn=role,
                resourcesVpcConfig={"subnetIds": [subnet["SubnetId"]]},
            )


def _scan(per_operation):
    with mock_aws():
        _estate()
        with inject_latency(0, per_operation=per_operation) as harness:
            disc = ComprehensiveAWSDiscovery(
                session=boto3.Session(region_name="us-east-1"),
                regions=REGIONS,
                enable_billing_validation=False,
                services=SERVICES,
            )
            rows = disc.discover_all_resources()
        calls = harness.calls_by_operation()
    normal = [
        RANDOM.sub("X", STAMP.sub("T", json.dumps(r, sort_keys=True, default=str)))
        for r in rows
    ]
    ledger = sorted(
        json.dumps({k: v for k, v in e.items() if k != "seconds"}, sort_keys=True)
        for e in disc.coverage.to_dict()
    )
    return normal, ledger, calls


def test_rows_ledger_and_detail_calls_do_not_depend_on_what_finishes_first():
    slow_lambda = {"lambda:GetFunctionConfiguration": 30, "s3:GetBucketLocation": 1}
    slow_s3 = {"lambda:GetFunctionConfiguration": 1, "s3:GetBucketLocation": 30}
    first = _scan(slow_lambda)
    second = _scan(slow_s3)
    assert first[0] == second[0]  # the rows, in the same order
    assert first[1] == second[1]  # the coverage ledger
    # One detail call per resource (plus the listing call of RDS and
    # CloudFormation, which use the same operation, in each region).
    detail = {
        "s3:GetBucketLocation": 6,
        "lambda:GetFunctionConfiguration": 10,
        "rds:DescribeDBInstances": 4 + 2,
        "cloudformation:DescribeStacks": 2 + 2,
        "eks:DescribeCluster": 4,
    }
    for _, _, calls in (first, second):
        assert {name: calls[name] for name in detail} == detail
    assert first[2] == second[2]
