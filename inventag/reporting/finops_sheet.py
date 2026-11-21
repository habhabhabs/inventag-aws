"""The "FinOps" sheet of the Excel report (``--finops-checks``).

It shows the ``finops_checks`` result as it is: the listed findings, then a
small table of counts per check. No value is read from anywhere else.
"""

from typing import Any, Dict

from openpyxl.styles import Font

SHEET_NAME = "FinOps"
NOTE = (
    "These are observations from the inventory. A resource listed here may be "
    "intended."
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
_FIELDS = [
    "policy",
    None,  # the check's title, from the summary
    "result",
    "reason",
    "account",
    "region",
    "service",
    "resource_type",
    "resource",
    "name",
    "message",
]
SUMMARY_COLUMNS = ["Check ID", "Check", "Fail", "Not evaluated", "Pass"]


def _put(ws, row: int, column: int, value: Any) -> None:
    if value in ("", None):
        return
    cell = ws.cell(row=row, column=column, value=value)
    if cell.data_type == "f":  # data that starts with "=" stays text
        cell.data_type = "s"


def add_finops_sheet(wb, finops: Dict[str, Any]):
    """Add the sheet as the last sheet of ``wb`` and return it."""
    ws = wb.create_sheet(SHEET_NAME)
    titles = {s["policy"]: s["check"] for s in finops.get("summary", [])}
    bold = Font(bold=True)

    _put(ws, 1, 1, NOTE)
    for column, name in enumerate(COLUMNS, 1):
        _put(ws, 3, column, name)
        ws.cell(row=3, column=column).font = bold
    row = 4
    for finding in finops.get("findings", []):
        for column, field in enumerate(_FIELDS, 1):
            value = titles.get(finding["policy"]) if field is None else finding[field]
            _put(ws, row, column, value)
        row += 1

    row += 1
    for column, name in enumerate(SUMMARY_COLUMNS, 1):
        _put(ws, row, column, name)
        ws.cell(row=row, column=column).font = bold
    for entry in finops.get("summary", []):
        row += 1
        values = [
            entry["policy"],
            entry["check"],
            entry["fail"],
            entry["not_evaluated"],
            entry["pass"],
        ]
        for column, value in enumerate(values, 1):
            if isinstance(value, int):
                ws.cell(row=row, column=column, value=value)
            else:
                _put(ws, row, column, value)

    for letter, width in zip(
        "ABCDEFGHIJK", (10, 42, 14, 16, 14, 16, 10, 16, 30, 24, 46)
    ):
        ws.column_dimensions[letter].width = width
    return ws
