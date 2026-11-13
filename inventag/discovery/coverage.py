"""What discovery attempted, and how each listing call ended.

Without this record a failed or throttled call looks the same as "no
resources here". Each listing call writes one :class:`CoverageEntry`; the
report can then say which service and region could not be read and why.
(The Coverage sheet itself belongs to reporting; this module only records.)
"""

import threading
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

# Outcomes
OK = "ok"  # call succeeded and returned resources
EMPTY = "empty"  # call succeeded, nothing there
DENIED = "denied"  # no permission (or region/service not enabled)
THROTTLED = "throttled"  # still throttled after the retries
ERROR = "error"  # any other failure
TIMEOUT = "timeout"  # not finished before the discovery time limit

FAILED_OUTCOMES = frozenset({DENIED, THROTTLED, ERROR, TIMEOUT})

_THROTTLE_CODES = frozenset(
    {
        "Throttling",
        "ThrottlingException",
        "ThrottledException",
        "TooManyRequestsException",
        "RequestLimitExceeded",
        "RequestThrottled",
        "RequestThrottledException",
        "SlowDown",
        "ProvisionedThroughputExceededException",
    }
)


def outcome_for_error(code: str, denied_codes) -> str:
    """Outcome for an AWS error code."""
    if code in denied_codes:
        return DENIED
    if code in _THROTTLE_CODES:
        return THROTTLED
    return ERROR


@dataclass(frozen=True)
class CoverageEntry:
    account_id: str
    region: str  # region code or "global"
    source: str  # "service-api" | "tagging-api" | "billing"
    service: str  # discovery service key, e.g. "ecs"
    resource_type: str  # "" when the source is not per type
    operation: str  # botocore operation name, e.g. "ListServices"
    outcome: str  # see the constants above
    count: int
    error_code: str = ""
    seconds: float = 0.0


class CoverageLedger:
    """Thread-safe list of :class:`CoverageEntry`."""

    def __init__(self, account_id: str = ""):
        self.account_id = account_id
        self._entries: List[CoverageEntry] = []
        self._lock = threading.Lock()

    def record(self, **fields: Any) -> CoverageEntry:
        fields.setdefault("account_id", self.account_id or "")
        entry = CoverageEntry(**fields)
        with self._lock:
            self._entries.append(entry)
        return entry

    @property
    def entries(self) -> List[CoverageEntry]:
        with self._lock:
            return list(self._entries)

    def to_dict(self) -> List[Dict[str, Any]]:
        return [asdict(e) for e in self.entries]

    def failed_units(self) -> List[CoverageEntry]:
        """Entries whose resources may be missing from the report."""
        return [e for e in self.entries if e.outcome in FAILED_OUTCOMES]

    def summary(self) -> Dict[str, int]:
        """Number of entries per outcome."""
        counts: Dict[str, int] = {}
        for e in self.entries:
            counts[e.outcome] = counts.get(e.outcome, 0) + 1
        return counts
