"""``inventag policy test`` and ``inventag.policy.testing`` (P4, spec section 5).

Fixtures live under ``tests/<policy name>/*.yaml`` next to the policies.
Every test asserts the exit code.
"""

import textwrap

import pytest

from .cli_helpers import GOLDEN, policies_dir, run, stub

DB_A = "arn:aws:rds:eu-west-1:111111111111:db:a"
DB_B = "arn:aws:rds:eu-west-1:111111111111:db:b"
BUCKET = "arn:aws:s3:::logs"

ROW = (
    '{service: RDS, resource_type: DBInstance, resource_id: %s, arn: "%s",'
    ' region: eu-west-1, source_account_id: "111111111111", detail_level: full,'
    " tags: {}, raw_data: {StorageEncrypted: %s}}"
)
BUCKET_ROW = (
    '{service: S3, resource_type: Bucket, resource_id: logs, arn: "%s",'
    ' region: us-east-1, source_account_id: "111111111111", detail_level: full,'
    " tags: {}, raw_data: {}}" % BUCKET
)


def fixture_text(resources, expect, extra="", name="basic", policy="rds-001"):
    rows = "\n".join(f"    - {r}" for r in resources) or "    []"
    wanted = "\n".join(f"    - {e}" for e in expect) or "    []"
    return (
        "format_version: 1\nkind: policy-test\n"
        f"name: {name}\n"
        "spec:\n"
        f"  policy: {policy}\n"
        "  now: 2026-11-20\n"
        f"  resources:\n{rows}\n"
        f"  expect:\n{wanted}\n" + textwrap.indent(extra, "  ") + "\n"
    )


def project(tmp_path, *fixtures, policy="ex01.yaml"):
    """A policy folder with ``fixtures``: a list of (file name, text)."""
    folder = policies_dir(tmp_path, policy)
    for file_name, text in fixtures:
        target = folder / "tests" / "rds-001" / file_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return folder


GOOD = fixture_text(
    [ROW % ("a", DB_A, "true"), ROW % ("b", DB_B, "false"), BUCKET_ROW],
    [
        f'{{resource: "{DB_A}", result: pass}}',
        f'{{resource: "{DB_B}", result: fail}}',
        f'{{resource: "{BUCKET}", result: out_of_scope}}',
    ],
)


def test_every_expectation_holds_exit_0(tmp_path):
    folder = project(tmp_path, ("basic.yaml", GOOD))
    code, out, err = run(["test", folder])
    assert code == 0, err
    assert out.splitlines() == [
        "PASS  rds-001/basic.yaml",
        "1 fixtures, 0 failed.",
    ]
    assert err == ""


def test_a_wrong_result_fails_the_fixture_exit_1(tmp_path):
    text = GOOD.replace(
        f'resource: "{DB_B}", result: fail', f'resource: "{DB_B}", result: pass'
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert out.splitlines() == [
        "FAIL  rds-001/basic.yaml",
        f"      {DB_B}: expected pass, got fail",
        "1 fixtures, 1 failed.",
    ]


def test_a_selected_row_without_expectation_fails_exit_1(tmp_path):
    text = fixture_text(
        [ROW % ("a", DB_A, "true"), ROW % ("b", DB_B, "false")],
        [f'{{resource: "{DB_A}", result: pass}}'],
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert f"      {DB_B}: no expectation for this row (got fail)" in out.splitlines()


def test_a_not_selected_row_must_be_listed_as_out_of_scope_exit_1(tmp_path):
    text = fixture_text(
        [ROW % ("a", DB_A, "true"), BUCKET_ROW],
        [f'{{resource: "{DB_A}", result: pass}}'],
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert (
        f"      {BUCKET}: no expectation for this row (got out_of_scope)"
        in out.splitlines()
    )


def test_an_extra_expectation_fails_exit_1(tmp_path):
    text = (
        GOOD
        + f'    - {{resource: "arn:aws:rds:eu-west-1:111111111111:db:zzz", result: pass}}\n'
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert (
        "      arn:aws:rds:eu-west-1:111111111111:db:zzz: expected pass, but the "
        "fixture has no such row" in out.splitlines()
    )


def test_out_of_scope_expected_for_a_selected_row_fails_exit_1(tmp_path):
    text = GOOD.replace(
        f'resource: "{DB_A}", result: pass', f'resource: "{DB_A}", result: out_of_scope'
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert f"      {DB_A}: expected out_of_scope, got pass" in out.splitlines()


def test_not_evaluated_for_an_identity_only_row(tmp_path):
    row = (ROW % ("a", DB_A, "true")).replace(
        "detail_level: full", "detail_level: identity"
    )
    text = fixture_text([row], [f'{{resource: "{DB_A}", result: not_evaluated}}'])
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 0, err


def test_units_not_read_and_expect_units(tmp_path):
    extra = (
        "units_not_read:\n"
        '  - {account: "111111111111", service: rds, region: eu-west-1, source: service-api, outcome: denied}\n'
        "expect_units:\n"
        '  - {account: "111111111111", service: rds, region: eu-west-1}\n'
    )
    text = fixture_text(
        [ROW % ("a", DB_A, "true")], [f'{{resource: "{DB_A}", result: pass}}'], extra
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 0, err


def test_expect_units_that_differ_fail_exit_1(tmp_path):
    text = fixture_text(
        [ROW % ("a", DB_A, "true")],
        [f'{{resource: "{DB_A}", result: pass}}'],
        'expect_units:\n  - {account: "111111111111", service: rds, region: eu-west-1}\n',
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert (
        "      unit 111111111111/rds/eu-west-1: expected not read, but the policy "
        "reports no such unit" in out.splitlines()
    )


def test_waivers_in_a_fixture_reach_the_waiver_module(tmp_path, monkeypatch):
    def apply(findings, waivers, now):
        assert [w.policy for w in waivers] == ["RDS-001"]
        out = []
        for f in findings:
            out.append(dict(f, result="waived") if f["result"] == "fail" else f)
        return out, []

    stub(monkeypatch, "waivers", apply=apply)
    extra = (
        "waivers:\n"
        f'  - {{policy: RDS-001, resource: "{DB_B}", reason: "Ticket OPS-123, migration.",'
        " approved_by: lead, expires: 2026-12-31}\n"
    )
    text = fixture_text(
        [ROW % ("b", DB_B, "false")], [f'{{resource: "{DB_B}", result: waived}}'], extra
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 0, err


def test_baseline_resources_reach_the_baseline_module(tmp_path, monkeypatch):
    seen = {}

    def evaluate_policy(policy, snapshot, baseline, ctx, evaluate_rows, snap):
        seen["n"] = len(baseline["resources"])
        return evaluate_rows(policy, snap, ctx)

    stub(monkeypatch, "baseline", evaluate_policy=evaluate_policy)
    path = tmp_path / "policies"
    path.mkdir()
    (path / "b.yaml").write_text(
        "format_version: 1\nkind: policy\nname: rds-001\n"
        "spec: {id: RDS-001, severity: low, check: [{type: baseline, change: [removed]}]}\n"
    )
    fixture = path / "tests" / "rds-001" / "base.yaml"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        fixture_text(
            [], [], "baseline_resources:\n  - " + (ROW % ("a", DB_A, "true")) + "\n"
        )
    )
    code, out, err = run(["test", path])
    assert seen == {"n": 1}
    assert code == 0, out + err


def test_an_unknown_field_in_a_fixture_exits_1_and_names_it(tmp_path):
    text = GOOD.replace("  now: 2026-11-20\n", "  now: 2026-11-20\n  colour: blue\n")
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert err == (
        "error: tests/rds-001/basic.yaml:7: spec.colour: unknown field 'colour' "
        "Allowed here: baseline_resources, expect, expect_units, now, policy, "
        "resources, units_not_read, waivers\n"
    )


def test_a_fixture_naming_an_unknown_policy_exits_1(tmp_path):
    text = GOOD.replace("policy: rds-001", "policy: nope")
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert err == (
        "error: tests/rds-001/basic.yaml:5: spec.policy: no policy named "
        "'nope' in this folder; use a name shown by 'inventag policy list'.\n"
    )


def test_a_fixture_in_the_wrong_folder_exits_1(tmp_path):
    folder = project(tmp_path)
    wrong = folder / "tests" / "other" / "basic.yaml"
    wrong.parent.mkdir(parents=True)
    wrong.write_text(GOOD)
    code, out, err = run(["test", folder])
    assert code == 1
    assert err == (
        "error: tests/other/basic.yaml:5: spec.policy: the fixture is in "
        "tests/other but tests the policy 'rds-001'; move it to tests/rds-001.\n"
    )


def test_a_fixture_waiver_that_is_not_valid_exits_1(tmp_path):
    extra = 'waivers:\n  - {policy: RDS-001, resource: "*", reason: "Ticket OPS-123, migration.", approved_by: x, expires: 2026-12-31}\n'
    text = fixture_text(
        [ROW % ("a", DB_A, "true")], [f'{{resource: "{DB_A}", result: pass}}'], extra
    )
    folder = project(tmp_path, ("basic.yaml", text))
    code, out, err = run(["test", folder])
    assert code == 1
    assert err.startswith("error: tests/rds-001/basic.yaml:")
    assert "waivers" in err


def test_an_invalid_policy_exits_1_before_any_fixture_runs(tmp_path):
    folder = project(tmp_path, ("basic.yaml", GOOD))
    (folder / "broken.yaml").write_text("kind: policy\n")
    code, out, err = run(["test", folder])
    assert code == 1
    assert out == ""
    assert err.startswith("error: broken.yaml")


def test_a_policy_without_fixtures_is_a_warning_exit_0(tmp_path):
    folder = policies_dir(tmp_path, "ex01.yaml")
    code, out, err = run(["test", folder])
    assert code == 0, err
    assert err == (
        "WARNING policy rds-001 has no fixtures; add tests/rds-001/NAME.yaml.\n"
    )
    assert out == "0 fixtures, 0 failed.\n"


def test_several_fixtures_run_in_name_order_and_one_failure_gives_1(tmp_path):
    bad = GOOD.replace(
        f'resource: "{DB_B}", result: fail', f'resource: "{DB_B}", result: pass'
    )
    folder = project(tmp_path, ("b-bad.yaml", bad), ("a-good.yaml", GOOD))
    code, out, err = run(["test", folder])
    assert code == 1
    heads = [line for line in out.splitlines() if line[:4] in ("PASS", "FAIL")]
    assert heads == ["PASS  rds-001/a-good.yaml", "FAIL  rds-001/b-bad.yaml"]
    assert out.splitlines()[-1] == "2 fixtures, 1 failed."


def test_default_folder_missing_exits_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, out, err = run(["test"])
    assert code == 1
    assert err == (
        "error: policy folder .inventag/policies does not exist; give the folder "
        "as DIR.\n"
    )


def test_the_testing_module_returns_a_report(tmp_path):
    from inventag.policy import testing

    folder = project(tmp_path, ("basic.yaml", GOOD))
    report = testing.run(folder)
    assert report.ok is True
    assert [r.name for r in report.results] == ["rds-001/basic.yaml"]
    assert report.results[0].problems == []
    assert report.warnings == []


def test_fixtures_are_not_read_as_policies_by_validate(tmp_path):
    folder = project(tmp_path, ("basic.yaml", GOOD))
    code, out, err = run(["validate", folder])
    assert code == 0, err
    assert out.splitlines()[-1] == "1 policies, 0 sets, 0 waivers: no problems."
