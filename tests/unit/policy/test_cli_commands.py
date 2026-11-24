"""``inventag policy validate / list / schema / check / explain / lock`` (P4).

Every test asserts the exit code. Waivers, lock and the output writers belong
to P2 and P3; the tests stand in for them with stubs (see cli_helpers.stub)
and list the interface they assume in the P4 report.
"""

import json

import pytest

from .cli_helpers import GOLDEN, NOW, policies_dir, run, snapshot_file, stub

# ---------------------------------------------------------------- validate


def test_validate_ok_names_each_file(tmp_path):
    folder = policies_dir(tmp_path, "ex01.yaml", "ex05.yaml")
    code, out, err = run(["validate", folder])
    assert code == 0, err
    assert out.splitlines() == [
        "OK    ex01.yaml (policy RDS-001)",
        "OK    ex05.yaml (policy TAG-002)",
        "2 policies, 0 sets, 0 waivers: no problems.",
    ]
    assert err == ""


def test_validate_reads_waivers_files_too(tmp_path):
    folder = policies_dir(tmp_path, "ex01.yaml")
    waivers = tmp_path / "w16.yaml"
    waivers.write_text((GOLDEN / "waivers" / "w16.yaml").read_text())
    code, out, err = run(["validate", folder, waivers, "--now", NOW])
    assert code == 0, err
    assert out.splitlines()[-1] == "1 policies, 0 sets, 1 waivers: no problems."


def test_validate_reports_the_problem_with_file_line_field(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "bad.yaml").write_text(
        "format_version: 1\nkind: policy\nname: bad\n"
        "spec: {id: BAD-001, severity: high, actions: [], "
        "check: [{type: value, key: raw_data.X, value: 1}]}\n"
    )
    code, out, err = run(["validate", folder])
    assert code == 1
    assert out == ""
    assert err == (
        "error: bad.yaml:4: spec.actions: InvenTag never changes resources; "
        "a policy has no actions.\n"
        "1 problem found; nothing was evaluated.\n"
    )


def test_validate_missing_path_is_exit_1(tmp_path):
    code, out, err = run(["validate", tmp_path / "nothing.yaml"])
    assert code == 1
    assert err.splitlines()[0].endswith(
        "nothing.yaml: cannot read file: No such file or directory"
    )


def test_validate_requires_a_path():
    code, out, err = run(["validate"])
    assert code == 2


# -------------------------------------------------------------------- list


def test_list_shows_id_severity_version_and_digest(tmp_path):
    folder = policies_dir(tmp_path, "ex05.yaml", "ex01.yaml")
    code, out, err = run(["list", "--policies", folder])
    assert code == 0, err
    lines = out.splitlines()
    assert lines[0].split() == ["ID", "SEVERITY", "VERSION", "SHA256", "FILE"]
    assert [line.split()[0] for line in lines[1:]] == ["RDS-001", "TAG-002"]
    import hashlib

    digest = hashlib.sha256((folder / "ex01.yaml").read_bytes()).hexdigest()[:12]
    assert lines[1].split() == ["RDS-001", "high", "1", digest, "ex01.yaml"]


def test_list_set_shows_only_the_members(tmp_path):
    folder = policies_dir(tmp_path, "ex01.yaml", "ex05.yaml")
    (folder / "basics.yaml").write_text(
        "format_version: 1\nkind: policy-set\nname: basics\n"
        "spec: {policies: [rds-001]}\n"
    )
    code, out, err = run(["list", "--policies", folder, "--set", "basics"])
    assert code == 0, err
    assert [line.split()[0] for line in out.splitlines()[1:]] == ["RDS-001"]


def test_list_unknown_set_is_exit_1(tmp_path):
    folder = policies_dir(tmp_path, "ex01.yaml")
    code, out, err = run(["list", "--policies", folder, "--set", "nope"])
    assert code == 1
    assert err == (
        "error: no policy set named 'nope'; run 'inventag policy list' and "
        "'inventag policy list --shipped' to see the sets.\n"
    )


def test_list_without_a_policy_folder_is_exit_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, out, err = run(["list"])
    assert code == 1
    assert err == (
        "error: policy folder .inventag/policies does not exist; "
        "give --policies PATH.\n"
    )


# ------------------------------------------------------------------ schema


def test_schema_field_help(tmp_path):
    code, out, err = run(["schema", "severity"])
    assert code == 0, err
    assert out.startswith("severity")
    assert "info, low, medium, high, critical" in out


def test_schema_without_field_lists_the_fields():
    code, out, err = run(["schema"])
    assert code == 0, err
    for word in ("id", "severity", "check", "resource", "require", "type"):
        assert word in out.split()


def test_schema_unknown_field_is_exit_1():
    code, out, err = run(["schema", "colour"])
    assert code == 1
    assert err == (
        "error: no field named 'colour'; run 'inventag policy schema' to list "
        "the fields.\n"
    )


def test_schema_json_is_a_json_schema_that_accepts_the_golden_policies():
    import jsonschema

    code, out, err = run(["schema", "--json"])
    assert code == 0, err
    schema = json.loads(out)
    jsonschema.Draft202012Validator.check_schema(schema)
    import yaml

    for path in sorted((GOLDEN / "policies").glob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text()):
            jsonschema.validate(doc, schema)
    bad = {
        "format_version": 1,
        "kind": "policy",
        "name": "x",
        "spec": {"id": "X-001", "severity": "huge", "check": []},
    }
    assert not jsonschema.Draft202012Validator(schema).is_valid(bad)


def test_schema_json_is_byte_stable():
    first = run(["schema", "--json"])
    assert first[0] == 0 and first[1].endswith("}\n")
    assert run(["schema", "--json"]) == first


# ------------------------------------------------------------------- check


def check_args(tmp_path, *names, extra=()):
    folder = policies_dir(tmp_path, *names)
    snap = snapshot_file(tmp_path)
    return [
        "check",
        "--snapshot",
        snap,
        "--policies",
        folder,
        "--now",
        NOW,
        "--output-directory",
        tmp_path / "out",
        *extra,
    ]


def test_check_writes_the_json_result_and_exits_0_without_gates(tmp_path):
    code, out, err = run(check_args(tmp_path, "ex01.yaml", extra=["--format", "json"]))
    assert code == 0, err
    written = tmp_path / "out" / "policy_findings_20261120_000000.json"
    result = json.loads(written.read_text())
    assert result["summary"]["by_result"]["fail"] == 1
    assert result["summary"]["exit_code"] == 0
    assert result["snapshot"]["file"] == "s1.json"
    assert err == f"Wrote {written}\n"
    assert out == ""


def test_check_file_equals_the_engines_bytes(tmp_path):
    from inventag.policy import engine

    code, out, err = run(check_args(tmp_path, "ex01.yaml", extra=["--format", "json"]))
    assert code == 0, err
    text = (tmp_path / "out" / "policy_findings_20261120_000000.json").read_text()
    assert text == engine.dumps(json.loads(text))
    assert text.endswith("}\n")


def test_check_fail_on_exits_7(tmp_path):
    args = check_args(
        tmp_path, "ex01.yaml", extra=["--format", "json", "--fail-on", "high"]
    )
    code, out, err = run(args)
    assert code == 7, err
    assert (tmp_path / "out" / "policy_findings_20261120_000000.json").exists()


def test_check_fail_on_above_the_failures_exits_0(tmp_path):
    args = check_args(
        tmp_path, "ex01.yaml", extra=["--format", "json", "--fail-on", "critical"]
    )
    code, out, err = run(args)
    assert code == 0, err


def test_check_fail_on_not_evaluated_exits_8_and_wins_over_7(tmp_path):
    args = check_args(
        tmp_path,
        "ex05.yaml",
        extra=["--format", "json", "--fail-on", "low", "--fail-on-not-evaluated"],
    )
    code, out, err = run(args)
    assert code == 8, err
    written = tmp_path / "out" / "policy_findings_20261120_000000.json"
    assert json.loads(written.read_text())["summary"]["exit_code"] == 8


def test_check_not_evaluated_without_the_flag_exits_0(tmp_path):
    code, out, err = run(check_args(tmp_path, "ex05.yaml", extra=["--format", "json"]))
    assert code == 0, err


def test_check_invalid_policy_exits_1_and_writes_nothing(tmp_path):
    args = check_args(tmp_path, "ex01.yaml", extra=["--format", "json"])
    (tmp_path / "policies" / "broken.yaml").write_text("kind: policy\n")
    code, out, err = run(args)
    assert code == 1
    assert err.startswith("error: broken.yaml")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "content, message",
    [
        (None, "cannot read the file (No such file or directory)"),
        ("{", "is not valid JSON (line 1, column 2)"),
        ("[]", "is not a state file (no 'resources' list)"),
        ('{"resources": 3}', "is not a state file (no 'resources' list)"),
    ],
)
def test_check_bad_snapshot_exits_1(tmp_path, content, message):
    args = check_args(tmp_path, "ex01.yaml", extra=["--format", "json"])
    snap = tmp_path / "s1.json"
    if content is None:
        snap.unlink()
    else:
        snap.write_text(content)
    code, out, err = run(args)
    assert code == 1
    assert err == (
        f"error: --snapshot s1.json: {message}; give a state file that "
        "InvenTag wrote.\n"
    )
    assert not (tmp_path / "out").exists()


def test_check_unknown_format_word_exits_2(tmp_path):
    code, out, err = run(
        check_args(tmp_path, "ex01.yaml", extra=["--format", "json,pdf"])
    )
    assert code == 2
    assert err == (
        "error: --format: unknown format 'pdf'; use text, json, sarif, junit, "
        "markdown.\n"
    )
    assert not (tmp_path / "out").exists()


def test_check_bad_now_exits_2(tmp_path):
    args = check_args(tmp_path, "ex01.yaml", extra=["--format", "json"])
    args[args.index("--now") + 1] = "20.11.2026"
    code, out, err = run(args)
    assert code == 2
    assert err == "error: --now: '20.11.2026' is not a date; write YYYY-MM-DD.\n"


def test_check_bad_fail_on_exits_2(tmp_path):
    code, out, err = run(check_args(tmp_path, "ex01.yaml", extra=["--fail-on", "huge"]))
    assert code == 2


def test_check_locked_needs_a_policy_folder_exit_2(tmp_path):
    args = check_args(tmp_path, "ex01.yaml", extra=["--format", "json", "--locked"])
    args[args.index("--policies") + 1] = tmp_path / "policies" / "ex01.yaml"
    code, out, err = run(args)
    assert code == 2
    assert err == (
        "error: --locked: --policies must be one folder that holds policy.lock; "
        "give the folder.\n"
    )


def test_check_locked_refuses_a_changed_file_exit_1(tmp_path, monkeypatch):
    seen = []

    def check(root):
        seen.append(root.name)
        return ["ex01.yaml: changed since policy.lock was written"]

    stub(monkeypatch, "lock", check=check)
    args = check_args(tmp_path, "ex01.yaml", extra=["--format", "json", "--locked"])
    code, out, err = run(args)
    assert code == 1
    assert seen == ["policies"]
    assert err == (
        "error: ex01.yaml: changed since policy.lock was written; run "
        "'inventag policy lock' to record the change, or restore the file.\n"
    )
    assert not (tmp_path / "out").exists()


def test_check_locked_passes_when_the_lock_is_current(tmp_path, monkeypatch):
    stub(monkeypatch, "lock", check=lambda root: [])
    args = check_args(tmp_path, "ex01.yaml", extra=["--format", "json", "--locked"])
    code, out, err = run(args)
    assert code == 0, err


def test_check_waivers_are_passed_to_the_engine(tmp_path, monkeypatch):
    calls = []

    def apply(findings, waivers, now, known_policies=()):
        calls.append((len(waivers), now.date().isoformat()))
        return findings, []

    stub(monkeypatch, "waivers", apply=apply)
    waivers = tmp_path / "w16.yaml"
    waivers.write_text((GOLDEN / "waivers" / "w16.yaml").read_text())
    args = check_args(
        tmp_path, "ex01.yaml", extra=["--format", "json", "--waivers", waivers]
    )
    code, out, err = run(args)
    assert code == 0, err
    assert calls == [(1, NOW)]


def test_check_invalid_waivers_file_exits_1(tmp_path):
    waivers = tmp_path / "w.yaml"
    waivers.write_text(
        "format_version: 1\nkind: waivers\nname: w\nspec: {waivers: [{policy: X}]}\n"
    )
    args = check_args(
        tmp_path, "ex01.yaml", extra=["--format", "json", "--waivers", waivers]
    )
    code, out, err = run(args)
    assert code == 1
    assert err.startswith("error: w.yaml")


def test_check_baseline_file_goes_to_the_engine(tmp_path, monkeypatch):
    seen = {}

    def evaluate_policy(policy, snapshot, baseline, ctx, evaluate_rows, snap):
        seen["baseline_rows"] = len(baseline["resources"])
        return (
            [],
            {"pass": 0, "fail": 0, "waived": 0, "not_evaluated": 0, "out_of_scope": 0},
            [],
        )

    stub(monkeypatch, "baseline", evaluate_policy=evaluate_policy)
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "b.yaml").write_text(
        "format_version: 1\nkind: policy\nname: b\n"
        "spec: {id: BAS-001, severity: low, check: [{type: baseline, change: [removed]}]}\n"
    )
    base = snapshot_file(tmp_path, "s0.json")
    args = check_args(tmp_path, extra=["--format", "json", "--baseline", base])
    code, out, err = run(args)
    assert code == 0, err
    assert seen["baseline_rows"] > 0
    written = tmp_path / "out" / "policy_findings_20261120_000000.json"
    assert json.loads(written.read_text())["baseline"]["file"] == "s0.json"


def test_check_other_formats_go_through_the_output_writers(tmp_path, monkeypatch):
    rendered = []

    def render(fmt, result):
        rendered.append(fmt)
        return f"<{fmt} {result['summary']['rows']}>\n"

    stub(monkeypatch, "outputs", render=render)
    args = check_args(
        tmp_path, "ex01.yaml", extra=["--format", "text,sarif,junit,markdown,json"]
    )
    code, out, err = run(args)
    assert code == 0, err
    assert sorted(rendered) == ["junit", "markdown", "sarif", "text"]
    assert out == "<text 10>\n"
    folder = tmp_path / "out"
    assert sorted(p.name for p in folder.iterdir()) == [
        "policy_findings_20261120_000000.json",
        "policy_findings_20261120_000000.md",
        "policy_findings_20261120_000000.sarif",
        "policy_findings_20261120_000000.xml",
    ]
    assert (
        folder / "policy_findings_20261120_000000.xml"
    ).read_text() == "<junit 10>\n"
    assert err.count("Wrote ") == 4


def test_check_text_without_the_output_module_exits_1(tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "inventag.policy.outputs", None)
    args = check_args(tmp_path, "ex01.yaml", extra=["--format", "text"])
    code, out, err = run(args)
    assert code == 1
    assert err == (
        "error: --format text: the output writers (inventag.policy.outputs) "
        "are not installed in this build.\n"
    )


def test_check_show_values_reaches_the_engine(tmp_path):
    args = check_args(
        tmp_path, "ex01.yaml", extra=["--format", "json", "--show-values"]
    )
    code, out, err = run(args)
    assert code == 0, err
    written = tmp_path / "out" / "policy_findings_20261120_000000.json"
    details = [
        f["details"]
        for f in json.loads(written.read_text())["findings"]
        if f.get("details")
    ]
    assert any("value" in d for group in details for d in group)


def test_check_makes_no_aws_call_and_reads_no_environment(tmp_path, monkeypatch):
    import socket

    def refuse(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    code, out, err = run(check_args(tmp_path, "ex01.yaml", extra=["--format", "json"]))
    assert code == 0, err


# ----------------------------------------------------------------- explain


def explain_args(tmp_path, policy, *extra):
    folder = policies_dir(tmp_path, "ex05.yaml")
    return [
        "explain",
        policy,
        "--policies",
        folder,
        "--snapshot",
        snapshot_file(tmp_path),
        "--now",
        NOW,
        *extra,
    ]


def test_explain_shows_each_row_with_the_deciding_check(tmp_path):
    code, out, err = run(explain_args(tmp_path, "TAG-002"))
    assert code == 0, err
    lines = out.splitlines()
    assert lines[0] == "TAG-002 (tag-002, medium, version 1)"
    assert "fail  arn:aws:ec2:us-east-1:111111111111:instance/i-0bbb" in lines
    assert "      check 0 (required-tags): missing tag: Owner" in lines
    assert "      check 0 (required-tags): missing tag: Environment" in lines
    assert (
        "not_evaluated  arn:aws:ec2:ap-southeast-1:222222222222:instance/i-0ccc"
        in lines
    )
    assert "      reason: tags_not_read" in lines
    assert "pass  arn:aws:s3:::logs-prod" in lines
    assert lines[-1] == "Rows: 8 selected, 2 not selected."


def test_explain_by_name_and_one_resource(tmp_path):
    arn = "arn:aws:ec2:us-east-1:111111111111:instance/i-0bbb"
    code, out, err = run(explain_args(tmp_path, "tag-002", "--resource", arn))
    assert code == 0, err
    assert out.count("arn:aws:") == 1
    assert "i-0bbb" in out


def test_explain_unknown_resource_exits_1(tmp_path):
    code, out, err = run(
        explain_args(tmp_path, "TAG-002", "--resource", "arn:aws:s3:::none")
    )
    assert code == 1
    assert err == (
        "error: --resource arn:aws:s3:::none: the policy does not select a row "
        "with this ARN; check the ARN or run without --resource.\n"
    )


def test_explain_unknown_policy_exits_1(tmp_path):
    code, out, err = run(explain_args(tmp_path, "NOPE-001"))
    assert code == 1
    assert err == (
        "error: no policy with id or name 'NOPE-001'; run 'inventag policy "
        "list' to see the loaded policies.\n"
    )


def test_explain_shows_no_found_value_without_show_values(tmp_path):
    folder = policies_dir(tmp_path, "ex01.yaml")
    args = [
        "explain",
        "RDS-001",
        "--policies",
        folder,
        "--snapshot",
        snapshot_file(tmp_path),
        "--now",
        NOW,
    ]
    code, out, err = run(args)
    assert code == 0, err
    assert "(value:" not in out
    code, shown, err = run(args + ["--show-values"])
    assert code == 0, err
    assert "(value: false)" in shown


# -------------------------------------------------------------------- lock


def test_lock_writes_through_the_lock_module(tmp_path, monkeypatch):
    folder = policies_dir(tmp_path, "ex01.yaml")
    written = []

    def write(root):
        written.append(root.name)
        return root / "policy.lock"

    stub(monkeypatch, "lock", write=write)
    code, out, err = run(["lock", folder])
    assert code == 0, err
    assert written == ["policies"]
    assert out == f"Wrote {folder / 'policy.lock'}\n"


def test_lock_check_current_exits_0(tmp_path, monkeypatch):
    folder = policies_dir(tmp_path, "ex01.yaml")
    stub(monkeypatch, "lock", check=lambda root: [])
    code, out, err = run(["lock", "--check", folder])
    assert code == 0, err
    assert out == "policy.lock is current.\n"


def test_lock_check_changed_exits_1(tmp_path, monkeypatch):
    folder = policies_dir(tmp_path, "ex01.yaml")
    stub(
        monkeypatch,
        "lock",
        check=lambda root: ["ex01.yaml: changed since policy.lock was written"],
    )
    code, out, err = run(["lock", "--check", folder])
    assert code == 1
    assert out == ""
    assert err == (
        "error: ex01.yaml: changed since policy.lock was written; run "
        "'inventag policy lock' to record the change, or restore the file.\n"
    )


def test_lock_missing_folder_exits_1(tmp_path):
    code, out, err = run(["lock", tmp_path / "none"])
    assert code == 1
    assert err == (
        f"error: policy folder {tmp_path / 'none'} does not exist; give the folder.\n"
    )


def test_lock_without_the_lock_module_exits_1(tmp_path, monkeypatch):
    import sys

    folder = policies_dir(tmp_path, "ex01.yaml")
    monkeypatch.setitem(sys.modules, "inventag.policy.lock", None)
    code, out, err = run(["lock", folder])
    assert code == 1
    assert err == (
        "error: policy lock: inventag.policy.lock is not installed in this build.\n"
    )


# -------------------------------------------------------------- the group


def test_no_command_is_exit_2():
    code, out, err = run([])
    assert code == 2


def test_help_is_exit_0():
    code, out, err = run(["--help"])
    assert code == 0
    for word in ("validate", "list", "schema", "test", "check", "explain", "lock"):
        assert word in out
