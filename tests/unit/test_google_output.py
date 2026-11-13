"""Google Sheets and Docs output, with the Google client mocked (no network)."""

import sys

import pytest
from docx import Document
from openpyxl import load_workbook

from inventag.reporting import google_output as go
from inventag.reporting.converter import BOMConverter
from inventag.security.redaction import redact

from tests.unit.test_cli_security import aws, run_cli  # noqa: F401 (fixtures)


class FakeApi:
    """Records every Google API call: api.a().b(x=1).execute() logs ('a.b', {x: 1})."""

    def __init__(self, log, responses, path=()):
        self._log, self._responses, self._path = log, responses, path

    def __getattr__(self, name):
        if name == "execute":
            return self._execute
        return FakeApi(self._log, self._responses, self._path + (name,))

    def __call__(self, **kwargs):
        self._last = kwargs
        self._log.append((".".join(self._path), kwargs))
        return self

    def _execute(self):
        key = ".".join(self._path)
        response = self._responses.get(key, {})
        kwargs = self._log[-1][1] if self._log else {}
        return response(kwargs) if callable(response) else response


def fake_services(log):
    def sheets_create(kwargs):
        titles = [s["properties"]["title"] for s in kwargs["body"]["sheets"]]
        return {
            "spreadsheetId": "SID",
            "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/SID/edit",
            "sheets": [
                {"properties": {"title": t, "sheetId": i}} for i, t in enumerate(titles)
            ],
        }

    sheets_responses = {"spreadsheets.create": sheets_create}
    docs_responses = {"documents.create": {"documentId": "DID"}}
    drive_responses = {"files.get": {"parents": ["root-folder"]}}
    return {
        "sheets": FakeApi(log, sheets_responses),
        "docs": FakeApi(log, docs_responses),
        "drive": FakeApi(log, drive_responses),
    }


RESOURCES = [
    {
        "service": "EC2",
        "type": "Instance",
        "id": "i-1",
        "name": "web",
        "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1",
        "region": "us-east-1",
        "source_account_id": "123456789012",
        "tags": {"Owner": '=HYPERLINK("http://evil.example","x")'},
    },
    {
        "service": "S3",
        "type": "Bucket",
        "id": "b1",
        "name": "b1",
        "arn": "arn:aws:s3:::b1",
        "region": "us-east-1",
        "source_account_id": "123456789012",
        "tags": {},
    },
]


def converter():
    c = BOMConverter(enrich_vpc_info=False)
    return c


def test_missing_libraries_give_an_install_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "google", None)
    monkeypatch.setitem(sys.modules, "googleapiclient", None)
    with pytest.raises(go.GoogleDependencyError) as error:
        go.load_credentials(go.GoogleOptions(sheets=True))
    assert 'pip install "inventag-aws[google]"' in str(error.value)


def test_cli_without_the_extra_exits_2_with_the_hint(
    aws, monkeypatch, capsys
):  # noqa: F811
    monkeypatch.setitem(sys.modules, "google", None)
    monkeypatch.setitem(sys.modules, "googleapiclient", None)
    code = run_cli("--account-regions", "us-east-1", "--create-google-sheets")
    assert code == 2
    assert "inventag-aws[google]" in capsys.readouterr().err


def test_option_problems_are_found_without_a_network_call(tmp_path):
    problems = go.validate_options(
        go.GoogleOptions(
            credentials_file=str(tmp_path / "missing.json"),
            share_with=["not-an-email"],
            sheets=True,
        )
    )
    assert any("file not found" in p for p in problems)
    assert any("not an email" in p for p in problems)
    both = go.validate_options(
        go.GoogleOptions(
            credentials_file=__file__, oauth_client_file=__file__, sheets=True
        )
    )
    assert any("not both" in p for p in both)


def test_spreadsheet_has_the_excel_sheets_in_the_same_order(tmp_path):
    c = converter()
    c.generate_excel_bom(RESOURCES, str(tmp_path / "r.xlsx"))
    excel_names = load_workbook(tmp_path / "r.xlsx").sheetnames
    excel_rows = [
        [list(r) for r in ws.iter_rows(values_only=True)]
        for ws in load_workbook(tmp_path / "r.xlsx").worksheets
    ]

    log = []
    urls = go.publish(
        converter(),
        RESOURCES,
        go.GoogleOptions(sheets=True, title="Test"),
        services=fake_services(log),
    )
    assert urls == {
        "spreadsheet_url": "https://docs.google.com/spreadsheets/d/SID/edit"
    }
    create = next(kw for name, kw in log if name == "spreadsheets.create")
    titles = [s["properties"]["title"] for s in create["body"]["sheets"]]
    assert titles == excel_names
    assert titles[0] == "Summary"
    assert create["body"]["properties"]["title"] == "Test"

    # Same cell values as the Excel report, sent as RAW text (never formulas).
    updates = [kw for name, kw in log if name == "spreadsheets.values.update"]
    assert updates and all(u["valueInputOption"] == "RAW" for u in updates)
    sent = {u["range"].split("!")[0].strip("'"): u["body"]["values"] for u in updates}
    for name, rows in zip(excel_names, excel_rows):
        want = [["" if v is None else v for v in row] for row in rows]
        assert sent[name] == want
    ec2 = sent["EC2"]
    assert any("HYPERLINK" in str(v) for row in ec2 for v in row)

    # Header row is bold, and the columns are sized.
    batch = next(kw for name, kw in log if name == "spreadsheets.batchUpdate")
    kinds = {next(iter(r)) for r in batch["body"]["requests"]}
    assert {"repeatCell", "autoResizeDimensions"} <= kinds


def test_files_are_private_by_default(tmp_path):
    log = []
    go.publish(
        converter(),
        RESOURCES,
        go.GoogleOptions(sheets=True, docs=True),
        services=fake_services(log),
    )
    names = [name for name, _ in log]
    assert not any(n.startswith("permissions") for n in names)
    assert not any(n == "files.update" for n in names)


def test_share_with_folder_and_public_link_only_when_asked():
    log = []
    options = go.GoogleOptions(
        sheets=True,
        docs=True,
        folder_id="FOLDER",
        share_with=["a@example.com", "b@example.com"],
        share_role="writer",
    )
    go.publish(converter(), RESOURCES, options, services=fake_services(log))
    perms = [kw for name, kw in log if name == "permissions.create"]
    # Two people, for each of the two files; nobody else.
    assert len(perms) == 4
    assert {p["body"]["emailAddress"] for p in perms} == {
        "a@example.com",
        "b@example.com",
    }
    assert all(
        p["body"]["role"] == "writer" and p["body"]["type"] == "user" for p in perms
    )
    moves = [kw for name, kw in log if name == "files.update"]
    assert len(moves) == 2
    assert all(
        m["addParents"] == "FOLDER" and m["removeParents"] == "root-folder"
        for m in moves
    )

    log.clear()
    go.publish(
        converter(),
        RESOURCES,
        go.GoogleOptions(sheets=True, share_anyone=True),
        services=fake_services(log),
    )
    perms = [kw for name, kw in log if name == "permissions.create"]
    assert [p["body"] for p in perms] == [{"type": "anyone", "role": "reader"}]


def test_scopes_use_full_drive_only_with_a_folder():
    assert go.SCOPE_DRIVE_FILE in go.GoogleOptions().scopes()
    assert go.SCOPE_DRIVE not in go.GoogleOptions().scopes()
    assert go.SCOPE_DRIVE in go.GoogleOptions(folder_id="x").scopes()


def test_service_account_without_sharing_is_warned_about(caplog):
    log = []
    with caplog.at_level("WARNING"):
        go.publish(
            converter(),
            RESOURCES,
            go.GoogleOptions(sheets=True, credentials_file="key.json"),
            services=fake_services(log),
        )
    assert "service account's own Google Drive" in caplog.text


def test_document_has_title_sections_and_tables():
    log = []
    urls = go.publish(
        converter(),
        RESOURCES,
        go.GoogleOptions(docs=True, title="Doc"),
        services=fake_services(log),
    )
    assert urls == {"document_url": "https://docs.google.com/document/d/DID/edit"}
    assert next(kw for n, kw in log if n == "documents.create")["body"] == {
        "title": "Doc"
    }
    requests = [
        r
        for name, kw in log
        if name == "documents.batchUpdate"
        for r in kw["body"]["requests"]
    ]
    kinds = [next(iter(r)) for r in requests]
    assert "insertTable" in kinds and "updateParagraphStyle" in kinds
    styles = {
        r["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"]
        for r in requests
        if "updateParagraphStyle" in r
    }
    assert "TITLE" in styles and "HEADING_1" in styles
    text = " ".join(r["insertText"]["text"] for r in requests if "insertText" in r)
    assert "EC2" in text and "web" in text


def test_doc_requests_track_indexes_for_text_and_tables():
    doc = Document()
    doc.add_heading("Hi", 1)
    table = doc.add_table(rows=2, cols=2)
    for r, row in enumerate([["A", "B"], ["C", "D"]]):
        for c, value in enumerate(row):
            table.rows[r].cells[c].text = value
    doc.add_paragraph("After")
    blocks = go.docx_to_blocks(doc)
    assert [b["type"] for b in blocks] == ["paragraph", "table", "paragraph"]
    requests = go.blocks_to_doc_requests(blocks)

    # "Hi\n" is 3 characters at index 1, so the table goes in at index 4 and its
    # first cell is at 8; the cells are then filled last to first.
    assert requests[0] == {"insertText": {"location": {"index": 1}, "text": "Hi\n"}}
    assert requests[1]["updateParagraphStyle"]["range"] == {
        "startIndex": 1,
        "endIndex": 4,
    }
    assert requests[2]["insertTable"] == {
        "location": {"index": 4},
        "rows": 2,
        "columns": 2,
    }
    cell_inserts = [
        (r["insertText"]["location"]["index"], r["insertText"]["text"])
        for r in requests[3:7]
    ]
    assert cell_inserts == [(15, "D"), (13, "C"), (10, "B"), (8, "A")]
    bold = [r["updateTextStyle"]["range"] for r in requests if "updateTextStyle" in r]
    assert bold == [
        {"startIndex": 8, "endIndex": 9},
        {"startIndex": 11, "endIndex": 12},
    ]
    # After the table: 4 + 1 split break + (1 + 2*5) table + 4 characters of text.
    after = requests[-1]["insertText"]
    assert after["location"]["index"] == 4 + 1 + 11 + 4
    assert after["text"] == "After\n"


def test_large_documents_are_sent_in_several_batches():
    log = []
    many = [
        {
            "service": service,
            "type": "Thing",
            "id": f"{service}-{n}",
            "name": f"n{n}",
            "arn": f"arn:aws:{service.lower()}:us-east-1:1:thing/{n}",
            "region": "us-east-1",
            "tags": {},
        }
        for service in ("A", "B", "C")
        for n in range(50)
    ]
    go.publish(
        converter(), many, go.GoogleOptions(docs=True), services=fake_services(log)
    )
    batches = [kw for name, kw in log if name == "documents.batchUpdate"]
    assert len(batches) > 1
    assert all(len(b["body"]["requests"]) <= go.DOC_REQUESTS_PER_BATCH for b in batches)


def test_api_failure_becomes_a_clear_error_without_secrets():
    class Boom(FakeApi):
        def _execute(self):
            raise RuntimeError("quota exceeded for project")

    services = fake_services([])
    services["sheets"] = Boom([], {})
    with pytest.raises(go.GoogleOutputError, match="Google API call failed"):
        go.publish(
            converter(), RESOURCES, go.GoogleOptions(sheets=True), services=services
        )


def test_google_credentials_are_redacted_from_logs():
    key = (
        '{"type": "service_account", "private_key_id": "abc123def456", '
        '"private_key": "-----BEGIN PRIVATE KEY-----\\nMIIEvQIBADANBg\\n'
        '-----END PRIVATE KEY-----\\n", "client_secret": "GOCSPX-abcdefghijk"}'
    )
    text = redact(
        key + " ya29.a0AfH6SMBabcdefghijklmnopqrstuv and 1//0gAbCdEfGhIjKlMnOpQrStUvWx"
    )
    for secret in ("MIIEvQIBADANBg", "abc123def456", "GOCSPX", "ya29.a0", "1//0gAb"):
        assert secret not in text


def test_cli_creates_sheet_and_doc_and_prints_urls(
    aws, monkeypatch, tmp_path, capsys
):  # noqa: F811
    log = []
    monkeypatch.setattr(go, "load_credentials", lambda options: object())
    monkeypatch.setattr(go, "build_services", lambda creds: fake_services(log))
    code = run_cli(
        "--account-regions",
        "us-east-1",
        "--create-google-sheets",
        "--create-google-docs",
        "--google-title",
        "AWS inventory",
        "--google-share-with",
        "me@example.com",
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "Google Sheet: https://docs.google.com/spreadsheets/d/SID/edit" in out
    assert "Google Doc: https://docs.google.com/document/d/DID/edit" in out
    # Only Google output was asked for, so no Excel or Word file is written.
    assert not list((tmp_path / "bom_output").glob("*.xlsx"))
    assert not list((tmp_path / "bom_output").glob("*.docx"))
    create = next(kw for name, kw in log if name == "spreadsheets.create")
    assert create["body"]["properties"]["title"] == "AWS inventory"
    perms = [kw for name, kw in log if name == "permissions.create"]
    assert {p["body"]["emailAddress"] for p in perms} == {"me@example.com"}
    assert all(p["body"]["role"] == "reader" for p in perms)


def test_cli_bad_credentials_file_stops_before_scanning(
    aws, capsys, tmp_path
):  # noqa: F811
    code = run_cli(
        "--account-regions",
        "us-east-1",
        "--create-google-sheets",
        "--google-credentials",
        str(tmp_path / "nope.json"),
    )
    assert code == 2
    assert "file not found" in capsys.readouterr().err
    assert not (tmp_path / "bom_output").exists()
