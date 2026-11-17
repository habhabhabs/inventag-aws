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

import botocore.client

from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    aws,
    empty_aws,
    run_cli,
)


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
