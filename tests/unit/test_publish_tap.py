"""B4c: ``scripts/packaging/publish_tap.sh`` (architect plan homebrew-publish,
sections 2 and 5).

The script writes the rendered formula to ``Formula/inventag.rb`` of the
Homebrew tap and pushes one commit to the tap's ``main``. The tests run the
real script against local bare repositories (``file://`` URLs): no network,
no token. A ``git`` shim records every call, so a test can prove that the
token never reaches a git argument or a remote URL.
"""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "packaging" / "publish_tap.sh"
REAL_GIT = shutil.which("git")
REAL_BASH = shutil.which("bash")
REPO = "habhabhabs/homebrew-inventag"
TOKEN = "github_pat_TESTTOKEN0123456789"
SHA = "a" * 64


def _formula(version, extra=""):
    return (
        "class Inventag < Formula\n"
        f'  url "https://example.invalid/inventag-{version}-darwin-arm64.tar.gz"\n'
        f'  sha256 "{SHA}"\n'
        f"{extra}"
        "end\n"
    )


def _git(*args, cwd=None, env=None):
    return subprocess.run(
        [REAL_GIT, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _identity_env(home):
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Seed",
        "GIT_AUTHOR_EMAIL": "seed@example.invalid",
        "GIT_COMMITTER_NAME": "Seed",
        "GIT_COMMITTER_EMAIL": "seed@example.invalid",
    }


class Tap:
    """A bare tap repository at <base>/<owner>/<name>.git with a main branch."""

    def __init__(self, tmp_path, formula=None, gitkeep=True):
        self.tmp = tmp_path
        self.base = tmp_path / "remote"
        self.bare = self.base / (REPO + ".git")
        self.bare.parent.mkdir(parents=True)
        self.home = tmp_path / "seed-home"
        self.home.mkdir()
        env = _identity_env(self.home)
        _git("init", "-q", "--bare", "-b", "main", str(self.bare), env=env)
        seed = tmp_path / "seed"
        _git("init", "-q", "-b", "main", str(seed), env=env)
        (seed / "README.md").write_text("# tap\n", "utf-8")
        (seed / "Formula").mkdir()
        if gitkeep:
            (seed / "Formula" / ".gitkeep").write_text("", "utf-8")
        if formula is not None:
            (seed / "Formula" / "inventag.rb").write_text(formula, "utf-8")
        _git("add", "-A", cwd=seed, env=env)
        _git("commit", "-q", "-m", "seed", cwd=seed, env=env)
        _git("push", "-q", str(self.bare), "main", cwd=seed, env=env)
        self.env = env

    def head(self):
        return _git("rev-parse", "main", cwd=self.bare, env=self.env)

    def show(self, path, rev="main"):
        return _git("show", f"{rev}:{path}", cwd=self.bare, env=self.env)

    def files(self, rev="main"):
        out = _git("ls-tree", "-r", "--name-only", rev, cwd=self.bare, env=self.env)
        return out.splitlines()

    def log(self, fmt, count=1):
        return _git(
            "log", f"--format={fmt}", f"-{count}", "main", cwd=self.bare, env=self.env
        )

    def count(self):
        return int(_git("rev-list", "--count", "main", cwd=self.bare, env=self.env))

    def hook(self, body):
        hook = self.bare / "hooks" / "pre-receive"
        hook.write_text(f"#!{REAL_BASH}\n{body}", "utf-8")
        hook.chmod(0o755)


@pytest.fixture()
def shims(tmp_path):
    bin_dir = tmp_path / "shims"
    bin_dir.mkdir()
    log = tmp_path / "git-calls.log"
    git = bin_dir / "git"
    git.write_text(
        f"#!{REAL_BASH}\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        f'env | grep -v "^HOMEBREW_TAP_TOKEN=" >> "{log}.env"\n'
        f'exec "{REAL_GIT}" "$@"\n',
        "utf-8",
    )
    gh = bin_dir / "gh"
    gh.write_text(f'#!{REAL_BASH}\necho "gh $*" >> "{log}"\nexit 99\n', "utf-8")
    for tool in (git, gh):
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return bin_dir, log


def run(tmp_path, shims, *args, base=None, token=None, extra_env=None):
    bin_dir, _ = shims
    home = tmp_path / "run-home"
    home.mkdir(exist_ok=True)
    env = {
        "PATH": os.pathsep.join(
            [str(bin_dir), str(Path(REAL_BASH).parent), "/usr/bin", "/bin"]
        ),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "TMPDIR": str(tmp_path),
    }
    if base is not None:
        env["PUBLISH_TAP_BASE_URL"] = base
    if token is not None:
        env["HOMEBREW_TAP_TOKEN"] = token
    env.update(extra_env or {})
    return subprocess.run(
        [REAL_BASH, str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def publish(tmp_path, shims, tap, version="1.4.1", text=None, **kw):
    formula = tmp_path / f"inventag-{version}.rb"
    formula.write_text(text if text is not None else _formula(version), "utf-8")
    return run(
        tmp_path,
        shims,
        "--formula",
        str(formula),
        "--version",
        version,
        "--repo",
        REPO,
        base=f"file://{tap.base}",
        **kw,
    )


# ---- the first publish ------------------------------------------------------


def test_the_formula_is_written_committed_and_pushed_to_main(tmp_path, shims):
    tap = Tap(tmp_path)
    before = tap.count()
    result = publish(tmp_path, shims, tap)
    assert result.returncode == 0, result.stdout + result.stderr
    assert tap.count() == before + 1
    assert tap.show("Formula/inventag.rb") + "\n" == _formula("1.4.1")
    # The placeholder file of an empty tap goes with the first formula.
    assert "Formula/.gitkeep" not in tap.files()
    assert "README.md" in tap.files()
    # The run names the tap commit, so the release log links to its checks.
    sha = tap.head()
    assert f"file://{tap.base}/{REPO}/commit/{sha}" in result.stdout
    assert "Tap checks" in result.stdout


def test_the_commit_is_alex_with_the_subject_only_and_no_trailer(tmp_path, shims):
    tap = Tap(tmp_path)
    result = publish(tmp_path, shims, tap)
    assert result.returncode == 0, result.stdout + result.stderr
    assert tap.log("%an <%ae>|%cn <%ce>") == (
        "Alex <alex.ng@ollion.com>|Alex <alex.ng@ollion.com>"
    )
    # The whole message is the subject: no body, no trailer of any kind.
    assert tap.log("%B") == "inventag 1.4.1"


def test_the_identity_does_not_come_from_the_runner_git_config(tmp_path, shims):
    tap = Tap(tmp_path)
    home = tmp_path / "run-home"
    home.mkdir()
    (home / ".gitconfig").write_text(
        "[user]\n\tname = Runner\n\temail = runner@example.invalid\n"
        "[commit]\n\tgpgsign = true\n",
        "utf-8",
    )
    result = publish(tmp_path, shims, tap)
    assert result.returncode == 0, result.stdout + result.stderr
    assert tap.log("%an|%cn") == "Alex|Alex"


# ---- an unchanged file, an older version ------------------------------------


def test_the_same_file_again_ends_with_success_and_pushes_nothing(tmp_path, shims):
    tap = Tap(tmp_path, formula=_formula("1.4.1"))
    before = tap.head()
    result = publish(tmp_path, shims, tap)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "already published" in result.stdout
    assert tap.head() == before
    _, log = shims
    assert not [c for c in log.read_text("utf-8").splitlines() if "push" in c.split()]


def test_a_new_formula_of_the_same_version_is_pushed(tmp_path, shims):
    # A re-run after a template fix: same version, other text.
    tap = Tap(tmp_path, formula=_formula("1.4.1"))
    result = publish(tmp_path, shims, tap, text=_formula("1.4.1", "  # fixed\n"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "# fixed" in tap.show("Formula/inventag.rb")


def test_a_newer_version_replaces_the_formula(tmp_path, shims):
    tap = Tap(tmp_path, formula=_formula("1.4.0"), gitkeep=False)
    result = publish(tmp_path, shims, tap, version="1.4.1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "inventag-1.4.1-" in tap.show("Formula/inventag.rb")


@pytest.mark.parametrize("old", ["1.4.2", "1.5.0", "2.0.0", "1.10.0"])
def test_a_version_lower_than_the_taps_is_refused(tmp_path, shims, old):
    # A re-run of an older tag must not take the tap back.
    tap = Tap(tmp_path, formula=_formula(old), gitkeep=False)
    before = tap.head()
    result = publish(tmp_path, shims, tap, version="1.4.1")
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"holds {old}" in result.stderr and "1.4.1" in result.stderr
    assert tap.head() == before


def test_the_version_compare_is_numeric_not_text(tmp_path, shims):
    tap = Tap(tmp_path, formula=_formula("1.9.0"), gitkeep=False)
    result = publish(tmp_path, shims, tap, version="1.10.0")
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_tap_formula_without_a_readable_version_is_refused(tmp_path, shims):
    tap = Tap(tmp_path, formula="class Inventag < Formula\nend\n", gitkeep=False)
    before = tap.head()
    result = publish(tmp_path, shims, tap)
    assert result.returncode == 1
    assert "cannot read the version" in result.stderr
    assert tap.head() == before


# ---- main moved during the run ----------------------------------------------

MOVE_MAIN = (
    # Rejects the first push and, in the same moment, moves main on by one
    # commit, as another push would. Objects are written outside the push's
    # quarantine, so the new commit stays.
    'marker="$(pwd)/moved"\n'
    'if [ ! -e "$marker" ]; then\n'
    '  touch "$marker"\n'
    "  unset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES\n"
    "  export GIT_AUTHOR_NAME=Other GIT_AUTHOR_EMAIL=o@example.invalid\n"
    "  export GIT_COMMITTER_NAME=Other GIT_COMMITTER_EMAIL=o@example.invalid\n"
    "  blob=$(printf 'moved\\n' | git hash-object -w --stdin)\n"
    "  tree=$( (git ls-tree main | grep -v README.md;"
    ' printf "100644 blob %s\\tREADME.md\\n" "$blob") | git mktree)\n'
    '  commit=$(git commit-tree "$tree" -p main -m "other")\n'
    '  git update-ref refs/heads/main "$commit"\n'
    "  exit 1\n"
    "fi\n"
    "{rest}"
)


def test_a_push_refused_because_main_moved_is_tried_once_more_on_the_new_main(
    tmp_path, shims
):
    tap = Tap(tmp_path)
    tap.hook(MOVE_MAIN.format(rest="exit 0\n"))
    result = publish(tmp_path, shims, tap)
    assert result.returncode == 0, result.stdout + result.stderr
    assert tap.log("%s", 2).splitlines() == ["inventag 1.4.1", "other"]
    assert tap.show("README.md") == "moved"
    assert "inventag-1.4.1-" in tap.show("Formula/inventag.rb")


def test_a_second_refused_push_fails_the_run(tmp_path, shims):
    tap = Tap(tmp_path)
    tap.hook(MOVE_MAIN.format(rest="exit 1\n"))
    result = publish(tmp_path, shims, tap)
    assert result.returncode == 1
    assert "was not pushed" in result.stderr
    _, log = shims
    pushes = [c for c in log.read_text("utf-8").splitlines() if "push" in c.split()]
    assert len(pushes) == 2


def test_the_second_try_also_refuses_an_older_version(tmp_path, shims):
    # Main moved to a newer formula between the clone and the push.
    tap = Tap(tmp_path)
    newer = _formula("1.5.0").replace("\n", "\\n")
    tap.hook(
        'marker="$(pwd)/moved"\n'
        'if [ ! -e "$marker" ]; then\n'
        '  touch "$marker"\n'
        "  unset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES\n"
        "  export GIT_AUTHOR_NAME=O GIT_AUTHOR_EMAIL=o@x.invalid GIT_COMMITTER_NAME=O GIT_COMMITTER_EMAIL=o@x.invalid\n"
        f"  blob=$(printf '{newer}' | git hash-object -w --stdin)\n"
        '  sub=$(printf "100644 blob %s\\tinventag.rb\\n" "$blob" | git mktree)\n'
        "  tree=$( (git ls-tree main | grep -v Formula;"
        ' printf "040000 tree %s\\tFormula\\n" "$sub") | git mktree)\n'
        '  commit=$(git commit-tree "$tree" -p main -m "inventag 1.5.0")\n'
        '  git update-ref refs/heads/main "$commit"\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    )
    result = publish(tmp_path, shims, tap, version="1.4.1")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "holds 1.5.0" in result.stderr
    assert tap.log("%s") == "inventag 1.5.0"


# ---- inputs -----------------------------------------------------------------


@pytest.mark.parametrize(
    "repo",
    [
        "habhabhabs/inventag",
        "habhabhabs/homebrew-",
        "homebrew-inventag",
        "a/b/homebrew-c",
        "habhabhabs/homebrew-inv tag",
        "habhabhabs/homebrew-inventag\nx",
        "../homebrew-inventag",
        "",
    ],
)
def test_a_repository_name_outside_the_pattern_is_refused(tmp_path, shims, repo):
    formula = tmp_path / "f.rb"
    formula.write_text(_formula("1.4.1"), "utf-8")
    result = run(
        tmp_path,
        shims,
        "--formula",
        str(formula),
        "--version",
        "1.4.1",
        "--repo",
        repo,
        base="file:///nowhere",
    )
    assert result.returncode == 2, repr(repo)
    assert "owner/homebrew-name" in result.stderr
    _, log = shims
    assert not log.exists()


@pytest.mark.parametrize("version", ["v1.4.1", "1.4", "1.4.1-rc1", ""])
def test_a_version_that_is_not_x_y_z_is_refused(tmp_path, shims, version):
    tap = Tap(tmp_path)
    result = publish(tmp_path, shims, tap, version=version, text=_formula("1.4.1"))
    assert result.returncode == 2
    assert "X.Y.Z" in result.stderr


def test_a_formula_that_still_holds_a_placeholder_is_refused(tmp_path, shims):
    tap = Tap(tmp_path)
    result = publish(
        tmp_path, shims, tap, text=_formula("1.4.1", '  sha256 "{{SHA256_X}}"\n')
    )
    assert result.returncode == 2
    assert "{{" in result.stderr
    assert tap.count() == 1


def test_a_formula_of_another_version_is_refused(tmp_path, shims):
    tap = Tap(tmp_path)
    result = publish(tmp_path, shims, tap, version="1.4.1", text=_formula("1.4.0"))
    assert result.returncode == 2
    assert "inventag-1.4.1-darwin-arm64.tar.gz" in result.stderr


def test_a_missing_formula_file_is_refused(tmp_path, shims):
    result = run(
        tmp_path,
        shims,
        "--formula",
        str(tmp_path / "nope.rb"),
        "--version",
        "1.4.1",
        "--repo",
        REPO,
        base="file:///nowhere",
    )
    assert result.returncode == 2
    assert "does not exist" in result.stderr


def test_a_tap_without_a_main_branch_is_named(tmp_path, shims):
    base = tmp_path / "remote"
    bare = base / (REPO + ".git")
    bare.parent.mkdir(parents=True)
    _git("init", "-q", "--bare", "-b", "main", str(bare), env=_identity_env(tmp_path))
    formula = tmp_path / "f.rb"
    formula.write_text(_formula("1.4.1"), "utf-8")
    result = run(
        tmp_path,
        shims,
        "--formula",
        str(formula),
        "--version",
        "1.4.1",
        "--repo",
        REPO,
        base=f"file://{base}",
    )
    assert result.returncode == 1
    assert "main" in result.stderr


# ---- the token --------------------------------------------------------------


def test_an_https_tap_needs_the_token_and_makes_no_call_without_it(tmp_path, shims):
    formula = tmp_path / "f.rb"
    formula.write_text(_formula("1.4.1"), "utf-8")
    for token in (None, ""):
        result = run(
            tmp_path,
            shims,
            "--formula",
            str(formula),
            "--version",
            "1.4.1",
            "--repo",
            REPO,
            token=token,
        )
        assert result.returncode == 2
        assert "HOMEBREW_TAP_TOKEN" in result.stderr
    _, log = shims
    assert not log.exists()


def test_a_base_url_that_is_neither_https_nor_file_is_refused(tmp_path, shims):
    formula = tmp_path / "f.rb"
    formula.write_text(_formula("1.4.1"), "utf-8")
    for base in ("http://github.com", "ssh://git@github.com", "git@github.com:"):
        result = run(
            tmp_path,
            shims,
            "--formula",
            str(formula),
            "--version",
            "1.4.1",
            "--repo",
            REPO,
            base=base,
            token=TOKEN,
        )
        assert result.returncode == 2, base


def test_the_token_never_reaches_a_git_argument_the_output_or_the_tap(tmp_path, shims):
    tap = Tap(tmp_path)
    result = publish(tmp_path, shims, tap, token=TOKEN)
    assert result.returncode == 0, result.stdout + result.stderr
    assert TOKEN not in result.stdout + result.stderr
    _, log = shims
    calls = log.read_text("utf-8")
    assert TOKEN not in calls
    # The remote is the plain URL: no user name or token inside it.
    assert f"file://{tap.base}/{REPO}.git" in calls
    assert "@" not in calls.split("clone", 1)[1].splitlines()[0]
    # Nothing written to the tap holds it.
    for name in tap.files():
        assert TOKEN not in tap.show(name)
    # The clone is removed at the end.
    assert not list(tmp_path.glob("publish-tap.*"))


def test_git_gets_the_token_only_through_the_askpass_answer(tmp_path, shims):
    # git asks the GIT_ASKPASS program twice for an https remote: the user
    # name, then the password. The script answers from the environment.
    env = {
        "PATH": "/usr/bin:/bin",
        "HOMEBREW_TAP_TOKEN": TOKEN,
        "PUBLISH_TAP_ASKPASS": "1",
    }
    user = subprocess.run(
        [REAL_BASH, str(SCRIPT), "Username for 'https://github.com': "],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    password = subprocess.run(
        [
            REAL_BASH,
            str(SCRIPT),
            "Password for 'https://x-access-token@github.com': ",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert user.returncode == 0 and user.stdout == "x-access-token\n"
    assert password.returncode == 0 and password.stdout == TOKEN + "\n"


def test_git_runs_with_the_askpass_program_and_no_credential_helper(tmp_path, shims):
    tap = Tap(tmp_path)
    result = publish(tmp_path, shims, tap, token=TOKEN)
    assert result.returncode == 0, result.stdout + result.stderr
    _, log = shims
    env_lines = (log.parent / (log.name + ".env")).read_text("utf-8").splitlines()
    assert f"GIT_ASKPASS={SCRIPT}" in env_lines
    assert "GIT_TERMINAL_PROMPT=0" in env_lines
    calls = log.read_text("utf-8").splitlines()
    remote = [c for c in calls if {"clone", "push", "fetch"} & set(c.split())]
    assert [c for c in remote if " push " in f" {c} "]
    for call in remote:
        assert "credential.helper=" in call.split(), call


def test_the_script_never_traces_and_never_echoes_the_token():
    text = SCRIPT.read_text("utf-8")
    assert "set -x" not in text and "xtrace" not in text
    assert "echo $HOMEBREW_TAP_TOKEN" not in text
    assert 'echo "$HOMEBREW_TAP_TOKEN"' not in text
    # It reads the token twice: the check that it is set, and the askpass
    # answer, which is the only place that prints it.
    assert len(re.findall(r"\$\{?HOMEBREW_TAP_TOKEN", text)) == 2
    printed = [ln for ln in text.splitlines() if "printf" in ln and "TAP_TOKEN" in ln]
    assert len(printed) == 1 and "PUBLISH_TAP_ASKPASS" in text.split(printed[0])[0]


def test_the_script_makes_no_call_to_gh_or_curl():
    # The hand procedure (a here-document the script prints) names gh; the
    # script itself never runs it.
    text = SCRIPT.read_text("utf-8")
    head, rest = text.split("<<EOF\n", 1)
    text = head + rest.split("\nEOF\n", 1)[1]
    for word in ("gh ", "curl", "wget"):
        assert word not in text, word


# ---- the hand procedure -----------------------------------------------------


def test_the_hand_procedure_is_printed_with_the_version_filled_in(tmp_path, shims):
    result = run(
        tmp_path, shims, "--manual-steps", "--version", "1.4.1", "--repo", REPO
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    for line in (
        "git clone --depth 1 --branch v1.4.1 https://github.com/habhabhabs/inventag-aws.git src",
        "gh release download v1.4.1 --repo habhabhabs/inventag-aws --pattern SHA256SUMS",
        "--version 1.4.1 --sums SHA256SUMS --output inventag.rb",
        "grep -c '{{' inventag.rb",
        f"git clone https://github.com/{REPO}.git tap",
        "git switch -c inventag-1.4.1",
        'git commit -m "inventag 1.4.1"',
        "brew install habhabhabs/inventag/inventag",
    ):
        assert line in out, line
    assert "{VERSION}" not in out and "$VERSION" not in out
    _, log = shims
    assert not log.exists()


def test_the_hand_procedure_checks_its_inputs_too(tmp_path, shims):
    result = run(tmp_path, shims, "--manual-steps", "--version", "x", "--repo", REPO)
    assert result.returncode == 2
    result = run(
        tmp_path, shims, "--manual-steps", "--version", "1.4.1", "--repo", "a/b"
    )
    assert result.returncode == 2


def test_the_script_passes_bash_n_and_shellcheck():
    assert subprocess.run([REAL_BASH, "-n", str(SCRIPT)], timeout=30).returncode == 0
    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        pytest.skip("shellcheck is not installed")  # reason is shown in the run
    result = subprocess.run(
        [shellcheck, "-S", "warning", str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout
