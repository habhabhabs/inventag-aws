"""A2 (plan 2.6): SIGTERM and Ctrl-C stop the run's limiter first, then take
today's path (same message, same exit status): no new AWS request starts and
every waiter ends at once."""

import importlib
import logging
import signal
import sys

from inventag.core import cloud_bom_generator as cbg

cli_main = importlib.import_module("inventag.cli.main")


def _generator(tmp_path):
    return cbg.CloudBOMGenerator(
        cbg.MultiAccountConfig(output_directory=str(tmp_path / "out"))
    )


def test_sigterm_stops_the_limiter_then_ends_as_before(tmp_path, monkeypatch):
    generator = _generator(tmp_path)
    killed, handlers, order = [], [], []
    monkeypatch.setattr(cli_main.os, "kill", lambda pid, sig: killed.append(sig))
    real_signal = signal.signal

    def fake_signal(signum, handler):
        handlers.append((signum, handler))
        return signal.SIG_DFL

    monkeypatch.setattr(cli_main.signal, "signal", fake_signal)
    logger = logging.getLogger("test-sigterm")
    monkeypatch.setattr(
        logger,
        "warning",
        lambda text: order.append(("warning", generator.limiter.stopped, text)),
    )
    cli_main._install_sigterm_message(logger, str(tmp_path / "out"), 0.0)
    installed = handlers[0][1]
    installed(signal.SIGTERM, None)
    monkeypatch.setattr(cli_main.signal, "signal", real_signal)

    assert generator.limiter.stopped
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
