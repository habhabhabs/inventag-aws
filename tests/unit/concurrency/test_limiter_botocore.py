"""A1 (plan 2.3, 2.5): the limiter on botocore's events.

A slot is taken in ``before-send`` and given back in ``response-received``,
on every path: success, HTTP error, throttling with the SDK's retry,
connection error, a handler that raises before the limiter, one that raises
after it, a streamed body. A call the read-only guard refuses takes no slot.

No network: a ``before-send`` handler answers every request. The SDK's
backoff sleep is replaced by a recorder, so nothing sleeps.
"""

import io
import types

import boto3
import botocore.endpoint
import pytest
from botocore.awsrequest import AWSResponse
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from inventag.core.cloud_bom_generator import AccountTimeoutError, _AccountDeadline
from inventag.core.limiter import InFlightLimiter, LimiterStopped
from inventag.security.read_only_guard import ReadOnlyGuard, ReadOnlyViolationError

ACCOUNT = "111122223333"
REGION = "eu-west-1"
KEY = (ACCOUNT, "dynamodb", REGION)


class _Raw(io.BytesIO):
    def stream(self, **kwargs):
        yield self.getvalue()


def _response(request, status, body, headers=None):
    return AWSResponse(request.url, status, headers or {}, _Raw(body))


class Responder:
    """Answers each request in turn from ``answers``; records what it saw."""

    def __init__(self, limiter, answers):
        self.limiter = limiter
        self.answers = list(answers)
        self.seen_in_flight = []
        self.calls = 0

    def __call__(self, request, **kwargs):
        self.calls += 1
        self.seen_in_flight.append(
            (self.limiter.in_flight(), self.limiter.in_flight(key=KEY))
        )
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, body = answer
        return _response(request, status, body)


def _session():
    return boto3.Session(
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="fake-secret-for-tests-only",
        region_name=REGION,
    )


def _setup(answers, attempts=1, limit=8, **limiter_options):
    session = _session()
    limiter = InFlightLimiter(limit, **limiter_options)
    limiter.attach(session, ACCOUNT)
    responder = Responder(limiter, answers)
    session.events.register("before-send", responder)
    client = session.client(
        "dynamodb",
        config=Config(retries={"mode": "standard", "total_max_attempts": attempts}),
    )
    return session, limiter, responder, client


OK = (200, b'{"TableNames": []}')
NOT_FOUND = (400, b'{"__type": "ResourceNotFoundException", "message": "no"}')
THROTTLED = (400, b'{"__type": "ThrottlingException", "message": "slow down"}')


def test_success_holds_one_slot_during_the_request_and_frees_it():
    _, limiter, responder, client = _setup([OK])
    assert client.list_tables()["TableNames"] == []
    assert responder.seen_in_flight == [(1, 1)]
    assert limiter.in_flight() == 0


def test_the_key_uses_the_clients_region_and_the_service_id():
    session, limiter, responder, _ = _setup([OK])
    other = session.client(
        "dynamodb",
        region_name="us-west-2",
        config=Config(retries={"total_max_attempts": 1}),
    )
    seen = []
    responder.answers = [OK]
    original = responder.__call__

    def spy(request, **kwargs):
        seen.append(limiter.in_flight(key=(ACCOUNT, "dynamodb", "us-west-2")))
        return original(request, **kwargs)

    session.events.unregister("before-send", responder)
    session.events.register("before-send", spy)
    other.list_tables()
    assert seen == [1]
    assert limiter.in_flight() == 0


def test_an_http_error_frees_the_slot():
    _, limiter, responder, client = _setup([NOT_FOUND])
    with pytest.raises(ClientError):
        client.list_tables()
    assert responder.seen_in_flight == [(1, 1)]
    assert limiter.in_flight() == 0


def test_a_retried_throttle_holds_no_slot_during_the_sdk_backoff(monkeypatch):
    slept = []
    clock = [100.0]

    def advance(condition, timeout):  # the limiter's pause after a throttle
        clock[0] += timeout

    _, limiter, responder, client = _setup(
        [THROTTLED, OK], attempts=2, clock=lambda: clock[0], wait=advance
    )

    def fake_sleep(seconds):
        slept.append((seconds, limiter.in_flight()))

    monkeypatch.setattr(
        botocore.endpoint, "time", types.SimpleNamespace(sleep=fake_sleep)
    )
    client.list_tables()
    assert responder.calls == 2
    assert [in_flight for _, in_flight in slept] == [0]
    assert responder.seen_in_flight == [(1, 1), (1, 1)]
    assert limiter.in_flight() == 0
    assert limiter.key_limit(KEY) == 2


def test_a_connection_error_frees_the_slot():
    _, limiter, responder, client = _setup(
        [
            EndpointConnectionError(
                endpoint_url="https://dynamodb.eu-west-1.amazonaws.com"
            )
        ]
    )
    with pytest.raises(EndpointConnectionError):
        client.list_tables()
    assert responder.seen_in_flight == [(1, 1)]
    assert limiter.in_flight() == 0


def test_a_handler_that_raises_before_the_limiter_takes_no_slot_and_frees_none():
    session, limiter, responder, client = _setup([OK])

    def boom(**kwargs):
        raise RuntimeError("a more specific handler failed")

    # botocore runs handlers of the more specific event name first.
    session.events.register("before-send.dynamodb.ListTables", boom)
    client = session.client(
        "dynamodb", config=Config(retries={"total_max_attempts": 1})
    )
    other = limiter.acquire("999", "s3", "us-east-1")
    with pytest.raises(RuntimeError, match="more specific"):
        client.list_tables()
    assert responder.calls == 0
    assert limiter.in_flight() == 1  # the unrelated slot is still held
    limiter.release(other)
    assert limiter.in_flight() == 0


def test_a_handler_that_raises_after_the_limiter_frees_the_slot():
    """The account deadline's before-send handler raises after the limiter's."""
    session = _session()
    clock = [0.0]
    deadline = _AccountDeadline(ACCOUNT, 10, clock=lambda: clock[0])
    deadline.attach(session)  # registered before the limiter, runs after it
    limiter = InFlightLimiter(8)
    limiter.attach(session, ACCOUNT)
    responder = Responder(limiter, [OK, OK])
    session.events.register("before-send", responder)
    client = session.client(
        "dynamodb", config=Config(retries={"total_max_attempts": 1})
    )
    deadline.start()
    client.list_tables()
    assert responder.seen_in_flight == [(1, 1)]
    clock[0] = 11.0
    # before-call refuses first; make before-send the one that refuses:
    session.events.unregister("before-call", unique_id=deadline._hook_id("call"))
    client = session.client(
        "dynamodb", config=Config(retries={"total_max_attempts": 1})
    )
    with pytest.raises(AccountTimeoutError):
        client.list_tables()
    assert responder.calls == 1
    assert limiter.in_flight() == 0


def test_a_streamed_body_frees_the_slot_when_the_response_arrives():
    session = _session()
    limiter = InFlightLimiter(8)
    limiter.attach(session, ACCOUNT)
    seen = []

    def answer(request, **kwargs):
        seen.append(limiter.in_flight(key=(ACCOUNT, "s3", REGION)))
        return AWSResponse(request.url, 200, {"Content-Length": "4"}, _Raw(b"data"))

    session.events.register("before-send", answer)
    s3 = session.client("s3", config=Config(retries={"total_max_attempts": 1}))
    result = s3.get_object(Bucket="bucket", Key="key")
    assert seen == [1]
    assert limiter.in_flight() == 0
    assert result["Body"].read() == b"data"


def test_a_call_the_read_only_guard_refuses_takes_no_slot(monkeypatch):
    session = _session()
    ReadOnlyGuard().attach_session(session)
    limiter = InFlightLimiter(8)
    limiter.attach(session, ACCOUNT)
    acquired = []
    original = limiter.acquire

    def spy(*args, **kwargs):
        acquired.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(limiter, "acquire", spy)
    responder = Responder(limiter, [])
    session.events.register("before-send", responder)
    client = session.client(
        "dynamodb", config=Config(retries={"total_max_attempts": 1})
    )
    with pytest.raises(ReadOnlyViolationError):
        client.delete_table(TableName="t")
    assert acquired == []
    assert responder.calls == 0
    assert limiter.in_flight() == 0


def test_the_limiter_runs_before_handlers_registered_earlier():
    session = _session()
    seen = []
    session.events.register(
        "before-send", lambda **kwargs: seen.append(limiter.in_flight())
    )
    limiter = InFlightLimiter(8)
    limiter.attach(session, ACCOUNT)
    session.events.register("before-send", Responder(limiter, [OK]))
    session.client(
        "dynamodb", config=Config(retries={"total_max_attempts": 1})
    ).list_tables()
    assert seen == [1]


def test_a_stopped_limiter_refuses_the_call_without_a_request_or_retry():
    _, limiter, responder, client = _setup([OK, OK], attempts=3)
    limiter.stop()
    with pytest.raises(LimiterStopped):
        client.list_tables()
    assert responder.calls == 0
    assert limiter.in_flight() == 0


def test_detach_removes_both_handlers():
    session, limiter, responder, _ = _setup([OK])
    limiter.detach(session, ACCOUNT)
    client = session.client(
        "dynamodb", config=Config(retries={"total_max_attempts": 1})
    )
    client.list_tables()
    assert responder.seen_in_flight == [(0, 0)]


def test_a_slot_left_by_an_interrupted_request_is_reclaimed_by_the_next_one():
    """A BaseException (Ctrl-C) between the two events leaves the thread's slot;
    the same thread's next request gives it back before taking a new one."""
    session, limiter, responder, client = _setup([OK])
    limiter._on_before_send(
        ACCOUNT,
        None,
        request=types.SimpleNamespace(context={}),
        event_name="before-send.dynamodb.ListTables",
    )
    assert limiter.in_flight() == 1
    client.list_tables()
    assert limiter.in_flight() == 0


def test_two_accounts_on_one_session_object_keep_their_own_handlers():
    session = _session()
    limiter = InFlightLimiter(8)
    limiter.attach(session, "111")
    limiter.attach(session, "222")
    limiter.detach(session, "111")
    seen = []

    def answer(request, **kwargs):
        seen.append(limiter.in_flight(account="222"))
        return _response(request, *OK)

    session.events.register("before-send", answer)
    session.client(
        "dynamodb", config=Config(retries={"total_max_attempts": 1})
    ).list_tables()
    assert seen == [1]
