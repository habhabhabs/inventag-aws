"""A2: ``inventag selftest`` and ``inventag completion`` are reached from the
main entry point (B1's two dispatch lines). No AWS call, no network."""

import importlib
import sys

import pytest

cli_main = importlib.import_module("inventag.cli.main")


def run_main(*argv):
    old = sys.argv
    sys.argv = ["inventag", *argv]
    try:
        cli_main.main()
    except SystemExit as e:
        return e.code
    finally:
        sys.argv = old
    return None


def test_selftest_word_runs_the_selftest_with_the_remaining_arguments(monkeypatch):
    from inventag.cli import selftest

    seen = []

    def fake_main(argv):
        seen.append(list(argv))
        return 0

    monkeypatch.setattr(selftest, "main", fake_main)
    assert run_main("selftest", "--quiet") == 0
    assert seen == [["--quiet"]]


def test_selftest_exit_code_is_passed_through(monkeypatch):
    from inventag.cli import selftest

    monkeypatch.setattr(selftest, "main", lambda argv: 1)
    assert run_main("selftest") == 1


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion_word_prints_the_script(shell, capsys):
    assert run_main("completion", shell) == 0
    out = capsys.readouterr().out
    # zsh's script starts with its "#compdef inventag" line.
    assert any(
        line.startswith(f"# {shell} completion for inventag")
        for line in out.splitlines()[:2]
    )
    # The new commands are offered by the script itself.
    assert "selftest" in out and "completion" in out


def test_completion_with_an_unknown_shell_is_a_usage_error(capsys):
    assert run_main("completion", "tcsh") == 2
    assert "invalid choice" in capsys.readouterr().err
