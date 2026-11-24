"""The shipped policy sets of v1.5.0 (plan P5): they load, every policy has
fixtures that hold, and the words follow the spec."""

import re
from pathlib import Path

import pytest

from inventag.policy import builtin, loader
from tests.unit.policy_builtin import runner

SETS = [
    "encryption-at-rest",
    "finops-checks",
    "naming",
    "public-exposure",
    "region-allowlist",
    "tagging-standard",
]
FORBIDDEN = re.compile(r"complian|certif|enforce", re.IGNORECASE)
FRAMEWORKS = re.compile(r"\b(cis|pci|hipaa|nist|soc2?|iso27001|gdpr|mas|im8)\b", re.I)


def test_the_shipped_sets_are_these_six():
    assert sorted(builtin.SET_NAMES) == SETS


def test_a_set_name_is_a_folder_of_the_package():
    for name in SETS:
        assert (builtin.BUILTIN_DIR / name / "set.yaml").is_file(), name


@pytest.mark.parametrize("name", SETS)
def test_the_set_loads_and_every_policy_is_in_it(name):
    policies = builtin.load_set(name)
    assert policies, name
    loaded = loader.load([builtin.BUILTIN_DIR / name])
    assert sorted(p.id for p in policies) == sorted(p.id for p in loaded.policies)
    assert all(p.version >= 1 and p.enabled for p in policies)


def test_policy_ids_are_unique_across_all_sets():
    ids = [p.id for name in SETS for p in builtin.load_set(name)]
    assert len(ids) == len(set(ids))
    names = [p.name for name in SETS for p in builtin.load_set(name)]
    assert len(names) == len(set(names))


def test_all_sets_load_together_without_a_clash():
    loaded = loader.load([builtin.BUILTIN_DIR])
    assert len(loaded.policies) == sum(len(builtin.load_set(n)) for n in SETS)


def test_finops_checks_is_six_policies_of_severity_low():
    policies = builtin.load_set("finops-checks")
    assert [p.id for p in sorted(policies, key=lambda p: p.id)] == [
        f"FIN-00{i}" for i in range(1, 7)
    ]
    assert {p.severity for p in policies} == {"low"}
    assert {p.version for p in policies} == {1}


def test_the_words_of_the_spec_hold_in_every_file():
    for path in builtin.BUILTIN_DIR.rglob("*.yaml"):
        text = path.read_text()
        assert not FORBIDDEN.search(text), path
        assert not FRAMEWORKS.search(text), path
    for name in SETS:
        assert not FRAMEWORKS.search(name)


def test_no_policy_has_an_action():
    for path in builtin.BUILTIN_DIR.rglob("*.yaml"):
        if "tests" in path.parts:
            continue
        for word in ("actions:", "mode:", "notify:", "remediate:"):
            assert word not in path.read_text(), (path, word)


@pytest.mark.parametrize("name", SETS)
def test_every_policy_has_fixtures_with_a_pass_and_a_fail(name):
    set_dir = builtin.BUILTIN_DIR / name
    for policy in builtin.load_set(name):
        folder = set_dir / "tests" / policy.name
        files = sorted(folder.glob("*.yaml"))
        assert files, f"{policy.id} {policy.name}: no fixtures in {folder}"
        seen = set()
        for path in files:
            import yaml

            doc = yaml.safe_load(path.read_text())
            seen.update(e["result"] for e in doc["spec"]["expect"])
        assert {"pass", "fail"} <= seen, (policy.id, seen)


@pytest.mark.parametrize("name", SETS)
def test_policy_test_is_green_on_every_fixture_of_the_set(name):
    set_dir = builtin.BUILTIN_DIR / name
    files = runner.fixtures_of(set_dir)
    assert files
    problems = [p for f in files for p in runner.run_fixture(set_dir, f)]
    assert problems == []


def test_a_fixture_that_is_wrong_is_reported():
    set_dir = builtin.BUILTIN_DIR / "finops-checks"
    path = runner.fixtures_of(set_dir)[0]
    text = path.read_text().replace("result: pass", "result: fail", 1)
    if text == path.read_text():
        text = path.read_text().replace("result: fail", "result: pass", 1)
    bad = Path(__file__).parent / "_bad_fixture.yaml"
    try:
        bad.write_text(text)
        assert runner.run_fixture(set_dir, bad)
    finally:
        bad.unlink()
