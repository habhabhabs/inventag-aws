"""The identity check uses the STS endpoint of the scan's partition, and a
region of another partition is named (A-44, two parts).

v1.2.x: the account's ``sts:GetCallerIdentity`` went to the session's default
region (S2 C6: ``us-east-1``) even when every scanned region was in GovCloud,
which fails with GovCloud credentials. And a region of another partition
(``cn-north-1`` with commercial credentials) was tried without a word.
Exit codes unchanged.
"""

import logging
import traceback

import botocore.client

from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    aws,
    empty_aws,
    logged,
    run_cli,
)


def identity_endpoints(monkeypatch):
    """Endpoint URLs of the GetCallerIdentity calls made by inventag/core."""
    seen = []
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        if operation_name == "GetCallerIdentity" and any(
            "/inventag/core/" in f.filename for f in traceback.extract_stack()
        ):
            seen.append(client.meta.endpoint_url)
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)
    return seen


def test_the_identity_check_uses_the_govcloud_endpoint(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    seen = identity_endpoints(monkeypatch)
    code = run_cli(
        *BASE, "--account-regions", "us-gov-west-1", "--output-directory", "out"
    )
    assert code in (0, 1)  # moto's answer for GovCloud; the code is not the point
    assert seen and all("us-gov-west-1" in url for url in seen), seen


def test_with_a_govcloud_default_region_nothing_changes(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-gov-west-1")
    seen = identity_endpoints(monkeypatch)
    run_cli(*BASE, "--account-regions", "us-gov-west-1", "--output-directory", "out")
    assert seen and all("us-gov-west-1" in url for url in seen), seen


def test_commercial_regions_keep_the_session_region(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    """Guard: a commercial scan is unchanged (endpoint of the session region)."""
    seen = identity_endpoints(monkeypatch)
    assert (
        run_cli(*BASE, "--account-regions", "eu-west-1", "--output-directory", "o") == 0
    )
    assert seen and all("us-east-1" in url for url in seen), seen


def test_a_region_of_another_partition_is_named(aws, tmp_path, caplog):  # noqa: F811
    caplog.set_level(logging.INFO)
    code = run_cli(
        *BASE, "--account-regions", "us-east-1,cn-north-1", "--output-directory", "o"
    )
    assert code == 0  # as before
    wanted = (
        "Region 'cn-north-1' is in the aws-cn partition, but the credentials of "
        "account 123456789012 are for the aws partition, so it cannot be scanned "
        "with them; scan it with credentials of that partition."
    )
    assert logged(caplog).count(wanted) == 1, logged(caplog)
