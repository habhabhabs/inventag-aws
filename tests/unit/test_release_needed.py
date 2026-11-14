"""Release decision: did the application change since the last release tag?

``.github/scripts/release-needed.sh`` is the one place that defines the
application paths. The release workflow releases a new version only when it
prints ``application_changed=true``. Each test builds a small git repository in
a temporary folder, so the tests need ``git`` and ``bash`` and nothing else.
"""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / ".github" / "scripts" / "release-needed.sh"
)

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
