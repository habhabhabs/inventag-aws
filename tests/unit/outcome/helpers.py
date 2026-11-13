"""Builders shared by the outcome tests."""

from botocore.exceptions import ClientError


def client_error(code, message="", status=400, operation="ListQueues"):
    response = {
        "Error": {"Code": code, "Message": message},
        "ResponseMetadata": {"HTTPStatusCode": status},
    }
    return ClientError(response, operation)


def bare(cls):
    """An instance of a botocore exception class without its constructor
    arguments (classify reads only the class and AWS's response)."""
    return cls.__new__(cls)


def entry(
    outcome="ok",
    *,
    account_id="111111111111",
    region="us-east-1",
    service="sqs",
    source="service-api",
    operation="ListQueues",
    count=0,
    error_code="",
    seconds=0.0,
    category="",
):
    """A ledger entry in its ``asdict`` form (as discovery writes it at ed91cd6)."""
    data = dict(
        account_id=account_id,
        region=region,
        source=source,
        service=service,
        resource_type="",
        operation=operation,
        outcome=outcome,
        count=count,
        error_code=error_code,
        seconds=seconds,
    )
    if category:
        data["category"] = category
    return data
