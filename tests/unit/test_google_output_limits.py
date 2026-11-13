"""Google output: request shapes, size limits, retries and failure messages.

The Google client is faked (no network). The key sets below were copied from the
discovery documents shipped in google-api-python-client 2.202.0
(googleapiclient/discovery_cache/documents/{sheets.v4,docs.v1,drive.v3}.json),
so a typo in a request body is caught here instead of by Google.
"""

import pytest
from openpyxl import Workbook

from inventag.reporting import google_output as go
from tests.unit.test_google_output import FakeApi, fake_services

SHEET_PROPERTIES = {
    "dataSourceSheetProperties",
    "gridProperties",
    "hidden",
    "index",
    "rightToLeft",
    "sheetId",
    "sheetType",
    "tabColor",
    "tabColorStyle",
    "title",
}
GRID_PROPERTIES = {
    "columnCount",
    "columnGroupControlAfter",
    "frozenColumnCount",
    "frozenRowCount",
    "hideGridlines",
    "rowCount",
    "rowGroupControlAfter",
}
SHEETS_REQUEST_KEYS = {"repeatCell", "autoResizeDimensions"}
DOCS_REQUEST_KEYS = {
    "insertText",
    "insertTable",
    "updateParagraphStyle",
    "updateTextStyle",
}
PERMISSION_KEYS = {"type", "role", "emailAddress"}


def workbook(rows_by_sheet):
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in rows_by_sheet.items():
        ws = wb.create_sheet(title)
        for row in rows:
            ws.append(row)
    return wb


def test_spreadsheet_request_bodies_use_real_api_field_names():
    log = []
    wb = workbook({"EC2": [["id", "size"], ["i-1", 5]]})
    go.create_spreadsheet(fake_services(log), wb, go.GoogleOptions(sheets=True))
    create = next(kw for name, kw in log if name == "spreadsheets.create")
    for sheet in create["body"]["sheets"]:
        assert set(sheet["properties"]) <= SHEET_PROPERTIES
        assert set(sheet["properties"]["gridProperties"]) <= GRID_PROPERTIES
    batch = next(kw for name, kw in log if name == "spreadsheets.batchUpdate")
    for request in batch["body"]["requests"]:
        assert set(request) <= SHEETS_REQUEST_KEYS


def test_doc_requests_use_real_api_field_names():
    blocks = [
        {"type": "paragraph", "text": "Title", "style": "HEADING_1"},
        {"type": "table", "rows": [["a", "b"], ["c", "d"]]},
    ]
    for request in go.blocks_to_doc_requests(blocks):
        assert set(request) <= DOCS_REQUEST_KEYS


def test_sharing_uses_all_drives_flag_and_known_permission_fields():
    log = []
    options = go.GoogleOptions(
        sheets=True,
        folder_id="FOLDER",
        share_with=["a@example.com"],
        share_anyone=True,
    )
    go.create_spreadsheet(fake_services(log), workbook({"S": [["x"]]}), options)
    drive_calls = [(n, kw) for n, kw in log if n.startswith(("files.", "permissions."))]
    assert drive_calls
    for name, kw in drive_calls:
        assert kw["supportsAllDrives"] is True, name
    for name, kw in drive_calls:
        if name == "permissions.create":
            assert set(kw["body"]) <= PERMISSION_KEYS | {"type", "role"}
    move = next(kw for n, kw in drive_calls if n == "files.update")
    assert move["addParents"] == "FOLDER" and move["removeParents"] == "root-folder"


def test_file_without_a_parent_is_moved_without_removeparents():
    log = []
    services = fake_services(log)
    services["drive"]._responses["files.get"] = {}
    go.create_spreadsheet(
        services, workbook({"S": [["x"]]}), go.GoogleOptions(sheets=True, folder_id="F")
    )
    move = next(kw for n, kw in log if n == "files.update")
    assert "removeParents" not in move


# ----------------------------------------------------------------- size limits
def test_a_report_over_ten_million_cells_is_refused_before_any_call():
    log = []
    rows = [["x"] * 1000] * 10001  # 10,001,000 cells
    sheets = [{"title": "Big", "rows": rows, "header_color": None, "frozen_rows": 0}]
    with pytest.raises(go.GoogleOutputError) as error:
        go.check_spreadsheet_size(sheets)
    assert "10,000,000" in str(error.value) and "No spreadsheet was created" in str(
        error.value
    )
    assert log == []


def test_cells_of_all_sheets_are_added_up():
    sheet = {"rows": [["x"] * 1000] * 6000, "header_color": None, "frozen_rows": 0}
    sheets = [dict(sheet, title="A"), dict(sheet, title="B")]  # 12 million
    with pytest.raises(go.GoogleOutputError):
        go.check_spreadsheet_size(sheets)
    go.check_spreadsheet_size([dict(sheet, title="A")])  # 6 million is fine


def test_too_many_columns_are_refused():
    sheets = [
        {
            "title": "Wide",
            "rows": [["x"] * (go.MAX_SHEET_COLUMNS + 1)],
            "header_color": None,
            "frozen_rows": 0,
        }
    ]
    with pytest.raises(go.GoogleOutputError, match="columns"):
        go.check_spreadsheet_size(sheets)


def test_rows_are_sent_in_requests_below_the_row_and_character_limits():
    rows = [["a" * 300] * 10 for _ in range(1000)]  # 3,000 characters per row
    chunks = list(go._chunk_rows(rows))
    assert sum(len(c) for _, c in chunks) == 1000
    assert [start for start, _ in chunks][0] == 0
    for start, chunk in chunks:
        assert len(chunk) <= go.ROWS_PER_REQUEST
        assert sum(len(v) for r in chunk for v in r) <= go.CHARS_PER_REQUEST + 3000
    # the next chunk starts where the last one ended
    ends = [start + len(c) for start, c in chunks]
    assert [s for s, _ in chunks][1:] == ends[:-1]
    assert len(chunks) > 1


def test_one_huge_row_is_still_sent_alone():
    rows = [["z" * 49000] * 50, ["a"]]
    chunks = list(go._chunk_rows(rows))
    assert [(s, len(c)) for s, c in chunks] == [(0, 1), (1, 1)]


def test_nan_and_infinity_become_text():
    wb = workbook({"S": [[float("nan"), float("inf"), 1.5, 7]]})
    row = go.workbook_to_sheets(wb)[0]["rows"][0]
    assert row == ["nan", "inf", 1.5, 7]


# ------------------------------------------------------------ retry and errors
class RateLimited(Exception):
    status_code = 429


class Forbidden(Exception):
    status_code = 403
    reason = "The caller does not have permission"


def test_429_is_retried_after_a_wait_and_other_errors_are_not(monkeypatch):
    waits = []
    monkeypatch.setattr(go, "_sleep", waits.append)

    class Request:
        def __init__(self, failures, error):
            self.calls, self.failures, self.error = 0, failures, error

        def execute(self):
            self.calls += 1
            if self.calls <= self.failures:
                raise self.error()
            return {"ok": True}

    request = Request(2, RateLimited)
    assert go._execute(request) == {"ok": True}
    assert request.calls == 3 and waits == [5, 10]

    forbidden = Request(1, Forbidden)
    with pytest.raises(Forbidden):
        go._execute(forbidden)
    assert forbidden.calls == 1

    endless = Request(99, RateLimited)
    with pytest.raises(RateLimited):
        go._execute(endless)
    assert endless.calls == len(go.RATE_LIMIT_WAITS) + 1


class FailingApi(FakeApi):
    """A FakeApi whose call at ``fail_at`` (for example "documents.batchUpdate") fails."""

    fail_at = ""

    def __getattr__(self, name):
        if name == "execute":
            return self._execute
        return type(self)(self._log, self._responses, self._path + (name,))

    def _execute(self):
        if ".".join(self._path) == self.fail_at:
            raise Forbidden("secret-token-abc123 should not matter")
        return super()._execute()


def failing_services(log, fail_at):
    services = fake_services(log)
    api_class = type("Failing", (FailingApi,), {"fail_at": fail_at})
    return {name: api_class(api._log, api._responses) for name, api in services.items()}


def test_failure_after_create_names_the_incomplete_spreadsheet():
    log = []
    services = failing_services(log, "spreadsheets.values.update")
    with pytest.raises(go.GoogleOutputError) as error:
        go.create_spreadsheet(
            services, workbook({"S": [["x"]]}), go.GoogleOptions(sheets=True)
        )
    message = str(error.value)
    assert "already created and may be incomplete" in message
    assert "https://docs.google.com/spreadsheets/d/SID/edit" in message
    assert "does not have permission" in message


def test_failure_after_create_names_the_incomplete_document():
    log = []
    services = failing_services(log, "documents.batchUpdate")
    from docx import Document

    doc = Document()
    doc.add_paragraph("hello")
    with pytest.raises(go.GoogleOutputError) as error:
        go.create_document(services, doc, go.GoogleOptions(docs=True))
    assert "https://docs.google.com/document/d/DID/edit" in str(error.value)


def test_error_text_masks_registered_secrets():
    from inventag.security import redaction

    redaction.register_secret("hunter2-token-value")
    try:

        class Boom(Exception):
            reason = "bad token hunter2-token-value"

        assert "hunter2-token-value" not in go._api_reason(Boom())
    finally:
        redaction.clear_registered_secrets()
