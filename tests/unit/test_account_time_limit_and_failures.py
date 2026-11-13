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

    def __init__(self, session, regions, **kwargs):
        self.session = session

    def discover_all_resources(self):
        ec2 = self.session.client("ec2", region_name="us-east-1")
        ec2.describe_regions()
        resource = {"id": "r", "service": "EC2", "type": "Instance"}
        if getattr(self.session, "_slow", False):
            SlowOrFastInventory.clock.now += 10_000
            # Real discovery code catches errors per service and carries on.
            for _ in range(5):
                try:
                    ec2.describe_vpcs()
                    SlowOrFastInventory.calls_after_limit += 1
                except Exception:
                    pass
        return [resource]


@pytest.mark.parametrize("parallel", [True, False])
def test_timed_out_account_fails_and_the_others_are_kept(aws, tmp_path, parallel):
    clock = FakeClock()
    SlowOrFastInventory.clock = clock
    SlowOrFastInventory.calls_after_limit = 0
    config = MultiAccountConfig(
        accounts=[],
        output_directory=str(tmp_path),
        account_processing_timeout=60,
        parallel_account_processing=parallel,
    )
    generator = CloudBOMGenerator(config)
    generator._clock = clock
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
