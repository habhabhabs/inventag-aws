"""P4b (spec 11.6, 11.7; rulings of architect-v150-p3p4-rulings.md): default
text output, ``--set`` with shipped sets, ``explain --baseline`` and the trace,
``reason`` and ``expect_units`` in fixtures. Every test asserts the exit code.

The engine's ``trace`` (P1c) is faked here: ``evaluate(..., trace=True,
trace_resource=ARN)`` puts ``trace`` on each finding, and a ``trace_resource``
that is out of scope comes back as a finding with ``result: out_of_scope``.
"""

import json

from inventag.policy import engine, loader

from .cli_helpers import GOLDEN, NOW, policies_dir, run, snapshot_file, stub
from .test_policy_testing import BUCKET, DB_A, DB_B, GOOD, ROW, fixture_text, project

TREE = {
    "part": "check",
    "kind": "and",
    "verdict": "false",
    "children": [
        {"part": "resource", "kind": "services", "verdict": "true"},
        {"part": "check", "kind": "required-tags", "key": "Owner", "verdict": "false"},
        {
            "part": "check",
            "kind": "value",
            "key": "raw_data.X",
            "verdict": "unknown",
            "reason": "identity_only",
        },
    ],
}
TRACE_LINES = [
    "      trace:",
    "        check and: false",
    "          resource services: true",
    "          check required-tags Owner: false",
    "          check value raw_data.X: unknown (identity_only)",
]


def fake_trace(monkeypatch):
    real = engine.evaluate

    def evaluate(*args, trace=False, trace_resource=None, **kwargs):
        result = real(*args, **kwargs)
        if trace:
            for finding in result["findings"]:
                finding["trace"] = TREE
            asked = trace_resource
            if asked and asked not in [f["resource"] for f in result["findings"]]:
                result["findings"].append(
                    {
                        "policy": "X",
                        "result": "out_of_scope",
                        "resource": asked,
                        "trace": TREE,
                    }
                )
        return result

    monkeypatch.setattr(engine, "evaluate", evaluate)


def shipped(monkeypatch, name="tagging-standard", policy="ex05.yaml"):
    def load_set(wanted):
        assert wanted == name
        return loader.load(
            [GOLDEN / "policies" / policy], root=GOLDEN / "policies"
        ).policies

    stub(monkeypatch, "builtin", SET_NAMES=(name,), load_set=load_set)


def out_args(tmp_path, *extra, policy_files=("ex01.yaml",)):
    return [
        "check",
        "--snapshot",
        snapshot_file(tmp_path),
        "--now",
        NOW,
        "--output-directory",
        tmp_path / "out",
        *extra,
    ]


# ------------------------------------------------------- default output


def test_check_default_is_text_on_stdout_and_no_file(tmp_path, monkeypatch):
    stub(monkeypatch, "outputs", render=lambda result, fmt, **kw: f"<{fmt}>\n")
    folder = policies_dir(tmp_path, "ex01.yaml")
    code, out, err = run(out_args(tmp_path, "--policies", folder))
    assert code == 0, err
    assert out == "<text>\n"
    assert err == ""
    assert not (tmp_path / "out").exists()
    assert list(tmp_path.glob("policy_findings_*")) == []


def test_check_json_is_written_only_when_named(tmp_path, monkeypatch):
    stub(monkeypatch, "outputs", render=lambda result, fmt, **kw: f"<{fmt}>\n")
    folder = policies_dir(tmp_path, "ex01.yaml")
    code, out, err = run(out_args(tmp_path, "--policies", folder, "--format", "json"))
    assert code == 0, err
    assert out == ""
    assert [p.name for p in (tmp_path / "out").iterdir()] == [
        "policy_findings_20261120_000000.json"
    ]


def test_show_values_with_sarif_or_junit_says_so_once(tmp_path, monkeypatch):
    stub(monkeypatch, "outputs", render=lambda result, fmt, **kw: "x\n")
    folder = policies_dir(tmp_path, "ex01.yaml")
    args = out_args(
        tmp_path, "--policies", folder, "--format", "sarif,junit", "--show-values"
    )
    code, out, err = run(args)
    assert code == 0, err
    assert err.splitlines()[0] == (
        "note: --show-values does not apply to sarif and junit; those files "
        "never carry a value."
    )
    assert err.count("note:") == 1


def test_show_values_with_json_has_no_note(tmp_path):
    folder = policies_dir(tmp_path, "ex01.yaml")
    args = out_args(tmp_path, "--policies", folder, "--format", "json", "--show-values")
    code, out, err = run(args)
    assert code == 0, err
    assert "note:" not in err


# ------------------------------------------------------------- --set


def test_list_shipped_lists_the_shipped_sets(tmp_path, monkeypatch):
    shipped(monkeypatch)
    code, out, err = run(["list", "--shipped"])
    assert code == 0, err
    assert out.split() == ["NAME", "POLICIES", "tagging-standard", "1"]


def test_list_shipped_with_set_is_exit_2(tmp_path, monkeypatch):
    shipped(monkeypatch)
    code, out, err = run(["list", "--shipped", "--set", "x"])
    assert code == 2
    assert err == "error: --shipped cannot be used with --set; use one of them.\n"


def test_list_set_falls_back_to_a_shipped_set(tmp_path, monkeypatch):
    shipped(monkeypatch)
    folder = policies_dir(tmp_path, "ex01.yaml")
    code, out, err = run(["list", "--policies", folder, "--set", "tagging-standard"])
    assert code == 0, err
    assert [l.split()[0] for l in out.splitlines()[1:]] == ["TAG-002"]
    assert err == ""


def test_list_set_without_any_policy_folder_uses_the_shipped_set(tmp_path, monkeypatch):
    shipped(monkeypatch)
    monkeypatch.chdir(tmp_path)
    code, out, err = run(["list", "--set", "tagging-standard"])
    assert code == 0, err
    assert [l.split()[0] for l in out.splitlines()[1:]] == ["TAG-002"]


def test_a_local_set_hides_the_shipped_one_and_says_so(tmp_path, monkeypatch):
    shipped(monkeypatch)
    folder = policies_dir(tmp_path, "ex01.yaml", "ex05.yaml")
    (folder / "ts.yaml").write_text(
        "format_version: 1\nkind: policy-set\nname: tagging-standard\n"
        "spec: {policies: [rds-001]}\n"
    )
    code, out, err = run(["list", "--policies", folder, "--set", "tagging-standard"])
    assert code == 0, err
    assert [l.split()[0] for l in out.splitlines()[1:]] == ["RDS-001"]
    assert err == (
        "note: the policy set 'tagging-standard' in your files hides the "
        "shipped set of the same name.\n"
    )


def test_check_set_uses_only_that_sets_policies(tmp_path, monkeypatch):
    shipped(monkeypatch)
    monkeypatch.chdir(tmp_path)
    args = out_args(tmp_path, "--set", "tagging-standard", "--format", "json")
    code, out, err = run(args)
    assert code == 0, err
    written = tmp_path / "out" / "policy_findings_20261120_000000.json"
    ids = [p["id"] for p in json.loads(written.read_text())["policies"]]
    assert ids == ["TAG-002"]


def test_check_unknown_set_is_exit_1(tmp_path, monkeypatch):
    shipped(monkeypatch)
    monkeypatch.chdir(tmp_path)
    code, out, err = run(out_args(tmp_path, "--set", "nope", "--format", "json"))
    assert code == 1
    assert err.startswith("error: no policy set named 'nope'")
    assert not (tmp_path / "out").exists()


def test_explain_set_finds_the_policy_in_the_shipped_set(tmp_path, monkeypatch):
    shipped(monkeypatch)
    monkeypatch.chdir(tmp_path)
    args = [
        "explain",
        "TAG-002",
        "--set",
        "tagging-standard",
        "--snapshot",
        snapshot_file(tmp_path),
        "--now",
        NOW,
    ]
    code, out, err = run(args)
    assert code == 0, err
    assert out.splitlines()[0] == "TAG-002 (tag-002, medium, version 1)"


# ------------------------------------------------- explain: baseline, trace


def explain_args(tmp_path, folder, *extra, policy="RDS-001"):
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


def baseline_policy(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "b.yaml").write_text(
        "format_version: 1\nkind: policy\nname: bas\n"
        "spec: {id: BAS-001, severity: low, check: [{type: baseline, change: [removed]}]}\n"
    )
    return folder


def test_explain_without_baseline_keeps_the_line_and_exits_0(tmp_path):
    folder = baseline_policy(tmp_path)
    code, out, err = run(explain_args(tmp_path, folder, policy="BAS-001"))
    assert code == 0, err
    assert out.splitlines()[1:] == [
        "This policy needs a baseline; pass --baseline FILE. No row was evaluated."
    ]


def test_explain_baseline_goes_to_the_baseline_module(tmp_path, monkeypatch):
    seen = {}

    def evaluate_policy(policy, snapshot, baseline, ctx, evaluate_rows, snap):
        seen["rows"] = len(baseline["resources"])
        return (
            [],
            {"pass": 0, "fail": 0, "waived": 0, "not_evaluated": 0, "out_of_scope": 0},
            [],
        )

    stub(monkeypatch, "baseline", evaluate_policy=evaluate_policy)
    folder = baseline_policy(tmp_path)
    base = snapshot_file(tmp_path, "s0.json")
    code, out, err = run(
        explain_args(tmp_path, folder, "--baseline", base, policy="BAS-001")
    )
    assert code == 0, err
    assert seen["rows"] > 0
    assert "needs a baseline" not in out


def test_explain_bad_baseline_file_exits_1(tmp_path):
    folder = baseline_policy(tmp_path)
    (tmp_path / "bad.json").write_text("[]")
    code, out, err = run(
        explain_args(
            tmp_path, folder, "--baseline", tmp_path / "bad.json", policy="BAS-001"
        )
    )
    assert code == 1
    assert err == (
        "error: --baseline bad.json: is not a state file (no 'resources' "
        "list); give a state file that InvenTag wrote.\n"
    )


def test_explain_prints_the_trace_of_each_row(tmp_path, monkeypatch):
    fake_trace(monkeypatch)
    folder = policies_dir(tmp_path, "ex01.yaml")
    code, out, err = run(explain_args(tmp_path, folder))
    assert code == 0, err
    lines = out.splitlines()
    at = lines.index("fail  arn:aws:rds:eu-west-1:111111111111:db:db-orders")
    assert lines[at + 1] == (
        "      check 0 (value): condition not met: raw_data.StorageEncrypted"
    )
    assert lines[at + 2 : at + 2 + len(TRACE_LINES)] == TRACE_LINES


def test_explain_trace_of_an_out_of_scope_row(tmp_path, monkeypatch):
    fake_trace(monkeypatch)
    folder = policies_dir(tmp_path, "ex01.yaml")
    code, out, err = run(
        explain_args(tmp_path, folder, "--resource", "arn:aws:s3:::logs-prod")
    )
    assert code == 0, err
    lines = out.splitlines()
    assert "out_of_scope  arn:aws:s3:::logs-prod" in lines
    for line in TRACE_LINES:
        assert line in lines
    assert lines[-1] == "Rows: 0 selected, 1 not selected."


def test_explain_trace_never_shows_a_value(tmp_path, monkeypatch):
    fake_trace(monkeypatch)
    folder = policies_dir(tmp_path, "ex01.yaml")
    code, out, err = run(explain_args(tmp_path, folder))
    assert code == 0, err
    assert "(value:" not in out


# ----------------------------------------------------------- fixtures


def test_a_fixture_with_unread_listings_must_give_expect_units(tmp_path):
    extra = (
        "units_not_read:\n"
        '  - {account: "111111111111", service: rds, region: eu-west-1, '
        "source: service-api, outcome: denied}\n"
    )
    text = fixture_text(
        [ROW % ("a", DB_A, "true")], [f'{{resource: "{DB_A}", result: pass}}'], extra
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert out.splitlines() == [
        "FAIL  rds-001/basic.yaml",
        "      this fixture has unread listings: say which unit lines you expect",
        "1 fixtures, 1 failed.",
    ]


def test_no_unread_listing_and_no_expect_units_is_not_checked(tmp_path):
    folder = project(tmp_path, ("basic.yaml", GOOD))
    code, out, err = run(["test", folder])
    assert code == 0, err


def test_expect_units_entry_may_say_from_baseline(tmp_path):
    text = fixture_text(
        [ROW % ("a", DB_A, "true")],
        [f'{{resource: "{DB_A}", result: pass}}'],
        'expect_units:\n  - {account: "111111111111", service: rds, '
        "region: eu-west-1, from: baseline}\n",
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert (
        "      unit 111111111111/rds/eu-west-1 from baseline: expected not "
        "read, but the policy reports no such unit" in out.splitlines()
    )


def test_expect_units_from_must_be_baseline(tmp_path):
    text = fixture_text(
        [ROW % ("a", DB_A, "true")],
        [f'{{resource: "{DB_A}", result: pass}}'],
        'expect_units:\n  - {account: "111111111111", service: rds, '
        "region: eu-west-1, from: other}\n",
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert err.startswith("error: tests/rds-001/basic.yaml:")
    assert "spec.expect_units.0.from: must be baseline" in err


def identity_fixture(reason, result="not_evaluated"):
    row = (ROW % ("a", DB_A, "true")).replace(
        "detail_level: full", "detail_level: identity"
    )
    return fixture_text(
        [row], [f'{{resource: "{DB_A}", result: {result}, reason: {reason}}}']
    )


def test_expect_reason_that_matches_passes(tmp_path):
    folder = project(tmp_path, ("basic.yaml", identity_fixture("identity_only")))
    code, out, err = run(["test", folder])
    assert code == 0, out + err


def test_expect_reason_that_differs_fails(tmp_path):
    folder = project(tmp_path, ("basic.yaml", identity_fixture("tags_not_read")))
    code, out, err = run(["test", folder])
    assert code == 1
    assert (
        f"      {DB_A}: expected reason tags_not_read, got identity_only"
        in out.splitlines()
    )


def test_expect_reason_only_with_not_evaluated(tmp_path):
    text = fixture_text(
        [ROW % ("a", DB_A, "true")],
        [f'{{resource: "{DB_A}", result: pass, reason: identity_only}}'],
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert err == (
        "error: tests/rds-001/basic.yaml:10: spec.expect.0.reason: only allowed "
        "with result: not_evaluated\n"
    )
