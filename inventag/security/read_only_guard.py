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
3. Clients that botocore's own credential providers create to sign in
   (IAM Identity Center/SSO, web identity, ``aws login``) are created
   *unsigned*: they carry no account credentials and can only exchange a
   token for credentials. Such a client may call exactly the operations in
   :data:`UNSIGNED_CREDENTIAL_EXCHANGE_OPERATIONS`. A signed client calling
   the same operation is still blocked.
4. A few read operations return secrets only when asked to with a parameter
   (``apigateway:GetApiKey(s)`` with ``includeValue(s)``,
   ``ec2:DescribeInstanceAttribute`` for ``userData``); those parameter
   values are blocked (:data:`DENIED_PARAMETERS`).
5. Methods that sign a request locally without calling AWS
   (``generate_presigned_url``, ``generate_presigned_post``, RDS/DSQL auth
   tokens) are checked against the same rules: a presigned URL or a database
   token is a credential for the operation it names.
6. A specific client can be granted extra operations with
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

import botocore
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

# Operations botocore's credential providers call on the *unsigned* clients
# they create to turn a token into credentials (SSO: sso:GetRoleCredentials and
# sso-oidc:CreateToken; web identity: sts:AssumeRoleWithWebIdentity; ``aws
# login``: signin:CreateOAuth2Token). Without these, an SSO or web-identity
# profile cannot sign in while the guard is installed.
UNSIGNED_CREDENTIAL_EXCHANGE_OPERATIONS: FrozenSet[Tuple[str, str]] = frozenset(
    {
        ("sso", "GetRoleCredentials"),
        ("sso-oidc", "CreateToken"),
        ("sts", "AssumeRoleWithWebIdentity"),
        ("signin", "CreateOAuth2Token"),
    }
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
        # More calls that hand out credentials, keys, tokens or passwords
        ("*", "GetAccessToken"),
        ("*", "GetDataAccess"),
        ("*", "GetSessionEndpoint"),
        ("*", "GetIdentityCenterAuthToken"),
        ("*", "GetDelegatedAccessToken"),
        ("*", "GetWorkloadAccessToken"),
        ("*", "GetWorkloadAccessTokenForJWT"),
        ("*", "GetWorkloadAccessTokenForUserId"),
        ("acm", "GetAcmeExternalAccountBindingCredentials"),
        ("appsync", "ListApiKeys"),
        ("bedrock-agentcore", "GetResourceApiKey"),
        ("bedrock-agentcore", "GetResourceOauth2Token"),
        ("bedrock-agentcore", "GetResourcePaymentToken"),
        ("cloudwatchomni", "GetSpaceCredentialsForOrganization"),
        ("cloudwatchomni", "GetSpaceDataAccess"),
        ("codepipeline", "GetJobDetails"),
        ("codepipeline", "GetThirdPartyJobDetails"),
        ("cognito-idp", "GetClientToken"),
        ("cognito-idp", "GetTokensFromRefreshToken"),
        ("cognito-idp", "ListUserPoolClientSecrets"),
        ("datazone", "GetEnvironmentCredentials"),
        ("ec2", "GetLaunchTemplateData"),
        ("emr", "GetClusterSessionCredentials"),
        ("emr-containers", "GetManagedEndpointSessionCredentials"),
        ("gamelift", "GetComputeAccess"),
        ("gamelift", "GetComputeAuthToken"),
        ("gamelift", "GetInstanceAccess"),
        ("ivs", "GetStreamKey"),
        ("ivs", "BatchGetStreamKey"),
        ("lightsail", "GetBucketAccessKeys"),
        ("lightsail", "GetRelationalDatabaseMasterUserPassword"),
        ("pca-connector-scep", "GetChallengePassword"),
        ("redshift-serverless", "GetCredentials"),
        ("storagegateway", "DescribeChapCredentials"),
        ("wickr", "GetOidcInfo"),
        ("wickr", "GetOpentdfConfig"),
        # Templates, files and object or media contents
        ("*", "GetObject"),
        ("*", "GetQueryResults"),
        ("cloudformation", "GetTemplate"),
        ("codecommit", "GetBlob"),
        ("codecommit", "GetFile"),
        ("ebs", "GetSnapshotBlock"),
        ("glacier", "GetJobOutput"),
        ("kinesis-video-media", "GetMedia"),
        ("kinesis-video-archived-media", "GetClip"),
        ("kinesis-video-archived-media", "GetMediaForFragmentList"),
        ("kinesis-video-archived-media", "GetHLSStreamingSessionURL"),
        ("kinesis-video-archived-media", "GetDASHStreamingSessionURL"),
        ("lightsail", "GetRelationalDatabaseLogEvents"),
        ("logs", "GetLogObject"),
    }
)

# (service, operation) -> {parameter: values that make the call return a secret}.
# Values are compared as lower-case strings, as they appear in the serialized
# request (query string or form body).
DENIED_PARAMETERS: Dict[Tuple[str, str], Dict[str, FrozenSet[str]]] = {
    ("apigateway", "GetApiKey"): {"includeValue": frozenset({"true"})},
    ("apigateway", "GetApiKeys"): {"includeValues": frozenset({"true"})},
    # User data often carries passwords and bootstrap tokens.
    ("ec2", "DescribeInstanceAttribute"): {"Attribute": frozenset({"userdata"})},
}

# Client methods that sign locally (no AWS call) -> how to name the operation
# they create a credential for. ``None`` means "the ClientMethod argument".
_LOCAL_SIGNING_METHODS: Dict[str, Optional[str]] = {
    "generate_presigned_url": None,
    "generate_presigned_post": "PostObject",
    "generate_db_auth_token": "GenerateDBAuthToken",
    "generate_db_connect_auth_token": "GenerateDBConnectAuthToken",
    "generate_db_connect_admin_auth_token": "GenerateDBConnectAdminAuthToken",
}

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


def _request_params(request_dict) -> Dict[str, Any]:
    """Parameter name -> value from a serialized botocore request dict.

    Query-protocol services (EC2, IAM ...) put parameters in a form ``body``
    dict; REST services put flags such as ``includeValue`` in ``query_string``.
    """
    found: Dict[str, Any] = {}
    if not isinstance(request_dict, dict):
        return found
    for part in ("query_string", "body"):
        value = request_dict.get(part)
        if isinstance(value, dict):
            found.update(value)
    return found


def _denied_parameter(service: str, operation: str, params) -> Optional[str]:
    rules = DENIED_PARAMETERS.get((service, operation))
    if not rules or not params:
        return None
    for name, bad_values in rules.items():
        if name in params and str(params[name]).lower() in bad_values:
            return f"{name}={params[name]}"
    return None


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
        params: Optional[Dict[str, Any]] = None,
        unsigned: bool = False,
    ) -> Tuple[bool, str]:
        """Return ``(allowed, reason)`` for ``service:operation``.

        Args:
            client_extra: operations allowed on this one client.
            params: serialized request parameters (name -> value), checked
                against :data:`DENIED_PARAMETERS`.
            unsigned: True for a client created with
                ``signature_version=UNSIGNED`` (no account credentials).
        """
        if operation in client_extra:
            return True, "explicitly allowed for this client"
        if _matches(self._extra_allowed, service, operation):
            return True, "explicitly allowed"
        if unsigned and (service, operation) in UNSIGNED_CREDENTIAL_EXCHANGE_OPERATIONS:
            return True, "sign-in token exchange by an unsigned credential client"
        if _matches(DENIED_OPERATIONS, service, operation):
            return False, "operation returns secrets, signed URLs or customer data"
        denied_param = _denied_parameter(service, operation, params)
        if denied_param:
            return False, f"parameter {denied_param} makes the call return secrets"
        if _matches(EXTRA_ALLOWED_OPERATIONS, service, operation):
            return True, "required to reach other accounts"
        if operation.startswith(READ_ONLY_PREFIXES):
            return True, "read-only prefix"
        return False, "operation is not on the read-only allowlist"

    # ------------------------------------------------------------- attachment
    def attach_client(self, client) -> None:
        """Attach the guard to an existing botocore/boto3 client.

        Hooks every API call, and wraps the client's local signing methods
        (presigned URLs and database auth tokens), which make no API call.
        """
        client_ref = weakref.ref(client)
        handler = functools.partial(self._before_call, client_ref=client_ref)
        client.meta.events.register("before-call", handler, unique_id=self.UNIQUE_ID)
        for method_name, operation in _LOCAL_SIGNING_METHODS.items():
            original = getattr(client, method_name, None)
            if original is None or getattr(original, "_inventag_guarded", False):
                continue
            setattr(
                client,
                method_name,
                self._guard_local_signing(client_ref, original, operation),
            )

    def _guard_local_signing(self, client_ref, original, operation_name):
        guard = self

        @functools.wraps(original)
        def guarded(*args, **kwargs):
            client = client_ref()
            service = client.meta.service_model.service_name if client else "?"
            if operation_name is None:
                method = kwargs.get("ClientMethod", args[0] if args else "")
                mapping = getattr(
                    getattr(client, "meta", None), "method_to_api_mapping", {}
                )
                operation = mapping.get(method, method)
            else:
                operation = operation_name
            guard._check(client, service, str(operation), params=None)
            return original(*args, **kwargs)

        guarded._inventag_guarded = True
        return guarded

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
    def _before_call(self, client_ref=None, model=None, params=None, **kwargs):
        if model is None:  # pragma: no cover - botocore always passes the model
            return None
        service = model.service_model.service_name
        operation = model.name
        client = client_ref() if client_ref is not None else None
        self._check(client, service, operation, params=_request_params(params))
        return None

    def _check(self, client, service: str, operation: str, params) -> None:
        client_extra = getattr(client, "_inventag_read_only_extra", frozenset())
        config = getattr(getattr(client, "meta", None), "config", None)
        unsigned = getattr(config, "signature_version", None) is botocore.UNSIGNED
        allowed, reason = self.evaluate(
            service, operation, client_extra, params=params, unsigned=unsigned
        )
        region = getattr(getattr(client, "meta", None), "region_name", None)
        self._record(service, operation, allowed, reason, region)
        if not allowed:
            logger.error(f"Read-only guard blocked {service}:{operation} ({reason})")
            raise ReadOnlyViolationError(service, operation, reason)

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


def check_client_call(client, method_name: str) -> Tuple[bool, str]:
    """Would the guard allow ``client.<method_name>(...)``?

    For code that picks operations by name at run time (enrichment, dynamic
    discovery): call this first, so the read-only policy applies also when the
    global guard is not installed (InvenTag used as a library). Parameter
    rules are not checked here; the installed guard still checks them.
    """
    meta = getattr(client, "meta", None)
    try:
        service = meta.service_model.service_name
    except AttributeError:
        return False, "not an AWS client"
    mapping = getattr(meta, "method_to_api_mapping", {}) or {}
    operation = mapping.get(method_name)
    if operation is None:
        return False, f"{method_name} is not an operation of {service}"
    guard = _installed_guard or ReadOnlyGuard()
    extra = getattr(client, "_inventag_read_only_extra", frozenset())
    config = getattr(meta, "config", None)
    unsigned = getattr(config, "signature_version", None) is botocore.UNSIGNED
    return guard.evaluate(service, operation, extra, unsigned=unsigned)
