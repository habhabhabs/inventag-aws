"""Docs archiving script: the snapshot check and the shallow-clone fetch.

``.github/scripts/sync-doc-versions.sh`` archives a docs version for each
release tag. These tests run it offline in a temporary git repository, with a
fake ``npm`` standing in for ``docusaurus docs:version`` and a fake ``node``
for the stamp step. They need ``git``, ``bash`` and ``jq``. They prove the two
branches that were rewritten from ``A && B || C`` to if/else.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "sync-doc-versions.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("git") is None,
    reason="needs git and jq",
)

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

# Fake docusaurus: `npm run docusaurus -- docs:version X` makes the snapshot
# unless FAKE_NPM_MODE says otherwise.
FAKE_NPM = """#!/usr/bin/env bash
version="${@: -1}"
case "${FAKE_NPM_MODE:-ok}" in
  ok)
    mkdir -p "versioned_docs/version-$version"
    cp -r ../docs/. "versioned_docs/version-$version/"
    echo '{}' > "versioned_sidebars/version-$version-sidebars.json" ;;
  no-docs) : ;;
  no-sidebar)
    mkdir -p "versioned_docs/version-$version"
    cp -r ../docs/. "versioned_docs/version-$version/" ;;
esac
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **GIT_ENV},
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A repository with docs at tag v1.0.0 and the current version 1.1.0."""
    repo = tmp_path / "source"
    (repo / "docs").mkdir(parents=True)
    (repo / "website").mkdir()
    git(repo, "init", "-q", "-b", "main")
    for number in range(6):
        (repo / "docs" / f"page{number}.md").write_text(f"page {number}\n")
    for sidebar in ("sidebars.ts", "sidebars.js"):
        (repo / "website" / sidebar).write_text("module.exports = {};\n")
    locale = repo / "website/i18n/fr/docusaurus-plugin-content-docs"
    locale.mkdir(parents=True)
    (locale / "current.json").write_text(
        '{"version.label": {"message": "Next"}, "sidebar": {"message": "x"}}\n'
    )
    (repo / "version.json").write_text('{"version": "1.1.0"}\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "docs v1.0.0")
    git(repo, "tag", "v1.0.0")
    (repo / "docs" / "page0.md").write_text("changed\n")
    git(repo, "commit", "-qam", "docs after the tag")
    return repo


def run_script(repo: Path, tmp_path: Path, mode: str = "ok", offline: str = "1"):
    fakes = tmp_path / "fakes"
    fakes.mkdir(exist_ok=True)
    for name, body in (("npm", FAKE_NPM), ("node", "#!/usr/bin/env bash\n")):
        tool = fakes / name
        tool.write_text(body)
        tool.chmod(0o755)
    env = {
        **os.environ,
        **GIT_ENV,
        "PATH": f"{fakes}{os.pathsep}{os.environ['PATH']}",
        "FAKE_NPM_MODE": mode,
        "SYNC_DOCS_OFFLINE": offline,
    }
    return subprocess.run(
        ["bash", str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True
    )


def test_archives_a_tag_when_the_snapshot_is_created(source, tmp_path):
    result = run_script(source, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Archiving v1.0.0" in result.stdout
    assert (source / "website/versioned_docs/version-1.0.0/page1.md").is_file()
    assert (source / "website/versioned_sidebars/version-1.0.0-sidebars.json").is_file()
    # the current docs are put back
    assert (source / "docs/page0.md").read_text() == "changed\n"


@pytest.mark.parametrize("mode", ["no-docs", "no-sidebar"])
def test_fails_and_restores_docs_when_a_snapshot_part_is_missing(
    source, tmp_path, mode
):
    result = run_script(source, tmp_path, mode=mode)
    assert result.returncode == 1
    assert "snapshot of v1.0.0 was not created" in result.stdout
    assert (source / "docs/page0.md").read_text() == "changed\n"
    assert not (
        source / "website/versioned_sidebars/version-1.0.0-sidebars.json"
    ).exists()


def test_a_shallow_clone_is_unshallowed_and_a_full_clone_is_left_alone(
    source, tmp_path
):
    shallow = tmp_path / "shallow"
    subprocess.run(
        [
            "git",
            "clone",
            "-q",
            "--depth=1",
            "--no-local",
            "--tags",
            f"file://{source}",
            str(shallow),
        ],
        check=True,
        env={**os.environ, **GIT_ENV},
    )
    assert git(shallow, "rev-parse", "--is-shallow-repository") == "true"
    result = run_script(shallow, tmp_path, offline="0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(shallow, "rev-parse", "--is-shallow-repository") == "false"
    # not shallow and no remote: the fetches fail, the run goes on
    full = run_script(source, tmp_path, offline="0")
    assert full.returncode == 0, full.stdout + full.stderr
