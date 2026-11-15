"""After an account's deadline its in-flight call is not retried (A-25, part 1).

Discovery clients retry up to 10 attempts (``aws_clients.retry_config``),
each with botocore's 60 s connect and 60 s read timeouts. The deadline was
checked only before a call (``before-call``), not before each retry attempt,
so a call that started before the deadline could go on for up to 10 more
attempts after it, and the process stayed alive that long after the summary
(harness row B10, S1 B10). Now the deadline is also checked before every
attempt (``before-send``): after the deadline the call ends at the next
attempt with the account's time-limit error.

No network, no real sleep: the HTTP answer is a 500 from a ``before-send``
handler, botocore's back-off sleep is replaced, and the clock is fake.
"""

import types

import boto3
import botocore.endpoint
import pytest
from botocore.awsrequest import AWSResponse

from inventag.core.cloud_bom_generator import AccountTimeoutError, _AccountDeadline
from inventag.discovery.aws_clients import retry_config


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class RawBody:
    def __init__(self, data):
        self._data = data

    def stream(self, **kwargs):
        yield self._data


ERROR = (
    b"<Response><Errors><Error><Code>InternalError</Code>"
    b"<Message>x</Message></Error></Errors></Response>"
)


@pytest.fixture
def no_backoff(monkeypatch):
    fake_time = types.SimpleNamespace(sleep=lambda seconds: None)
    monkeypatch.setattr(botocore.endpoint, "time", fake_time)
    monkeypatch.delenv("AWS_RETRY_MODE", raising=False)
    monkeypatch.delenv("AWS_MAX_ATTEMPTS", raising=False)


def _session_with_failing_endpoint(clock, attempts, slow_seconds):
    session = boto3.Session(
        aws_access_key_id="AKIAFAKEFAKEFAKEFAKE",
        aws_secret_access_key="fake-secret-for-tests-only",
        region_name="us-east-1",
    )

    def respond(request, **kwargs):
        attempts.append(clock())
        clock.now += slow_seconds  # each attempt takes this long
        return AWSResponse(request.url, 500, {}, RawBody(ERROR))

    session.events.register_last("before-send.ec2", respond)
    return session


def test_a_call_is_not_retried_after_the_accounts_deadline(no_backoff):
    clock = FakeClock()
    attempts = []
    session = _session_with_failing_endpoint(clock, attempts, slow_seconds=100)
    deadline = _AccountDeadline("111111111111", 60, clock=clock)
    deadline.start()
    deadline.attach(session)
    client = session.client("ec2", config=retry_config())
    with pytest.raises(AccountTimeoutError, match="60 seconds"):
        client.describe_vpcs()
    assert len(attempts) == 1  # v1.2.1: 10 attempts after the deadline
    assert deadline.expired


def test_before_the_deadline_the_retries_are_unchanged(no_backoff):
    """Guard: a failing call within the limit keeps all 10 attempts."""
    clock = FakeClock()
    attempts = []
    session = _session_with_failing_endpoint(clock, attempts, slow_seconds=1)
    deadline = _AccountDeadline("111111111111", 600, clock=clock)
    deadline.start()
    deadline.attach(session)
    client = session.client("ec2", config=retry_config())
    with pytest.raises(Exception) as caught:
        client.describe_vpcs()
    assert not isinstance(caught.value, AccountTimeoutError)
    assert len(attempts) == 10


def test_after_detach_the_session_retries_as_before(no_backoff):
    clock = FakeClock()
    attempts = []
    session = _session_with_failing_endpoint(clock, attempts, slow_seconds=100)
    deadline = _AccountDeadline("111111111111", 60, clock=clock)
    deadline.start()
    deadline.attach(session)
    deadline.detach(session)
    client = session.client("ec2", config=retry_config())
    with pytest.raises(Exception) as caught:
        client.describe_vpcs()
    assert not isinstance(caught.value, AccountTimeoutError)
    assert len(attempts) == 10
