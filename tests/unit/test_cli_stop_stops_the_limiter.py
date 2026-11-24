"""A2 (plan 2.6): SIGTERM and Ctrl-C stop the run's limiter first, then take
today's path (same message, same exit status): no new AWS request starts.
Ctrl-C makes every waiter end at once (``stop_running_scans``, after the stack
has unwound). SEC1: SIGTERM only asks for the stop, without a lock
(``request_stop_of_running_scans``); the process ends a moment later."""

import importlib
import logging
import os
import signal
import sys

from inventag.core import cloud_bom_generator as cbg

cli_main = importlib.import_module("inventag.cli.main")


def _generator(tmp_path):
    return cbg.CloudBOMGenerator(
        cbg.MultiAccountConfig(output_directory=str(tmp_path / "out"))
    )


def _sigterm(tmp_path, monkeypatch, logger, generator):
    killed, handlers = [], []
    monkeypatch.setattr(cli_main.os, "kill", lambda pid, sig: killed.append(sig))
    real_signal = signal.signal

    def fake_signal(signum, handler):
        handlers.append((signum, handler))
        return signal.SIG_DFL

    monkeypatch.setattr(cli_main.signal, "signal", fake_signal)

    def takes_locks():
        raise AssertionError("the SIGTERM handler called stop_running_scans")

    monkeypatch.setattr(cli_main, "stop_running_scans", takes_locks)
    cli_main._install_sigterm_message(logger, str(tmp_path / "out"), 0.0)
    installed = handlers[0][1]
    installed(signal.SIGTERM, None)
    monkeypatch.setattr(cli_main.signal, "signal", real_signal)
    return killed, handlers


def test_sigterm_stops_the_limiter_then_ends_as_before(tmp_path, monkeypatch):
    # A-79: the line is one os.write on the log stream's file descriptor.
    # The logger has its own stream (not pytest's root handlers).
    generator = _generator(tmp_path)
    order = []
    stream = open(os.devnull, "w")
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("test-sigterm")
    monkeypatch.setattr(logger, "handlers", [handler])
    monkeypatch.setattr(logger, "propagate", False)
    monkeypatch.setattr(logger, "level", logging.WARNING)

    def not_through_logging(text):
        raise AssertionError("the SIGTERM line went through logging")

    monkeypatch.setattr(logger, "warning", not_through_logging)
    real_write = os.write

    def write(fd, data):
        if fd == stream.fileno():
            order.append(("write", generator.limiter.stopped, data))
            return len(data)
        return real_write(fd, data)

    monkeypatch.setattr(cli_main.os, "write", write)
    try:
        killed, handlers = _sigterm(tmp_path, monkeypatch, logger, generator)
    finally:
        monkeypatch.setattr(cli_main.os, "write", real_write)
        stream.close()

    assert generator.limiter.stopped
    assert order == [("write", True, b"Terminated (SIGTERM). No report was written.\n")]
    assert killed == [signal.SIGTERM]
    assert handlers[-1] == (signal.SIGTERM, signal.SIG_DFL)


def test_sigterm_without_a_log_stream_logs_the_line_as_before(tmp_path, monkeypatch):
    generator = _generator(tmp_path)
    order = []
    logger = logging.getLogger("test-sigterm-no-stream")
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(logger, "propagate", False)
    monkeypatch.setattr(
        logger,
        "warning",
        lambda text: order.append(("warning", generator.limiter.stopped, text)),
    )
    killed, handlers = _sigterm(tmp_path, monkeypatch, logger, generator)

    assert order == [("warning", True, "Terminated (SIGTERM). No report was written.")]
    assert killed == [signal.SIGTERM]
    assert handlers[-1] == (signal.SIGTERM, signal.SIG_DFL)


def test_ctrl_c_stops_the_limiter_with_todays_message_and_exit_1(
    tmp_path, monkeypatch, caplog
):
    generator = _generator(tmp_path)

    def interrupted(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_main, "create_multi_account_config", interrupted)
    monkeypatch.chdir(tmp_path)
    old = sys.argv
    sys.argv = ["inventag", "--skip-credential-validation"]
    try:
        cli_main._run(
            cli_main.create_parser().parse_args(sys.argv[1:]), logging.getLogger("t")
        )
    except SystemExit as e:
        code = e.code
    finally:
        sys.argv = old
    assert code == 1
    assert generator.limiter.stopped
    assert "Stopped by the user (Ctrl-C). No report was written." in caplog.text


def test_sigterm_restores_the_default_action_before_anything_that_can_block(
    tmp_path, monkeypatch
):
    # Security re-check v1.4.1 R1 and the architect's ruling: the default
    # action comes back first, so a second SIGTERM ends the process even while
    # the folder read or the write of the line blocks.
    events = []
    installed = []
    stream = open(os.devnull, "w")
    logger = logging.getLogger("test-sigterm-order")
    monkeypatch.setattr(logger, "handlers", [logging.StreamHandler(stream)])
    monkeypatch.setattr(logger, "propagate", False)
    monkeypatch.setattr(logger, "level", logging.WARNING)

    def fake_signal(signum, handler):
        if not installed:
            installed.append(handler)
        else:
            events.append(("signal", handler))
        return signal.SIG_DFL

    def note(output_dir, since):
        events.append("note")
        return "No report was written."

    real_write = os.write

    def write(fd, data):
        if fd == stream.fileno():
            events.append("write")
            return len(data)
        return real_write(fd, data)

    monkeypatch.setattr(cli_main.signal, "signal", fake_signal)
    monkeypatch.setattr(cli_main, "_written_reports_note", note)
    monkeypatch.setattr(
        cli_main, "request_stop_of_running_scans", lambda: events.append("stop")
    )
    monkeypatch.setattr(cli_main.os, "kill", lambda pid, sig: events.append("kill"))
    monkeypatch.setattr(cli_main.os, "write", write)
    try:
        cli_main._install_sigterm_message(logger, str(tmp_path / "out"), 0.0)
        installed[0](signal.SIGTERM, None)
    finally:
        monkeypatch.setattr(cli_main.os, "write", real_write)
        stream.close()

    assert events == [("signal", signal.SIG_DFL), "stop", "note", "write", "kill"]
