"""Docs claim check for docs/templates/*.md and docs/examples/*.md (v1.2.1).

Claims that the pages state and that no other test proved, run for real.
Rendering tests use the captured sample data (``sample_resources.json``);
the CLI tests run the whole ``inventag`` command under moto.

T1   every YAML template block on the example pages is a valid template
T2   example pages: the ci-pipeline / single-account blocks equal the built-in files
T3   executive-summary: Excel sheets and Word outline; no tag columns
T4   finops-cost-report: Word section order
T5   standard-bom: one tag column per key found on that sheet
T6   standard-bom Word: at most 50 rows per service table, with a note
T7   all three report templates: header colour 1F3A5F, text FFFFFF
T8   tag policies: scope (Alias out of scope), case-insensitive Environment, pattern
T9   resource field table: tags, tags.<Key>, tagged, source_account_name, raw_data
T10  include_all_fields adds columns after the listed ones
T11  word.columns default: first max_columns of columns, no tag columns
T12  logo alt text defaults to "<company_name> logo"
T13  templates init exit codes (1 exists, 2 bad name or extension)
T14  validation message format "<file>:<line>: <field>: <message>"
T15  the job-summary snippet of the CI example runs on a real JSON file
T16  single-account, ci-pipeline: what they write (files, exit code)
T17  config template spec keys map to CLI flags
T18  the docs claim "--template with a tag policy wins" and "flags win"
"""

import glob
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from docx import Document
from openpyxl import load_workbook

from inventag.cli.main import create_parser
from inventag.templating import cli as templates_cli
from inventag.templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry
from inventag.templating.render_excel import render_excel
from inventag.templating.render_word import render_word
from inventag.templating.runner import apply_config, explicit_dests, load_templates
from inventag.templating.tag_policy import evaluate

from tests.integration.templating.test_report_templates import (  # noqa: F401
    aws,
    run_inventag,
    tiny_png,
)

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "unit" / "templating" / "sample_resources.json"
DOCS = ROOT / "docs"


@pytest.fixture(scope="module")
def resources():
    return json.loads(SAMPLE.read_text())["resources"]


@pytest.fixture
def registry():
    return TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])


def headings(doc):
    return [
        (p.style.name, p.text)
        for p in doc.paragraphs
        if p.style.name.startswith(("Heading", "Title"))
    ]


def render(tmp_path, registry, resources, name, policy=None):
    template = registry.resolve(name)
    ref = policy or template.spec.get("tag_policy")
    compliance = evaluate(resources, registry.resolve(ref)) if ref else None
    wb = load_workbook(
        render_excel(str(tmp_path / "r.xlsx"), resources, template, compliance)
    )
    doc = Document(
        render_word(str(tmp_path / "r.docx"), resources, template, compliance)
    )
    return template, wb, doc


def yaml_blocks(page):
    text = (DOCS / page).read_text()
    return re.findall(r'```yaml title="([^"]+)"\n(.*?)```', text, re.S)


# ------------------------------------------------------------------ T1, T2
EXAMPLE_TEMPLATES = [
    ("examples/quick-audit.md", ".inventag/templates/audit.yaml"),
    ("examples/accounts-setup.md", ".inventag/templates/our-org.yaml"),
    ("examples/custom-columns.md", ".inventag/templates/team-sheet.yaml"),
    ("examples/finops-cost-allocation.md", ".inventag/templates/our-cost-tags.yaml"),
    ("examples/security-review.md", ".inventag/templates/data-stores.yaml"),
    ("examples/branded-executive-report.md", ".inventag/templates/board-report.yaml"),
]


@pytest.mark.parametrize("page,title", EXAMPLE_TEMPLATES)
def test_t1_template_blocks_on_example_pages_validate(
    page, title, monkeypatch, tmp_path, capsys
):
    blocks = dict(yaml_blocks(page))
    assert title in blocks
    target = tmp_path / title
    target.parent.mkdir(parents=True)
    target.write_text(blocks[title])
    if "board-report" in title:  # the page puts the logo in brand/
        (target.parent / "brand").mkdir()
        (target.parent / "brand" / "acme-logo.png").write_bytes(tiny_png())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    code = templates_cli.main(["validate", str(target)])
    out = capsys.readouterr()
    assert code == 0, out.err + out.out
    assert "OK" in out.out


def test_t2_ci_pipeline_block_equals_builtin_file():
    block = yaml.safe_load(
        dict(yaml_blocks("examples/tag-policy-in-ci.md"))["ci-pipeline (built-in)"]
    )
    builtin = yaml.safe_load((BUILTIN_DIR / "ci-pipeline.yaml").read_text())
    assert block == builtin


def test_t2_single_account_block_is_the_builtin_with_regions_and_name_changed():
    block = yaml.safe_load(
        dict(yaml_blocks("examples/quick-audit.md"))[".inventag/templates/audit.yaml"]
    )
    builtin = yaml.safe_load((BUILTIN_DIR / "single-account.yaml").read_text())
    assert block["spec"].pop("regions") == ["us-east-1", "eu-west-1"]
    builtin["spec"].pop("regions")
    block.pop("name")
    builtin.pop("name")
    assert block == builtin


def test_t2_org_example_block_is_the_builtin_with_name_and_description_changed():
    block = yaml.safe_load(
        dict(yaml_blocks("examples/accounts-setup.md"))[
            ".inventag/templates/our-org.yaml"
        ]
    )
    builtin = yaml.safe_load((BUILTIN_DIR / "org-multi-account.yaml").read_text())
    for data in (block, builtin):
        data.pop("name")
        data.pop("description")
    builtin["spec"].pop("output_directory")  # the page leaves out the default
    assert block == builtin


# ---------------------------------------------------------------------- T3
def test_t3_executive_summary_excel_and_word(tmp_path, registry, resources):
    _, wb, doc = render(tmp_path, registry, resources, "executive-summary")
    assert wb.sheetnames == ["Summary", "Resources"]
    header = [c.value for c in wb["Resources"][1]]
    assert header == ["Account", "Region", "Service", "Type", "Name", "ID", "ARN"]
    assert wb["Resources"].max_row == 1 + len(resources)  # every resource, one sheet
    names = headings(doc)
    assert names[0] == ("Title", "AWS Inventory Summary")
    assert [h for _, h in names[1:]] == [
        "Summary",
        "Resources by service",
        "About this report",
    ]
    assert len(doc.tables) == 1  # only the service table, no per-resource tables


# ---------------------------------------------------------------------- T4
def test_t4_finops_cost_report_sections_and_tag_columns(tmp_path, registry, resources):
    _, wb, doc = render(tmp_path, registry, resources, "finops-cost-report")
    assert wb.sheetnames[-1] == "Tag Compliance"
    header = [c.value for c in wb["S3"][1]]
    assert header[7:] == [
        "Tag: CostCenter",
        "Tag: Owner",
        "Tag: Project",
        "Tag: Environment",
    ]
    h1 = [h for s, h in headings(doc) if s == "Heading 1"]
    assert h1 == [
        "Summary",
        "Tag compliance",
        "Resources by service",
        "About this report",
    ]


# ---------------------------------------------------------------------- T5
def test_t5_one_tag_column_per_key_found_on_the_sheet(tmp_path, registry, resources):
    _, wb, _ = render(tmp_path, registry, resources, "standard-bom")
    for ws in wb.worksheets[1:]:
        keys = set()
        for r in resources:
            if r["service"] == ws.title:
                keys |= set((r.get("tags") or {}).keys())
        found = {c.value[5:] for c in ws[1] if str(c.value).startswith("Tag: ")}
        assert found == keys, ws.title
    assert wb["Summary"]["A1"].value == "AWS Resource Inventory"


# ---------------------------------------------------------------------- T6
def test_t6_word_service_table_stops_at_50_rows_with_a_note(tmp_path, registry):
    many = [
        {
            "service": "S3",
            "resource_type": "Bucket",
            "resource_id": f"b{i}",
            "resource_name": f"b{i}",
            "region": "us-east-1",
            "source_account_id": "123456789012",
            "tags": {},
        }
        for i in range(60)
    ]
    template = registry.resolve("standard-bom")
    doc = Document(render_word(str(tmp_path / "m.docx"), many, template))
    sizes = sorted(len(t.rows) for t in doc.tables)
    assert sizes[-1] == 51  # header + 50 rows
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "10" in text and "50" in text  # the note says how many were left out


# ---------------------------------------------------------------------- T7
@pytest.mark.parametrize(
    "name", ["standard-bom", "executive-summary", "finops-cost-report"]
)
def test_t7_header_colours_of_all_three_report_templates(registry, name):
    colors = registry.resolve(name).spec["colors"]
    assert colors["header_fill"] == "1F3A5F" and colors["header_text"] == "FFFFFF"


# ---------------------------------------------------------------------- T8
def _res(rtype, tags, service="S3"):
    return {
        "service": service,
        "resource_type": rtype,
        "resource_id": "x",
        "arn": "arn:aws:s3:::x",
        "tags": tags,
        "source_account_id": "123456789012",
    }


FULL = {"CostCenter": "CC-1234", "Owner": "a", "Project": "p", "Environment": "prod"}


def test_t8_alias_is_out_of_scope_and_environment_ignores_case(registry):
    items = [
        _res("Alias", {}, "KMS"),
        _res("Bucket", dict(FULL, Environment="PROD")),
        _res("Bucket", dict(FULL, CostCenter="CC-12345")),
        _res("Bucket", dict(FULL, Environment="production")),
    ]
    report = evaluate(items, registry.resolve("finops-cost-allocation"))
    assert report.out_of_scope == 1
    assert report.compliant == 1
    assert report.non_compliant == 2


def test_t8_security_baseline_values_and_scope(registry):
    ok = dict(Owner="a", Environment="Dev", DataClassification="RESTRICTED")
    bad = dict(ok, DataClassification="secret")
    items = [_res("Alias", {}, "KMS"), _res("Bucket", ok), _res("Bucket", bad)]
    report = evaluate(items, registry.resolve("security-baseline"))
    assert report.out_of_scope == 1
    assert report.compliant == 1


def test_t8_extending_policy_with_pattern_and_scope_services(tmp_path):
    reg = TemplateRegistry(
        [SearchDir("p", tmp_path), SearchDir("builtin", BUILTIN_DIR)]
    )
    for page, title in (
        (
            "examples/finops-cost-allocation.md",
            ".inventag/templates/our-cost-tags.yaml",
        ),
        ("examples/security-review.md", ".inventag/templates/data-stores.yaml"),
    ):
        (tmp_path / Path(title).name).write_text(dict(yaml_blocks(page))[title])
    five = reg.resolve("our-cost-tags")
    keys = {t["key"]: t for t in five.spec["required_tags"]}
    assert keys["CostCenter"]["pattern"] == "[0-9]{5}"
    assert set(keys) == {"CostCenter", "Owner", "Project", "Environment"}
    items = [_res("Bucket", dict(FULL, CostCenter="12345"))]
    assert evaluate(items, five).compliant == 1
    stores = reg.resolve("data-stores")
    items = [_res("Instance", {}, "EC2"), _res("Bucket", {}, "S3")]
    summary = evaluate(items, stores)
    assert summary.out_of_scope == 1 and summary.non_compliant == 1


# ---------------------------------------------------------------------- T9
def test_t9_resource_field_table_values(tmp_path, registry):
    items = [
        {
            "service": "EC2",
            "resource_type": "Volume",
            "resource_id": "vol-1",
            "resource_name": "v",
            "region": "us-east-1",
            "source_account_id": "123456789012",
            "source_account_name": "Prod",
            "tags": {"Owner": "me", "Env": "x"},
            "tagged": True,
            "raw_data": {"VolumeType": "gp3"},
        },
        {
            "service": "EC2",
            "resource_type": "Volume",
            "resource_id": "vol-2",
            "tagged": False,
        },
    ]
    path = tmp_path / "t.yaml"
    path.write_text(
        "kind: report\nname: t\nspec:\n  tag_columns: none\n  columns:\n"
        "    - {field: source_account_name, header: AN}\n"
        "    - {field: tags, header: T}\n"
        "    - {field: tags.Owner, header: O}\n"
        "    - {field: tagged, header: G}\n"
        "    - {field: raw_data.VolumeType, header: V}\n"
    )
    wb = load_workbook(
        render_excel(str(tmp_path / "t.xlsx"), items, registry.resolve(str(path)))
    )
    rows = list(wb["EC2"].iter_rows(min_row=2, values_only=True))
    tagged = [r for r in rows if r[0] == "Prod"][0]
    other = [r for r in rows if r[0] != "Prod"][0]
    assert tagged == ("Prod", "Env=x, Owner=me", "me", "Yes", "gp3")
    assert other[3] == "No"  # not tagged
    assert other[4] in (None, "")  # missing values are left blank


# --------------------------------------------------------------------- T10
def test_t10_include_all_fields_adds_columns_after_the_listed_ones(
    tmp_path, registry, resources
):
    path = tmp_path / "all.yaml"
    path.write_text(
        "kind: report\nname: all\nextends: standard-bom\nspec:\n"
        "  excel: {include_all_fields: true}\n"
    )
    wb = load_workbook(
        render_excel(str(tmp_path / "a.xlsx"), resources, registry.resolve(str(path)))
    )
    header = [c.value for c in wb["EC2"][1]]
    assert header[:7] == ["Account", "Region", "Service", "Type", "Name", "ID", "ARN"]
    plain = load_workbook(
        render_excel(
            str(tmp_path / "b.xlsx"), resources, registry.resolve("standard-bom")
        )
    )
    assert len(header) > len([c.value for c in plain["EC2"][1]])


# --------------------------------------------------------------------- T11
def test_t11_word_columns_default_is_first_max_columns_without_tags(
    tmp_path, registry, resources
):
    path = tmp_path / "w.yaml"
    path.write_text(
        "kind: report\nname: w\nspec:\n  tag_columns: all\n"
        "  columns:\n"
        "    - {field: service}\n    - {field: resource_type}\n    - {field: region}\n"
        "  word: {max_columns: 2, sections: [service-tables]}\n"
    )
    doc = Document(
        render_word(str(tmp_path / "w.docx"), resources, registry.resolve(str(path)))
    )
    widths = {len(t.columns) for t in doc.tables}
    assert widths == {2}
    first = [c.text for c in doc.tables[0].rows[0].cells]
    assert first == ["Service", "Resource type"]


# --------------------------------------------------------------------- T12
def test_t12_logo_alt_text_defaults_to_company_name_logo(tmp_path, registry, resources):
    (tmp_path / "logo.png").write_bytes(tiny_png())
    path = tmp_path / "b.yaml"
    path.write_text(
        "kind: report\nname: b\nextends: executive-summary\nspec:\n"
        "  company_name: Acme Ltd\n  logo: logo.png\n"
    )
    doc = Document(
        render_word(str(tmp_path / "b.docx"), resources, registry.resolve(str(path)))
    )
    assert 'descr="Acme Ltd logo"' in doc.element.body.xml


# --------------------------------------------------------------------- T13
def run_templates(args, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    code = templates_cli.main(args)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_t13_init_exit_codes_and_messages(monkeypatch, tmp_path, capsys):
    args = [
        "init",
        "standard-bom",
        "--output",
        ".inventag/templates/acme-bom.yaml",
        "--extend",
    ]
    code, out, _ = run_templates(args, monkeypatch, tmp_path, capsys)
    assert code == 0
    assert out.splitlines() == [
        "Created .inventag/templates/acme-bom.yaml (kind: report, name: acme-bom).",
        "Next: edit it, then run 'inventag templates validate "
        ".inventag/templates/acme-bom.yaml'.",
    ]
    assert run_templates(args, monkeypatch, tmp_path, capsys)[0] == 1  # exists
    assert run_templates(args + ["--force"], monkeypatch, tmp_path, capsys)[0] == 0
    bad_ext = ["init", "standard-bom", "-o", "x.txt"]
    assert run_templates(bad_ext, monkeypatch, tmp_path, capsys)[0] == 2
    bad_name = ["init", "standard-bom", "-o", "n.yaml", "--name", "Bad_Name"]
    assert run_templates(bad_name, monkeypatch, tmp_path, capsys)[0] == 2


def test_t13_without_extend_the_copy_keeps_comments(monkeypatch, tmp_path, capsys):
    run_templates(
        ["init", "standard-bom", "-o", "c.yaml"], monkeypatch, tmp_path, capsys
    )
    text = (tmp_path / "c.yaml").read_text()
    assert "#" in text and "extends" not in text


def test_t13_name_option_and_extended_file_content(monkeypatch, tmp_path, capsys):
    code, _, _ = run_templates(
        ["init", "standard-bom", "-o", "f.yaml", "--extend", "--name", "other"],
        monkeypatch,
        tmp_path,
        capsys,
    )
    assert code == 0
    data = yaml.safe_load((tmp_path / "f.yaml").read_text())
    assert data["name"] == "other" and data["extends"] == "standard-bom"
    assert data["spec"] == {} and data["description"] == "Adapted from standard-bom"


# --------------------------------------------------------------------- T14
def test_t14_validation_message_format_and_list_all(monkeypatch, tmp_path, capsys):
    (tmp_path / "bad.yaml").write_text(
        "kind: report\nname: bad\nspec:\n  title: x\n  colors:\n    header_fill: blue\n"
    )
    code, out, err = run_templates(
        ["validate", "bad.yaml"], monkeypatch, tmp_path, capsys
    )
    assert code == 1
    text = out + err
    assert re.search(
        r"bad\.yaml:6: spec\.colors\.header_fill: must be a six-digit hex colour "
        r"such as 1F3A5F \(got 'blue'\)",
        text,
    )


def test_t14_unknown_template_message_lists_search_folders(monkeypatch, tmp_path):
    from inventag.templating.errors import TemplateError

    reg = TemplateRegistry(
        [SearchDir("project", tmp_path), SearchDir("builtin", BUILTIN_DIR)]
    )
    with pytest.raises(TemplateError) as info:
        load_templates(["acme-bomm"], reg)
    message = str(info.value)
    assert "no template named 'acme-bomm'" in message
    assert "Run 'inventag templates list' to see what is available" in message
    assert "searched:" in message


# --------------------------------------------------------------------- T15
JOB_SUMMARY = re.search(
    r'```bash title="Workflow step"\npython3 -c "\n(.*?)" >> "\$GITHUB_STEP_SUMMARY"',
    (DOCS / "examples" / "tag-policy-in-ci.md").read_text(),
    re.S,
).group(1)


@pytest.mark.usefixtures("aws")
def test_t15_ci_job_summary_snippet_runs_on_real_output(monkeypatch, tmp_path):
    code = run_inventag(monkeypatch, tmp_path, "--template", "ci-pipeline")
    assert code == 3  # the page: exit code 3 on violations
    files = sorted(p.name for p in (tmp_path / "bom_output").iterdir())
    assert [f.split(".")[-1] for f in files if not f.startswith("state")] == [
        "xlsx",
        "json",
    ] or (
        sorted(f.split(".")[-1] for f in files if not f.startswith("state"))
        == ["json", "xlsx"]
    )
    assert "state" in files  # the page's file listing shows the state folder
    script = JOB_SUMMARY.replace('\\"', '"').replace("\\$", "$")
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert re.fullmatch(r"\d+ non-compliant resources", lines[0])
    assert all(re.match(r"- \S+ \S+ missing: ", line) for line in lines[1:])


# --------------------------------------------------------------------- T16
@pytest.mark.usefixtures("aws")
def test_t16_single_account_writes_excel_and_word_only(monkeypatch, tmp_path):
    code = run_inventag(monkeypatch, tmp_path, "--template", "single-account")
    assert code == 0
    out = tmp_path / "bom_output"
    assert glob.glob(str(out / "multi_account_bom_*.xlsx"))
    assert glob.glob(str(out / "multi_account_bom_*.docx"))
    assert not glob.glob(str(out / "tag_compliance_*.json"))  # no tag policy


@pytest.mark.usefixtures("aws")
def test_t16_report_template_alone_adds_no_tag_policy_files(monkeypatch, tmp_path):
    code = run_inventag(
        monkeypatch,
        tmp_path,
        "--template",
        "executive-summary",
        "--create-word",
        "--account-regions",
        "us-east-1",
    )
    assert code == 0
    assert not glob.glob(str(tmp_path / "bom_output" / "tag_compliance_*.json"))
    assert glob.glob(str(tmp_path / "bom_output" / "*.docx"))


# --------------------------------------------------------------------- T17
def test_t17_config_spec_keys_set_the_flags_the_reference_names(registry, tmp_path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        "kind: config\nname: cfg\nspec:\n"
        "  regions: [us-east-1, eu-west-1]\n  services: [S3]\n"
        "  outputs: [excel, word]\n  output_directory: out\n"
        "  max_concurrent_accounts: 7\n  account_processing_timeout: 900\n"
        "  parallel_processing: false\n"
    )
    argv = ["--template", str(path)]
    args = create_parser().parse_args(argv)
    run = load_templates(args.template, registry)
    apply_config(run, args, explicit_dests(create_parser, argv), logging.getLogger("t"))
    assert args.account_regions == "us-east-1,eu-west-1"
    assert args.account_services == "S3"
    assert args.create_excel and args.create_word
    assert args.output_directory == "out"
    assert args.max_concurrent_accounts == 7
    assert args.account_processing_timeout == 900
    assert args.disable_parallel_processing is True


def test_t17_defaults_when_the_config_leaves_keys_out(registry, tmp_path):
    path = tmp_path / "cfg.yaml"
    path.write_text("kind: config\nname: cfg\nspec: {}\n")
    run = load_templates([str(path)], registry)
    spec = run.config.spec
    assert spec["outputs"] == ["excel"]
    assert spec["output_directory"] == "bom_output"
    assert spec["report_template"] == "standard-bom"
    assert spec["fail_on_tag_violations"] is False
    assert spec["max_concurrent_accounts"] == 4
    assert spec["account_processing_timeout"] == 1800
    assert spec["parallel_processing"] is True


# --------------------------------------------------------------------- T18
def test_t18_FALSE_claim_typed_flag_replaces_config_outputs(registry, tmp_path):
    """docs/templates/index.md says outputs [excel] plus --create-word gives both
    files. FALSE: a typed --create-excel or --create-word makes InvenTag ignore
    the config's ``outputs`` completely, so only the typed formats are written."""
    path = tmp_path / "cfg.yaml"
    path.write_text("kind: config\nname: cfg\nspec:\n  outputs: [excel]\n")
    argv = ["--template", str(path), "--create-word"]
    args = create_parser().parse_args(argv)
    run = load_templates(args.template, registry)
    apply_config(run, args, explicit_dests(create_parser, argv), logging.getLogger("t"))
    assert args.create_word and not args.create_excel


def test_t18_command_line_policy_replaces_the_one_named_by_the_report(registry):
    run = load_templates(["finops-cost-report", "security-baseline"], registry)
    assert run.policy.name == "security-baseline"
    run = load_templates(["finops-cost-report"], registry)
    assert run.policy.name == "finops-cost-allocation"
    run = load_templates(["finops-cost-allocation"], registry)
    assert run.report.name == "standard-bom"  # without a report template


def test_t18_fail_on_tag_violations_default_and_two_of_a_kind(registry):
    from inventag.templating.errors import TemplateError

    with pytest.raises(TemplateError):
        load_templates(["standard-bom", "executive-summary"], registry)


# --------------------------------------------------------------------- T19
def test_t19_layout_flags_error_example_is_what_the_cli_prints(
    monkeypatch, tmp_path, capsys
):
    """The two hand-written error lines in layout-flags.md are real output."""
    import importlib

    cli_main = importlib.import_module("inventag.cli.main")
    (tmp_path / "my_word_template.yaml").write_text(
        'template_version: "2.0"\nformat_type: word\ncolour: red\nsections:\n'
        "  - id: a\n    content_type: title\n"
        "  - id: b\n    content_type: resources\n    columns:\n"
        "      - field: name\n      - field: id\n      - field: owner_name\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "inventag",
            "--validate-templates",
            "--word-template",
            "my_word_template.yaml",
        ],
    )
    with pytest.raises(SystemExit) as stop:
        cli_main.main()
    assert stop.value.code == 1
    shown = (DOCS / "templates" / "layout-flags.md").read_text()
    for line in capsys.readouterr().err.strip().splitlines():
        assert line in shown


# --------------------------------------------------------------------- T20
def _s3_upload_run(aws_fixture, monkeypatch, tmp_path, *extra):
    import boto3

    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="reports-out")
    code = run_inventag(
        monkeypatch,
        tmp_path,
        "--template",
        "ci-pipeline",
        "--account-regions",
        "us-east-1",
        "--s3-bucket",
        "reports-out",
        "--s3-key-prefix",
        "bom-reports/",
        "--audit-output",
        "audit.json",
        *extra,
    )
    keys = [
        o["Key"]
        for o in boto3.client("s3", region_name="us-east-1").list_objects_v2(
            Bucket="reports-out"
        )["Contents"]
    ]
    return code, keys


def test_t20_s3_upload_key_layout_json_uploaded_and_audit_shows_a_write(
    aws, monkeypatch, tmp_path
):
    """scheduled-s3-upload.md: key layout, the compliance JSON goes too, AES256 by
    default. FALSE: 'blocked_calls is 0: the run only made read calls' - the audit
    lists PutObject (an allowed write) when an upload ran."""
    import boto3

    code, keys = _s3_upload_run(aws, monkeypatch, tmp_path)
    assert code == 3  # ci-pipeline: the sample estate breaks the policy
    assert len(keys) == 2
    for key in keys:
        assert re.fullmatch(r"bom-reports/\d{8}_\d{6}/[^/]+", key), key
    assert any(k.endswith(".xlsx") for k in keys)
    assert any(
        "tag_compliance_" in k and k.endswith(".json") for k in keys
    )  # the JSON is uploaded too
    head = boto3.client("s3", region_name="us-east-1").head_object(
        Bucket="reports-out", Key=keys[0]
    )
    assert head["ServerSideEncryption"] == "AES256"
    audit = json.loads((tmp_path / "audit.json").read_text())
    assert audit["blocked_calls"] == 0
    assert any(
        o["operation"] == "PutObject" and o["allowed"] for o in audit["operations"]
    )
    assert (tmp_path / "bom_output").exists()


def test_t20_kms_without_a_key_id_is_sent_as_aws_kms(aws, monkeypatch, tmp_path):
    """The request InvenTag sends: aws:kms and no key id. What S3 then does (use
    aws/s3) is AWS behaviour and is not proven here."""
    import boto3

    code, keys = _s3_upload_run(
        aws, monkeypatch, tmp_path, "--s3-encryption", "aws:kms"
    )
    assert code == 3 and keys
    head = boto3.client("s3", region_name="us-east-1").head_object(
        Bucket="reports-out", Key=keys[0]
    )
    assert head["ServerSideEncryption"] == "aws:kms"


# --------------------------------------------------------------------- T21
def test_t21_zero_in_scope_resources_print_100_percent(registry):
    """No page says what happens with zero in-scope resources: the summary line
    reads '0 of 0 resources compliant (100.0%)' and the JSON has 100.0."""
    policy = registry.resolve("finops-cost-allocation")
    only_alias = [
        {"service": "KMS", "resource_type": "Alias", "resource_id": "a", "tags": {}}
    ]
    for resources in ([], only_alias):
        result = evaluate(resources, policy)
        assert result.checked == 0
        assert result.percent_compliant == 100.0
        assert result.compliant == 0 and result.non_compliant == 0


# --------------------------------------------------------------------- T22
def test_t22_header_fill_contrast_claim_of_the_branded_example():
    """branded-executive-report.md: '4B2E83 has 10.4:1 contrast with white'."""

    def lum(hex_colour):
        channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [
            c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            for c in channels
        ]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    ratio = (lum("FFFFFF") + 0.05) / (lum("4B2E83") + 0.05)
    assert round(ratio, 1) == 10.4


# --------------------------------------------------------------------- T23
def test_t23_untitled_adapt_example_validates_and_renders_as_described(
    tmp_path, registry, resources
):
    """adapt-a-template.md step 2: single sheet, green header, three tag columns."""
    text = (DOCS / "templates" / "adapt-a-template.md").read_text()
    block = re.search(
        r"```yaml\nformat_version: 1\nkind: report\nname: acme-bom\n(.*?)```",
        text,
        re.S,
    )
    body = "format_version: 1\nkind: report\nname: acme-bom\n" + block.group(1)
    folder = tmp_path / "tpl"
    folder.mkdir()
    (folder / "acme-bom.yaml").write_text(body)
    reg = TemplateRegistry(
        [SearchDir("project", folder), SearchDir("builtin", BUILTIN_DIR)]
    )
    template = reg.resolve("acme-bom")
    wb = load_workbook(
        render_excel(str(tmp_path / "r.xlsx"), resources, template, None)
    )
    assert wb.sheetnames == ["Summary", "Resources"]
    header = [c.value for c in wb["Resources"][1]]
    assert header[-3:] == ["Tag: Owner", "Tag: CostCenter", "Tag: Environment"]
    assert wb["Resources"]["A1"].fill.start_color.rgb.endswith("0B5D1E")


# --------------------------------------------------------------------- T24
def test_t24_cron_example_command_line_is_accepted_by_the_parser():
    text = (DOCS / "examples" / "scheduled-s3-upload.md").read_text()
    line = re.search(
        r"^17 2 \* \* 1-5\s+cd \S+ && \S+ inventag_cli\.py (.*?) >>", text, re.M
    )
    import shlex

    create_parser().parse_args(shlex.split(line.group(1)))
    assert (ROOT / "inventag_cli.py").exists()


# --------------------------------------------------------------------- T25
@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "GIF", "BMP"])
def test_t25_word_logo_formats_named_on_the_pages_are_embedded(
    tmp_path, registry, resources, fmt
):
    from PIL import Image

    name = "logo." + {"JPEG": "jpg"}.get(fmt, fmt.lower())
    Image.new("RGB", (20, 20), "purple").save(tmp_path / name, fmt)
    (tmp_path / "t.yaml").write_text(f"kind: report\nname: t\nspec:\n  logo: {name}\n")
    reg = TemplateRegistry([SearchDir("p", tmp_path), SearchDir("b", BUILTIN_DIR)])
    template = reg.resolve("t")
    path = render_word(str(tmp_path / "r.docx"), resources, template, None)
    assert len(Document(path).inline_shapes) == 1


# ------------------------------------------------- claims3: rows of the sheet
def _sheet_names(path):
    return load_workbook(path, read_only=True).sheetnames


def test_t26_services_in_a_config_template_leave_one_sheet_a49(
    aws, monkeypatch, tmp_path
):
    """reference.md spec.services (register A-49): a config template with
    ``services: [S3]`` over an estate with S3, SQS and DynamoDB gives the
    Summary sheet and one S3 sheet, and no other service sheet. The page says
    the filter is applied in one discovery path only, so other services can
    still appear."""
    import boto3

    boto3.client("sqs", region_name="us-east-1").create_queue(QueueName="q-1")
    boto3.client("dynamodb", region_name="us-east-1").create_table(
        TableName="t-1",
        KeySchema=[{"AttributeName": "k", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "k", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    def run(sub, *argv):
        out = tmp_path / sub
        out.mkdir()
        code = run_inventag(monkeypatch, out, *argv)
        assert code == 0
        return _sheet_names(glob.glob(str(out / "bom_output" / "*.xlsx"))[0])

    cfg = tmp_path / "only-s3.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "format_version": 1,
                "kind": "config",
                "name": "only-s3",
                "spec": {
                    "regions": ["us-east-1"],
                    "services": ["S3"],
                    "outputs": ["excel"],
                },
            }
        )
    )
    unfiltered = run("all", "--create-excel", "--account-regions", "us-east-1")
    assert {"S3", "SQS", "DYNAMODB"} <= set(unfiltered)  # the estate has all three
    filtered = run("filtered", "--template", str(cfg))
    assert filtered == ["Summary", "S3"]


def test_t27_source_and_detail_level_values_of_the_three_kinds_of_row(monkeypatch):
    """reference.md: a service-API row is service-api/full, a tagging-only
    resource is tagging-api/identity, a billing-only service is billing/identity."""
    import boto3
    from moto import mock_aws

    from inventag.discovery.comprehensive_discovery import (
        ComprehensiveAWSDiscovery,
    )
    from inventag.discovery.inventory import AWSResourceInventory

    for key in ("AWS_PROFILE", "AWS_ENDPOINT_URL", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")
    vault = "arn:aws:backup:us-east-1:123456789012:backup-vault:v1"

    def tagging_only(self):
        return {
            "us-east-1": [{"ResourceARN": vault, "Tags": [{"Key": "k", "Value": "v"}]}]
        }

    def billed(self):
        self.billing_services.add("lightsail")

    monkeypatch.setattr(
        ComprehensiveAWSDiscovery, "_prefetch_tagging_resources", tagging_only
    )
    monkeypatch.setattr(ComprehensiveAWSDiscovery, "_discover_billing_services", billed)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="bucket-one")
        rows = AWSResourceInventory(
            regions=["us-east-1"], enable_billing_validation=True
        ).discover_resources()
    kinds = {
        r["service"]: (r["source"], r["detail_level"])
        for r in rows
        if r["service"] in {"S3", "BACKUP", "LIGHTSAIL"}
    }
    assert kinds == {
        "S3": ("service-api", "full"),
        "BACKUP": ("tagging-api", "identity"),
        "LIGHTSAIL": ("billing", "identity"),
    }


def _layout_excel():
    return {
        "template_version": "2.0",
        "format_type": "excel",
        "sections": [
            {
                "id": "all",
                "content_type": "resources",
                "group_by_service": False,
                "sheet_name": "All",
                "columns": [{"field": "id", "heading": "ID"}],
            }
        ],
    }


@pytest.mark.parametrize(
    "flag,fmt", [("--excel-template", "excel"), ("--word-template", "word")]
)
def test_t28_layout_file_with_the_old_keys_is_refused(
    aws, monkeypatch, tmp_path, capsys, flag, fmt
):
    """layout-flags.md: a layout file with templates, document_templates or
    default_template is refused with 'unknown key'."""
    layout = dict(
        _layout_excel(),
        format_type=fmt,
        templates={},
        document_templates={},
        default_template="x",
    )
    if fmt == "word":
        layout["sections"] = [{"id": "s", "content_type": "resources"}]
    lay = tmp_path / "layout.json"
    lay.write_text(json.dumps(layout))
    code = run_inventag(
        monkeypatch,
        tmp_path,
        flag,
        str(lay),
        *(["--create-word"] if fmt == "word" else []),
        "--account-regions",
        "us-east-1",
    )
    assert code == 1
    err = capsys.readouterr().err
    for key in ("templates", "document_templates", "default_template"):
        assert f"{key}: unknown key" in err


def test_t30_old_keys_in_a_bom_config_file_have_no_effect(aws, monkeypatch, tmp_path):
    """layout-flags.md: the keys of older configuration examples (here the shipped
    config/defaults/complete_configuration_example.yaml, used with --bom-config)
    change no report: same sheets, same Word paragraphs, exit 0."""
    example = yaml.safe_load(
        (
            ROOT / "config" / "defaults" / "complete_configuration_example.yaml"
        ).read_text()
    )
    old_keys = ("templates", "document_templates", "default_template")
    assert "document_templates" in example and "default_template" in example
    with_keys = dict(example, templates={"x": "y"})
    without = {k: v for k, v in example.items() if k not in old_keys}
    results = []
    for sub, data in (("with", with_keys), ("without", without)):
        out = tmp_path / sub
        out.mkdir()
        cfg = out / "bom.yaml"
        cfg.write_text(yaml.safe_dump(data))
        code = run_inventag(
            monkeypatch,
            out,
            "--bom-config",
            str(cfg),
            "--create-excel",
            "--create-word",
            "--account-regions",
            "us-east-1",
        )
        assert code == 0
        xlsx = glob.glob(str(out / "bom_output" / "*.xlsx")) or glob.glob(
            str(out / "output" / "*.xlsx")
        )
        docx = glob.glob(str(out / "bom_output" / "*.docx")) or glob.glob(
            str(out / "output" / "*.docx")
        )
        assert xlsx and docx
        results.append((_sheet_names(xlsx[0]), len(Document(docx[0]).paragraphs)))
    assert results[0] == results[1]


def test_t29_reports_stay_on_disk_after_a_failed_upload(aws, monkeypatch, tmp_path):
    """scheduled-s3-upload.md: a missing bucket stops the upload with exit 1;
    the report files are already written."""
    code = run_inventag(
        monkeypatch,
        tmp_path,
        "--create-excel",
        "--account-regions",
        "us-east-1",
        "--s3-bucket",
        "no-such-bucket",
    )
    assert code == 1
    assert glob.glob(str(tmp_path / "bom_output" / "*.xlsx"))
