"""``--create-html`` through the CLI (v1.5.1): opt-in and additive.

Without the flag the run asks for the formats v1.5.0 asked for. With it: one
``.html`` file for each report scope, next to the other reports with the same
name stem, no extra AWS call, the file uploaded with the others, and the
template and template-flag rules.
"""

import re
from pathlib import Path

import boto3
import botocore.client
import pytest

from inventag.cli.main import create_parser
from inventag.core import cloud_bom_generator as cbg
from tests.regression import v143_equality
from tests.unit.finops.conftest import _run_main, run_scans
from tests.unit.test_cli_exit_codes_and_flags import aws, run_cli  # noqa: F401

pytestmark = pytest.mark.e2e


class _Formats(Exception):
    pass


# argument set -> the formats v1.5.0 asked the generator for
V150_FORMATS = [
    ([], ["excel"]),
    (["--create-excel"], ["excel"]),
    (["--create-word"], ["word"]),
    (["--create-word", "--create-excel"], ["word", "excel"]),
    (["--create-excel", "--create-word"], ["word", "excel"]),
    (["--per-account-reports"], ["excel"]),
    (["--create-word", "--per-account-reports"], ["word"]),
]


def _formats_asked(tmp_path, monkeypatch, extra):
    seen = {}

    def record(self, output_formats=None, **kwargs):
        seen["formats"] = list(output_formats)
        raise _Formats()

    monkeypatch.setattr(cbg.CloudBOMGenerator, "generate_comprehensive_bom", record)
    from moto import mock_aws

    with mock_aws():
        try:
            _run_main(tmp_path / "out", tmp_path / "audit.json", extra, False, {})
        except _Formats:
            pass
    return seen.get("formats")


@pytest.mark.parametrize("extra,expected", V150_FORMATS)
def test_formats_without_the_flag_are_those_of_v150(
    tmp_path, monkeypatch, extra, expected
):
    assert _formats_asked(tmp_path, monkeypatch, extra) == expected


@pytest.mark.parametrize("extra,expected", V150_FORMATS)
def test_the_flag_adds_html_last_and_alone_writes_html_only(
    tmp_path, monkeypatch, extra, expected
):
    found = _formats_asked(tmp_path, monkeypatch, [*extra, "--create-html"])
    explicit = {"--create-word", "--create-excel"} & set(extra)
    assert found == (expected if explicit else []) + ["html"]


def test_the_flag_is_off_by_default_and_in_the_output_group():
    parser = create_parser()
    assert parser.parse_args([]).create_html is False
    group = next(g for g in parser._action_groups if g.title == "Output Format Options")
    assert "--create-html" in [
        s for a in group._group_actions for s in a.option_strings
    ]
    assert "inventag --create-excel --create-html" in parser.epilog


# ---------------------------------------------------------- moto runs


@pytest.fixture(scope="module")
def html_runs(tmp_path_factory):
    """One estate: Excel alone, Excel and HTML, HTML alone, per account."""
    return run_scans(
        tmp_path_factory.mktemp("html"),
        ["--create-excel"],
        ["--create-excel", "--create-html"],
        ["--create-html"],
        ["--create-html", "--per-account-reports"],
        ["--create-html", "--template", "standard-bom"],
        [
            "--create-html",
            "--finops-checks",
            "--enable-network-analysis",
            "--enable-security-analysis",
        ],
        ["--create-html", "--template", "finops-cost-allocation"],
    )


def _names(scan):
    return sorted(
        re.sub(r"\d{8}_\d{6}", "STAMP", p.name)
        for p in scan.out.iterdir()
        if p.is_file()
    )


def test_html_is_written_next_to_excel_with_the_same_stem(html_runs):
    excel_only, both = html_runs[0], html_runs[1]
    assert excel_only.code == both.code == 0
    assert _names(excel_only) == ["multi_account_bom_STAMP.xlsx"]
    assert _names(both) == [
        "multi_account_bom_STAMP.html",
        "multi_account_bom_STAMP.xlsx",
    ]
    stems = {p.stem for p in both.out.iterdir() if p.is_file()}
    assert len(stems) == 1


def test_the_excel_report_is_the_same_with_and_without_html(html_runs):
    excel_only, both = html_runs[0], html_runs[1]
    assert v143_equality._workbook(excel_only.workbook()) == v143_equality._workbook(
        both.workbook()
    )


def test_html_adds_no_aws_call(html_runs):
    excel_only, both, html_only = html_runs[0], html_runs[1], html_runs[2]
    assert both.audit["operations"] == excel_only.audit["operations"]
    assert html_only.audit["operations"] == excel_only.audit["operations"]


def test_html_alone_writes_only_html_and_lists_every_row(html_runs):
    scan = html_runs[2]
    assert scan.code == 0
    assert _names(scan) == ["multi_account_bom_STAMP.html"]
    document = next(scan.out.glob("*.html")).read_text()
    for row in scan.rows:
        if row.get("id"):
            assert str(row["id"]) in document
    assert "<script" not in document.lower()


def test_one_html_file_per_account_with_per_account_reports(html_runs):
    scan = html_runs[3]
    accounts = {str(r.get("source_account_id")) for r in scan.rows}
    assert scan.code == 0
    assert _names(scan) == sorted(f"{a}_bom_STAMP.html" for a in accounts)


def test_with_a_template_the_html_has_the_default_layout_and_one_warning(html_runs):
    scan = html_runs[4]
    assert scan.code == 0
    names = _names(scan)
    # a report template with --create-html alone: HTML only
    assert names == ["multi_account_bom_STAMP.html"]
    warnings = [line for line in scan.text.splitlines() if "--create-html:" in line]
    assert len(warnings) == 1 and "WARNING" in warnings[0]
    assert "default layout" in warnings[0]
    document = next(scan.out.glob("*.html")).read_text()
    assert '<section id="resources"' in document


def test_the_console_names_no_resource_value_in_the_new_lines(html_runs):
    excel_only, both = html_runs[0], html_runs[1]

    def lines(scan):
        return [
            re.sub(r"/run\d+/", "/runN/", line)
            for line in v143_equality._console(scan.text)
        ]

    before = set(lines(excel_only))
    added = [line for line in lines(both) if line not in before]
    assert added == []


# ---------------------------------------------------------- flag rules


def test_excel_template_with_html_only_stops_with_exit_2(tmp_path, capsys):
    template = tmp_path / "excel.yaml"
    template.write_text("x: 1\n")
    code = run_cli("--create-html", "--excel-template", str(template))
    err = capsys.readouterr().err
    assert code == 2
    assert "--excel-template: this flag needs --create-excel" in err
    assert "With only --create-html" in err


# ---------------------------------------------------------- S3 upload

RUN = [
    "--account-regions",
    "us-east-1",
    "--account-services",
    "s3",
    "--no-billing-validation",
]


def test_the_html_file_is_uploaded_as_html_and_other_reports_unchanged(
    aws, monkeypatch, tmp_path  # noqa: F811
):
    sent = {}
    real = botocore.client.BaseClient._make_api_call

    def make_api_call(self, operation_name, api_params):
        if operation_name == "PutObject":
            sent[Path(api_params["Key"]).suffix] = sorted(
                k for k in api_params if k != "Body"
            )
        return real(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", make_api_call)
    code = run_cli(*RUN, "--create-excel", "--create-html", "--s3-bucket", "a-bucket")
    assert code == 0
    s3 = boto3.client("s3", region_name="us-east-1")
    keys = sorted(
        item["Key"] for item in s3.list_objects_v2(Bucket="a-bucket")["Contents"]
    )
    assert [Path(k).suffix for k in keys] == [".html", ".xlsx"]
    # the Excel upload sends the same parameters as in v1.5.0
    assert sent[".xlsx"] == ["Bucket", "Key", "ServerSideEncryption"]
    assert sent[".html"] == ["Bucket", "ContentType", "Key", "ServerSideEncryption"]
    head = {Path(k).suffix: s3.head_object(Bucket="a-bucket", Key=k) for k in keys}
    assert head[".html"]["ContentType"] == "text/html; charset=utf-8"
    assert head[".xlsx"]["ContentType"] == "binary/octet-stream"


def _html_table(document, caption):
    table = document.split(f"<caption>{caption}</caption>", 1)[1].split("</table>")[0]
    headings = re.findall(r'<th scope="col">(.*?)</th>', table)
    return headings, re.findall(r"<tr><td>", table)


def test_each_service_table_has_the_columns_and_rows_of_its_excel_sheet(html_runs):
    from html import escape

    both = html_runs[1]
    document = next(both.out.glob("*.html")).read_text()
    services = [s for s in both.sheet_names() if s != "Summary"]
    assert services
    for service in services:
        sheet = both.sheet(service)
        headings, rows = _html_table(document, f"{escape(service)} resources")
        assert headings == [escape(str(h)) for h in sheet[0]], service
        assert len(rows) == len(sheet) - 1, service


def test_optional_sections_follow_their_flags(html_runs):
    plain, full = html_runs[2], html_runs[5]
    sections = re.compile(r'<section id="([a-z-]+)"')
    assert sections.findall(next(plain.out.glob("*.html")).read_text()) == [
        "summary",
        "resources",
        "coverage",
    ]
    assert full.code == 0
    assert sections.findall(next(full.out.glob("*.html")).read_text()) == [
        "summary",
        "resources",
        "network",
        "security",
        "finops",
        "coverage",
    ]


def test_no_html_file_when_there_are_no_resources(aws, capsys):  # noqa: F811
    code = run_cli(
        "--account-regions",
        "us-east-1",
        "--account-services",
        "lambda",
        "--no-billing-validation",
        "--create-html",
    )
    assert code == 0
    assert list(Path("bom_output").glob("*.html")) == []
    captured = capsys.readouterr()
    assert "No report file was written" in captured.out + captured.err


def test_a_tag_policy_template_gives_the_tag_compliance_section(html_runs):
    scan = html_runs[6]
    assert scan.code == 0
    document = next(scan.out.glob("*.html")).read_text()
    assert '<section id="compliance"' in document
    headings, rows = _html_table(document, "Tag compliance summary")
    assert headings == ["Item", "Value"] and rows
    assert "<td>checked</td>" in document
