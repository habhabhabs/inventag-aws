"""Field descriptions in ``schema.py`` that were checked against the code.

Each test pins one sentence of the template field reference. If a test here
fails, the sentence in ``schema.py`` (and ``docs/templates/reference.md``,
regenerated with ``python -m inventag.templating.reference --write``) is wrong.
"""

import json
import zipfile

from docx import Document
from openpyxl import load_workbook

from inventag.templating.render_excel import render_excel
from inventag.templating.render_word import render_word
from inventag.templating.runner import load_templates
from inventag.templating.schema import CONFIG_SPEC, REPORT_SPEC, TAG_POLICY_SPEC
from inventag.templating.tag_policy import evaluate

from .conftest import write

RESOURCES = [
    {
        "service": "S3",
        "resource_type": "Bucket",
        "resource_id": "b1",
        "resource_name": "b1",
        "arn": "arn:aws:s3:::b1",
        "region": "us-east-1",
        "source_account_id": "111111111111",
        "tags": {},
    }
]


def _all_text(tmp_path, registry, name):
    template = registry.resolve(name)
    compliance = evaluate(RESOURCES, registry.resolve("finops-cost-allocation"))
    xlsx = render_excel(str(tmp_path / "r.xlsx"), RESOURCES, template, compliance)
    docx = render_word(str(tmp_path / "r.docx"), RESOURCES, template, compliance)
    cells = [
        str(c.value)
        for ws in load_workbook(xlsx)
        for row in ws.iter_rows()
        for c in row
    ]
    paragraphs = [p.text for p in Document(docx).paragraphs]
    tables = [c.text for t in Document(docx).tables for r in t.rows for c in r.cells]
    return "\n".join(cells + paragraphs + tables + [json.dumps(compliance.to_dict())])


def test_tag_rule_description_is_not_shown_in_any_output(tmp_path, registry):
    policy = registry.resolve("finops-cost-allocation")
    sentence = policy.spec["required_tags"][0]["description"]
    assert sentence == "Budget that pays for the resource."
    assert sentence not in _all_text(tmp_path, registry, "standard-bom")
    description = TAG_POLICY_SPEC["required_tags"].item.fields["description"]
    assert "not shown in the reports" in description.description


def test_word_tables_ignore_column_width(tmp_path, registry, user_dir):
    def document(width):
        extra = f", width: {width}" if width else ""
        write(
            user_dir / "w.yaml",
            "format_version: 1\nkind: report\nname: w\nspec:\n  columns:\n"
            f"    - {{field: resource_id{extra}}}\n",
        )
        path = render_word(
            str(tmp_path / f"w{width}.docx"), RESOURCES, registry.resolve("w")
        )
        return zipfile.ZipFile(path).read("word/document.xml")

    assert document(None) == document(100)
    assert (
        "Word tables ignore it"
        in REPORT_SPEC["columns"].item.fields["width"].description
    )


def test_company_name_is_in_no_file_property(tmp_path, registry, user_dir):
    write(
        user_dir / "c.yaml",
        "format_version: 1\nkind: report\nname: c\nspec:\n  company_name: Acme Ltd\n",
    )
    template = registry.resolve("c")
    xlsx = render_excel(str(tmp_path / "c.xlsx"), RESOURCES, template)
    docx = render_word(str(tmp_path / "c.docx"), RESOURCES, template)
    for path in (xlsx, docx):
        with zipfile.ZipFile(path) as archive:
            properties = b"".join(
                archive.read(n) for n in archive.namelist() if n.startswith("docProps/")
            )
        assert b"Acme Ltd" not in properties
    text = REPORT_SPEC["company_name"].description
    assert "not stored in the file properties" in text


def test_logo_alt_text_default_without_company_name(tmp_path, registry, user_dir):
    from tests.integration.templating.test_report_templates import tiny_png

    (user_dir / "logo.png").write_bytes(tiny_png())
    write(
        user_dir / "l.yaml",
        "format_version: 1\nkind: report\nname: l\nspec:\n  logo: logo.png\n",
    )
    docx = render_word(str(tmp_path / "l.docx"), RESOURCES, registry.resolve("l"))
    with zipfile.ZipFile(docx) as archive:
        assert b'descr="Logo"' in archive.read("word/document.xml")
    assert "or `Logo`" in REPORT_SPEC["logo_alt_text"].description


def test_config_tag_policy_wins_over_the_report_tag_policy(tmp_path, registry):
    write(
        tmp_path / "r.yaml",
        "format_version: 1\nkind: report\nname: r\nspec:\n  tag_policy: security-baseline\n",
    )
    write(
        tmp_path / "c.yaml",
        "format_version: 1\nkind: config\nname: c\nspec:\n"
        "  tag_policy: finops-cost-allocation\n",
    )
    run = load_templates([str(tmp_path / "r.yaml"), str(tmp_path / "c.yaml")], registry)
    assert run.policy.name == "finops-cost-allocation"
    text = REPORT_SPEC["tag_policy"].description
    assert "command line" in text and "of a config template" in text
    assert CONFIG_SPEC["tag_policy"].description  # the config field is unchanged
