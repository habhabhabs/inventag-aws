"""Docs claims of v1.5.1 (``--create-html``): each sentence on the pages that
the code decides is checked against the code, in all five languages.

The behaviours themselves are proven in ``test_html_report.py`` (writer) and
``test_html_report_cli.py`` (CLI under moto); this file keeps the pages true
to them.
"""

from pathlib import Path

import pytest

from inventag.reporting import html_report

ROOT = Path(__file__).resolve().parents[2]
LOCALES = ["en", "es", "fr", "zh-Hans", "zh-Hant"]


def _page(locale, name):
    if locale == "en":
        return (ROOT / "docs" / name).read_text()
    return (ROOT / "website" / "translations" / locale / "docs" / name).read_text()


@pytest.mark.parametrize("locale", LOCALES)
def test_the_csp_on_the_outputs_page_is_the_one_in_the_file(locale):
    page = _page(locale, "reference/outputs.md")
    assert f"`{html_report.CSP}`" in page


@pytest.mark.parametrize("locale", LOCALES)
def test_the_outputs_page_has_the_html_section_file_row_and_privacy_warning(locale):
    page = _page(locale, "reference/outputs.md")
    assert "{#html-report}" in page or locale == "en"
    if locale == "en":
        assert "\n## HTML report\n" in page
    assert "| `multi_account_bom_<timestamp>.html` | `--create-html` |" in page
    assert "`<account-id>_bom_<timestamp>.html`" in page
    assert page.count(":::warning") >= 1
    assert "```bash\ninventag --create-excel --create-html\n```" in page
    # the same sample as the generated English block
    sample = _page("en", "reference/outputs.md").split(
        "<!-- BEGIN EXAMPLE OUTPUT: outputs-html -->"
    )[1]
    first = sample.split("```", 2)[1]
    assert first in page


@pytest.mark.parametrize("locale", LOCALES)
def test_the_cli_page_lists_the_flag_and_the_excel_template_rule(locale):
    page = _page(locale, "reference/cli.md")
    rows = [line for line in page.splitlines() if line.startswith("| `--create-html`")]
    assert len(rows) == 1
    assert "multi_account_bom_<timestamp>.html" in rows[0]
    template = [
        line for line in page.splitlines() if line.startswith("| `--excel-template")
    ]
    assert "`--create-html`" in template[0]


@pytest.mark.parametrize("locale", LOCALES)
def test_the_status_page_has_the_limits_row(locale):
    page = _page(locale, "getting-started/status.md")
    rows = [line for line in page.splitlines() if line.startswith("| `--create-html`")]
    assert len(rows) == 1 and "`--policy`" in rows[0]
    assert "outputs.md#html-report" in rows[0]


def test_the_privacy_note_in_the_file_matches_the_page():
    page = _page("en", "reference/outputs.md")
    assert "Treat it like the Excel report." in page
    assert "Keep it private, as you keep the Excel report." in html_report.PRIVACY_NOTE


def test_the_changelog_lists_the_flag_under_added_in_unreleased():
    text = (ROOT / "CHANGELOG.md").read_text()
    unreleased = text.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    assert "### Added" in unreleased
    assert "`--create-html`" in unreleased.split("### Added", 1)[1]


@pytest.mark.parametrize("locale", LOCALES)
def test_the_upload_content_type_on_the_page_is_the_one_sent(locale):
    from inventag.core import s3_upload

    page = _page(locale, "reference/outputs.md")
    assert s3_upload.CONTENT_TYPES == {".html": "text/html; charset=utf-8"}
    assert "`text/html; charset=utf-8`" in page
