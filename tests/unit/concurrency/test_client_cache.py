"""A1 (plan 2.3, 2.5): the client cache of ``aws_clients.create_client``.

With the cache turned on for a session, there is one client per (session,
service, region, retry settings), created under the module's lock and shared
by threads. Without it (every session today), each call makes a new client,
as in v1.3.0: the cache is not wired into a scan by this work order.
"""

import threading

import boto3

from inventag.discovery import aws_clients
from inventag.discovery.aws_clients import (
    MAX_ATTEMPTS,
    RETRY_MODE,
    create_client,
    enable_client_cache,
)


def _session():
    return boto3.Session(
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="fake-secret-for-tests-only",
        region_name="us-east-1",
    )


class CountingSession:
    """A stand-in session that records each client it creates."""

    def __init__(self):
        self.created = []
        self.lock_held = []

    def client(self, service_name, region_name=None, config=None):
        self.lock_held.append(_held_by_this_thread(aws_clients._CREATE_LOCK))
        client = object()
        self.created.append((service_name, region_name, config, client))
        return client


def _held_by_this_thread(lock):
    """True when another thread cannot take ``lock`` now."""
    taken = []

    def probe():
        got = lock.acquire(blocking=False)
        taken.append(got)
        if got:
            lock.release()

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join(10)
    return taken == [False]


def test_without_the_cache_each_call_makes_a_new_client_as_before():
    session = CountingSession()
    first = create_client(session, "s3", "us-east-1")
    second = create_client(session, "s3", "us-east-1")
    assert first is not second
    assert len(session.created) == 2


def test_with_the_cache_one_client_per_service_and_region():
    session = CountingSession()
    enable_client_cache(session)
    s3 = create_client(session, "s3", "us-east-1")
    assert create_client(session, "s3", "us-east-1") is s3
    assert create_client(session, "s3", "eu-west-1") is not s3
    assert create_client(session, "ec2", "us-east-1") is not s3
    assert create_client(session, "s3") is not s3  # no region named: its own key
    assert create_client(session, "s3") is create_client(session, "s3")
    assert len(session.created) == 4


def test_clients_are_created_under_the_lock():
    session = CountingSession()
    enable_client_cache(session)
    create_client(session, "s3", "us-east-1")
    create_client(session, "s3", "us-east-1")
    plain = CountingSession()
    create_client(plain, "s3", "us-east-1")
    assert session.lock_held == [True]
    assert plain.lock_held == [True]


def test_the_cache_belongs_to_one_session():
    first, second = CountingSession(), CountingSession()
    enable_client_cache(first)
    enable_client_cache(second)
    a = create_client(first, "s3", "us-east-1")
    b = create_client(second, "s3", "us-east-1")
    assert a is not b
    assert create_client(first, "s3", "us-east-1") is a
    assert create_client(second, "s3", "us-east-1") is b


def test_turning_the_cache_on_twice_keeps_the_clients():
    session = CountingSession()
    enable_client_cache(session)
    a = create_client(session, "s3", "us-east-1")
    enable_client_cache(session)
    assert create_client(session, "s3", "us-east-1") is a


def test_threads_asking_at_once_get_the_same_client():
    session = CountingSession()
    enable_client_cache(session)
    barrier = threading.Barrier(8)
    results = []
    results_lock = threading.Lock()

    def ask():
        barrier.wait(10)
        client = create_client(session, "lambda", "eu-west-1")
        with results_lock:
            results.append(client)

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert len(results) == 8
    assert len({id(client) for client in results}) == 1
    assert len(session.created) == 1


def test_a_cached_client_keeps_the_shared_retry_settings():
    session = _session()
    enable_client_cache(session)
    client = create_client(session, "sqs", "us-east-1")
    assert create_client(session, "sqs", "us-east-1") is client
    retries = client.meta.config.retries
    assert retries["mode"] == RETRY_MODE
    assert retries["total_max_attempts"] == MAX_ATTEMPTS


def test_the_users_retry_environment_still_wins_and_gets_its_own_client(monkeypatch):
    session = _session()
    enable_client_cache(session)
    ours = create_client(session, "sqs", "us-east-1")
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "3")
    users = create_client(session, "sqs", "us-east-1")
    assert users is not ours
    assert users.meta.config.retries.get("total_max_attempts") == 3
    assert create_client(session, "sqs", "us-east-1") is users
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "5")
    assert create_client(session, "sqs", "us-east-1") is not users
    monkeypatch.delenv("AWS_MAX_ATTEMPTS")
    assert create_client(session, "sqs", "us-east-1") is ours


def test_the_users_retry_mode_still_wins(monkeypatch):
    session = _session()
    enable_client_cache(session)
    monkeypatch.setenv("AWS_RETRY_MODE", "adaptive")
    client = create_client(session, "sqs", "us-east-1")
    assert client.meta.config.retries["mode"] == "adaptive"


def test_threads_sharing_a_cached_client_share_one_retry_quota():
    """Side effect stated in the plan (2.3): botocore keeps the ``standard``
    retry quota per client, so threads on one cached client draw on one quota."""
    session = _session()
    enable_client_cache(session)
    a = create_client(session, "sqs", "us-east-1")
    b = create_client(session, "sqs", "us-east-1")
    assert a is b
    assert a.meta.config.retries["mode"] == "standard"
