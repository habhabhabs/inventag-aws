"""A-57: what a default run (no --debug, no --verbose) prints when Cost Explorer fails.

Each case starts one real child process (moto and the fault injector run inside
it), so it is slow (about 10 s). The point of the child process is the real
logging setup: an in-process run hides what a default console shows.
"""

import dataclasses
import re

import pytest

from tests.regression import scenarios
from tests.regression.faults import Fault
from tests.regression.runner import run_child

_WARNING = re.compile(r"WARNING - ([^\r\n]*)")


def _run(tmp_path, error, extra_args=()):
    base = scenarios.BY_ID["E1"]
    sc = dataclasses.replace(
        base,
        process="child",
        args=tuple(base.args) + tuple(extra_args),
        faults=(Fault(service="ce", op="GetCostAndUsage", error=error),),
    )
    return run_child(sc, tmp_path)


def _billing_warnings(outcome):
    found = _WARNING.findall(outcome.stdout + "\n" + outcome.stderr)
    return [
        m
        for m in found
        if re.search(r"cost explorer|billing", m, re.I)
        and "Permissions:" not in m  # the summary of denied actions has its own tests
        # F1b: the request count said before discovery (tests/unit/test_cost_requests.py)
        and not m.startswith("Cost Explorer: up to")
    ]


@pytest.mark.parametrize(
    "error, cause",
    [
        ("AccessDeniedException", "AccessDeniedException"),
        ("ThrottlingException", "ThrottlingException"),
    ],
)
def test_default_run_shows_exactly_one_billing_warning_with_the_cause(
    tmp_path, error, cause
):
    outcome = _run(tmp_path, error)
    lines = _billing_warnings(outcome)
    assert outcome.code == 0
    assert len(lines) == 1, lines
    assert cause in lines[0], lines[0]


def test_debug_run_still_shows_the_detail_lines(tmp_path):
    outcome = _run(tmp_path, "AccessDeniedException", extra_args=("--debug",))
    lines = _billing_warnings(outcome)
    assert outcome.code == 0
    assert len(lines) >= 1, lines
