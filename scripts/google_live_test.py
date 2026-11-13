#!/usr/bin/env python3
"""Live test of InvenTag's Google Sheets and Google Docs output.

Run it from a checkout of InvenTag, in your own terminal, with your own Google
sign-in. It needs no AWS account: it builds a small fictional estate in this
process with moto (a mock of AWS), runs the real InvenTag command line with
``--create-google-sheets --create-google-docs`` (once with the default layout,
once with ``--template standard-bom``), then reads the files back through the
Google APIs and compares them with the Excel and Word files built in the same
run. The only real network calls go to Google.

Safe by construction:
  * It never reads, prints or copies the contents of a credential file. The
    file path is handed to InvenTag and Google's own libraries.
  * It uses the narrow ``drive.file`` scope: it can only see files it created.
    (``--folder-id`` is opt-in and needs the full Drive scope.)
  * Files are private (only the owner) unless you pass ``--share-with``.
  * At the end it moves the files it created to the Drive trash. ``--keep``
    leaves them.
  * Error output shows the HTTP status and Google's reason, never a token.

Exit code 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.util
import io
import json
import math
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]

INSTALL = 'pip install "inventag-aws[google]"'
GCLOUD_SCOPES = ",".join(
    [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/cloud-platform",
    ]
)

EPILOG = f"""\
BEFORE YOU RUN (the script checks the first two and says what is missing)

1. Install the Google libraries (and moto, which fakes AWS for this test):
     {INSTALL}
     pip install moto
   Run the script from a checkout of the repository, with that Python.

2. In the Google Cloud project of your credentials, enable three APIs
   (Google Cloud console > APIs & Services > Library, search by these names):
     "Google Sheets API"   "Google Docs API"   "Google Drive API"
   If one is off, Google answers HTTP 403 "accessNotConfigured" or
   "SERVICE_DISABLED" and this script names the API to enable.

3. Pick ONE way to sign in:
   a) Your own Google account (simplest for a laptop). In the console create an
      OAuth client of type "Desktop app", download its JSON, then:
        python scripts/google_live_test.py --google-oauth-client client_secret.json
      A browser opens once; the token is cached in
      ~/.config/inventag/google-token.json (readable by you only).
      If the app is in "Testing" status, add your account under OAuth consent
      screen > Test users.
   b) A service account key:
        python scripts/google_live_test.py --google-credentials key.json
      The service account owns the files in its own Drive, so you cannot open
      them in a browser. The script reads them back with the same key and puts
      them in the trash at the end. Add --share-with you@example.com to look.
   c) Application Default Credentials (ADC). Google blocks gcloud's own sign-in
      client from the Drive, Docs and Sheets scopes, so you need your own
      Desktop-app OAuth client file (as in a) and:
        gcloud auth application-default login \\
          --client-id-file=client_secret.json \\
          --scopes={GCLOUD_SCOPES}
      then:
        python scripts/google_live_test.py
      If Google answers "requires a quota project", also run
        gcloud auth application-default set-quota-project YOUR_PROJECT_ID
      NOT VERIFIED by us: the --client-id-file requirement and the quota-project
      step come from gcloud's reference page and one write-up, not from a run.
      With --client-id-file gcloud does not write a quota project itself.

WHAT IT CHECKS (PASS/FAIL table at the end)
  spreadsheet and document exist, have the right type and the printed URL id;
  sheet titles and order, rows and columns per sheet and every cell match the
  local .xlsx; text that starts with = comes back as text, not a formula;
  long, accented and CJK text and an empty sheet survive; header row bold and
  coloured; frozen rows; headings, table count and every table cell of the Doc
  match the local .docx; both files are private (only the owner can open
  them). With --large: a 20,000-row sheet and a 300-row Doc table, with the
  API call count and time, and an injected "429 too many requests" that must
  be retried.
"""


# ----------------------------------------------------------------------------
# Results table


@dataclass
class Check:
    group: str
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    checks: List[Check] = field(default_factory=list)
    urls: List[Tuple[str, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add(self, group: str, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append(Check(group, name, bool(ok), detail))
        return bool(ok)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    def render(self) -> str:
        lines = []
        width = max([len(f"{c.group}: {c.name}") for c in self.checks] + [10])
        for c in self.checks:
            label = f"{c.group}: {c.name}".ljust(width)
            tail = f"  {c.detail}" if c.detail else ""
            lines.append(f"  {'PASS' if c.ok else 'FAIL'}  {label}{tail}")
        failed = sum(1 for c in self.checks if not c.ok)
        lines.append("")
        lines.append(
            f"{len(self.checks) - failed} passed, {failed} failed"
            if self.checks
            else "no checks ran"
        )
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# Errors: status and reason only, never tokens


def _redact(text: str) -> str:
    try:
        from inventag.security.redaction import redact

        text = redact(text)
    except Exception:
        pass
    # Belt and braces for anything that looks like a bearer or OAuth token.
    text = re.sub(r"ya29\.[A-Za-z0-9_\-\.]+", "[token]", text)
    text = re.sub(r"1//[A-Za-z0-9_\-]{20,}", "[token]", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [token]", text)
    return text


API_HINTS = (
    (
        "sheets.googleapis.com",
        'Enable "Google Sheets API" in APIs & Services > Library.',
    ),
    ("docs.googleapis.com", 'Enable "Google Docs API" in APIs & Services > Library.'),
    ("drive.googleapis.com", 'Enable "Google Drive API" in APIs & Services > Library.'),
)


def describe_error(error: BaseException) -> str:
    """HTTP status and Google's reason (plus a hint), with secrets masked."""
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "resp", None), "status", None)
    reason = getattr(error, "reason", None) or str(error)
    text = str(reason)
    details = getattr(error, "error_details", None)
    if details:
        text += f" {details}"
    full = f"{error} {text}"
    hint = ""
    low = full.lower()
    if (
        "accessnotconfigured" in low
        or "service_disabled" in low
        or "has not been used in project" in low
    ):
        named = [h for host, h in API_HINTS if host in low]
        hint = " " + (
            " ".join(named) if named else "Enable the Sheets, Docs and Drive APIs."
        )
    elif "quota project" in low:
        hint = " Run: gcloud auth application-default set-quota-project YOUR_PROJECT_ID"
    elif "insufficient" in low and "scope" in low:
        hint = (
            " The sign-in lacks a scope. With ADC, log in again with the --scopes "
            "shown in --help; with --google-oauth-client delete "
            "~/.config/inventag/google-token.json and rerun."
        )
    prefix = f"HTTP {status}: " if status else f"{type(error).__name__}: "
    return _redact(prefix + text[:400]) + hint


# ----------------------------------------------------------------------------
# Counting proxy around the Google clients


@dataclass
class Stats:
    calls: int = 0
    seconds: float = 0.0
    by_method: Dict[str, int] = field(default_factory=dict)
    inject_429: int = 0
    injected: int = 0
    max_request_chars: int = 0
    values_update_calls: int = 0

    def summary(self) -> str:
        return f"{self.calls} API calls in {self.seconds:.1f} s"


class Proxy:
    """Wraps a Google client; counts ``execute()`` calls and can inject a 429."""

    def __init__(self, target, stats: Stats, path: Tuple[str, ...] = (), kwargs=None):
        self._t, self._s, self._p, self._kw = target, stats, path, kwargs or {}

    def __getattr__(self, name):
        attr = getattr(self._t, name)
        if name == "execute":
            return self._execute
        if callable(attr):

            def call(*args, **kwargs):
                return Proxy(attr(*args, **kwargs), self._s, self._p + (name,), kwargs)

            return call
        return attr

    def _execute(self, *args, **kwargs):
        path = ".".join(self._p)
        stats = self._s
        if path.endswith("values.update"):
            stats.values_update_calls += 1
            body = self._kw.get("body")
            if body is not None:
                size = len(json.dumps(body))
                stats.max_request_chars = max(stats.max_request_chars, size)
            if stats.injected < stats.inject_429:
                stats.injected += 1
                stats.calls += 1
                stats.by_method[path] = stats.by_method.get(path, 0) + 1
                raise _http_error(429, "Injected by google_live_test: rate limit")
        start = time.time()
        stats.calls += 1
        stats.by_method[path] = stats.by_method.get(path, 0) + 1
        try:
            return self._t.execute(*args, **kwargs)
        finally:
            stats.seconds += time.time() - start


def _http_error(status: int, message: str):
    from googleapiclient.errors import HttpError
    import httplib2

    content = json.dumps({"error": {"code": status, "message": message}}).encode()
    return HttpError(httplib2.Response({"status": str(status)}), content)


def counting_services(services: Dict[str, Any], stats: Stats) -> Dict[str, Any]:
    return {name: Proxy(api, stats, (name,)) for name, api in services.items()}


# ----------------------------------------------------------------------------
# Reading Google files back

SHEET_MIME = "application/vnd.google-apps.spreadsheet"
DOC_MIME = "application/vnd.google-apps.document"
URL_RE = re.compile(
    r"https://docs\.google\.com/(spreadsheets|document)/d/([A-Za-z0-9_\-]+)"
)


def quote_title(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def file_id_from_url(url: str, kind: str) -> Optional[str]:
    match = URL_RE.match(url or "")
    if match and match.group(1) == kind:
        return match.group(2)
    return None


def read_sheet_properties(sheets, spreadsheet_id: str) -> List[Dict[str, Any]]:
    result = (
        sheets.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties(sheetId,title,index,gridProperties))",
        )
        .execute()
    )
    return [s["properties"] for s in result.get("sheets", [])]


def read_sheet_values(
    sheets, spreadsheet_id: str, title: str, a1: Optional[str] = None
) -> List[List[Any]]:
    rng = quote_title(title) + (f"!{a1}" if a1 else "")
    result = (
        sheets.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=rng,
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    return result.get("values", [])


def read_cells(sheets, spreadsheet_id: str, title: str, a1_cells: Sequence[str]):
    """userEnteredValue and format of single cells, in the order asked."""
    result = (
        sheets.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            ranges=[f"{quote_title(title)}!{c}:{c}" for c in a1_cells],
            includeGridData=True,
            fields=(
                "sheets(properties(title),data(rowData(values("
                "userEnteredValue,userEnteredFormat(textFormat(bold),backgroundColor)"
                "))))"
            ),
        )
        .execute()
    )
    out = []
    data = (result.get("sheets") or [{}])[0].get("data", [])
    for grid in data:
        rows = grid.get("rowData") or [{}]
        values = rows[0].get("values") or [{}]
        out.append(values[0])
    return out


def a1(row: int, col: int) -> str:
    letters = ""
    n = col + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row + 1}"


def same_value(expected: Any, actual: Any) -> bool:
    if expected in ("", None):
        return actual in ("", None)
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and math.isclose(float(expected), float(actual), rel_tol=1e-9, abs_tol=1e-9)
        )
    return isinstance(actual, str) and actual == expected


def compare_rows(
    expected: List[List[Any]], actual: List[List[Any]]
) -> List[Tuple[str, Any, Any]]:
    """Cells that differ. Google drops trailing empty cells, so those are padded."""
    mismatches = []
    for r in range(max(len(expected), len(actual))):
        erow = expected[r] if r < len(expected) else []
        arow = actual[r] if r < len(actual) else []
        for c in range(max(len(erow), len(arow))):
            e = erow[c] if c < len(erow) else ""
            a = arow[c] if c < len(arow) else ""
            if not same_value(e, a):
                mismatches.append((a1(r, c), e, a))
    return mismatches


def short(value: Any, limit: int = 60) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def color_close(expected_hex: str, actual: Dict[str, float]) -> bool:
    want = [int(expected_hex[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    got = [actual.get(k, 0.0) for k in ("red", "green", "blue")]
    return all(abs(w - g) < 0.01 for w, g in zip(want, got))


def verify_spreadsheet(
    report: Report,
    group: str,
    services: Dict[str, Any],
    spreadsheet_id: str,
    expected: List[Dict[str, Any]],
    probes: Sequence[str] = (),
    optional_probes: Sequence[str] = (),
    full_compare_limit: int = 5000,
) -> None:
    """Compare a Google spreadsheet with ``google_output.workbook_to_sheets`` data."""
    sheets = services["sheets"]
    props = read_sheet_properties(sheets, spreadsheet_id)
    got_titles = [p["title"] for p in sorted(props, key=lambda p: p.get("index", 0))]
    want_titles = [s["title"] for s in expected]
    report.add(
        group,
        "sheet titles and order match",
        got_titles == want_titles,
        "" if got_titles == want_titles else f"want {want_titles}, got {got_titles}",
    )
    by_title = {p["title"]: p for p in props}
    count_problems, value_problems, format_problems = [], [], []
    for sheet in expected:
        title = sheet["title"]
        prop = by_title.get(title)
        if prop is None:
            count_problems.append(f"{title}: missing")
            continue
        grid = prop.get("gridProperties", {})
        rows = sheet["rows"]
        want_rows = max(len(rows), 1)
        want_cols = max((len(r) for r in rows), default=1)
        if (grid.get("rowCount"), grid.get("columnCount")) != (want_rows, want_cols):
            count_problems.append(
                f"{title}: want {want_rows}x{want_cols}, got "
                f"{grid.get('rowCount')}x{grid.get('columnCount')}"
            )
        if sheet.get("frozen_rows", 0) != grid.get("frozenRowCount", 0):
            format_problems.append(
                f"{title}: frozen rows want {sheet.get('frozen_rows', 0)}, got "
                f"{grid.get('frozenRowCount', 0)}"
            )
        if len(rows) <= full_compare_limit:
            actual = read_sheet_values(sheets, spreadsheet_id, title) if rows else []
            diffs = compare_rows(rows, actual)
            if diffs:
                shown = "; ".join(
                    f"{c} want {short(e)} got {short(a)}" for c, e, a in diffs[:3]
                )
                value_problems.append(f"{title}: {len(diffs)} cells differ ({shown})")
        if rows:
            cell = read_cells(sheets, spreadsheet_id, title, ["A1"])[0]
            fmt = cell.get("userEnteredFormat", {})
            if not fmt.get("textFormat", {}).get("bold"):
                format_problems.append(f"{title}: A1 is not bold")
            if sheet.get("header_color") and not color_close(
                sheet["header_color"], fmt.get("backgroundColor", {})
            ):
                format_problems.append(f"{title}: header colour differs")
    report.add(
        group,
        "rows and columns per sheet match",
        not count_problems,
        "; ".join(count_problems[:3]),
    )
    report.add(
        group,
        "every cell value matches",
        not value_problems,
        "; ".join(value_problems[:3]),
    )
    report.add(
        group,
        "header bold and coloured, rows frozen",
        not format_problems,
        "; ".join(format_problems[:3]),
    )
    empties = [s["title"] for s in expected if not s["rows"]]
    if empties:
        problems = []
        for title in empties:
            if read_sheet_values(sheets, spreadsheet_id, title):
                problems.append(title)
        report.add(group, "empty sheet stays empty", not problems, ", ".join(problems))

    # Probes: text that must come back as text and not as a formula.
    for probe in [*probes, *[p for p in optional_probes if p not in probes]]:
        required = probe in probes
        location = None
        for sheet in expected:
            for r, row in enumerate(sheet["rows"]):
                for c, value in enumerate(row):
                    if value == probe:
                        location = (sheet["title"], r, c)
                        break
                if location:
                    break
            if location:
                break
        label = f"probe {short(probe, 24)}"
        if location is None:
            if required:
                report.add(group, label, False, "not found in the local workbook")
            continue
        title, r, c = location
        cell = read_cells(sheets, spreadsheet_id, title, [a1(r, c)])[0]
        entered = cell.get("userEnteredValue", {})
        ok = entered.get("stringValue") == probe and "formulaValue" not in entered
        report.add(
            group,
            label + (" is text" if probe.startswith("=") else " is intact"),
            ok,
            "" if ok else f"{title}!{a1(r, c)} came back as {short(entered)}",
        )


# --- Docs


def read_document(docs, document_id: str) -> Dict[str, Any]:
    return docs.documents().get(documentId=document_id).execute()


def _paragraph_text(paragraph: Dict[str, Any]) -> str:
    return "".join(
        e.get("textRun", {}).get("content", "") for e in paragraph.get("elements", [])
    )


def parse_document(document: Dict[str, Any]):
    """(paragraphs, tables) from a Docs API document.

    paragraphs: [(style, text)] outside tables, empty ones left out.
    tables: [[[cell text]]].
    """
    paragraphs, tables = [], []
    for element in document.get("body", {}).get("content", []):
        if "paragraph" in element:
            text = _paragraph_text(element["paragraph"]).rstrip("\n")
            if text.strip():
                style = (
                    element["paragraph"]
                    .get("paragraphStyle", {})
                    .get("namedStyleType", "NORMAL_TEXT")
                )
                paragraphs.append((style, text))
        elif "table" in element:
            rows = []
            for row in element["table"].get("tableRows", []):
                cells = []
                for cell in row.get("tableCells", []):
                    parts = [
                        _paragraph_text(c["paragraph"]).rstrip("\n")
                        for c in cell.get("content", [])
                        if "paragraph" in c
                    ]
                    cells.append("\n".join(parts).strip())
                rows.append(cells)
            tables.append(rows)
    return paragraphs, tables


def expected_from_blocks(blocks: List[Dict[str, Any]]):
    """What parse_document should return for ``google_output.docx_to_blocks`` blocks."""
    paragraphs, tables = [], []
    for block in blocks:
        if block["type"] == "paragraph":
            style = block.get("style") or "NORMAL_TEXT"
            for line in block["text"].split("\n"):
                if line.strip():
                    paragraphs.append((style, line))
        else:
            tables.append([[str(c).strip() for c in row] for row in block["rows"]])
    return paragraphs, tables


def verify_document(
    report: Report,
    group: str,
    services: Dict[str, Any],
    document_id: str,
    blocks: List[Dict[str, Any]],
) -> None:
    document = read_document(services["docs"], document_id)
    got_p, got_t = parse_document(document)
    want_p, want_t = expected_from_blocks(blocks)

    want_h = [(s, t) for s, t in want_p if s != "NORMAL_TEXT"]
    got_h = [(s, t) for s, t in got_p if s != "NORMAL_TEXT"]
    report.add(
        group,
        "headings match the local outline",
        got_h == want_h,
        (
            ""
            if got_h == want_h
            else f"{len(want_h)} wanted, {len(got_h)} found; first difference: "
            + short(
                next((pair for pair in zip(want_h, got_h) if pair[0] != pair[1]), None)
            )
        ),
    )
    report.add(
        group,
        "paragraph text matches",
        got_p == want_p,
        (
            ""
            if got_p == want_p
            else f"{len(want_p)} wanted, {len(got_p)} found; first difference: "
            + short(
                next((pair for pair in zip(want_p, got_p) if pair[0] != pair[1]), None)
            )
        ),
    )
    report.add(
        group,
        "table count matches",
        len(got_t) == len(want_t),
        f"want {len(want_t)}, got {len(got_t)}",
    )
    problems = []
    for index, (want, got) in enumerate(zip(want_t, got_t)):
        if len(want) != len(got):
            problems.append(f"table {index + 1}: want {len(want)} rows, got {len(got)}")
            continue
        for r, (wrow, grow) in enumerate(zip(want, got)):
            width = max(len(wrow), len(grow))
            wrow = wrow + [""] * (width - len(wrow))
            grow = grow + [""] * (width - len(grow))
            for c, (w, g) in enumerate(zip(wrow, grow)):
                if w != g:
                    problems.append(
                        f"table {index + 1} r{r + 1}c{c + 1}: want {short(w, 30)} got {short(g, 30)}"
                    )
    report.add(
        group,
        "every table cell matches",
        not problems,
        f"{len(problems)} differ; " + "; ".join(problems[:3]) if problems else "",
    )


# --- Drive


def verify_file(
    report: Report,
    group: str,
    services: Dict[str, Any],
    file_id: str,
    url: str,
    kind: str,
    title: Optional[str] = None,
    folder_id: Optional[str] = None,
) -> None:
    drive = services["drive"]
    url_id = file_id_from_url(url, "spreadsheets" if kind == "sheet" else "document")
    report.add(
        group,
        "URL has the right shape and the file id",
        url_id == file_id,
        "" if url_id == file_id else f"url {url!r}",
    )
    meta = (
        drive.files()
        .get(
            fileId=file_id,
            fields="id,name,mimeType,trashed,parents,webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )
    mime = SHEET_MIME if kind == "sheet" else DOC_MIME
    ok = meta.get("id") == file_id and meta.get("mimeType") == mime
    report.add(
        group,
        "file exists in Drive with the right type",
        ok,
        "" if ok else f"id {meta.get('id')!r} type {meta.get('mimeType')!r}",
    )
    link = meta.get("webViewLink")
    if link:
        report.add(
            group, "Drive's own link has the same id", file_id in link, link[:90]
        )
    if title is not None:
        report.add(
            group,
            "title is as requested",
            meta.get("name") == title,
            f"got {meta.get('name')!r}",
        )
    if folder_id:
        report.add(
            group,
            "file is in the requested folder",
            folder_id in (meta.get("parents") or []),
            f"parents {meta.get('parents')}",
        )


def verify_private(
    report: Report,
    group: str,
    services: Dict[str, Any],
    file_id: str,
    share_with: Sequence[str] = (),
    share_role: str = "reader",
) -> None:
    result = (
        services["drive"]
        .permissions()
        .list(
            fileId=file_id,
            fields="permissions(id,type,role,emailAddress)",
            supportsAllDrives=True,
        )
        .execute()
    )
    perms = result.get("permissions", [])
    owners = [p for p in perms if p.get("role") == "owner"]
    others = [p for p in perms if p.get("role") != "owner"]
    wanted = sorted(e.lower() for e in share_with)
    got = sorted((p.get("emailAddress") or "").lower() for p in others)
    public = [p for p in perms if p.get("type") in ("anyone", "domain")]
    if share_with:
        ok = (
            len(owners) == 1
            and got == wanted
            and all(p.get("role") == share_role for p in others)
            and not public
        )
        name = "shared only with the people asked for"
    else:
        ok = len(owners) == 1 and not others
        name = "private: only the owner can open it"
    detail = (
        ""
        if ok
        else "permissions: "
        + ", ".join(f"{p.get('type')}/{p.get('role')}" for p in perms)
    )
    report.add(group, name, ok, detail)


def account_email(drive) -> Optional[str]:
    try:
        about = drive.about().get(fields="user(emailAddress)").execute()
        return (about.get("user") or {}).get("emailAddress") or None
    except Exception:
        return None


def trash(drive, file_id: str) -> Optional[str]:
    """Move a file to the Drive trash. Returns an error text or None."""
    try:
        drive.files().update(
            fileId=file_id,
            body={"trashed": True},
            fields="id,trashed",
            supportsAllDrives=True,
        ).execute()
        return None
    except Exception as e:  # pragma: no cover - exercised against real Google
        return describe_error(e)


# ----------------------------------------------------------------------------
# Probe and large synthetic files

PROBE_FORMULA = '=HYPERLINK("http://evil.example","click")'
PROBE_PLUS = "+1+1"
PROBE_MINUS = "-2+3"
PROBE_AT = "@SUM(A1)"
PROBE_CJK = "平台团队 日本語テスト 한국어 Équipe ñ 🙂"
# Over 30,000 characters but under Excel's 32,767 limit, so the local .xlsx and the
# Google sheet hold the same text (openpyxl cuts longer text).
PROBE_LONG = "long-" + "0123456789" * 3200  # 32,005 characters
PROBE_QUOTE_TITLE = "It's a probe sheet"


def probe_workbook():
    """A workbook of awkward values, sent straight through create_spreadsheet."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Probe")
    ws.append(["Case", "Value", "Number"])
    ws.append(["formula", PROBE_FORMULA, 1])
    ws.append(["plus", PROBE_PLUS, 2.5])
    ws.append(["minus", PROBE_MINUS, -3])
    ws.append(["at", PROBE_AT, 0])
    ws.append(["cjk and accents", PROBE_CJK, 4])
    ws.append(["long", PROBE_LONG, 5])
    ws.append(["quote 'single' and \"double\"", 'it\'s "quoted"', 6])
    ws.append(["number-like text", "00123", 7])
    ws.append(["boolean-like text", "TRUE", 8])
    ws.append(["multi\nline", "line one\nline two", 9])
    ws.append(["not a number", float("nan"), 10])
    wb.create_sheet("Empty")
    ws3 = wb.create_sheet(PROBE_QUOTE_TITLE)
    ws3.append(["a", "b"])
    ws3.append([1, 2])
    return wb


PROBE_STRINGS = [
    PROBE_FORMULA,
    PROBE_PLUS,
    PROBE_MINUS,
    PROBE_AT,
    PROBE_CJK,
    PROBE_LONG,
    "00123",
    "TRUE",
]

LARGE_ROWS = 20000
LARGE_COLS = 10
LARGE_TEXT = 1000
LARGE_TABLE_ROWS = 300


def large_workbook():
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Large")
    ws.append([f"col{c}" for c in range(LARGE_COLS)])
    filler = "x" * LARGE_TEXT
    for r in range(LARGE_ROWS):
        row = [f"r{r}c{c}" for c in range(LARGE_COLS - 1)]
        row.append(f"{r}-{filler}")
        ws.append(row)
    return wb


def large_document():
    from docx import Document

    doc = Document()
    doc.add_heading("Large table", level=1)
    table = doc.add_table(rows=LARGE_TABLE_ROWS + 1, cols=4)
    for c in range(4):
        table.cell(0, c).text = f"H{c}"
    for r in range(1, LARGE_TABLE_ROWS + 1):
        for c in range(4):
            table.cell(r, c).text = f"row {r} col {c}"
    doc.add_heading("After the table", level=2)
    doc.add_paragraph("last paragraph")
    return doc


def verify_large_sheet(
    report: Report,
    services: Dict[str, Any],
    spreadsheet_id: str,
    stats: Stats,
    chunks: int,
) -> None:
    group = "large sheet"
    sheets = services["sheets"]
    props = read_sheet_properties(sheets, spreadsheet_id)
    grid = props[0].get("gridProperties", {}) if props else {}
    report.add(
        group,
        f"grid is {LARGE_ROWS + 1} x {LARGE_COLS}",
        (grid.get("rowCount"), grid.get("columnCount")) == (LARGE_ROWS + 1, LARGE_COLS),
        f"got {grid.get('rowCount')}x{grid.get('columnCount')}",
    )
    first_col = read_sheet_values(
        sheets, spreadsheet_id, "Large", f"A1:A{LARGE_ROWS + 1}"
    )
    want = ["col0"] + [f"r{r}c0" for r in range(LARGE_ROWS)]
    got = [row[0] if row else "" for row in first_col]
    report.add(
        group,
        "column A holds all 20,001 rows in order",
        got == want,
        f"got {len(got)} rows",
    )
    problems = []
    for r in (0, 1, LARGE_ROWS // 2, LARGE_ROWS):
        row = read_sheet_values(sheets, spreadsheet_id, "Large", f"A{r + 1}:J{r + 1}")
        got_row = row[0] if row else []
        if r == 0:
            want_row = [f"col{c}" for c in range(LARGE_COLS)]
        else:
            n = r - 1
            want_row = [f"r{n}c{c}" for c in range(LARGE_COLS - 1)] + [
                f"{n}-{'x' * LARGE_TEXT}"
            ]
        if got_row != want_row:
            problems.append(f"row {r + 1}")
    report.add(
        group,
        "sampled rows (first, second, middle, last) match",
        not problems,
        ", ".join(problems),
    )
    real_updates = stats.values_update_calls - stats.injected
    report.add(
        group,
        "rows were split into several requests",
        real_updates == chunks and chunks > 1,
        f"{real_updates} write requests, expected {chunks}",
    )
    report.add(
        group,
        "no request was larger than about 2 MB",
        stats.max_request_chars <= 2_000_000,
        f"largest {stats.max_request_chars:,} characters",
    )


# ----------------------------------------------------------------------------
# In-process InvenTag run against moto


def load_estate_helpers():
    path = ROOT / "scripts" / "docs" / "generate_example_outputs.py"
    spec = importlib.util.spec_from_file_location("inventag_estate", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["inventag_estate"] = module
    spec.loader.exec_module(module)
    return module


def seed_probe_resources(session) -> None:
    """Extra tagged buckets: formula-like, long and CJK tag values."""
    s3 = session.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="acme-probe")
    s3.put_bucket_tagging(
        Bucket="acme-probe",
        Tagging={
            "TagSet": [
                {"Key": "Owner", "Value": PROBE_FORMULA},
                {"Key": "Notes", "Value": "n" * 250},
                {"Key": "Team", "Value": PROBE_CJK},
                {"Key": "Env", "Value": PROBE_PLUS},
            ]
        },
    )


@dataclass
class CliRun:
    label: str
    argv: List[str]
    exit_code: int
    console: str
    output_dir: Path
    sheet_url: Optional[str] = None
    doc_url: Optional[str] = None

    def file(self, suffix: str) -> Optional[Path]:
        files = sorted(self.output_dir.glob(f"*{suffix}"))
        return files[0] if files else None


def run_inventag(label: str, argv: List[str], workdir: Path, helpers) -> CliRun:
    """Run the real CLI in this process; its console output is captured."""
    cli_main = importlib.import_module("inventag.cli.main")
    out_dir = workdir / "bom_output"
    out = io.StringIO()
    old_argv, old_cwd = sys.argv, os.getcwd()
    sys.argv = ["inventag", *argv, "--output-directory", str(out_dir)]
    os.chdir(workdir)
    code = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                cli_main.main()
            except SystemExit as stop:
                code = (
                    stop.code
                    if isinstance(stop.code, int)
                    else (0 if stop.code is None else 1)
                )
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
        import logging

        root = logging.getLogger()
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in list(logging.getLogger("inventag").handlers):
            logging.getLogger("inventag").removeHandler(handler)
        helpers.drop_guard()
    console = _redact(out.getvalue())
    run = CliRun(label, argv, code, console, out_dir)
    sheet = re.search(r"Google Sheet: (\S+)", console)
    doc = re.search(r"Google Doc: (\S+)", console)
    run.sheet_url = sheet.group(1) if sheet else None
    run.doc_url = doc.group(1) if doc else None
    return run


def credential_argv(args) -> List[str]:
    if args.google_credentials:
        return ["--google-credentials", args.google_credentials]
    if args.google_oauth_client:
        return ["--google-oauth-client", args.google_oauth_client]
    return []


def sign_in_name(args) -> str:
    if args.google_credentials:
        return "service account key (--google-credentials)"
    if args.google_oauth_client:
        return "your Google account (--google-oauth-client)"
    return "Application Default Credentials"


# ----------------------------------------------------------------------------
# One CLI scenario, verified


def verify_cli_run(
    report: Report,
    run: CliRun,
    services: Dict[str, Any],
    args,
    created: List[str],
    title: str,
    folder_id: Optional[str] = None,
) -> None:
    from docx import Document
    from openpyxl import load_workbook

    from inventag.reporting import google_output as go

    group = run.label
    report.add(
        group,
        "inventag exited with code 0",
        run.exit_code == 0,
        "" if run.exit_code == 0 else f"exit code {run.exit_code}",
    )
    if run.exit_code != 0:
        report.notes.append(
            f"[{group}] console tail:\n" + "\n".join(run.console.splitlines()[-12:])
        )
    report.add(
        group, "both Google URLs were printed", bool(run.sheet_url and run.doc_url)
    )
    xlsx, docx_path = run.file(".xlsx"), run.file(".docx")
    report.add(group, "local .xlsx and .docx were written", bool(xlsx and docx_path))
    if run.sheet_url:
        report.urls.append((f"{group} spreadsheet", run.sheet_url))
    if run.doc_url:
        report.urls.append((f"{group} document", run.doc_url))
    sid = file_id_from_url(run.sheet_url or "", "spreadsheets")
    did = file_id_from_url(run.doc_url or "", "document")
    created.extend(i for i in (sid, did) if i)

    if sid and xlsx:
        expected = go.workbook_to_sheets(load_workbook(xlsx))
        verify_file(
            report,
            f"{group} sheet",
            services,
            sid,
            run.sheet_url,
            "sheet",
            title,
            folder_id,
        )
        verify_spreadsheet(
            report,
            f"{group} sheet",
            services,
            sid,
            expected,
            probes=(
                [PROBE_FORMULA, PROBE_CJK, PROBE_PLUS]
                if run.label == "default layout"
                else ()
            ),
            optional_probes=[PROBE_FORMULA, PROBE_CJK, PROBE_PLUS],
        )
        verify_private(report, f"{group} sheet", services, sid, args.share_with)
    if did and docx_path:
        blocks = go.docx_to_blocks(Document(str(docx_path)))
        verify_file(
            report, f"{group} doc", services, did, run.doc_url, "doc", title, folder_id
        )
        verify_document(report, f"{group} doc", services, did, blocks)
        verify_private(report, f"{group} doc", services, did, args.share_with)


# ----------------------------------------------------------------------------
# Command line


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="google_live_test.py",
        description=(
            "Test InvenTag's Google Sheets and Docs output against real Google, "
            "using a fictional estate built with moto (no AWS account needed)."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sign = parser.add_argument_group("sign-in (pick one; with none, ADC is used)")
    sign.add_argument(
        "--google-credentials", metavar="KEY.JSON", help="service account key file"
    )
    sign.add_argument(
        "--google-oauth-client",
        metavar="CLIENT_SECRET.JSON",
        help="OAuth client file (Desktop app); a browser opens once",
    )
    parser.add_argument(
        "--share-with",
        action="append",
        default=[],
        metavar="EMAIL",
        help="share the files (reader) with this address and check that only they and the owner can open them; repeatable",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="leave the files in Drive (default: move them to the trash at the end)",
    )
    parser.add_argument(
        "--large",
        action="store_true",
        help=f"also test a {LARGE_ROWS:,}-row sheet and a {LARGE_TABLE_ROWS}-row Doc table; counts API calls, injects two 429 errors to prove the retry (adds about a minute)",
    )
    parser.add_argument(
        "--folder-id",
        metavar="ID",
        help="opt-in: also create a pair of files in this Drive folder. This needs the FULL Drive scope, so the sign-in must grant https://www.googleapis.com/auth/drive (with --google-oauth-client, delete ~/.config/inventag/google-token.json first so it asks again)",
    )
    return parser


def preflight(args) -> List[str]:
    """Problems that stop the run, found before any network call."""
    problems = []
    if args.google_credentials and args.google_oauth_client:
        problems.append("give --google-credentials or --google-oauth-client, not both")
    for flag, path in (
        ("--google-credentials", args.google_credentials),
        ("--google-oauth-client", args.google_oauth_client),
    ):
        if path and not os.path.isfile(path):
            problems.append(f"{flag}: file not found: {path}")
    missing = []
    for module in ("google.auth", "googleapiclient.discovery", "httplib2"):
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
    if args.google_oauth_client:
        try:
            importlib.import_module("google_auth_oauthlib.flow")
        except ImportError:
            missing.append("google_auth_oauthlib")
    if missing:
        problems.append(
            f"the Google libraries are not installed ({', '.join(missing)}). Install them with: {INSTALL}"
        )
    for module, hint in (
        ("moto", "pip install moto"),
        ("openpyxl", "pip install openpyxl"),
        ("docx", "pip install python-docx"),
        ("boto3", "pip install boto3"),
    ):
        try:
            importlib.import_module(module)
        except ImportError:
            problems.append(f"{module} is not installed. Install it with: {hint}")
    if (
        not (ROOT / "inventag").is_dir()
        or not (ROOT / "scripts" / "docs" / "generate_example_outputs.py").is_file()
    ):
        problems.append(
            "run this script from a checkout of the InvenTag repository (scripts/google_live_test.py)"
        )
    for email in args.share_with:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            problems.append(f"--share-with: not an email address: {email}")
    return problems


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    problems = preflight(args)
    if problems:
        print("Cannot start:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("Run with --help for the full list of prerequisites.", file=sys.stderr)
        return 2
    sys.path.insert(0, str(ROOT))
    return run_all(args)


def run_all(args) -> int:  # pragma: no cover - needs real Google
    import boto3
    import moto

    from inventag.reporting import google_output as go

    report = Report()
    created: List[str] = []
    started = time.time()
    stats = Stats()

    print(f"Sign-in: {sign_in_name(args)}")
    options = go.GoogleOptions(
        credentials_file=args.google_credentials,
        oauth_client_file=args.google_oauth_client,
        sheets=True,
        docs=True,
    )
    try:
        creds = go.load_credentials(options)
        services = counting_services(go.build_services(creds), stats)
    except Exception as e:
        print(f"Could not sign in: {describe_error(e)}", file=sys.stderr)
        return 2
    email = account_email(services["drive"])
    print(f"Account: {email}" if email else "Account: (Google did not return an email)")
    print("Scope: drive.file (files this test creates only)")
    if args.folder_id:
        print("Folder test requested: needs the full Drive scope (see --help)")
    print("Building the fictional estate with moto and running InvenTag ...")

    helpers = load_estate_helpers()
    helpers.fake_aws_environment()
    workdir_root = Path(tempfile.mkdtemp(prefix="inventag-google-live-"))
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    share_argv: List[str] = []
    for email_address in args.share_with:
        share_argv += ["--google-share-with", email_address]
    runs: List[Tuple[CliRun, str, Optional[str]]] = []
    try:
        with moto.mock_aws():
            helpers.drop_guard()
            session = boto3.Session()
            helpers.seed_account(session)
            seed_probe_resources(session)
            scenarios = [
                ("default layout", []),
                ("template standard-bom", ["--template", "standard-bom"]),
            ]
            if args.folder_id:
                scenarios.append(("folder", ["--google-folder-id", args.folder_id]))
            for label, extra in scenarios:
                work = workdir_root / re.sub(r"\W+", "-", label)
                work.mkdir()
                title = f"InvenTag live test {stamp} ({label})"
                cli_args = [
                    "--account-regions",
                    "us-east-1",
                    "--create-excel",
                    "--create-word",
                    "--create-google-sheets",
                    "--create-google-docs",
                    "--google-title",
                    title,
                    *credential_argv(args),
                    *share_argv,
                    *extra,
                ]
                runs.append(
                    (
                        run_inventag(label, cli_args, work, helpers),
                        title,
                        args.folder_id if label == "folder" else None,
                    )
                )
    except Exception as e:
        print(
            f"The InvenTag run failed before Google was reached: {describe_error(e)}",
            file=sys.stderr,
        )
        return 1

    try:
        for run, title, folder in runs:
            print(f"Reading back: {run.label} ...")
            try:
                verify_cli_run(report, run, services, args, created, title, folder)
            except Exception as e:
                report.add(run.label, "read-back finished", False, describe_error(e))

        print("Probe spreadsheet (awkward values) ...")
        try:
            wb = probe_workbook()
            probe_options = go.GoogleOptions(
                sheets=True,
                title=f"InvenTag live test {stamp} (probe)",
                share_with=list(args.share_with),
            )
            url = go.create_spreadsheet(services, wb, probe_options)
            report.urls.append(("probe spreadsheet", url))
            pid = file_id_from_url(url, "spreadsheets")
            if pid:
                created.append(pid)
                expected = go.workbook_to_sheets(wb)
                verify_file(report, "probe sheet", services, pid, url, "sheet")
                verify_spreadsheet(
                    report, "probe sheet", services, pid, expected, PROBE_STRINGS
                )
                verify_private(report, "probe sheet", services, pid, args.share_with)
        except Exception as e:
            report.add("probe sheet", "created and read back", False, describe_error(e))

        if args.large:
            run_large(report, services, go, args, created, stamp, stats)
    finally:
        if args.keep:
            print("--keep: the files stay in Drive.")
        else:
            problems = []
            for file_id in dict.fromkeys(created):
                err = trash(services["drive"], file_id)
                if err:
                    problems.append(f"{file_id}: {err}")
            if problems:
                print("Could not move to the trash:\n  " + "\n  ".join(problems))
            else:
                print(
                    f"Moved {len(set(created))} file(s) to the Drive trash (use --keep to leave them)."
                )

    print()
    print(report.render())
    for note in report.notes:
        print("\n" + note)
    print()
    for label, url in report.urls:
        print(f"{label}: {url}")
    print(
        f"\nTotal Google API calls: {stats.calls}, {time.time() - started:.0f} s elapsed"
    )
    if not report.passed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS")
    return 0


def run_large(
    report, services, go, args, created, stamp, stats
) -> None:  # pragma: no cover
    """A 20,000-row sheet and a 300-row Doc table; counts calls, injects 429."""
    from docx import Document  # noqa: F401

    print(
        f"Large sheet ({LARGE_ROWS:,} rows) and Doc ({LARGE_TABLE_ROWS}-row table) ..."
    )
    sleeps: List[float] = []
    real_sleep = go._sleep
    go._sleep = lambda seconds: (sleeps.append(seconds), real_sleep(seconds))[1]
    large_stats = Stats(inject_429=2)
    large_services = counting_services(
        {k: v._t for k, v in services.items()}, large_stats
    )
    try:
        wb = large_workbook()
        expected = go.workbook_to_sheets(wb)
        chunks = len(list(go._chunk_rows(expected[0]["rows"])))
        start = time.time()
        url = go.create_spreadsheet(
            large_services,
            wb,
            go.GoogleOptions(
                sheets=True,
                title=f"InvenTag live test {stamp} (large sheet)",
                share_with=list(args.share_with),
            ),
        )
        elapsed = time.time() - start
        report.urls.append(("large spreadsheet", url))
        sid = file_id_from_url(url, "spreadsheets")
        if sid:
            created.append(sid)
        report.add(
            "large sheet",
            "created despite two injected 429 errors",
            True,
            f"{large_stats.calls} calls in {elapsed:.0f} s, {chunks} write requests",
        )
        report.add(
            "large sheet",
            "429 was waited out and retried",
            large_stats.injected == 2 and len(sleeps) >= 2,
            f"injected {large_stats.injected}, waits {sleeps}",
        )
        if sid:
            verify_large_sheet(report, large_services, sid, large_stats, chunks)
    except Exception as e:
        report.add("large sheet", "created and read back", False, describe_error(e))
    doc_stats = Stats()
    try:
        doc = large_document()
        blocks = go.docx_to_blocks(doc)
        requests = len(go.blocks_to_doc_requests(blocks))
        batches = -(-requests // go.DOC_REQUESTS_PER_BATCH)
        doc_services = counting_services(
            {k: v._t for k, v in services.items()}, doc_stats
        )
        start = time.time()
        url = go.create_document(
            doc_services,
            doc,
            go.GoogleOptions(
                docs=True,
                title=f"InvenTag live test {stamp} (large doc)",
                share_with=list(args.share_with),
            ),
        )
        elapsed = time.time() - start
        report.urls.append(("large document", url))
        did = file_id_from_url(url, "document")
        if did:
            created.append(did)
        batch_calls = doc_stats.by_method.get("docs.documents.batchUpdate", 0)
        report.add(
            "large doc",
            "request list was split into batches",
            batch_calls == batches and batches > 1,
            f"{requests} requests, {batch_calls} batchUpdate calls, {elapsed:.0f} s",
        )
        if did:
            verify_document(report, "large doc", services, did, blocks)
    except Exception as e:
        report.add("large doc", "created and read back", False, describe_error(e))
    finally:
        go._sleep = real_sleep
        stats.calls += large_stats.calls + doc_stats.calls


if __name__ == "__main__":
    sys.exit(main())
