"""v1.3.1: ``sts:GetScopedCredentials`` issues temporary AWS credentials.

botocore 1.44.7 adds ``sts:GetScopedCredentials``. Its answer holds
``Credentials`` with ``AccessKeyId``, ``SecretAccessKey`` and ``SessionToken``:
it issues a set of temporary credentials scoped down from the caller's own.
Its name starts with ``Get``, so the guard allowed it by the prefix. It is the
same class as ``sts:GetSessionToken`` (already refused) and
``sts:GetWebIdentityToken`` (refused since v1.3.1): it issues credentials, it
is not a read. InvenTag never calls it.

Older botocore (the shared venv's 1.44.2 and the CI floor 1.35.0) does not
have the operation: there the guard still refuses the name, and the client
tests are skipped because the client has no such method.
"""

import boto3
import botocore.session
import pytest

from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    check_client_call,
)

HAS_OPERATION = "GetScopedCredentials" in (
    botocore.session.get_session().get_service_model("sts").operation_names
)


class Sent(Exception):
    """The request got past the guard and was about to leave the process."""


def _refuse_send(request, **_):
    raise Sent(request.url)


def _client():
    return boto3.Session(
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    ).client("sts")


def test_the_guard_refuses_it():
    allowed, reason = ReadOnlyGuard().evaluate("sts", "GetScopedCredentials")
    assert not allowed
    assert "secrets" in reason


@pytest.mark.skipif(
    not HAS_OPERATION,
    reason="the installed botocore has no sts:GetScopedCredentials (added in 1.44.7)",
)
def test_the_name_check_for_dynamic_callers_refuses_it():
    allowed, reason = check_client_call(_client(), "get_scoped_credentials")
    assert allowed is False
    assert "not an operation" not in reason


@pytest.mark.skipif(
    not HAS_OPERATION,
    reason="the installed botocore has no sts:GetScopedCredentials (added in 1.44.7)",
)
def test_a_guarded_client_never_sends_it():
    client = _client()
    ReadOnlyGuard().attach_client(client)
    # before-send fires after before-call (the guard), before any request
    # leaves the process.
    client.meta.events.register("before-send", _refuse_send)
    with pytest.raises(ReadOnlyViolationError) as raised:
        client.get_scoped_credentials()
    assert raised.value.operation == "GetScopedCredentials"


def test_the_sts_neighbours_that_inventag_uses_are_still_allowed():
    guard = ReadOnlyGuard()
    assert guard.evaluate("sts", "GetCallerIdentity")[0]
    assert guard.evaluate("sts", "AssumeRole")[0]
    assert guard.evaluate("sts", "AssumeRoleWithWebIdentity", unsigned=True)[0]
