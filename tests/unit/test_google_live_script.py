"""scripts/google_live_test.py: the read-back checks, tested against a fake Google.

The fake stores what google_output writes and answers the read calls the script
makes, so a passing run proves the comparisons accept a correct copy and the
tampered copies below prove they notice each kind of difference.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest
from docx import Document

from inventag.reporting import google_output as go

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "google_live_test.py"
spec = importlib.util.spec_from_file_location("google_live_test", SCRIPT)
glt = importlib.util.module_from_spec(spec)
sys.modules["google_live_test"] = glt
spec.loader.exec_module(glt)


# ------------------------------------------------------------------ fake Google
class Req:
    def __init__(self, fn):
        self.fn = fn

    def execute(self, *args, **kwargs):
        return self.fn()


def col_number(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def parse_range(rng):
    """ "'Title'!A1:J5" -> (title, (r0, c0, r1, c1) or None)."""
    match = re.match(r"^'((?:[^']|'')*)'(?:!([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?)?$", rng)
    title = match.group(1).replace("''", "'")
    if not match.group(2):
        return title, None
    c0, r0 = col_number(match.group(2)), int(match.group(3)) - 1
    c1 = col_number(match.group(4)) if match.group(4) else c0
    r1 = int(match.group(5)) - 1 if match.group(5) else r0
    return title, (r0, c0, r1, c1)


class FakeSheets:
    def __init__(self):
        self.sheets = []  # {"title", "index", "id", "grid", "cells", "format"}

    def spreadsheets(self):
        return self

    def values(self):
        return FakeValues(self)

    def create(self, body):
        def run():
            self.sheets = []
            for i, s in enumerate(body["sheets"]):
                grid = dict(s["properties"]["gridProperties"])
                self.sheets.append(
                    {
                        "title": s["properties"]["title"],
                        "index": i,
                        "id": i,
                        "grid": grid,
                        "cells": {},
                        "format": None,
                    }
                )
            return {
                "spreadsheetId": "SID",
                "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/SID/edit",
                "sheets": [
                    {"properties": {"title": s["title"], "sheetId": s["id"]}}
                    for s in self.sheets
                ],
            }

        return Req(run)

    def batchUpdate(self, spreadsheetId, body):
        def run():
            for request in body["requests"]:
                if "repeatCell" in request:
                    rc = request["repeatCell"]
                    sheet = self.sheets[rc["range"]["sheetId"]]
                    sheet["format"] = rc["cell"]["userEnteredFormat"]
            return {}

        return Req(run)

    def get(self, spreadsheetId, fields=None, ranges=None, includeGridData=False):
        def run():
            if not includeGridData:
                return {
                    "sheets": [
                        {
                            "properties": {
                                "sheetId": s["id"],
                                "title": s["title"],
                                "index": s["index"],
                                "gridProperties": s["grid"],
                            }
                        }
                        for s in self.sheets
                    ]
                }
            out = []
            for rng in ranges:
                title, box = parse_range(rng)
                sheet = next(s for s in self.sheets if s["title"] == title)
                r, c = box[0], box[1]
                value = sheet["cells"].get((r, c))
                cell = {}
                if isinstance(value, str) and value != "":
                    cell["userEnteredValue"] = {"stringValue": value}
                elif isinstance(value, (int, float)):
                    cell["userEnteredValue"] = {"numberValue": value}
                if r == 0 and sheet["format"]:
                    cell["userEnteredFormat"] = sheet["format"]
                out.append({"rowData": [{"values": [cell]}]})
            return {"sheets": [{"properties": {}, "data": out}]}

        return Req(run)


class FakeValues:
    def __init__(self, owner):
        self.owner = owner

    def update(self, spreadsheetId, range, valueInputOption, body):
        def run():
            assert valueInputOption == "RAW"
            title, box = parse_range(range)
            sheet = next(s for s in self.owner.sheets if s["title"] == title)
            r0, c0 = box[0], box[1]
            for dr, row in enumerate(body["values"]):
                for dc, value in enumerate(row):
                    sheet["cells"][(r0 + dr, c0 + dc)] = value
            return {}

        return Req(run)

    def get(self, spreadsheetId, valueRenderOption, **kwargs):
        def run():
            title, box = parse_range(kwargs["range"])
            sheet = next(s for s in self.owner.sheets if s["title"] == title)
            cells = sheet["cells"]
            if box is None:
                box = (
                    0,
                    0,
                    max([r for r, _ in cells] + [0]),
                    max([c for _, c in cells] + [0]),
                )
            rows = []
            for r in range(box[0], box[2] + 1):
                row = [cells.get((r, c), "") for c in range(box[1], box[3] + 1)]
                while row and row[-1] == "":
                    row.pop()
                rows.append(row)
            while rows and not rows[-1]:
                rows.pop()
            return {"values": rows} if rows else {}

        return Req(run)


class FakeDrive:
    def __init__(self, mime, permissions=None):
        self.mime = mime
        self.name = "T"
        self.mime_by_id = {}
        self.permissions_list = permissions or [
            {
                "id": "1",
                "type": "user",
                "role": "owner",
                "emailAddress": "me@example.com",
            }
        ]
        self.trashed = []
        self.parents = []

    def files(self):
        return self

    def permissions(self):
        return self

    def about(self):
        return self

    def get(self, **kwargs):
        if "fileId" in kwargs:
            fid = kwargs["fileId"]
            return Req(
                lambda: {
                    "id": fid,
                    "name": self.name,
                    "mimeType": self.mime_by_id.get(fid, self.mime),
                    "parents": self.parents or ["root"],
                    "webViewLink": f"https://docs.google.com/x/d/{fid}/edit",
                }
            )
        return Req(lambda: {"user": {"emailAddress": "me@example.com"}})

    def list(self, fileId, fields, supportsAllDrives):
        return Req(lambda: {"permissions": self.permissions_list})

    def update(self, **kwargs):
        def run():
            if kwargs.get("body", {}).get("trashed"):
                self.trashed.append(kwargs["fileId"])
            return {}

        return Req(run)

    def create(self, **kwargs):
        return Req(lambda: {})


class FakeDocs:
    def __init__(self):
        self.view = {"body": {"content": []}}

    def documents(self):
        return self

    def get(self, documentId):
        return Req(lambda: self.view)

    def create(self, body):
        return Req(lambda: {"documentId": "DID"})

    def batchUpdate(self, documentId, body):
        return Req(lambda: {})


def services(mime=glt.SHEET_MIME):
    return {"sheets": FakeSheets(), "docs": FakeDocs(), "drive": FakeDrive(mime)}


def doc_json(blocks):
    """A Docs API document as Google would return it for these blocks."""

    def paragraph(text, style="NORMAL_TEXT"):
        return {
            "paragraph": {
                "elements": [{"textRun": {"content": text + "\n"}}],
                "paragraphStyle": {"namedStyleType": style},
            }
        }

    content = [{"sectionBreak": {}}]
    for block in blocks:
        if block["type"] == "paragraph":
            for line in block["text"].split("\n"):  # Docs: one paragraph per line
                content.append(paragraph(line, block.get("style") or "NORMAL_TEXT"))
        else:
            content.append(
                {
                    "table": {
                        "tableRows": [
                            {
                                "tableCells": [
                                    {
                                        "content": [
                                            paragraph(t)["paragraph"] and paragraph(t)
                                        ]
                                    }
                                    for t in row
                                ]
                            }
                            for row in block["rows"]
                        ]
                    }
                }
            )
    content.append(paragraph(""))
    return {"body": {"content": content}}


def created_spreadsheet(workbook, options=None):
    s = services()
    go.create_spreadsheet(s, workbook, options or go.GoogleOptions(sheets=True))
    return s, go.workbook_to_sheets(workbook)


def failed(report):
    return [c.name for c in report.checks if not c.ok]


# ---------------------------------------------------------------------- sheets
def test_correct_copy_of_the_probe_workbook_passes_every_check():
    wb = glt.probe_workbook()
    s, expected = created_spreadsheet(wb)
    report = glt.Report()
    glt.verify_spreadsheet(report, "probe", s, "SID", expected, glt.PROBE_STRINGS)
    assert failed(report) == [], [c for c in report.checks if not c.ok]
    names = " ".join(c.name for c in report.checks)
    assert "empty sheet stays empty" in names
    assert "is text" in names  # the formula probe
    assert report.passed


def test_probe_workbook_contains_the_awkward_values():
    wb = glt.probe_workbook()
    values = {c.value for ws in wb.worksheets for row in ws.iter_rows() for c in row}
    for probe in (glt.PROBE_FORMULA, glt.PROBE_CJK, glt.PROBE_PLUS):
        assert probe in values or any(probe == str(v) for v in values)
    assert 30000 < len(glt.PROBE_LONG) < 32767
    assert wb["Empty"].max_row == 1 and wb["Empty"]["A1"].value is None
    assert wb.sheetnames[-1] == glt.PROBE_QUOTE_TITLE


def test_a_changed_cell_is_reported():
    s, expected = created_spreadsheet(glt.probe_workbook())
    s["sheets"].sheets[0]["cells"][(1, 0)] = "tampered"
    report = glt.Report()
    glt.verify_spreadsheet(report, "t", s, "SID", expected)
    assert "every cell value matches" in failed(report)
    assert "A2" in next(
        c.detail for c in report.checks if c.name == "every cell value matches"
    )


def test_a_formula_that_came_back_is_reported():
    s, expected = created_spreadsheet(glt.probe_workbook())
    sheet = s["sheets"].sheets[0]
    original = s["sheets"].get

    def get(spreadsheetId, fields=None, ranges=None, includeGridData=False):
        req = original(spreadsheetId, fields, ranges, includeGridData)
        if not includeGridData:
            return req
        data = req.execute()
        for grid in data["sheets"][0]["data"]:
            value = grid["rowData"][0]["values"][0].get("userEnteredValue", {})
            if value.get("stringValue", "").startswith("="):
                grid["rowData"][0]["values"][0]["userEnteredValue"] = {
                    "formulaValue": value["stringValue"]
                }
        return Req(lambda: data)

    s["sheets"].get = get
    report = glt.Report()
    glt.verify_spreadsheet(report, "t", s, "SID", expected, [glt.PROBE_FORMULA])
    assert any("is text" in n for n in failed(report))
    assert sheet  # fake has the sheet


def test_sheet_order_row_counts_and_header_format_are_checked():
    s, expected = created_spreadsheet(glt.probe_workbook())
    fake = s["sheets"]
    fake.sheets[0]["index"], fake.sheets[1]["index"] = 1, 0
    report = glt.Report()
    glt.verify_spreadsheet(report, "t", s, "SID", expected)
    assert "sheet titles and order match" in failed(report)

    s, expected = created_spreadsheet(glt.probe_workbook())
    s["sheets"].sheets[0]["grid"]["rowCount"] += 1
    report = glt.Report()
    glt.verify_spreadsheet(report, "t", s, "SID", expected)
    assert "rows and columns per sheet match" in failed(report)

    s, expected = created_spreadsheet(glt.probe_workbook())
    s["sheets"].sheets[0]["format"] = None
    report = glt.Report()
    glt.verify_spreadsheet(report, "t", s, "SID", expected)
    assert "header bold and coloured, rows frozen" in failed(report)


def test_empty_sheet_with_data_is_reported():
    s, expected = created_spreadsheet(glt.probe_workbook())
    empty = next(x for x in s["sheets"].sheets if x["title"] == "Empty")
    empty["cells"][(0, 0)] = "oops"
    report = glt.Report()
    glt.verify_spreadsheet(report, "t", s, "SID", expected)
    assert "empty sheet stays empty" in failed(report)


def test_optional_probes_are_skipped_when_the_workbook_lacks_them():
    s, expected = created_spreadsheet(glt.probe_workbook())
    report = glt.Report()
    glt.verify_spreadsheet(
        report, "t", s, "SID", expected, probes=[], optional_probes=["not in there"]
    )
    assert report.passed
    glt.verify_spreadsheet(report, "t", s, "SID", expected, probes=["not in there"])
    assert not report.passed


def test_compare_rows_pads_trailing_empty_cells_and_compares_numbers():
    assert glt.compare_rows([["a", "", None], [1, 2.5]], [["a"], [1, 2.5]]) == []
    assert glt.compare_rows([["a"]], [["a", "extra"]]) == [("B1", "", "extra")]
    assert glt.compare_rows([["123"]], [[123]]) != []  # text turned into a number
    assert glt.compare_rows([[1]], [["1"]]) != []


def test_a1_names():
    assert [glt.a1(0, 0), glt.a1(0, 25), glt.a1(0, 26), glt.a1(9, 701)] == [
        "A1",
        "Z1",
        "AA1",
        "ZZ10",
    ]


# ------------------------------------------------------------------------ docs
def sample_document():
    doc = Document()
    doc.add_heading("Report", level=0)
    doc.add_heading("Compute", level=1)
    doc.add_paragraph("First line\nSecond line")
    table = doc.add_table(rows=3, cols=2)
    for r in range(3):
        for c in range(2):
            table.cell(r, c).text = f"r{r}c{c} 平台"
    doc.add_heading("End", level=2)
    return doc


def test_doc_that_matches_passes_and_changes_are_reported():
    blocks = go.docx_to_blocks(sample_document())
    s = services(glt.DOC_MIME)
    s["docs"].view = doc_json(blocks)
    report = glt.Report()
    glt.verify_document(report, "d", s, "DID", blocks)
    assert failed(report) == []

    wrong = [dict(b) for b in blocks]
    next(b for b in wrong if b.get("style") == "HEADING_1")["text"] = "Other"
    s["docs"].view = doc_json(wrong)
    report = glt.Report()
    glt.verify_document(report, "d", s, "DID", blocks)
    assert "headings match the local outline" in failed(report)

    wrong = [dict(b) for b in blocks]
    table = next(b for b in wrong if b["type"] == "table")
    table["rows"] = [list(r) for r in table["rows"]]
    table["rows"][2][1] = "changed"
    s["docs"].view = doc_json(wrong)
    report = glt.Report()
    glt.verify_document(report, "d", s, "DID", blocks)
    assert "every table cell matches" in failed(report)
    assert "r3c2" in next(
        c.detail for c in report.checks if c.name == "every table cell matches"
    )

    s["docs"].view = doc_json([b for b in blocks if b["type"] != "table"])
    report = glt.Report()
    glt.verify_document(report, "d", s, "DID", blocks)
    assert "table count matches" in failed(report)


def test_parse_document_ignores_empty_paragraphs():
    view = doc_json([{"type": "paragraph", "text": "Hi", "style": None}])
    paragraphs, tables = glt.parse_document(view)
    assert paragraphs == [("NORMAL_TEXT", "Hi")] and tables == []


# ----------------------------------------------------------------------- drive
def test_private_file_checks():
    s = services()
    report = glt.Report()
    glt.verify_private(report, "f", s, "FID")
    assert report.passed

    s["drive"].permissions_list.append({"id": "2", "type": "anyone", "role": "reader"})
    report = glt.Report()
    glt.verify_private(report, "f", s, "FID")
    assert not report.passed

    s["drive"].permissions_list = [
        {"id": "1", "type": "user", "role": "owner", "emailAddress": "me@example.com"},
        {
            "id": "2",
            "type": "user",
            "role": "reader",
            "emailAddress": "You@Example.com",
        },
    ]
    report = glt.Report()
    glt.verify_private(report, "f", s, "FID", ["you@example.com"])
    assert report.passed
    report = glt.Report()
    glt.verify_private(report, "f", s, "FID")  # nobody was meant to have access
    assert not report.passed


def test_file_checks_url_and_type_and_title():
    s = services()
    report = glt.Report()
    url = "https://docs.google.com/spreadsheets/d/FID123/edit"
    glt.verify_file(report, "f", s, "FID123", url, "sheet", title="T")
    assert report.passed
    report = glt.Report()
    glt.verify_file(report, "f", s, "OTHER", url, "sheet", title="T")
    assert not report.passed
    report = glt.Report()
    glt.verify_file(report, "f", s, "FID123", url, "doc")  # wrong kind of URL and type
    assert len(failed(report)) == 2
    assert glt.file_id_from_url(url, "spreadsheets") == "FID123"
    assert glt.file_id_from_url(url, "document") is None


def test_trash_and_account_email():
    s = services()
    assert glt.account_email(s["drive"]) == "me@example.com"
    assert glt.trash(s["drive"], "FID") is None
    assert s["drive"].trashed == ["FID"]


# ---------------------------------------------------------------------- errors
class Boom(Exception):
    def __init__(self, status, reason):
        super().__init__(f"<HttpError {status} {reason}>")
        self.status_code, self.reason = status, reason


def test_error_text_has_status_and_reason_and_never_a_token():
    text = glt.describe_error(
        Boom(401, "Invalid Credentials ya29.a0AfH6SMBsecretsecret Bearer abc.def")
    )
    assert text.startswith("HTTP 401:")
    assert "ya29" not in text and "abc.def" not in text
    api = glt.describe_error(
        Boom(
            403,
            "Google Sheets API has not been used in project 1 (sheets.googleapis.com) accessNotConfigured",
        )
    )
    assert 'Enable "Google Sheets API"' in api
    quota = glt.describe_error(Boom(403, "requires a quota project, which is not set"))
    assert "set-quota-project" in quota
    assert glt.describe_error(ValueError("plain")).startswith("ValueError: plain")


# ------------------------------------------------------------- proxy and large
def test_proxy_counts_calls_and_injects_429_that_google_output_retries(monkeypatch):
    class Http429(Exception):
        status_code = 429

    monkeypatch.setattr(glt, "_http_error", lambda status, message: Http429(message))
    monkeypatch.setattr(go, "_sleep", lambda seconds: None)
    monkeypatch.setattr(go, "ROWS_PER_REQUEST", 7)
    monkeypatch.setattr(glt, "LARGE_ROWS", 40)
    monkeypatch.setattr(glt, "LARGE_COLS", 4)
    monkeypatch.setattr(glt, "LARGE_TEXT", 5)
    stats = glt.Stats(inject_429=2)
    fake = {
        "sheets": FakeSheets(),
        "docs": FakeDocs(),
        "drive": FakeDrive(glt.SHEET_MIME),
    }
    proxied = glt.counting_services(fake, stats)
    wb = glt.large_workbook()
    expected = go.workbook_to_sheets(wb)
    chunks = len(list(go._chunk_rows(expected[0]["rows"])))
    go.create_spreadsheet(proxied, wb, go.GoogleOptions(sheets=True))
    assert stats.injected == 2
    assert stats.values_update_calls == chunks + 2
    assert stats.by_method["sheets.spreadsheets.create"] == 1
    assert stats.calls >= chunks + 2 + 2

    report = glt.Report()
    glt.verify_large_sheet(report, proxied, "SID", stats, chunks)
    assert failed(report) == [], [c for c in report.checks if not c.ok]
    # the same checks fail when a row is wrong
    fake["sheets"].sheets[0]["cells"][(20, 1)] = "bad"
    report = glt.Report()
    glt.verify_large_sheet(report, proxied, "SID", stats, chunks)
    assert not report.passed


# -------------------------------------------------------------------- command
def test_help_works_without_the_google_packages_and_names_the_prerequisites():
    code = (
        "import sys, runpy; sys.modules['google']=None; sys.modules['googleapiclient']=None; "
        f"sys.argv=['x','--help']; runpy.run_path({str(SCRIPT)!r}, run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert 'pip install "inventag-aws[google]"' in out
    for api in ("Google Sheets API", "Google Docs API", "Google Drive API"):
        assert api in out
    assert "gcloud auth application-default login" in out
    assert "--scopes=https://www.googleapis.com/auth/drive.file" in out
    assert "set-quota-project" in out and "NOT VERIFIED" in out


def test_preflight_names_what_is_missing(tmp_path, monkeypatch):
    args = glt.build_parser().parse_args(
        ["--google-credentials", str(tmp_path / "no.json")]
    )
    real_import = glt.importlib.import_module

    def fake_import(name, *a, **k):
        if name.startswith("google") or name == "httplib2":
            raise ImportError(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr(glt.importlib, "import_module", fake_import)
    problems = glt.preflight(args)
    assert any("file not found" in p for p in problems)
    assert any('pip install "inventag-aws[google]"' in p for p in problems)
    both = glt.build_parser().parse_args(
        [
            "--google-credentials",
            __file__,
            "--google-oauth-client",
            __file__,
            "--share-with",
            "bad",
        ]
    )
    problems = glt.preflight(both)
    assert any("not both" in p for p in problems)
    assert any("not an email" in p for p in problems)


def test_main_exits_2_without_starting_when_prerequisites_fail(monkeypatch, capsys):
    monkeypatch.setattr(glt, "preflight", lambda args: ["something is missing"])
    assert glt.main([]) == 2
    err = capsys.readouterr().err
    assert "something is missing" in err and "--help" in err


def test_report_exit_logic_and_table():
    report = glt.Report()
    assert not report.passed  # nothing ran is not a pass
    report.add("g", "ok check", True)
    assert report.passed
    report.add("g", "bad check", False, "why")
    assert not report.passed
    text = report.render()
    assert "PASS  g: ok check" in text and "FAIL  g: bad check  why" in text
    assert "1 passed, 1 failed" in text


def test_credential_flags_are_passed_through_as_paths_only():
    args = glt.build_parser().parse_args(["--google-credentials", "key.json"])
    assert glt.credential_argv(args) == ["--google-credentials", "key.json"]
    args = glt.build_parser().parse_args(["--google-oauth-client", "c.json"])
    assert glt.credential_argv(args) == ["--google-oauth-client", "c.json"]
    assert glt.credential_argv(glt.build_parser().parse_args([])) == []
    source = SCRIPT.read_text()
    # the script never opens a credential file itself
    assert "open(args.google" not in source and "read_text(args.google" not in source


# ------------------------------------------------ whole script path, fake Google
def test_cli_run_and_read_back_end_to_end_with_a_fake_google(tmp_path, monkeypatch):
    """Real CLI (moto estate), real google_output writes, fake Google behind them."""
    import boto3
    import moto
    from docx import Document as OpenDocx

    from inventag.security import redaction

    fake = services()
    created = {}

    class CapturingDocs(FakeDocs):
        def create(self, body):
            created["title"] = body["title"]
            return super().create(body)

    fake["docs"] = CapturingDocs()
    monkeypatch.setattr(go, "load_credentials", lambda options: object())
    monkeypatch.setattr(go, "build_services", lambda credentials: fake)
    monkeypatch.setattr(go, "_sleep", lambda seconds: None)

    helpers = glt.load_estate_helpers()
    helpers.fake_aws_environment()
    run = None
    try:
        with moto.mock_aws():
            helpers.drop_guard()
            session = boto3.Session()
            helpers.seed_account(session)
            glt.seed_probe_resources(session)
            work = tmp_path / "work"
            work.mkdir()
            title = "InvenTag live test (default layout)"
            run = glt.run_inventag(
                "default layout",
                [
                    "--account-regions",
                    "us-east-1",
                    "--create-excel",
                    "--create-word",
                    "--create-google-sheets",
                    "--create-google-docs",
                    "--google-title",
                    title,
                ],
                work,
                helpers,
            )
    finally:
        import logging

        redaction.uninstall_log_record_redaction()
        for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
            logging.getLogger(name).handlers.clear()
            logging.getLogger(name).propagate = True
    assert run.exit_code == 0, run.console[-800:]
    assert run.sheet_url == "https://docs.google.com/spreadsheets/d/SID/edit"
    assert run.doc_url == "https://docs.google.com/document/d/DID/edit"

    # Google's view of the document is what a correct copy would look like.
    blocks = go.docx_to_blocks(OpenDocx(str(run.file(".docx"))))
    fake["docs"].view = doc_json(blocks)
    fake["drive"].name = title
    fake["drive"].mime_by_id = {"DID": glt.DOC_MIME}
    report = glt.Report()
    args = glt.build_parser().parse_args([])
    ids = []
    glt.verify_cli_run(report, run, fake, args, ids, title)
    assert ids == ["SID", "DID"]
    bad = [(c.group, c.name, c.detail) for c in report.checks if not c.ok]
    assert bad == []
    names = {c.name for c in report.checks}
    assert any("probe" in n and "is text" in n for n in names)
    assert "every table cell matches" in names
