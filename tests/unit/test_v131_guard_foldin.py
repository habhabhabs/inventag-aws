"""v1.3.1 fold-in (architect ruling 2): two more operations and one parameter rule.

- ``payment-cryptography:GetParametersForImport`` and ``GetParametersForExport``
  issue an import or export token with wrapping or signing key material, the
  same as ``kms:GetParametersForImport``, which the guard already refuses.
- ``datazone:GetConnection`` with ``withSecret=true`` returns the connection's
  credentials (``connectionCredentials``), the same as
  ``apigateway:GetApiKey`` with ``includeValue=true``. Without the parameter,
  or with ``false``, it is a read and stays allowed.

InvenTag calls none of them.
"""

import boto3
import pytest

from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    check_client_call,
)

PAYMENT = [
    (
        "GetParametersForImport",
        "get_parameters_for_import",
        {"KeyMaterialType": "TR34_KEY_BLOCK", "WrappingKeyAlgorithm": "RSA_2048"},
    ),
    (
        "GetParametersForExport",
        "get_parameters_for_export",
        {"KeyMaterialType": "TR34_KEY_BLOCK", "SigningKeyAlgorithm": "RSA_2048"},
    ),
]
CONNECTION = {"domainIdentifier": "dzd_abc123", "identifier": "conn123"}


class Sent(Exception):
    """The request got past the guard and was about to leave the process."""


def _refuse_send(request, **_):
    raise Sent(request.url)


def _client(service):
    client = boto3.Session(
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    ).client(service)
    ReadOnlyGuard().attach_client(client)
    # before-send fires after before-call (the guard), before any request
    # leaves the process.
    client.meta.events.register("before-send", _refuse_send)
    return client


@pytest.mark.parametrize("operation,method,params", PAYMENT)
def test_payment_cryptography_key_exchange_is_never_sent(operation, method, params):
    client = _client("payment-cryptography")
    with pytest.raises(ReadOnlyViolationError) as raised:
        getattr(client, method)(**params)
    assert raised.value.operation == operation


@pytest.mark.parametrize("operation,method,params", PAYMENT)
def test_payment_cryptography_key_exchange_is_refused_by_name(
    operation, method, params
):
    allowed, reason = ReadOnlyGuard().evaluate("payment-cryptography", operation)
    assert not allowed and "secrets" in reason
    assert check_client_call(_client("payment-cryptography"), method)[0] is False


def test_datazone_get_connection_with_secret_is_never_sent():
    client = _client("datazone")
    with pytest.raises(ReadOnlyViolationError) as raised:
        client.get_connection(withSecret=True, **CONNECTION)
    assert "withSecret" in raised.value.reason


@pytest.mark.parametrize("extra", [{}, {"withSecret": False}])
def test_datazone_get_connection_without_secret_is_sent(extra):
    client = _client("datazone")
    with pytest.raises(Sent) as sent:
        client.get_connection(**CONNECTION, **extra)
    assert "/connections/conn123" in str(sent.value)
    # The name check (no parameters known) still allows the read
    assert check_client_call(client, "get_connection")[0] is True


def test_datazone_presigned_get_connection_with_secret_is_refused():
    client = _client("datazone")
    with pytest.raises(ReadOnlyViolationError):
        client.generate_presigned_url(
            "get_connection", Params={**CONNECTION, "withSecret": True}
        )
    url = client.generate_presigned_url("get_connection", Params=dict(CONNECTION))
    assert url.startswith("https://")


def test_the_neighbours_are_still_allowed():
    guard = ReadOnlyGuard()
    for service, operation in [
        ("payment-cryptography", "GetKey"),
        ("payment-cryptography", "ListKeys"),
        ("payment-cryptography", "GetAlias"),
        ("datazone", "ListConnections"),
        ("datazone", "GetDomain"),
        ("datazone", "GetConnection"),
    ]:
        assert guard.evaluate(service, operation)[0], (service, operation)


def test_every_parameter_rule_applies_to_a_presigned_url():
    """The changelog says the parameter rules apply to presigned URLs."""
    from inventag.security.read_only_guard import DENIED_PARAMETERS

    examples = {
        ("apigateway", "GetApiKey"): {"apiKey": "k", "includeValue": True},
        ("apigateway", "GetApiKeys"): {"includeValues": True},
        ("ec2", "DescribeInstanceAttribute"): {
            "InstanceId": "i-1",
            "Attribute": "userData",
        },
        ("datazone", "GetConnection"): {**CONNECTION, "withSecret": True},
    }
    assert set(examples) == set(DENIED_PARAMETERS)
    for (service, operation), params in examples.items():
        client = _client(service)
        method = {v: k for k, v in client.meta.method_to_api_mapping.items()}[operation]
        with pytest.raises(ReadOnlyViolationError):
            client.generate_presigned_url(method, Params=params)
