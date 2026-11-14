"""Docs claims for docs/guides/*.md that were only read in code before (v1.2.0 docs).

Each test runs the real CLI under moto, like tests/unit/test_docs_claims_v120.py.
"""

import json
import logging

import pytest

from tests.unit.test_docs_claims_v120 import (  # noqa: F401  (fixtures + helpers)
    BASE,
    GOOD,
    GOOD_ID,
    OTHER,
    OTHER_ID,
    RoleControl,
    accounts_file,
    aws,
    empty_aws,
    logged,
    reports,
    run_cli,
    seed_account,
)


# ------------------------------------------------ option ranges (run-a-scan, troubleshooting)
@pytest.mark.parametrize(
    "flag,value,text",
    [
        ("--max-concurrent-accounts", "0", "must be a positive integer"),
        ("--account-processing-timeout", "59", "must be at least 60 seconds"),
        ("--resume-max-age-hours", "169", "must be above 0 and at most 168"),
        ("--resume-max-age-hours", "0", "must be above 0 and at most 168"),
    ],
)
def test_range_errors_name_the_option_and_exit_code(
    flag, value, text, empty_aws, capsys, caplog
):
    code = run_cli(flag, value, "--resume", "--validate-config-only", *BASE)
    out = capsys.readouterr().err + "\n".join(logged(caplog))
    assert text in out
    assert code == 1  # docs: "stops with exit code 1"


@pytest.mark.parametrize("flag", ["--state-retention-days", "--state-max-snapshots"])
def test_state_limits_not_a_number_exit_2(flag, empty_aws, capsys):
    assert run_cli(flag, "abc", *BASE) == 2
    assert "expected a whole number or 'none'" in capsys.readouterr().err


def test_resume_with_disabled_state_management_exit_2(empty_aws, capsys):
    assert run_cli("--resume", "--disable-state-management", *BASE) == 2
    assert "--resume: needs state management" in capsys.readouterr().err


def test_accounts_file_with_prompt_and_role_arn_with_file_exit_2(
    empty_aws, tmp_path, capsys
):
    path = accounts_file(tmp_path, [GOOD])
    assert run_cli("--accounts-file", path, "--accounts-prompt", *BASE) == 2
    assert "give one of them, not both" in capsys.readouterr().err
    arn = f"arn:aws:iam::{GOOD_ID}:role/R"
    assert run_cli("--accounts-file", path, "--cross-account-role", arn, *BASE) == 2
    assert "a full role ARN names one account" in capsys.readouterr().err


# ------------------------------------------------ track changes (CLI level)
def _run(tmp_path, *extra):
    return run_cli(
        *BASE, "--account-regions", "us-east-1", "--output-directory", "out", *extra
    )


def _state(tmp_path):
    return sorted((tmp_path / "out" / "state").glob("state_*.json"))


def test_first_run_no_changelog_second_run_writes_one(aws, tmp_path):
    import time

    assert _run(tmp_path) == 0
    out = tmp_path / "out"
    assert len(_state(tmp_path)) == 1
    assert not list(out.glob("changelog_*.md"))
    assert (out / "state" / "metadata.json").exists()
    time.sleep(1.1)
    assert _run(tmp_path) == 0
    assert len(_state(tmp_path)) == 2
    assert len(list(out.glob("changelog_*.md"))) == 1
    snap = json.loads(_state(tmp_path)[-1].read_text())
    assert {"resources", "metadata"} <= set(snap)
    meta = snap["metadata"]
    assert meta["version"] == "1.1" or meta.get("snapshot_version") == "1.1"
    assert "accounts_scanned" in meta and "accounts_failed" in meta


@pytest.mark.parametrize(
    "flags,changelog,snapshots",
    [
        (["--no-generate-changelog"], False, True),
        (["--disable-delta-detection"], False, True),
        (["--disable-state-management"], False, False),
    ],
)
def test_flags_that_stop_the_change_report(aws, tmp_path, flags, changelog, snapshots):
    import time

    assert _run(tmp_path) == 0
    time.sleep(1.1)
    assert _run(tmp_path, *flags) == 0
    out = tmp_path / "out"
    assert bool(list(out.glob("changelog_*.md"))) is changelog
    if snapshots:
        assert len(_state(tmp_path)) == 2
    else:
        assert len(_state(tmp_path)) == 1  # nothing new was saved


def test_state_max_snapshots_one_leaves_two_files(aws, tmp_path):
    import time

    for _ in range(3):
        assert _run(tmp_path, "--state-max-snapshots", "1") == 0
        time.sleep(1.1)
    assert len(_state(tmp_path)) == 2


# ------------------------------------------------ a role that cannot be assumed
def test_role_name_failure_does_not_scan_the_account_with_default_credentials(
    aws, tmp_path, monkeypatch, caplog
):
    seed_account(OTHER_ID, OTHER["role_arn"])
    caplog.set_level(logging.INFO)
    RoleControl(monkeypatch, failing={OTHER_ID})
    path = accounts_file(
        tmp_path, [GOOD, {"account_id": OTHER_ID, "regions": ["us-east-1"]}]
    )
    code = run_cli(
        "--accounts-file",
        path,
        "--cross-account-role",
        "InvenTagReadOnly",
        *BASE,
        "--output-directory",
        "out",
    )
    assert code == 0
    files = reports(tmp_path / "out")
    assert len(files) == 1
    from tests.unit.test_docs_claims_v120 import workbook_text

    text = workbook_text(files[0])
    assert f"acct-{OTHER_ID}" not in text  # no resources of the other account
    assert OTHER_ID in text  # but the Run notes name it
    assert any("were not scanned" in m for m in logged(caplog))


# ------------------------------------------------ security analysis risk rules (network-and-security-analysis.md)
def test_wide_private_source_is_medium_and_outbound_is_always_low():
    import boto3
    from moto import mock_aws

    from inventag.discovery.security_analyzer import SecurityAnalyzer

    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
        g = ec2.create_security_group(GroupName="wide", Description="d", VpcId=vpc)[
            "GroupId"
        ]
        ec2.authorize_security_group_ingress(
            GroupId=g,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "10.0.0.0/8"}],
                }
            ],
        )
        ec2.authorize_security_group_egress(
            GroupId=g,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                }
            ],
        )
        analyzer = SecurityAnalyzer(boto3.Session(region_name="us-east-1"))
        analyzer.analyze_security_groups([{"id": "x", "region": "us-east-1"}])
        info = analyzer.sg_cache[g]
        assert [r.risk_assessment for r in info.inbound_rules] == ["medium"]
        assert {r.risk_assessment for r in info.outbound_rules} == {"low"}


def test_template_validate_catches_role_arn_of_another_account(
    empty_aws, tmp_path, capsys
):
    folder = tmp_path / ".inventag" / "templates"
    folder.mkdir(parents=True)
    (folder / "bad.yaml").write_text(
        "format_version: 1\nkind: config\nname: bad\nspec:\n  accounts:\n"
        '    - account_id: "123456789012"\n'
        "      role_arn: arn:aws:iam::999999999999:role/X\n  regions: [us-east-1]\n"
    )
    assert run_cli("templates", "validate", "bad") == 1
    out = capsys.readouterr()
    assert "role is in account 999999999999 but account_id is 123456789012" in (
        out.out + out.err
    )


# ------------------------------------------------ exit code 5 for a timed-out account (Ruling R1)
def test_timed_out_account_gives_exit_5(empty_aws, tmp_path):
    import argparse
    import threading
    from unittest.mock import patch

    from inventag.cli.main import _opt_in_exit_code
    from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
    from tests.unit.test_account_time_limit_and_failures import (
        FakeClock,
        SlowOrFastInventory,
        _contexts,
    )

    clock = FakeClock()
    SlowOrFastInventory.clock = clock
    SlowOrFastInventory.fast_done = threading.Event()
    SlowOrFastInventory.calls_after_limit = 0
    g = CloudBOMGenerator(
        MultiAccountConfig(
            accounts=[],
            output_directory=str(tmp_path),
            account_processing_timeout=60,
            parallel_account_processing=False,
        )
    )
    g._clock = clock
    g._poll_seconds = 0.01
    c = _contexts(["111111111111", "222222222222"])
    c["222222222222"].session._slow = True
    g.account_contexts.update(c)
    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", SlowOrFastInventory
    ):
        g._sequential_account_discovery(c)
    failed = g._failed_accounts()
    assert [f["account_id"] for f in failed] == ["222222222222"]
    args = argparse.Namespace(fail_on_account_error=True, fail_if_empty=False)
    code = _opt_in_exit_code(args, {"failed_accounts": failed}, logging.getLogger("x"))
    assert code == 5
