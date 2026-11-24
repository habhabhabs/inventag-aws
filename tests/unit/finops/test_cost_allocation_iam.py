"""The one new IAM action of --finops-cost-allocation: ce:ListCostAllocationTags."""

import json
from pathlib import Path

from inventag.security.iam_policy import (
    READ_ONLY_ACTIONS,
    action_for,
    build_read_only_policy,
)

REPO = Path(__file__).resolve().parents[3]


def test_the_action_is_in_the_code_list_and_the_shipped_policy():
    assert READ_ONLY_ACTIONS["ce:ListCostAllocationTags"] == (
        "ce",
        "ListCostAllocationTags",
    )
    shipped = json.loads(
        (REPO / "config/defaults/iam-policy-read-only.json").read_text()
    )
    assert shipped == build_read_only_policy()
    (read,) = [
        s for s in shipped["Statement"] if s["Sid"] == "InvenTagReadOnlyDiscovery"
    ]
    assert "ce:ListCostAllocationTags" in read["Action"]


def test_the_call_maps_to_the_action():
    assert action_for("ce", "ListCostAllocationTags") == "ce:ListCostAllocationTags"
    assert action_for("ce", "list_cost_allocation_tags") == "ce:ListCostAllocationTags"
