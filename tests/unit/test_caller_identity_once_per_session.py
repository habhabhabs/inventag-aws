"""The caller identity of an account is resolved once (A-70).

Review I5 saw 4 to 8 ``sts:GetCallerIdentity`` calls between identical runs:
discovery looked the account up again in each region's worker thread
(``ComprehensiveAWSDiscovery._get_account_id``, check-then-set without a
lock), although the generator had resolved it already. Now the generator
hands the account it resolved to discovery, so the count is the same in
every run and discovery makes none.
"""

import collections
import traceback

import boto3
import botocore.client
import pytest
from unittest.mock import patch

from inventag.core import cloud_bom_generator as cbg

from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    aws,
    empty_aws,
    run_cli,
)


@pytest.mark.slow  # ten real runs (the acceptance of WO-A6): about 2 minutes
def test_identical_runs_make_the_same_identity_calls(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    calls = collections.Counter()
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        if operation_name == "GetCallerIdentity":
            here = [
                f.filename
                for f in traceback.extract_stack()
                if "/inventag/discovery/" in f.filename
            ]
            calls["discovery" if here else "other"] += 1
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)
    counts = []
    for i in range(10):
        calls.clear()
        args = [*BASE, "--account-regions", "us-east-1,eu-west-1,eu-west-2"]
        assert run_cli(*args, "--output-directory", f"out{i}") == 0
        counts.append(dict(calls))
    assert all(c.get("discovery", 0) == 0 for c in counts), counts
    assert len({c.get("other", 0) for c in counts}) == 1, counts


class Engine:
    def _get_account_id(self):
        return getattr(self, "_cached_account_id", None)


class Inventory:
    def __init__(self, session, regions, **kwargs):
        self.comprehensive_discovery = Engine()
        Inventory.last = self

    def discover_all_resources(self):
        return []


def test_discovery_gets_the_account_the_generator_resolved(tmp_path):
    """Fast check of the hand-over (no AWS call)."""
    generator = cbg.CloudBOMGenerator(
        cbg.MultiAccountConfig(accounts=[], output_directory=str(tmp_path))
    )
    context = cbg.AccountContext(
        credentials=cbg.AccountCredentials(account_id="111111111111"),
        session=boto3.Session(region_name="us-east-1"),
        caller_identity={"Account": "111111111111"},
        accessible_regions=["us-east-1"],
    )
    with patch.object(cbg, "AWSResourceInventory", Inventory):
        generator._discover_account_resources_inner("111111111111", context)
    assert Inventory.last.comprehensive_discovery._get_account_id() == "111111111111"
