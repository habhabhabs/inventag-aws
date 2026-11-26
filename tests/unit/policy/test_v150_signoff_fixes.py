"""v1.5.0 architect sign-off condition 4 (reports/architect-v150-signoff.md) and
the security re-check (reports/v150-security-review.md, R1 to R3).

Condition 4: ``--finops-checks --template`` without ``--policy``: a snapshot
that was not saved gives one WARNING and leaves the exit code; with
``--policy`` it stays exit 1.
R1: sets that include each other by name: memoised, depth capped, clean error.
R2: adjacent unbounded repeats and repeats of a variable repeat are refused.
R3: the SARIF message never holds a tag value, whatever the value says.
"""

import importlib
import json
import time
from types import SimpleNamespace

import pytest

from inventag.policy import loader, model
from inventag.policy.schema import backtracks

from .cli_helpers import NOW, run, snapshot_file

cli_main = importlib.import_module("inventag.cli.main")

WARNING = (
    "--finops-checks: the state snapshot of this run was not saved, so no "
    "FinOps findings were written; see the notes above."
)


# ------------------------------------------------------------ condition 4
class _Log:
    def __init__(self):
        self.lines = []

    def warning(self, text):
        self.lines.append(("WARNING", text))

    def error(self, text):
        self.lines.append(("ERROR", text))

    def info(self, text):
        self.lines.append(("INFO", text))


def _args(policy):
    return SimpleNamespace(
        policy=policy,
        loaded_policies=(SimpleNamespace(policies=()), []),
        policy_fail_on=None,
    )


def test_finops_template_without_a_saved_snapshot_warns_and_goes_on():
    log = _Log()
    results = {"state_management": {"state_saved": False}}
    assert cli_main._run_scan_policies(_args(None), results, log) is None
    assert log.lines == [("WARNING", WARNING)]


def test_with_policy_an_unsaved_snapshot_still_exits_1():
    log = _Log()
    results = {"state_management": {"state_saved": False}}
    code = cli_main._run_scan_policies(_args(["p.yaml"]), results, log)
    assert code == cli_main.EXIT_ERROR
    assert [level for level, _ in log.lines] == ["ERROR"]


# ------------------------------------------------------------ R1
def _sets(folder, count, include):
    docs = []
    for i in range(count):
        nxt = [f"s{i + 1}"] * include if i + 1 < count else []
        docs.append(
            f"format_version: 1\nkind: policy-set\nname: s{i}\n"
            f"spec: {{include: {json.dumps(nxt)}}}\n"
        )
    (folder / "sets.yaml").write_text("---\n".join(docs))


@pytest.mark.parametrize("count, include", [(1500, 1), (26, 2)])
def test_long_or_branching_include_chains_are_a_clean_error(tmp_path, count, include):
    folder = tmp_path / "policies"
    folder.mkdir()
    _sets(folder, count, include)
    started = time.monotonic()
    code, out, err = run(["validate", folder])
    assert time.monotonic() - started < 30
    assert code == 1
    assert (
        f"policy sets include each other deeper than {model.LIMITS.set_file_depth}"
        in out + err
    )
    assert "Traceback" not in err and "RecursionError" not in err


def test_a_diamond_of_includes_within_the_limit_is_resolved_once(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    _sets(folder, 8, 2)
    started = time.monotonic()
    loaded = loader.load([folder], root=folder)
    assert time.monotonic() - started < 10
    assert len(loaded.sets) == 8


# ------------------------------------------------------------ R2
@pytest.mark.parametrize(
    "pattern",
    [
        "a*a*a*a*a*a*a*a*a*a*b",
        ".*.*.*.*.*.*.*.*=",
        "(a{1,50}){1,50}$",
        "(a?){30}a{30}",
        "a*b?a*c",
    ],
)
def test_repeated_and_nested_quantifiers_are_refused(pattern):
    assert backtracks(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        "^v?[0-9]+$",
        "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
        ".*-prod$",
        "^[0-9]+\\.[0-9]+\\.[0-9]+$",
        "(\\d{4}-)+",
        "^PROJ-[0-9]{4}-[A-Z0-9]+$",
    ],
)
def test_ordinary_patterns_are_still_accepted(pattern):
    assert not backtracks(pattern)


def test_validate_refuses_an_adjacent_repeat_pattern(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    entry = {"type": "name-pattern", "pattern": "a*a*a*b"}
    (folder / "p.yaml").write_text(
        "format_version: 1\nkind: policy\nname: r\n"
        f"spec: {json.dumps({'id': 'REG-009', 'severity': 'low', 'check': [entry]})}\n"
    )
    code, out, err = run(["validate", folder])
    assert code == 1
    assert "pattern can take very long to match" in out + err


# ------------------------------------------------------------ R3
HOSTILE = "y' does not match x' is not one of prod"


@pytest.mark.parametrize(
    "rule", ["pattern: 'CC-\\d{4}'", "allowed_values: [CC-0001, CC-0002]"]
)
def test_sarif_never_holds_a_tag_value(tmp_path, rule):
    snap = snapshot_file(tmp_path)
    data = snap.read_text().replace(
        '"CostCenter": "1234"', json.dumps({"CostCenter": HOSTILE})[1:-1]
    )
    snap.write_text(data)
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "p.yaml").write_text(
        "format_version: 1\nkind: policy\nname: tag-003\n"
        "spec: {id: TAG-003, severity: low, resource: {services: [RDS]},\n"
        f"       check: [{{type: required-tags, keys: [{{key: CostCenter, {rule}}}]}}]}}\n"
    )
    code, out, err = run(
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
            "sarif",
        ]
    )
    assert code == 0, err
    (written,) = (tmp_path / "out").glob("*.sarif")
    text = written.read_text()
    assert HOSTILE not in text and "x' is not one of" not in text
    messages = [
        r["message"]["text"]
        for r in json.loads(text)["runs"][0]["results"]
        if r["ruleId"] == "TAG-003"
    ]
    assert messages and set(messages) == {"TAG-003: CostCenter: value not allowed"}
