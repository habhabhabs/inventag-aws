"""Per-account time limit, partial failures and failed report formats."""

from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    AccountTimeoutError,
    CloudBOMGenerator,
    MultiAccountConfig,
    _AccountDeadline,
)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def aws(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


def test_deadline_blocks_calls_after_the_limit_only(aws):
    clock = FakeClock()
    session = boto3.Session()
    deadline = _AccountDeadline("111111111111", 60, clock=clock)
    deadline.start()
    deadline.attach(session)
    ec2 = session.client("ec2", region_name="us-east-1")
    ec2.describe_regions()
    clock.now += 61
    with pytest.raises(AccountTimeoutError, match="60 seconds"):
        ec2.describe_regions()
    assert deadline.expired
    deadline.detach(session)
    # After detach, the session (used later for reports) works again.
    session.client("ec2", region_name="us-east-1").describe_regions()
    ec2.describe_regions()


def _contexts(account_ids):
    return {
        account_id: AccountContext(
            credentials=AccountCredentials(
                account_id=account_id, account_name=f"acct-{account_id}"
            ),
            session=boto3.Session(),
            caller_identity={"Account": account_id},
            accessible_regions=["us-east-1"],
        )
        for account_id in account_ids
    }


class SlowOrFastInventory:
    """Fake discovery: the 'slow' account runs past its limit."""

    clock = None
    calls_after_limit = 0
    fast_done = None

    def __init__(self, session, regions, **kwargs):
        self.session = session

    def discover_all_resources(self):
        ec2 = self.session.client("ec2", region_name="us-east-1")
        ec2.describe_regions()
        resource = {"id": "r", "service": "EC2", "type": "Instance"}
        if getattr(self.session, "_slow", False):
            # Wait for the fast account (one shared fake clock for both).
            SlowOrFastInventory.fast_done.wait(10)
            SlowOrFastInventory.clock.now += 10_000
            # Real discovery code catches errors per service and carries on.
            for _ in range(5):
                try:
                    ec2.describe_vpcs()
                    SlowOrFastInventory.calls_after_limit += 1
                except Exception:
                    pass
        else:
            SlowOrFastInventory.fast_done.set()
        return [resource]


@pytest.mark.parametrize("parallel", [True, False])
def test_timed_out_account_fails_and_the_others_are_kept(aws, tmp_path, parallel):
    clock = FakeClock()
    SlowOrFastInventory.clock = clock
    SlowOrFastInventory.fast_done = __import__("threading").Event()
    SlowOrFastInventory.calls_after_limit = 0
    config = MultiAccountConfig(
        accounts=[],
        output_directory=str(tmp_path),
        account_processing_timeout=60,
        parallel_account_processing=parallel,
    )
    generator = CloudBOMGenerator(config)
    generator._clock = clock
    generator._poll_seconds = 0.01
    contexts = _contexts(["111111111111", "222222222222"])
    contexts["222222222222"].session._slow = True
    generator.account_contexts.update(contexts)

    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", SlowOrFastInventory
    ):
        if parallel:
            resources = generator._parallel_account_discovery(contexts)
        else:
            resources = generator._sequential_account_discovery(contexts)

    assert [r["source_account_id"] for r in resources] == ["111111111111"]
    assert SlowOrFastInventory.calls_after_limit == 0
    assert generator._processing_stats["successful_accounts"] == 1
    assert generator._processing_stats["failed_accounts"] == 1
    errors = contexts["222222222222"].processing_errors
    assert len(errors) == 1 and "60 seconds" in errors[0]
    assert contexts["111111111111"].resource_count == 1
    failed = generator._failed_accounts()
    assert [item["account_id"] for item in failed] == ["222222222222"]


def test_a_report_format_that_fails_fails_the_run(aws, tmp_path):
    config = MultiAccountConfig(
        accounts=[AccountCredentials(account_id="123456789012", regions=["us-east-1"])],
        output_directory=str(tmp_path),
        enable_billing_validation=False,
    )
    generator = CloudBOMGenerator(config)
    with (
        patch("inventag.core.cloud_bom_generator.AWSResourceInventory") as inventory,
        patch(
            "inventag.core.cloud_bom_generator.BOMConverter.generate_excel_bom",
            side_effect=RuntimeError("disk full"),
        ),
    ):
        inventory.return_value.discover_all_resources.return_value = [
            {"id": "b", "service": "S3", "type": "Bucket", "region": "us-east-1"}
        ]
        result = generator.generate_comprehensive_bom(output_formats=["excel"])
    assert result["success"] is False
    assert "excel: disk full" in result["error"]
    assert result["bom_generation"]["success"] is False


class HangingInventory:
    """Fake discovery: account 222... blocks until the test releases it."""

    clock = None
    started = None
    release = None
    finished = None
    calls_after_release = []

    def __init__(self, session, regions, **kwargs):
        self.session = session

    def discover_all_resources(self):
        if not getattr(self.session, "_hang", False):
            return [{"id": "ok", "service": "S3", "type": "Bucket"}]
        HangingInventory.started.set()
        HangingInventory.clock.now += 10_000  # the account is now past its limit
        HangingInventory.release.wait(10)
        try:
            self.session.client("ec2", region_name="us-east-1").describe_vpcs()
            HangingInventory.calls_after_release.append("allowed")
        except Exception as e:
            HangingInventory.calls_after_release.append(type(e).__name__)
        HangingInventory.finished.set()
        return [{"id": "late", "service": "EC2", "type": "Instance"}] * 7


def test_hung_account_is_abandoned_and_cannot_change_results_later(aws, tmp_path):
    import threading

    clock = FakeClock()
    HangingInventory.clock = clock
    HangingInventory.started = threading.Event()
    HangingInventory.release = threading.Event()
    HangingInventory.finished = threading.Event()
    HangingInventory.calls_after_release = []
    config = MultiAccountConfig(
        accounts=[], output_directory=str(tmp_path), account_processing_timeout=60
    )
    generator = CloudBOMGenerator(config)
    generator._clock = clock
    generator._poll_seconds = 0.01
    contexts = _contexts(["111111111111", "222222222222"])
    contexts["222222222222"].session._hang = True
    generator.account_contexts.update(contexts)

    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", HangingInventory
    ):
        resources = generator._parallel_account_discovery(contexts)
        # The main thread returned while the worker is still blocked.
        assert HangingInventory.started.is_set()
        assert not HangingInventory.finished.is_set()
        HangingInventory.release.set()
        assert HangingInventory.finished.wait(10)

    assert [r["id"] for r in resources] == ["ok"]
    assert HangingInventory.calls_after_release == ["AccountTimeoutError"]
    slow = contexts["222222222222"]
    assert slow.resource_count == 0 and slow.discovered_services == []
    assert len(slow.processing_errors) == 1
    assert "timed out after 60 seconds" in slow.processing_errors[0]
    assert generator._processing_stats["successful_accounts"] == 1
    assert generator._processing_stats["failed_accounts"] == 1


def test_one_timed_out_account_still_gives_a_report(aws, tmp_path):
    clock = FakeClock()
    SlowOrFastInventory.clock = clock
    SlowOrFastInventory.fast_done = __import__("threading").Event()
    config = MultiAccountConfig(
        accounts=[
            AccountCredentials(account_id="123456789012", regions=["us-east-1"]),
            AccountCredentials(account_id="123456789012", regions=["us-east-1"]),
        ],
        output_directory=str(tmp_path),
        account_processing_timeout=60,
        enable_billing_validation=False,
    )
    generator = CloudBOMGenerator(config)
    generator._clock = clock
    generator._poll_seconds = 0.01
    # Two contexts: the real one (fast) and a slow copy under another ID.
    real = generator._establish_account_contexts

    def establish():
        contexts = real()
        fast = contexts["123456789012"]
        slow = AccountContext(
            credentials=AccountCredentials(account_id="999999999999"),
            session=boto3.Session(),
            caller_identity={},
            accessible_regions=["us-east-1"],
        )
        slow.session._slow = True
        contexts = {"123456789012": fast, "999999999999": slow}
        generator.account_contexts = dict(contexts)
        return contexts

    generator._establish_account_contexts = establish
    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", SlowOrFastInventory
    ):
        result = generator.generate_multi_account_bom(output_formats=["json"])
    assert result["success"] is True, result.get("error")
    assert [a["account_id"] for a in result["failed_accounts"]] == ["999999999999"]
    assert len(result["bom_generation"]["generated_files"]) == 1


# ------------------------------------------------------------- checkpoints
class FakeStore:
    """Same interface as inventag.state.partial_results.PartialResultStore."""

    saved = {}
    cleared = 0

    def __init__(self, state_dir, run_key, max_age_hours=24.0):
        self.run_key = run_key

    def save_account(self, account_id, resources, regions=None):
        FakeStore.saved[(self.run_key, account_id)] = list(resources)

    def load_account(self, account_id):
        from datetime import datetime, timezone
        from types import SimpleNamespace

        resources = FakeStore.saved.get((self.run_key, account_id))
        if resources is None:
            return None
        return SimpleNamespace(
            resources=resources,
            completed_at=datetime(2026, 11, 13, 2, 10, tzinfo=timezone.utc),
        )

    def completed_accounts(self):
        return {a: None for (k, a) in FakeStore.saved if k == self.run_key}

    def clear(self):
        FakeStore.cleared += 1
        for key in [k for k in FakeStore.saved if k[0] == self.run_key]:
            del FakeStore.saved[key]


@pytest.fixture
def fake_store(monkeypatch):
    import inventag.core.cloud_bom_generator as cbg

    FakeStore.saved = {}
    FakeStore.cleared = 0
    monkeypatch.setattr(cbg, "PartialResultStore", FakeStore)
    monkeypatch.setattr(cbg, "make_run_key", lambda scope: str(sorted(scope)))
    return FakeStore


class CountingInventory:
    scanned = []
    fail = set()

    def __init__(self, session, regions, **kwargs):
        self.session = session

    def discover_all_resources(self):
        account = self.session._account
        CountingInventory.scanned.append(account)
        if account in CountingInventory.fail:
            raise RuntimeError("throttled")
        return [{"id": f"r-{account}", "service": "S3", "type": "Bucket"}]


def _run(tmp_path, resume):
    config = MultiAccountConfig(
        accounts=[], output_directory=str(tmp_path), resume=resume
    )
    generator = CloudBOMGenerator(config)
    generator._poll_seconds = 0.01

    def establish():
        contexts = _contexts(["111111111111", "222222222222"])
        for account_id, ctx in contexts.items():
            ctx.session._account = account_id
        generator.account_contexts = dict(contexts)
        return contexts

    generator._establish_account_contexts = establish
    generator.config.accounts = [object(), object()]
    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", CountingInventory
    ):
        return generator.generate_multi_account_bom(output_formats=["json"])


def test_resume_reuses_finished_accounts_only_when_asked(aws, tmp_path, fake_store):
    CountingInventory.scanned = []
    CountingInventory.fail = {"222222222222"}
    first = _run(tmp_path, resume=False)
    assert first["success"] is True
    assert [k[1] for k in fake_store.saved] == ["111111111111"]
    assert fake_store.cleared == 0

    # Without --resume, saved results are not reused.
    CountingInventory.scanned = []
    _run(tmp_path, resume=False)
    assert sorted(CountingInventory.scanned) == ["111111111111", "222222222222"]

    # With --resume, only the failed account is scanned again; the report
    # says which account is reused and when it was scanned.
    CountingInventory.scanned = []
    CountingInventory.fail = set()
    result = _run(tmp_path, resume=True)
    assert CountingInventory.scanned == ["222222222222"]
    assert result["success"] is True
    assert result["reused_accounts"] == {"111111111111": "2026-11-13 02:10 UTC"}
    assert result["processing_statistics"]["successful_accounts"] == 2
    # Every account finished: the checkpoints are removed.
    assert fake_store.cleared == 1 and fake_store.saved == {}


def test_timed_out_account_is_not_checkpointed(aws, tmp_path, fake_store):
    clock = FakeClock()
    SlowOrFastInventory.clock = clock
    SlowOrFastInventory.fast_done = __import__("threading").Event()
    config = MultiAccountConfig(
        accounts=[], output_directory=str(tmp_path), account_processing_timeout=60
    )
    generator = CloudBOMGenerator(config)
    generator._clock = clock
    generator._poll_seconds = 0.01
    contexts = _contexts(["111111111111", "222222222222"])
    contexts["222222222222"].session._slow = True
    generator.account_contexts.update(contexts)
    generator._checkpoints = FakeStore("x", "k")
    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", SlowOrFastInventory
    ):
        generator._parallel_account_discovery(contexts)
    assert [k[1] for k in fake_store.saved] == ["111111111111"]
