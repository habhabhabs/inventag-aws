"""A2 (plan 2.1 row 5, 2.5): the credential stage runs accounts in parallel.

* Accounts are validated through an account pool (``--max-concurrent-accounts``)
  and their contexts are inserted in the configured order, whatever order
  they finish in.
* ``--disable-parallel-processing``: one account after the other, as before.
* An account that needs a terminal (a profile with ``mfa_serial`` while stdin
  is a terminal: the SDK asks for the code) is handled first, on the main
  thread, one at a time.
* Every session the stage creates has the run's limiter, so ``--concurrency
  1`` is one request at a time here too.
* The default credentials' identity is looked up once per run, also when
  accounts ask for it at the same time (same AWS calls as v1.3.x).

Barriers and events force the interleavings; no sleep.
"""

import sys
import threading

import boto3
import pytest
from moto import mock_aws

from inventag.core import cloud_bom_generator as cbg
from inventag.core.cloud_bom_generator import (
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)

A, B, C = "111111111111", "222222222222", "333333333333"


@pytest.fixture
def aws(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-creds"))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


def _generator(tmp_path, accounts, **settings):
    return CloudBOMGenerator(
        MultiAccountConfig(
            accounts=accounts,
            output_directory=str(tmp_path / "out"),
            enable_state_management=False,
            **settings,
        )
    )


def _keys(account):
    return AccountCredentials(
        account_id=account,
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="fake-secret-for-moto-only",
        regions=["us-east-1"],
    )


def _stub_identity(generator, monkeypatch, hook=None):
    """Each account's identity is its own ID; ``hook(account)`` runs first."""
    by_session = {}
    create = generator._create_account_session

    def create_session(credentials):
        if hook:
            hook(credentials.account_id)
        session = create(credentials)
        by_session[id(session)] = credentials.account_id
        return session

    monkeypatch.setattr(generator, "_create_account_session", create_session)
    monkeypatch.setattr(
        generator,
        "_get_caller_identity",
        lambda session: {"Account": by_session[id(session)], "Arn": ""},
    )


def test_contexts_are_in_configured_order_when_the_first_finishes_last(
    aws, tmp_path, monkeypatch
):
    generator = _generator(
        tmp_path, [_keys(A), _keys(B), _keys(C)], max_concurrent_accounts=3
    )
    others_done = threading.Event()
    started = threading.Barrier(3, timeout=30)
    finished = []
    lock = threading.Lock()

    def hook(account):
        started.wait()  # all three at once: the stage is parallel
        if account == A and not others_done.wait(30):
            raise AssertionError("B and C did not finish while A waited")

    def done(session, regions):
        with lock:
            finished.append(session)
            if len(finished) == 2:
                others_done.set()
        return list(regions)

    _stub_identity(generator, monkeypatch, hook)
    monkeypatch.setattr(generator, "_test_accessible_regions", done)
    contexts = generator._establish_account_contexts()
    assert list(contexts) == [A, B, C]
    assert list(generator.account_contexts) == [A, B, C]
    assert all(contexts[a].session is not None for a in (A, B, C))
    assert all(not contexts[a].processing_errors for a in (A, B, C))


def test_without_parallel_processing_accounts_run_one_after_the_other(
    aws, tmp_path, monkeypatch
):
    generator = _generator(
        tmp_path, [_keys(A), _keys(B)], parallel_account_processing=False
    )
    threads = []
    _stub_identity(
        generator, monkeypatch, lambda account: threads.append(threading.get_ident())
    )
    contexts = generator._establish_account_contexts()
    assert list(contexts) == [A, B]
    assert threads == [threading.get_ident()] * 2


def test_a_failed_account_keeps_its_place_and_its_message(aws, tmp_path, monkeypatch):
    generator = _generator(tmp_path, [_keys(A), _keys(B), _keys(C)])

    def hook(account):
        if account == B:
            raise RuntimeError("no way in")

    _stub_identity(generator, monkeypatch, hook)
    contexts = generator._establish_account_contexts()
    assert list(contexts) == [A, B, C]
    assert contexts[B].session is None
    assert contexts[B].processing_errors == ["Context establishment failed: no way in"]


def test_an_account_that_needs_a_terminal_goes_first_on_the_main_thread(
    aws, tmp_path, monkeypatch
):
    config = tmp_path / "config"
    config.write_text(
        "[profile mfa]\n"
        "aws_access_key_id = AKIAIOSFODNN7EXAMPLE\n"
        "aws_secret_access_key = fake-secret-for-moto-only\n"
        "mfa_serial = arn:aws:iam::111111111111:mfa/me\n"
    )
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))

    class Terminal:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", Terminal())
    mfa = AccountCredentials(account_id=A, profile_name="mfa", regions=["us-east-1"])
    generator = _generator(tmp_path, [_keys(B), mfa, _keys(C)])
    seen = []
    _stub_identity(
        generator,
        monkeypatch,
        lambda account: seen.append((account, threading.get_ident())),
    )
    monkeypatch.setattr(generator, "_sts", lambda session: _NoCallSts())
    contexts = generator._establish_account_contexts()
    assert list(contexts) == [B, A, C]  # configured order
    assert seen[0] == (A, threading.get_ident())
    assert {account for account, _ in seen[1:]} == {B, C}


class _NoCallSts:
    def get_caller_identity(self):
        return {"Account": A}


def test_every_session_of_the_stage_has_the_run_limiter(aws, tmp_path, monkeypatch):
    moto_account = "123456789012"  # the account moto answers for
    generator = _generator(tmp_path, [_keys(moto_account)], concurrency=1)
    taken = []
    acquire = generator.limiter.acquire

    def recording_acquire(account, service, region, deadline=None):
        taken.append((account, service))
        return acquire(account, service, region, deadline)

    monkeypatch.setattr(generator.limiter, "acquire", recording_acquire)
    contexts = generator._establish_account_contexts()
    assert not contexts[moto_account].processing_errors
    assert (moto_account, "sts") in taken and (moto_account, "ec2") in taken
    assert {account for account, _ in taken} == {moto_account}
    assert generator.limiter.in_flight() == 0


def test_the_default_identity_is_looked_up_once_when_asked_at_the_same_time(
    tmp_path, monkeypatch
):
    generator = _generator(tmp_path, [])
    first_inside, second_called, release = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    calls = []

    class Sts:
        def get_caller_identity(self):
            calls.append(threading.get_ident())
            if len(calls) == 1:
                first_inside.set()
                release.wait(30)
            else:
                second_called.set()
            return {"Account": A, "Arn": f"arn:aws:iam::{A}:user/me"}

    monkeypatch.setattr(generator, "_sts", lambda session: Sts())
    monkeypatch.setattr(cbg.boto3, "Session", lambda *a, **k: object())
    results = []
    one = threading.Thread(
        target=lambda: results.append(generator._default_caller_account())
    )
    two = threading.Thread(
        target=lambda: results.append(generator._default_caller_account())
    )
    one.start()
    assert first_inside.wait(30)
    two.start()
    # With the lookup under a lock, the second thread cannot reach the call.
    second_called.wait(2)
    release.set()
    one.join(30)
    two.join(30)
    assert results == [A, A]
    assert len(calls) == 1
