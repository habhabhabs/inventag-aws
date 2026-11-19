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


def test_log_lines_in_sample_output_are_not_commands():
    for line in (
        "inventag - ERROR - Template problem:",
        "inventag - WARNING - - No account specification method provided.",
        "inventag.cli.main - ERROR - Cannot proceed",
    ):
        assert helper.extract_commands(line) == []


def test_help_and_version_are_accepted(capsys):
    assert _check("inventag --help") == []
    assert _check("inventag --version") == []
    assert _check("inventag templates --help") == []
    assert capsys.readouterr().out == ""


def test_markdown_reads_shell_blocks_only():
    page = (
        "```text\ninventag [flags]   run a scan\ninventag - ERROR - x\n```\n\n"
        "```bash\ninventag --no-such-flag\n```\n"
    )
    found = helper.check_markdown(page)
    assert [(line, cmd) for line, cmd, _ in found] == [(7, "inventag --no-such-flag")]


def test_markdown_langs_can_be_narrowed():
    page = "```yaml\nrun: inventag --no-such-flag\n```\n"
    assert helper.check_markdown(page, ("bash",)) == []
    assert helper.check_markdown(page)


def test_json_blocks_must_parse():
    good = '```json\n{"a": [1, 2]}\n```\n'
    bad = '```json\n{\n  "a": 1,\n}\n```\n'
    assert helper.check_json_blocks(good) == []
    ((line, problem),) = helper.check_json_blocks(bad)
    assert line in (3, 4) and "does not parse" in problem
    # other languages are not read as JSON
    assert helper.check_json_blocks("```text\n{not json\n```\n") == []


def test_main_reads_markdown_by_block(tmp_path, capsys):
    page = tmp_path / "p.md"
    page.write_text("```text\ninventag - WARNING - x\n```\n```json\n{\n```\n")
    assert helper.main([str(page)]) == 1
    out = capsys.readouterr().out
    assert "json block does not parse" in out and "WARNING" not in out


def test_shipped_docs_have_no_findings():
    root = Path(__file__).resolve().parents[2]
    pages = sorted((root / "docs").rglob("*.md"))
    assert pages
    problems = []
    for page in pages:
        text = page.read_text("utf-8")
        problems += [(str(page), *f) for f in helper.check_markdown(text)]
        problems += [(str(page), *f) for f in helper.check_json_blocks(text)]
    assert problems == []
