"""A region name typed wrong is named with a next step (A-16, message part).

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
    "Region 'us-east-9' is not a known AWS region; check its spelling in "
    "--account-regions or in the accounts file. To list the regions of your "
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
        "Regions not scanned in account 123456789012 because they are not known "
        "AWS regions (check the spelling): us-east-9."
    ) in summary, summary


def test_known_regions_give_no_new_message(aws, tmp_path, caplog):  # noqa: F811
    caplog.set_level(logging.INFO)
    assert run("us-east-1,eu-west-1") == 0
    assert not any("not a known AWS region" in m for m in logged(caplog))
