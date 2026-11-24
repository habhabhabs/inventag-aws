"""P6: ``inventag policy`` from the main command, and ``--policy`` on a scan
(spec 4, 11.7; plan section 3, P6 row). Every CLI test asserts the exit code."""

import datetime as dt
import json
import textwrap

import pytest

from inventag import exit_codes
import importlib

cli_main = importlib.import_module("inventag.cli.main")
from tests.unit.finops.conftest import run_scan

pytestmark = pytest.mark.e2e

STOPPED = """
format_version: 1
kind: policy
name: no-stopped-instance
spec:
  id: EC2-101
  severity: high
  resource: {services: [EC2], resource_types: [Instance]}
  check:
    - {type: value, key: raw_data.State.Name, op: ne, value: stopped}
"""
OWNER = """
format_version: 1
kind: policy
name: owner-tag
spec:
  id: TAG-101
  severity: low
  resource: {services: [EC2], resource_types: [Volume]}
  check:
    - {type: required-tags, keys: [{key: Owner}]}
"""


def policy_file(tmp_path, text=STOPPED, name="p.yaml"):
    folder = tmp_path / "policies"
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_text(textwrap.dedent(text).lstrip())
    return path


def findings_files(scan, suffix="json"):
    return sorted(scan.out.glob(f"policy_findings_*.{suffix}"))


# ----------------------------------------------------------------- codes
def test_the_exit_codes_keep_their_order_and_add_7_and_8():
    assert [
        exit_codes.EXIT_OK,
        exit_codes.EXIT_ERROR,
        exit_codes.EXIT_USAGE,
        exit_codes.EXIT_TAG_VIOLATIONS,
        exit_codes.EXIT_RISK_THRESHOLD,
        exit_codes.EXIT_ACCOUNT_FAILED,
        exit_codes.EXIT_NO_RESOURCES,
        exit_codes.EXIT_POLICY_FAIL,
        exit_codes.EXIT_POLICY_NOT_EVALUATED,
    ] == list(range(9))


@pytest.mark.parametrize(
    "opt_in, tag, risk, policy, expected",
    [
        (0, 0, 0, 0, 0),
        (0, 0, 0, 7, 7),
        (0, 0, 0, 8, 8),
        (0, 0, 4, 7, 4),
        (0, 3, 0, 8, 3),
        (5, 3, 4, 7, 5),
        (6, 0, 0, 8, 6),
    ],
)
def test_on_a_scan_5_6_3_4_come_first_then_the_policy_code(
    opt_in, tag, risk, policy, expected
):
    assert cli_main.scan_exit_code(opt_in, tag, risk, policy) == expected


# ----------------------------------------------------------------- dispatch
def test_the_policy_word_runs_the_policy_command(tmp_path, monkeypatch, capsys):
    path = policy_file(tmp_path)
    monkeypatch.setattr("sys.argv", ["inventag", "policy", "validate", str(path)])
    with pytest.raises(SystemExit) as stop:
        cli_main.main()
    assert stop.value.code == 0
    assert "EC2-101" in capsys.readouterr().out


def test_the_help_names_the_policy_command_and_the_scan_flags():
    text = " ".join(cli_main.create_parser().format_help().split())
    for word in (
        "inventag policy check",
        "--policy PATH",
        "--policy-waivers",
        "--policy-fail-on",
        "--policy-format",
    ):
        assert word in text, word


# ----------------------------------------------------------------- scan
def test_a_scan_with_a_policy_writes_the_json_file_and_the_summary(tmp_path):
    scan = run_scan(tmp_path, "--policy", str(policy_file(tmp_path)))
    assert scan.code == 0, scan.text
    (path,) = findings_files(scan)
    result = json.loads(path.read_text())
    (fail,) = [f for f in result["findings"] if f["result"] == "fail"]
    assert fail["resource"].endswith(scan.ids["stopped"])
    assert result["snapshot"]["file"].startswith("state_")
    assert "Exit code 0: findings are reported; no threshold was set." in scan.text
    assert findings_files(scan, "sarif") == []


def test_policy_fail_on_gives_exit_7(tmp_path):
    scan = run_scan(
        tmp_path, "--policy", str(policy_file(tmp_path)), "--policy-fail-on", "high"
    )
    assert scan.code == 7, scan.text
    assert len(findings_files(scan)) == 1


def test_a_lower_severity_than_the_threshold_exits_0(tmp_path):
    scan = run_scan(
        tmp_path,
        "--policy",
        str(policy_file(tmp_path, OWNER)),
        "--policy-fail-on",
        "medium",
    )
    assert scan.code == 0, scan.text


def test_several_policies_and_formats(tmp_path):
    scan = run_scan(
        tmp_path,
        "--policy",
        str(policy_file(tmp_path)),
        "--policy",
        str(policy_file(tmp_path, OWNER, "owner.yaml")),
        "--policy-format",
        "json,sarif",
    )
    assert scan.code == 0, scan.text
    assert len(findings_files(scan)) == 1
    (sarif,) = findings_files(scan, "sarif")
    rules = json.loads(sarif.read_text())["runs"][0]["tool"]["driver"]["rules"]
    assert sorted(r["id"] for r in rules) == ["EC2-101", "TAG-101"]


def test_a_policy_folder(tmp_path):
    policy_file(tmp_path)
    policy_file(tmp_path, OWNER, "owner.yaml")
    scan = run_scan(tmp_path, "--policy", str(tmp_path / "policies"))
    assert scan.code == 0, scan.text
    result = json.loads(findings_files(scan)[0].read_text())
    assert [p["id"] for p in result["policies"]] == ["EC2-101", "TAG-101"]


def test_waivers_on_a_scan(tmp_path):
    # moto gives new IDs to every estate, so the waiver names the instances
    # of the account by a glob (with the account, as spec 2.5 requires)
    waivers = tmp_path / "w.yaml"
    waivers.write_text(
        "format_version: 1\nkind: waivers\nname: w\nspec:\n  waivers:\n"
        "    - policy: EC2-101\n"
        '      resource: "arn:aws:ec2:us-east-1:123456789012:instance/i-*"\n'
        '      account: "123456789012"\n'
        '      reason: "Kept stopped for the quarterly audit."\n'
        "      approved_by: platform-lead\n"
        f"      expires: {dt.date.today() + dt.timedelta(days=30)}\n"
    )
    scan = run_scan(
        tmp_path,
        "--policy",
        str(policy_file(tmp_path)),
        "--policy-waivers",
        str(waivers),
        "--policy-fail-on",
        "high",
    )
    assert scan.code == 0, scan.text
    result = json.loads(findings_files(scan)[0].read_text())
    assert [f["result"] for f in result["findings"]] == ["waived"]


def test_an_invalid_policy_stops_before_any_aws_call(tmp_path):
    bad = policy_file(tmp_path, STOPPED.replace("EC2-101", "ec2-1"))
    scan = run_scan(tmp_path, "--policy", str(bad))
    assert scan.code == 1, scan.text
    assert "id must look like ABC-001" in scan.text
    assert scan.audit is None or scan.audit["total_calls"] == 0


@pytest.mark.parametrize(
    "extra, message",
    [
        (["--disable-state-management"], "--policy needs the state snapshot"),
        (["--policy-format", "pdf"], "--policy-format"),
    ],
)
def test_conflicting_options_exit_2(tmp_path, extra, message):
    scan = run_scan(tmp_path, "--policy", str(policy_file(tmp_path)), *extra)
    assert scan.code == 2, scan.text
    assert message in scan.text


@pytest.mark.parametrize(
    "flag", ["--policy-waivers", "--policy-fail-on", "--policy-format"]
)
def test_policy_options_without_policy_exit_2(tmp_path, flag):
    value = {
        "--policy-waivers": "w.yaml",
        "--policy-fail-on": "high",
        "--policy-format": "json",
    }
    scan = run_scan(tmp_path, flag, value[flag])
    assert scan.code == 2, scan.text
    assert f"{flag} needs --policy" in scan.text


def test_a_scan_with_a_policy_and_a_template(tmp_path):
    scan = run_scan(
        tmp_path,
        "--policy",
        str(policy_file(tmp_path)),
        "--template",
        "standard-bom",
        "--policy-fail-on",
        "high",
    )
    assert scan.code == 7, scan.text
    assert len(findings_files(scan)) == 1


def test_a_scan_without_policy_writes_no_findings_file(tmp_path):
    scan = run_scan(tmp_path)
    assert scan.code == 0, scan.text
    assert findings_files(scan) == []
    assert "Exit code" not in scan.text
