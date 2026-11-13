"""How the parts built on separate branches work together.

* the per-account time limit decides discovery's own limit, and an account
  that discovery stopped early keeps its results but counts as failed;
* region auto-discovery goes through ``discover_regions()``;
* ``--resume`` with the real state layer: run 1 with one account failing,
  run 2 reuses the finished account and scans only the other one;
* the snapshot records the failed account, and the report data carries the
  coverage ledger.
"""

import json
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
    _AccountDeadline,
)
from inventag.state.state_manager import StateManager


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


def _contexts(account_ids):
    contexts = {}
    for account_id in account_ids:
        session = boto3.Session()
        session._account = account_id
        contexts[account_id] = AccountContext(
            credentials=AccountCredentials(
                account_id=account_id, account_name=f"acct-{account_id}"
            ),
            session=session,
            caller_identity={"Account": account_id},
            accessible_regions=["us-east-1"],
        )
    return contexts


class FakeLedger:
    def __init__(self, entries):
        self._entries = entries

    def to_dict(self):
        return list(self._entries)


class LedgerInventory:
    """Fake discovery that records the limit it got and returns a ledger."""

    seen_timeouts = []
    unfinished = set()  # accounts whose listings ran out of time
    fail = set()  # accounts whose discovery raises
    scanned = []

    def __init__(self, session, regions, discovery_timeout=None, **kwargs):
        self.session = session
        LedgerInventory.seen_timeouts.append(discovery_timeout)
        account = session._account
        outcome = "timeout" if account in LedgerInventory.unfinished else "ok"
        self.coverage = FakeLedger(
            [
                {
                    "account_id": "",
                    "region": "us-east-1",
                    "source": "service-api",
                    "service": "s3",
                    "resource_type": "",
                    "operation": "ListBuckets",
                    "outcome": outcome,
                    "count": 1,
                }
            ]
        )

    def discover_all_resources(self):
        account = self.session._account
        LedgerInventory.scanned.append(account)
        if account in LedgerInventory.fail:
            raise RuntimeError("throttled after the retries")
        return [
            {
                "id": f"bucket-{account}",
                "service": "S3",
                "type": "Bucket",
                "region": "us-east-1",
                "arn": f"arn:aws:s3:::bucket-{account}",
                "source": "service-api",
            }
        ]


@pytest.fixture(autouse=True)
def _reset():
    LedgerInventory.seen_timeouts = []
    LedgerInventory.unfinished = set()
    LedgerInventory.fail = set()
    LedgerInventory.scanned = []


def _generator(tmp_path, **config):
    generator = CloudBOMGenerator(
        MultiAccountConfig(accounts=[], output_directory=str(tmp_path), **config)
    )
    generator._poll_seconds = 0.01
    return generator


# ------------------------------------------------------------------ timeouts
def test_discovery_limit_is_the_account_limit_minus_a_margin():
    clock = [100.0]
    deadline = _AccountDeadline("1", 1800, clock=lambda: clock[0])
    deadline.start()
    assert CloudBOMGenerator._discovery_time_limit(deadline) == pytest.approx(1500)
    clock[0] += 1000  # 800 s left
    assert CloudBOMGenerator._discovery_time_limit(deadline) == pytest.approx(500)
    small = _AccountDeadline("1", 60, clock=lambda: 0.0)
    small.start()
    assert CloudBOMGenerator._discovery_time_limit(small) == pytest.approx(48)
    assert CloudBOMGenerator._discovery_time_limit(None) == 600


@pytest.mark.parametrize("parallel", [True, False])
def test_account_stopped_by_discovery_limit_keeps_results_and_fails(
    aws, tmp_path, parallel
):
    generator = _generator(
        tmp_path, account_processing_timeout=120, parallel_account_processing=parallel
    )
    contexts = _contexts(["111111111111", "222222222222"])
    generator.account_contexts.update(contexts)
    LedgerInventory.unfinished = {"222222222222"}
    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", LedgerInventory
    ):
        if parallel:
            resources = generator._parallel_account_discovery(contexts)
        else:
            resources = generator._sequential_account_discovery(contexts)

    # Discovery got the per-account limit minus the margin, not a fixed 600 s.
    assert all(t == pytest.approx(96, abs=1) for t in LedgerInventory.seen_timeouts)
    # Both accounts' resources are in the result ...
    assert sorted(r["id"] for r in resources) == [
        "bucket-111111111111",
        "bucket-222222222222",
    ]
    # ... but the partly scanned account is failed, with a clear reason.
    slow = contexts["222222222222"]
    assert slow.partial is True
    assert "did not finish" in slow.processing_errors[0]
    assert [a["account_id"] for a in generator._failed_accounts()] == ["222222222222"]
    assert generator._processing_stats["failed_accounts"] == 1
    assert generator._processing_stats["successful_accounts"] == 1
    # The coverage ledger reached the account context.
    assert slow.coverage[0]["outcome"] == "timeout"
    assert slow.coverage[0]["account_id"] == "222222222222"
    notes = " ".join(generator._run_notes())
    assert "only partly scanned" in notes


# ------------------------------------------------------------------- regions
def test_region_auto_discovery_uses_discover_regions(aws, tmp_path):
    generator = _generator(tmp_path)
    ctx = _contexts(["111111111111"])["111111111111"]
    ctx.accessible_regions = []
    with (
        patch(
            "inventag.core.cloud_bom_generator.discover_regions",
            return_value=(["eu-west-3"], "account"),
        ) as found,
        patch(
            "inventag.core.cloud_bom_generator.AWSResourceInventory", LedgerInventory
        ) as inv,
    ):
        captured = {}
        real_init = LedgerInventory.__init__

        def spy(self, session, regions, **kwargs):
            captured["regions"] = regions
            real_init(self, session, regions, **kwargs)

        with patch.object(inv, "__init__", spy):
            generator._discover_account_resources_inner("111111111111", ctx)
    assert found.called
    assert captured["regions"] == ["eu-west-3"]


def test_context_setup_uses_discover_regions_when_describe_regions_is_denied(
    aws, tmp_path
):
    generator = _generator(tmp_path)
    session = boto3.Session()
    with (
        patch(
            "inventag.core.cloud_bom_generator.discover_regions",
            return_value=(["us-east-1", "eu-west-1"], "botocore"),
        ) as found,
        patch.object(generator, "_create_account_session", return_value=session),
        patch.object(
            generator,
            "_get_caller_identity",
            return_value={"Account": "123456789012", "Arn": "arn:aws:iam::1:user/u"},
        ),
    ):
        generator.config.accounts = [AccountCredentials(account_id="123456789012")]
        contexts = generator._establish_account_contexts()
    assert found.called
    assert contexts["123456789012"].accessible_regions == ["us-east-1", "eu-west-1"]


def test_access_check_keeps_all_regions_when_describe_regions_is_denied_everywhere(
    tmp_path, aws
):
    generator = _generator(tmp_path)

    class DeniedEC2:
        def describe_regions(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "UnauthorizedOperation", "Message": "no"}},
                "DescribeRegions",
            )

    class Session:
        def client(self, *a, **k):
            return DeniedEC2()

    assert generator._test_accessible_regions(
        Session(), ["us-east-1", "eu-west-1"]
    ) == ["us-east-1", "eu-west-1"]


def test_access_check_still_skips_a_region_that_alone_is_denied(tmp_path, aws):
    generator = _generator(tmp_path)

    class EC2:
        def __init__(self, region):
            self.region = region

        def describe_regions(self, **kwargs):
            if self.region == "eu-west-1":
                raise ClientError(
                    {"Error": {"Code": "UnauthorizedOperation", "Message": "scp"}},
                    "DescribeRegions",
                )
            return {"Regions": []}

    class Session:
        def client(self, service, region_name):
            return EC2(region_name)

    assert generator._test_accessible_regions(
        Session(), ["us-east-1", "eu-west-1"]
    ) == ["us-east-1"]


# ------------------------------------------------------- resume round trip
def _full_run(tmp_path, resume):
    generator = _generator(tmp_path, resume=resume, enable_billing_validation=False)

    def establish():
        contexts = _contexts(["111111111111", "222222222222"])
        generator.account_contexts = dict(contexts)
        return contexts

    generator._establish_account_contexts = establish
    generator.config.accounts = [object(), object()]
    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", LedgerInventory
    ):
        return generator.generate_multi_account_bom(output_formats=["json"])


def test_resume_round_trip_with_the_real_state_layer(aws, tmp_path):
    # Run 1: account 222 fails; 111 finishes and is saved.
    LedgerInventory.fail = {"222222222222"}
    first = _full_run(tmp_path, resume=False)
    assert first["success"] is True
    assert [a["account_id"] for a in first["failed_accounts"]] == ["222222222222"]
    partial_files = list((tmp_path / "state" / "partial").rglob("*.json"))
    assert [p.name for p in partial_files] == ["111111111111.json"]

    # The snapshot names the failed account, so it is left out of the next
    # comparison instead of showing its resources as removed.
    manager = StateManager(str(tmp_path / "state"))
    state_id = first["state_management"]["state_id"]
    meta = manager.load_state(state_id).metadata
    assert meta.accounts_failed == ["222222222222"]
    assert meta.accounts_scanned == ["111111111111"]

    # Run 2 with --resume: only the failed account is scanned again.
    LedgerInventory.fail = set()
    LedgerInventory.scanned = []
    second = _full_run(tmp_path, resume=True)
    assert second["success"] is True, second.get("error")
    assert LedgerInventory.scanned == ["222222222222"]
    assert list(second["reused_accounts"]) == ["111111111111"]
    assert second["failed_accounts"] == []
    assert second["processing_statistics"]["successful_accounts"] == 2
    assert second["processing_statistics"]["total_resources"] == 2
    # Every account finished: the saved results are removed.
    assert not list((tmp_path / "state" / "partial").rglob("*.json"))

    # The JSON output carries the coverage ledger and each row's source.
    out = json.loads(Path(second["bom_generation"]["generated_files"][0]).read_text())
    assert out["metadata"]["coverage"], "coverage ledger missing from the report"
    assert out["metadata"]["coverage_summary"]["222222222222"] == {"ok": 1}
    assert {r.get("source") for r in out["resources"]} == {"service-api"}


def test_state_retention_settings_reach_the_state_manager(aws, tmp_path):
    LedgerInventory.fail = set()
    generator = _generator(
        tmp_path,
        enable_billing_validation=False,
        state_retention_days=None,
        state_max_snapshots=3,
    )
    with patch("inventag.core.cloud_bom_generator.StateManager") as manager:
        manager.return_value.save_state.return_value = "x"
        manager.return_value.find_previous_state.return_value = (None, [])
        generator._generate_state_artifacts([])
    kwargs = manager.call_args.kwargs
    assert kwargs["retention_days"] is None and kwargs["max_snapshots"] == 3
