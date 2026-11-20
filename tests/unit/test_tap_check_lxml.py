"""B4b: the check that Homebrew leaves the lxml extension modules unchanged.

Architect triage row 15 (Decision 2, condition 2: lxml's modules stay separate,
unmodified files). ``packaging/homebrew-tap/check_lxml.sh <archive> <root>``
compares the sha256 of every ``lxml/*.so`` in the release archive with the file
at the same place under the installed root (``$(brew --prefix inventag)/libexec``).
There is no Homebrew here, so the tests build small archives with ``tar``.
"""

import io
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TAP = ROOT / "packaging" / "homebrew-tap"
SCRIPT = TAP / "check_lxml.sh"
BASH = shutil.which("bash")
SO = "_internal/lxml/etree.cpython-312-x86_64-linux-gnu.so"
SO2 = "_internal/lxml/objectify.cpython-312-x86_64-linux-gnu.so"


def make_archive(path: Path, files: dict) -> Path:
    """Like the release archive: one top folder, ``inventag/``."""
    with tarfile.open(path, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(f"inventag/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def install(root: Path, files: dict) -> Path:
    for name, data in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


def run(*args, env=None):
    env = env or {"PATH": "/usr/bin:/bin:/usr/local/bin", "LANG": "C.UTF-8"}
    return subprocess.run(
        [BASH, str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


FILES = {
    SO: b"etree binary",
    SO2: b"objectify binary",
    "inventag": b"launcher",
    "_internal/other/native.so": b"not lxml",
}


@pytest.fixture()
def pair(tmp_path):
    archive = make_archive(tmp_path / "a.tar.gz", FILES)
    root = install(tmp_path / "libexec", FILES)
    return archive, root


def test_unchanged_lxml_files_pass_and_each_is_listed(pair):
    done = run(*pair)
    assert done.returncode == 0, done.stdout + done.stderr
    assert sorted(re.findall(r"^ok (\S+)$", done.stdout, re.M)) == sorted([SO, SO2])


def test_a_changed_lxml_file_fails_and_is_named(pair):
    archive, root = pair
    (root / SO).write_bytes(b"re-signed by someone")
    done = run(archive, root)
    assert done.returncode == 1
    assert f"DIFFERENT {SO}" in done.stdout
    assert f"ok {SO2}" in done.stdout


def test_a_missing_lxml_file_fails_and_is_named(pair):
    archive, root = pair
    (root / SO2).unlink()
    done = run(archive, root)
    assert done.returncode == 1 and f"MISSING {SO2}" in done.stdout


def test_an_extra_lxml_file_in_the_install_fails(pair):
    archive, root = pair
    (root / "_internal/lxml/new.so").write_bytes(b"x")
    done = run(archive, root)
    assert done.returncode == 1 and "EXTRA _internal/lxml/new.so" in done.stdout


def test_a_change_outside_lxml_is_not_this_checks_business(pair):
    archive, root = pair
    (root / "_internal/other/native.so").write_bytes(b"relinked")
    assert run(archive, root).returncode == 0


def test_an_archive_without_lxml_modules_fails_because_it_proves_nothing(tmp_path):
    archive = make_archive(tmp_path / "a.tar.gz", {"inventag": b"x"})
    root = install(tmp_path / "libexec", {"inventag": b"x"})
    done = run(archive, root)
    assert done.returncode == 1 and "no lxml" in done.stdout + done.stderr


def test_bad_usage_exits_2(tmp_path):
    assert run().returncode == 2
    assert run(tmp_path / "nope.tar.gz", tmp_path).returncode == 2
    archive = make_archive(tmp_path / "a.tar.gz", FILES)
    assert run(archive, tmp_path / "missing").returncode == 2


def test_the_check_makes_no_network_call_and_leaves_no_temporary_file(pair, tmp_path):
    text = SCRIPT.read_text("utf-8")
    code = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    for word in ("curl", "wget", "brew ", "git "):
        assert not any(word in ln for ln in code), word
    tmp = tmp_path / "scratch"
    tmp.mkdir()
    env = {"PATH": "/usr/bin:/bin", "TMPDIR": str(tmp)}
    done = run(*pair, env=env)
    assert done.returncode == 0, done.stderr
    assert list(tmp.iterdir()) == []


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="no shellcheck")
def test_the_check_passes_shellcheck():
    done = subprocess.run(
        [shutil.which("shellcheck"), str(SCRIPT)], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stdout


def test_the_tap_workflow_runs_the_check_on_both_systems():
    path = TAP / ".github" / "workflows" / "ci.yml"
    doc = yaml.safe_load(path.read_text("utf-8"))
    assert len(doc["jobs"]) == 2
    for job in doc["jobs"].values():
        runs = "\n".join(s.get("run", "") for s in job["steps"])
        assert "brew --cache" in runs
        assert "libexec" in runs
        assert ("sha256sum" in runs or "shasum -a 256" in runs) and "lxml" in runs
        assert runs.index("brew install") < runs.index("lxml")
        assert runs.index("lxml") < runs.index("brew uninstall")


def test_the_readme_says_the_check_is_not_verified_against_homebrew():
    text = " ".join((TAP / "README.md").read_text("utf-8").split())
    assert "Not verified against a Homebrew install: that Homebrew leaves" in text
