"""Tagging the release commit: ``.github/scripts/release-tag.sh``.

release.yml's step "Create Git Tag" calls the script with the commit that the
bump step pushed. Each test builds a local bare repository as the remote and a
clone as the release job's checkout, then runs the real script. The rejection
of the v1.2.2 release, ``(missing necessary objects)``, is made the way git
makes it: the remote's branch names a commit whose object the remote cannot
read, so the client sends no objects with the tag. The tests need ``git``.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "release-tag.sh"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
REAL_GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(REAL_GIT is None, reason="needs git")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [REAL_GIT, *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def base_env(tmp_path: Path, **extra: str) -> dict:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "RELEASE_TAG_DELAY": "0",
    }
    env.update(extra)
    return env


class Release:
    """A bare remote and the release job's clone with a pushed bump commit."""

    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.remote = tmp_path / "remote.git"
        self.work = tmp_path / "work"
        subprocess.run(
            [REAL_GIT, "init", "-q", "--bare", "-b", "main", str(self.remote)],
            check=True,
            env=base_env(tmp_path),
        )
        subprocess.run(
            [REAL_GIT, "clone", "-q", str(self.remote), str(self.work)],
            check=True,
            capture_output=True,
            env=base_env(tmp_path),
        )
        self.commit("fix: something")
        self.push_main()
        self.sha = self.commit("chore: bump version to v1.2.2")
        self.push_main()

    def commit(self, message: str) -> str:
        (self.work / "f.txt").write_text(message, encoding="utf-8")
        env = base_env(self.tmp)
        subprocess.run([REAL_GIT, "add", "f.txt"], cwd=self.work, check=True, env=env)
        subprocess.run(
            [REAL_GIT, "commit", "-q", "-m", message], cwd=self.work, check=True, env=env
        )
        return git(self.work, "rev-parse", "HEAD")

    def push_main(self):
        subprocess.run(
            [REAL_GIT, "push", "-q", "origin", "main"],
            cwd=self.work,
            check=True,
            capture_output=True,
            env=base_env(self.tmp),
        )

    def object_path(self, sha: str) -> Path:
        return self.remote / "objects" / sha[:2] / sha[2:]

    def hide_commit_on_remote(self) -> Path:
        """Keep the remote's main on the bump commit but make its object unreadable."""
        source = self.object_path(self.sha)
        assert source.exists(), "expected a loose object on the remote"
        saved = self.tmp / "saved-object"
        shutil.copy2(source, saved)
        source.unlink()
        return saved

    def run(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=self.work,
            capture_output=True,
            text=True,
            env=base_env(self.tmp, **env),
            timeout=120,
        )


def remote_tag(release: Release, tag: str) -> str:
    result = subprocess.run(
        [REAL_GIT, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}"],
        cwd=release.remote,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def release(tmp_path) -> Release:
    return Release(tmp_path)


# --------------------------------------------------------------- the happy path
def test_tag_is_created_on_the_given_commit_and_verified(release):
    result = release.run("v1.2.2", release.sha)
    assert result.returncode == 0, result.stdout + result.stderr
    assert remote_tag(release, "v1.2.2") == release.sha
    assert "attempt 1 of 5: push accepted" in result.stdout
    assert f"verified with git ls-remote: origin has v1.2.2 on {release.sha}" in (
        result.stdout
    )


def test_the_given_commit_wins_over_head(release):
    # A later local commit (never pushed) must not get the tag.
    release.commit("local only")
    result = release.run("v1.2.2", release.sha)
    assert result.returncode == 0, result.stdout + result.stderr
    assert remote_tag(release, "v1.2.2") == release.sha


def test_a_tag_already_on_the_remote_at_that_commit_is_a_no_op(release):
    git(release.work, "tag", "v1.2.2", release.sha)
    git(release.work, "push", "-q", "origin", "v1.2.2")
    result = release.run("v1.2.2", release.sha)
    assert result.returncode == 0
    assert "already has v1.2.2 on" in result.stdout
    assert "attempt" not in result.stdout


def test_a_tag_on_another_commit_is_refused_and_left_alone(release):
    old = git(release.work, "rev-parse", "HEAD~1")
    git(release.work, "tag", "v1.2.2", old)
    git(release.work, "push", "-q", "origin", "v1.2.2")
    git(release.work, "tag", "-d", "v1.2.2")
    result = release.run("v1.2.2", release.sha)
    assert result.returncode == 1
    assert f"already has v1.2.2 on {old}, not on {release.sha}" in result.stdout
    assert remote_tag(release, "v1.2.2") == old


def test_a_local_tag_on_another_commit_is_refused(release):
    git(release.work, "tag", "v1.2.2", "HEAD~1")
    result = release.run("v1.2.2", release.sha)
    assert result.returncode == 1
    assert "The local tag v1.2.2 points at" in result.stdout
    assert remote_tag(release, "v1.2.2") == ""


@pytest.mark.parametrize(
    "args",
    [
        ("1.2.2", "SHA"),
        ("v1.2", "SHA"),
        ("v1.2.2", "abc123"),
        ("v1.2.2", "0" * 40),
    ],
)
def test_wrong_arguments_exit_2(release, args):
    args = tuple(release.sha if a == "SHA" else a for a in args)
    result = release.run(*args)
    assert result.returncode == 2
    assert remote_tag(release, "v1.2.2") == ""


def test_attempts_are_bounded(release):
    result = release.run("v1.2.2", release.sha, RELEASE_TAG_ATTEMPTS="0")
    assert result.returncode == 2
    result = release.run("v1.2.2", release.sha, RELEASE_TAG_ATTEMPTS="100")
    assert result.returncode == 2


# ------------------------------------------- the v1.2.2 failure and its retry
def test_missing_necessary_objects_is_the_answer_git_gives(release):
    # The failure of run 44499441432, made locally: one plain push, no retry.
    release.hide_commit_on_remote()
    git(release.work, "tag", "v1.2.2", release.sha)
    result = subprocess.run(
        [REAL_GIT, "push", "origin", "v1.2.2"],
        cwd=release.work,
        capture_output=True,
        text=True,
        env=base_env(release.tmp),
    )
    assert result.returncode != 0
    assert "[remote rejected] v1.2.2 -> v1.2.2 (missing necessary objects)" in (
        result.stderr
    )


def test_a_lasting_rejection_fails_with_the_recovery_named(release):
    release.hide_commit_on_remote()
    result = release.run("v1.2.2", release.sha, RELEASE_TAG_ATTEMPTS="3")
    assert result.returncode == 1
    out = result.stdout
    assert out.count("push refused") == 3
    assert "attempt 3 of 3: push refused" in out
    assert "missing necessary objects" in result.stderr
    error = [line for line in out.splitlines() if line.startswith("::error::")]
    assert len(error) == 1
    assert f"Tag v1.2.2 was not pushed to commit {release.sha}" in error[0]
    assert f"target {release.sha}" in error[0]
    assert "publish_existing_tag=v1.2.2" in error[0]
    assert "The tag push failed" in error[0]
    assert remote_tag(release, "v1.2.2") == ""


def test_the_waits_grow_with_each_attempt(release):
    release.hide_commit_on_remote()
    result = release.run(
        "v1.2.2", release.sha, RELEASE_TAG_ATTEMPTS="3", RELEASE_TAG_DELAY="0"
    )
    assert "next attempt in 0 s" in result.stdout
    # The arithmetic of the wait: delay times the attempt number.
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'sleep "$((delay * attempt))"' in text
    assert 'attempts="${RELEASE_TAG_ATTEMPTS:-5}" delay="${RELEASE_TAG_DELAY:-5}"' in (
        text
    )


def make_flaky_git(release: Release, saved: Path, fail_pushes: int) -> Path:
    """A git on PATH that puts the remote's object back after N refused pushes."""
    bin_dir = release.tmp / "bin"
    bin_dir.mkdir()
    counter = release.tmp / "pushes"
    counter.write_text("0", encoding="utf-8")
    target = release.object_path(release.sha)
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'for a in "$@"; do\n'
        '  if [ "$a" = push ]; then\n'
        f'    n=$(( $(cat "{counter}") + 1 )); echo "$n" > "{counter}"\n'
        f'    if [ "$n" -gt {fail_pushes} ] && [ ! -e "{target}" ]; then\n'
        f'      mkdir -p "{target.parent}"; cp "{saved}" "{target}"\n'
        "    fi\n"
        "    break\n"
        "  fi\n"
        "done\n"
        f'exec "{REAL_GIT}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return bin_dir


def test_a_passing_rejection_is_retried_and_the_tag_lands(release):
    saved = release.hide_commit_on_remote()
    bin_dir = make_flaky_git(release, saved, fail_pushes=2)
    path = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}"
    result = release.run("v1.2.2", release.sha, PATH=path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "attempt 1 of 5: push refused" in result.stdout
    assert "attempt 2 of 5: push refused" in result.stdout
    assert "attempt 3 of 5: push accepted" in result.stdout
    assert "missing necessary objects" in result.stderr
    assert "::error::" not in result.stdout
    assert remote_tag(release, "v1.2.2") == release.sha


# --------------------------------------------------------- release.yml wiring
def release_steps() -> dict:
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    return {step["name"]: step for step in workflow["jobs"]["release"]["steps"]}


def test_bump_step_writes_the_pushed_commit_as_its_sha_output():
    step = release_steps()["Commit and push version.json changes"]
    assert step["id"] == "bump"
    lines = step["run"].splitlines()
    push = max(i for i, line in enumerate(lines) if "git push origin main" in line)
    out = [i for i, line in enumerate(lines) if 'echo "sha=$(git rev-parse HEAD)"' in line]
    assert len(out) == 1 and out[0] > push
    # After the closing "fi" of the commit branch: also written when there
    # was nothing to commit (then HEAD is the checked-out tip of main).
    closing = max(i for i, line in enumerate(lines) if line.strip() == "fi")
    assert push < closing < out[0]
    assert lines[out[0]] == lines[out[0]].lstrip()


def test_tag_step_calls_the_script_with_the_bump_sha():
    steps = release_steps()
    names = list(steps)
    assert names.index("Create Git Tag") == names.index(
        "Commit and push version.json changes"
    ) + 1
    step = steps["Create Git Tag"]
    assert step["env"]["RELEASE_SHA"] == "${{ steps.bump.outputs.sha }}"
    assert step["env"]["TAG_NAME"] == "${{ steps.version.outputs.tag_name }}"
    run = step["run"]
    assert 'bash .github/scripts/release-tag.sh "$TAG_NAME" "$RELEASE_SHA"' in run
    assert "git tag " not in run and "git push" not in run
