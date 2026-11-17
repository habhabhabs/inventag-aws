"""A listing that failed after some pages still read something (D1 with A-01).

With ``--account-services`` limiting the scan (senior D's D1), an account can
have one chosen listing only. When that listing fails after some pages
(outcome ``error``, rows kept, ``count`` > 0) the account read something: it
gets the "Not read ... partial" note, not "every service listing was denied
or failed" (harness row D4 with D1). Ledger-only test: holds with and without
fix3/track-d.
"""

from tests.unit.test_checkpoint_only_complete_accounts import _entry
from tests.unit.test_run_notes_name_what_was_not_read import _generator


def test_a_partly_read_only_listing_gets_the_partial_note(tmp_path):
    generator = _generator(
        tmp_path,
        {
            "111111111111": [
                _entry(
                    "throttled", "ThrottlingException", service="dynamodb", count=100
                )
            ]
        },
    )
    assert generator._run_notes() == [
        "Not read in account 111111111111, so the report is partial there: "
        "dynamodb in us-east-1 (throttled)."
    ]


def test_a_listing_that_read_nothing_still_counts_as_read_nothing(tmp_path):
    generator = _generator(
        tmp_path,
        {"111111111111": [_entry("denied", "AccessDenied", service="dynamodb")]},
    )
    assert generator._accounts_that_read_nothing() == ["111111111111"]
    assert list(generator._accounts_without_service_apis()) == ["111111111111"]
