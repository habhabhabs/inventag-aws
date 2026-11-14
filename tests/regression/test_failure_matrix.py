"""Tier 2 of the failure regression suite: one row, one CLI run against moto.

Each row of ``scenarios.MATRIX_ROWS`` gets two tests that share one run:

``test_current``     what v1.2.0 does today (exit code, files, messages). Always asserted.
``test_invariants``  what must hold after every row, whatever went wrong in it.

The row's ``target`` (what the accepted plan wants later) is data in ``scenarios.py``;
it is not asserted here. Run with ``INVENTAG_REGRESSION_DUMP=<folder>`` to get one text file
per row: what the run did, and which target checks do not hold today.

How a row becomes a test: ``scenarios.py`` holds the injection (seed, accounts, faults,
limits, steps) and the checks; ``runner.py`` runs it; ``checks.py`` evaluates the checks.
A row with ``skip`` set is skipped with that reason.

Slow rows (``slow=True``, marker ``slow``, left out of the default run by ``pytest.ini``):
B3 and B5 need an account limit above the time of a whole scan (about 8 s), so they take 20 and
30 s; B10 waits for a hung worker to end the process (about 50 s); K1 waits for the scan to run
on after Ctrl-C (14 to 22 s). Run them with ``-m slow``.
"""

import os

import pytest

from tests.regression import scenarios
from tests.regression.checks import failures, sheet_rows, snapshot_counts, summary_sheet
from tests.regression.runner import run_child, run_in_process

_RUNS = {}


def _outcome(sc, tmp_path, monkeypatch):
    """Run the row once; the current test and the invariants test share the result."""
    if sc.id not in _RUNS:
        if sc.process == "child":
            _RUNS[sc.id] = run_child(sc, tmp_path)
        else:
            _RUNS[sc.id] = run_in_process(sc, tmp_path, monkeypatch)
        _dump(sc, _RUNS[sc.id])
    return _RUNS[sc.id]


def _dump(sc, outcome):
    """With INVENTAG_REGRESSION_DUMP=<folder>: write what each row did and which target checks fail."""
    folder = os.environ.get("INVENTAG_REGRESSION_DUMP")
    if not folder:
        return
    os.makedirs(folder, exist_ok=True)
    files = sorted(
        str(p.relative_to(outcome.out_dir))
        for p in outcome.out_dir.rglob("*")
        if p.is_file()
    )
    head = (
        f"exit code: {outcome.code!r}\nseconds: {outcome.wall_seconds:.1f}\n"
        f"seconds after the summary line: {outcome.seconds_after_summary}\nfiles: {files}\n"
        f"sheet rows: {sheet_rows(outcome)}\nsnapshot resource counts: {snapshot_counts(outcome)}\n"
        f"summary sheet: {summary_sheet(outcome)}\n"
        f"cost explorer calls: {sum(1 for c in outcome.calls if c['service'] == 'ce')}\n"
        f"TARGET {sc.target_checks()}\nTARGET NOT MET: {failures(sc.target_checks(), outcome)}\n--- messages ---\n"
    )
    with open(os.path.join(folder, f"{sc.id}.txt"), "w") as fh:
        fh.write(head + "\n".join(outcome.message_lines()))


def _params():
    params = []
    for row in scenarios.MATRIX_ROWS:
        marks = [pytest.mark.slow] if row.slow else []
        params.append(pytest.param(row, id=row.id, marks=marks))
    return params


@pytest.mark.parametrize("sc", _params())
def test_current(sc, tmp_path, monkeypatch):
    if sc.skip:
        pytest.skip(sc.skip)
    outcome = _outcome(sc, tmp_path, monkeypatch)
    bad = failures(sc.current, outcome)
    assert not bad, f"{sc.id}: {bad}\n--- output ---\n{outcome.text[-3000:]}"


@pytest.mark.parametrize("sc", _params())
def test_invariants(sc, tmp_path, monkeypatch):
    """Invariants that must hold after every row, whatever went wrong in it."""
    if sc.skip:
        pytest.skip(sc.skip)
    outcome = _outcome(sc, tmp_path, monkeypatch)
    # I2: no zero-byte or temporary file in the output folder
    stray = [
        p
        for p in outcome.out_dir.rglob("*")
        if p.is_file()
        and (p.stat().st_size == 0 or p.suffix == ".tmp")
        and not p.name.endswith("inventag.log")
    ]
    assert not stray, f"{sc.id}: zero-byte or temporary files: {stray}"
    # I5: no secret in any output (the fake keys of the harness)
    for secret in ("regression-secret-key-0000000000000000",):
        assert secret not in outcome.text, f"{sc.id}: a secret is in the output"
    # I6: the read-only guard never blocked a call the row did not ask for
    assert (
        "Blocked AWS operation" not in outcome.text
    ), f"{sc.id}: the read-only guard blocked a call"
