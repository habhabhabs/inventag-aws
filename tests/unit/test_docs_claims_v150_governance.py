"""Docs claim check for v1.5.0 governance pages (package P8, part A).

Pages: docs/guides/governance-as-code.md, docs/reference/policy-files.md,
docs/reference/policy-sets.md.

Every output block and table the pages show is produced here by the real
``inventag policy`` command or the real engine and compared with the page. A
test marked ``xfail(strict=True)`` states what the page says is NOT verified
(a build problem found while writing the page); when the build is fixed the
test passes, strict mode fails the run, and the page sentence is to be removed.
"""

import copy
import datetime as dt
import io
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from inventag.policy import builtin, cli, engine, loader, model
from inventag.policy.outputs import findings_schema

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
GUIDE = DOCS / "guides" / "governance-as-code.md"
FILES = DOCS / "reference" / "policy-files.md"
SETS = DOCS / "reference" / "policy-sets.md"
GOLDEN = ROOT / "tests" / "unit" / "policy" / "golden"
NOW = "2026-11-20"
ACCOUNT = "111111111111"


# ------------------------------------------------------------------ helpers
def text_of(path):
    return path.read_text(encoding="utf-8")


def fences(text):
    """[(info line, body)] of the fenced blocks, in order."""
    return [
        (m.group(1).strip(), m.group(2))
        for m in re.finditer(r"^```([^\n]*)\n(.*?)^```", text, re.S | re.M)
    ]


def block(text, *needles, lang="yaml"):
    """The body of the one fenced block of ``lang`` that holds every needle."""
    found = [
        body
        for info, body in fences(text)
        if info.split(" ")[0] == lang and all(n in body for n in needles)
    ]
    assert len(found) == 1, (needles, len(found))
    return found[0]


def output_blocks(text):
    return [
        body.rstrip("\n")
        for info, body in fences(text)
        if info.startswith("text") and 'title="Output"' in info
    ]


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main([str(a) for a in argv], out=out, err=err)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """A folder laid out as the guide says, built from the guide's own blocks."""
    guide = text_of(GUIDE)
    monkeypatch.chdir(tmp_path)
    policies = tmp_path / ".inventag" / "policies"
    (policies / "tests" / "rds-storage-encrypted").mkdir(parents=True)
    (policies / "rds-encrypted.yaml").write_text(block(guide, "id: RDS-001"))
    (policies / "tests" / "rds-storage-encrypted" / "basic.yaml").write_text(
        block(guide, "kind: policy-test")
    )
    (tmp_path / "waivers").mkdir()
    (tmp_path / "waivers" / "waivers.yaml").write_text(block(guide, "kind: waivers"))
    (tmp_path / "drift.yaml").write_text(block(guide, "id: DRF-001"))
    for name in ("s1.json", "s0.json"):
        (tmp_path / name).write_text((GOLDEN / name).read_text())
    return tmp_path


def row(raw=None, tags=None, **kw):
    base = {
        "service": "EC2",
        "resource_type": "Instance",
        "resource_id": "i-1",
        "resource_name": "i-1",
        "arn": f"arn:aws:ec2:us-east-1:{ACCOUNT}:instance/i-1",
        "region": "us-east-1",
        "source_account_id": ACCOUNT,
        "detail_level": "full",
        "tags": tags or {},
        "raw_data": raw if raw is not None else {},
    }
    base.update(kw)
    return base


def snapshot(rows, units=()):
    return {
        "metadata": {
            "timestamp": "2026-11-20T00:00:00+00:00",
            "tags": {"inventag_version": "1.5.0", "units_not_read": list(units)},
        },
        "resources": rows,
    }


def policy_text(check, severity="low", pid="TT-001", resource=None, require=None):
    spec = {"id": pid, "severity": severity, "check": check}
    if resource:
        spec["resource"] = resource
    if require:
        spec["require"] = require
    return json.dumps(
        {"format_version": 1, "kind": "policy", "name": pid.lower(), "spec": spec},
        indent=1,
    )


def judge(tmp_path, check, rows, units=(), now=NOW, **kw):
    """(result, reason) of the first row for one check entry, with the engine."""
    path = tmp_path / "judge.yaml"
    path.write_text(policy_text(check if isinstance(check, list) else [check], **kw))
    loaded = loader.load([path])
    result = engine.evaluate(
        snapshot(rows, units), loaded.policies, now=now, include_pass=True
    )
    finding = next(f for f in result["findings"] if f["resource"] == rows[0]["arn"])
    return finding["result"], finding.get("reason")


# -------------------------------------------------------------- page hygiene
PAGES = [GUIDE, FILES, SETS]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_the_pages_say_none_of_the_forbidden_words(page):
    body = text_of(page)
    for word in ("compliant", "certified", "enforce"):
        assert word not in body.lower(), word
    assert "—" not in body  # no em dash


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_the_pages_have_front_matter_and_the_two_standard_lines(page):
    body = text_of(page)
    front = yaml.safe_load(body.split("---")[1])
    assert front["title"] and front["description"]
    assert isinstance(front["sidebar_position"], int)
    assert "**Who this is for:**" in body
    assert "**What you can do after reading:**" in body


def test_the_sidebar_positions_do_not_clash_in_their_folder():
    for folder in ("guides", "reference"):
        seen = {}
        for path in (DOCS / folder).glob("*.md"):
            front = yaml.safe_load(text_of(path).split("---")[1])
            seen.setdefault(front.get("sidebar_position"), []).append(path.name)
        assert all(len(v) == 1 for v in seen.values()), seen


# --------------------------------------------------------------- guide: basics
def test_a_policy_with_an_action_field_is_refused(tmp_path):
    for field in ("actions", "mode", "notify", "remediate"):
        folder = tmp_path / field
        folder.mkdir()
        (folder / "p.yaml").write_text(
            "format_version: 1\nkind: policy\nname: p\n"
            f"spec: {{id: AB-001, severity: low, {field}: [], "
            "check: [{type: value, key: raw_data.X, value: 1}]}\n"
        )
        code, out, err = run(["validate", folder])
        assert code == 1
        assert "InvenTag never changes resources; a policy has no actions." in err
    assert "InvenTag never changes resources; a policy has no actions." in " ".join(
        text_of(GUIDE).split()
    )


def test_validate_output_is_the_guides(ws):
    code, out, err = run(["validate", ".inventag/policies"])
    assert code == 0, err
    assert out.rstrip("\n") in output_blocks(text_of(GUIDE))


def test_a_mistake_is_file_line_field_problem_and_exit_1(tmp_path):
    (tmp_path / "p.yaml").write_text(
        "format_version: 1\nkind: policy\nname: p\n"
        "spec: {id: bad, severity: low, check: [{type: value, key: a, value: 1}]}\n"
    )
    code, out, err = run(["validate", tmp_path])
    assert code == 1
    assert err.startswith("error: p.yaml:4: spec.id: ")
    assert out == ""


def test_the_fixture_runs_and_the_output_is_the_guides(ws):
    code, out, err = run(["test", ".inventag/policies"])
    assert code == 0, err
    assert out.rstrip("\n") in output_blocks(text_of(GUIDE))


def test_a_fixture_that_misses_a_row_or_is_wrong_exits_1(ws):
    path = ws / ".inventag" / "policies" / "tests" / "rds-storage-encrypted"
    fixture = path / "basic.yaml"
    original = fixture.read_text()
    fixture.write_text(original.replace('db:b", result: fail', 'db:b", result: pass'))
    code, out, err = run(["test", ".inventag/policies"])
    assert code == 1 and "FAIL" in out
    fixture.write_text(
        "\n".join(
            line
            for line in original.splitlines()
            if 'arn:aws:s3:::logs", result' not in line
        )
        + "\n"
    )
    code, out, err = run(["test", ".inventag/policies"])
    assert code == 1 and "FAIL" in out


def test_check_output_is_the_guides_and_exit_is_7(ws):
    code, out, err = run(
        ["check", "--snapshot", "s1.json", "--now", NOW, "--fail-on", "high"]
    )
    assert code == 7, err
    assert out.rstrip("\n") in output_blocks(text_of(GUIDE))


def test_check_without_a_threshold_exits_0_whatever_it_finds(ws):
    code, out, err = run(["check", "--snapshot", "s1.json", "--now", NOW])
    assert code == 0, err
    assert "fail: 1" in out


def test_explain_output_is_the_guides_and_shows_no_value(ws):
    args = [
        "explain",
        "RDS-001",
        "--snapshot",
        "s1.json",
        "--now",
        NOW,
        "--resource",
        "arn:aws:rds:eu-west-1:111111111111:db:db-orders",
    ]
    code, out, err = run(args)
    assert code == 0, err
    assert out.rstrip("\n") in output_blocks(text_of(GUIDE))
    code2, out2, _ = run(args + ["--show-values"])
    trace = lambda text: text[text.index("trace:") :]  # noqa: E731
    assert trace(out2) == trace(out)


def test_the_not_evaluated_example_and_exit_8(ws):
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--set",
            "naming",
            "--now",
            NOW,
            "--fail-on-not-evaluated",
        ]
    )
    assert code == 8, err
    assert out.rstrip("\n") in output_blocks(text_of(GUIDE))
    assert "tags_not_read" in out


@pytest.mark.parametrize(
    "check, raw, reason",
    [
        (
            {"type": "value", "key": "raw_data.A", "op": "gt", "value": 3},
            {"A": "abc"},
            "not_comparable",
        ),
        (
            {
                "type": "value",
                "key": "raw_data.A",
                "value_type": "age",
                "op": "gt",
                "value": 3,
            },
            {"A": "not a date"},
            "not_convertible",
        ),
        (
            {"type": "value", "key": "raw_data.A", "op": "glob", "value": "x*"},
            {"A": "x" * 5000},
            "value_too_long",
        ),
    ],
)
def test_the_three_comparison_reasons(tmp_path, check, raw, reason):
    assert judge(tmp_path, check, [row(raw)]) == ("not_evaluated", reason)


def test_identity_only_and_field_missing_and_tags_not_read(tmp_path):
    entry = {"type": "value", "key": "raw_data.A", "value": 1}
    assert judge(tmp_path, entry, [row(detail_level="identity")]) == (
        "not_evaluated",
        "identity_only",
    )
    assert judge(tmp_path, entry, [row({})], require=["raw_data.A"]) == (
        "not_evaluated",
        "field_missing",
    )
    unit = {
        "account": ACCOUNT,
        "service": "resourcegroupstaggingapi",
        "region": "us-east-1",
        "source": "tagging-api",
        "outcome": "denied",
    }
    assert judge(tmp_path, {"tag:Owner": "present"}, [row()], units=[unit]) == (
        "not_evaluated",
        "tags_not_read",
    )


def test_the_order_of_reasons_when_several_apply(tmp_path):
    # identity_only before listing_not_read before field_missing before tags_not_read
    assert list(model.REASONS) == [
        "identity_only",
        "listing_not_read",
        "field_missing",
        "tags_not_read",
        "not_comparable",
        "not_convertible",
        "value_too_long",
    ]
    guide = " ".join(text_of(GUIDE).split())
    order = "`identity_only`, `listing_not_read`, `field_missing`, `tags_not_read`, `not_comparable`, `not_convertible`, `value_too_long`"
    assert order in guide
    unit = {
        "account": ACCOUNT,
        "service": "resourcegroupstaggingapi",
        "region": "us-east-1",
        "source": "tagging-api",
        "outcome": "denied",
    }
    entry = {"tag:Owner": "present"}
    # field_missing and tags_not_read both apply: field_missing is written
    assert judge(tmp_path, entry, [row({})], units=[unit], require=["raw_data.A"]) == (
        "not_evaluated",
        "field_missing",
    )


def test_a_unit_not_read_is_listed_under_units_not_read(ws):
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--baseline",
            "s0.json",
            "--policies",
            "drift.yaml",
            "--now",
            NOW,
        ]
    )
    assert "Units not read:\n  DRF-001 111111111111 lambda eu-west-1: throttled" in out


# ---------------------------------------------------------------- guide: waivers
def test_the_waiver_example_output_is_the_guides_and_exit_0(ws):
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--waivers",
            "waivers/waivers.yaml",
            "--now",
            NOW,
            "--fail-on",
            "high",
        ]
    )
    assert code == 0, err
    assert out.rstrip("\n") in output_blocks(text_of(GUIDE))


def waiver_file(path, **override):
    entry = {
        "policy": "RDS-001",
        "resource": "arn:aws:rds:eu-west-1:111111111111:db:db-orders",
        "reason": "Migration to an encrypted instance is planned.",
        "approved_by": "lead",
        "expires": "2026-12-31",
    }
    entry.update(override)
    entry = {k: v for k, v in entry.items() if v is not None}
    path.write_text(
        yaml.safe_dump(
            {
                "format_version": 1,
                "kind": "waivers",
                "name": path.stem,
                "spec": {"waivers": [entry]},
            }
        )
    )
    return path


@pytest.mark.parametrize(
    "override, problem",
    [
        ({"reason": "short"}, "reason must be 10 to 300 characters"),
        ({"resource": "*"}, "a waiver cannot match every resource"),
        (
            {"resource": "arn:aws:rds:*"},
            "account is required when resource has a wildcard",
        ),
        ({"expires": "2028-01-01"}, "expires must be at most 366 days after now"),
        ({"approved_by": None}, "approved_by is required"),
    ],
)
def test_the_waiver_rules_the_guide_states(ws, tmp_path, override, problem):
    path = waiver_file(ws / "w.yaml", **override)
    code, out, err = run(["validate", path, "--now", NOW])
    assert code == 1
    assert problem in err


def test_a_wildcard_waiver_with_an_account_is_accepted(ws):
    path = waiver_file(ws / "w.yaml", resource="arn:aws:rds:*", account=ACCOUNT)
    code, out, err = run(["validate", path, "--now", NOW])
    assert code == 0, err


def findings(ws, *args):
    out_dir = ws / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--format",
            "json",
            "--output-directory",
            out_dir,
            *args,
        ]
    )
    data = json.loads(next(out_dir.glob("*.json")).read_text())
    for f in out_dir.glob("*"):
        f.unlink()
    return code, data


def test_expiry_is_through_the_end_of_the_utc_day_and_then_fail(ws):
    path = waiver_file(ws / "w.yaml", expires="2026-11-30")
    code, data = findings(
        ws, "--waivers", path, "--now", "2026-11-30", "--fail-on", "high"
    )
    assert code == 0 and data["summary"]["by_result"]["waived"] == 1
    code, data = findings(
        ws, "--waivers", path, "--now", "2026-12-01", "--fail-on", "high"
    )
    assert code == 7
    failing = [f for f in data["findings"] if f["result"] == "fail"]
    assert failing[0]["waiver_expired"] == "2026-11-30"
    assert [(u["why"]) for u in data["unused_waivers"]] == ["expired"]


def test_a_waiver_changes_only_a_fail(ws):
    path = waiver_file(
        ws / "w.yaml", resource="arn:aws:rds:eu-west-1:111111111111:db:db-audit"
    )
    code, data = findings(ws, "--waivers", path, "--now", NOW, "--fail-on", "high")
    assert code == 7
    assert data["summary"]["by_result"]["waived"] == 0
    assert [u["why"] for u in data["unused_waivers"]] == ["no match"]


def test_a_waiver_for_an_unknown_policy_is_listed_unused(ws):
    path = waiver_file(ws / "w.yaml", policy="NOPE-001")
    code, data = findings(ws, "--waivers", path, "--now", NOW)
    assert [u["why"] for u in data["unused_waivers"]] == ["unknown policy"]


def test_the_waiver_with_the_latest_expiry_wins_and_the_other_is_superseded(ws):
    a = waiver_file(ws / "a.yaml", expires="2026-12-31")
    b = waiver_file(ws / "b.yaml", expires="2027-01-31")
    code, data = findings(ws, "--waivers", a, "--now", NOW)
    # one --waivers file only: put both entries in one file
    spec = yaml.safe_load(a.read_text())
    spec["spec"]["waivers"].append(yaml.safe_load(b.read_text())["spec"]["waivers"][0])
    a.write_text(yaml.safe_dump(spec))
    code, data = findings(ws, "--waivers", a, "--now", NOW)
    waived = [f for f in data["findings"] if f["result"] == "waived"]
    assert waived[0]["waiver"]["expires"] == "2027-01-31"
    assert [u["why"] for u in data["unused_waivers"]] == ["superseded"]


@pytest.mark.xfail(
    strict=True,
    reason="a waivers file inside the policy folder is refused by policy check "
    "(loader.load validates it as a policy file with no date)",
)
def test_a_waivers_file_inside_the_policy_folder_is_not_a_problem(ws):
    shutil_target = ws / ".inventag" / "policies" / "waivers.yaml"
    shutil_target.write_text((ws / "waivers" / "waivers.yaml").read_text())
    code, out, err = run(["check", "--snapshot", "s1.json", "--now", NOW])
    assert code == 0, err


def test_the_guide_says_the_waivers_in_the_folder_case_is_not_verified():
    guide = " ".join(text_of(GUIDE).split())
    assert (
        "Not verified against a run: a waivers file inside the folder given to `--policies`."
        in guide
    )


# ---------------------------------------------------------------- guide: baseline
def test_the_baseline_example_output_is_the_guides_and_exit_7(ws):
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--baseline",
            "s0.json",
            "--policies",
            "drift.yaml",
            "--now",
            NOW,
            "--fail-on",
            "medium",
        ]
    )
    assert code == 7, err
    assert out.rstrip("\n") in output_blocks(text_of(GUIDE))
    assert "fn-eu" not in out  # a listing that failed: not reported as removed


def test_without_a_baseline_the_policy_is_listed_not_evaluated(ws):
    out_dir = ws / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--policies",
            "drift.yaml",
            "--now",
            NOW,
            "--format",
            "json",
            "--output-directory",
            out_dir,
        ]
    )
    assert code == 0, err
    data = json.loads(next(out_dir.glob("*.json")).read_text())
    assert data["not_evaluated_policies"] == [
        {"policy": "DRF-001", "reason": "no_baseline"}
    ]
    assert data["findings"] == []


def test_a_baseline_entry_inside_and_is_refused(tmp_path):
    (tmp_path / "p.yaml").write_text(
        policy_text(
            [{"and": [{"type": "baseline", "change": ["added"]}]}], pid="AB-001"
        )
    )
    code, out, err = run(["validate", tmp_path])
    assert code == 1
    assert "a baseline check must be a top-level entry of check" in err


# ------------------------------------------------------------- guide: sets, lock
def test_a_set_names_policies_includes_a_set_and_overrides_a_severity(ws):
    folder = ws / "team"
    folder.mkdir()
    (folder / "rds.yaml").write_text(block(text_of(GUIDE), "id: RDS-001"))
    set_text = block(text_of(GUIDE), "kind: policy-set")
    (folder / "set.yaml").write_text(set_text)
    (folder / "naming.yaml").write_text(
        (ROOT / "inventag/policy/builtin/naming/set.yaml").read_text()
    )
    for f in (ROOT / "inventag/policy/builtin/naming").glob("name-*.yaml"):
        (folder / f.name).write_text(f.read_text())
    code, out, err = run(["list", "--policies", folder, "--set", "team-baseline"])
    assert code == 0, err
    ids = [line.split()[0] for line in out.splitlines()[1:]]
    assert sorted(ids) == ["NAME-001", "NAME-002", "RDS-001"]
    assert re.search(r"NAME-001\s+medium", out)
    out_dir = ws / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--policies",
            folder,
            "--set",
            "team-baseline",
            "--now",
            NOW,
            "--format",
            "json",
            "--output-directory",
            out_dir,
        ]
    )
    data = json.loads(next(out_dir.glob("*.json")).read_text())
    by = {p["id"]: p for p in data["policies"]}
    assert by["NAME-001"]["severity"] == "medium"
    assert by["NAME-001"]["severity_overridden_by"].startswith("team-baseline")


def test_a_cycle_of_include_is_an_error_and_a_policy_reached_twice_runs_once(tmp_path):
    (tmp_path / "a.yaml").write_text(
        "format_version: 1\nkind: policy-set\nname: a\nspec: {include: [b]}\n"
    )
    (tmp_path / "b.yaml").write_text(
        "format_version: 1\nkind: policy-set\nname: b\nspec: {include: [a]}\n"
    )
    code, out, err = run(["validate", tmp_path])
    assert code == 1 and "include each other" in err
    twice = tmp_path / "twice"
    twice.mkdir()
    (twice / "p.yaml").write_text(
        policy_text([{"type": "value", "key": "x", "value": 1}], pid="AB-001")
    )
    for n in ("s1", "s2"):
        (twice / f"{n}.yaml").write_text(
            f"format_version: 1\nkind: policy-set\nname: {n}\nspec: {{policies: [ab-001]}}\n"
        )
    code, out, err = run(["list", "--policies", twice])
    assert code == 0, err
    assert out.count("AB-001") == 1


def test_lock_writes_a_json_file_that_leaves_out_tests(ws):
    code, out, err = run(["lock", ".inventag/policies"])
    assert code == 0, err
    data = json.loads((ws / ".inventag/policies/policy.lock").read_text())
    assert data["kind"] == "lock" and data["format_version"] == 1
    assert list(data["files"]) == ["rds-encrypted.yaml"]
    assert re.fullmatch(r"[0-9a-f]{64}", data["files"]["rds-encrypted.yaml"])


@pytest.mark.xfail(
    strict=True,
    reason="policy lock --check calls inventag.policy.lock.check, which does not exist",
)
def test_lock_check_exits_1_when_a_listed_file_changed(ws):
    run(["lock", ".inventag/policies"])
    assert run(["lock", "--check", ".inventag/policies"])[0] == 0
    with open(ws / ".inventag/policies/rds-encrypted.yaml", "a") as handle:
        handle.write("# edit\n")
    assert run(["lock", "--check", ".inventag/policies"])[0] == 1


@pytest.mark.xfail(
    strict=True,
    reason="policy check --locked calls inventag.policy.lock.check, which does not exist",
)
def test_locked_check_refuses_a_changed_file(ws):
    run(["lock", ".inventag/policies"])
    with open(ws / ".inventag/policies/rds-encrypted.yaml", "a") as handle:
        handle.write("# edit\n")
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--policies",
            ".inventag/policies",
            "--locked",
            "--now",
            NOW,
        ]
    )
    assert code == 1


def test_the_guide_says_lock_check_and_locked_are_not_verified():
    guide = " ".join(text_of(GUIDE).split())
    assert "Not verified against a run: `inventag policy lock --check`" in guide


# ---------------------------------------------------------------- guide: outputs
def test_formats_write_these_files_named_by_the_snapshot_timestamp(ws):
    out_dir = ws / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--now",
            NOW,
            "--format",
            "json,sarif,junit,markdown",
            "--output-directory",
            out_dir,
        ]
    )
    assert code == 0, err
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "policy_findings_20261120_000000.json",
        "policy_findings_20261120_000000.md",
        "policy_findings_20261120_000000.sarif",
        "policy_findings_20261120_000000.xml",
    ]
    guide = text_of(GUIDE)
    for name in ("json", "sarif", "xml", "md"):
        assert f"`policy_findings_<timestamp>.{name}`" in guide


def test_the_same_inputs_give_the_same_bytes(ws):
    first, second = ws / "o1", ws / "o2"
    for target in (first, second):
        run(
            [
                "check",
                "--snapshot",
                "s1.json",
                "--now",
                NOW,
                "--format",
                "json,sarif,junit,markdown",
                "--output-directory",
                target,
            ]
        )
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()


def test_files_are_written_for_0_7_and_8_and_not_for_1_and_2(ws):
    cases = [
        ([], 0, True),
        (["--fail-on", "high"], 7, True),
        (["--set", "naming", "--fail-on-not-evaluated"], 8, True),
        (["--now", "yesterday"], 2, False),
    ]
    for extra, expected, written in cases:
        out_dir = ws / f"o{expected}"
        args = [
            "check",
            "--snapshot",
            "s1.json",
            "--format",
            "json",
            "--output-directory",
            out_dir,
        ]
        if "--now" not in extra:
            args += ["--now", NOW]
        code, out, err = run(args + extra)
        assert code == expected, (extra, err)
        assert (
            out_dir.exists()
            and any(out_dir.iterdir()) == written
            or (not written and not out_dir.exists())
        ), extra
    out_dir = ws / "o1"
    bad = ws / "bad"
    bad.mkdir()
    (bad / "p.yaml").write_text("kind: nope\n")
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--policies",
            bad,
            "--format",
            "json",
            "--output-directory",
            out_dir,
        ]
    )
    assert code == 1
    assert not out_dir.exists() or not any(out_dir.iterdir())


def test_the_packaged_schema_and_its_urn_id():
    schema = findings_schema()
    assert schema["$id"] == "urn:inventag:schema:policy-findings:1"
    assert (ROOT / "inventag/policy/outputs/schemas/policy-findings-1.json").is_file()
    code, out, err = run(["schema", "--json"])
    assert code == 0
    assert json.loads(out)["$id"] == "urn:inventag:policy-file:1"


def test_a_findings_file_validates_against_the_packaged_schema(ws):
    import jsonschema

    out_dir = ws / "o"
    run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--now",
            NOW,
            "--format",
            "json",
            "--output-directory",
            out_dir,
        ]
    )
    data = json.loads(next(out_dir.glob("*.json")).read_text())
    jsonschema.validate(data, findings_schema())


def test_the_findings_file_has_the_keys_the_reference_lists(ws):
    out_dir = ws / "o"
    run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--now",
            NOW,
            "--format",
            "json",
            "--output-directory",
            out_dir,
        ]
    )
    data = json.loads(next(out_dir.glob("*.json")).read_text())
    assert list(data) == sorted(data)
    listed = re.search(
        r"top-level keys, sorted:\s+(.*?)\.", " ".join(text_of(FILES).split())
    )
    assert listed
    assert re.findall(r"`(\w+)`", listed.group(1)) == list(data)


def test_findings_list_fail_waived_not_evaluated_and_count_pass(ws):
    code, data = findings(ws, "--now", NOW)
    assert {f["result"] for f in data["findings"]} <= {
        "fail",
        "waived",
        "not_evaluated",
    }
    assert data["summary"]["by_result"]["pass"] == 1


def test_show_values_adds_the_value_to_text_and_json_and_never_to_sarif_or_junit(ws):
    out_dir = ws / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--now",
            NOW,
            "--show-values",
            "--format",
            "text,json,sarif,junit",
            "--output-directory",
            out_dir,
        ]
    )
    assert code == 0
    assert "(value: false)" in out
    shown = (
        "  FAIL arn:aws:rds:eu-west-1:111111111111:db:db-orders\n"
        "    RDS-001: condition not met: raw_data.StorageEncrypted\n"
        "    - condition not met: raw_data.StorageEncrypted (value: false)"
    )
    assert shown in out
    assert shown in "\n".join(output_blocks(text_of(GUIDE)))
    detail = json.loads(next(out_dir.glob("*.json")).read_text())["findings"][0][
        "details"
    ][0]
    assert detail["value"] is False
    for suffix in ("sarif", "xml"):
        body = next(out_dir.glob(f"*.{suffix}")).read_text()
        assert "StorageEncrypted" in body or suffix == "xml"
        assert '"value"' not in body and "value: false" not in body
    code, out, err = run(["check", "--snapshot", "s1.json", "--now", NOW])
    assert "(value:" not in out
    code, data = findings(ws, "--now", NOW)
    assert "value" not in data["findings"][0]["details"][0]


def test_a_masked_value_stays_masked_with_show_values(tmp_path):
    entry = {"type": "value", "key": "raw_data.Env.API_KEY", "value": "absent"}
    path = tmp_path / "p.yaml"
    path.write_text(policy_text([entry], pid="AB-001"))
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps(snapshot([row({"Env": {"API_KEY": "***REDACTED***"}})])))
    out_dir = tmp_path / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            snap,
            "--policies",
            path,
            "--now",
            NOW,
            "--show-values",
            "--format",
            "text,json",
            "--output-directory",
            out_dir,
        ]
    )
    assert code == 0, err
    assert "***REDACTED***" in out
    assert "***REDACTED***" in next(out_dir.glob("*.json")).read_text()


def test_sarif_levels_and_junit_outcomes(tmp_path):
    folder = tmp_path / "pol"
    folder.mkdir()
    for n, severity in enumerate(model.SEVERITIES, 1):
        (folder / f"p{n}.yaml").write_text(
            policy_text(
                [{"type": "value", "key": "raw_data.Nope", "value": "x"}],
                severity=severity,
                pid=f"SV-00{n}",
                resource={"resource_types": ["Instance"]},
            )
        )
    (folder / "ne.yaml").write_text(
        policy_text(
            [{"type": "value", "key": "raw_data.Nope", "value": "x"}],
            pid="NE-001",
            resource={"resource_types": ["Queue"]},
        )
    )
    snap = tmp_path / "s.json"
    snap.write_text(
        json.dumps(
            snapshot(
                [
                    row({"A": 1}),
                    row(
                        resource_type="Queue",
                        resource_id="q",
                        arn="arn:aws:sqs:us-east-1:111111111111:q",
                        detail_level="identity",
                        raw_data=None,
                    ),
                ]
            )
        )
    )
    out_dir = tmp_path / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            snap,
            "--policies",
            folder,
            "--now",
            NOW,
            "--format",
            "sarif,junit",
            "--output-directory",
            out_dir,
        ]
    )
    assert code == 0, err
    sarif = json.loads(next(out_dir.glob("*.sarif")).read_text())
    levels = {}
    for result in sarif["runs"][0]["results"]:
        levels.setdefault(result["ruleId"], set()).add(
            (result["kind"], result["level"])
        )
    assert levels["SV-001"] == {("fail", "note")}  # info
    assert levels["SV-002"] == {("fail", "note")}  # low
    assert levels["SV-003"] == {("fail", "warning")}  # medium
    assert levels["SV-004"] == {("fail", "error")}  # high
    assert levels["SV-005"] == {("fail", "error")}  # critical
    assert levels["NE-001"] == {("review", "none")}
    rules = sarif["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 6
    suite = ET.fromstring(next(out_dir.glob("*.xml")).read_text())
    suites = suite.findall("testsuite") if suite.tag == "testsuites" else [suite]
    assert len(suites) == 6  # one per policy file
    cases = {c.get("name", ""): c for s in suites for c in s.findall("testcase")}
    failing = [c for c in cases.values() if c.find("failure") is not None]
    skipped = [c for c in cases.values() if c.find("skipped") is not None]
    assert len(failing) == 5 and len(skipped) == 1


# ---------------------------------------------------------------- guide: exit
EXPECTED_SENTENCES = [
    ([], 0, "Exit code 0: findings are reported; no threshold was set."),
    (
        ["--fail-on", "critical"],
        0,
        "Exit code 0: nothing failed at severity critical or higher.",
    ),
    (["--fail-on-not-evaluated"], 0, "Exit code 0: everything could be evaluated."),
    (
        ["--fail-on", "critical", "--fail-on-not-evaluated"],
        0,
        "Exit code 0: nothing failed at severity critical or higher. "
        "Exit code 0: everything could be evaluated.",
    ),
    (
        ["--fail-on", "high"],
        7,
        "Exit code 7: at least one finding failed at severity high or higher.",
    ),
]


@pytest.mark.parametrize("extra, code_expected, sentence", EXPECTED_SENTENCES)
def test_the_exit_sentences_are_the_ones_the_guide_lists(
    ws, extra, code_expected, sentence
):
    for fmt in ("text", "markdown"):
        out_dir = ws / f"o-{fmt}"
        code, out, err = run(
            [
                "check",
                "--snapshot",
                "s1.json",
                "--now",
                NOW,
                "--format",
                fmt,
                "--output-directory",
                out_dir,
                *extra,
            ]
        )
        assert code == code_expected, err
        if fmt == "text":
            last = out.rstrip("\n").splitlines()[-1]
        else:
            last = next(out_dir.glob("*.md")).read_text().rstrip("\n").splitlines()[-1]
        assert last == sentence
    guide = text_of(GUIDE)
    generic = re.sub(r"severity (critical|high)", "severity S", sentence)
    for part in re.split(r"(?<=\.) ", generic):
        assert part in guide, part


def test_exit_8_wins_over_7_and_waived_and_pass_never_change_the_code(ws):
    args = [
        "check",
        "--snapshot",
        "s1.json",
        "--set",
        "naming",
        "--now",
        NOW,
        "--fail-on",
        "low",
    ]
    assert run(args)[0] == 7
    code, out, err = run(args + ["--fail-on-not-evaluated"])
    assert code == 8
    assert (
        out.rstrip("\n").splitlines()[-1]
        == "Exit code 8: some checks could not be evaluated."
    )
    guide = text_of(GUIDE)
    assert "`Exit code 8: some checks could not be evaluated.`" in guide
    assert (
        "`Exit code 7: at least one finding failed at severity S or higher.`" in guide
    )


def test_a_unit_not_read_alone_gives_exit_8(ws):
    code, out, err = run(
        [
            "check",
            "--snapshot",
            "s1.json",
            "--policies",
            "drift.yaml",
            "--now",
            NOW,
            "--fail-on-not-evaluated",
        ]
    )
    assert code == 8


def test_a_scan_has_no_option_for_exit_8():
    import importlib
    import sys

    cli_main = importlib.import_module("inventag.cli.main")

    old = sys.argv
    sys.argv = ["inventag", "--policy", "x", "--policy-fail-on-not-evaluated"]
    try:
        with pytest.raises(SystemExit) as stop:
            cli_main.main()
    finally:
        sys.argv = old
    assert stop.value.code == 2


# ---------------------------------------------------------- shipped sets (page)
def parse_policy_rows(page_text, section):
    """{id: (name, severity)} from the table that follows ``## section``."""
    start = page_text.index(f"## `{section}`")
    nxt = page_text.find("\n## ", start + 5)
    body = page_text[start : nxt if nxt != -1 else None]
    found = {}
    for line in body.splitlines():
        m = re.match(r"\| `([A-Z]+-\d+)` `([a-z0-9-]+)` \| (\w+) \|", line)
        if m:
            found[m.group(1)] = (m.group(2), m.group(3))
    return found


@pytest.mark.parametrize(
    "set_name",
    [
        "tagging-standard",
        "region-allowlist",
        "naming",
        "encryption-at-rest",
        "public-exposure",
    ],
)
def test_the_set_tables_name_the_ids_names_and_severities_of_the_files(set_name):
    policies = builtin.load_set(set_name)
    expected = {p.id: (p.name, p.severity) for p in policies}
    assert parse_policy_rows(text_of(SETS), set_name) == expected


def test_the_finops_set_table_names_the_six_policies_at_severity_low():
    policies = builtin.load_set("finops-checks")
    assert sorted(p.id for p in policies) == [f"FIN-00{i}" for i in range(1, 7)]
    assert {p.severity for p in policies} == {"low"}
    guide = text_of(GUIDE)
    for p in policies:
        assert f"| `{p.id}` |" in guide


def test_the_list_shipped_output_is_the_pages(ws):
    code, out, err = run(["list", "--shipped"])
    assert code == 0, err
    assert out.rstrip("\n") in output_blocks(text_of(SETS))
    assert set(builtin.SET_NAMES) == {
        "encryption-at-rest",
        "finops-checks",
        "naming",
        "public-exposure",
        "region-allowlist",
        "tagging-standard",
    }


def test_every_shipped_policy_has_fixtures():
    for set_name in builtin.SET_NAMES:
        folder = builtin.BUILTIN_DIR / set_name / "tests"
        for p in builtin.load_set(set_name):
            assert list((folder / p.name).glob("*.yaml")), (set_name, p.name)


def test_a_local_set_wins_over_a_shipped_set_of_the_same_name(tmp_path):
    (tmp_path / "p.yaml").write_text(
        policy_text([{"type": "value", "key": "x", "value": 1}], pid="LOC-001")
    )
    (tmp_path / "s.yaml").write_text(
        "format_version: 1\nkind: policy-set\nname: naming\nspec: {policies: [loc-001]}\n"
    )
    code, out, err = run(["list", "--policies", tmp_path, "--set", "naming"])
    assert code == 0, err
    assert [line.split()[0] for line in out.splitlines()[1:]] == ["LOC-001"]


def test_the_region_and_tag_sets_keep_their_starting_point_comment():
    for set_name, fixed in (
        (
            "tagging-standard",
            "A starting point: copy the set and change the keys and values to your own conventions.",
        ),
        (
            "region-allowlist",
            "A starting point: copy the set and list the regions your organisation uses.",
        ),
    ):
        files = list((builtin.BUILTIN_DIR / set_name).glob("*-0*.yaml"))
        assert files and all(fixed in f.read_text() for f in files)
        assert fixed in " ".join(text_of(SETS).split())


def test_the_region_policy_lists_the_three_regions_and_allows_global():
    entry = builtin.load_set("region-allowlist")[0].check[0]
    assert entry["regions"] == ["ap-southeast-1", "eu-west-1", "us-east-1"]
    assert entry["allow_global"] is True


def test_the_tag_environment_values_on_the_page_are_the_files():
    policy = next(p for p in builtin.load_set("tagging-standard") if p.id == "TAG-002")
    values = policy.check[0]["keys"][0]["allowed_values"]
    assert values == ["prod", "staging", "dev", "test", "sandbox"]
    assert "`prod`, `staging`, `dev`, `test`, `sandbox`" in text_of(SETS)


def test_the_not_shipped_keys_named_on_the_page_are_not_read_by_a_shipped_policy():
    read = set()
    for set_name in builtin.SET_NAMES:
        for p in builtin.load_set(set_name):
            read.add(
                json.dumps([list(p.require), list(p.check), p.resource], default=str)
            )
    blob = " ".join(read)
    page = text_of(SETS)
    for key in (
        "ServerSideEncryptionConfiguration",
        "PublicAccessBlockConfiguration",
        "KmsMasterKeyId",
        "SSEDescription",
    ):
        assert key not in blob
    for key in (
        "ServerSideEncryptionConfiguration",
        "KmsMasterKeyId",
        "SSEDescription",
        "PublicAccessBlockConfiguration",
    ):
        assert key in page


@pytest.mark.parametrize(
    "set_name",
    [
        "tagging-standard",
        "region-allowlist",
        "naming",
        pytest.param(
            "finops-checks",
            marks=pytest.mark.xfail(
                strict=True,
                reason="fixtures use expect_units fields (reason, outcome) that the validator refuses",
            ),
        ),
        pytest.param(
            "encryption-at-rest", marks=pytest.mark.xfail(strict=True, reason="same")
        ),
        pytest.param(
            "public-exposure", marks=pytest.mark.xfail(strict=True, reason="same")
        ),
    ],
)
def test_inventag_policy_test_runs_the_fixtures_of_the_shipped_sets(set_name):
    code, out, err = run(["test", builtin.BUILTIN_DIR / set_name])
    assert code == 0, err + out


def test_the_sets_page_says_which_three_sets_are_not_verified():
    page = " ".join(text_of(SETS).split())
    assert "`finops-checks`, `encryption-at-rest` and `public-exposure`" in page
    assert "unknown field 'reason'" in page


# ------------------------------------------------------------ finops promise
def test_the_golden_file_of_the_promise_holds_304_cases():
    from tests.unit.finops import golden_cases

    golden = json.loads(
        (ROOT / "tests/unit/finops/golden/checks-v143.json").read_text()
    )
    assert len(golden_cases.cases()) == len(golden) == 304
    assert "holds 304 cases" in " ".join(text_of(GUIDE).split())


def test_policy_check_can_differ_from_the_sheet(tmp_path):
    """The case the guide names: a v2 load balancer named by a target group,
    with the classic ``elb`` listing failed in the same account and region."""
    from inventag.finops import checks
    from tests.unit.finops import golden_cases as g

    rows = [g.v2("web"), g.group("tg", [g.LB2])]
    units = [g.unit("elb")]
    sheet = checks.run_checks(rows, units, g.T0)
    assert not [f for f in sheet["findings"] if f["resource"] == "web"]
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps(snapshot(rows, units)))
    out_dir = tmp_path / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            snap,
            "--set",
            "finops-checks",
            "--now",
            NOW,
            "--format",
            "json",
            "--output-directory",
            out_dir,
        ]
    )
    assert code == 0, err
    data = json.loads(next(out_dir.glob("*.json")).read_text())
    lb = [
        f for f in data["findings"] if f["resource"].endswith("loadbalancer/app/web/1")
    ]
    assert [(f["policy"], f["result"], f["reason"]) for f in lb] == [
        ("FIN-005", "not_evaluated", "listing_not_read")
    ]


# ---------------------------------------------------------------- reference page
def test_every_schema_field_is_on_the_reference_page():
    page = text_of(FILES)
    for field in cli.FIELD_HELP:
        assert f"`{field}`" in page, field


def test_the_code_constants_are_all_on_the_reference_page():
    page = text_of(FILES)
    for group in (
        model.SEVERITIES,
        model.REASONS,
        model.CHECK_TYPES,
        model.OPERATORS,
        model.VALUE_TYPES,
        model.SPECIAL_VALUES,
        model.KINDS,
        model.FORBIDDEN_FIELDS,
    ):
        for word in group:
            assert f"`{word}`" in page, word
    for name in model.PLACEHOLDERS:
        assert "{" + name + "}" in page, name
    for result in ("pass", "fail", "waived", "not_evaluated", "out_of_scope"):
        assert f"`{result}`" in page


def test_the_limits_on_the_reference_page_are_the_codes():
    page = " ".join(text_of(FILES).split())
    limits = model.LIMITS
    assert limits.file_bytes == 256 * 1024 and "| File size | 256 KiB |" in page
    assert f"| Policies in one run | {limits.policies_per_run} |" in page
    assert f"| Entries in `check` | {limits.checks_per_policy} |" in page
    assert (
        f"| Entries in one `and`, `or` or `not` | {limits.entries_per_group} |" in page
    )
    assert f"| Nesting depth of `and`, `or`, `not` | {limits.nesting_depth} |" in page
    assert f"| Length of a `key` | {limits.key_length} characters |" in page
    assert f"| Length of a pattern | {limits.pattern_length} characters |" in page
    assert f"{limits.found_string_length} characters (longer" in page
    assert f"| Length of `message` | {limits.message_length} characters |" in page
    assert f"| Entries in `references` | {limits.references} |" in page
    assert (
        f"| Related rows per account and region | {limits.related_rows_per_place} |"
        in page
    )
    assert f"| Days a waiver may run ahead | {limits.waiver_days_ahead} |" in page


def test_the_limits_are_enforced_as_the_page_says(tmp_path):
    (tmp_path / "big").mkdir()
    (tmp_path / "big" / "b.yaml").write_text("# " + "x" * (257 * 1024) + "\n")
    code, out, err = run(["validate", tmp_path / "big"])
    assert code == 1 and "larger than 256 KiB" in err
    (tmp_path / "al").mkdir()
    (tmp_path / "al" / "a.yaml").write_text(
        "format_version: 1\nkind: policy\nname: a\nx: &a 1\nspec:\n  id: AL-001\n"
        "  severity: low\n  check: [{type: value, key: foo, value: *a}]\n"
    )
    code, out, err = run(["validate", tmp_path / "al"])
    assert code == 1 and "YAML aliases are not allowed" in err
    (tmp_path / "dup").mkdir()
    for n in ("a", "b"):
        (tmp_path / "dup" / f"{n}.yaml").write_text(
            policy_text(
                [{"type": "value", "key": "foo", "value": 1}], pid="DUP-001"
            ).replace("dup-001", n)
        )
    code, out, err = run(["validate", tmp_path / "dup"])
    assert code == 1 and "is also used in" in err


@pytest.mark.parametrize(
    "bad, problem",
    [
        ("21 checks", "at most 20 checks"),
    ],
)
def test_twenty_one_checks_are_refused(tmp_path, bad, problem):
    check = [{"type": "value", "key": "raw_data.A", "value": i} for i in range(21)]
    (tmp_path / "p.yaml").write_text(policy_text(check, pid="AB-001"))
    code, out, err = run(["validate", tmp_path])
    assert code == 1 and problem in err


def test_nesting_deeper_than_five_and_a_bad_message_placeholder_are_refused(tmp_path):
    entry = {"type": "value", "key": "raw_data.A", "value": 1}
    for _ in range(6):
        entry = {"and": [entry]}
    (tmp_path / "p.yaml").write_text(policy_text([entry], pid="AB-001"))
    code, out, err = run(["validate", tmp_path])
    assert code == 1 and "nested more than 5 levels" in err
    spec = yaml.safe_load(
        policy_text([{"type": "value", "key": "a", "value": 1}], pid="AB-002")
    )
    spec["spec"]["message"] = "bad {nope}"
    (tmp_path / "p.yaml").write_text(yaml.safe_dump(spec))
    code, out, err = run(["validate", tmp_path])
    assert code == 1 and "unknown placeholder" in err


def test_id_pattern_name_pattern_and_severity_are_as_the_page_says(tmp_path):
    for pid, ok in (
        ("RDS-001", True),
        ("A-001", False),
        ("ABCDEFGHI-001", False),
        ("AB-01", False),
        ("AB-123456", False),
        ("AB-12345", True),
        ("ABCDEFGH-123", True),
    ):
        (tmp_path / "p.yaml").write_text(
            policy_text([{"type": "value", "key": "a", "value": 1}], pid=pid)
        )
        assert (run(["validate", tmp_path])[0] == 0) is ok, pid
    (tmp_path / "p.yaml").write_text(
        policy_text(
            [{"type": "value", "key": "a", "value": 1}], severity="urgent", pid="AB-001"
        )
    )
    assert run(["validate", tmp_path])[0] == 1


# the evidence for each operator, special word and value_type row of the page
OPERATOR_CASES = [
    # (doc text on the page, entry, raw_data, expected result)
    ("`abc`, `abc`: true", {"op": "eq", "value": "abc"}, {"A": "abc"}, "pass"),
    ("`abc`, `xyz`: true", {"op": "ne", "value": "xyz"}, {"A": "abc"}, "pass"),
    ("`5`, `3` with `gt`: true", {"op": "gt", "value": 3}, {"A": 5}, "pass"),
    (None, {"op": "ge", "value": 5}, {"A": 5}, "pass"),
    (None, {"op": "lt", "value": 5}, {"A": 5}, "fail"),
    (None, {"op": "le", "value": 5}, {"A": 5}, "pass"),
    ("`a`, `[a, b]`: true", {"op": "in", "value": ["a", "b"]}, {"A": "a"}, "pass"),
    ("`c`, `[a, b]`: true", {"op": "not-in", "value": ["a", "b"]}, {"A": "c"}, "pass"),
    (
        "`hello`, `ell`: true",
        {"op": "contains", "value": "ell"},
        {"A": "hello"},
        "pass",
    ),
    (None, {"op": "contains", "value": 2}, {"A": [1, 2]}, "pass"),
    (
        "`web-1`, `web-*`: true",
        {"op": "glob", "value": "web-*"},
        {"A": "web-1"},
        "pass",
    ),
    (None, {"op": "glob", "value": "web-*"}, {"A": "Web-1"}, "fail"),
    ("`Prod`, `prod`: true", {"op": "regex", "value": "prod"}, {"A": "Prod"}, "pass"),
    (None, {"op": "regex", "value": "prod"}, {"A": "xprod"}, "fail"),
    (None, {"op": "regex", "value": "prod"}, {"A": "prodx"}, "pass"),
    (
        "`Prod`, `prod`: false",
        {"op": "regex-case", "value": "prod"},
        {"A": "Prod"},
        "fail",
    ),
    # a text never equals a number
    (None, {"value": 5}, {"A": "5"}, "fail"),
    (None, {"value": True}, {"A": True}, "pass"),
    # special words
    (None, {"value": "absent"}, {}, "pass"),
    (None, {"value": "absent"}, {"A": None}, "pass"),
    (None, {"value": "present"}, {"A": 1}, "pass"),
    (None, {"value": "present"}, {"A": None}, "fail"),
    (None, {"value": "empty"}, {"A": []}, "pass"),
    (None, {"value": "empty"}, {"A": ""}, "pass"),
    (None, {"value": "empty"}, {}, "pass"),
    (None, {"value": "empty"}, {"A": "a"}, "fail"),
    (None, {"value": "not-null"}, {"A": 0}, "pass"),
    (None, {"value": "absent", "value_type": "text"}, {"A": "absent"}, "pass"),
    (None, {"value": "absent"}, {"A": "absent"}, "fail"),
    # an absent key
    (None, {"value": "x"}, {}, "fail"),
    (None, {"op": "ne", "value": "x"}, {}, "pass"),
    (None, {"op": "not-in", "value": ["x"]}, {}, "pass"),
    # value_type
    (None, {"value": 5, "value_type": "integer"}, {"A": "5"}, "pass"),
    (None, {"value": 3, "value_type": "size"}, {"A": [1, 2, 3]}, "pass"),
    (None, {"value": 3, "value_type": "size"}, {"A": "abc"}, "pass"),
    (None, {"value": "prod", "value_type": "normalize"}, {"A": " Prod "}, "pass"),
    (None, {"op": "ge", "value": 10, "value_type": "age"}, {"A": "2026-11-10"}, "pass"),
    (
        None,
        {"op": "gt", "value": 0.4, "value_type": "age"},
        {"A": "2026-11-19T12:00:00+00:00"},
        "pass",
    ),
    (
        None,
        {"op": "lt", "value": 0.6, "value_type": "age"},
        {"A": "2026-11-19T12:00:00+00:00"},
        "pass",
    ),
    (None, {"value": 10, "value_type": "expiration"}, {"A": "2026-11-30"}, "pass"),
    (
        None,
        {"op": "ge", "value": 1, "value_type": "age"},
        {"A": 1795046400},
        "pass",
    ),  # epoch seconds: 2026-11-19
    (
        None,
        {"op": "ge", "value": 10, "value_type": "age"},
        {"A": "2026-11-10T00:00:00"},
        "pass",
    ),  # no zone: UTC
]


@pytest.mark.parametrize("doc, entry, raw, expected", OPERATOR_CASES)
def test_each_operator_special_word_and_value_type_does_what_the_page_says(
    tmp_path, doc, entry, raw, expected
):
    check = {"type": "value", "key": "raw_data.A", **entry}
    assert judge(tmp_path, check, [row(raw)])[0] == expected
    if doc:
        assert doc in text_of(FILES)


def test_the_tag_forms_read_the_tag_and_tag_keys_are_case_sensitive(tmp_path):
    assert (
        judge(tmp_path, {"tag:Owner": "present"}, [row(tags={"Owner": "a"})])[0]
        == "pass"
    )
    assert (
        judge(tmp_path, {"tag:Owner": "present"}, [row(tags={"owner": "a"})])[0]
        == "fail"
    )
    assert (
        judge(
            tmp_path,
            {"type": "value", "key": "tags.Owner", "value": "a"},
            [row(tags={"Owner": "a"})],
        )[0]
        == "pass"
    )
    assert (
        judge(
            tmp_path, {"tag:Environment": "prod"}, [row(tags={"Environment": "prod"})]
        )[0]
        == "pass"
    )


def test_three_valued_logic_follows_kleene(tmp_path):
    unknown = {"type": "value", "key": "raw_data.A", "op": "gt", "value": 1}
    true = {"type": "value", "key": "raw_data.B", "value": 1}
    false = {"type": "value", "key": "raw_data.B", "value": 2}
    raw = [row({"A": "text", "B": 1})]
    assert judge(tmp_path, {"and": [false, unknown]}, raw)[0] == "fail"
    assert judge(tmp_path, {"or": [true, unknown]}, raw)[0] == "pass"
    assert judge(tmp_path, {"not": [unknown]}, raw)[0] == "not_evaluated"
    assert judge(tmp_path, {"not": [true, true]}, raw)[0] == "fail"
    assert judge(tmp_path, {"not": [true, false]}, raw)[0] == "pass"
    assert judge(tmp_path, {"and": [true, unknown]}, raw)[0] == "not_evaluated"


def test_the_verdict_of_check_is_the_and_of_its_entries(tmp_path):
    entries = [
        {"type": "value", "key": "raw_data.B", "value": 1},
        {"type": "value", "key": "raw_data.B", "value": 2},
    ]
    assert judge(tmp_path, entries, [row({"B": 1})])[0] == "fail"


def test_resource_block_tests_and_scope(tmp_path):
    path = tmp_path / "p.yaml"
    rows = [
        row({"A": 1}),
        row(
            service="S3",
            resource_type="Bucket",
            resource_id="b",
            arn="arn:aws:s3:::b",
            region="global",
        ),
        row(
            resource_id="i-2",
            arn="arn:aws:ec2:eu-west-1:222222222222:instance/i-2",
            region="eu-west-1",
            source_account_id="222222222222",
        ),
    ]

    def selected(block):
        path.write_text(
            policy_text(
                [{"type": "value", "key": "raw_data.A", "value": "absent"}],
                pid="AB-001",
                resource=block,
            )
        )
        loaded = loader.load([path])
        result = engine.evaluate(
            snapshot(rows), loaded.policies, now=NOW, include_pass=True
        )
        return result["summary"]["by_result"]["out_of_scope"]

    assert selected({"services": ["ec2"]}) == 1  # not case-sensitive
    assert selected({"services": ["EC2"], "resource_types": ["instance"]}) == 1
    assert selected({"services": ["EC2"], "exclude_resource_types": ["Instance"]}) == 3
    assert selected({"regions": ["us-east-1"]}) == 2  # global must be named
    assert selected({"regions": ["us-east-1", "global"]}) == 1
    assert selected({"accounts": ["222222222222"]}) == 2
    assert selected({"filters": [{"tag:Owner": "present"}]}) == 3


def test_required_tags_options(tmp_path):
    keys = [{"key": "Environment", "allowed_values": ["prod"]}]
    entry = {"type": "required-tags", "keys": keys}
    assert judge(tmp_path, entry, [row(tags={"Environment": "PROD"})])[0] == "pass"
    keys[0]["case_sensitive"] = True
    assert judge(tmp_path, entry, [row(tags={"Environment": "PROD"})])[0] == "fail"
    assert judge(tmp_path, entry, [row(tags={})])[0] == "fail"
    pattern = {"type": "required-tags", "keys": [{"key": "Id", "pattern": "[0-9]+"}]}
    assert judge(tmp_path, pattern, [row(tags={"Id": "123"})])[0] == "pass"
    assert judge(tmp_path, pattern, [row(tags={"Id": "123x"})])[0] == "fail"
    assert judge(tmp_path, pattern, [row(tags={"id": "123"})])[0] == "fail"


def test_required_tags_policy_options_need_policy_and_keys_xor_policy(tmp_path):
    for entry in (
        {"type": "required-tags", "keys": [{"key": "A"}], "missing_only": True},
        {"type": "required-tags"},
        {
            "type": "required-tags",
            "keys": [{"key": "A"}],
            "policy": "finops-cost-allocation",
        },
    ):
        (tmp_path / "p.yaml").write_text(policy_text([entry], pid="AB-001"))
        assert run(["validate", tmp_path])[0] == 1, entry


def test_allowed_regions_and_name_pattern(tmp_path):
    regions = {"type": "allowed-regions", "regions": ["us-east-1"]}
    assert judge(tmp_path, regions, [row()])[0] == "pass"
    assert judge(tmp_path, regions, [row(region="eu-west-1")])[0] == "fail"
    assert judge(tmp_path, regions, [row(region="global")])[0] == "pass"
    no_global = {**regions, "allow_global": False}
    assert judge(tmp_path, no_global, [row(region="global")])[0] == "fail"
    pattern = {"type": "name-pattern", "pattern": "web-[0-9]"}
    assert judge(tmp_path, pattern, [row(resource_name="web-1")])[0] == "pass"
    assert (
        judge(tmp_path, pattern, [row(resource_name="web-12")])[0] == "fail"
    )  # full match
    assert (
        judge(tmp_path, pattern, [row(resource_name="Web-1")])[0] == "fail"
    )  # case-sensitive
    on_key = {"type": "name-pattern", "field": "raw_data.G", "pattern": "a"}
    assert judge(tmp_path, on_key, [row({})])[0] == "fail"  # absent field
    assert judge(tmp_path, on_key, [row(detail_level="identity")]) == (
        "not_evaluated",
        "identity_only",
    )


def test_require_makes_an_absent_key_not_evaluated_rather_than_a_verdict(tmp_path):
    entry = {"type": "value", "key": "raw_data.A", "op": "ne", "value": "x"}
    assert judge(tmp_path, entry, [row({})])[0] == "pass"
    assert judge(tmp_path, entry, [row({})], require=["raw_data.A"]) == (
        "not_evaluated",
        "field_missing",
    )


def test_related_expect_any_and_none(tmp_path):
    lb = row(
        {"Arn": "L1"}, service="ELBV2", resource_type="LoadBalancerV2", resource_id="lb"
    )
    tg = row(
        {"Arns": ["L1"]},
        service="ELBV2",
        resource_type="TargetGroup",
        resource_id="tg",
        arn="arn:aws:elasticloadbalancing:us-east-1:111111111111:targetgroup/tg/1",
    )
    related = {
        "type": "related",
        "rows": {"services": ["ELBV2"], "resource_types": ["TargetGroup"]},
        "their_key": "raw_data.Arns",
        "my_key": "raw_data.Arn",
        "listing": "elbv2",
    }
    block = {"resource_types": ["LoadBalancerV2"]}
    assert judge(tmp_path, related, [lb, tg], resource=block)[0] == "pass"
    assert (
        judge(tmp_path, {**related, "expect": "none"}, [lb, tg], resource=block)[0]
        == "fail"
    )
    assert judge(tmp_path, related, [lb], resource=block)[0] == "fail"
    no_key = copy.deepcopy(lb)
    no_key["raw_data"] = {}
    assert judge(tmp_path, related, [no_key, tg], resource=block) == (
        "not_evaluated",
        "field_missing",
    )
    unit = {
        "account": ACCOUNT,
        "service": "elbv2",
        "region": "us-east-1",
        "source": "service-api",
        "outcome": "throttled",
    }
    assert judge(tmp_path, related, [lb], units=[unit], resource=block) == (
        "not_evaluated",
        "listing_not_read",
    )
    other_account = copy.deepcopy(tg)
    other_account["source_account_id"] = "222222222222"
    assert judge(tmp_path, related, [lb, other_account], resource=block)[0] == "fail"


def test_related_refusals_are_the_pages(tmp_path):
    cases = [
        ({"type": "related"}, "related needs rows, their_key and my_key"),
        (
            {
                "type": "related",
                "rows": {},
                "their_key": "a",
                "my_key": "b",
                "expect": "some",
            },
            "expect must be any or none",
        ),
        (
            {
                "type": "related",
                "rows": {"filters": []},
                "their_key": "a",
                "my_key": "b",
            },
            "rows of a related check take no filters",
        ),
    ]
    for entry, problem in cases:
        (tmp_path / "p.yaml").write_text(policy_text([entry], pid="AB-001"))
        code, out, err = run(["validate", tmp_path])
        assert code == 1 and problem in err, entry


def test_the_policy_schema_command_prints_the_fields_and_one_field(tmp_path):
    code, out, err = run(["schema"])
    assert code == 0
    assert out.splitlines()[0].startswith("format_version")
    code, out, err = run(["schema", "severity"])
    assert code == 0 and out.startswith("severity  (spec.severity)")
    assert run(["schema", "nope"])[0] == 1


def test_the_reference_page_says_it_is_written_by_hand():
    assert "there is no generator for it" in " ".join(text_of(FILES).split())
    assert not list((ROOT / "inventag").rglob("*policy*reference*.py"))


# ------------------------------------------------- more claims of the pages
def test_policy_commands_need_no_network_and_no_credentials(ws, monkeypatch):
    import socket

    def refuse(*args, **kwargs):
        raise AssertionError("a network call was made")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_PROFILE",
        "AWS_SESSION_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    code, out, err = run(
        ["check", "--snapshot", "s1.json", "--now", NOW, "--fail-on", "high"]
    )
    assert code == 7, err


def test_now_is_a_date_and_a_time_is_refused_with_exit_2(ws):
    code, out, err = run(
        ["check", "--snapshot", "s1.json", "--now", "2026-11-20T00:00:00"]
    )
    assert code == 2 and "write YYYY-MM-DD" in err
    guide = " ".join(text_of(GUIDE).split())
    assert "`--now YYYY-MM-DD` sets the date of the run" in guide


def test_the_default_date_is_today_in_utc(ws, monkeypatch):
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    code, out, err = run(["check", "--snapshot", "s1.json"])
    assert code == 0, err
    assert f"now: {today}" in out


def test_a_fixture_with_units_not_read_must_give_expect_units(ws):
    folder = ws / ".inventag" / "policies" / "tests" / "rds-storage-encrypted"
    text = (folder / "basic.yaml").read_text()
    unit = "{account: '111111111111', service: rds, region: eu-west-1, source: service-api, outcome: denied}"
    (folder / "basic.yaml").write_text(
        text.replace("  resources:\n", f"  units_not_read: [{unit}]\n  resources:\n", 1)
    )
    code, out, err = run(["test", ".inventag/policies"])
    assert code == 1
    (folder / "basic.yaml").write_text(
        text.replace("  resources:\n", f"  units_not_read: [{unit}]\n  resources:\n", 1)
        + "  expect_units:\n    - {account: '111111111111', service: rds, region: eu-west-1}\n"
    )
    code, out, err = run(["test", ".inventag/policies"])
    assert code == 0, out + err


def test_explain_accepts_set(ws):
    code, out, err = run(
        [
            "explain",
            "NAME-001",
            "--snapshot",
            "s1.json",
            "--set",
            "naming",
            "--now",
            NOW,
        ]
    )
    assert code == 0, err


def test_listings_decide_which_failed_listings_become_units_not_read(tmp_path):
    unit = {
        "account": ACCOUNT,
        "service": "ec2",
        "region": "us-east-1",
        "source": "service-api",
        "outcome": "denied",
    }
    rows = [row({"A": 1}, service="RDS", resource_type="DBInstance")]

    def units(resource):
        path = tmp_path / "p.yaml"
        path.write_text(
            policy_text(
                [{"type": "value", "key": "raw_data.A", "value": 1}],
                pid="AB-001",
                resource=resource,
            )
        )
        loaded = loader.load([path])
        return engine.evaluate(snapshot(rows, [unit]), loaded.policies, now=NOW)[
            "not_evaluated_units"
        ]

    assert units({"services": ["RDS"]}) == []
    assert [
        u["service"] for u in units({"services": ["RDS"], "listings": ["ec2"]})
    ] == ["ec2"]


def test_the_header_and_document_rules(tmp_path):
    good = policy_text([{"type": "value", "key": "a", "value": 1}], pid="AB-001")
    two = yaml.safe_dump_all(
        [
            json.loads(good),
            {
                **json.loads(good),
                "name": "other",
                "spec": {**json.loads(good)["spec"], "id": "AB-002"},
            },
        ]
    )
    (tmp_path / "p.yaml").write_text(two)
    code, out, err = run(["list", "--policies", tmp_path])
    assert (
        code == 0 and "AB-001" in out and "AB-002" in out
    )  # several documents in one file
    for text, problem in (
        (
            good.replace('"name": "ab-001"', '"name": "Bad_Name"'),
            "must use lower-case letters, digits and hyphens",
        ),
        (good.replace('"format_version": 1', '"format_version": 2'), "must be 1"),
        (
            good.replace('"kind": "policy"', '"kind": "other"'),
            "must be one of policy, policy-set, waivers",
        ),
        (
            good.replace('"name": "ab-001",', '"name": "ab-001", "colour": 1,'),
            "unknown field 'colour'",
        ),
        (good.replace('"name": "ab-001",', ""), "name: is required"),
    ):
        (tmp_path / "p.yaml").write_text(text)
        (tmp_path / "q.yaml").unlink(missing_ok=True)
        code, out, err = run(["validate", tmp_path / "p.yaml"])
        assert code == 1 and problem in err, (problem, err)
    (tmp_path / "p.yaml").write_text(
        "format_version: 1\nkind: policy\nname: a\nname: b\nspec: {}\n"
    )
    code, out, err = run(["validate", tmp_path / "p.yaml"])
    assert code == 1 and "duplicate" in err.lower()
    long_name = "a" * 64
    (tmp_path / "p.yaml").write_text(good.replace("ab-001", long_name))
    assert run(["validate", tmp_path / "p.yaml"])[0] == 1
    (tmp_path / "p.yaml").write_text(good.replace("ab-001", "a" * 63))
    assert run(["validate", tmp_path / "p.yaml"])[0] == 0


def test_a_bad_key_a_bad_pattern_and_a_resource_filter_type_are_refused_at_load(
    tmp_path,
):
    for entry, problem in (
        ({"type": "value", "key": "raw_data[", "value": 1}, "not a valid key"),
        (
            {"type": "value", "key": "a", "op": "regex", "value": "("},
            "not a valid regular expression",
        ),
        ({"type": "value", "key": "a", "op": "in", "value": "x"}, "'in' needs a list"),
        (
            {"type": "value", "key": "a", "op": "near", "value": 1},
            "unknown operator 'near'",
        ),
        (
            {"type": "value", "key": "a", "value_type": "word", "value": 1},
            "unknown value_type 'word'",
        ),
        ({"type": "name-pattern", "pattern": "("}, "not a valid regular expression"),
        ({"type": "value", "key": "a" * 201, "value": 1}, "at most 200 characters"),
    ):
        (tmp_path / "p.yaml").write_text(policy_text([entry], pid="AB-001"))
        code, out, err = run(["validate", tmp_path])
        assert code == 1 and problem in err, (entry, err)
    (tmp_path / "p.yaml").write_text(
        policy_text(
            [{"type": "value", "key": "a", "value": 1}],
            pid="AB-001",
            resource={"filters": [{"type": "required-tags", "keys": [{"key": "A"}]}]},
        )
    )
    code, out, err = run(["validate", tmp_path])
    assert code == 1 and "filters take only type: value" in err


def test_message_placeholders_references_version_and_enabled(tmp_path):
    spec = {
        "id": "AB-001",
        "severity": "low",
        "version": 3,
        "message": "{name} in {region} ({policy}) is bad",
        "references": ["text", "https://example.test/x"],
        "resource": {"services": ["EC2"]},
        "check": [{"type": "value", "key": "raw_data.A", "value": 2}],
    }
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps(snapshot([row({"A": 1})])))
    folder = tmp_path / "p"
    folder.mkdir()
    (folder / "a.yaml").write_text(
        json.dumps({"format_version": 1, "kind": "policy", "name": "a", "spec": spec})
    )
    (folder / "b.yaml").write_text(
        json.dumps(
            {
                "format_version": 1,
                "kind": "policy",
                "name": "b",
                "spec": {**spec, "id": "AB-002", "enabled": False},
            }
        )
    )
    out_dir = tmp_path / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            snap,
            "--policies",
            folder,
            "--now",
            NOW,
            "--format",
            "json,sarif",
            "--output-directory",
            out_dir,
        ]
    )
    assert code == 0, err
    data = json.loads(next(out_dir.glob("*.json")).read_text())
    assert [f["message"] for f in data["findings"]] == [
        "i-1 in us-east-1 (AB-001) is bad"
    ]
    by = {p["id"]: p for p in data["policies"]}
    assert by["AB-001"]["version"] == 3
    assert set(by["AB-002"]["counts"].values()) == {0}  # listed, all counts 0
    sarif = json.loads(next(out_dir.glob("*.sarif")).read_text())
    rule = sarif["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["helpUri"] == "https://example.test/x"  # the first URL
    assert rule["properties"]["version"] == 3


def test_a_placeholder_that_does_not_exist_is_refused(tmp_path):
    (tmp_path / "p.yaml").write_text(
        policy_text([{"type": "value", "key": "a", "value": 1}], pid="AB-001").replace(
            '"check"', '"message": "{nope}", "check"'
        )
    )
    code, out, err = run(["validate", tmp_path])
    assert code == 1 and "unknown placeholder" in err


def test_the_row_fields_the_reference_lists_are_on_the_rows_of_a_snapshot(tmp_path):
    fields = (
        "service resource_type resource_id resource_name arn region account_id "
        "source_account_id tags raw_data detail_level sources"
    ).split()
    page = text_of(FILES)
    for name in fields:
        assert f"`{name}`" in page, name
    golden = json.loads((GOLDEN / "s1.json").read_text())
    for r in golden["resources"]:
        assert {
            "service",
            "resource_type",
            "resource_id",
            "arn",
            "region",
            "tags",
            "detail_level",
            "source_account_id",
        } <= set(r)


@pytest.mark.e2e
def test_a_scan_writes_the_snapshot_the_policy_command_reads(tmp_path):
    from tests.unit.finops.conftest import run_scan

    folder = tmp_path / "pol"
    folder.mkdir()
    (folder / "stopped.yaml").write_text(
        policy_text(
            [
                {
                    "type": "value",
                    "key": "raw_data.State.Name",
                    "op": "ne",
                    "value": "stopped",
                }
            ],
            severity="high",
            pid="EC2-101",
            resource={"services": ["EC2"], "resource_types": ["Instance"]},
        )
    )
    scan = run_scan(tmp_path, "--policy", str(folder), "--policy-fail-on", "high")
    assert scan.code == 7, scan.text
    states = sorted((scan.out / "state").glob("state_*.json"))
    assert len(states) == 1
    snap = json.loads(states[0].read_text())
    for r in snap["resources"]:
        assert {
            "service",
            "resource_type",
            "resource_id",
            "arn",
            "region",
            "tags",
            "raw_data",
            "detail_level",
            "sources",
        } <= set(r) or r.get("detail_level") == "identity"
        assert "account_id" in r or "source_account_id" in r
    on_scan = json.loads(next(scan.out.glob("policy_findings_*.json")).read_text())
    out_dir = tmp_path / "again"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            states[0],
            "--policies",
            folder,
            "--now",
            on_scan["now"],
            "--format",
            "json",
            "--output-directory",
            out_dir,
        ]
    )
    assert code == 0, err
    again = json.loads(next(out_dir.glob("*.json")).read_text())
    assert [f["resource"] for f in again["findings"]] == [
        f["resource"] for f in on_scan["findings"]
    ]


def test_a_waiver_matches_the_arn_or_the_service_type_id_and_a_glob_with_an_account(ws):
    rows = [
        row({"A": 1}, arn="", resource_id="i-9"),
        row(
            {"A": 1},
            resource_id="i-8",
            arn="arn:aws:ec2:us-east-1:111111111111:instance/i-8",
        ),
    ]
    snap = ws / "own.json"
    snap.write_text(json.dumps(snapshot(rows)))
    (ws / "pol").mkdir()
    (ws / "pol" / "p.yaml").write_text(
        policy_text(
            [{"type": "value", "key": "raw_data.A", "value": 2}],
            severity="high",
            pid="AB-001",
        )
    )
    spec = {
        "format_version": 1,
        "kind": "waivers",
        "name": "w",
        "spec": {
            "waivers": [
                {
                    "policy": "AB-001",
                    "resource": "EC2/Instance/i-9",
                    "reason": "a long enough reason",
                    "approved_by": "x",
                    "expires": "2026-12-31",
                },
                {
                    "policy": "AB-001",
                    "resource": "arn:aws:ec2:us-east-1:*:instance/i-?",
                    "account": ACCOUNT,
                    "reason": "a long enough reason",
                    "approved_by": "x",
                    "expires": "2026-12-31",
                },
            ]
        },
    }
    (ws / "w.yaml").write_text(json.dumps(spec))
    out_dir = ws / "o"
    code, out, err = run(
        [
            "check",
            "--snapshot",
            snap,
            "--policies",
            ws / "pol",
            "--waivers",
            ws / "w.yaml",
            "--now",
            NOW,
            "--fail-on",
            "high",
            "--format",
            "json",
            "--output-directory",
            out_dir,
        ]
    )
    data = json.loads(next(out_dir.glob("*.json")).read_text())
    assert code == 0, err
    assert data["summary"]["by_result"]["waived"] == 2
    assert data["unused_waivers"] == []


def slug(heading):
    heading = re.sub(r"[`*]", "", heading)
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", heading.lower()).strip())


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_every_relative_link_of_the_pages_resolves_to_a_page_and_a_heading(page):
    for target in re.findall(r"\]\(([^)\s]+)\)", text_of(page)):
        if target.startswith(("http://", "https://", "#")):
            continue
        path, _, anchor = target.partition("#")
        found = (page.parent / path).resolve()
        assert found.is_file(), target
        if anchor:
            headings = re.findall(r"^#{1,6} (.*?)\s*$", text_of(found), re.M)
            assert anchor in {slug(h) for h in headings}, target


def test_every_command_in_the_bash_blocks_parses_with_the_real_parser():
    """The ci-examples checker (scripts/docs) does not know ``inventag policy``
    yet, so the commands of these pages are parsed here with the real parsers."""
    import importlib
    import shlex

    main_parser = importlib.import_module("inventag.cli.main").create_parser()
    count = 0
    for page in PAGES:
        for info, body in fences(text_of(page)):
            if info != "bash":
                continue
            for line in body.splitlines():
                tokens = shlex.split(line)
                assert tokens[0] == "inventag", line
                if tokens[1] == "policy":
                    parser = cli.build_parser()
                    args = tokens[2:]
                else:
                    parser, args = main_parser, tokens[1:]
                try:
                    parser.parse_args(args)
                except SystemExit as stop:  # pragma: no cover
                    raise AssertionError(f"{line}: exit {stop.code}") from None
                count += 1
    assert count == 12
