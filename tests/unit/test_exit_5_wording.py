"""Exit code 5 means what ruling R1 says (A-53): an account could not be
scanned or ran out of time. The help text and the docstring say it, and the
flag and the code are unchanged."""

from inventag import exit_codes
from inventag.cli.main import create_parser

R1 = "an account could not be scanned or ran out of time"


def _help_of(flag):
    for action in create_parser()._actions:
        if flag in action.option_strings:
            return action
    raise AssertionError(f"{flag} not found")


def test_fail_on_account_error_help_states_the_ruling():
    action = _help_of("--fail-on-account-error")
    assert action.option_strings == ["--fail-on-account-error"]
    assert R1 in " ".join(action.help.split())
    assert "(or only partly)" not in action.help


def test_exit_codes_docstring_states_the_ruling():
    text = " ".join(exit_codes.__doc__.split())
    assert "An account could not be scanned or ran out of time" in text
    assert "(or only partly)" not in text


def test_exit_code_5_is_unchanged():
    assert exit_codes.EXIT_ACCOUNT_FAILED == 5
