"""A run without the v1.5.0 flags gives what v1.4.3 gave (plan section 3, P6 row).

``fingerprint()`` runs the CLI in-process on the FinOps moto estate, once per
scenario, and reduces each run to what a reader sees: the exit code, the
files written (names without the timestamp), every cell of each workbook,
every paragraph and table cell of each Word document, the JSON outputs, and
the console lines at WARNING or above. Values that change from run to run
(timestamps, durations, the IDs moto makes) are replaced by placeholders.

The golden ``golden/v143_default_runs.json`` was made by running this module
against the v1.4.3 sources (``git archive v1.4.3``)::

    env MOTO_EC2_LOAD_DEFAULT_AMIS=false AWS_EC2_METADATA_DISABLED=true \\
        AWS_ACCESS_KEY_ID=testing AWS_SECRET_ACCESS_KEY=testing \\
        python tests/regression/v143_equality.py --write <v1.4.3 source folder>

The module needs only what v1.4.3 already had (``inventag.cli.main``,
``tests.unit.finops``), so the same file runs on both versions.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

GOLDEN = Path(__file__).resolve().parent / "golden" / "v143_default_runs.json"

# scenario name -> extra CLI arguments (none of them new in v1.5.0)
SCENARIOS = {
    "default": [],
    "word-and-excel": ["--create-word", "--create-excel"],
    "template": ["--template", "standard-bom"],
    "finops-checks": ["--finops-checks"],
    "tag-policy-template": ["--template", "finops-cost-allocation"],
}

_RULES = [
    (
        re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
        "UUID",
    ),
    (re.compile(r"\b[0-9a-f]{2}(:[0-9a-f]{2}){5}\b"), "MAC"),
    (re.compile(r"datetime\.datetime\([^)]*\)\)?"), "DATETIME"),
    (re.compile(r"\b\d{1,3}([.-])\d{1,3}\1\d{1,3}\1\d{1,3}\b"), "IP"),
    # moto's random IDs and hashes
    (re.compile(r"\b(ami|[a-z]{1,10})-[0-9a-z]{8,17}\b"), r"\1-ID"),
    (re.compile(r"/[0-9a-f]{16}\b"), "/HASH"),
    # times and durations
    (re.compile(r"\d{8}_\d{6}"), "STAMP"),
    (
        re.compile(
            r"\d{4}-\d\d-\d\d([ T]\d\d:\d\d(:\d\d(\.\d+)?)?)?"
            r"( ?(UTC|Z|[+-]\d\d:?\d\d))?"
        ),
        "TIME",
    ),
    (re.compile(r"\b\d+(\.\d+)? ?(s|sec|seconds|ms)\b"), "DURATION"),
    (re.compile(r"\b\d+\.\d{2,}\b"), "N.N"),
    # the temporary folder of the run
    (re.compile(r"(/[^\s'\"]*)?/run-out\b"), "OUT"),
    (re.compile(r"(/[^\s'\"]*)?/audit\.json\b"), "AUDIT"),
]
_CONSOLE_PREFIX = re.compile(r"^TIME,\d+ - [\w.]+ - (\w+) - ")
# lines that name the version or the run's own process
_VOLATILE = (
    "InvenTag v",
    "version",
    "Processing time",
    "Duration",
    "took",
)


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        for pattern, repl in _RULES:
            value = pattern.sub(repl, value)
        return value
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, dict):
        return {_clean(k): _clean(v) for k, v in sorted(value.items(), key=str)}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if value is None or isinstance(value, (bool, int)):
        return value
    return _clean(str(value))


def _workbook(path: Path) -> Dict[str, Any]:
    from openpyxl import load_workbook

    book = load_workbook(path)
    sheets = {}
    for ws in book.worksheets:
        rows = [
            [_clean(c) for c in row]
            for row in ws.iter_rows(values_only=True)
            if any(c is not None for c in row)
        ]
        sheets[ws.title] = _digest(rows[:1], rows[1:])
    return sheets


def _digest(head: List[Any], rows: List[Any]) -> Dict[str, Any]:
    """The first rows in full; the rest as a count and a hash, in sorted order
    (moto lists its public images in no fixed order)."""
    body = sorted(json.dumps(r, sort_keys=True) for r in rows)
    found = {
        "head": head,
        "rows": len(body),
        "sha256": hashlib.sha256("\n".join(body).encode()).hexdigest(),
    }
    if os.environ.get("INVENTAG_EQUALITY_FULL"):  # to see what differs
        found["body"] = body
    return found


def _document(path: Path) -> Dict[str, Any]:
    from docx import Document

    doc = Document(path)
    return {
        "paragraphs": [_clean(p.text) for p in doc.paragraphs if p.text.strip()],
        "tables": [
            _digest(rows[:1], rows[1:])
            for rows in (
                [[_clean(c.text) for c in row.cells] for row in table.rows]
                for table in doc.tables
            )
        ],
    }


def _json(path: Path) -> Any:
    try:
        data = _clean(json.loads(path.read_text()))
    except ValueError:
        return "not JSON"
    text = json.dumps(data, sort_keys=True)
    if len(text) < 4000:
        return data
    return {
        "keys": sorted(data) if isinstance(data, dict) else "list",
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _console(text: str) -> List[str]:
    lines = []
    for raw in text.splitlines():
        line = _clean(raw)
        found = _CONSOLE_PREFIX.match(line)
        if found:
            if found.group(1) not in ("WARNING", "ERROR", "CRITICAL"):
                continue
            line = f"{found.group(1)}: {line[found.end():]}"
        if not line.strip() or any(word in raw for word in _VOLATILE):
            continue
        if any(0x2800 <= ord(ch) <= 0x28FF for ch in raw):  # progress spinner
            continue
        lines.append(line)
    return lines


def _files(out: Path) -> Dict[str, Any]:
    found: Dict[str, Any] = {}
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        name = _clean(str(path.relative_to(out)))
        if path.suffix == ".xlsx":
            found[name] = _workbook(path)
        elif path.suffix == ".docx":
            found[name] = _document(path)
        elif path.suffix == ".json" and not name.startswith("state"):
            found[name] = _json(path)
        else:
            found[name] = "present"
    return found


def fingerprint() -> Dict[str, Any]:
    """Every scenario on one moto estate (seeded once)."""
    from moto import mock_aws

    from tests.unit.finops import estate
    from tests.unit.finops.conftest import _run_main

    result: Dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp, mock_aws():
        ids = estate.seed()
        for name, extra in SCENARIOS.items():
            where = Path(tmp) / name
            where.mkdir()
            scan = _run_main(where / "run-out", where / "audit.json", extra, False, ids)
            result[name] = {
                "exit_code": scan.code,
                "files": _files(where / "run-out"),
                "console": _console(scan.text),
            }
    return result


def main(argv: List[str]) -> int:
    if len(argv) != 2 or argv[0] != "--write":
        print("usage: v143_equality.py --write <v1.4.3 source folder>", file=sys.stderr)
        return 2
    source = Path(argv[1]).resolve()
    sys.path.insert(0, str(source))
    # the environment of a pytest run (tests/conftest.py) is set on the
    # command line, as the module docstring shows; it is not written here
    import inventag

    if not Path(inventag.__file__).resolve().is_relative_to(source):
        print(f"inventag is not taken from {source}", file=sys.stderr)
        return 1
    GOLDEN.write_text(json.dumps(fingerprint(), indent=1, sort_keys=True) + "\n")
    print(f"Wrote {GOLDEN}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
