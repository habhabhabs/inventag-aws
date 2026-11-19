"""The scenario table covers the plan: every ID exactly once, no hole, no stray row."""

import os
import re
from pathlib import Path

import pytest

from tests.regression import scenarios

HERE = Path(__file__).parent
SNAPSHOT = HERE / "plan_ids.txt"
DEFAULT_PLAN = Path("/home/claude/audit/reports/failure-regression-plan.md")
RUNNERS = {"matrix", "tier1", "tier2", "tier1+tier2", "existing", "none"}


def _expand(cell):
    ids = []
    for part in re.split(r",\s*", cell.strip()):
        m = re.match(r"([A-L])(\d+)-([A-L])?(\d+)$", part)
        if m:
            ids += [
                f"{m.group(1)}{n}" for n in range(int(m.group(2)), int(m.group(4)) + 1)
            ]
        else:
            ids.append(part)
    return ids


def ids_from_plan(path):
    """IDs of the tables in sections 3 and 7 (first column, ranges expanded)."""
    ids, in_tables = [], False
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            in_tables = line.startswith(("## 3.", "## 7."))
            continue
        m = re.match(r"\| ([A-L]\d+(?:[-,] ?[A-L]?\d+)*) \|", line)
        if in_tables and m:
            ids += _expand(m.group(1))
    return ids


def plan_ids():
    path = Path(os.environ.get("INVENTAG_FAILURE_PLAN", DEFAULT_PLAN))
    if path.is_file():
        return sorted(set(ids_from_plan(path)))
    return sorted(
        line.strip()
        for line in SNAPSHOT.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    )


def test_snapshot_matches_the_plan_when_the_plan_is_available():
    path = Path(os.environ.get("INVENTAG_FAILURE_PLAN", DEFAULT_PLAN))
    if not path.is_file():
        pytest.skip("the plan file is not on this machine")
    snapshot = sorted(
        line.strip()
        for line in SNAPSHOT.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    )
    assert snapshot == sorted(
        set(ids_from_plan(path))
    ), "update tests/regression/plan_ids.txt"


def test_the_plan_has_ids():
    assert len(plan_ids()) > 90


def test_every_plan_id_appears_exactly_once_in_the_table():
    counts = {}
    for row in scenarios.PLAN:
        counts[row.id] = counts.get(row.id, 0) + 1
    missing = [i for i in plan_ids() if i not in counts]
    twice = [i for i, n in counts.items() if n > 1]
    stray = [i for i in counts if i not in set(plan_ids())]
    assert not missing, f"plan IDs missing from scenarios.py: {missing}"
    assert not twice, f"IDs listed twice: {twice}"
    assert not stray, f"IDs that are not in the plan: {stray}"


def test_extra_rows_have_their_own_prefix_and_never_reuse_a_plan_id():
    ids = [row.id for row in scenarios.EXTRA]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("S1-") for i in ids)
    assert not set(ids) & {row.id for row in scenarios.PLAN}


def test_all_ids_are_unique_in_the_final_table():
    ids = [row.id for row in scenarios.ROWS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("row", scenarios.ROWS, ids=lambda r: r.id)
def test_every_row_is_described(row):
    assert row.title.strip()
    assert row.runner in RUNNERS
    assert row.owner.strip()


@pytest.mark.parametrize("row", scenarios.MATRIX_ROWS, ids=lambda r: r.id)
def test_matrix_rows_are_complete(row):
    assert (
        row.current or row.skip
    ), "a matrix row records what v1.2.0 does today (or says why it is skipped)"
    assert (
        any(c[0] == "code" for c in row.current) or row.skip
    ), "the current behaviour names an exit code"
    assert row.source in {"run", "code"}
    if row.wp:
        assert (
            row.target or row.code or row.issue_keys
        ), "a row waiting for a work package needs a target"
    if row.issue_keys:
        assert all(re.match(r"^[a-z_]+(:[a-z0-9_-]+)?$", k) for k in row.issue_keys)
    if row.process == "child":
        assert row.signal or row.slow


def _named_tests(row):
    """``(path, test name)`` pairs of a row's ``where`` ("tests/x.py::name; ...")."""
    pairs = []
    for part in row.where.split(";"):
        part = part.strip()
        if part.startswith("tests/") and "::" in part:
            path, name = part.split("::", 1)
            pairs.append((path, name.split()[0]))
    return pairs


EXISTING_WITH_TESTS = [
    row for row in scenarios.ROWS if row.runner == "existing" and _named_tests(row)
]


def test_the_rows_added_from_unit_tests_name_tests_that_exist():
    ids = {row.id for row in EXISTING_WITH_TESTS}
    assert {
        "A2",
        "A5",
        "C3",
        "H2",
        "H8",
        "I2",
        "S1-I7-skipped-upload-is-told",
        "S1-I4d-sheet-url-when-the-doc-fails",
        "S1-I1d-wrong-bucket-region-hint",
        "S1-G4a-upload-bound-to-the-bucket",
        "S1-T17-one-format-fails-the-others-are-written",
    } <= ids


@pytest.mark.parametrize("row", EXISTING_WITH_TESTS, ids=lambda r: r.id)
def test_every_test_an_existing_row_names_is_defined(row):
    root = HERE.parent.parent
    for path, name in _named_tests(row):
        source = (root / path).read_text()
        assert re.search(rf"^\s*def {re.escape(name)}\(", source, re.M), (path, name)
