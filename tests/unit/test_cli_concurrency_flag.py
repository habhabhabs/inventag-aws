"""A2 (plan 2.7): the ``--concurrency N`` flag.

"Most AWS requests in flight at once, for the whole run (default: 64). 1 sends
one request at a time." Not an integer, below 1 or above 256: exit 2 with one
line that names the flag and the allowed range, before any AWS call.
"""

import importlib
import os
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


def test_default_is_64():
    assert cli_main.create_parser().parse_args([]).concurrency == 64


@pytest.mark.parametrize("value", ["1", "8", "256"])
def test_values_from_1_to_256_are_accepted(value):
    args = cli_main.create_parser().parse_args(["--concurrency", value])
    assert args.concurrency == int(value)


@pytest.mark.parametrize("value", ["0", "-1", "257", "abc", "1.5", ""])
def test_values_out_of_range_stop_with_exit_2_before_any_work(
    value, capsys, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_main("--concurrency", value) == 2
    err = capsys.readouterr().err
    assert (
        "inventag: error: argument --concurrency: must be a whole number "
        f"from 1 to 256, not {value!r}"
    ) in err
    assert not os.path.exists("bom_output")


def test_help_text():
    help_text = " ".join(cli_main.create_parser().format_help().split())
    assert (
        "--concurrency N Most AWS requests in flight at once, for the whole run "
        "(default: 64). 1 sends one request at a time."
    ) in help_text


def test_the_value_reaches_the_scan_config(tmp_path):
    accounts = tmp_path / "accounts.json"
    accounts.write_text('{"accounts": [{"account_id": "123456789012"}]}')
    parser = cli_main.create_parser()
    config = cli_main.create_multi_account_config(
        parser.parse_args(["--accounts-file", str(accounts), "--concurrency", "8"])
    )
    assert config.concurrency == 8
    default = cli_main.create_multi_account_config(
        parser.parse_args(["--accounts-file", str(accounts)])
    )
    assert default.concurrency == 64


def test_the_library_default_is_the_cli_default():
    from inventag.core.cloud_bom_generator import MultiAccountConfig
    from inventag.core.limiter import DEFAULT_LIMIT

    assert MultiAccountConfig().concurrency == DEFAULT_LIMIT == 64
