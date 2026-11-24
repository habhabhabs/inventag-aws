"""B6 fix 7 (v1.4.1): the release upload also fails on files it did not attach.

After ``gh release upload --clobber`` the publish job checked only for files
that were missing. A re-run with other file names (for example after a version
fix) left the old files beside the new SHA256SUMS. Now a file on the release
that is neither in this upload nor one of release.yml's two source archives
(``inventag-aws-<version>.tar.gz`` and ``.zip``) fails the job.

The step's shell runs against a stub ``gh``; nothing calls GitHub.
"""

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
JOBS = yaml.safe_load((ROOT / ".github/workflows/package.yml").read_text("utf-8"))[
    "jobs"
]
TAG = "v1.4.1"
FILES = ["SHA256SUMS", "inventag_1.4.1_amd64.deb", "inventag-1.4.1-macos-arm64.tar.gz"]
SOURCES = ["inventag-aws-1.4.1.tar.gz", "inventag-aws-1.4.1.zip"]


def _upload_step():
    (step,) = [
        s
        for s in JOBS["publish"]["steps"]
        if s.get("name") == "Upload to the GitHub release of the tag"
    ]
    return step["run"]


def _run(tmp_path, on_release):
    release = tmp_path / "release"
    release.mkdir()
    for name in FILES:
        (release / name).write_text(name, encoding="utf-8")
    assets = tmp_path / "assets.txt"
    assets.write_text("".join(f"{n}\n" for n in on_release), encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/bash\n"
        f'echo "$@" >> "{tmp_path}/gh.log"\n'
        f'case "$*" in *--json*) cat "{assets}";; esac\n',
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", _upload_step()],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "RUNNER_TEMP": str(tmp_path),
            "TAG": TAG,
        },
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_uploaded_files_and_the_two_source_archives_pass(tmp_path):
    result = _run(tmp_path, FILES + SOURCES)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"3 files are on the release {TAG}." in result.stdout


def test_a_missing_file_still_fails(tmp_path):
    result = _run(tmp_path, FILES[1:] + SOURCES)
    assert result.returncode == 1
    assert "::error::Not on the release after the upload: SHA256SUMS" in result.stdout


def test_a_stale_file_from_an_earlier_run_fails(tmp_path):
    stale = "inventag_1.4.0_amd64.deb"
    result = _run(tmp_path, FILES + SOURCES + [stale])
    assert result.returncode == 1
    assert (
        f"::error::On the release but not in this upload: {stale}. Delete it "
        f'(gh release delete-asset {TAG} "{stale}") and run the job again.'
    ) in result.stdout


def test_a_source_archive_of_another_version_fails(tmp_path):
    other = "inventag-aws-1.4.0.zip"
    result = _run(tmp_path, FILES + SOURCES + [other])
    assert result.returncode == 1
    assert f"On the release but not in this upload: {other}." in result.stdout


def test_a_file_name_with_a_space_is_named_whole(tmp_path):
    # security review v1.4.1 finding 5: the loop must not split a name
    stale = "old notes *.txt"
    result = _run(tmp_path, FILES + SOURCES + [stale])
    assert result.returncode == 1
    errors = [l for l in result.stdout.splitlines() if l.startswith("::error::")]
    assert errors == [
        f"::error::On the release but not in this upload: {stale}. Delete it "
        f'(gh release delete-asset {TAG} "{stale}") and run the job again.'
    ]
