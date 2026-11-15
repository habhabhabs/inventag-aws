"""A run with no output flag prints one true line about the Excel default,
not a second, misleading one (A-54). Golden console of the default run; the
generator is a stand-in, so only the CLI's own lines are looked at."""

import importlib
import logging
import re
import sys

import pytest
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-tests-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        yield
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


class FakeGenerator:
    formats = None

    def __init__(self, config):
        pass

    def generate_comprehensive_bom(self, output_formats=None, **kwargs):
        FakeGenerator.formats = output_formats
        return {
            "success": True,
            "bom_generation": {"generated_files": []},
            "failed_accounts": [],
            "processing_statistics": {},
        }


def run(monkeypatch, capsys, *args):
    monkeypatch.setattr(cli_main, "CloudBOMGenerator", FakeGenerator)
    monkeypatch.setattr(cli_main, "validate_aws_credentials_early", lambda t: True)
    old = sys.argv
    sys.argv = ["inventag", *args]
    code = 0
    try:
        cli_main.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old
    out = capsys.readouterr()
    text = out.out + out.err
    lines = [
        re.sub(r"^\S+ \S+ - ", "", x) for x in text.splitlines() if " - WARNING - " in x
    ]
    return code, [re.sub(r"^\S+ - ", "", x) for x in lines]


def test_default_run_console_has_one_line_about_the_excel_default(
    env, monkeypatch, capsys
):
    code, lines = run(monkeypatch, capsys, "--no-billing-validation")
    assert code == 0
    assert FakeGenerator.formats == ["excel"]
    assert lines == [
        "WARNING -   - No account specification method provided. Using default AWS credentials.",
        "WARNING - No output formats specified. Defaulting to Excel format.",
    ]


def test_a_run_with_an_output_flag_prints_no_format_line(env, monkeypatch, capsys):
    code, lines = run(monkeypatch, capsys, "--create-word", "--no-billing-validation")
    assert code == 0
    assert FakeGenerator.formats == ["word"]
    assert not any("output format" in x for x in lines)
