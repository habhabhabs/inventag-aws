"""Every built-in template loads without a warning and renders what
``docs/templates/catalogue.md`` says it renders (sheet names, Word outline).

The estate is the captured sample (``sample_resources.json``, an offline run
against moto), the same one the catalogue's sample blocks come from.
"""

import json
import logging
import re
from pathlib import Path

import pytest
from docx import Document
from openpyxl import load_workbook

from inventag.templating import cli as templates_cli
from inventag.templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry
from inventag.templating.render_excel import render_excel
from inventag.templating.render_word import render_word
from inventag.templating.runner import load_templates
from inventag.templating.tag_policy import evaluate

HERE = Path(__file__).parent
CATALOGUE = Path(__file__).parents[3] / "docs" / "templates" / "catalogue.md"
ALL = sorted(p.stem for p in BUILTIN_DIR.glob("*.yaml"))
REPORTS = ["standard-bom", "executive-summary", "finops-cost-report"]


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])


@pytest.fixture(scope="module")
def estate():
    return json.loads((HERE / "sample_resources.json").read_text())["resources"]


def _catalogue_sheets():
    """Sheet lists of the catalogue, keyed by the heading above them."""
    found = {}
    heading = None
    for line in CATALOGUE.read_text().splitlines():
        if line.startswith("### "):
            heading = line[4:].strip("` ")
        match = re.match(r"\*\*Sheets:\*\* (.*)", line)
        if match and heading:
            found.setdefault(heading, []).append(re.findall(r"`([^`]+)`", match[1]))
    return found


@pytest.mark.parametrize("name", ALL)
def test_builtin_loads_without_a_warning(name, registry, caplog, capsys):
    with caplog.at_level(logging.WARNING):
        load_templates([name], registry)
    assert [r.getMessage() for r in caplog.records] == []
    assert templates_cli.main(["validate", name]) == 0
    lines = capsys.readouterr().out.splitlines()
    warnings = [line for line in lines if line.startswith("WARNING")]
    if name == "org-multi-account":
        # The catalogue says so: the three account IDs are placeholders.
        assert len(warnings) == 1 and "look like placeholders" in warnings[0]
    else:
        assert warnings == []


def _render(tmp_path, registry, estate, name):
    template = registry.resolve(name)
    policy_ref = template.spec.get("tag_policy")
    compliance = evaluate(estate, registry.resolve(policy_ref)) if policy_ref else None
    xlsx = render_excel(str(tmp_path / f"{name}.xlsx"), estate, template, compliance)
    docx = render_word(str(tmp_path / f"{name}.docx"), estate, template, compliance)
    return load_workbook(xlsx).sheetnames, Document(docx)


@pytest.mark.parametrize("name", REPORTS)
def test_sheet_names_match_the_catalogue(name, tmp_path, registry, estate):
    sheets, _ = _render(tmp_path, registry, estate, name)
    listed = _catalogue_sheets()[name]
    assert listed, f"no 'Sheets:' line under '{name}' in catalogue.md"
    # The catalogue's estate has two services (ATHENA, VPC) that the captured
    # sample file lacks, so compare the names the two estates share, in order.
    for expected in listed:
        assert set(sheets) <= set(expected), (name, sheets, expected)
        assert sheets == [x for x in expected if x in sheets], (name, sheets)
        assert sheets[0] == "Summary"
        assert (sheets[-1] == "Tag Compliance") == ("Tag Compliance" in expected)


def _outline(doc):
    return [
        p.text
        for p in doc.paragraphs
        if p.style.name.startswith("Heading 1") or p.style.name == "Title"
    ]


def test_word_outlines_match_the_catalogue(tmp_path, registry, estate):
    outlines = {
        name: _outline(_render(tmp_path, registry, estate, name)[1]) for name in REPORTS
    }
    assert outlines["standard-bom"] == [
        "AWS Resource Inventory",
        "Summary",
        "Resources by service",
        "Resource details",
        "About this report",
    ]
    assert outlines["executive-summary"] == [
        "AWS Inventory Summary",
        "Summary",
        "Resources by service",
        "About this report",
    ]
    # catalogue.md: "Cover, summary, tag compliance, resources by service, about"
    assert outlines["finops-cost-report"][1:] == [
        "Summary",
        "Tag compliance",
        "Resources by service",
        "About this report",
    ]
