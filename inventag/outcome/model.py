"""Data model of a run's outcome: categories, issues and outcome dataclasses.

Pure data and pure helpers. This module imports only the standard library, so
every layer (discovery, core, reporting, the CLI) can import it without a
cycle.

* :class:`Category` is the closed set of 14 reasons why something was not
  read or written. A test pins the set; adding one is a deliberate change.
* :class:`Issue` is one thing that went wrong, merged over regions and
  repeated calls by :class:`IssueLog`.
* :class:`ServiceOutcome`, :class:`RegionOutcome`, :class:`AccountOutcome`,
  :class:`OutputOutcome` and :class:`RunOutcome` hold the state of each level
  (complete, partial, skipped, failed). They are computed by
  :mod:`inventag.outcome.reduce`, never by the code that met the error.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple


class Category(str, Enum):
    """Why a unit was not read, or an output not written. Closed set."""

    CREDENTIALS = "credentials"
    PERMISSION_DENIED = "permission_denied"
    NOT_ENABLED = "not_enabled"
    NOT_AVAILABLE = "not_available"
    NOT_FOUND = "not_found"
    THROTTLED = "throttled"
    TIMEOUT = "timeout"
    NETWORK = "network"
    SERVICE_ERROR = "service_error"
    GUARD_BLOCK = "guard_block"
    INVALID_INPUT = "invalid_input"
    OUTPUT_FAILURE = "output_failure"
    CANCELLED = "cancelled"
    INTERNAL_ERROR = "internal_error"


class Scope(str, Enum):
    RUN = "run"
    ACCOUNT = "account"
    REGION = "region"
    SERVICE = "service"
    RESOURCE = "resource"
    OUTPUT = "output"


class State(str, Enum):
    COMPLETE = "complete"  # everything asked for was read
    PARTIAL = "partial"  # some data kept, some may be missing
    SKIPPED = "skipped"  # nothing read and nothing expected to be missing
    FAILED = "failed"  # nothing read; resources may exist


ERROR = "error"
WARNING = "warning"
INFO = "info"
SEVERITY_RANK = {ERROR: 2, WARNING: 1, INFO: 0}

#: Steps of a run. The same AWS code can mean different things per step.
PHASES = (
    "credentials",
    "assume_role",
    "region_check",
    "listing",
    "tagging",
    "detail",
    "billing",
    "pricing",
    "report",
    "upload",
    "state",
)

#: A unit that ended this way and read nothing is not missing anything.
BENIGN = frozenset({Category.NOT_ENABLED, Category.NOT_AVAILABLE})

#: Default severity per category, before the scope rule of :func:`severity_of`.
DEFAULT_SEVERITY: Dict[Category, str] = {
    Category.CREDENTIALS: ERROR,
    Category.PERMISSION_DENIED: WARNING,
    Category.NOT_ENABLED: INFO,
    Category.NOT_AVAILABLE: INFO,
    Category.NOT_FOUND: INFO,
    Category.THROTTLED: WARNING,
    Category.TIMEOUT: WARNING,
    Category.NETWORK: WARNING,
    Category.SERVICE_ERROR: WARNING,
    Category.GUARD_BLOCK: ERROR,
    Category.INVALID_INPUT: ERROR,
    Category.OUTPUT_FAILURE: ERROR,
    Category.CANCELLED: INFO,
    Category.INTERNAL_ERROR: ERROR,
}

#: Running the same command again may succeed.
RETRYABLE = frozenset(
    {
        Category.THROTTLED,
        Category.TIMEOUT,
        Category.NETWORK,
        Category.SERVICE_ERROR,
        Category.CANCELLED,
    }
)

_CATEGORY_ORDER = {c: i for i, c in enumerate(Category)}
_MAX_EXAMPLES = 3


def severity_of(scope: Scope, category: Category) -> str:
    """Severity of an issue: the category's default, adjusted by scope.

    Run, output and account scope are always ``error``; region scope is at
    least ``warning`` (a region that was not scanned is always shown);
    resource scope is at most ``warning``, except ``guard_block``.
    """
    scope = Scope(scope)
    category = Category(category)
    default = DEFAULT_SEVERITY[category]
    if scope in (Scope.RUN, Scope.OUTPUT, Scope.ACCOUNT):
        return ERROR
    if scope is Scope.REGION and default == INFO:
        return WARNING
    if (
        scope is Scope.RESOURCE
        and default == ERROR
        and category is not Category.GUARD_BLOCK
    ):
        return WARNING
    return default


def worst_category(categories: Iterable[Optional[Category]]) -> Optional[Category]:
    """The most serious category (highest default severity, then table order)."""
    best = None
    for c in categories:
        if c is None:
            continue
        c = Category(c)
        if best is None or _category_sort_key(c) < _category_sort_key(best):
            best = c
    return best


def _category_sort_key(c: Category) -> Tuple[int, int]:
    return (-SEVERITY_RANK[DEFAULT_SEVERITY[c]], _CATEGORY_ORDER[c])


@dataclass(frozen=True)
class Issue:
    """One thing that went wrong. Never holds ``str(exc)`` (secrets)."""

    scope: Scope
    category: Category
    account: str = ""  # 12-digit ID, "" at run scope
    region: str = ""  # region code or "global"; "" after a merge over regions
    service: str = ""  # discovery service key; for scope=output the output name
    operation: str = ""  # AWS API name or output step
    code: str = ""  # AWS error code or exception class name
    phase: str = ""
    message: str = ""  # filled by the wording table, after merging
    next_step: str = ""  # printed as "Instead: ..."
    more: str = ""  # one docs URL, printed as "More: ..."
    aws_message: str = ""  # AWS's own text: cleaned, redacted, cut to 300
    retryable: bool = False
    count: int = 1  # occurrences merged into this issue
    regions: Tuple[str, ...] = ()  # all regions merged into this issue
    examples: Tuple[str, ...] = ()  # up to 3 resource IDs (scope=resource)

    def __post_init__(self):
        object.__setattr__(self, "scope", Scope(self.scope))
        object.__setattr__(self, "category", Category(self.category))
        if self.region and not self.regions:
            object.__setattr__(self, "regions", (self.region,))
        object.__setattr__(self, "regions", tuple(sorted(set(self.regions))))
        object.__setattr__(self, "examples", tuple(self.examples)[:_MAX_EXAMPLES])

    @property
    def severity(self) -> str:
        return severity_of(self.scope, self.category)

    @property
    def key(self) -> Tuple[str, str, str, str, str, str]:
        """De-duplication key. Region is not in it: regions are merged."""
        return (
            self.scope.value,
            self.category.value,
            self.account,
            self.service,
            self.operation,
            self.code,
        )

    def merged_with(self, other: "Issue") -> "Issue":
        """This issue with ``other`` (same key) folded in."""
        if other.key != self.key:
            raise ValueError("issues with different keys cannot be merged")
        examples = list(self.examples)
        for e in other.examples:
            if e not in examples:
                examples.append(e)
        return replace(
            self,
            region=self.region if self.region == other.region else "",
            regions=tuple(sorted(set(self.regions) | set(other.regions))),
            count=self.count + other.count,
            examples=tuple(examples[:_MAX_EXAMPLES]),
            aws_message=self.aws_message or other.aws_message,
            retryable=self.retryable or other.retryable,
        )


def issue_sort_key(issue: Issue):
    """Deterministic order: severity, account, service, category, then the rest."""
    return (
        -SEVERITY_RANK[issue.severity],
        issue.account,
        issue.service,
        issue.category.value,
        issue.scope.value,
        issue.operation,
        issue.code,
    )


def merge_issues(issues: Iterable[Issue]) -> List[Issue]:
    """Merge issues with the same key; return them sorted (pure)."""
    merged: Dict[tuple, Issue] = {}
    for issue in issues:
        current = merged.get(issue.key)
        merged[issue.key] = issue if current is None else current.merged_with(issue)
    return sorted(merged.values(), key=issue_sort_key)


class IssueLog:
    """Thread-safe collector of issues; merges by :attr:`Issue.key`."""

    def __init__(self, issues: Iterable[Issue] = ()):
        self._lock = threading.Lock()
        self._issues: Dict[tuple, Issue] = {}
        for issue in issues:
            self.add(issue)

    def add(self, issue: Issue) -> Issue:
        with self._lock:
            current = self._issues.get(issue.key)
            merged = issue if current is None else current.merged_with(issue)
            self._issues[issue.key] = merged
            return merged

    def extend(self, issues: Iterable[Issue]) -> None:
        for issue in issues:
            self.add(issue)

    def issues(self) -> List[Issue]:
        with self._lock:
            values = list(self._issues.values())
        return sorted(values, key=issue_sort_key)

    def __len__(self) -> int:
        with self._lock:
            return len(self._issues)


@dataclass
class ServiceOutcome:
    """One service in one region of one account, from one source."""

    account: str
    region: str
    service: str
    source: str = "service-api"  # service-api, tagging-api, billing
    state: State = State.COMPLETE
    resources: int = 0
    calls_ok: int = 0
    calls_failed: int = 0
    category: Optional[Category] = None  # worst category when not complete
    seconds: float = 0.0


@dataclass
class RegionOutcome:
    region: str
    state: State = State.COMPLETE
    category: Optional[Category] = None
    services: Dict[Tuple[str, str], ServiceOutcome] = field(default_factory=dict)


@dataclass
class AccountOutcome:
    account_id: str
    account_name: str = ""
    state: State = State.COMPLETE
    category: Optional[Category] = None
    # An issue at account scope: no session, time limit, session expired, crash.
    account_issue: bool = False
    # The account read nothing (or no account-level cause other than an expired
    # session): the cases of owner decision O1 (OF-1). See exit_codes.Policy.
    derived_failure: bool = False
    regions: Dict[str, RegionOutcome] = field(default_factory=dict)
    resources: int = 0
    seconds: float = 0.0
    reused_from: str = ""  # UTC time of the earlier scan (--resume), else ""


@dataclass
class OutputOutcome:
    # excel, word, json, google-sheets, google-docs, tag-compliance, s3-upload,
    # state-snapshot, changelog, audit, checkpoints
    name: str
    # True for what the user asked for by flag or template: report formats,
    # Google, S3.
    required: bool
    state: State = State.COMPLETE
    files: Tuple[str, ...] = ()
    category: Optional[Category] = None


@dataclass
class Findings:
    """Results, not failures; they feed exit codes 3 and 4."""

    tag_violations: int = 0
    risk_findings: int = 0


@dataclass
class RunOutcome:
    accounts: List[AccountOutcome] = field(default_factory=list)
    outputs: List[OutputOutcome] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    findings: Findings = field(default_factory=Findings)
    resources_found: int = 0
    resources_reported: int = 0
    guard_blocks: int = 0
    cancelled_by: Optional[int] = None  # signal number
    usage_error: bool = False
    run_error: Optional[Category] = None

    @property
    def empty(self) -> bool:
        return self.resources_reported == 0

    @property
    def cancelled(self) -> bool:
        return self.cancelled_by is not None

    @property
    def state(self) -> State:
        """COMPLETE, PARTIAL or FAILED (a cancelled run is FAILED here)."""
        if self.cancelled_by is not None or self.run_error is not None:
            return State.FAILED
        scanned = [a for a in self.accounts if a.state is not State.SKIPPED]
        if scanned and all(a.state is State.FAILED for a in scanned):
            return State.FAILED
        if any(o.required and o.state is State.FAILED for o in self.outputs):
            return State.FAILED
        if any(a.state is not State.COMPLETE for a in self.accounts):
            return State.PARTIAL
        if any(o.state is State.FAILED for o in self.outputs):
            return State.PARTIAL
        if self.guard_blocks:
            return State.PARTIAL
        return State.COMPLETE

    @property
    def state_word(self) -> str:
        """The status word: COMPLETE, INCOMPLETE, FAILED or CANCELLED."""
        if self.cancelled_by is not None:
            return "CANCELLED"
        return {
            State.COMPLETE: "COMPLETE",
            State.PARTIAL: "INCOMPLETE",
            State.FAILED: "FAILED",
        }[self.state]
