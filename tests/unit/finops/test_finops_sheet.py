"""The "FinOps" sheet: columns, order, note line and the summary table (golden)."""

import datetime as dt

from openpyxl import Workbook

from inventag.finops import checks
from inventag.reporting import finops_sheet
from tests.unit.finops.test_checks_rules import (
    RUN,
    address,
    instance,
    snapshot,
    unit,
    volume,
)

COLUMNS = [
    "Check ID",
    "Check",
    "Result",
    "Reason",
    "Account",
    "Region",
    "Service",
    "Resource Type",
    "Resource ID",
    "Name",
    "Observed",
]
NOTE = (
    "These are observations from the inventory. A resource listed here may be "
    "intended."
)


def build(result):
    wb = Workbook()
    wb.remove(wb["Sheet"])
    wb.create_sheet("Summary")
    finops_sheet.add_finops_sheet(wb, result)
    return wb


def values(ws):
    return [tuple(row) for row in ws.iter_rows(values_only=True)]


def sample():
    rows = [
        volume("vol-1", tags={"Owner": "x"}),
        address("eipalloc-1", "eipassoc-1"),
        snapshot("snap-1", RUN - dt.timedelta(days=100)),
        instance("i-1", "running"),
    ]
    return checks.run_checks(rows, [unit("elb")], RUN)


def test_the_column_names_and_note_are_the_decided_ones():
    assert finops_sheet.SHEET_NAME == "FinOps"
    assert finops_sheet.COLUMNS == COLUMNS
    assert finops_sheet.NOTE == NOTE


def test_the_sheet_comes_after_the_existing_sheets():
    wb = build(sample())
    assert wb.sheetnames == ["Summary", "FinOps"]


def test_golden_sheet():
    a, r = "111122223333", "ap-southeast-1"
    assert values(build(sample())["FinOps"]) == [
        (NOTE,) + (None,) * 10,
        (None,) * 11,
        tuple(COLUMNS),
        (
            "FIN-001",
            checks.CHECKS["FIN-001"],
            "fail",
            None,
            a,
            r,
            "EC2",
            "Volume",
            "vol-1",
            "name-vol-1",
            "no attachment",
        ),
        (
            "FIN-003",
            checks.CHECKS["FIN-003"],
            "fail",
            None,
            a,
            r,
            "EC2",
            "Snapshot",
            "snap-1",
            "name-snap-1",
            "started 2026-08-13",
        ),
        (
            "FIN-005",
            checks.CHECKS["FIN-005"],
            "not_evaluated",
            "listing_not_read",
            a,
            r,
            "elb",
            None,
            None,
            None,
            "elb listing in ap-southeast-1 not read (denied)",
        ),
        (
            "FIN-006",
            checks.CHECKS["FIN-006"],
            "not_evaluated",
            "listing_not_read",
            a,
            r,
            "elb",
            None,
            None,
            None,
            "elb listing in ap-southeast-1 not read (denied)",
        ),
        (
            "FIN-006",
            checks.CHECKS["FIN-006"],
            "fail",
            None,
            a,
            r,
            "EC2",
            "Volume",
            "vol-1",
            "name-vol-1",
            "missing: CostCenter, Project, Environment",
        ),
        (None,) * 11,
        ("Check ID", "Check", "Fail", "Not evaluated", "Pass") + (None,) * 6,
        ("FIN-001", checks.CHECKS["FIN-001"], 1, 0, 0) + (None,) * 6,
        ("FIN-002", checks.CHECKS["FIN-002"], 0, 0, 1) + (None,) * 6,
        ("FIN-003", checks.CHECKS["FIN-003"], 1, 0, 0) + (None,) * 6,
        ("FIN-004", checks.CHECKS["FIN-004"], 0, 0, 1) + (None,) * 6,
        ("FIN-005", checks.CHECKS["FIN-005"], 0, 1, 0) + (None,) * 6,
        ("FIN-006", checks.CHECKS["FIN-006"], 1, 1, 3) + (None,) * 6,
    ]


def test_an_empty_result_still_has_the_note_header_and_summary():
    rows = values(build(checks.run_checks([], [], RUN))["FinOps"])
    assert rows[0][0] == NOTE
    assert rows[2] == tuple(COLUMNS)
    assert rows[4][:5] == ("Check ID", "Check", "Fail", "Not evaluated", "Pass")
    assert len(rows) == 5 + len(checks.CHECKS)


def test_a_value_that_looks_like_a_formula_is_kept_as_text():
    row = volume("=HYPERLINK(1)")
    row["resource_name"] = "=cmd|' /C calc'!A0"
    wb = build(checks.run_checks([row], [], RUN))
    cells = [c for r in wb["FinOps"].iter_rows() for c in r if c.value]
    for cell in cells:
        if isinstance(cell.value, str) and cell.value.startswith("="):
            assert cell.data_type == "s"
