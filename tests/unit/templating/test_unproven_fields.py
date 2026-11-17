"""One test per template field that no earlier test proved (register row T-15).

Each test shows that the code does what the sentence in ``schema.py`` says.
"""

import logging

from docx import Document
from openpyxl import load_workbook

from inventag.cli.main import create_multi_account_config, create_parser
from inventag.core import credential_manager
from inventag.core.cloud_bom_generator import AccountCredentials
from inventag.templating.render_excel import render_excel
from inventag.templating.render_word import render_word
from inventag.templating.runner import apply_config, explicit_dests, load_templates
from inventag.templating.schema import CONFIG_SPEC
from inventag.templating.tag_policy import evaluate

from .conftest import write


def _res(i, service="S3", rtype="Bucket", tags=None, name=None):
    return {
        "service": service,
        "resource_type": rtype,
        "resource_id": f"id-{i}",
        "resource_name": name or f"name-{i}",
        "arn": f"arn:aws:{service.lower()}:::id-{i}",
        "region": "us-east-1",
        "source_account_id": "111111111111",
        "tags": tags or {},
    }


def _report(user_dir, registry, body, name="t"):
    write(
        user_dir / f"{name}.yaml",
        f"format_version: 1\nkind: report\nname: {name}\nspec:\n{body}",
    )
    return registry.resolve(name)


def _policy(user_dir, registry, body, name="p"):
    write(
        user_dir / f"{name}.yaml",
        f"format_version: 1\nkind: tag-policy\nname: {name}\nspec:\n{body}",
    )
    return registry.resolve(name)


# ---------------------------------------------------------------- report


def test_excel_single_sheet_name(tmp_path, registry, user_dir):
    template = _report(
        user_dir,
        registry,
        "  excel:\n    layout: single-sheet\n    single_sheet_name: Everything\n",
    )
    path = render_excel(str(tmp_path / "a.xlsx"), [_res(1), _res(2, "EC2")], template)
    assert "Everything" in load_workbook(path).sheetnames
    assert "S3" not in load_workbook(path).sheetnames


def test_excel_autofilter(tmp_path, registry, user_dir):
    on = _report(user_dir, registry, "  excel:\n    autofilter: true\n", "filter-on")
    off = _report(user_dir, registry, "  excel:\n    autofilter: false\n", "filter-off")
    for template, expected in ((on, True), (off, False)):
        path = render_excel(
            str(tmp_path / f"{template.name}.xlsx"), [_res(1)], template
        )
        sheet = load_workbook(path)["S3"]
        assert bool(sheet.auto_filter.ref) is expected


def test_excel_max_column_width_caps_automatic_widths_only(
    tmp_path, registry, user_dir
):
    template = _report(
        user_dir,
        registry,
        "  columns:\n    - field: resource_name\n    - field: arn\n      width: 90\n"
        "  tag_columns: none\n  excel:\n    max_column_width: 12\n",
    )
    long_name = "n" * 60
    path = render_excel(str(tmp_path / "w.xlsx"), [_res(1, name=long_name)], template)
    sheet = load_workbook(path)["S3"]
    assert sheet.column_dimensions["A"].width == 12  # capped
    assert sheet.column_dimensions["B"].width == 90  # explicit width is not capped


def test_excel_tag_compliance_sheet(tmp_path, registry, user_dir):
    policy = _policy(user_dir, registry, "  required_tags:\n    - key: Owner\n", "pol")
    compliance = evaluate([_res(1)], policy)
    names = {}
    for flag in ("true", "false"):
        template = _report(
            user_dir,
            registry,
            f"  excel:\n    tag_compliance_sheet: {flag}\n",
            f"sheet-{flag}",
        )
        path = render_excel(
            str(tmp_path / f"{flag}.xlsx"), [_res(1)], template, compliance
        )
        names[flag] = load_workbook(path).sheetnames
    assert "Tag Compliance" in names["true"]
    assert "Tag Compliance" not in names["false"]


def test_word_max_noncompliant_rows(tmp_path, registry, user_dir):
    policy = _policy(user_dir, registry, "  required_tags:\n    - key: Owner\n", "pol")
    resources = [_res(i) for i in range(5)]
    compliance = evaluate(resources, policy)
    template = _report(user_dir, registry, "  word:\n    max_noncompliant_rows: 2\n")
    path = render_word(str(tmp_path / "n.docx"), resources, template, compliance)
    doc = Document(path)
    table = next(
        t
        for t in doc.tables
        if t.rows[0].cells[0].text == "Service"
        and t.rows[0].cells[2].text == "Missing tags"
    )
    assert len(table.rows) == 1 + 2
    assert any(
        "Showing 2 of 5 non-compliant resources" in p.text for p in doc.paragraphs
    )


# ------------------------------------------------------------ tag policy


def test_scope_resource_types_and_exclusions(registry, user_dir):
    resources = [
        _res(1, "S3", "Bucket"),
        _res(2, "EC2", "Instance"),
        _res(3, "EC2", "Volume"),
    ]
    only = _policy(
        user_dir,
        registry,
        "  required_tags:\n    - key: Owner\n  scope:\n    resource_types: [instance]\n",
        "only",
    )
    report = evaluate(resources, only)
    assert [f.resource["resource_id"] for f in report.findings] == ["id-2"]
    assert report.out_of_scope == 2
    excluded = _policy(
        user_dir,
        registry,
        "  required_tags:\n    - key: Owner\n  scope:\n    exclude_resource_types: [Volume]\n",
        "excl",
    )
    report = evaluate(resources, excluded)
    assert sorted(f.resource["resource_id"] for f in report.findings) == [
        "id-1",
        "id-2",
    ]
    assert report.out_of_scope == 1


# ---------------------------------------------------------------- config


def _config_args(registry, user_dir, body, argv=()):
    write(
        user_dir / "cfg.yaml",
        f"format_version: 1\nkind: config\nname: cfg\nspec:\n{body}",
    )
    argv = ["--template", "cfg", *argv]
    args = create_parser().parse_args(argv)
    run = load_templates(args.template, registry)
    apply_config(run, args, explicit_dests(create_parser, argv), logging.getLogger("t"))
    return args, run


ACCOUNT = (
    "  accounts:\n"
    "    - account_id: '111111111111'\n"
    "      account_name: Payments\n"
    "      role_arn: arn:aws:iam::111111111111:role/InvenTagReadOnly\n"
    "      external_id: ext-123\n"
    "      services: [S3, SQS]\n"
    "      regions: [eu-west-1]\n"
)


def test_account_entry_reaches_the_scan_config(registry, user_dir):
    args, run = _config_args(registry, user_dir, ACCOUNT)
    try:
        account = create_multi_account_config(args).accounts[0]
    finally:
        run.cleanup()
    assert account.external_id == "ext-123"
    assert account.services == ["S3", "SQS"]
    assert account.account_name == "Payments"
    assert account.regions == ["eu-west-1"]


def test_external_id_is_sent_to_assume_role(monkeypatch):
    calls = []

    class Sts:
        def assume_role(self, **kwargs):
            calls.append(kwargs)
            return {
                "Credentials": {
                    "AccessKeyId": "AKIATESTTESTTESTTEST",
                    "SecretAccessKey": "s" * 40,
                    "SessionToken": "t" * 40,
                }
            }

    class Session:
        def __init__(self, *args, **kwargs):
            pass

        def client(self, name, **kwargs):
            assert name == "sts"
            return Sts()

    monkeypatch.setattr(credential_manager.boto3, "Session", Session)
    manager = credential_manager.CredentialManager.__new__(
        credential_manager.CredentialManager
    )
    manager._create_session_from_credentials(
        AccountCredentials(
            account_id="111111111111",
            role_arn="arn:aws:iam::111111111111:role/InvenTagReadOnly",
            external_id="ext-123",
        )
    )
    assert calls[0]["ExternalId"] == "ext-123"


def test_account_name_is_a_report_field_and_in_run_notes(tmp_path, registry, user_dir):
    """The name is on every resource as ``source_account_name``; a template
    shows it only when a column lists that field."""
    template = _report(
        user_dir,
        registry,
        "  columns:\n    - field: source_account_name\n      header: Who\n",
    )
    resource = _res(1)
    resource["source_account_name"] = "Payments"
    path = render_excel(str(tmp_path / "n.xlsx"), [resource], template)
    assert load_workbook(path)["S3"]["A2"].value == "Payments"
    default = render_excel(
        str(tmp_path / "d.xlsx"), [resource], registry.resolve("standard-bom")
    )
    cells = [c.value for row in load_workbook(default)["S3"].iter_rows() for c in row]
    assert "Payments" not in cells  # not a default column


def test_regions_left_out_means_every_enabled_region(registry, user_dir):
    import moto

    args, run = _config_args(registry, user_dir, "  outputs: [excel]\n")
    assert args.account_regions is None  # the template adds no region list
    from inventag.discovery.regions import discover_regions

    with moto.mock_aws():
        import boto3

        regions, source = discover_regions(boto3.Session(region_name="us-east-1"))
    assert source == "ec2" and len(regions) > 10


def test_schema_defaults_match_the_cli_defaults():
    args = create_parser().parse_args([])
    assert CONFIG_SPEC["account_processing_timeout"].default == 1800
    assert args.account_processing_timeout == 1800
    assert CONFIG_SPEC["max_concurrent_accounts"].default == 4
    assert args.max_concurrent_accounts == 4


def test_account_name_is_in_the_run_notes_of_a_failed_account(registry, tmp_path):
    from .test_template_run_notes import _generate, _generator, _workbook_text

    xlsx, _ = _generate(_generator(registry, tmp_path, failed=True))
    cells = _workbook_text(xlsx)["Summary"]
    assert any("222222222222 (bad):" in c for c in cells), cells
    text = CONFIG_SPEC["accounts"].item.fields["account_name"].description
    assert "Run notes" in text and "source_account_name" in text
