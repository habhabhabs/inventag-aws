"""v1.5.0 behaviour review (reports/v150-behaviour-review.md), F1, F2 and F4 to F6.

F1: ``policy check --locked`` uses the default folder ``.inventag/policies``.
F2: on a scan, the last line and ``summary.exit_code`` give the code the scan
    exits with (5, 6, 3 and 4 come before the policy check's 7).
F4: on a scan the console gets a summary: the counts, the fails by severity
    and the first ``SCAN_FINDINGS_SHOWN`` findings; ``-v`` prints them all.
F5: ``policy explain`` shows an out-of-scope row as out of scope, without the
    check nodes.
F6: the editor schema accepts ``kind: policy-test``.
"""

import importlib
import json
import shutil
import textwrap
from types import SimpleNamespace

import pytest

from inventag.policy import outputs

from .cli_helpers import GOLDEN, NOW, policies_dir, run, snapshot_file

cli_main = importlib.import_module("inventag.cli.main")


# ------------------------------------------------------------------- F1
def test_check_locked_uses_the_default_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / ".inventag" / "policies"
    folder.mkdir(parents=True)
    shutil.copy(GOLDEN / "policies" / "ex01.yaml", folder / "ex01.yaml")
    assert run(["lock"])[0] == 0
    snap = snapshot_file(tmp_path)
    args = ["check", "--snapshot", snap, "--now", NOW, "--locked", "--format", "json"]
    code, out, err = run(args + ["--output-directory", tmp_path / "out"])
    assert code == 0, err
    (folder / "ex01.yaml").write_text(
        (folder / "ex01.yaml").read_text().replace("high", "low")
    )
    code, out, err = run(args + ["--output-directory", tmp_path / "out2"])
    assert code == 1
    assert "ex01.yaml: changed since policy.lock was written" in err


def test_check_locked_without_a_folder_still_exits_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    snap = snapshot_file(tmp_path)
    code, out, err = run(["check", "--snapshot", snap, "--now", NOW, "--locked"])
    assert code == 2
    assert "--locked" in err


# ------------------------------------------------------------------- F2
def _result(fails=1):
    folder_result = {
        "summary": {
            "rows": 3,
            "by_result": {
                "pass": 1,
                "fail": fails,
                "waived": 0,
                "not_evaluated": 0,
                "out_of_scope": 0,
            },
            "fail_by_severity": {"high": fails} if fails else {},
            "exit_code": 7 if fails else 0,
        },
        "snapshot": {"file": "state_x.json"},
        "now": "2026-11-20T00:00:00Z",
        "policies": [],
        "findings": [],
        "not_evaluated_units": [],
        "not_evaluated_policies": [],
        "unused_waivers": [],
    }
    return folder_result


SENTENCES = {
    0: "Exit code 0: nothing failed at severity low or higher.",
    3: "Exit code 3: the template's tag policy found violations "
    "(fail_on_tag_violations); this code comes before the policy check's code.",
    4: "Exit code 4: a security group rule is at or above --risk-threshold; "
    "this code comes before the policy check's code.",
    5: "Exit code 5: an account could not be scanned (--fail-on-account-error); "
    "this code comes before the policy check's code.",
    6: "Exit code 6: no resources were found (--fail-if-empty); this code comes "
    "before the policy check's code.",
    7: "Exit code 7: at least one finding failed at severity low or higher.",
}


@pytest.mark.parametrize("final", [0, 3, 4, 5, 6, 7])
def test_the_scan_sentence_and_file_give_the_real_code(tmp_path, capsys, final):
    pending = cli_main._PendingPolicies(
        result=_result(fails=1 if final else 0),
        gates={"fail_on": "low", "thresholds": ["fail_on"]},
    )
    args = SimpleNamespace(
        output_directory=str(tmp_path),
        policy_format=None,
        verbose=0,
        debug=False,
    )
    cli_main._finish_scan_policies(
        args, pending, final, logger=SimpleNamespace(info=lambda *a: None)
    )
    printed = capsys.readouterr().out.rstrip("\n").splitlines()
    assert printed[-1] == SENTENCES[final]
    (written,) = tmp_path.glob("policy_findings_*.json")
    assert json.loads(written.read_text())["summary"]["exit_code"] == final


POLICY = """
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


def _policy_file(tmp_path, text=POLICY):
    folder = tmp_path / "policies"
    folder.mkdir(exist_ok=True)
    path = folder / "p.yaml"
    path.write_text(textwrap.dedent(text).lstrip())
    return path


@pytest.mark.e2e
def test_an_empty_scan_with_a_policy_says_6_and_exits_6(tmp_path):
    from tests.unit.finops.conftest import run_scan

    scan = run_scan(
        tmp_path,
        "--policy",
        str(_policy_file(tmp_path)),
        "--policy-fail-on",
        "low",
        "--account-services",
        "sqs",
        "--fail-if-empty",
    )
    assert scan.code == 6, scan.text
    (path,) = sorted(scan.out.glob("policy_findings_*.json"))
    assert json.loads(path.read_text())["summary"]["exit_code"] == 6
    assert SENTENCES[6] in scan.text
    assert "Exit code 0" not in scan.text


# ------------------------------------------------------------------- F4
def _many(n):
    result = _result(fails=n)
    result["policies"] = [
        {
            "id": "EC2-101",
            "severity": "high",
            "file": "p.yaml",
            "counts": {"fail": n, "pass": 0},
        }
    ]
    result["findings"] = [
        {
            "policy": "EC2-101",
            "result": "fail",
            "severity": "high",
            "resource": f"arn:aws:ec2:us-east-1:111111111111:instance/i-{i:04d}",
            "message": "EC2-101: condition not met",
        }
        for i in range(n)
    ]
    return result


def test_the_scan_summary_shows_the_first_findings_only():
    shown = cli_main.SCAN_FINDINGS_SHOWN
    text = outputs.render(
        _many(shown + 5),
        "text",
        fail_on="low",
        thresholds=["fail_on"],
        limit=shown,
        more_in="policy_findings_x.json",
    )
    assert text.count("  FAIL arn:aws:ec2") == shown
    assert "Failed by severity: high 15" in text
    assert (
        "5 more findings are in policy_findings_x.json; add -v to print them." in text
    )


def test_without_a_limit_the_text_report_is_unchanged():
    full = outputs.render(_many(15), "text", fail_on="low", thresholds=["fail_on"])
    assert full.count("  FAIL arn:aws:ec2") == 15
    assert "Failed by severity" not in full
    assert "more findings" not in full


@pytest.mark.parametrize("verbose, limited", [(0, True), (1, False)])
def test_v_prints_every_finding_on_a_scan(tmp_path, capsys, verbose, limited):
    pending = cli_main._PendingPolicies(
        result=_many(cli_main.SCAN_FINDINGS_SHOWN + 3),
        gates={"fail_on": "low", "thresholds": ["fail_on"]},
    )
    args = SimpleNamespace(
        output_directory=str(tmp_path),
        policy_format=None,
        verbose=verbose,
        debug=False,
    )
    cli_main._finish_scan_policies(
        args, pending, 7, logger=SimpleNamespace(info=lambda *a: None)
    )
    out = capsys.readouterr().out
    count = out.count("  FAIL arn:aws:ec2")
    if limited:
        assert count == cli_main.SCAN_FINDINGS_SHOWN
    else:
        assert count == cli_main.SCAN_FINDINGS_SHOWN + 3


# ------------------------------------------------------------------- F5
def test_explain_shows_an_out_of_scope_row_as_out_of_scope(tmp_path):
    folder = policies_dir(tmp_path, "ex02.yaml")
    code, out, err = run(
        [
            "explain",
            "EC2-001",
            "--snapshot",
            snapshot_file(tmp_path),
            "--policies",
            folder,
            "--now",
            NOW,
            "--resource",
            "arn:aws:ec2:us-east-1:111111111111:instance/i-0bbb",
        ]
    )
    assert code == 0, err
    lines = out.splitlines()
    assert "        resource and: out of scope" in lines
    assert "          resource value raw_data.State.Name: false" in lines
    assert not [x for x in lines if x.strip().startswith("check ")]


# ------------------------------------------------------------------- F6
def test_the_editor_schema_accepts_a_policy_test():
    jsonschema = pytest.importorskip("jsonschema")
    code, out, err = run(["schema", "--json"])
    assert code == 0, err
    schema = json.loads(out)
    fixture = {
        "format_version": 1,
        "kind": "policy-test",
        "name": "basic",
        "spec": {
            "policy": "ec2-001",
            "now": "2026-11-20",
            "resources": [{"service": "EC2"}],
            "expect": [{"resource": "x", "result": "pass"}],
        },
    }
    jsonschema.validate(fixture, schema)
    bad = dict(fixture, spec=dict(fixture["spec"], actions=["stop"]))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
