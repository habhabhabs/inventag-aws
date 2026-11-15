"""The console completion line does not say "successful" when the state
snapshot or the change report had a problem (A-18, console side). Exit code 0
in all cases, as before. Generator stand-in; the text of the state fields is
what the real generator puts in the result."""

import importlib
import logging
import sys

import pytest
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")

CASES = {
    "snapshot not saved": {"state_saved": False, "error": "[Errno 28] disk full"},
    "index not saved": {"state_saved": True, "state_index_error": "disk full"},
    "change report failed": {
        "state_saved": True,
        "delta_detection": {"error": "boom"},
    },
}
GOOD = "✓ BOM generation successful"
PROBLEM = (
    "✓ Reports written; the state snapshot or the change report "
    "had a problem (see the notes below)"
)


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


def run(monkeypatch, capsys, state):
    class Fake:
        def __init__(self, config):
            pass

        def generate_comprehensive_bom(self, **kwargs):
            result = {
                "success": True,
                "bom_generation": {"generated_files": []},
                "failed_accounts": [],
                "processing_statistics": {},
            }
            if state is not None:
                result["state_management"] = state
            return result

    monkeypatch.setattr(cli_main, "CloudBOMGenerator", Fake)
    monkeypatch.setattr(cli_main, "validate_aws_credentials_early", lambda t: True)
    old = sys.argv
    sys.argv = ["inventag", "--create-excel", "--no-billing-validation", "--verbose"]
    code = 0
    try:
        cli_main.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old
    out = capsys.readouterr()
    return code, out.out + out.err


@pytest.mark.parametrize("name", sorted(CASES))
def test_a_state_problem_is_not_called_successful(env, monkeypatch, capsys, name):
    code, text = run(monkeypatch, capsys, CASES[name])
    assert code == 0
    assert PROBLEM in text
    assert GOOD not in text


@pytest.mark.parametrize(
    "state",
    [None, {}, {"state_saved": True, "delta_detection": {"changes": 0}}],
)
def test_a_clean_run_prints_the_same_line_as_before(env, monkeypatch, capsys, state):
    code, text = run(monkeypatch, capsys, state)
    assert code == 0
    assert GOOD in text and PROBLEM not in text
