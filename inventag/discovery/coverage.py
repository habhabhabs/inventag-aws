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
# Not listed because ``--account-services`` (or a template's ``services``)
# left the service out. Not a failure: it is not in ``FAILED_OUTCOMES``.
OUT_OF_SCOPE = "out_of_scope"

FAILED_OUTCOMES = frozenset({DENIED, THROTTLED, ERROR, TIMEOUT})

# Source of a record for a call that adds detail to a resource a listing found
# (bucket location, function configuration, ...). It is not a listing: the
# change report reads only "service-api" and "tagging-api" records as listings,
# so a failed detail call never makes it skip the resources of that service.
DETAIL_SOURCE = "service-api-detail"

# What AWS answers when the thing asked for is not set up, or is gone. These
# are answers, not failures: nothing is missing from the report.
NOTHING_CONFIGURED_CODES = frozenset(
    {
        "NoSuchBucketPolicy",
        "NoSuchTagSet",
        "NoSuchLifecycleConfiguration",
        "NoSuchPublicAccessBlockConfiguration",
        "NoSuchCORSConfiguration",
        "NoSuchWebsiteConfiguration",
        "NoSuchReplicationConfiguration",
        "ServerSideEncryptionConfigurationNotFoundError",
        "ObjectLockConfigurationNotFoundError",
        "404",
        "NotFound",
        "NoSuchKey",
        # The resource was deleted between the listing and the detail call.
        "NoSuchBucket",
        "ResourceNotFoundException",
        "DBInstanceNotFound",
        "DBInstanceNotFoundFault",
    }
)

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


_UNREADABLE_ANSWER = (ValueError, KeyError, TypeError, AttributeError, IndexError)
# A call that did not answer in time: botocore's own timeouts, or the shorter
# ones the generator gives Cost Explorer under a short account limit (A-24).
_TIMEOUT_ERRORS = frozenset({"ConnectTimeoutError", "ReadTimeoutError"})
_CONNECTION_ERRORS = frozenset(
    {
        "EndpointConnectionError",
        "ConnectTimeoutError",
        "ReadTimeoutError",
        "ConnectionClosedError",
        "ProxyConnectionError",
        "SSLError",
    }
)
_BILLING_TAIL = " so billing data is missing and billing checks are skipped. "


def billing_failure_message(error: BaseException, code: str, denied_codes) -> str:
    """One line for a failed Cost Explorer read: the cause, then one next step.

    Only the error code and the name of the exception are used. The botocore
    text is left out because it can hold request parameters.
    """
    if hasattr(error, "response") and isinstance(error.response, dict):
        outcome = outcome_for_error(code, denied_codes)
        if code == "OptInRequired":
            return (
                f"Cost Explorer is not enabled for this account ({code}),"
                + _BILLING_TAIL
                + "Enable Cost Explorer in the AWS Billing console."
            )
        if outcome == DENIED:
            return (
                f"Cost Explorer was denied ({code}),"
                + _BILLING_TAIL
                + "Allow ce:GetCostAndUsage for this role."
            )
        if outcome == THROTTLED:
            return (
                f"Cost Explorer was throttled ({code}),"
                + _BILLING_TAIL
                + "Run the scan again later."
            )
        what = f"could not be read ({code})"
    elif isinstance(error, _UNREADABLE_ANSWER):
        what = "returned an answer InvenTag could not read"
    elif type(error).__name__ in _TIMEOUT_ERRORS:
        return (
            f"Cost Explorer did not answer in time ({type(error).__name__}),"
            + _BILLING_TAIL
            + "Run the scan again."
        )
    elif type(error).__name__ in _CONNECTION_ERRORS:
        return (
            f"Cost Explorer could not be reached ({type(error).__name__}),"
            + _BILLING_TAIL
            + "Check the network connection and run the scan again."
        )
    else:
        what = f"failed ({type(error).__name__})"
    return (
        f"Cost Explorer {what},"
        + _BILLING_TAIL
        + "Run the scan again; if it repeats, report it with the --debug log."
    )
