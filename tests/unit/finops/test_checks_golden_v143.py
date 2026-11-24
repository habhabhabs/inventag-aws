"""``--finops-checks`` output is byte-equal to v1.4.3 (v1.5.0 plan, decision 3).

The golden file holds ``run_checks`` output made by the v1.4.3 code (base
f5ca9e24) before ``inventag/finops/checks.py`` was changed. The inputs are in
``golden_cases.py``; they are not random at run time.
"""

import copy
import json
from pathlib import Path

import pytest

from inventag.finops import checks
from tests.unit.finops import golden_cases

GOLDEN = Path(__file__).parent / "golden" / "checks-v143.json"
EXPECTED = json.loads(GOLDEN.read_text())
CASES = golden_cases.cases()


def test_the_golden_file_and_the_inputs_name_the_same_cases():
    assert sorted(EXPECTED) == sorted(CASES)
    assert len(CASES) >= 250


@pytest.mark.parametrize("name", sorted(CASES))
def test_output_is_byte_equal_to_v1_4_3(name):
    rows, units, started = CASES[name]
    before = copy.deepcopy((rows, units))
    got = checks.run_checks(rows, units, started)
    # key order too: the sheet and the JSON report read the dict as it is
    assert json.dumps(got, indent=1) == json.dumps(EXPECTED[name], indent=1)
    assert (rows, units) == before, "run_checks changed its input"


def test_the_golden_inputs_reach_every_result_and_reason():
    seen = set()
    for output in EXPECTED.values():
        for found in output["findings"]:
            seen.add((found["policy"], found["result"], found["reason"]))
        for line in output["summary"]:
            if line["pass"]:
                seen.add((line["policy"], "pass", ""))
    for policy in checks.CHECKS:
        assert (policy, "pass", "") in seen, policy
    for policy in ("FIN-001", "FIN-002", "FIN-003", "FIN-004", "FIN-005", "FIN-006"):
        assert (policy, "fail", "") in seen, policy
    for policy in ("FIN-001", "FIN-002", "FIN-003", "FIN-004", "FIN-005"):
        for reason in ("identity_only", "field_missing", "listing_not_read"):
            assert (policy, "not_evaluated", reason) in seen, (policy, reason)
    assert ("FIN-006", "not_evaluated", "tags_not_read") in seen
    assert ("FIN-005", "not_evaluated", "field_missing") in seen


def test_the_run_without_a_start_time_still_does_not_read_the_clock():
    rows, units, _ = CASES["fin3 run without a start time"]
    got = checks.run_checks(rows, units, None)
    reasons = {
        (f["resource"], f["reason"])
        for f in got["findings"]
        if f["policy"] == "FIN-003"
    }
    assert ("snap-1", "field_missing") in reasons


def test_a_start_time_without_a_zone_is_refused():
    import datetime as dt

    with pytest.raises(ValueError):
        checks.run_checks([], [], dt.datetime(2026, 11, 20))
