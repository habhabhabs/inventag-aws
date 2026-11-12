"""
Read-only enforcement for AWS API calls.

The guard hooks botocore's ``before-call`` event, which fires for every API
operation after parameter validation and before the request is signed or
sent. Operations that are not on the read-only allowlist raise
:class:`ReadOnlyViolationError`, so the request never leaves the process.

Allowlist rules (see :meth:`ReadOnlyGuard.evaluate`):

1. The operation name must start with one of :data:`READ_ONLY_PREFIXES`
   (``List``, ``Describe``, ``Get``, ``Head``, ``Lookup``, ``Search``,
   ``BatchGet``), or be listed in :data:`EXTRA_ALLOWED_OPERATIONS`
   (``sts:AssumeRole``, used to reach other accounts).
2. Operations in :data:`DENIED_OPERATIONS` are blocked even though they look
   like reads, because they return secret material (``GetSecretValue``,
   ``GetAuthorizationToken``, ``GetSessionToken`` ...), presigned download
   URLs (``lambda:GetFunction``), or customer data (``s3:GetObject``,
   ``dynamodb:GetItem`` ...). InvenTag builds an inventory; it never needs
   these.
3. A specific client can be granted extra operations with
   :meth:`ReadOnlyGuard.allow_on_client` (InvenTag uses this only for
   ``s3:PutObject`` on the client that uploads reports when ``--s3-bucket`` is
   given).

``Scan`` and ``Query`` are not allowed: they read table contents, not
inventory metadata.
"""

import functools
import logging
import threading
import weakref
from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Tuple

import botocore.session

logger = logging.getLogger(__name__)

READ_ONLY_PREFIXES: Tuple[str, ...] = (
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet",
)

# (service, operation); service "*" matches any service.
EXTRA_ALLOWED_OPERATIONS: FrozenSet[Tuple[str, str]] = frozenset(
    {
        ("sts", "AssumeRole"),
    }
)

DENIED_OPERATIONS: FrozenSet[Tuple[str, str]] = frozenset(
    {
        # Secret values and credentials
        ("*", "GetSecretValue"),
        ("*", "BatchGetSecretValue"),
        ("*", "GetAuthorizationToken"),
        ("*", "GetSessionToken"),
        ("*", "GetFederationToken"),
        ("*", "GetClusterCredentials"),
        ("*", "GetClusterCredentialsWithIAM"),
        ("*", "GetCredentialsForIdentity"),
        ("*", "GetOpenIdToken"),
        ("*", "GetOpenIdTokenForDeveloperIdentity"),
        ("*", "GetRoleCredentials"),
        ("*", "GetPasswordData"),
        ("*", "GetInstanceAccessDetails"),
        ("ssm", "GetParameter"),
        ("ssm", "GetParameters"),
        ("ssm", "GetParametersByPath"),
        ("ssm", "GetParameterHistory"),
        ("glue", "GetConnection"),
        ("glue", "GetConnections"),
        # Presigned code download URLs
        ("lambda", "GetFunction"),
        ("lambda", "GetLayerVersion"),
        ("lambda", "GetLayerVersionByArn"),
        ("ecr", "GetDownloadUrlForLayer"),
        # Customer data rather than inventory metadata
        ("s3", "GetObject"),
        ("s3", "GetObjectTorrent"),
        ("dynamodb", "GetItem"),
        ("dynamodb", "BatchGetItem"),
        ("kinesis", "GetRecords"),
        ("kinesis", "GetShardIterator"),
        ("logs", "GetLogEvents"),
        ("logs", "GetLogRecord"),
        ("logs", "GetQueryResults"),
        ("ec2", "GetConsoleOutput"),
        ("ec2", "GetConsoleScreenshot"),
    }
)

_MAX_RECORDED_BLOCKS = 1000


class ReadOnlyViolationError(Exception):
    """Raised when a non-read-only AWS operation is attempted under the guard."""

    def __init__(self, service: str, operation: str, reason: str):
        self.service = service
        self.operation = operation
        self.reason = reason
        super().__init__(
            f"Blocked AWS operation {service}:{operation} - {reason}. "
            "InvenTag runs in read-only mode: only List/Describe/Get/Head/"
            "Lookup/Search/BatchGet operations (minus a deny-list of "
            "secret- or data-returning calls) are allowed."
        )


def _matches(
    rule_set: FrozenSet[Tuple[str, str]], service: str, operation: str
) -> bool:
    return (service, operation) in rule_set or ("*", operation) in rule_set


class ReadOnlyGuard:
    """Blocks non-read-only AWS API calls via botocore's ``before-call`` event."""

    UNIQUE_ID = "inventag-read-only-guard"

    def __init__(self, extra_allowed: Iterable[str] = ()):
        """
        Args:
            extra_allowed: additional ``service:Operation`` strings allowed on
                every client (normally empty).
        """
        self._extra_allowed = frozenset(
            tuple(item.split(":", 1)) for item in extra_allowed
        )
        self._lock = threading.Lock()
        self._counts: Dict[Tuple[str, str, bool], int] = {}
        self._blocked: List[Dict[str, Any]] = []
        self._started_at = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------ policy
    def evaluate(
        self,
        service: str,
        operation: str,
        client_extra: FrozenSet[str] = frozenset(),
    ) -> Tuple[bool, str]:
        """Return ``(allowed, reason)`` for ``service:operation``."""
        if operation in client_extra:
            return True, "explicitly allowed for this client"
        if _matches(self._extra_allowed, service, operation):
            return True, "explicitly allowed"
        if _matches(DENIED_OPERATIONS, service, operation):
            return False, "operation returns secrets, signed URLs or customer data"
        if _matches(EXTRA_ALLOWED_OPERATIONS, service, operation):
            return True, "required to reach other accounts"
        if operation.startswith(READ_ONLY_PREFIXES):
            return True, "read-only prefix"
        return False, "operation is not on the read-only allowlist"

    # ------------------------------------------------------------- attachment
    def attach_client(self, client) -> None:
        """Attach the guard to an existing botocore/boto3 client."""
        client_ref = weakref.ref(client)
        handler = functools.partial(self._before_call, client_ref=client_ref)
        client.meta.events.register("before-call", handler, unique_id=self.UNIQUE_ID)

    def attach_session(self, session) -> None:
        """Attach to a boto3 or botocore session; affects clients created later."""
        events = getattr(session, "events", None)
        if events is None and hasattr(session, "_session"):
            events = session._session.get_component("event_emitter")
        handler = functools.partial(self._before_call, client_ref=None)
        events.register("before-call", handler, unique_id=self.UNIQUE_ID)

    @staticmethod
    def allow_on_client(client, operations: Iterable[str]) -> None:
        """Allow extra operation names (e.g. ``PutObject``) on one client only."""
        current = getattr(client, "_inventag_read_only_extra", frozenset())
        client._inventag_read_only_extra = frozenset(current) | frozenset(operations)

    # ---------------------------------------------------------------- handler
    def _before_call(self, client_ref=None, model=None, **kwargs):
        if model is None:  # pragma: no cover - botocore always passes the model
            return None
        service = model.service_model.service_name
        operation = model.name
        client = client_ref() if client_ref is not None else None
        client_extra = getattr(client, "_inventag_read_only_extra", frozenset())
        allowed, reason = self.evaluate(service, operation, client_extra)
        region = getattr(getattr(client, "meta", None), "region_name", None)
        self._record(service, operation, allowed, reason, region)
        if not allowed:
            logger.error(f"Read-only guard blocked {service}:{operation} ({reason})")
            raise ReadOnlyViolationError(service, operation, reason)
        return None

    def _record(
        self, service: str, operation: str, allowed: bool, reason: str, region
    ) -> None:
        with self._lock:
            key = (service, operation, allowed)
            self._counts[key] = self._counts.get(key, 0) + 1
            if not allowed and len(self._blocked) < _MAX_RECORDED_BLOCKS:
                self._blocked.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": service,
                        "operation": operation,
                        "region": region,
                        "reason": reason,
                    }
                )

    # ------------------------------------------------------------------ audit
    def audit_report(self) -> Dict[str, Any]:
        """Summary of every operation the guard saw (for ``--audit-output``)."""
        with self._lock:
            operations = [
                {
                    "service": service,
                    "operation": operation,
                    "allowed": allowed,
                    "count": count,
                }
                for (service, operation, allowed), count in sorted(self._counts.items())
            ]
            blocked = list(self._blocked)
        return {
            "read_only_enforced": True,
            "started_at": self._started_at,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "allowed_prefixes": list(READ_ONLY_PREFIXES),
            "total_calls": sum(op["count"] for op in operations),
            "allowed_calls": sum(op["count"] for op in operations if op["allowed"]),
            "blocked_calls": sum(op["count"] for op in operations if not op["allowed"]),
            "operations": operations,
            "blocked": blocked,
        }


# ------------------------------------------------------------ global install
_install_lock = threading.Lock()
_installed_guard: Optional[ReadOnlyGuard] = None
_original_create_client = None


def install_global_guard(guard: Optional[ReadOnlyGuard] = None) -> ReadOnlyGuard:
    """
    Attach ``guard`` to every botocore client created from now on, from any
    session (including ``boto3.client(...)`` and fresh ``boto3.Session()``s).

    Idempotent: a second call returns the guard already installed.
    """
    global _installed_guard, _original_create_client
    with _install_lock:
        if _installed_guard is not None:
            return _installed_guard
        guard = guard or ReadOnlyGuard()
        _original_create_client = botocore.session.Session.create_client
        original = _original_create_client

        @functools.wraps(original)
        def create_client(self, *args, **kwargs):
            client = original(self, *args, **kwargs)
            guard.attach_client(client)
            return client

        botocore.session.Session.create_client = create_client
        _installed_guard = guard
        return guard


def uninstall_global_guard() -> None:
    """Remove the global guard (clients already created keep their hook)."""
    global _installed_guard, _original_create_client
    with _install_lock:
        if _original_create_client is not None:
            botocore.session.Session.create_client = _original_create_client
        _installed_guard = None
        _original_create_client = None


def get_installed_guard() -> Optional[ReadOnlyGuard]:
    return _installed_guard
