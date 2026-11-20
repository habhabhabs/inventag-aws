"""A2 (plan 2.4, A5 pin in tests/regression/test_serial_order_pin.py): the
snapshot's ``metadata.regions`` is sorted, so its order does not follow the
hash seed (v1.3.x wrote ``list(set(...))``)."""

from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from inventag.state.state_manager import StateManager

REGIONS = [
    "us-west-2",
    "eu-west-1",
    "ap-south-1",
    "us-east-1",
    "sa-east-1",
    "eu-central-1",
    "ap-northeast-1",
    "ca-central-1",
    "eu-north-1",
    "us-east-2",
]


def test_snapshot_regions_are_sorted(tmp_path, monkeypatch):
    generator = CloudBOMGenerator(
        MultiAccountConfig(output_directory=str(tmp_path / "out"))
    )
    for account, regions in (
        ("111111111111", REGIONS[:6]),
        ("222222222222", REGIONS[4:]),
    ):
        generator.account_contexts[account] = AccountContext(
            credentials=AccountCredentials(account_id=account),
            session=None,
            caller_identity={"Account": account},
            accessible_regions=list(regions),
        )
    seen = []

    def save_state(self, **kwargs):
        seen.append(kwargs["regions"])
        return "state-id"

    monkeypatch.setattr(StateManager, "save_state", save_state)
    generator._generate_state_artifacts(
        [{"service": "S3", "id": "b", "region": "us-east-1"}]
    )
    assert seen == [sorted(REGIONS)]
