"""Tier 2 of the failure regression suite: one row, one CLI run against moto.

Each row of ``scenarios.MATRIX_ROWS`` gets two tests that share one run:

``test_pins``    what is right today stays right (always asserted).
``test_target``  behaviour under the accepted decisions O1 to O12. While the row names a
                 work package (``wp``), the test is ``xfail(strict=True, reason=<ID>)``;
                 when the package lands it removes ``wp`` from the row and the test must pass.

How a row becomes a test: ``scenarios.py`` holds the injection (seed, accounts, faults,
limits, steps) and the checks; ``runner.py`` runs it; ``checks.py`` evaluates the checks.
The shared invariants are checked for every row in ``test_invariants``.
"""

import pytest

from tests.regression import scenarios
from tests.regression.checks import failures
from tests.regression.runner import run_child, run_in_process

_RUNS = {}


def _outcome(sc, tmp_path, monkeypatch):
    """Run the row once; the pins test and the target test share the result."""
    if sc.id not in _RUNS:
        if sc.process == "child":
            _RUNS[sc.id] = run_child(sc, tmp_path)
        else:
            _RUNS[sc.id] = run_in_process(sc, tmp_path, monkeypatch)
    return _RUNS[sc.id]


def _params():
    params = []
    for row in scenarios.MATRIX_ROWS:
        marks = [pytest.mark.slow] if row.slow else []
        params.append(pytest.param(row, id=row.id, marks=marks))
    return params


def _target_checks(sc):
    checks = list(sc.target)
    if not any(c[0] == "code" for c in checks):
        checks.insert(0, ("code", sc.code))
    checks += [("issue", key) for key in sc.issue_keys]
    return checks


@pytest.mark.parametrize("sc", _params())
def test_pins(sc, tmp_path, monkeypatch):
    outcome = _outcome(sc, tmp_path, monkeypatch)
    bad = failures(sc.pins, outcome)
    assert not bad, f"{sc.id}: {bad}\n--- output ---\n{outcome.text[-3000:]}"


@pytest.mark.parametrize("sc", _params())
def test_target(sc, tmp_path, monkeypatch, request):
    if sc.wp:
        request.applymarker(pytest.mark.xfail(strict=True, reason=sc.id))
    outcome = _outcome(sc, tmp_path, monkeypatch)
    bad = failures(_target_checks(sc), outcome)
    assert not bad, f"{sc.id} ({sc.wp or 'true today'}): {bad}"


@pytest.mark.parametrize("sc", _params())
def test_invariants(sc, tmp_path, monkeypatch):
    """Invariants that must hold after every row, whatever went wrong in it."""
    outcome = _outcome(sc, tmp_path, monkeypatch)
    # I2: no zero-byte or temporary file in the output folder
    stray = [
        p for p in outcome.out_dir.rglob("*")
        if p.is_file() and (p.stat().st_size == 0 or p.suffix == ".tmp")
        and not p.name.endswith("inventag.log")
    ]
    assert not stray, f"{sc.id}: zero-byte or temporary files: {stray}"
    # I5: no secret in any output (the fake keys of the harness)
    for secret in ("regression-secret-key-0000000000000000",):
        assert secret not in outcome.text, f"{sc.id}: a secret is in the output"
    # I6: the read-only guard never blocked a call the row did not ask for
    assert "Blocked AWS operation" not in outcome.text, f"{sc.id}: the read-only guard blocked a call"
