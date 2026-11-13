"""Error types for InvenTag templates.

Every problem found while loading or validating a template is reported as a
:class:`TemplateIssue`, which knows the file, the line (when known) and the
dotted path of the field. A :class:`TemplateError` carries one or more issues.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class TemplateIssue:
    """One problem in a template file."""

    message: str
    source: Optional[str] = None  # file path, or "builtin:<name>"
    line: Optional[int] = None  # 1-based line number, when known
    field: Optional[str] = None  # dotted path, e.g. "spec.excel.layout"

    def __str__(self) -> str:
        location = self.source or ""
        if self.line and location:
            location = f"{location}:{self.line}"
        parts = [p for p in (location, self.field, self.message) if p]
        return ": ".join(parts)


class TemplateError(Exception):
    """Raised when a template cannot be found, loaded or validated."""

    def __init__(self, issues: Iterable[TemplateIssue] | str):
        if isinstance(issues, str):
            issues = [TemplateIssue(issues)]
        self.issues: List[TemplateIssue] = list(issues)
        super().__init__("\n".join(str(i) for i in self.issues))


class TemplateNotFoundError(TemplateError):
    """Raised when a template name or path does not resolve to a file."""
