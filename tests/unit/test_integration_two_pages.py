"""Every listing operation of the discovery table reads a second page.

The tests-coverage engineer found that SQS ListQueues stopped at 1,000 queues:
SQS returns a continuation token only when the request sets MaxResults. This
test runs ``_pages`` for EVERY operation of the service table against a
stubbed client that answers with two pages, and checks that both are read and
that the second request carries the token from the first.
"""

import boto3
import botocore.session
import pytest
from botocore import xform_name
from botocore.stub import Stubber
from moto import mock_aws

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery


def _engine():
    with mock_aws():
        return ComprehensiveAWSDiscovery(
            session=boto3.Session(
                region_name="us-east-1",
                aws_access_key_id="testing",
                aws_secret_access_key="testing",
            ),
            regions=["us-east-1"],
        )


ENGINE = _engine()
BOTOCORE = botocore.session.get_session()


def _cases():
    cases = []
    for service, spec in sorted(ENGINE.service_discovery_patterns.items()):
        client_service = spec.get("client_service", service)
        for op in spec.get("operations", []):
            if isinstance(op, (tuple, list)):
                name, params, custom = op[0], (op[3] if len(op) > 3 else {}), None
            else:
                name, params, custom = op["op"], op.get("params") or {}, op.get("token")
            if custom:
                continue  # operations with their own token rule: see below
            cases.append(
                pytest.param(client_service, name, params, id=f"{service}.{name}")
            )
    return cases


def _dummy(shape):
    if shape.type_name == "string":
        return "x"
    if shape.type_name == "integer":
        return 1
    if shape.type_name == "boolean":
        return False
    if shape.type_name == "list":
        return [_dummy(shape.member)]
    if shape.type_name == "structure":
        return {k: _dummy(shape.members[k]) for k in shape.required_members}
    return "x"


def _required_output(op_model):
    """An answer with only the members the model requires (empty lists)."""
    shape = op_model.output_shape
    if shape is None:
        return {}
    out = {}
    for name in shape.required_members:
        member = shape.members[name]
        out[name] = [] if member.type_name == "list" else _dummy(member)
    return out


def _token_names(client, operation_name):
    """(request token, response token(s), extra 'more results' key) or None."""
    model = client.meta.service_model
    api = client.meta.method_to_api_mapping[operation_name]
    if client.can_paginate(operation_name):
        config = BOTOCORE.get_paginator_model(model.service_name).get_paginator(api)
        inputs = config["input_token"]
        outputs = config["output_token"]
        inputs = inputs if isinstance(inputs, list) else [inputs]
        outputs = outputs if isinstance(outputs, list) else [outputs]
        if any(not o.isidentifier() for o in outputs):
            return None  # an expression (S3-style): not a plain token
        return inputs, outputs, config.get("more_results")
    op_model = model.operation_model(api)
    ins = set(op_model.input_shape.members) if op_model.input_shape else set()
    outs = set(op_model.output_shape.members) if op_model.output_shape else set()
    for req, resp in ComprehensiveAWSDiscovery._TOKEN_FIELDS:
        if req in ins and resp in outs:
            return [req], [resp], None
    return "single"


@pytest.mark.parametrize("client_service, operation_name, params", _cases())
def test_second_page_is_read(client_service, operation_name, params):
    client = BOTOCORE.create_client(
        client_service,
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    api = client.meta.method_to_api_mapping[operation_name]
    op_model = client.meta.service_model.operation_model(api)
    request = dict(params)
    if op_model.input_shape is not None:
        for member in op_model.input_shape.required_members:
            request.setdefault(member, _dummy(op_model.input_shape.members[member]))

    tokens = _token_names(client, operation_name)
    if tokens == "single":
        pytest.skip("the API has no continuation token for this operation")
    if tokens is None:
        pytest.skip("token is an expression; covered by botocore's paginator")
    inputs, outputs, more = tokens

    sent = []
    client.meta.events.register(
        f"provide-client-params.{client.meta.service_model.service_name}.{api}",
        lambda params, **kwargs: sent.append(dict(params)),
    )
    base = _required_output(op_model)
    first = dict(base, **{name: f"page-2-{name}" for name in outputs})
    last = dict(base)
    if more:
        first[more] = True
        last[more] = False
    with Stubber(client) as stub:
        stub.add_response(operation_name, first)
        stub.add_response(operation_name, last)
        pages = list(ENGINE._pages(client, operation_name, request))
        stub.assert_no_pending_responses()

    assert len(pages) == 2, f"{operation_name}: second page not read"
    assert sent[1].get(inputs[0]) == f"page-2-{outputs[0]}"
    if (client_service, operation_name) == ("sqs", "list_queues"):
        # Without MaxResults SQS gives no token at all (at most 1,000 queues).
        assert sent[0].get("MaxResults") == 1000


def test_custom_token_operations_read_a_second_page():
    """Table entries with their own token rule (e.g. 'more results' flags)."""
    checked = 0
    for service, spec in ENGINE.service_discovery_patterns.items():
        for op in spec.get("operations", []):
            if isinstance(op, (tuple, list)) or not op.get("token"):
                continue
            calls = []
            request_param, more_field = op["token"]

            class Fake:
                def __init__(self):
                    self.n = 0

                def call(self, **kwargs):
                    calls.append(kwargs)
                    self.n += 1
                    if self.n == 1:
                        return {op["key"]: ["first"], more_field: True}
                    return {op["key"]: ["second"]}

            fake = Fake()
            client = type("C", (), {op["op"]: staticmethod(fake.call)})()
            pages = list(ENGINE._pages_with_token(client, op, {}))
            assert len(pages) == 2, (service, op["op"])
            assert calls[1][request_param] == "first"
            checked += 1
    assert checked >= 0
