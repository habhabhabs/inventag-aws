"""Wording of the FinOps checks: a finding says what was observed.

Never "savings", "waste", "wasted" or "compliant" in the module's strings, the
sheet or the FinOps docs pages."""

import datetime as dt
import re
from pathlib import Path

from openpyxl import Workbook

from inventag.finops import checks
from inventag.reporting import finops_sheet
from tests.unit.finops import test_checks_rules as rules

REPO = Path(__file__).resolve().parents[3]
BANNED = re.compile(r"\b(savings?|waste|wasted|wasteful|compliant)\b", re.I)
LOCALES = ("es", "fr", "zh-Hans", "zh-Hant")


def sources():
    yield from sorted((REPO / "inventag" / "finops").glob("*.py"))
    yield REPO / "inventag" / "reporting" / "finops_sheet.py"


def docs_pages():
    yield REPO / "docs" / "guides" / "finops-checks.md"
    for locale in LOCALES:
        yield (
            REPO
            / "website"
            / "translations"
            / locale
            / "docs"
            / "guides"
            / "finops-checks.md"
        )


def every_result():
    started = rules.RUN
    rows = [
        rules.volume("vol-1", tags={}),
        rules.volume("vol-2", None),
        rules.address("eipalloc-1"),
        rules.snapshot("snap-1", started - dt.timedelta(days=200)),
        rules.snapshot("snap-2", None),
        rules.instance("i-1"),
        rules.lb_v2("lb", "arn:lb"),
        rules.lb_v2("lb2"),
        rules.target_group("tg", None),
        rules.classic("c", []),
        rules.identity_row("arn:aws:ec2:eu-west-1:111122223333:volume/vol-9", "vol-9"),
    ]
    units = [
        rules.unit("ec2"),
        rules.unit("resourcegroupstaggingapi", source="tagging-api"),
    ]
    return checks.run_checks(rows, units, started)


def test_no_banned_word_in_the_module_sources():
    for path in sources():
        found = BANNED.findall(path.read_text(encoding="utf-8"))
        assert found == [], f"{path}: {found}"


def test_no_banned_word_in_any_finding_or_the_sheet():
    result = every_result()
    reasons = {f["reason"] for f in result["findings"]}
    assert reasons >= {
        "identity_only",
        "field_missing",
        "tags_not_read",
        "listing_not_read",
    }
    wb = Workbook()
    finops_sheet.add_finops_sheet(wb, result)
    texts = [
        str(v) for row in wb["FinOps"].iter_rows(values_only=True) for v in row if v
    ]
    texts += [s["check"] for s in result["summary"]]
    texts += [f["message"] for f in result["findings"]]
    for text in texts:
        assert not BANNED.search(text), text


def test_a_finding_says_what_was_observed_not_what_to_do():
    imperative = re.compile(r"\b(delete|remove|terminate|release|should|must)\b", re.I)
    for f in every_result()["findings"]:
        assert not imperative.search(f["message"]), f["message"]
    for title in checks.CHECKS.values():
        assert not imperative.search(title), title


def test_no_banned_word_in_the_docs_pages():
    for path in docs_pages():
        assert path.is_file(), path
        found = BANNED.findall(path.read_text(encoding="utf-8"))
        assert found == [], f"{path}: {found}"
