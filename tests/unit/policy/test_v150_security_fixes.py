"""v1.5.0 security review (reports/v150-security-review.md), findings 1 and 3 to 7.

1. ``policy.lock`` covers every file that decides the result: a file a set
   names by path (any suffix, also under ``tests/``) and the tag-policy
   template that ``required-tags`` with ``policy: NAME`` reads.
3. SARIF carries no tag value.
4. A ``message`` with a format spec or a conversion is refused; the engine
   never formats with one.
5. Sets that name each other by path, and deep YAML: a clean error, exit 1.
6. A pattern that can backtrack without end is refused; a long value is not
   matched.
7. A waiver ``resource`` made only of wildcards is refused.
"""

import datetime as dt
import json

import pytest

from inventag.policy import engine, filters, loader, model
from inventag.policy.filters import UNKNOWN
from inventag.policy.schema import PolicyError

from .cli_helpers import NOW, run, snapshot_file

TAG_POLICY = """format_version: 1
kind: policy
name: {name}
spec: {{id: {pid}, severity: low,
       resource: {{services: [RDS]}},
       check: [{{type: required-tags,
                 keys: [{{key: CostCenter, pattern: '{pattern}'}}]}}]}}
"""


def _policy_text(pattern="CC-\\d{4}", name="tag-003", pid="TAG-003"):
    return TAG_POLICY.format(name=name, pid=pid, pattern=pattern)


def _check(tmp_path, folder, *extra):
    snap = snapshot_file(tmp_path)
    return run(
        [
            "check",
            "--snapshot",
            snap,
            "--policies",
            folder,
            "--now",
            NOW,
            "--output-directory",
            tmp_path / "out",
            "--format",
            "json",
            "--fail-on",
            "low",
            *extra,
        ]
    )


def _no_traceback(err):
    assert "Traceback" not in err
    assert "RecursionError" not in err


# ------------------------------------------------------------- finding 1
@pytest.mark.parametrize("target", ["sub/p.txt", "tests/q.yaml"])
def test_lock_covers_a_file_a_set_names_by_path(tmp_path, target):
    folder = tmp_path / "policies"
    (folder / target).parent.mkdir(parents=True)
    (folder / target).write_text(_policy_text())
    (folder / "set.yaml").write_text(
        "format_version: 1\nkind: policy-set\nname: s\n"
        f"spec: {{policies: ['{target}']}}\n"
    )
    code, out, err = run(["lock", folder])
    assert code == 0, err
    assert target in json.loads((folder / "policy.lock").read_text())["files"]
    code, out, err = _check(tmp_path, folder, "--locked")
    assert code == 7, err

    (folder / target).write_text(_policy_text(pattern=".*"))
    code, out, err = run(["lock", folder, "--check"])
    assert code == 1
    assert f"{target}: changed since policy.lock was written" in err
    code, out, err = _check(tmp_path, folder, "--locked")
    assert code == 1, (out, err)
    assert target in err


def _template(folder, pattern):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "my-tags.yaml").write_text(
        "format_version: 1\nkind: tag-policy\nname: my-tags\n"
        "description: test\nspec:\n  required_tags:\n"
        f"    - key: CostCenter\n      pattern: '{pattern}'\n"
    )


def test_lock_covers_the_tag_policy_template(tmp_path, monkeypatch):
    templates = tmp_path / "templates"
    _template(templates, "CC-\\d{4}")
    monkeypatch.setenv("INVENTAG_TEMPLATE_PATH", str(templates))
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "p.yaml").write_text(
        "format_version: 1\nkind: policy\nname: tags\n"
        "spec: {id: TAG-010, severity: low, resource: {services: [RDS]},\n"
        "       check: [{type: required-tags, policy: my-tags}]}\n"
    )
    code, out, err = run(["lock", folder])
    assert code == 0, err
    locked = json.loads((folder / "policy.lock").read_text())
    assert sorted(locked["tag_policies"]) == ["my-tags"]
    code, out, err = _check(tmp_path, folder, "--locked")
    assert code == 7, err

    _template(templates, ".*")
    code, out, err = run(["lock", folder, "--check"])
    assert code == 1
    assert "tag policy my-tags: changed since policy.lock was written" in err
    code, out, err = _check(tmp_path, folder, "--locked")
    assert code == 1, (out, err)


def test_a_lock_without_the_new_keys_still_reads(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "p.yaml").write_text(_policy_text())
    run(["lock", folder])
    data = json.loads((folder / "policy.lock").read_text())
    assert "tag_policies" not in data  # only written when a policy uses one
    code, out, err = run(["lock", folder, "--check"])
    assert code == 0, err


# ------------------------------------------------------------- finding 3
@pytest.mark.parametrize("show", [False, True])
def test_sarif_carries_no_tag_value(tmp_path, show):
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "ex06.yaml").write_text(_policy_text())
    extra = ["--format", "sarif"] + (["--show-values"] if show else [])
    code, out, err = _check(tmp_path, folder, *extra)
    assert code == 7, err
    (written,) = (tmp_path / "out").glob("*.sarif")
    text = written.read_text()
    assert "1234" not in text
    messages = [
        r["message"]["text"]
        for r in json.loads(text)["runs"][0]["results"]
        if r["ruleId"] == "TAG-003"
    ]
    assert messages == ["TAG-003: CostCenter: value not allowed"]


# ------------------------------------------------------------- finding 4
@pytest.mark.parametrize(
    "message", ["{name:{name}}", "{name:>400000000}", "{name!r}", "{name:x}"]
)
def test_validate_refuses_a_format_spec_in_message(tmp_path, message):
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "p.yaml").write_text(
        "format_version: 1\nkind: policy\nname: m\n"
        "spec: {id: MSG-001, severity: low, "
        f"message: '{message}', "
        "check: [{type: value, key: raw_data.X, value: 1}]}\n"
    )
    code, out, err = run(["validate", folder])
    assert code == 1
    assert "a message placeholder takes no format spec or conversion" in out + err
    _no_traceback(err)


def test_the_engine_never_formats_with_a_spec():
    policy = model.Policy(
        id="MSG-001",
        name="m",
        severity="low",
        check=({"type": "value", "key": "raw_data.X", "value": 1},),
        message="{name:{name}} {name:>400000000} {{x}} {policy}",
    )
    row = {"resource_name": "web-1", "service": "EC2"}
    text = engine._message(policy, row, "fail", None, [])
    assert text == "web-1 web-1 {x} MSG-001"


# ------------------------------------------------------------- finding 5
def _set(path, name, policies):
    path.write_text(
        f"format_version: 1\nkind: policy-set\nname: {name}\n"
        f"spec: {{policies: {json.dumps(policies)}}}\n"
    )


def test_a_set_file_that_names_itself_is_a_clean_error(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    _set(folder / "set.yaml", "s", ["set.yaml"])
    code, out, err = run(["validate", folder])
    assert code == 1
    assert "policy set file reached again: set.yaml -> set.yaml" in out + err
    _no_traceback(err)


def test_two_set_files_that_name_each_other_are_a_clean_error(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    _set(folder / "a.yaml", "a", ["b.yaml"])
    _set(folder / "b.yaml", "b", ["a.yaml"])
    code, out, err = run(["validate", folder])
    assert code == 1
    assert "policy set file reached again: a.yaml -> b.yaml -> a.yaml" in out + err
    _no_traceback(err)
    code, out, err = _check(tmp_path, folder)
    assert code == 1
    _no_traceback(err)


def test_a_long_chain_of_set_files_stops_at_the_depth_limit(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    depth = model.LIMITS.set_file_depth + 2
    for i in range(depth):
        _set(folder / f"s{i}.yaml", f"s{i}", [f"s{i + 1}.yaml"])
    (folder / f"s{depth}.yaml").write_text(_policy_text())
    with pytest.raises(PolicyError) as caught:
        loader.load([folder / "s0.yaml"], root=folder)
    text = " ".join(str(i) for i in caught.value.issues)
    assert f"policy set files nested deeper than {model.LIMITS.set_file_depth}" in text


def test_deep_yaml_is_a_clean_error(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "deep.yaml").write_text("a: " + "[" * 50000 + "]" * 50000 + "\n")
    code, out, err = run(["validate", folder])
    assert code == 1
    assert "nested too deeply" in out + err
    _no_traceback(err)


# ------------------------------------------------------------- finding 6
@pytest.mark.parametrize(
    "entry",
    [
        {"type": "name-pattern", "pattern": "(a|a)+$"},
        {"type": "name-pattern", "pattern": "(a+)+"},
        {"type": "value", "key": "raw_data.X", "op": "regex", "value": "(.*a){20}"},
        {
            "type": "required-tags",
            "keys": [{"key": "CostCenter", "pattern": "(x*)*y"}],
        },
    ],
)
def test_validate_refuses_a_pattern_that_can_backtrack(tmp_path, entry):
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "p.yaml").write_text(
        "format_version: 1\nkind: policy\nname: r\n"
        f"spec: {json.dumps({'id': 'REG-009', 'severity': 'low', 'check': [entry]})}\n"
    )
    code, out, err = run(["validate", folder])
    assert code == 1, out
    assert "pattern can take very long to match" in out + err


@pytest.mark.parametrize(
    "pattern",
    [
        "^CC-[0-9]{4}$",
        "(?!launch-wizard-).*",
        "[a-z][a-z0-9-]*",
        "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
        "(\\d{4}-)+",
    ],
)
def test_ordinary_patterns_still_validate(tmp_path, pattern):
    folder = tmp_path / "policies"
    folder.mkdir()
    entry = {"type": "name-pattern", "pattern": pattern}
    (folder / "p.yaml").write_text(
        "format_version: 1\nkind: policy\nname: r\n"
        f"spec: {json.dumps({'id': 'REG-009', 'severity': 'low', 'check': [entry]})}\n"
    )
    code, out, err = run(["validate", folder])
    assert code == 0, (out, err)


def test_a_long_name_is_not_matched(tmp_path):
    node = filters.compile_entry({"type": "name-pattern", "pattern": "x+"})
    row = {"resource_name": "x" * (model.LIMITS.found_string_length + 1)}
    ctx = filters.Context(
        now=dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc),
        tags_unknown=lambda row: False,
    )
    assert filters.evaluate(node, row, ctx) == (UNKNOWN, "value_too_long")


# ------------------------------------------------------------- finding 7
@pytest.mark.parametrize("resource", ["**", "?*", "[!]", "[a-z]*", " * "])
def test_a_waiver_made_only_of_wildcards_is_refused(tmp_path, resource):
    waivers = tmp_path / "w.yaml"
    waivers.write_text(
        "format_version: 1\nkind: waivers\nname: w\n"
        f"spec: {{waivers: [{{policy: RDS-001, resource: '{resource}', "
        "account: '111111111111', "
        "reason: 'Migration to an encrypted instance.', approved_by: lead, "
        "expires: 2026-12-31}]}\n"
    )
    code, out, err = run(["validate", waivers, "--now", NOW])
    assert code == 1
    assert "a waiver cannot match every resource" in out + err


def test_a_waiver_glob_with_a_literal_part_is_accepted(tmp_path):
    waivers = tmp_path / "w.yaml"
    waivers.write_text(
        "format_version: 1\nkind: waivers\nname: w\n"
        "spec: {waivers: [{policy: RDS-001, resource: 'arn:aws:rds:*:db:db-*', "
        "account: '111111111111', "
        "reason: 'Migration to an encrypted instance.', approved_by: lead, "
        "expires: 2026-12-31}]}\n"
    )
    code, out, err = run(["validate", waivers, "--now", NOW])
    assert code == 0, (out, err)
