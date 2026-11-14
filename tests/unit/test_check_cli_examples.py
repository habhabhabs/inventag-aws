"""Unit tests for scripts/docs/check_cli_examples.py (parse only, no AWS)."""

import importlib.util
from pathlib import Path

_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "docs" / "check_cli_examples.py"
)
_spec = importlib.util.spec_from_file_location("check_cli_examples", _PATH)
helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helper)


def _check(line: str):
    commands = helper.extract_commands(line)
    assert len(commands) == 1, commands
    return helper.check_command(commands[0][2])


def test_good_command_passes():
    assert _check("inventag --template nightly --fail-on-account-error") == []


def test_unknown_flag_fails():
    problems = _check("inventag --template nightly --no-such-flag")
    assert problems and "--no-such-flag" in problems[0]


def test_placeholder_values_pass():
    assert _check('inventag --s3-bucket "$BUCKET" --s3-key-prefix ${PREFIX}/') == []
    assert _check("run: inventag --s3-bucket ${{ vars.BUCKET }} --create-excel") == []


def test_continuation_lines_are_joined():
    text = "inventag --create-excel \\\n  --bogus-flag\n"
    ((_, _, tokens),) = helper.extract_commands(text)
    assert "--bogus-flag" in tokens
    assert helper.check_command(tokens)


def test_invalid_choice_fails_and_pip_line_is_ignored():
    problems = _check("inventag --s3-encryption rot13 --s3-bucket b")
    assert problems and "invalid choice" in problems[0]
    assert helper.extract_commands('pip install "inventag-aws==1.2.0"') == []
