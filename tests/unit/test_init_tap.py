"""B4: ``scripts/packaging/init_tap.sh`` and the files of the tap directory.

``init_tap.sh`` lays out the tap repository (``habhabhabs/homebrew-inventag``)
in an empty directory and makes one local commit. It never pushes and never
calls ``gh``: it prints the two commands the owner runs. The tests run the real
script with a ``git`` shim that records every call (a push, a fetch or a clone
would show up) and a ``gh`` shim that must never run.
"""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "packaging" / "init_tap.sh"
TAP = ROOT / "packaging" / "homebrew-tap"
INSTALL_PAGE = (
    "https://habhabhabs.github.io/inventag-aws/docs/getting-started/installation"
)
VERSION_RX = re.compile(r"(?<![\w.])v?\d+\.\d+\.\d+(?![\w.])")
REAL_GIT = shutil.which("git")
REAL_BASH = shutil.which("bash")


@pytest.fixture()
def shims(tmp_path):
    """A folder with a git shim that logs its arguments and a gh shim that fails."""
    bin_dir = tmp_path / "shims"
    bin_dir.mkdir()
    log = tmp_path / "git-calls.log"
    git = bin_dir / "git"
    git.write_text(
        f'#!{REAL_BASH}\necho "$*" >> "{log}"\nexec "{REAL_GIT}" "$@"\n', "utf-8"
    )
    gh = bin_dir / "gh"
    gh.write_text(f'#!{REAL_BASH}\necho "gh $*" >> "{log}"\nexit 99\n', "utf-8")
    for tool in (git, gh):
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return bin_dir, log


def run(tmp_path, shims, *args, identity=True):
    bin_dir, _ = shims
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{Path(REAL_BASH).parent}{os.pathsep}/usr/bin:/bin",
        "HOME": str(home),
        "LANG": "C.UTF-8",
    }
    if identity:
        env.update(
            GIT_AUTHOR_NAME="Test Owner",
            GIT_AUTHOR_EMAIL="owner@example.invalid",
            GIT_COMMITTER_NAME="Test Owner",
            GIT_COMMITTER_EMAIL="owner@example.invalid",
        )
    return subprocess.run(
        [REAL_BASH, str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def git_calls(shims):
    _, log = shims
    return log.read_text("utf-8").splitlines() if log.exists() else []


def tree(path: Path):
    return sorted(
        str(p.relative_to(path))
        for p in path.rglob("*")
        if ".git" not in p.relative_to(path).parts
    )


# ------------------------------------------------------------------ success
def test_an_empty_directory_gets_the_tap_layout(tmp_path, shims):
    target = tmp_path / "tap"
    target.mkdir()
    done = run(tmp_path, shims, target)
    assert done.returncode == 0, done.stderr
    assert (target / "README.md").read_text("utf-8") == (TAP / "README.md").read_text(
        "utf-8"
    )
    assert (target / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
    assert (target / ".github" / "workflows" / "ci.yml").is_file()
    assert (target / "Formula").is_dir()


def test_a_directory_that_does_not_exist_is_made(tmp_path, shims):
    target = tmp_path / "a" / "b" / "tap"
    done = run(tmp_path, shims, target)
    assert done.returncode == 0, done.stderr
    assert (target / "README.md").is_file()


def test_the_template_is_not_copied_as_a_formula(tmp_path, shims):
    # A formula with {{...}} in it would break every install of the tap.
    target = tmp_path / "tap"
    assert run(tmp_path, shims, target).returncode == 0
    assert not (target / "Formula" / "inventag.rb").exists()
    assert "Formula/.gitkeep" in tree(target)


def test_one_local_commit_on_main_without_trailers(tmp_path, shims):
    target = tmp_path / "tap"
    assert run(tmp_path, shims, target).returncode == 0
    log = subprocess.run(
        [REAL_GIT, "-C", str(target), "log", "--format=%an <%ae>%n%B", "main"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert log.count("Test Owner") == 1
    assert "Co-Authored-By" not in log and "Claude" not in log
    status = subprocess.run(
        [REAL_GIT, "-C", str(target), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert status == ""


def test_the_remote_is_set_but_nothing_goes_over_the_network(tmp_path, shims):
    target = tmp_path / "tap"
    assert run(tmp_path, shims, target).returncode == 0
    url = subprocess.run(
        [REAL_GIT, "-C", str(target), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert url == "https://github.com/habhabhabs/homebrew-inventag.git"
    calls = git_calls(shims)
    assert calls, "the git shim was not used"
    for word in ("push", "fetch", "pull", "clone", "ls-remote"):
        assert not [c for c in calls if re.search(rf"(^|\s){word}(\s|$)", c)], word
    assert not [c for c in calls if c.startswith("gh ")]


def test_the_two_commands_of_the_owner_are_printed_not_run(tmp_path, shims):
    target = tmp_path / "tap"
    done = run(tmp_path, shims, target)
    lines = [ln.strip() for ln in done.stdout.splitlines()]
    assert "gh repo create habhabhabs/homebrew-inventag --public" in lines
    assert f"git -C {target} push -u origin main" in lines
    assert lines.index(
        "gh repo create habhabhabs/homebrew-inventag --public"
    ) < lines.index(f"git -C {target} push -u origin main")
    assert "nothing was pushed" in done.stdout


def test_a_rendered_formula_can_be_added(tmp_path, shims):
    formula = tmp_path / "rendered.rb"
    formula.write_text('class Inventag < Formula\n  version "9.8.7"\nend\n', "utf-8")
    target = tmp_path / "tap"
    done = run(tmp_path, shims, target, "--formula", formula)
    assert done.returncode == 0, done.stderr
    assert (target / "Formula" / "inventag.rb").read_text("utf-8") == formula.read_text(
        "utf-8"
    )
    assert not (target / "Formula" / ".gitkeep").exists()


def test_a_formula_that_is_still_a_template_is_refused(tmp_path, shims):
    target = tmp_path / "tap"
    done = run(tmp_path, shims, target, "--formula", TAP / "Formula" / "inventag.rb")
    assert done.returncode == 2
    assert "template" in done.stderr
    assert not target.exists()


# ------------------------------------------------------------------ refusals
@pytest.mark.parametrize("name", ["notes.txt", ".hidden", ".git"])
def test_a_directory_with_anything_in_it_is_refused(tmp_path, shims, name):
    target = tmp_path / "tap"
    target.mkdir()
    entry = target / name
    if name == ".git":
        entry.mkdir()
    else:
        entry.write_text("mine\n", "utf-8")
    before = tree(target)
    done = run(tmp_path, shims, target)
    assert done.returncode == 2
    assert done.stderr.startswith("init_tap.sh: ")
    assert "not empty" in done.stderr
    assert done.stdout == ""
    assert tree(target) == before
    assert git_calls(shims) == []


def test_a_path_that_is_a_file_is_refused(tmp_path, shims):
    target = tmp_path / "tap"
    target.write_text("x\n", "utf-8")
    done = run(tmp_path, shims, target)
    assert done.returncode == 2 and "not a directory" in done.stderr
    assert target.read_text("utf-8") == "x\n"


def test_the_tap_directory_of_the_repository_is_refused(tmp_path, shims):
    # Laying the tap out inside the source tree would copy it into itself.
    done = run(tmp_path, shims, TAP)
    assert done.returncode == 2
    assert not (TAP / ".git").exists()


def test_no_argument_prints_the_usage_and_exits_2(tmp_path, shims):
    done = run(tmp_path, shims)
    assert done.returncode == 2
    assert "usage" in done.stderr.lower()


def test_an_unknown_option_exits_2(tmp_path, shims):
    done = run(tmp_path, shims, tmp_path / "tap", "--push")
    assert done.returncode == 2
    assert not (tmp_path / "tap").exists()


def test_without_a_git_identity_nothing_is_written(tmp_path, shims):
    target = tmp_path / "tap"
    done = run(tmp_path, shims, target, identity=False)
    assert done.returncode == 2
    assert "git config" in done.stderr
    assert not target.exists()


# ------------------------------------------------------- the files of the tap
def test_the_readme_states_the_install_command_and_the_limits():
    text = (TAP / "README.md").read_text("utf-8")
    assert "brew install habhabhabs/inventag/inventag" in text
    assert "Apple Silicon" in text and "Intel Mac" in text
    assert INSTALL_PAGE in text
    assert "inventag selftest" in text


def test_the_readme_states_the_lgpl_libiconv_and_where_the_source_is():
    text = (TAP / "README.md").read_text("utf-8")
    assert "libiconv" in text and "LGPL-2.1" in text
    assert "lxml" in text
    assert "THIRD-PARTY-LICENSES.txt" in text
    assert "https://www.gnu.org/software/libiconv/" in text
    assert "macOS and Linux" in text
    assert "not legal advice" in text.lower()


def test_the_readme_carries_the_caveat_and_no_forbidden_words():
    text = (TAP / "README.md").read_text("utf-8")
    assert "Not verified against macOS outside a GitHub runner" in text
    for word in ("compliant", "certified", "enforce"):
        assert word not in text.lower()


def test_no_file_of_the_tap_directory_holds_a_version_number():
    found = []
    for path in sorted(TAP.rglob("*")):
        if path.is_file():
            for number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
                if VERSION_RX.search(line):
                    found.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not found, "\n".join(found)


@pytest.fixture(scope="module")
def tap_ci():
    path = TAP / ".github" / "workflows" / "ci.yml"
    return path.read_text("utf-8"), yaml.safe_load(path.read_text("utf-8"))


def test_the_tap_workflow_is_read_only_and_runs_on_literal_labels(tap_ci):
    text, doc = tap_ci
    triggers = doc.get("on", doc.get(True))
    assert set(triggers) <= {"push", "pull_request", "workflow_dispatch"}
    assert "pull_request_target" not in text
    assert doc["permissions"] == {"contents": "read"}
    labels = set()
    for job in doc["jobs"].values():
        assert "secrets" not in job
        runs_on = job["runs-on"]
        assert isinstance(runs_on, str) and "${{" not in runs_on
        labels.add(runs_on)
    assert {"macos-15", "ubuntu-24.04"} <= labels


def test_the_tap_workflow_pins_every_action_by_commit_and_has_no_inline_expression(
    tap_ci,
):
    text, doc = tap_ci
    uses = re.findall(r"uses:\s*(\S+)", text)
    assert uses, "no action used"
    assert all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u) for u in uses), uses
    for job in doc["jobs"].values():
        for step in job["steps"]:
            assert "${{" not in step.get("run", "")


def test_the_tap_workflow_checks_style_audit_install_and_test(tap_ci):
    text, _ = tap_ci
    for command in (
        "brew style",
        "brew audit --strict",
        "brew install habhabhabs/inventag/inventag",
        "brew test habhabhabs/inventag/inventag",
        "inventag selftest",
    ):
        assert command in text, command


@pytest.mark.skipif(
    shutil.which("actionlint") is None,
    reason="actionlint is not installed on this machine",
)
def test_the_tap_workflow_passes_actionlint():
    done = subprocess.run(
        [
            shutil.which("actionlint"),
            "-pyflakes=",
            str(TAP / ".github" / "workflows" / "ci.yml"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.skipif(
    shutil.which("shellcheck") is None,
    reason="shellcheck is not installed on this machine",
)
def test_init_tap_passes_shellcheck():
    done = subprocess.run(
        [shutil.which("shellcheck"), str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout


def test_init_tap_has_no_network_command():
    text = SCRIPT.read_text("utf-8")
    code = [
        ln
        for ln in text.splitlines()
        if not ln.lstrip().startswith(("#", "echo", "printf"))
    ]
    for word in ("curl", "wget", "push", "fetch", "clone", "gh "):
        assert not [ln for ln in code if re.search(rf"\b{word}", ln)], word
