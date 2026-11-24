"""The "FinOps costs" sheet (golden), and the wording of the feature."""

import re
from pathlib import Path

from openpyxl import Workbook

from inventag.finops import cost_allocation as ca
from inventag.reporting import finops_costs_sheet as sheet

REPO = Path(__file__).resolve().parents[3]
BANNED = re.compile(r"\b(savings?|waste|wasted|wasteful|compliant)\b", re.I)


def costs():
    return ca.result(
        [
            {
                "account": "111122223333",
                "period": {"start": "2026-10-01", "end": "2026-11-01"},
                "metric": "UnblendedCost",
                "requests": 4,
                "tag_keys": [],
                "tables": {
                    "service": {
                        "status": "read",
                        "currency": "USD",
                        "rows": [{"name": "AmazonS3", "amount": "12.5", "unit": "USD"}],
                    },
                    "linked_account": {"status": "denied", "currency": "", "rows": []},
                    "tag:CostCenter": {
                        "status": "read",
                        "currency": "USD",
                        "rows": [
                            {"name": "(no value)", "amount": "2.5", "unit": "USD"},
                            {"name": "=cmd", "amount": "10.0", "unit": "USD"},
                        ],
                    },
                    "tag:Owner": {"status": "not_active", "currency": "", "rows": []},
                },
                "failed": [],
            }
        ]
    )


def build(data):
    wb = Workbook()
    wb.remove(wb["Sheet"])
    wb.create_sheet("Summary")
    sheet.add_finops_costs_sheet(wb, data)
    return wb


def test_names_and_place():
    assert sheet.SHEET_NAME == "FinOps costs"
    assert build(costs()).sheetnames == ["Summary", "FinOps costs"]


def test_golden_sheet():
    a, p = "111122223333", ("UnblendedCost", "2026-10-01", "2026-11-01")
    rows = [
        tuple(r) for r in build(costs())["FinOps costs"].iter_rows(values_only=True)
    ]
    assert rows == [
        (sheet.NOTE,) + (None,) * 8,
        ("(no value): spend without that tag key.",) + (None,) * 8,
        (None,) * 9,
        tuple(sheet.COLUMNS),
        (a, "Service", "AmazonS3", "12.5", "USD", *p, None),
        (a, "Linked account", None, None, None, *p, "not read: access denied"),
        (a, "Tag CostCenter", "(no value)", "2.5", "USD", *p, None),
        (a, "Tag CostCenter", "=cmd", "10.0", "USD", *p, None),
        (a, "Tag Owner", None, None, None, *p, "not active as a cost allocation tag"),
    ]


def test_a_value_that_looks_like_a_formula_stays_text():
    ws = build(costs())["FinOps costs"]
    cell = next(c for r in ws.iter_rows() for c in r if c.value == "=cmd")
    assert cell.data_type == "s"


def test_the_note_says_no_cost_per_resource():
    assert "not costs of single resources" in sheet.NOTE
    assert "own credentials" in sheet.NOTE


def test_no_banned_word_in_the_sources_and_the_sheet():
    for path in (
        REPO / "inventag" / "finops" / "cost_allocation.py",
        REPO / "inventag" / "reporting" / "finops_costs_sheet.py",
    ):
        assert BANNED.findall(path.read_text(encoding="utf-8")) == [], path
    texts = [
        str(v)
        for r in build(costs())["FinOps costs"].iter_rows(values_only=True)
        for v in r
        if v
    ]
    texts += ca.run_notes(costs()) + [
        ca.status_text(s)
        for s in (
            "not_active",
            "not_found",
            "not_queried",
            "incomplete",
            "denied",
            "throttled",
            "error",
        )
    ]
    for text in texts:
        assert not BANNED.search(text), text
