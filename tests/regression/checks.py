"""Checks a scenario row can make. A check is a tuple, ``(name, argument...)``.

``evaluate(check, outcome)`` returns ``None`` when the check holds, else a short
sentence that says what was missing (it ends up in the assertion message).
"""

import glob
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from openpyxl import load_workbook


@dataclass
class RunOutcome:
    """What one run of the CLI left behind."""

    code: Any
    stdout: str
    stderr: str
    out_dir: Path
    calls: List[dict] = field(default_factory=list)
    wall_seconds: float = 0.0
    seconds_after_summary: Optional[float] = None
    earlier: List["RunOutcome"] = field(default_factory=list)

    @property
    def text(self) -> str:
        return self.stdout + "\n" + self.stderr

    def message_lines(self) -> List[str]:
        """Log lines without timestamp and logger name, each message once.

        The CLI prints every log record twice (once with the logger name), so
        a count of lines would otherwise be doubled.
        """
        seen, lines = set(), []
        for raw in self.text.replace("\r", "\n").splitlines():
            if not raw.strip():
                continue
            msg = re.sub(r"^.*? - (INFO|WARNING|ERROR|DEBUG) - ", "", raw)
            if msg not in seen:
                seen.add(msg)
                lines.append(msg)
        return lines

    def files(self, *patterns) -> List[Path]:
        found = []
        for pattern in patterns:
            found += [Path(p) for p in glob.glob(str(self.out_dir / pattern))]
        return sorted(found, key=os.path.getmtime)

    def reports(self) -> List[Path]:
        return self.files("*.xlsx", "*.docx")


def _workbook_cells(path: Path):
    wb = load_workbook(path, read_only=True)
    try:
        for name in wb.sheetnames:
            for row in wb[name].iter_rows(values_only=True):
                yield name, row
    finally:
        wb.close()


def _newest_workbook(outcome):
    books = outcome.files("*.xlsx")
    return books[-1] if books else None


def _snapshot_resource_counts(outcome) -> List[int]:
    counts = []
    for path in outcome.files("state/state_*.json"):
        counts.append(len(json.loads(path.read_text()).get("resources") or []))
    return counts


def run_summary(outcome):
    path = outcome.out_dir / "run_summary.json"
    return json.loads(path.read_text()) if path.is_file() else None


def evaluate(check: tuple, o: RunOutcome) -> Optional[str]:
    name, args = check[0], check[1:]
    if name == "code":
        return None if o.code == args[0] else f"exit code {o.code!r}, wanted {args[0]}"
    if name == "code_nonzero":
        return None if o.code not in (0, None) else "exit code 0, wanted non-zero"
    if name == "out":
        return None if args[0] in o.text else f"output does not contain {args[0]!r}"
    if name == "no_out":
        return None if args[0] not in o.text else f"output contains {args[0]!r}"
    if name == "out_regex":
        return None if re.search(args[0], o.text) else f"output does not match /{args[0]}/"
    if name == "report":
        have = bool(o.reports())
        return None if have == args[0] else f"report file {'exists' if have else 'does not exist'}"
    if name == "report_text":
        book = _newest_workbook(o)
        if book is None:
            return "no workbook to read"
        needle = args[0].lower()
        for _, row in _workbook_cells(book):
            if any(isinstance(v, str) and needle in v.lower() for v in row):
                return None
        return f"the workbook never says {args[0]!r}"
    if name == "rows":
        book = _newest_workbook(o)
        if book is None:
            return "no workbook to read"
        wb = load_workbook(book, read_only=True)
        try:
            if args[0] not in wb.sheetnames:
                return f"no sheet {args[0]}"
            n = sum(1 for _ in wb[args[0]].iter_rows(values_only=True)) - 1
        finally:
            wb.close()
        return None if n == args[1] else f"sheet {args[0]} has {n} rows, wanted {args[1]}"
    if name in ("row", "no_row"):
        book = _newest_workbook(o)
        if book is None:
            return "no workbook to read" if name == "row" else None
        found = any(args[0] in row for _, row in _workbook_cells(book))
        if name == "row":
            return None if found else f"no row named {args[0]!r}"
        return None if not found else f"a row named {args[0]!r} is in the report"
    if name == "ce_calls":
        n = sum(1 for c in o.calls if c["service"] == "ce")
        return None if n == args[0] else f"{n} Cost Explorer calls, wanted {args[0]}"
    if name == "snapshot_zero":
        counts = _snapshot_resource_counts(o)
        has_zero = any(c == 0 for c in counts)
        return None if has_zero == args[0] else (
            "a snapshot with 0 resources was saved" if has_zero else "no snapshot with 0 resources"
        )
    if name == "log_file":
        path = o.out_dir / "inventag.log"
        if not path.is_file():
            return "no log file"
        return None if args[0] in path.read_text() else f"{args[0]!r} is not in the log file"
    if name == "lines_with":
        n = sum(1 for line in o.message_lines() if args[0] in line)
        return None if n == args[1] else f"{n} lines mention {args[0]!r}, wanted {args[1]}"
    if name == "summary":
        data = run_summary(o)
        if data is None:
            return "no run_summary.json"
        return None if data.get(args[0]) == args[1] else f"run_summary {args[0]} is {data.get(args[0])!r}"
    if name == "summary_has_cause":
        text = o.text
        marker = "Account-specific errors:"
        if marker not in text:
            return "no account error summary"
        return None if args[0] in text.split(marker, 1)[1] else (
            f"the account summary does not give the cause ({args[0]})"
        )
    if name == "exit_within_after_summary":
        if o.seconds_after_summary is None:
            return "no summary line found"
        return None if o.seconds_after_summary <= args[0] else (
            f"the process ended {o.seconds_after_summary:.0f} s after the summary, wanted {args[0]}"
        )
    if name == "issue":
        data = run_summary(o)
        if data is None:
            return "no run_summary.json (issue keys are read from it)"
        keys = set()
        for issue in data.get("issues", []):
            keys.add(issue["category"])
            if issue.get("service"):
                keys.add(f"{issue['category']}:{issue['service']}")
        return None if args[0] in keys else f"issue {args[0]} is not in run_summary.json"
    raise ValueError(f"unknown check {name!r}")


def failures(checks, outcome) -> List[str]:
    return [msg for msg in (evaluate(c, outcome) for c in checks) if msg]
