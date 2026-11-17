"""A region name typed wrong is named with a next step (A-16, message part;
review M2: a region the installed botocore does not know is still tried, and
the message names both causes).

v1.2.1 under moto: "Region us-east-9 test failed: 'us-east-9'" (a raw
KeyError text) and exit 0. The exit code stays 0 in the patch (exit 2 for an
unknown region is owner decision O8). The region is still tried, as before:
a region newer than the installed botocore must keep working.
"""

import logging

from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    aws,
    empty_aws,
    logged,
    reports,
    run_cli,
    workbook,
)

WANTED = (
    "Region 'us-east-9' could not be checked and the installed boto3 does not "
    "know it: check its spelling in --account-regions or in the accounts file, "
    "or, if it is a new AWS region, upgrade boto3. To list the regions of your "
    "account, run: aws ec2 describe-regions --query 'Regions[].RegionName' "
    "--output text"
)


def run(regions):
    return run_cli(
        "--create-excel",
        "--no-billing-validation",
        "--account-regions",
        regions,
        "--output-directory",
        "out",
    )


def test_a_mistyped_region_is_named_with_a_next_step(
    aws, tmp_path, caplog, capsys  # noqa: F811
):
    caplog.set_level(logging.INFO)
    assert run("us-east-1,us-east-9") == 0  # exit code as in v1.2.1 (O8: owner)
    messages = logged(caplog)
    assert messages.count(WANTED) == 1, messages
    assert not any("test failed: 'us-east-9'" in m for m in messages), messages
    files = reports(tmp_path / "out")
    assert len(files) == 1 and "VPC" in workbook(files[0])  # us-east-1 scanned
    summary = [str(r[0]) for r in workbook(files[0])["Summary"] if r and r[0]]
    assert (
        "Regions not scanned in account 123456789012 because their region check "
        "failed and the installed boto3 does not know them (a misspelled name, "
        "or a region newer than boto3): us-east-9."
    ) in summary, summary


def test_known_regions_give_no_new_message(aws, tmp_path, caplog):  # noqa: F811
    caplog.set_level(logging.INFO)
    assert run("us-east-1,eu-west-1") == 0
    assert not any("does not know it" in m for m in logged(caplog))


def test_a_real_region_the_installed_botocore_does_not_know_is_still_scanned(
    aws, tmp_path, caplog, monkeypatch  # noqa: F811
):
    """Review M2: eu-west-1 hidden from botocore's region list stands for a
    real region newer than the installed boto3. Its region check passes, so
    it is scanned as in v1.2.1, with no warning and no note."""
    import botocore.client

    from inventag.core import cloud_bom_generator as cbg

    real = cbg._known_regions
    monkeypatch.setattr(
        cbg, "_known_regions", lambda session: real(session) - {"eu-west-1"}
    )
    calls = []
    original = botocore.client.BaseClient._make_api_call

    def spy(client, operation_name, api_params):
        calls.append((client.meta.region_name, operation_name))
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", spy)
    caplog.set_level(logging.INFO)
    assert run("us-east-1,eu-west-1") == 0
    messages = logged(caplog)
    assert not any("does not know it" in m for m in messages), messages
    assert ("eu-west-1", "DescribeRegions") in calls
    assert ("eu-west-1", "ListQueues") in calls  # a listing ran there
    summary = [
        str(r[0])
        for r in workbook(reports(tmp_path / "out")[0])["Summary"]
        if r and r[0]
    ]
    assert not any("eu-west-1" in line for line in summary), summary
