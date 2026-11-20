"""A2 (plan 2.3, 2.5, 2.6): the run's limiter is wired into the scan.

* One ``InFlightLimiter`` per run, with the ``--concurrency`` value.
* Each account's session gets it during the account's scan, after the read-only
  guard and the account deadline: every AWS call of the scan takes a slot of
  its own account, and a call the guard refuses takes none.
* The session's client cache is on during the scan.
* Waiting for a slot counts against the account's time limit: an account
  that waits past it fails with today's time-limit message.
* ``stop_running_scans()`` (SIGTERM, Ctrl-C) stops every running limiter.

moto only; no real time: the waiting test uses a fake clock and a fake wait.
"""

import threading

import boto3
import pytest
from moto import mock_aws

from inventag.core import cloud_bom_generator as cbg
from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from inventag.core.limiter import InFlightLimiter
from inventag.discovery.aws_clients import create_client
from inventag.security.read_only_guard import (
    ReadOnlyViolationError,
    install_global_guard,
    uninstall_global_guard,
)

ACCOUNTS = ("111111111111", "222222222222")


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


def _generator(tmp_path, **settings):
    config = MultiAccountConfig(
        accounts=[AccountCredentials(account_id=a) for a in ACCOUNTS],
        output_directory=str(tmp_path / "out"),
        enable_state_management=False,
        **settings,
    )
    return CloudBOMGenerator(config)


def _contexts():
    return {
        account: AccountContext(
            credentials=AccountCredentials(account_id=account),
            session=boto3.Session(region_name="us-east-1"),
            caller_identity={"Account": account},
            accessible_regions=["us-east-1"],
        )
        for account in ACCOUNTS
    }


def _list_buckets(account_id, context):
    create_client(context.session, "s3", "us-east-1").list_buckets()
    return [{"service": "S3", "id": f"b-{account_id}", "region": "us-east-1"}]


def test_one_limiter_per_run_with_the_concurrency_value(tmp_path):
    generator = _generator(tmp_path, concurrency=8)
    assert isinstance(generator.limiter, InFlightLimiter)
    assert generator.limiter.limit == 8
    assert _generator(tmp_path).limiter.limit == 64
    assert _generator(tmp_path).limiter is not generator.limiter


@pytest.mark.parametrize("parallel", [True, False])
def test_every_call_of_an_account_takes_a_slot_of_that_account(
    aws, tmp_path, monkeypatch, parallel
):
    generator = _generator(tmp_path, parallel_account_processing=parallel)
    taken = []
    acquire = generator.limiter.acquire

    def recording_acquire(account, service, region, deadline=None):
        taken.append((account, service, deadline is not None))
        return acquire(account, service, region, deadline)

    monkeypatch.setattr(generator.limiter, "acquire", recording_acquire)
    monkeypatch.setattr(
        generator,
        "_discover_account_resources_inner",
        lambda account_id, context: _list_buckets(account_id, context),
    )
    contexts = _contexts()
    if parallel:
        found = generator._parallel_account_discovery(contexts)
    else:
        found = generator._sequential_account_discovery(contexts)

    assert sorted(r["id"] for r in found) == [f"b-{a}" for a in ACCOUNTS]
    # One slot per call, attributed to the account, with its time limit.
    assert sorted(taken) == [(a, "s3", True) for a in ACCOUNTS]
    assert generator.limiter.in_flight() == 0


def test_the_client_cache_is_on_during_the_scan(aws, tmp_path, monkeypatch):
    generator = _generator(tmp_path)
    seen = []

    def inner(account_id, context):
        seen.append(
            create_client(context.session, "s3", "us-east-1")
            is create_client(context.session, "s3", "us-east-1")
        )
        return []

    monkeypatch.setattr(generator, "_discover_account_resources_inner", inner)
    generator._sequential_account_discovery(_contexts())
    assert seen == [True, True]


def test_a_call_the_guard_refuses_takes_no_slot(aws, tmp_path, monkeypatch):
    uninstall_global_guard()
    install_global_guard()
    try:
        generator = _generator(tmp_path)
        refused = []

        def inner(account_id, context):
            s3 = create_client(context.session, "s3", "us-east-1")
            try:
                s3.create_bucket(Bucket=f"not-{account_id}")
            except ReadOnlyViolationError:
                refused.append(generator.limiter.in_flight(account=account_id))
            return []

        taken = []
        acquire = generator.limiter.acquire
        monkeypatch.setattr(
            generator.limiter,
            "acquire",
            lambda *a, **k: taken.append(a) or acquire(*a, **k),
        )
        monkeypatch.setattr(generator, "_discover_account_resources_inner", inner)
        generator._sequential_account_discovery(_contexts())
    finally:
        uninstall_global_guard()
    assert refused == [0, 0]
    assert taken == []


class FakeTime:
    """A clock that moves only when the limiter waits."""

    def __init__(self):
        self.now = 1000.0

    def clock(self):
        return self.now

    def wait(self, condition, timeout):
        self.now += timeout if timeout is not None else 1.0


def test_waiting_for_a_slot_past_the_time_limit_is_todays_time_limit_failure(
    aws, tmp_path, monkeypatch
):
    fake = FakeTime()
    generator = _generator(tmp_path, concurrency=1, account_processing_timeout=60)
    generator.limiter = InFlightLimiter(1, clock=fake.clock, wait=fake.wait)
    generator._clock = fake.clock
    # Another account holds the run's only slot for the whole test.
    generator.limiter.acquire("999999999999", "ec2", "us-east-1")
    monkeypatch.setattr(
        generator,
        "_discover_account_resources_inner",
        lambda account_id, context: _list_buckets(account_id, context),
    )
    contexts = _contexts()
    found = generator._sequential_account_discovery(contexts)

    assert found == []
    for account in ACCOUNTS:
        assert contexts[account].processing_errors == [
            "Resource discovery failed: timed out after 60 seconds "
            "(--account-processing-timeout); no results of this account are in "
            "the report"
        ]
    assert generator.limiter.in_flight(account=ACCOUNTS[0]) == 0


def test_stop_running_scans_stops_the_limiter_of_every_run(tmp_path):
    first, second = _generator(tmp_path), _generator(tmp_path)
    cbg.stop_running_scans()
    assert first.limiter.stopped and second.limiter.stopped


def test_a_stopped_run_starts_no_new_aws_request(aws, tmp_path, monkeypatch):
    generator = _generator(tmp_path)
    errors = []

    def inner(account_id, context):
        try:
            _list_buckets(account_id, context)
        except Exception as error:  # noqa: BLE001 - the test looks at it
            errors.append(type(error).__name__)
        return []

    monkeypatch.setattr(generator, "_discover_account_resources_inner", inner)
    generator.limiter.stop()
    generator._sequential_account_discovery(_contexts())
    assert errors == ["LimiterStopped", "LimiterStopped"]


def test_a_waiting_call_ends_at_once_when_the_run_is_stopped(
    aws, tmp_path, monkeypatch
):
    generator = _generator(tmp_path, concurrency=1)
    generator.limiter.acquire("999999999999", "ec2", "us-east-1")  # run is full
    waiting = threading.Event()
    original_wait = generator.limiter._wait

    def wait(condition, timeout):
        waiting.set()
        original_wait(condition, timeout)

    generator.limiter._wait = wait
    errors = []

    def inner(account_id, context):
        try:
            _list_buckets(account_id, context)
        except Exception as error:  # noqa: BLE001 - the test looks at it
            errors.append(type(error).__name__)
        return []

    monkeypatch.setattr(generator, "_discover_account_resources_inner", inner)
    contexts = {ACCOUNTS[0]: _contexts()[ACCOUNTS[0]]}
    worker = threading.Thread(
        target=generator._sequential_account_discovery, args=(contexts,)
    )
    worker.start()
    assert waiting.wait(30)
    cbg.stop_running_scans()
    worker.join(30)
    assert not worker.is_alive()
    assert errors == ["LimiterStopped"]
