"""Estates a scenario can ask for by name. Each function runs inside ``mock_aws()``.

moto is never empty: it ships a default VPC, security groups and KMS keys. A
scenario that needs "nothing to report" therefore combines the ``empty`` estate
with ``--account-services SQS`` (see ``scenarios.EMPTY_ARGS``).
"""

import boto3

from tests.e2e.estate import seed_estate

REGION = "us-east-1"


def estate():
    seed_estate()


def empty():
    pass


def ddb105():
    ddb = boto3.client("dynamodb", region_name=REGION)
    for i in range(105):
        ddb.create_table(
            TableName=f"tbl{i:03d}",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )


def upload_bucket():
    boto3.client("s3", region_name=REGION).create_bucket(Bucket="regression-upload")


SEEDS = {"estate": estate, "empty": empty, "ddb105": ddb105, "upload_bucket": upload_bucket}


def seed(names):
    for name in names:
        SEEDS[name]()
