"""The "FinOps costs" sheet of the Excel report (``--finops-cost-allocation``).

It shows the ``finops_costs`` tables as Cost Explorer returned them: one row
per account, grouping and value. Never a cost per resource.
"""

from typing import Any, Dict

from openpyxl.styles import Font

from ..finops.cost_allocation import NO_VALUE, status_text, table_label

SHEET_NAME = "FinOps costs"
NOTE = (
    "Amounts as Cost Explorer returns them for each account, read with that "
    "account's own credentials, for the last full month. They are not costs "
    "of single resources."
)
COLUMNS = [
    "Account",
    "Grouping",
    "Value",
    "Amount",
    "Currency",
    "Metric",
    "Period start",
    "Period end",
    "Status",
]


def _put(ws, row: int, column: int, value: Any) -> None:
    if value in ("", None):
        return
    cell = ws.cell(row=row, column=column, value=value)
    if cell.data_type == "f":  # data that starts with "=" stays text
        cell.data_type = "s"


def add_finops_costs_sheet(wb, costs: Dict[str, Any]):
    """Add the sheet as the last sheet of ``wb`` and return it."""
    ws = wb.create_sheet(SHEET_NAME)
    bold = Font(bold=True)
    _put(ws, 1, 1, NOTE)
    _put(ws, 2, 1, f"{NO_VALUE}: spend without that tag key.")
    for column, name in enumerate(COLUMNS, 1):
        _put(ws, 4, column, name)
        ws.cell(row=4, column=column).font = bold
    row = 5
    metric = costs.get("metric", "")
    for account in costs.get("accounts", []):
        period = account.get("period", {})
        for name, table in account.get("tables", {}).items():
            base = [account["account"], table_label(name)]
            tail = [metric, period.get("start"), period.get("end")]
            rows = table.get("rows", [])
            if not rows:
                values = base + [None, None, table.get("currency")] + tail
                values.append(status_text(table["status"]) or "no spend returned")
                for column, value in enumerate(values, 1):
                    _put(ws, row, column, value)
                row += 1
                continue
            for item in rows:
                values = base + [item["name"], item["amount"], item["unit"]] + tail
                values.append(status_text(table["status"]))
                for column, value in enumerate(values, 1):
                    _put(ws, row, column, value)
                row += 1
    for letter, width in zip("ABCDEFGHI", (16, 18, 40, 16, 10, 16, 14, 14, 44)):
        ws.column_dimensions[letter].width = width
    return ws
