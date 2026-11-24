"""``inventag completion bash|zsh|fish``: shell completion scripts from the parsers.

Golden files hold the scripts for a small parser made in this file, so they
change only when the generator changes (not when a flag is added to the real
command). Other tests build the scripts from the real parsers and check that
every flag and word is in them, and run the bash script in a real bash.
"""

import argparse
import io
import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

from inventag.cli import completion

GOLDEN = Path(__file__).resolve().parent / "completion_golden"
SCRIPT_NAMES = {"bash": "inventag.bash", "zsh": "_inventag", "fish": "inventag.fish"}


def sample_model():
    root = argparse.ArgumentParser(prog="inventag")
    root.add_argument(
        "-v", "--verbose", action="store_true", help="Talk more. Then stop."
    )
    root.add_argument("--output-directory", help="Folder for the files")
    root.add_argument(
        "--accounts-file", metavar="FILE", help="Accounts, as JSON [or YAML]"
    )
    root.add_argument(
        "--mode",
        choices=["fast", "slow", "aws:kms"],
        help="How it's done: (default fast)",
    )
    root.add_argument("--name", metavar="NAME", help="A name")
    root.add_argument(
        "--color", action=argparse.BooleanOptionalAction, help="Use colour"
    )
    root.add_argument("--secret-flag", help=argparse.SUPPRESS)
    root.add_argument("--version", action="version", version="x")

    tool = argparse.ArgumentParser(
        prog="inventag tool", description="Do tool things. More text."
    )
    tool.add_argument("--dry", action="store_true", help="Change nothing")
    sub = tool.add_subparsers(dest="command")
    run = sub.add_parser("run", help="Run it")
    run.add_argument("--force", "-f", action="store_true", help="Overwrite")
    run.add_argument("--out", "-o", help="Output file")
    run.add_argument("files", nargs="+", metavar="NAME|PATH")
    show = sub.add_parser("show", help="Show it")
    show.add_argument("what", choices=["one", "two"])

    shell = argparse.ArgumentParser(prog="inventag shell", description="Print a script")
    shell.add_argument("shell", choices=["bash", "zsh"])
    return completion.build_model(root, {"tool": tool, "shell": shell})


@pytest.mark.parametrize("shell", completion.SHELLS)
def test_the_script_for_a_sample_parser_equals_its_golden_file(shell):
    script = completion.RENDERERS[shell](sample_model())
    assert script == (GOLDEN / SCRIPT_NAMES[shell]).read_text()


@pytest.mark.parametrize("shell", completion.SHELLS)
def test_the_script_is_the_same_every_time(shell):
    assert completion.RENDERERS[shell](completion.real_model()) == completion.RENDERERS[
        shell
    ](completion.real_model())


def test_the_first_sentence_of_a_help_text_is_used():
    action = argparse.Action(["--x"], "x", default=7)
    assert (
        completion._short("Use e.g. this one. And then that.", action)
        == "Use e.g. this one"
    )
    assert completion._short("Default is %(default)s%%.", action) == "Default is 7%"
    assert completion._short(argparse.SUPPRESS) == ""
    assert len(completion._short("word " * 60)) <= completion.HELP_LIMIT


# ------------------------------------------------------- the real parsers


def real_scripts():
    return {
        shell: completion.RENDERERS[shell](completion.real_model())
        for shell in completion.SHELLS
    }


def test_every_flag_and_command_word_of_the_real_command_is_in_every_script():
    from inventag.cli.main import create_parser
    from inventag.templating.cli import build_parser

    flags = {s for a in create_parser()._actions for s in a.option_strings}
    words = {
        "templates",
        "selftest",
        "completion",
        "policy",
        "list",
        "show",
        "init",
        "validate",
        "schema",
        "test",
        "check",
        "explain",
        "lock",
    }
    assert "--create-excel" in flags and len(flags) > 50
    for shell, script in real_scripts().items():
        for flag in sorted(flags):
            token = flag[2:] if shell == "fish" and flag.startswith("--") else flag
            token = flag[1:] if shell == "fish" and not flag.startswith("--") else token
            assert token in script, f"{shell}: {flag}"
        for word in sorted(words):
            assert word in script, f"{shell}: {word}"
    assert build_parser().prog == "inventag templates"


def test_a_hidden_option_is_not_offered():
    for shell, script in {
        s: completion.RENDERERS[s](sample_model()) for s in completion.SHELLS
    }.items():
        assert "secret-flag" not in script, shell


# ------------------------------------------------------------ the command


def run_main(argv):
    out = io.StringIO()
    code = completion.main(argv, out=out)
    return code, out.getvalue()


@pytest.mark.parametrize("shell", completion.SHELLS)
def test_the_command_prints_the_script_and_exits_0_without_the_network(
    shell, monkeypatch
):
    def refuse(*args, **kwargs):
        raise AssertionError("completion used the network")

    monkeypatch.setattr(socket.socket, "__init__", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)

    code, text = run_main([shell])

    assert code == 0
    assert text == real_scripts()[shell]
    assert text.endswith("\n") and not text.endswith("\n\n")


@pytest.mark.parametrize("argv", [[], ["powershell"], ["bash", "zsh"]])
def test_a_missing_or_unknown_shell_exits_2(argv, capsys):
    with pytest.raises(SystemExit) as stop:
        completion.main(argv)
    assert stop.value.code == 2
    assert capsys.readouterr().out == ""


def test_help_exits_0_and_names_the_three_shells(capsys):
    with pytest.raises(SystemExit) as stop:
        completion.main(["--help"])
    assert stop.value.code == 0
    text = capsys.readouterr().out
    for shell in completion.SHELLS:
        assert shell in text
    assert "no AWS call" in text


# --------------------------------------------------- syntax in the real shells


def check_syntax(shell, flag, tmp_path):
    exe = shutil.which(shell)
    assert exe, f"{shell} is not installed"
    path = tmp_path / SCRIPT_NAMES[shell]
    path.write_text(real_scripts()[shell])
    done = subprocess.run(
        [exe, flag, str(path)], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stderr


def test_bash_accepts_the_script_with_bash_n(tmp_path):
    check_syntax("bash", "-n", tmp_path)


@pytest.mark.skipif(
    shutil.which("zsh") is None, reason="zsh is not installed on this machine"
)
def test_zsh_accepts_the_script_with_zsh_n(tmp_path):
    check_syntax("zsh", "-n", tmp_path)


@pytest.mark.skipif(
    shutil.which("fish") is None, reason="fish is not installed on this machine"
)
def test_fish_accepts_the_script_with_fish_n(tmp_path):
    check_syntax("fish", "-n", tmp_path)


# ------------------------------------------------------ bash, run for real


def complete_in_bash(tmp_path, words, cword, cwd=None):
    """The words bash would offer: source the script, set what bash sets, call the function."""
    script = tmp_path / "inventag.bash"
    script.write_text(real_scripts()["bash"])
    quoted = " ".join(f"'{w}'" for w in words)
    program = (
        f"source '{script}'\n"
        f"COMP_WORDS=({quoted})\nCOMP_CWORD={cword}\n"
        "_inventag\n"
        'printf "%s\\n" "${COMPREPLY[@]}"\n'
    )
    done = subprocess.run(
        [shutil.which("bash"), "--norc", "--noprofile", "-c", program],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd or tmp_path,
        env={"PATH": os.environ["PATH"]},
    )
    assert done.returncode == 0, done.stderr
    return sorted(line for line in done.stdout.splitlines() if line)


def test_bash_offers_the_command_words_first(tmp_path):
    assert complete_in_bash(tmp_path, ["inventag", ""], 1) == [
        "completion",
        "policy",
        "selftest",
        "templates",
    ]


def test_bash_offers_flags_that_match(tmp_path):
    offered = complete_in_bash(tmp_path, ["inventag", "--create-"], 1)
    assert "--create-excel" in offered and "--create-word" in offered
    assert all(name.startswith("--create-") for name in offered)


def test_bash_does_not_offer_command_words_after_a_flag(tmp_path):
    assert complete_in_bash(tmp_path, ["inventag", "--create-excel", ""], 2) == []


def test_bash_offers_the_shells_after_completion(tmp_path):
    assert complete_in_bash(tmp_path, ["inventag", "completion", ""], 2) == [
        "bash",
        "fish",
        "zsh",
    ]


def test_bash_offers_the_template_commands_and_their_flags(tmp_path):
    assert complete_in_bash(tmp_path, ["inventag", "templates", ""], 2) == [
        "init",
        "list",
        "show",
        "validate",
    ]
    assert complete_in_bash(tmp_path, ["inventag", "templates", "list", "--k"], 3) == [
        "--kind"
    ]


def test_bash_offers_the_choices_of_an_option(tmp_path):
    assert complete_in_bash(tmp_path, ["inventag", "--risk-threshold", ""], 2) == [
        "CRITICAL",
        "HIGH",
        "LOW",
        "MEDIUM",
    ]
    assert complete_in_bash(
        tmp_path, ["inventag", "templates", "list", "--kind", ""], 4
    ) == [
        "config",
        "report",
        "tag-policy",
    ]


def test_bash_completes_the_value_after_an_equals_sign(tmp_path):
    # bash splits '--fallback-display=al' into three words.
    assert complete_in_bash(
        tmp_path, ["inventag", "--fallback-display", "=", ""], 3
    ) == [
        "always",
        "auto",
        "never",
    ]
    assert complete_in_bash(
        tmp_path, ["inventag", "--fallback-display", "=", "al"], 3
    ) == ["always"]


def test_bash_offers_files_for_a_file_option_and_folders_for_a_folder_option(tmp_path):
    (tmp_path / "accounts.json").write_text("{}")
    (tmp_path / "reports").mkdir()
    both = complete_in_bash(tmp_path, ["inventag", "--accounts-file", "acc"], 2)
    assert both == ["accounts.json"]
    folders = complete_in_bash(tmp_path, ["inventag", "--output-directory", ""], 2)
    assert "reports" in folders and "accounts.json" not in folders


def test_bash_offers_nothing_for_a_free_text_option(tmp_path):
    assert complete_in_bash(tmp_path, ["inventag", "--account-regions", ""], 2) == []


def test_the_script_registers_itself_for_inventag(tmp_path):
    script = tmp_path / "inventag.bash"
    script.write_text(real_scripts()["bash"])
    done = subprocess.run(
        [
            shutil.which("bash"),
            "--norc",
            "--noprofile",
            "-c",
            f"source '{script}'; complete -p inventag",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": os.environ["PATH"]},
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "complete -F _inventag inventag"


def test_bash_offers_the_policy_command_words(tmp_path):
    assert complete_in_bash(tmp_path, ["inventag", "policy", ""], 2) == [
        "check",
        "explain",
        "list",
        "lock",
        "schema",
        "test",
        "validate",
    ]


def test_bash_offers_the_flags_of_policy_check(tmp_path):
    offered = complete_in_bash(tmp_path, ["inventag", "policy", "check", "--f"], 3)
    assert offered == ["--fail-on", "--fail-on-not-evaluated", "--format"]


def test_policy_words_and_flags_are_in_every_script():
    from inventag.policy.cli import build_parser

    flags = {
        s
        for action in build_parser()
        ._subparsers._group_actions[0]
        .choices["check"]
        ._actions
        for s in action.option_strings
    }
    assert {"--snapshot", "--policies", "--waivers", "--baseline", "--locked"} <= flags
    for shell, script in real_scripts().items():
        for flag in sorted(flags):
            token = flag[2:] if shell == "fish" and flag.startswith("--") else flag
            token = flag[1:] if shell == "fish" and not flag.startswith("--") else token
            assert token in script, f"{shell}: {flag}"
        for word in ("policy", "validate", "explain", "lock", "schema"):
            assert word in script, f"{shell}: {word}"
