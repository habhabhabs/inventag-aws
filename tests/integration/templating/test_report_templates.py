"""Generate real Excel and Word files from every built-in report template.

The first group renders the captured sample data (from an offline run against
moto). The second group runs the whole ``inventag`` command in-process against
moto's mocked AWS, so discovery, processing, templates and the exit code are
all exercised together. That group is skipped if ``moto`` is not installed.
"""

import glob
import importlib
import json
import os
import sys
from pathlib import Path

import pytest
from docx import Document
from openpyxl import load_workbook

from inventag.templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry
from inventag.templating.render_excel import render_excel
from inventag.templating.render_word import render_word
from inventag.templating.tag_policy import evaluate

SAMPLE = Path(__file__).parents[2] / "unit" / "templating" / "sample_resources.json"
REPORTS = ["standard-bom", "executive-summary", "finops-cost-report"]


@pytest.fixture(scope="module")
def resources():
    return json.loads(SAMPLE.read_text())["resources"]


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])


def render_both(tmp_path, registry, resources, name, policy_name=None):
    template = registry.resolve(name)
    policy_ref = policy_name or template.spec.get("tag_policy")
    compliance = (
        evaluate(resources, registry.resolve(policy_ref)) if policy_ref else None
    )
    xlsx = render_excel(str(tmp_path / "r.xlsx"), resources, template, compliance)
    docx = render_word(str(tmp_path / "r.docx"), resources, template, compliance)
    return template, load_workbook(xlsx), Document(docx)


def tiny_png():
    import struct
    import zlib

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\x1f\x3a\x5f")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", pixels)
        + chunk(b"IEND", b"")
    )


def headings(doc):
    return [
        (p.style.name, p.text)
        for p in doc.paragraphs
        if p.style.name.startswith(("Heading", "Title"))
    ]


@pytest.mark.parametrize("name", REPORTS)
def test_header_styling_and_freeze(tmp_path, registry, resources, name):
    template, wb, _ = render_both(tmp_path, registry, resources, name)
    fill = template.spec["colors"]["header_fill"]
    for ws in wb.worksheets[1:]:
        cell = ws["A1"]
        assert cell.font.bold
        assert cell.fill.start_color.rgb.endswith(fill)
        assert cell.font.color.rgb.endswith(template.spec["colors"]["header_text"])
        assert ws.freeze_panes == "A2"
        assert ws.auto_filter.ref.startswith("A1:")


def test_standard_bom_excel(tmp_path, registry, resources):
    _, wb, _ = render_both(tmp_path, registry, resources, "standard-bom")
    services = sorted({r["service"] for r in resources}, key=str.lower)
    assert wb.sheetnames == ["Summary"] + services
    s3 = wb["S3"]
    header = [c.value for c in s3[1]]
    assert header[:7] == ["Account", "Region", "Service", "Type", "Name", "ID", "ARN"]
    assert {"Tag: CostCenter", "Tag: Environment", "Tag: Owner", "Tag: Project"} <= set(
        header
    )
    assert s3.max_row == 1 + sum(1 for r in resources if r["service"] == "S3")
    summary = [row for row in wb["Summary"].iter_rows(values_only=True)]
    assert ("Total", len(resources), "100.0%") in summary


def test_standard_bom_word(tmp_path, registry, resources):
    _, _, doc = render_both(tmp_path, registry, resources, "standard-bom")
    names = headings(doc)
    assert names[0] == ("Title", "AWS Resource Inventory")
    assert ("Heading 1", "Resource details") in names
    assert ("Heading 2", "S3 (4)") in names
    assert ("Heading 1", "Tag compliance") not in names  # no policy active
    first = doc.tables[0]
    assert [c.text for c in first.rows[0].cells] == ["Service", "Resources", "Share"]
    xml = first.rows[0]._tr.xml
    assert "w:tblHeader" in xml and "1F3A5F" in xml
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "not affiliated with" in text


def test_executive_summary(tmp_path, registry, resources):
    _, wb, doc = render_both(tmp_path, registry, resources, "executive-summary")
    assert wb.sheetnames == ["Summary", "Resources"]
    header = [c.value for c in wb["Resources"][1]]
    assert "Service" in header and not any(h.startswith("Tag:") for h in header)
    assert wb["Resources"].max_row == len(resources) + 1
    assert ("Heading 1", "Resource details") not in headings(doc)


def test_finops_cost_report_with_compliance(tmp_path, registry, resources):
    _, wb, doc = render_both(tmp_path, registry, resources, "finops-cost-report")
    assert wb.sheetnames[-1] == "Tag Compliance"
    header = [c.value for c in wb["DYNAMODB"][1]]
    assert header[-4:] == [
        "Tag: CostCenter",
        "Tag: Owner",
        "Tag: Project",
        "Tag: Environment",
    ]
    rows = list(wb["Tag Compliance"].iter_rows(min_row=2, values_only=True))
    statuses = {r[6] for r in rows if r and r[6]}
    assert {"Compliant", "Non-compliant"} <= statuses
    names = headings(doc)
    assert ("Heading 1", "Tag compliance") in names
    assert ("Heading 2", "Non-compliant resources") in names


def test_formula_injection_is_neutralised(tmp_path, registry):
    evil = [
        {
            "service": "S3",
            "resource_type": "Bucket",
            "resource_name": '=HYPERLINK("http://example.invalid","x")',
            "tags": {"Owner": "=1+1"},
        }
    ]
    template = registry.resolve("standard-bom")
    wb = load_workbook(render_excel(str(tmp_path / "e.xlsx"), evil, template))
    for row in wb["S3"].iter_rows(min_row=2):
        for cell in row:
            assert cell.data_type != "f"


def test_empty_inventory_still_produces_files(tmp_path, registry):
    template = registry.resolve("standard-bom")
    wb = load_workbook(render_excel(str(tmp_path / "e.xlsx"), [], template))
    assert wb.sheetnames == ["Summary"]
    doc = Document(render_word(str(tmp_path / "e.docx"), [], template))
    assert "No resources were found." in [p.text for p in doc.paragraphs]


def test_logo_with_alt_text_and_landscape(tmp_path, registry, resources):
    png = tiny_png()
    (tmp_path / "logo.png").write_bytes(png)
    path = tmp_path / "branded.yaml"
    path.write_text(
        "kind: report\nname: branded\nextends: executive-summary\nspec:\n"
        "  company_name: Example Co\n  logo: logo.png\n"
        "  word:\n    orientation: landscape\n"
    )
    template = registry.resolve(str(path))
    doc = Document(render_word(str(tmp_path / "b.docx"), resources, template))
    xml = doc.element.body.xml
    assert 'descr="Example Co logo"' in xml
    section = doc.sections[0]
    assert section.page_width > section.page_height


# ---------------------------------------------------------------- full CLI


@pytest.fixture
def aws(monkeypatch):
    moto = pytest.importorskip(
        "moto", reason="moto is needed for the end-to-end CLI tests"
    )
    for key in ("AWS_PROFILE", "AWS_ENDPOINT_URL", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")
    with moto.mock_aws():
        import boto3

        s3 = boto3.client("s3", region_name="us-east-1")
        for name, tags in [
            (
                "good",
                {
                    "CostCenter": "CC-1001",
                    "Owner": "a",
                    "Project": "p",
                    "Environment": "prod",
                },
            ),
            ("bad", {"Environment": "Production"}),
        ]:
            s3.create_bucket(Bucket=name)
            s3.put_bucket_tagging(
                Bucket=name,
                Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in tags.items()]},
            )
        yield


def run_inventag(monkeypatch, tmp_path, *argv):
    cli_main = importlib.import_module("inventag.cli.main")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(sys, "argv", ["inventag", *argv])
    try:
        cli_main.main()
    except SystemExit as stop:
        return stop.code or 0
    return 0


@pytest.mark.parametrize("name", REPORTS)
def test_cli_end_to_end(aws, monkeypatch, tmp_path, name):
    code = run_inventag(
        monkeypatch,
        tmp_path,
        "--template",
        name,
        "--create-excel",
        "--create-word",
        "--account-regions",
        "us-east-1",
    )
    assert code == 0
    xlsx = glob.glob(str(tmp_path / "bom_output" / "multi_account_bom_*.xlsx"))
    docx = glob.glob(str(tmp_path / "bom_output" / "multi_account_bom_*.docx"))
    assert len(xlsx) == 1 and len(docx) == 1
    wb = load_workbook(xlsx[0])
    assert wb.sheetnames[0] == "Summary"
    if name == "finops-cost-report":
        assert "Tag Compliance" in wb.sheetnames
        assert glob.glob(str(tmp_path / "bom_output" / "tag_compliance_*.json"))


def test_cli_ci_config_fails_on_violations(aws, monkeypatch, tmp_path):
    code = run_inventag(monkeypatch, tmp_path, "--template", "ci-pipeline")
    assert code == 3
    files = os.listdir(tmp_path / "bom_output")
    assert any(f.endswith(".xlsx") for f in files)
    assert not any(f.endswith(".docx") for f in files)  # outputs: [excel]
    report = json.load(
        open(glob.glob(str(tmp_path / "bom_output" / "tag_compliance_*.json"))[0])
    )
    assert (
        report["summary"]["compliant"] >= 1 and report["summary"]["non_compliant"] >= 1
    )


def test_cli_invalid_template_exits_1(aws, monkeypatch, tmp_path):
    (tmp_path / "bad.yaml").write_text(
        "kind: report\nname: bad\nspec:\n  excel: {layout: x}\n"
    )
    assert run_inventag(monkeypatch, tmp_path, "--template", "./bad.yaml") == 1
    assert not (tmp_path / "bom_output").exists()


def test_cli_templates_subcommand(monkeypatch, tmp_path, capsys):
    code = run_inventag(monkeypatch, tmp_path, "templates", "list", "--kind", "config")
    assert code == 0
    out = capsys.readouterr().out
    assert "org-multi-account" in out and "standard-bom" not in out


def test_missing_or_unsupported_logo_fails_before_scanning(tmp_path):
    from inventag.templating.errors import TemplateError
    from inventag.templating.runner import load_templates

    registry = TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])
    path = tmp_path / "t.yaml"
    path.write_text("kind: report\nname: t\nspec:\n  logo: missing.png\n")
    with pytest.raises(TemplateError, match="logo file not found"):
        load_templates([str(path)], registry)
    (tmp_path / "logo.svg").write_text("<svg/>")
    path.write_text("kind: report\nname: t\nspec:\n  logo: logo.svg\n")
    with pytest.raises(TemplateError, match="PNG, JPEG"):
        load_templates([str(path)], registry)
