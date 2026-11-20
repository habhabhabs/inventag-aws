"""SEC1 (security P3-2, architect A7 F5): a scan starts with an empty client cache.

A client copies its session's handlers when it is created. A client cached
during one scan carries the limiter handler bound to that scan's deadline; a
second scan on the same session object (library use) must not get it back, or
its requests wait on the first scan's deadline, which is no longer active.

No AWS call: the limiter's own botocore events are emitted on the client.
"""

import boto3

from inventag.core import cloud_bom_generator as cbg
from inventag.discovery import aws_clients

ACCOUNT = "123456789012"


class _Deadline:
    active = False

    def __init__(self, name, seen):
        self.name, self.seen = name, seen

    def before_call(self):
        self.seen.append(self.name)


def _one_request(client):
    """The limiter's two events around one HTTP attempt, without the attempt
    (``before-call`` is left out: botocore's own handlers of it need a model)."""
    events = client.meta.events
    send = "before-send.sts.GetCallerIdentity"
    events.emit(send, request=None)
    events.emit(
        "response-received.sts.GetCallerIdentity",
        parsed_response={},
        response_dict={"status_code": 200},
        exception=None,
    )


def _session():
    return boto3.Session(
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    )


def test_a_second_scan_on_one_session_uses_clients_bound_to_its_own_deadline(tmp_path):
    generator = cbg.CloudBOMGenerator(
        cbg.MultiAccountConfig(output_directory=str(tmp_path / "out"))
    )
    session, seen = _session(), []

    generator._attach_limiter(session, ACCOUNT, _Deadline("first", seen))
    first = aws_clients.create_client(session, "sts", "us-east-1")
    _one_request(first)
    assert seen == ["first"]

    generator._attach_limiter(session, ACCOUNT, _Deadline("second", seen))
    second = aws_clients.create_client(session, "sts", "us-east-1")
    _one_request(second)
    assert seen == ["first", "second"]
    assert second is not first
    assert generator.limiter.in_flight() == 0


def test_reset_client_cache_empties_the_cache_and_keeps_it_on():
    session = _session()
    aws_clients.enable_client_cache(session)
    before = aws_clients.create_client(session, "sts", "us-east-1")
    aws_clients.reset_client_cache(session)
    after = aws_clients.create_client(session, "sts", "us-east-1")
    assert after is not before
    assert aws_clients.create_client(session, "sts", "us-east-1") is after


def test_reset_client_cache_on_a_session_without_a_cache_turns_nothing_on():
    session = _session()
    aws_clients.reset_client_cache(session)
    one = aws_clients.create_client(session, "sts", "us-east-1")
    assert aws_clients.create_client(session, "sts", "us-east-1") is not one
