"""v1.3.1: reads by name that issue a token or credentials, or take a queue item.

The guard allows an operation by its prefix (``Get``...). Some ``Get``
operations are not reads:

- ``sts:GetWebIdentityToken`` issues a signed JSON Web Token for the caller;
- ``stepfunctions:GetActivityTask`` takes a task from an activity's queue (the
  worker that called it now holds the task, another worker cannot get it);
- ``lakeformation:GetTemporary*Credentials`` (four operations) vend temporary
  AWS credentials (their answer holds ``SecretAccessKey`` and
  ``SessionToken``), the same class as ``sts:GetSessionToken``, which the
  guard already refuses.

InvenTag calls none of them; the guard must refuse them anyway.
"""

import boto3
import botocore.session
import pytest

from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    check_client_call,
)

REFUSED = [
    ("sts", "GetWebIdentityToken", "get_web_identity_token"),
    ("stepfunctions", "GetActivityTask", "get_activity_task"),
    (
        "lakeformation",
        "GetTemporaryGlueTableCredentials",
        "get_temporary_glue_table_credentials",
    ),
    (
        "lakeformation",
        "GetTemporaryGluePartitionCredentials",
        "get_temporary_glue_partition_credentials",
    ),
    (
        "lakeformation",
        "GetTemporaryGlueFunctionCredentials",
        "get_temporary_glue_function_credentials",
    ),
    (
        "lakeformation",
        "GetTemporaryDataLocationCredentials",
        "get_temporary_data_location_credentials",
    ),
]


def _missing_from_botocore(service, operation):
    return operation not in (
        botocore.session.get_session().get_service_model(service).operation_names
    )


def _present_only(rows):
    """The rows, each skipped where the installed botocore lacks the operation
    (added after the floor, 1.35.0). The guard test by name still runs."""
    return [
        pytest.param(
            *row,
            marks=pytest.mark.skipif(
                _missing_from_botocore(row[0], row[1]),
                reason="the installed botocore lacks this operation (added after 1.35.0)",
            ),
        )
        for row in rows
    ]


# Smallest valid input of each operation (botocore validates before the guard).
PARAMS = {
    "GetWebIdentityToken": {"Audience": ["a"], "SigningAlgorithm": "RS256"},
    "GetActivityTask": {
        "activityArn": "arn:aws:states:us-east-1:111111111111:activity:a"
    },
    "GetTemporaryGlueTableCredentials": {
        "TableArn": "arn:aws:glue:us-east-1:111111111111:table/d/t"
    },
    "GetTemporaryGluePartitionCredentials": {
        "TableArn": "arn:aws:glue:us-east-1:111111111111:table/d/t",
        "Partition": {"Values": ["v"]},
    },
    "GetTemporaryGlueFunctionCredentials": {
        "UserDefinedFunctionArn": "arn:aws:glue:us-east-1:111111111111:userDefinedFunction/d/f"
    },
    "GetTemporaryDataLocationCredentials": {},
}


def _client(service):
    return boto3.Session(
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    ).client(service)


@pytest.mark.parametrize("service,operation,method", REFUSED)
def test_the_guard_refuses_it(service, operation, method):
    allowed, reason = ReadOnlyGuard().evaluate(service, operation)
    assert not allowed
    assert "secrets" in reason


@pytest.mark.parametrize("service,operation,method", _present_only(REFUSED))
def test_the_name_check_for_dynamic_callers_refuses_it(service, operation, method):
    assert check_client_call(_client(service), method)[0] is False


class Sent(Exception):
    """The request got past the guard and was about to leave the process."""


def _refuse_send(request, **_):
    raise Sent(request.url)


@pytest.mark.parametrize("service,operation,method", _present_only(REFUSED))
def test_a_guarded_client_never_sends_it(service, operation, method):
    client = _client(service)
    ReadOnlyGuard().attach_client(client)
    # before-send fires after before-call (the guard), before any request
    # leaves the process.
    client.meta.events.register("before-send", _refuse_send)
    with pytest.raises(ReadOnlyViolationError) as raised:
        getattr(client, method)(**PARAMS[operation])
    assert raised.value.operation == operation


def test_the_neighbours_that_inventag_reads_are_still_allowed():
    guard = ReadOnlyGuard()
    for service, operation in [
        ("sts", "GetCallerIdentity"),
        ("sts", "AssumeRole"),
        ("stepfunctions", "ListStateMachines"),
        ("stepfunctions", "DescribeActivity"),
        ("lakeformation", "GetDataLakeSettings"),
        ("lakeformation", "ListResources"),
    ]:
        assert guard.evaluate(service, operation)[0], (service, operation)
    # The sign-in exchange of a web-identity profile is untouched
    assert guard.evaluate("sts", "AssumeRoleWithWebIdentity", unsigned=True)[0]


def _members(shape, seen=frozenset(), depth=0):
    if depth > 4:
        return
    if shape.type_name == "structure":
        if shape.name in seen:
            return
        for name, member in shape.members.items():
            yield name.lower()
            yield from _members(member, seen | {shape.name}, depth + 1)
    elif shape.type_name == "list":
        yield from _members(shape.member, seen, depth + 1)
    elif shape.type_name == "map":
        yield from _members(shape.value, seen, depth + 1)


# Allowed, and its answer can hold credentials: why it stays allowed.
CREDENTIAL_ANSWER_ALLOWED = {
    ("sts", "AssumeRole"): "required to reach other accounts",
    ("datazone", "GetConnection"): (
        "allowed only without withSecret; the parameter rule blocks " "withSecret=true"
    ),
}


def test_no_other_allowed_operation_answers_with_aws_credentials():
    """In the installed botocore: an allowed operation whose answer holds both
    SecretAccessKey and SessionToken issues credentials."""
    session = botocore.session.get_session()
    guard = ReadOnlyGuard()
    found = set()
    for service in session.get_available_services():
        model = session.get_service_model(service)
        for operation in model.operation_names:
            if not guard.evaluate(service, operation)[0]:
                continue
            output = model.operation_model(operation).output_shape
            if output is None:
                continue
            names = set(_members(output))
            if {"secretaccesskey", "sessiontoken"} <= names:
                found.add((service, operation))
    assert found - set(CREDENTIAL_ANSWER_ALLOWED) == set()
