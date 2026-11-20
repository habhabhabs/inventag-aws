"""Compare what two runs wrote: bytes for text files, cells for Excel, text for Word.

The rule of plan 2.4: the same AWS answers and a fixed clock give the same
files, whatever ``--concurrency``, ``--max-concurrent-accounts``, thread timing
or hash seed. ``describe_difference`` returns ``None`` when two runs agree, else
one sentence that says where they differ (so a failing test names the file, the
sheet and the cell).
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from openpyxl import load_workbook


def workbook(path: Path) -> Dict[str, List[list]]:
    """Sheet name -> rows of cell values, in workbook order."""
    book = load_workbook(str(path), data_only=False)
    try:
        return {
            sheet.title: [list(row) for row in sheet.iter_rows(values_only=True)]
            for sheet in book.worksheets
        }
    finally:
        book.close()


def document(path: Path) -> List[str]:
    """Paragraph text and table cell text of a Word file, in document order."""
    from docx import Document

    doc = Document(str(path))
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            lines.append("\t".join(cell.text for cell in row.cells))
    return lines


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def tree(root: Path) -> Dict[str, Path]:
    return {str(p.relative_to(root)): p for p in sorted(root.rglob("*")) if p.is_file()}


# Known on v1.3.0 (measured, see tests/regression/test_serial_order_pin.py): the key
# order of ``coverage_summary`` in the snapshot follows the order in which the
# listings of an account ended. Work order A4 sorts the ledger. Rows that do not
# test the ledger pass ``sorted_dicts=LEDGER_ORDER`` so that they test what they say.
LEDGER_ORDER = ("coverage_summary",)


def _sort_named(value, names):
    """Sort the keys of every dict that is the value of a key in ``names``."""
    if isinstance(value, dict):
        return {
            k: (
                dict(sorted(_sort_named(v, names).items()))
                if k in names and isinstance(v, dict)
                else _sort_named(v, names)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sort_named(v, names) for v in value]
    return value


def describe_difference(a: Path, b: Path, sorted_dicts=()) -> Optional[str]:
    """Where the files under folder ``a`` and folder ``b`` differ; ``None`` if equal.

    ``sorted_dicts``: names of JSON keys whose dict value is compared with its keys
    sorted (``LEDGER_ORDER``)."""
    left, right = tree(a), tree(b)
    if sorted(left) != sorted(right):
        return f"different files: {sorted(set(left) ^ set(right))}"
    for name in sorted(left):
        one, two = left[name], right[name]
        if one.suffix == ".xlsx":
            found = _sheets_differ(name, workbook(one), workbook(two))
        elif one.suffix == ".docx":
            found = _lines_differ(name, document(one), document(two))
        else:
            found = _bytes_differ(name, one, two, a, b, sorted_dicts)
        if found:
            return found
    return None


def _read(path: Path, root: Path) -> bytes:
    """The bytes of a file, with the run's own folder name replaced: some files
    (``state/metadata.json``) name the folder they were written to."""
    return path.read_bytes().replace(str(root).encode(), b"<run folder>")


def _bytes_differ(name, one, two, a, b, sorted_dicts=()) -> Optional[str]:
    if _read(one, a) == _read(two, b):
        return None
    if one.suffix == ".json":
        try:
            first = json.loads(_read(one, a))
            second = json.loads(_read(two, b))
        except ValueError:
            return f"{name}: bytes differ"
        if sorted_dicts:
            first = _sort_named(first, sorted_dicts)
            second = _sort_named(second, sorted_dicts)
            if json.dumps(first) == json.dumps(second):
                return None
        where = _first_json_difference(first, second, "$")
        return f"{name}: bytes differ; first difference at {where}"
    return f"{name}: bytes differ ({_digest(one)} against {_digest(two)})"


def _first_json_difference(a, b, path: str) -> str:
    if type(a) is not type(b):
        return path
    if isinstance(a, dict):
        if list(a) != list(b):
            return f"{path} (keys or key order)"
        for key in a:
            found = _first_json_difference(a[key], b[key], f"{path}.{key}")
            if found:
                return found
        return ""
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path} (length {len(a)} against {len(b)})"
        for index, (x, y) in enumerate(zip(a, b)):
            found = _first_json_difference(x, y, f"{path}[{index}]")
            if found:
                return found
        return ""
    return "" if a == b else path


def _sheets_differ(name, a: Dict[str, List[list]], b: Dict[str, List[list]]):
    if list(a) != list(b):
        return f"{name}: sheets {list(a)} against {list(b)}"
    for sheet in a:
        rows_a, rows_b = a[sheet], b[sheet]
        if len(rows_a) != len(rows_b):
            return f"{name}/{sheet}: {len(rows_a)} rows against {len(rows_b)}"
        for number, (x, y) in enumerate(zip(rows_a, rows_b), start=1):
            if x != y:
                for column, (c, d) in enumerate(zip(x, y), start=1):
                    if c != d:
                        return f"{name}/{sheet}: row {number} column {column}: {c!r} against {d!r}"
                return (
                    f"{name}/{sheet}: row {number} has {len(x)} cells against {len(y)}"
                )
    return None


def _lines_differ(name, a: List[str], b: List[str]):
    if a == b:
        return None
    for number, (x, y) in enumerate(zip(a, b), start=1):
        if x != y:
            return f"{name}: line {number}: {x!r} against {y!r}"
    return f"{name}: {len(a)} lines against {len(b)}"


def resource_rows(path: Path) -> List[tuple]:
    """(sheet, service, type, id, region, account) of every resource row of a
    workbook, in the order the workbook lists them. Sheets that are not service
    sheets (summary, notes) are left out."""
    rows: List[tuple] = []
    for sheet, content in workbook(path).items():
        if not content or not sheet.isupper():
            continue
        header = [str(c) for c in content[0]]
        if "service" not in header or "type" not in header:
            continue
        index = {name: header.index(name) for name in header}
        for row in content[1:]:

            def cell(name):
                return row[index[name]] if name in index else None

            rows.append(
                (
                    sheet,
                    cell("service"),
                    cell("type"),
                    cell("id"),
                    cell("region"),
                    cell("account_id"),
                )
            )
    return rows
