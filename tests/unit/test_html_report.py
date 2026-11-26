"""The HTML report writer (``--create-html``, v1.5.1, architect plan part C).

Escaping, no external reference, CSP, no JavaScript, determinism, masking
parity with Excel, sections present only when their data is, the logo rules,
atomic write and file mode, structure for assistive technology, and the
10 000-row budget.
"""

import logging
import os
import re
import stat
import struct
import time
import zlib
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml
from openpyxl import load_workbook

from inventag.reporting import html_report
from inventag.reporting.bom_processor import BOMData
from inventag.reporting.converter import BOMConverter
from inventag.reporting.report_template import (
    default_template_text,
    load_report_template as load_template,
)
from inventag.security.secret_values import MASK

SCRIPT = "<script>alert(1)</script>"
BREAKOUT = '"><img src=x onerror=alert(1)>'
JS_URL = "javascript:alert(1)"
SECRET = "S3CR3T-PLANTED-HTML-VALUE"


def _row(n, service="S3", region="us-east-1", account="123456789012", **extra):
    row = {
        "service": service,
        "type": "Bucket",
        "id": f"res-{n:05d}",
        "name": f"name-{n:05d}",
        "arn": f"arn:aws:s3:::res-{n:05d}",
        "region": region,
        "source_account_id": account,
        "tags": {"Owner": "team-a", "CostCenter": f"CC-{n % 7}"},
    }
    row.update(extra)
    return row


def _hostile_rows():
    return [
        _row(
            1,
            name=SCRIPT,
            tags={"Owner": BREAKOUT, "Link": JS_URL, "Note": "a & b <i>x</i>"},
        ),
        _row(2, service="EC2", region="eu-west-1", name=JS_URL),
    ]


def _render(rows=None, **kwargs):
    data = kwargs.pop("data", None) or BOMData(resources=rows or _hostile_rows())
    return html_report.render_html_report(
        data, generated_at="2026-11-12 09:00 UTC", **kwargs
    )


class _Structure(HTMLParser):
    """Tags, attributes, text and nesting of a document."""

    VOID = {"meta", "img", "br", "hr", "link", "input"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.starts = []
        self.stack = []
        self.errors = []
        self.text = []
        self.tables = []  # [has caption, every th has scope]
        self.headings = []

    def handle_starttag(self, tag, attrs):
        self.starts.append((tag, dict(attrs)))
        if tag == "table":
            self.tables.append([False, True])
        if tag == "caption" and self.tables:
            self.tables[-1][0] = True
        if tag == "th" and self.tables and "scope" not in dict(attrs):
            self.tables[-1][1] = False
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")
            return
        self.stack.pop()

    def handle_data(self, data):
        self.text.append(data)


def _parse(document):
    parser = _Structure()
    parser.feed(document)
    parser.close()
    return parser


# ------------------------------------------------------------------ escaping


def test_markup_in_values_is_shown_as_text_only():
    document = _render()
    parsed = _parse(document)
    tags = {tag for tag, _ in parsed.starts}
    assert "script" not in tags
    assert not [a for _, a in parsed.starts if any(k.startswith("on") for k in a)]
    assert [a for t, a in parsed.starts if t == "img"] == []  # no logo given
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in document
    assert "&quot;&gt;&lt;img src=x onerror=alert(1)&gt;" in document
    assert "a &amp; b &lt;i&gt;x&lt;/i&gt;" in document
    visible = "".join(parsed.text)
    assert SCRIPT in visible and BREAKOUT in visible


def test_no_link_with_a_url_scheme_and_no_external_reference():
    document = _render()
    parsed = _parse(document)
    for tag, attrs in parsed.starts:
        for name in ("href", "src", "action", "srcset", "formaction", "poster"):
            value = attrs.get(name)
            if value is None:
                continue
            if name == "href":
                assert re.fullmatch(r"#[A-Za-z][A-Za-z0-9_-]*", value), value
            else:
                assert value.startswith(("data:image/png;", "data:image/jpeg;"))
    attributes = " ".join(str(a) for _, a in parsed.starts)
    assert "http://" not in attributes and "https://" not in attributes
    assert "javascript:" not in attributes
    assert "url(" not in document and "@import" not in document
    forbidden = {"script", "iframe", "object", "embed", "form", "link", "base"}
    assert forbidden.isdisjoint(t for t, _ in parsed.starts)


def test_the_csp_meta_tag_is_the_first_thing_after_the_charset():
    document = _render()
    head = document.split("<head>", 1)[1]
    lines = head.strip().splitlines()
    assert lines[0] == '<meta charset="utf-8">'
    assert lines[1] == (
        '<meta http-equiv="Content-Security-Policy" content="'
        "default-src &#x27;none&#x27;; style-src &#x27;unsafe-inline&#x27;; "
        "img-src data:; base-uri &#x27;none&#x27;; form-action &#x27;none&#x27;"
        '">'
    )
    parsed = _parse(document)
    csp = [a for t, a in parsed.starts if a.get("http-equiv")][0]["content"]
    assert csp == html_report.CSP
    assert csp.startswith(
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    )


@pytest.mark.parametrize(
    "target",
    ["javascript:alert(1)", "https://example.com", "//x", "data:text/html,x", "#a b"],
)
def test_safe_href_rejects_everything_but_a_section_link(target):
    assert html_report.safe_href(target) is None
    assert html_report.safe_href("#summary") == "#summary"


def test_characters_html_cannot_carry_become_the_replacement_character():
    document = _render([_row(1, name="a\x00b\x1bc\x7fd")])
    assert "a�b�c�d" in document
    assert not re.search("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", document)


# --------------------------------------------------------------- determinism


def test_the_same_data_gives_the_same_bytes_in_any_row_order():
    rows = [_row(n, service=s) for n, s in enumerate(["S3", "EC2", "IAM"] * 5)]
    first = _render([dict(r) for r in rows])
    second = _render([dict(r) for r in reversed(rows)])
    assert first == second


# ----------------------------------------------------------- masking parity


def test_masked_values_are_masked_as_in_the_excel_report(tmp_path):
    rows = [
        _row(
            1,
            service="Lambda",
            raw_data={"Environment": {"Variables": {"DB_PASSWORD": SECRET}}},
        )
    ]
    excel = tmp_path / "r.xlsx"
    BOMConverter(enrich_vpc_info=False).generate_excel_bom(
        BOMData(resources=[dict(r) for r in rows]), str(excel)
    )
    cells = [
        str(c)
        for ws in load_workbook(excel).worksheets
        for row in ws.iter_rows(values_only=True)
        for c in row
        if c is not None
    ]
    document = _render([dict(r) for r in rows])
    assert SECRET not in "".join(cells) and SECRET not in document
    masked_in_excel = sum(MASK in c for c in cells)
    assert masked_in_excel >= 1
    assert document.count(MASK) == masked_in_excel


# ------------------------------------------------------------------- sections


def _section_ids(document):
    return re.findall(r'<section id="([a-z-]+)"', document)


def test_an_empty_scope_gives_a_complete_document():
    document = _render(data=BOMData(resources=[]))
    assert _section_ids(document) == ["summary", "resources", "coverage"]
    assert html_report.NO_RESOURCES in document
    assert _parse(document).errors == []


def test_optional_sections_appear_only_with_their_data():
    plain = _render()
    assert _section_ids(plain) == ["summary", "resources", "coverage"]
    finops = {
        "schema_version": 1,
        "summary": [
            {
                "policy": "FIN-001",
                "check": "Stopped instance",
                "fail": 1,
                "not_evaluated": 0,
                "pass": 0,
            }
        ],
        "findings": [
            {
                "policy": "FIN-001",
                "result": "fail",
                "reason": "",
                "account": "123456789012",
                "region": "us-east-1",
                "service": "EC2",
                "resource_type": "Instance",
                "resource": "i-1",
                "name": SCRIPT,
                "message": "stopped",
            }
        ],
    }
    costs = {
        "metric": "UnblendedCost",
        "accounts": [
            {
                "account": "123456789012",
                "period": {"start": "2026-10-01", "end": "2026-11-01"},
                "tables": {
                    "service": {
                        "status": "ok",
                        "currency": "USD",
                        "rows": [{"name": "S3", "amount": "1.00", "unit": "USD"}],
                    }
                },
            }
        ],
    }
    data = BOMData(
        resources=_hostile_rows(),
        compliance_summary={"summary": {"checked": 2, "compliant": 1}},
        generation_metadata={
            "finops_checks": finops,
            "finops_costs": costs,
            "account_summary": [
                {
                    "account_id": "123456789012",
                    "account_name": "a",
                    "resource_count": 2,
                    "error_count": 0,
                    "partial": False,
                }
            ],
            "coverage_summary": {"123456789012": {"ok": 3, "denied": 1}},
            "permissions_denied": [{"action": "s3:ListBuckets", "count": 1}],
        },
    )
    full = _render(data=data)
    assert _section_ids(full) == [
        "summary",
        "resources",
        "compliance",
        "finops",
        "finops-costs",
        "coverage",
    ]
    assert "&lt;script&gt;" in full and SCRIPT not in full
    assert "<caption>Listings by outcome</caption>" in full
    assert "<caption>Permissions denied</caption>" in full


def test_one_closed_details_block_per_service_and_counts_by_region():
    document = _render()
    assert document.count("<details ") == 2
    assert "<details open" not in document
    assert "<caption>Resources by region</caption>" in document
    assert re.search(r"<td>eu-west-1</td><td>1</td>", document)


def test_counts_without_a_tag_policy_give_no_compliance_section():
    # the BOM processor always counts compliance_status ("unknown" without a
    # policy); only a tag policy result has a "summary" mapping
    data = BOMData(
        resources=_hostile_rows(),
        compliance_summary={"total_resources": 2, "unknown_compliance": 2},
    )
    assert "compliance" not in _section_ids(_render(data=data))


def test_run_notes_are_listed():
    document = _render(notes=["Account 1 was not scanned <b>"])
    assert "<li>Account 1 was not scanned &lt;b&gt;</li>" in document


# ----------------------------------------------------------------------- logo


def _png_bytes():
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xff\x00\x00")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", pixels)
        + chunk(b"IEND", b"")
    )


def _word_template(path, title=None, branding=None):
    data = yaml.safe_load(default_template_text("word"))
    if title is not None:
        data["document"]["title"] = title
    data["branding"].update(branding or {})
    path.write_text(yaml.safe_dump(data))


def test_png_and_jpeg_logos_are_embedded(tmp_path):
    png = tmp_path / "logo.png"
    png.write_bytes(_png_bytes())
    jpeg = tmp_path / "logo.jpg"
    jpeg.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
    for path, kind in ((png, "image/png"), (jpeg, "image/jpeg")):
        document = _render(branding={"company_name": "Acme <x>", "logo_file": path})
        img = [a for t, a in _parse(document).starts if t == "img"]
        assert len(img) == 1
        assert img[0]["src"].startswith(f"data:{kind};base64,")
        assert img[0]["alt"] == "Acme <x> logo"


def test_an_svg_logo_is_rejected(tmp_path):
    svg = tmp_path / "logo.png"  # the content decides, not the name
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>')
    with pytest.raises(ValueError, match="not a PNG or JPEG"):
        _render(branding={"logo_file": svg})


@pytest.mark.parametrize(
    "logo,reason",
    [("logo.svg", "must be a .png, .jpg or .jpeg"), ("../logo.png", "must stay in")],
)
def test_a_template_logo_that_is_svg_or_outside_the_folder_is_rejected(
    tmp_path, logo, reason
):
    folder = tmp_path / "t"
    folder.mkdir()
    (folder / "logo.svg").write_text("<svg/>")
    (tmp_path / "logo.png").write_bytes(_png_bytes())
    path = folder / "word.yaml"
    _word_template(path, branding={"logo_path": logo})
    with pytest.raises(Exception, match=reason):
        load_template(str(path), "word")


def test_branding_comes_from_the_word_template_first(tmp_path):
    (tmp_path / "logo.png").write_bytes(_png_bytes())
    word = tmp_path / "word.yaml"
    _word_template(
        word,
        title="Board pack {{ account_count }}",
        branding={"company_name": "Acme", "logo_path": "logo.png"},
    )
    branding = html_report.branding_of(load_template(str(word), "word"), None)
    document = _render(branding=branding)
    assert "<title>Board pack 1</title>" in document
    assert "<h1>Board pack 1</h1>" in document
    assert "<p>Acme</p>" in document
    assert "data:image/png;base64," in document
    assert html_report.branding_of(None, None) == {}


# --------------------------------------------------- file, mode and structure


def test_the_file_is_written_whole_or_not_at_all(tmp_path, monkeypatch):
    target = tmp_path / "r.html"
    target.write_text("old report\n")

    def broken(*args, **kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr(html_report, "render_html_report", broken)
    with pytest.raises(RuntimeError):
        html_report.write_html_report(BOMData(resources=[_row(1)]), target)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["r.html"]
    assert target.read_text() == "old report\n"


def test_a_failed_write_part_way_keeps_the_old_file(tmp_path, monkeypatch):
    target = tmp_path / "r.html"
    target.write_text("old report\n")
    real_open = open

    class _Half:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()
            return False

        def write(self, data):
            self.handle.write(data[:10])
            raise OSError("disk full")

    def half_open(path, mode="r", *args, **kwargs):
        return _Half(real_open(path, mode, *args, **kwargs))

    monkeypatch.setattr("builtins.open", half_open)
    with pytest.raises(OSError):
        html_report.write_html_report(BOMData(resources=[_row(1)]), target)
    monkeypatch.undo()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["r.html"]
    assert target.read_text() == "old report\n"


@pytest.mark.parametrize("mask", [0o022, 0o077, 0o000])
def test_the_file_is_private_to_the_user(tmp_path, mask):
    previous = os.umask(mask)
    try:
        path = html_report.write_html_report(
            BOMData(resources=[_row(1)]), tmp_path / "r.html"
        )
    finally:
        os.umask(previous)
    assert stat.S_IMODE(Path(path).stat().st_mode) == 0o600


def test_semantic_structure_for_assistive_technology():
    document = _render()
    parsed = _parse(document)
    assert parsed.errors == [] and parsed.stack == []
    assert document.startswith('<!DOCTYPE html>\n<html lang="en">')
    assert parsed.tables and all(caption for caption, _ in parsed.tables)
    assert all(scoped for _, scoped in parsed.tables)
    assert parsed.headings[0] == 1 and parsed.headings.count(1) == 1
    assert all(b - a <= 1 for a, b in zip(parsed.headings, parsed.headings[1:]))
    tags = [t for t, _ in parsed.starts]
    for landmark in ("header", "nav", "main", "footer"):
        assert tags.count(landmark) == 1
    assert "@media print" in document
    assert html_report.PRIVACY_NOTE in document


def _luminance(hex_color):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


@pytest.mark.parametrize(
    "fg,bg",
    [
        ("#1a1a1a", "#ffffff"),  # body text
        ("#1f3b5c", "#ffffff"),  # headings
        ("#0b4f8a", "#ffffff"),  # links
        ("#1a1a1a", "#e3e9f0"),  # table headings
        ("#1a1a1a", "#f3f5f8"),  # notes
    ],
)
def test_text_colors_meet_wcag_aa_contrast(fg, bg):
    assert fg in html_report._STYLE and bg in html_report._STYLE
    light, dark = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    assert (light + 0.05) / (dark + 0.05) >= 4.5


def test_rendering_logs_nothing(caplog):
    with caplog.at_level(logging.DEBUG):
        _render()
    assert [r for r in caplog.records if r.name.startswith("inventag")] == []


# ----------------------------------------------------------------- budget


def test_ten_thousand_rows_in_under_two_seconds_and_twenty_megabytes(tmp_path):
    services = ["EC2", "S3", "IAM", "Lambda", "RDS"]
    regions = ["us-east-1", "eu-west-1", "ap-southeast-1"]
    rows = [
        _row(
            n,
            service=services[n % 5],
            region=regions[n % 3],
            raw_data={"Size": n, "State": "available", "Flags": ["a", "b"]},
        )
        for n in range(10_000)
    ]
    started = time.perf_counter()
    path = html_report.write_html_report(BOMData(resources=rows), tmp_path / "big.html")
    elapsed = time.perf_counter() - started
    size = Path(path).stat().st_size
    assert elapsed < 2.0, elapsed
    assert size < 20 * 1024 * 1024, size
    assert (
        Path(path).read_text().count("<tr><td>") == 10_000 + 5 + 3 + 1
    )  # and the total row
