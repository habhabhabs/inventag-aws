"""Whole runs under moto for items the final reviews did not run (T-08).

* ``org-multi-account``: the built-in config template, with its three
  placeholder accounts, assumes a role in each account and writes one
  consolidated report (the behaviour review read the template only).
* A-19: a run whose previous snapshot is damaged names the file, still exits 0
  and writes the report (the security and behaviour reviews read the diff only).

Moto cannot answer a ``PermanentRedirect`` for a bucket in another region (it
accepts any region), so the region hint is tested with a stubbed client in
``test_s3_upload_reports_outcome.py``; the Google Sheet URL needs the Google
APIs, which moto does not serve (``test_google_doc_failure_names_sheet.py``).
"""

import glob
import json
import logging
import time

import openpyxl

from tests.unit.test_cli_exit_codes_and_flags import aws, run_cli  # noqa: F401

TEMPLATE_ACCOUNTS = {"111111111111", "222222222222", "333333333333"}
RUN = [
    "--account-regions",
    "us-east-1",
    "--account-services",
    "VPC",
    "--no-billing-validation",
    "--create-excel",
]


def test_org_multi_account_template_scans_each_listed_account(
    aws, tmp_path  # noqa: F811
):
    out = tmp_path / "out"
    code = run_cli(
        "--template",
        "org-multi-account",
        "--no-billing-validation",
        "--account-services",
        "VPC",
        "--output-directory",
        str(out),
    )
    assert code == 0
    (xlsx,) = glob.glob(str(out / "*.xlsx"))
    assert glob.glob(str(out / "*.docx"))
    assert glob.glob(str(out / "tag_compliance_*.json"))
    workbook = openpyxl.load_workbook(xlsx)
    summary = [row[0] for row in workbook["Summary"].iter_rows(values_only=True)]
    assert "Accounts: 3   Regions: 1" in summary
    rows = list(workbook["VPC"].iter_rows(values_only=True))
    assert rows[0][0] == "Account"
    assert {row[0] for row in rows[1:]} == TEMPLATE_ACCOUNTS
    for account in TEMPLATE_ACCOUNTS:
        assert any(f":{account}:" in str(row[6]) for row in rows[1:]), account


def test_a_damaged_previous_snapshot_is_named_and_the_run_still_reports(
    aws, tmp_path, caplog  # noqa: F811
):
    out = str(tmp_path / "out")
    assert run_cli(*RUN, "--output-directory", out) == 0
    (snapshot,) = glob.glob(out + "/state/state_*.json")
    data = json.loads(open(snapshot).read())
    data["resources"] = ["a", "b"]
    with open(snapshot, "w") as handle:
        json.dump(data, handle)
    time.sleep(1.1)  # snapshot ids carry the second
    caplog.clear()
    caplog.set_level(logging.WARNING)
    assert run_cli(*RUN, "--output-directory", out) == 0
    messages = [r.getMessage() for r in caplog.records]
    named = [m for m in messages if "Skipped unreadable snapshot" in m]
    assert len(named) == 1
    assert snapshot in named[0]
    assert "entry 1 of 'resources' is a str, not an object" in named[0]
    assert not [m for m in messages if "has no attribute 'get'" in m]
    assert len(glob.glob(out + "/*.xlsx")) == 2
