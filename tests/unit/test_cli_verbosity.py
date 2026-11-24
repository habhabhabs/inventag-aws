"""UX plan U1, part B: ``-v`` is INFO, ``-vv`` is DEBUG (the same as
``--debug``). Every test asserts the exit code."""

import logging
import stat
import sys

import pytest

from tests.e2e.conftest import restored_process_state

SDK = ("boto3", "botocore", "s3transfer", "urllib3")


@pytest.fixture
def sdk_levels():
    saved = {
        n: (logging.getLogger(n).level, list(logging.getLogger(n).handlers))
        for n in SDK
    }
    yield
    for name, (level, handlers) in saved.items():
        logging.getLogger(name).setLevel(level)
        logging.getLogger(name).handlers[:] = handlers


def _main(argv, capsys, monkeypatch, inspect=None):
    """Run main(); ``inspect`` runs before the process state is restored."""
    from inventag.cli.main import main

    monkeypatch.setattr(sys, "argv", ["inventag", *argv])
    code, seen = 0, None
    with restored_process_state():
        try:
            main()
        except SystemExit as stop:
            code = 0 if stop.code is None else stop.code
        if inspect:
            seen = inspect()
    captured = capsys.readouterr()
    return code, captured.out, captured.err, seen


def _levels():
    package = logging.getLogger("inventag")
    console = [
        h
        for h in package.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
    ]
    return (
        logging.getLevelName(package.level),
        logging.getLevelName(logging.getLogger("botocore").level),
        logging.getLevelName(console[0].level),
    )


WARNING = ("WARNING", "WARNING", "WARNING")
INFO = ("INFO", "WARNING", "INFO")
DEBUG = ("DEBUG", "DEBUG", "DEBUG")


@pytest.mark.parametrize(
    "flags, expected",
    [
        ([], WARNING),
        (["-v"], INFO),
        (["--verbose"], INFO),
        (["-vv"], DEBUG),
        (["-v", "-v"], DEBUG),
        (["--verbose", "--verbose"], DEBUG),
        (["-vvv"], DEBUG),
        (["-vvvv"], DEBUG),
        (["-d"], DEBUG),
        (["--debug"], DEBUG),
        (["-v", "-d"], DEBUG),
        (["-vv", "-d"], DEBUG),
        (["-vd"], DEBUG),
    ],
)
def test_the_level_table(flags, expected, capsys, monkeypatch, sdk_levels):
    code, out, err, levels = _main(
        ["--validate-config-only", *flags], capsys, monkeypatch, _levels
    )
    assert code == 0, out + err
    assert levels == expected


def test_vv_output_is_redacted_on_the_console_and_in_the_log_file(
    capsys, monkeypatch, sdk_levels, tmp_path
):
    token = "FQoGZXIvYXdzEJr//////////wEaDEXAMPLESESSIONTOKENVALUE1234567890"
    log_file = tmp_path / "run.log"

    def log_a_secret():
        logging.getLogger("botocore").debug(
            "Response body: {'SessionToken': '%s'}", token
        )
        for handler in logging.getLogger("inventag").handlers:
            handler.flush()

    code, out, err, _ = _main(
        ["--validate-config-only", "-vv", "--log-file", str(log_file)],
        capsys,
        monkeypatch,
        log_a_secret,
    )
    assert code == 0, out + err
    text = log_file.read_text()
    assert "Response body" in out and "Response body" in text
    assert token not in out + err and token not in text
    assert stat.S_IMODE(log_file.stat().st_mode) == 0o600


def _boom(*args, **kwargs):
    raise RuntimeError("boom-marker")


@pytest.mark.parametrize("flags, traceback", [(["-vv"], True), (["-v"], False)])
def test_vv_logs_the_traceback_of_an_unexpected_error(
    flags, traceback, capsys, monkeypatch, sdk_levels
):
    import importlib

    cli_main = importlib.import_module("inventag.cli.main")

    monkeypatch.setattr(cli_main, "validate_aws_credentials_early", _boom)
    code, out, err, _ = _main(flags, capsys, monkeypatch)
    assert code == 1
    assert "Unexpected error: RuntimeError: boom-marker" in out
    assert ("Traceback (most recent call last)" in out) is traceback


def test_v_shows_no_sdk_line_below_warning(capsys, monkeypatch, sdk_levels):
    def sdk_lines():
        for name in SDK:
            logging.getLogger(name).info(f"sdk-info-{name}")
            logging.getLogger(name).debug(f"sdk-debug-{name}")

    code, out, err, _ = _main(
        ["--validate-config-only", "-v"], capsys, monkeypatch, sdk_lines
    )
    assert code == 0, out + err
    assert "sdk-" not in out + err


def test_the_help_texts_of_the_two_options(capsys, monkeypatch):
    code, out, err, _ = _main(["--help"], capsys, monkeypatch)
    assert code == 0
    text = " ".join(out.split())
    assert (
        "--verbose, -v Show each step (INFO). Give it twice (-vv) for debug "
        "output, the same as --debug." in text
    )
    assert (
        "--debug, -d Show debug output and every AWS request. Secrets are "
        "masked; treat the output as sensitive." in text
    )
    assert "inventag --create-excel -v" in out
