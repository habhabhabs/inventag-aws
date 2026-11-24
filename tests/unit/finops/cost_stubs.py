"""Cost Explorer answers for the cost allocation tests, shaped like the real
responses (botocore Stubber validates each one against the service model).

The amounts are fixed test values, not prices; they only travel through the
code, which never computes with them."""

import boto3
from botocore.stub import ANY, Stubber

KEYS = ["CostCenter", "Owner", "Project", "Environment"]
PERIOD = {"Start": "2026-10-01", "End": "2026-11-01"}


def client():
    return boto3.Session(
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    ).client("ce")


def tag_list(active=(), inactive=()):
    tags = [{"TagKey": k, "Type": "UserDefined", "Status": "Active"} for k in active]
    tags += [
        {"TagKey": k, "Type": "UserDefined", "Status": "Inactive"} for k in inactive
    ]
    return {"CostAllocationTags": tags}


def usage(groups, token=None, period=PERIOD):
    answer = {
        "GroupDefinitions": [],
        "ResultsByTime": [
            {
                "TimePeriod": dict(period),
                "Total": {},
                "Groups": [
                    {
                        "Keys": [key],
                        "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}},
                    }
                    for key, amount in groups
                ],
                "Estimated": False,
            }
        ],
        "DimensionValueAttributes": [],
    }
    if token:
        answer["NextPageToken"] = token
    return answer


SERVICES = [("Amazon Simple Storage Service", "12.5"), ("AmazonCloudWatch", "0.31")]
ACCOUNTS = [("111122223333", "12.81")]


def tag_groups(key):
    return [(f"{key}$CC-1234", "10.0"), (f"{key}$", "2.81")]


def expect_usage(stub, group_type, key, answer, token=None, period=PERIOD):
    params = {
        "TimePeriod": dict(period),
        "Granularity": "MONTHLY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [{"Type": group_type, "Key": key}],
    }
    if token:
        params["NextPageToken"] = token
    stub.add_response("get_cost_and_usage", answer, params)


def full_stub(c, active=tuple(KEYS), inactive=(), period=PERIOD):
    """A Stubber that answers the requests of one account, in order."""
    stub = Stubber(c)
    stub.add_response(
        "list_cost_allocation_tags", tag_list(active, inactive), {"TagKeys": KEYS}
    )
    expect_usage(
        stub, "DIMENSION", "SERVICE", usage(SERVICES, period=period), period=period
    )
    expect_usage(
        stub,
        "DIMENSION",
        "LINKED_ACCOUNT",
        usage(ACCOUNTS, period=period),
        period=period,
    )
    for key in KEYS:
        if key in active:
            expect_usage(
                stub, "TAG", key, usage(tag_groups(key), period=period), period=period
            )
    return stub


__all__ = ["ANY", "Stubber"]
