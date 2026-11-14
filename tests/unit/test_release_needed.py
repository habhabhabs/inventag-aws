"""Release decision: did the application change since the last release tag?

``.github/scripts/release-needed.sh`` is the one place that defines the
application paths. The release workflow releases a new version only when it
prints ``application_changed=true``. Each test builds a small git repository in
a temporary folder, so the tests need ``git``, ``bash`` and PyYAML.

The last group runs the "Check for release triggers" step of release.yml itself
(read from the workflow file) against such a repository, to prove the order of
the release rules.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "release-needed.sh"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

INITIAL_FILES = {
    "inventag/__init__.py": "",
    "inventag/_version.py": '__version__ = "1.0.0"\n',
    "pyproject.toml": "[project]\n",
    "requirements.txt": "boto3\n",
    "LICENSE": "MIT\n",
    "README.md": "# x\n",
    "CHANGELOG.md": "# Changelog\n",
    "version.json": '{"version": "1.0.0"}\n',
    "docs/index.md": "docs\n",
    "website/src/page.js": "page\n",
    "tests/test_a.py": "def test_a():\n    pass\n",
    "scripts/docs/check.py": "print()\n",
    "config/defaults/iam-policy-read-only.json": "{}\n",
    "templates/default_word_template.yaml": "a: 1\n",
    "examples/run.sh": "echo\n",
    ".github/workflows/ci.yml": "name: CI\n",
    ".github/scripts/sync-doc-versions.sh": "echo\n",
}


class Repo:
    def __init__(self, path: Path):
        self.path = path

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.path,
            env={**os.environ, **GIT_ENV},
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def commit(self, message: str, files: dict) -> str:
        for name, text in files.items():
            target = self.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")


def run_script(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
        env={**os.environ, **GIT_ENV},
        capture_output=True,
        text=True,
    )


def decision(repo: Repo, *args: str) -> dict:
    result = run_script(repo.path, *args)
    assert result.returncode == 0, result.stderr
    out = {"paths": []}
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        if key == "path":
            out["paths"].append(value)
        else:
            out[key] = value
    return out


@pytest.fixture
def repo(tmp_path) -> Repo:
    """A repository with one release, v1.0.0, on main."""
    r = Repo(tmp_path / "repo")
    r.path.mkdir()
    r.git("init", "-q", "-b", "main")
    r.commit("initial", INITIAL_FILES)
    r.git("tag", "v1.0.0")
    return r


def test_docs_only_change_is_not_a_release(repo):
    repo.commit("docs: fix a page", {"docs/index.md": "better docs\n"})
    out = decision(repo)
    assert out == {"base_tag": "v1.0.0", "application_changed": "false", "paths": []}


def test_site_markdown_examples_config_and_templates_are_not_application(repo):
    repo.commit(
        "site and repo files",
        {
            "website/src/page.js": "new page\n",
            "README.md": "# y\n",
            "examples/run.sh": "echo 2\n",
            "scripts/docs/check.py": "print(1)\n",
            "config/defaults/iam-policy-read-only.json": '{"a": 1}\n',
            "templates/default_word_template.yaml": "a: 2\n",
            "version.json": '{"version": "1.0.1"}\n',
        },
    )
    assert decision(repo)["application_changed"] == "false"


def test_tests_only_change_is_not_a_release(repo):
    repo.commit("tests: one more", {"tests/test_b.py": "def test_b():\n    pass\n"})
    assert decision(repo)["application_changed"] == "false"


def test_github_actions_only_change_is_not_a_release(repo):
    repo.commit(
        "ci: change a workflow",
        {
            ".github/workflows/ci.yml": "name: CI 2\n",
            ".github/scripts/sync-doc-versions.sh": "echo 2\n",
        },
    )
    assert decision(repo)["application_changed"] == "false"


def test_package_code_change_is_a_release(repo):
    repo.commit("fix: a bug", {"inventag/core.py": "x = 1\n"})
    out = decision(repo)
    assert out == {
        "base_tag": "v1.0.0",
        "application_changed": "true",
        "paths": ["inventag/core.py"],
    }


@pytest.mark.parametrize("name", ["pyproject.toml", "requirements.txt", "LICENSE"])
def test_build_and_dependency_files_are_application(repo, name):
    repo.commit("build: change " + name, {name: "changed\n"})
    out = decision(repo)
    assert out["application_changed"] == "true"
    assert out["paths"] == [name]


def test_mixed_change_lists_only_the_application_paths(repo):
    repo.commit(
        "feat: new flag and its docs",
        {"website/src/page.js": "v2\n", "inventag/cli.py": "flag = 1\n"},
    )
    out = decision(repo)
    assert out["application_changed"] == "true"
    assert out["paths"] == ["inventag/cli.py"]


def test_an_earlier_unreleased_code_commit_still_counts(repo):
    """One release covers every commit since the previous tag."""
    repo.commit("fix: a bug", {"inventag/core.py": "x = 1\n"})
    repo.commit("docs: later page", {"docs/index.md": "later\n"})
    out = decision(repo)
    assert out["application_changed"] == "true"
    assert out["paths"] == ["inventag/core.py"]


def test_deleting_a_package_file_counts(repo):
    repo.git("rm", "-q", "inventag/__init__.py")
    repo.git("commit", "-q", "-m", "refactor: drop a module")
    assert decision(repo)["paths"] == ["inventag/__init__.py"]


def test_the_release_bump_commit_does_not_count(repo):
    repo.commit(
        "chore: bump version to v1.0.1",
        {
            "version.json": '{"version": "1.0.1"}\n',
            "inventag/_version.py": '__version__ = "1.0.1"\n',
            "CHANGELOG.md": "# Changelog\n\n## v1.0.1\n",
        },
    )
    repo.commit("docs: archive [skip release]", {"docs/index.md": "archived\n"})
    assert decision(repo)["application_changed"] == "false"


def test_the_latest_ancestor_release_tag_is_the_base(repo):
    repo.commit("fix: a bug", {"inventag/core.py": "x = 1\n"})
    repo.git("tag", "-a", "v1.1.0", "-m", "annotated release tag")
    repo.git("tag", "v1.1.0-rc1")  # not a release tag
    repo.git("tag", "docs-snapshot")  # not a release tag
    repo.commit("docs: page", {"docs/index.md": "after v1.1.0\n"})
    out = decision(repo)
    assert out == {"base_tag": "v1.1.0", "application_changed": "false", "paths": []}


def test_a_tag_that_is_not_an_ancestor_is_ignored(repo):
    repo.git("checkout", "-q", "-b", "side")
    repo.commit("side work", {"docs/side.md": "side\n"})
    repo.git("tag", "v9.0.0")
    repo.git("checkout", "-q", "main")
    repo.commit("fix: on main", {"inventag/core.py": "x = 2\n"})
    out = decision(repo)
    assert out["base_tag"] == "v1.0.0"
    assert out["application_changed"] == "true"


def test_a_merged_pull_request_with_code_counts(repo):
    repo.git("checkout", "-q", "-b", "feature")
    repo.commit("feat: new module", {"inventag/new.py": "y = 1\n"})
    repo.git("checkout", "-q", "main")
    repo.commit("docs: meanwhile", {"docs/index.md": "meanwhile\n"})
    repo.git("merge", "-q", "--no-ff", "-m", "Merge pull request #7", "feature")
    out = decision(repo)
    assert out["application_changed"] == "true"
    assert out["paths"] == ["inventag/new.py"]


def test_no_release_tag_at_all_counts_every_file_as_new(tmp_path):
    r = Repo(tmp_path / "fresh")
    r.path.mkdir()
    r.git("init", "-q", "-b", "main")
    r.commit("initial", {"docs/index.md": "docs\n", "inventag/core.py": "x\n"})
    out = decision(r)
    assert out == {
        "base_tag": "",
        "application_changed": "true",
        "paths": ["inventag/core.py"],
    }


def test_no_release_tag_and_no_package_files_is_not_a_release(tmp_path):
    r = Repo(tmp_path / "fresh")
    r.path.mkdir()
    r.git("init", "-q", "-b", "main")
    r.commit("initial", {"docs/index.md": "docs\n"})
    assert decision(r)["application_changed"] == "false"


def test_an_explicit_commit_is_judged_not_the_checkout(repo):
    first = repo.commit("docs: page", {"docs/index.md": "one\n"})
    repo.commit("fix: later", {"inventag/core.py": "x = 3\n"})
    assert decision(repo, first)["application_changed"] == "false"
    assert decision(repo, "HEAD")["application_changed"] == "true"


def test_a_shallow_clone_is_refused(repo, tmp_path):
    repo.commit("fix: a bug", {"inventag/core.py": "x = 1\n"})
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", repo.path.as_uri(), str(shallow)],
        env={**os.environ, **GIT_ENV},
        check=True,
        capture_output=True,
    )
    result = run_script(shallow)
    assert result.returncode != 0
    assert "shallow" in result.stderr
    assert "application_changed" not in result.stdout


def test_an_unknown_commit_is_an_error(repo):
    result = run_script(repo.path, "no-such-commit")
    assert result.returncode != 0
    assert "application_changed" not in result.stdout


# ----------------------------------------------- the release.yml decision step
def check_step_script() -> str:
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["check-for-release"]["steps"]
    return next(step for step in steps if step.get("id") == "check")["run"]


def run_check_step(
    repo: Repo,
    tmp_path: Path,
    event: str = "push",
    labels: str = "",
    version_bump: str = "",
    publish_tag: str = "",
) -> tuple:
    """Run the step as GitHub would (bash -e), with a fake ``gh`` for PR labels."""
    sha = repo.git("rev-parse", "HEAD")
    values = {"github.event_name": event, "github.ref": "refs/heads/main"}
    values["github.sha"] = sha

    def render(match):
        return values[match.group(1)]

    script = re.sub(r"\$\{\{\s*([a-z_.]+)\s*\}\}", render, check_step_script())
    # The step runs the script from the checkout of the commit.
    target = repo.path / ".github" / "scripts" / "release-needed.sh"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT, target)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake_gh = bin_dir / "gh"
    fake_gh.write_text("#!/bin/sh\nprintf '%s\\n' " + repr(labels) + "\n")
    fake_gh.chmod(0o755)
    output = tmp_path / "github_output"
    output.write_text("")
    env = {
        **os.environ,
        **GIT_ENV,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(output),
        "GITHUB_SHA": sha,
        "INPUT_VERSION_BUMP": version_bump,
        "INPUT_PUBLISH_TAG": publish_tag,
    }
    result = subprocess.run(
        ["bash", "-e", "-c", script],
        cwd=repo.path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    outputs = {}
    for line in output.read_text().splitlines():
        key, _, value = line.partition("=")
        outputs[key] = value  # the last value written wins, as on GitHub
    return outputs, result.stdout


def test_step_docs_only_push_is_no_release_and_says_why(repo, tmp_path):
    repo.commit("docs: a page", {"docs/index.md": "x\n"})
    outputs, log = run_check_step(repo, tmp_path)
    assert outputs["should_release"] == "false"
    assert "No application change since v1.0.0: no release" in log


def test_step_code_push_is_a_patch_release(repo, tmp_path):
    repo.commit("fix: a bug", {"inventag/core.py": "x = 1\n"})
    outputs, _ = run_check_step(repo, tmp_path)
    assert (outputs["should_release"], outputs["version_bump"]) == ("true", "patch")


def test_step_release_as_line_with_code_sets_the_bump(repo, tmp_path):
    repo.commit("feat: x\n\nRelease-As: minor", {"inventag/core.py": "x = 1\n"})
    outputs, _ = run_check_step(repo, tmp_path)
    assert (outputs["should_release"], outputs["version_bump"]) == ("true", "minor")


def test_step_release_as_line_without_code_is_no_release(repo, tmp_path):
    repo.commit("docs: x\n\nRelease-As: major", {"docs/index.md": "x\n"})
    outputs, log = run_check_step(repo, tmp_path)
    assert outputs["should_release"] == "false"
    assert "No application change since v1.0.0: no release" in log
    assert "The Release-As line is ignored" in log


def test_step_pr_label_with_code_sets_the_bump(repo, tmp_path):
    repo.commit("Merge pull request #12 from a/b\n\nfeat", {"inventag/x.py": "1\n"})
    outputs, _ = run_check_step(repo, tmp_path, labels="release:minor")
    assert (outputs["should_release"], outputs["version_bump"]) == ("true", "minor")
    assert outputs["pr_number"] == "12"


def test_step_pr_label_without_code_is_no_release(repo, tmp_path):
    repo.commit("Merge pull request #13 from a/b\n\ndocs", {"docs/index.md": "x\n"})
    outputs, log = run_check_step(repo, tmp_path, labels="release:major")
    assert outputs["should_release"] == "false"
    assert "release:* label on the pull request is ignored" in log


def test_step_skip_release_wins_over_a_code_change(repo, tmp_path):
    repo.commit("fix: x [skip release]", {"inventag/core.py": "x = 1\n"})
    outputs, log = run_check_step(repo, tmp_path)
    assert outputs["should_release"] == "false"
    assert "skip the release" in log


def test_step_bump_commit_is_no_release(repo, tmp_path):
    repo.commit("fix: x", {"inventag/core.py": "x = 1\n"})
    repo.commit("chore: bump version to v1.0.1", {"inventag/_version.py": "1.0.1\n"})
    outputs, log = run_check_step(repo, tmp_path)
    assert outputs["should_release"] == "false"
    assert "Automated version bump commit" in log


def test_step_commit_inside_a_release_tag_is_no_release(repo, tmp_path):
    repo.commit("fix: x", {"inventag/core.py": "x = 1\n"})
    repo.git("tag", "v1.0.1")
    outputs, log = run_check_step(repo, tmp_path)
    assert outputs["should_release"] == "false"
    assert "already part of v1.0.1" in log


def test_step_manual_run_with_a_bump_forces_a_release(repo, tmp_path):
    repo.commit("docs: only docs", {"docs/index.md": "x\n"})
    outputs, _ = run_check_step(
        repo, tmp_path, event="workflow_dispatch", version_bump="minor"
    )
    assert (outputs["should_release"], outputs["version_bump"]) == ("true", "minor")


def test_step_publish_only_run_is_no_release(repo, tmp_path):
    repo.commit("fix: x", {"inventag/core.py": "x = 1\n"})
    outputs, log = run_check_step(
        repo, tmp_path, event="workflow_dispatch", publish_tag="v1.0.0"
    )
    assert outputs["should_release"] == "false"
    assert "Publish-only run" in log
