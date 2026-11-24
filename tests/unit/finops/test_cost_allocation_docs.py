"""Docs of --finops-cost-allocation in five languages (security review F3)."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PAGES = [REPO / "docs"] + [
    REPO / "website" / "translations" / loc / "docs"
    for loc in ("es", "fr", "zh-Hans", "zh-Hant")
]


def test_the_readonlyaccess_option_names_the_new_action():
    for docs in PAGES:
        text = (docs / "guides" / "read-only-access.md").read_text(encoding="utf-8")
        assert "ce:ListCostAllocationTags" in text, docs
        assert "--finops-cost-allocation" in text, docs


def test_the_guide_says_what_a_payer_accounts_tables_can_hold():
    for docs in PAGES:
        text = (docs / "guides" / "finops-checks.md").read_text(encoding="utf-8")
        start = text.index("cost_allocation`")
        part = text[start : start + 2500]
        assert "--no-cost-in-snapshot" in part, docs
        assert "999988887777" not in part  # the test value stays in the tests
        assert (
            ("payer" in part)
            or ("pagadora" in part)
            or ("payeur" in part)
            or ("付费" in part or "付費" in part)
        ), docs
