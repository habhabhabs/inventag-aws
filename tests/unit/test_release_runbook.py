"""The release runbook (docs/development/release-runbook.md) and its rules.

Every rule R1, R2, ... in the runbook's table names the tests that prove it.
The first group checks that each named test exists, in English and in the four
translations. The other groups are the proofs that live in this file: they
run steps of release.yml (read from the workflow file) with stand-ins for
``gh`` and ``semver``, and read the committed translation files.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "docs" / "development" / "release-runbook.md"
LOCALES = ("zh-Hans", "zh-Hant", "es", "fr")
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
DOCS_VERSIONING = ROOT / ".github" / "workflows" / "release-docs-versioning.yml"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

ROW = re.compile(r"^\| (R\d+) \|.*\|(.*)\|\s*$")
TEST_ID = re.compile(r"`(tests/[\w/]+\.py)::(test_\w+)`")


def rules(page: Path) -> dict:
    """{rule id: [(file, test name), ...]} from the table of one page."""
    found = {}
    for line in page.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            found[match.group(1)] = TEST_ID.findall(match.group(2))
    return found


# -------------------------------------------------------- one test per rule
def test_every_rule_names_at_least_one_test_that_exists():
    table = rules(RUNBOOK)
    assert list(table) == [f"R{n}" for n in range(1, len(table) + 1)]
    assert len(table) >= 18
    for rule, tests in table.items():
        assert tests, f"{rule} names no test"
        for file, name in tests:
            source = (ROOT / file).read_text(encoding="utf-8")
            assert re.search(
                rf"^def {name}\(", source, re.M
            ), f"{rule}: {file}::{name} not found"


def test_every_test_id_on_the_page_is_a_real_test():
    # Test ids outside the table too (the known limits).
    text = RUNBOOK.read_text(encoding="utf-8")
    for file, name in TEST_ID.findall(text):
        source = (ROOT / file).read_text(encoding="utf-8")
        assert re.search(rf"^def {name}\(", source, re.M), f"{file}::{name}"


@pytest.mark.parametrize("locale", LOCALES)
def test_each_translation_has_the_same_rules_and_tests(locale):
    page = (
        ROOT
        / "website"
        / "translations"
        / locale
        / "docs"
        / "development"
        / "release-runbook.md"
    )
    assert rules(page) == rules(RUNBOOK)
    assert TEST_ID.findall(page.read_text(encoding="utf-8")) == TEST_ID.findall(
        RUNBOOK.read_text(encoding="utf-8")
    )


def release_step(job: str, name: str) -> dict:
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    return next(s for s in workflow["jobs"][job]["steps"] if s.get("name") == name)


# ------------------------------------------------------------- R11 concurrency
def test_runs_that_cannot_release_have_their_own_concurrency_group():
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    group = " ".join(workflow["concurrency"]["group"].split())
    assert group == (
        "${{ ((github.event_name == 'workflow_dispatch' && "
        "github.event.inputs.publish_existing_tag != '') || "
        "contains(github.event.head_commit.message, '[skip release]') || "
        "contains(github.event.head_commit.message, '[skip ci]')) && "
        "format('release-noop-{0}', github.run_id) || 'release-main' }}"
    )
    assert workflow["concurrency"]["cancel-in-progress"] is False


# -------------------------------------------------------- R12 the new version
SEMVER_STAND_IN = """
class Version:
    def __init__(self, major, minor, patch):
        self.parts = (major, minor, patch)

    @classmethod
    def parse(cls, text):
        major, minor, patch = (int(p) for p in text.split("."))
        return cls(major, minor, patch)

    def bump_major(self):
        return Version(self.parts[0] + 1, 0, 0)

    def bump_minor(self):
        return Version(self.parts[0], self.parts[1] + 1, 0)

    def bump_patch(self):
        return Version(self.parts[0], self.parts[1], self.parts[2] + 1)

    def __str__(self):
        return "%d.%d.%d" % self.parts
"""


def next_version(tmp_path: Path, latest_release: str, file_version: str, bump: str):
    """Run the step "Calculate new version" with a stand-in gh and semver."""
    work = tmp_path / "work"
    (work / "inventag").mkdir(parents=True)
    (work / "inventag" / "_version.py").write_text(
        f'"""x"""\n\n__version__ = "{file_version}"\n', encoding="utf-8"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(f"#!/bin/sh\necho {latest_release}\n")
    (bin_dir / "gh").chmod(0o755)
    (bin_dir / "python").symlink_to(sys.executable)
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "semver.py").write_text(SEMVER_STAND_IN, encoding="utf-8")
    script = release_step("release", "Calculate new version")["run"]
    script = script.replace("${{ needs.check-for-release.outputs.version_bump }}", bump)
    assert "${{" not in script
    output = tmp_path / "out"
    output.write_text("")
    result = subprocess.run(
        ["bash", "-e", "-c", script],
        cwd=work,
        env={
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
            "PYTHONPATH": str(lib),
            "GITHUB_OUTPUT": str(output),
            "GH_TOKEN": "x",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    values = dict(line.split("=", 1) for line in output.read_text().splitlines())
    return values["new_version"]


@pytest.mark.parametrize(
    "release,file,bump,expected",
    [
        ("v1.2.2", "1.2.2", "patch", "1.2.3"),
        ("v1.2.2", "1.2.2", "minor", "1.3.0"),
        ("v1.2.2", "1.2.0", "patch", "1.2.3"),
        # A failed release whose bump commit is on main (the v1.2.2 case):
        # running the job again gives the next number, not the lost one.
        ("v1.2.1", "1.2.2", "patch", "1.2.3"),
    ],
)
def test_next_version_bumps_the_higher_of_release_and_file(
    tmp_path, release, file, bump, expected
):
    assert next_version(tmp_path, release, file, bump) == expected


# ------------------------------------------------------- R16 the publish guard
def publish_guard(tmp_path: Path, tag_on_head: bool, release_exists: bool, event: str):
    """Run the step "Tag and release exist?" in a clone of a local remote."""
    env = {**os.environ, **GIT_ENV}
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True, env=env
    )
    subprocess.run(
        ["git", "clone", "-q", str(remote), str(work)],
        check=True,
        env=env,
        capture_output=True,
    )
    for message in ("one", "chore: bump version to v1.2.3"):
        subprocess.run(
            ["git", "commit", "-q", "--allow-empty", "-m", message],
            cwd=work,
            check=True,
            env=env,
        )
    subprocess.run(
        ["git", "push", "-q", "origin", "main"], cwd=work, check=True, env=env
    )
    target = "HEAD" if tag_on_head else "HEAD~1"
    if tag_on_head is not None:
        subprocess.run(["git", "tag", "v1.2.3", target], cwd=work, check=True, env=env)
        subprocess.run(
            ["git", "push", "-q", "origin", "v1.2.3"], cwd=work, check=True, env=env
        )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(f"#!/bin/sh\nexit {0 if release_exists else 1}\n")
    (bin_dir / "gh").chmod(0o755)
    output = tmp_path / "out"
    output.write_text("")
    script = release_step("publish-pypi", "Tag and release exist?")["run"]
    assert "${{" not in script
    result = subprocess.run(
        ["bash", "-e", "-c", script],
        cwd=work,
        env={
            **env,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "VERSION": "1.2.3",
            "GH_TOKEN": "x",
            "EVENT_NAME": event,
            "GITHUB_REPOSITORY": "o/r",
            "GITHUB_OUTPUT": str(output),
        },
        capture_output=True,
        text=True,
    )
    values = dict(
        line.split("=", 1) for line in output.read_text().splitlines() if "=" in line
    )
    return result, values.get("ok")


def test_publish_guard_passes_with_the_tag_and_the_release(tmp_path):
    result, ok = publish_guard(tmp_path, True, True, "push")
    assert result.returncode == 0 and ok == "true"


def test_publish_guard_on_a_push_without_the_tag_publishes_nothing(tmp_path):
    result, ok = publish_guard(tmp_path, None, False, "push")
    assert result.returncode == 0 and ok == "false"
    assert "run Automated Release with publish_existing_tag" in result.stdout


def test_publish_guard_with_the_tag_on_another_commit_publishes_nothing(tmp_path):
    result, ok = publish_guard(tmp_path, False, True, "push")
    assert result.returncode == 0 and ok == "false"


def test_publish_guard_on_a_manual_run_without_the_release_fails(tmp_path):
    result, ok = publish_guard(tmp_path, True, False, "workflow_dispatch")
    assert result.returncode == 1 and ok is None
    assert "refusing to publish" in result.stdout


# --------------------------------------------- R18 the current-version labels
def test_docs_versioning_commits_the_current_json_labels():
    workflow = yaml.safe_load(DOCS_VERSIONING.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["archive"]["steps"]
    names = [s["name"] for s in steps]
    # The build (its prebuild runs sync-i18n.mjs, which writes the label)
    # comes before the commit, and the commit adds the four files.
    assert names.index("Build the site") < names.index("Commit and push")
    run = " ".join(steps[names.index("Commit and push")]["run"].split())
    add = run[run.index("git add") : run.index("if git diff")]
    assert "website/i18n/*/docusaurus-plugin-content-docs/current.json" in add
    package = json.loads((ROOT / "website" / "package.json").read_text("utf-8"))
    assert package["scripts"]["prebuild"] == "node scripts/sync-i18n.mjs"


CURRENT_WORD = {"zh-Hans": "当前", "zh-Hant": "目前", "es": "actual", "fr": "actuelle"}


@pytest.mark.parametrize("locale", sorted(CURRENT_WORD))
def test_committed_current_labels_name_a_released_version(locale):
    # On the bump commit the label still names the previous release, until the
    # docs versioning run commits the new one; so either version is right.
    version = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    allowed = {version["version"], version.get("previous_version")}
    path = (
        ROOT
        / "website"
        / "i18n"
        / locale
        / "docusaurus-plugin-content-docs"
        / "current.json"
    )
    label = json.loads(path.read_text(encoding="utf-8"))["version.label"]["message"]
    word = CURRENT_WORD[locale]
    match = re.fullmatch(
        r"v(\d+\.\d+\.\d+)"
        + (f"（{word}）" if locale.startswith("zh") else f" \\({word}\\)"),
        label,
    )
    assert match, label
    assert match.group(1) in allowed, f"{locale}: {label} for version.json {allowed}"


def test_the_label_words_are_the_ones_sync_i18n_writes():
    source = (ROOT / "website" / "scripts" / "sync-i18n.mjs").read_text("utf-8")
    for locale, word in CURRENT_WORD.items():
        key = f"'{locale}'" if "-" in locale else locale
        assert f"{key}: '{word}'" in source
