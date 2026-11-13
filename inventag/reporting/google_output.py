"""
Google Sheets and Google Docs output.

The spreadsheet and the document are built by the same code as the Excel and
Word reports (``BOMConverter.build_excel_workbook`` and
``BOMConverter.build_word_document``), so the layout, the sheet order, the row
order and the templates are the same. This module only sends the result to
Google with the official client libraries.

The Google libraries are an optional install::

    pip install "inventag-aws[google]"

They are imported only when Google output is requested. Credentials are never
logged, and files are private to the account that creates them unless the
caller passes an explicit share option.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..security.safe_output import ensure_private_dir, open_private

logger = logging.getLogger(__name__)

INSTALL_HINT = 'Install the Google libraries with: pip install "inventag-aws[google]"'

SCOPE_SHEETS = "https://www.googleapis.com/auth/spreadsheets"
SCOPE_DOCS = "https://www.googleapis.com/auth/documents"
SCOPE_DRIVE_FILE = "https://www.googleapis.com/auth/drive.file"
SCOPE_DRIVE = "https://www.googleapis.com/auth/drive"

SHARE_ROLES = ("reader", "commenter", "writer")

# Google limits: 50,000 characters in one cell; keep a margin.
MAX_CELL_CHARS = 49000
# Rows sent to the Sheets API in one request.
ROWS_PER_REQUEST = 2000
# Docs API requests sent in one batchUpdate.
DOC_REQUESTS_PER_BATCH = 400


class GoogleOutputError(Exception):
    """Google output could not be created. The message says why."""


class GoogleDependencyError(GoogleOutputError):
    """The optional Google libraries are not installed."""


@dataclass
class GoogleOptions:
    """What the user asked for on the command line."""

    credentials_file: Optional[str] = None
    oauth_client_file: Optional[str] = None
    folder_id: Optional[str] = None
    share_with: List[str] = field(default_factory=list)
    share_role: str = "reader"
    share_anyone: bool = False
    title: Optional[str] = None
    sheets: bool = False
    docs: bool = False
    # Loaded credentials. Never printed: repr=False keeps them out of logs.
    credentials: Any = field(default=None, repr=False, compare=False)

    def scopes(self) -> List[str]:
        scopes = [SCOPE_SHEETS, SCOPE_DOCS]
        # A folder the service account did not create needs the full Drive scope.
        scopes.append(SCOPE_DRIVE if self.folder_id else SCOPE_DRIVE_FILE)
        return scopes

    def resolved_title(self) -> str:
        return self.title or (
            "InvenTag AWS inventory " + datetime.now().strftime("%Y-%m-%d %H:%M")
        )


def validate_options(options: GoogleOptions) -> List[str]:
    """Problems with the options that can be found without a network call."""
    problems = []
    if options.credentials_file and options.oauth_client_file:
        problems.append("give --google-credentials or --google-oauth-client, not both")
    for path_name, path in (
        ("--google-credentials", options.credentials_file),
        ("--google-oauth-client", options.oauth_client_file),
    ):
        if path and not os.path.isfile(path):
            problems.append(f"{path_name}: file not found: {path}")
    if options.share_role not in SHARE_ROLES:
        problems.append(f"--google-share-role must be one of {', '.join(SHARE_ROLES)}")
    for email in options.share_with:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            problems.append(f"--google-share-with: not an email address: {email}")
    if (
        options.share_role != "reader" or options.share_with or options.share_anyone
    ) and not (options.sheets or options.docs):
        problems.append(
            "the --google-share options need --create-google-sheets or "
            "--create-google-docs"
        )
    return problems


def _import_google():
    """Import the Google libraries, or explain how to install them."""
    try:
        import google.auth  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
    except ImportError as e:
        raise GoogleDependencyError(
            f"Google output needs libraries that are not installed ({e.name}). "
            + INSTALL_HINT
        ) from e


def load_credentials(options: GoogleOptions):
    """Google credentials from a service-account file, an OAuth client, or ADC.

    Reads local files only; it makes no call to the Google APIs (a stale OAuth
    token is refreshed, which is the one network call).
    """
    _import_google()
    scopes = options.scopes()
    try:
        if options.credentials_file:
            from google.oauth2 import service_account

            creds = service_account.Credentials.from_service_account_file(
                options.credentials_file, scopes=scopes
            )
            return creds
        if options.oauth_client_file:
            return _oauth_user_credentials(options.oauth_client_file, scopes)
        import google.auth

        creds, _project = google.auth.default(scopes=scopes)
        return creds
    except GoogleOutputError:
        raise
    except Exception as e:
        # The message of a credentials error can quote the file; keep it short.
        raise GoogleOutputError(
            f"Could not load Google credentials ({type(e).__name__}). Pass a "
            "service-account key with --google-credentials, or set up "
            "Application Default Credentials "
            "(gcloud auth application-default login)."
        ) from e


def _token_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return Path(base) / "inventag" / "google-token.json"


def _oauth_user_credentials(client_file: str, scopes: Sequence[str]):
    """User sign-in in the browser; the token is cached in an owner-only file."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_file = _token_path()
    creds = None
    if token_file.is_file():
        creds = Credentials.from_authorized_user_file(str(token_file), list(scopes))
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(client_file, list(scopes))
        creds = flow.run_local_server(port=0)
    ensure_private_dir(token_file.parent)
    with open_private(token_file, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return creds


def build_services(credentials) -> Dict[str, Any]:
    """The Sheets, Docs and Drive clients."""
    _import_google()
    from googleapiclient.discovery import build

    return {
        name: build(name, version, credentials=credentials, cache_discovery=False)
        for name, version in (("sheets", "v4"), ("docs", "v1"), ("drive", "v3"))
    }


# ---------------------------------------------------------------- Drive helpers


def _place_and_share(drive, file_id: str, options: GoogleOptions) -> None:
    """Move the file into the folder and share it, as the options say."""
    if options.folder_id:
        current = drive.files().get(fileId=file_id, fields="parents").execute()
        parents = ",".join(current.get("parents", []))
        drive.files().update(
            fileId=file_id,
            addParents=options.folder_id,
            removeParents=parents,
            fields="id,parents",
        ).execute()
    for email in options.share_with:
        drive.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": options.share_role, "emailAddress": email},
            sendNotificationEmail=False,
            fields="id",
        ).execute()
    if options.share_anyone:
        drive.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute()


def warn_if_file_will_be_invisible(
    options: GoogleOptions, credentials: Any = None
) -> Optional[str]:
    """A service account owns what it creates; say so if nothing will share it."""
    is_service_account = bool(options.credentials_file) or hasattr(
        credentials, "service_account_email"
    )
    if is_service_account and not (
        options.folder_id or options.share_with or options.share_anyone
    ):
        return (
            "The files are created in the service account's own Google Drive, "
            "where you cannot open them. Add --google-share-with YOU@example.com "
            "or --google-folder-id FOLDER_ID."
        )
    return None


# ---------------------------------------------------------------- Sheets


def workbook_to_sheets(workbook) -> List[Dict[str, Any]]:
    """Plain data for each sheet of an openpyxl workbook, in sheet order."""
    sheets = []
    for ws in workbook.worksheets:
        rows: List[List[Any]] = []
        for values in ws.iter_rows(values_only=True):
            row = []
            for value in values:
                if value is None:
                    row.append("")
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    row.append(value)
                else:
                    row.append(str(value)[:MAX_CELL_CHARS])
            rows.append(row)
        while rows and not any(v != "" for v in rows[-1]):
            rows.pop()
        header_color = None
        first = ws.cell(row=1, column=1)
        if first.fill is not None and first.fill.fill_type == "solid":
            rgb = str(first.fill.start_color.rgb or "")
            if re.fullmatch(r"[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}", rgb):
                header_color = rgb[-6:]
        frozen = 0
        if ws.freeze_panes:
            match = re.search(r"(\d+)$", str(ws.freeze_panes))
            frozen = max(int(match.group(1)) - 1, 0) if match else 0
        sheets.append(
            {
                "title": ws.title[:100],
                "rows": rows,
                "header_color": header_color,
                "frozen_rows": frozen,
            }
        )
    return sheets


def _rgb(hex_color: str) -> Dict[str, float]:
    return {
        "red": int(hex_color[0:2], 16) / 255,
        "green": int(hex_color[2:4], 16) / 255,
        "blue": int(hex_color[4:6], 16) / 255,
    }


def create_spreadsheet(
    services: Dict[str, Any], workbook, options: GoogleOptions
) -> str:
    """Create the spreadsheet from a report workbook. Returns its URL."""
    sheets_data = workbook_to_sheets(workbook)
    if not sheets_data:
        raise GoogleOutputError("The report has no sheets to send to Google Sheets.")
    sheets = services["sheets"]

    body = {
        "properties": {"title": options.resolved_title()[:250]},
        "sheets": [
            {
                "properties": {
                    "title": s["title"],
                    "gridProperties": {
                        "rowCount": max(len(s["rows"]), 1),
                        "columnCount": max((len(r) for r in s["rows"]), default=1),
                        **(
                            {"frozenRowCount": s["frozen_rows"]}
                            if s["frozen_rows"]
                            else {}
                        ),
                    },
                }
            }
            for s in sheets_data
        ],
    }
    created = sheets.spreadsheets().create(body=body).execute()
    spreadsheet_id = created["spreadsheetId"]

    # RAW: a value that starts with "=" stays text and never becomes a formula.
    for s in sheets_data:
        rows = s["rows"]
        for start in range(0, len(rows), ROWS_PER_REQUEST):
            chunk = rows[start : start + ROWS_PER_REQUEST]
            sheets.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{s['title'].replace(chr(39), chr(39) * 2)}'!A{start + 1}",
                valueInputOption="RAW",
                body={"values": chunk},
            ).execute()

    sheet_ids = {
        sheet["properties"]["title"]: sheet["properties"]["sheetId"]
        for sheet in created.get("sheets", [])
    }
    requests = []
    for s in sheets_data:
        sheet_id = sheet_ids.get(s["title"])
        if sheet_id is None or not s["rows"]:
            continue
        cell_format = {"textFormat": {"bold": True}}
        fields = "userEnteredFormat(textFormat)"
        if s["header_color"]:
            cell_format["backgroundColor"] = _rgb(s["header_color"])
            fields = "userEnteredFormat(textFormat,backgroundColor)"
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {"userEnteredFormat": cell_format},
                    "fields": fields,
                }
            }
        )
        requests.append(
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": max(len(r) for r in s["rows"]),
                    }
                }
            }
        )
    if requests:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    _place_and_share(services["drive"], spreadsheet_id, options)
    return created.get(
        "spreadsheetUrl",
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
    )


# ---------------------------------------------------------------- Docs

_HEADING_STYLES = {
    "Title": "TITLE",
    "Subtitle": "SUBTITLE",
    "Heading 1": "HEADING_1",
    "Heading 2": "HEADING_2",
    "Heading 3": "HEADING_3",
    "Heading 4": "HEADING_4",
}


def docx_to_blocks(document) -> List[Dict[str, Any]]:
    """The body of a python-docx Document as ordered paragraph and table blocks."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    blocks: List[Dict[str, Any]] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = paragraph.text
            if not text.strip():
                continue  # blank lines and page-break-only paragraphs
            style = paragraph.style.name if paragraph.style is not None else ""
            blocks.append(
                {"type": "paragraph", "text": text, "style": _HEADING_STYLES.get(style)}
            )
        elif tag == "tbl":
            table = Table(child, document)
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            if rows:
                blocks.append({"type": "table", "rows": rows})
    return blocks


def _utf16_len(text: str) -> int:
    """Length in UTF-16 code units, which is how the Docs API counts indexes."""
    return len(text.encode("utf-16-le")) // 2


def blocks_to_doc_requests(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Docs API requests that write the blocks into an empty document.

    Content is inserted from the start of the body (index 1) in order, tracking
    the index after each block. A table of R rows and C columns inserted at
    index i puts its first cell's paragraph at i + 4 (the new table follows a
    paragraph break at i); the cell after it is 2 further on, and each new row
    adds 1 + 2*C. The cells are filled last-to-first so earlier indexes stay
    valid, and the table takes 1 + R*(1 + 2*C) + (the text in its cells) more
    index positions.
    """
    requests: List[Dict[str, Any]] = []
    cursor = 1
    for block in blocks:
        if block["type"] == "paragraph":
            text = block["text"] + "\n"
            requests.append(
                {"insertText": {"location": {"index": cursor}, "text": text}}
            )
            length = _utf16_len(text)
            style = block.get("style")
            if style:
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": cursor,
                                "endIndex": cursor + length,
                            },
                            "paragraphStyle": {"namedStyleType": style},
                            "fields": "namedStyleType",
                        }
                    }
                )
            cursor += length
            continue

        rows = block["rows"]
        n_rows = len(rows)
        n_cols = max(len(r) for r in rows)
        requests.append(
            {
                "insertTable": {
                    "location": {"index": cursor},
                    "rows": n_rows,
                    "columns": n_cols,
                }
            }
        )
        first = cursor + 4

        def cell_index(r: int, c: int) -> int:
            return first + 2 * c + r * (1 + 2 * n_cols)

        texts = {
            (r, c): (rows[r][c] if c < len(rows[r]) else "")
            for r in range(n_rows)
            for c in range(n_cols)
        }
        for r in reversed(range(n_rows)):
            for c in reversed(range(n_cols)):
                if texts[(r, c)]:
                    requests.append(
                        {
                            "insertText": {
                                "location": {"index": cell_index(r, c)},
                                "text": texts[(r, c)],
                            }
                        }
                    )
        # Bold header cells, using the final positions (all text is in place).
        offset = 0
        for r in range(n_rows):
            for c in range(n_cols):
                length = _utf16_len(texts[(r, c)])
                if r == 0 and length:
                    start = cell_index(r, c) + offset
                    requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": start,
                                    "endIndex": start + length,
                                },
                                "textStyle": {"bold": True},
                                "fields": "bold",
                            }
                        }
                    )
                offset += length
        total_text = sum(_utf16_len(t) for t in texts.values())
        cursor += 1 + (1 + n_rows * (1 + 2 * n_cols)) + total_text
    return requests


def create_document(
    services: Dict[str, Any], word_document, options: GoogleOptions
) -> str:
    """Create the Google Doc from a report Word document. Returns its URL."""
    blocks = docx_to_blocks(word_document)
    if not blocks:
        raise GoogleOutputError("The report is empty; no Google Doc was created.")
    docs = services["docs"]
    created = (
        docs.documents()
        .create(body={"title": options.resolved_title()[:250]})
        .execute()
    )
    document_id = created["documentId"]
    requests = blocks_to_doc_requests(blocks)
    for start in range(0, len(requests), DOC_REQUESTS_PER_BATCH):
        docs.documents().batchUpdate(
            documentId=document_id,
            body={"requests": requests[start : start + DOC_REQUESTS_PER_BATCH]},
        ).execute()
    _place_and_share(services["drive"], document_id, options)
    return f"https://docs.google.com/document/d/{document_id}/edit"


# ---------------------------------------------------------------- entry point


def publish(
    converter,
    bom_data,
    options: GoogleOptions,
    sheets_template=None,
    docs_template=None,
    services: Optional[Dict[str, Any]] = None,
    credentials: Any = None,
) -> Dict[str, str]:
    """Create the requested Google files. Returns {"spreadsheet_url", "document_url"}."""
    if services is None:
        credentials = credentials or options.credentials or load_credentials(options)
        services = build_services(credentials)
    note = warn_if_file_will_be_invisible(options, credentials)
    if note:
        logger.warning(note)

    results: Dict[str, str] = {}
    try:
        if options.sheets:
            converter.prepare_data(bom_data)
            workbook = converter.build_excel_workbook(sheets_template)
            results["spreadsheet_url"] = create_spreadsheet(services, workbook, options)
        if options.docs:
            converter.prepare_data(bom_data)
            document = converter.build_word_document(docs_template)
            results["document_url"] = create_document(services, document, options)
    except GoogleOutputError:
        raise
    except Exception as e:
        # API errors (HttpError) carry the reason; never include credentials.
        reason = getattr(e, "reason", None) or str(e)
        raise GoogleOutputError(
            f"Google API call failed ({type(e).__name__}): {str(reason)[:300]}"
        ) from e
    return results
