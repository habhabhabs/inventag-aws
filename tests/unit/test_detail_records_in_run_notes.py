"""Failed detail calls are in the run notes (A-22, generator side).

Senior D's discovery (fix2/track-d) records a detail call that failed (bucket
location, function configuration ...) as a ledger entry with the source
``service-api-detail`` and ``count`` = resources whose details were not read.
The rows stay in the report with some fields missing; the run note says so.
Unit test on ledger entries, so it holds with or without that branch.
"""

from tests.unit.test_checkpoint_only_complete_accounts import _entry
from tests.unit.test_run_notes_name_what_was_not_read import _generator


def _detail(service, operation, outcome, code, count):
    return dict(
        _entry(outcome, code, service=service, count=count),
        source="service-api-detail",
        operation=operation,
    )


def test_failed_detail_calls_are_named_with_their_count(tmp_path):
    generator = _generator(
        tmp_path,
        {
            "111111111111": [
                _entry("ok", count=3, service="s3"),
                _entry("ok", count=2, service="lambda"),
                _detail("s3", "GetBucketLocation", "denied", "AccessDenied", 3),
                _detail(
                    "lambda", "GetFunctionConfiguration", "throttled", "Throttling", 2
                ),
            ]
        },
    )
    notes = [n for n in generator._run_notes() if not n.startswith("Permissions:")]
    assert notes == [
        "Details of 5 resource(s) in account 111111111111 could not be read, so "
        "those rows have some fields missing: lambda GetFunctionConfiguration in "
        "us-east-1 (throttled, 2); s3 GetBucketLocation in us-east-1 (denied, 3)."
    ]


def test_a_clean_ledger_has_no_detail_note(tmp_path):
    generator = _generator(
        tmp_path,
        {
            "111111111111": [
                _entry("ok", count=3, service="s3"),
                _detail("s3", "GetBucketLocation", "error", "404", 1),
            ]
        },
    )
    assert generator._run_notes() == []
