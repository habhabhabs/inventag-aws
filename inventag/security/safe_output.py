"""
Safe output helpers: private file permissions, safe file names, and
spreadsheet (CSV/Excel) formula-injection neutralisation.

Reports, state snapshots and credential files contain account IDs, ARNs, IP
ranges and sometimes secrets, so InvenTag writes them owner-only (0600) and
creates its own directories owner-only (0700).

Resource names and tag values come from the AWS accounts being scanned, so
they are untrusted. They must not be able to:

* escape the output directory when used in a file name (``../../x``), or
* run as a formula when a report is opened in a spreadsheet application
  (``=HYPERLINK(...)``, ``+cmd|' /C calc'!A0``, ``@SUM(...)``).
"""

import os
import re
from pathlib import Path
from typing import Any, Iterable, Union

PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700

PathLike = Union[str, "os.PathLike[str]"]

# Leading characters that make spreadsheet applications treat a cell as a
# formula (OWASP "CSV Injection"), plus their full-width forms.
FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")


# --------------------------------------------------------------- permissions
def _chmod_quietly(path_or_fd, mode: int) -> None:
    try:
        if isinstance(path_or_fd, int):
            if hasattr(os, "fchmod"):
                os.fchmod(path_or_fd, mode)
        else:
            os.chmod(path_or_fd, mode)
    except (OSError, NotImplementedError):  # pragma: no cover - e.g. some network FS
        pass


def ensure_private_dir(path: PathLike) -> Path:
    """Create ``path`` (and parents) if missing; new directories get 0700.

    Existing directories are left alone: InvenTag never tightens permissions on
    a directory it did not create (it may be the user's working directory).
    """
    path = Path(path)
    missing = []
    current = path
    while not current.exists() and current != current.parent:
        missing.append(current)
        current = current.parent
    path.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIR_MODE)
    for created in missing:
        _chmod_quietly(created, PRIVATE_DIR_MODE)
    return path


def open_private(path: PathLike, mode: str = "w", **kwargs):
    """Open ``path`` for writing with owner-only permissions (0600).

    The file is created 0600 atomically (no window where it is world-readable)
    and an existing file is reset to 0600. Symlinks are not followed where the
    platform supports it, so a planted link cannot redirect the write.
    """
    if not any(flag in mode for flag in ("w", "a", "x")):
        raise ValueError("open_private is for writing; use open() to read")
    flags = os.O_WRONLY | os.O_CREAT
    if "a" in mode:
        flags |= os.O_APPEND
    elif "x" in mode:
        flags |= os.O_EXCL
    else:
        flags |= os.O_TRUNC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_BINARY", 0) if "b" in mode else 0
    fd = os.open(os.fspath(path), flags, PRIVATE_FILE_MODE)
    try:
        _chmod_quietly(fd, PRIVATE_FILE_MODE)
        return os.fdopen(fd, mode, **kwargs)
    except Exception:
        os.close(fd)
        raise


def precreate_private(path: PathLike) -> Path:
    """Create/truncate ``path`` as an empty 0600 file.

    Libraries such as openpyxl and python-docx open the destination with
    ``open(path, "wb")``, which keeps the mode of an existing file, so
    pre-creating it makes their output private too.
    """
    with open_private(path, "wb"):
        pass
    return Path(path)


def make_private(path: PathLike) -> None:
    """Set an existing file to 0600 (best effort)."""
    _chmod_quietly(os.fspath(path), PRIVATE_FILE_MODE)


# --------------------------------------------------------------- file names
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename_component(
    value: Any, max_length: int = 100, default: str = "unnamed"
) -> str:
    """Turn untrusted text (resource name, account name, tag) into a safe file name part.

    Only ``[A-Za-z0-9._-]`` survive; path separators, ``..``, NUL and control
    characters cannot. Leading dots are removed so the result is never hidden
    or a relative path component.
    """
    text = "" if value is None else str(value)
    text = _UNSAFE_FILENAME_CHARS.sub("_", text)
    text = re.sub(r"\.{2,}", "_", text)
    text = text.strip("._-")
    text = text[:max_length].rstrip("._-")
    return text or default


def safe_join(base: PathLike, *parts: str) -> Path:
    """Join ``parts`` under ``base`` and refuse anything that escapes it."""
    base_path = Path(base).resolve()
    candidate = base_path.joinpath(*parts).resolve()
    if candidate != base_path and base_path not in candidate.parents:
        raise ValueError(f"Refusing to write outside {base_path}: {candidate}")
    return candidate


# ----------------------------------------------------- formula neutralising
def neutralize_csv_value(value: Any) -> Any:
    """Prefix a string that a spreadsheet would treat as a formula with ``'``.

    Non-string values (numbers, booleans, None) are returned unchanged, so
    real numbers stay numeric.
    """
    if isinstance(value, str) and value.startswith(FORMULA_TRIGGER_CHARS):
        return "'" + value
    return value


def neutralize_csv_row(row: dict) -> dict:
    return {key: neutralize_csv_value(val) for key, val in row.items()}


def neutralize_csv_sequence(values: Iterable[Any]) -> list:
    return [neutralize_csv_value(v) for v in values]


def neutralize_workbook_formulas(workbook) -> int:
    """Turn every formula cell of an openpyxl workbook into a literal string.

    openpyxl stores any string starting with ``=`` as a formula. InvenTag never
    writes intentional formulas, so every formula cell comes from discovered
    data (resource names, tags ...). Storing it as a string keeps the text
    exactly as discovered but means Excel/LibreOffice display it instead of
    evaluating it. Strings starting with ``+``, ``-`` or ``@`` are already
    stored as strings in .xlsx files and are not evaluated on open.

    Returns the number of cells changed.
    """
    changed = 0
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"
                    changed += 1
    return changed


def write_safe_csv(fileobj, headers: Iterable[str], rows: Iterable[dict]) -> None:
    """Write dict rows as CSV with header and every value formula-neutralised.

    Equivalent to ``csv.DictWriter(...).writeheader(); writerow(...)`` with
    ``restval=""``, but tag keys used as column headers are neutralised too.
    """
    import csv

    headers = list(headers)
    writer = csv.writer(fileobj)
    writer.writerow(neutralize_csv_sequence(headers))
    for row in rows:
        writer.writerow([neutralize_csv_value(row.get(h, "")) for h in headers])
