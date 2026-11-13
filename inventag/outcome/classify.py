"""Turn an exception into an :class:`~inventag.outcome.model.Issue`.

:func:`classify` is the only place in InvenTag that reads an exception to
decide what it means. Order of checks, first match wins:

1. InvenTag's own exceptions: a class attribute ``inventag_category``, or
   (until every class carries the attribute) the class name in
   :data:`OWN_CLASS_CATEGORIES`. No InvenTag exception class is imported.
2. botocore ``ClientError``: the AWS error code, looked up by phase
   (:data:`PHASE_CODES`), then by service (:data:`SERVICE_CODES`), then in
   :data:`AWS_CODES`; then the "not found" pattern; then the HTTP status.
3. botocore exception classes (:data:`BOTOCORE_CLASSES`), matched by class
   name along the method resolution order, so subclasses win over bases and
   a class missing from an older botocore costs nothing.
4. Python built-ins.
5. Everything else: ``internal_error``.

The issue keeps the AWS error code or the exception class name, never
``str(exc)``. AWS's own message is kept in ``aws_message`` only after it is
cleaned (see :func:`clean_aws_message`).
"""

from __future__ import annotations

import errno
import re
import socket
import ssl
from typing import Dict, Optional, Tuple

from inventag.security.redaction import REDACTED, redact

from .model import RETRYABLE, Category, Issue, Scope

C = Category

# --------------------------------------------------------------------------
# 1. InvenTag's own exceptions (by class name; the attribute wins)

OWN_CLASS_CATEGORIES: Dict[str, Category] = {
    "ReadOnlyViolationError": C.GUARD_BLOCK,
    "AccountTimeoutError": C.TIMEOUT,
    "BudgetExceeded": C.TIMEOUT,
    "RunCancelled": C.CANCELLED,
    "TemplateError": C.INVALID_INPUT,
    "TemplateNotFoundError": C.INVALID_INPUT,
    "TemplateValidationError": C.INVALID_INPUT,
    "SettingsFileError": C.INVALID_INPUT,
    "InvalidRoleError": C.INVALID_INPUT,
    "S3UploadError": C.INVALID_INPUT,
    "ReportGenerationError": C.OUTPUT_FAILURE,
    "GoogleOutputError": C.OUTPUT_FAILURE,
    "AccountSessionError": C.CREDENTIALS,
}

# --------------------------------------------------------------------------
# 2. AWS error codes

#: Table C. Codes found in botocore's service data, and common AWS codes.
AWS_CODES: Dict[str, Category] = {}


def _codes(category: Category, *codes: str) -> None:
    for code in codes:
        AWS_CODES[code] = category


_codes(
    C.CREDENTIALS,
    "ExpiredTokenException",
    "UnrecognizedClientException",
    "MissingAuthenticationToken",
    "InvalidToken",
    "InvalidIdentityToken",
    "IDPCommunicationError",
    "IDPRejectedClaim",
    "InvalidGrantException",
    "UnauthorizedClientException",
    # from memory (AWS common errors)
    "ExpiredToken",
    "RequestExpired",
    "InvalidClientTokenId",
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
    "IncompleteSignature",
    "InvalidSignatureException",
    "AuthFailure",
    "TokenRefreshRequired",
)
_codes(
    C.PERMISSION_DENIED,
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedOperation",
    "UnauthorizedException",
    "AuthorizationError",
    "AuthorizationErrorException",
    "NotAuthorizedException",
    "AccessDeniedFault",
    "ForbiddenException",
    "KMSAccessDeniedException",
    "OrganizationAccessDeniedException",
    # from memory
    "Forbidden",
    "403",
    "KMS.AccessDeniedException",
    "UnauthorizedAccess",
)
_codes(
    C.NOT_ENABLED,
    "OptInRequiredException",
    "SubscriptionRequiredException",
    "RegionDisabledException",
    "AWSOrganizationsNotInUseException",
    "PendingVerification",
    # from memory
    "OptInRequired",
    "NotSignedUp",
    "AllAccessDisabled",
    "AccountProblem",
    "Blocked",
)
_codes(
    C.NOT_AVAILABLE,
    "UnsupportedOperation",
    "UnsupportedOperationException",
    # from memory
    "InvalidAction",
    "UnknownOperationException",
)
_codes(
    C.NOT_FOUND,
    "ResourceNotFoundException",
    "NoSuchEntity",
    "NoSuchBucket",
    "NotFoundException",
    # from memory
    "404",
)
_codes(
    C.THROTTLED,
    "ThrottlingException",
    "ThrottledException",
    "TooManyRequestsException",
    "RequestLimitExceeded",
    "RequestThrottled",
    "RequestThrottledException",
    "ProvisionedThroughputExceededException",
    "LimitExceededException",
    "TransactionInProgressException",
    "PriorRequestNotComplete",
    "EC2ThrottledException",
    # botocore's retry table only
    "Throttling",
    "SlowDown",
    "BandwidthLimitExceeded",
)
_codes(
    C.TIMEOUT,
    "RequestTimeout",
    "RequestTimeoutException",
    "DependencyTimeoutException",
)
_codes(
    C.SERVICE_ERROR,
    "InternalFailure",
    "InternalError",
    "InternalServerError",
    "InternalServerException",
    "InternalServiceError",
    "InternalServiceException",
    "ServiceUnavailable",
    "ServiceUnavailableException",
    "ServiceFailure",
    "ServiceException",
    "ServerException",
    "KMSInternalException",
    # expired or invalid pagination tokens
    "InvalidNextToken",
    "InvalidNextTokenException",
    "ExpiredNextTokenException",
    "PaginationTokenExpiredException",
    "InvalidPaginationToken",
)
_codes(
    C.INTERNAL_ERROR,
    # AWS rejects the request InvenTag built
    "ValidationException",
    "ValidationError",
    "InvalidParameterValue",
    "InvalidParameter",
    "InvalidParameterException",
    "InvalidParameterCombination",
    "MissingParameter",
    "InvalidArgument",
    "InvalidInput",
    "InvalidRequest",
    "InvalidRequestException",
    # from memory
    "MalformedQueryString",
    "SerializationException",
)

#: Table D. Service-specific codes (win over table C).
SERVICE_CODES: Dict[Tuple[str, str], Category] = {
    ("stepfunctions", "InvalidToken"): C.SERVICE_ERROR,  # pagination token
    ("sso", "UnauthorizedException"): C.CREDENTIALS,  # SSO session expired
    ("ce", "DataUnavailableException"): C.NOT_ENABLED,  # no data yet
}
#: ``ce`` ``AccessDeniedException`` with this text means "not enabled".
CE_NOT_ENABLED_TEXT = "not enabled for cost explorer"

#: Table E. Phase-specific codes (win over tables C and D).
PHASE_CODES: Dict[Tuple[str, str], Category] = {
    ("region_check", "AuthFailure"): C.NOT_ENABLED,
    ("region_check", "UnrecognizedClientException"): C.NOT_ENABLED,
    ("region_check", "InvalidClientTokenId"): C.NOT_ENABLED,
    ("assume_role", "ValidationError"): C.INVALID_INPUT,
    ("assume_role", "MalformedPolicyDocument"): C.INVALID_INPUT,
    ("upload", "NoSuchBucket"): C.INVALID_INPUT,
    ("upload", "PermanentRedirect"): C.INVALID_INPUT,
    ("upload", "AuthorizationHeaderMalformed"): C.INVALID_INPUT,
    ("upload", "IllegalLocationConstraintException"): C.INVALID_INPUT,
    ("upload", "KMS.NotFoundException"): C.INVALID_INPUT,
}

#: Table F. Unknown code, by HTTP status (else ``service_error``).
HTTP_STATUS: Dict[int, Category] = {
    429: C.THROTTLED,
    401: C.PERMISSION_DENIED,
    403: C.PERMISSION_DENIED,
    408: C.TIMEOUT,
}

#: Codes that mean "the session expired" (account-fatal inside a scan).
EXPIRED_SESSION_CODES = frozenset(
    {"ExpiredToken", "ExpiredTokenException", "RequestExpired"}
)

_NOT_FOUND_PATTERN = re.compile(
    r"^NoSuch|(?:NotFound|NotFoundException|NotFoundFault|\.NotFound)$"
)

# --------------------------------------------------------------------------
# 3. botocore exception classes, by name (Table B)

BOTOCORE_CLASSES: Dict[str, Category] = {}


def _classes(category: Category, *names: str) -> None:
    for name in names:
        BOTOCORE_CLASSES[name] = category


_classes(
    C.CREDENTIALS,
    "NoCredentialsError",
    "PartialCredentialsError",
    "CredentialRetrievalError",
    "UnknownCredentialError",
    "ProfileNotFound",
    "SSOError",
    "SSOTokenLoadError",
    "UnauthorizedSSOTokenError",
    "TokenRetrievalError",
    "NoAuthTokenError",
    "RefreshWithMFAUnsupportedError",
    "MetadataRetrievalError",
    "LoginError",
    "LoginRefreshRequired",
    "LoginTokenLoadError",
)
_classes(C.TIMEOUT, "ReadTimeoutError")
_classes(
    C.NETWORK,
    "ConnectionError",
    "EndpointConnectionError",
    "ConnectTimeoutError",
    "SSLError",
    "ProxyConnectionError",
    "HTTPClientError",
    "ConnectionClosedError",
    "ResponseStreamingError",
    "IncompleteReadError",
)
_classes(
    C.NOT_AVAILABLE,
    "UnknownServiceError",
    "UnknownEndpointError",
    "ServiceNotInRegionError",
    "EndpointProviderError",
    "EndpointResolutionError",
)
_classes(
    C.INVALID_INPUT,
    "NoRegionError",
    "InvalidRegionError",
    "UnknownRegionError",
    "InvalidConfigError",
    "InfiniteLoopConfigError",
    "ConfigNotFound",
    "ConfigParseError",
    "InvalidProxiesConfigError",
    "InvalidIMDSEndpointError",
    "InvalidRetryConfigurationError",
    "MissingDependencyException",
)
_classes(C.SERVICE_ERROR, "PaginationError", "ChecksumError")
#: Any other botocore error is a defect in how InvenTag called botocore.
_classes(C.INTERNAL_ERROR, "BotoCoreError")

#: Code stored when botocore's MFA prompt finds no terminal (EOFError).
MFA_WITHOUT_TERMINAL = "MfaPromptWithoutTerminal"

_MAX_AWS_MESSAGE = 300
_MAX_CODE = 100
_CODE_CHARS = re.compile(r"[^A-Za-z0-9._:\-]")

# Extra scrubbing for AWS messages, on top of redact(): access key IDs, long
# opaque tokens (secret keys, session tokens), and credentials in proxy URLs.
_ACCESS_KEY_ID = re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b")
_LONG_TOKEN = re.compile(r"[A-Za-z0-9/+=]{32,}")
# A long token is opaque (a key or token) when it mixes digits and both cases;
# resource paths such as "role/InvenTagCrossAccountRole/Session" are kept.
_OPAQUE = (re.compile(r"[0-9]"), re.compile(r"[a-z]"), re.compile(r"[A-Z]"))
_URL_CREDENTIALS = re.compile(r"(\b[a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@")
_ENCODED_AUTH = re.compile(r"\s*Encoded authorization failure message:.*$", re.DOTALL)


def clean_aws_message(text: object) -> str:
    """AWS's ``Error.Message`` made safe to print.

    Removes "Encoded authorization failure message: ..." to the end, applies
    :func:`inventag.security.redaction.redact`, masks access key IDs, long
    opaque tokens and user:password in URLs, collapses whitespace and cuts to
    300 characters.
    """
    if text is None:
        return ""
    text = str(text)
    text = _ENCODED_AUTH.sub("", text)
    text = redact(text)
    text = _ACCESS_KEY_ID.sub(REDACTED, text)
    text = _URL_CREDENTIALS.sub(lambda m: m.group(1) + REDACTED + "@", text)
    text = _LONG_TOKEN.sub(
        lambda m: (
            REDACTED if all(p.search(m.group(0)) for p in _OPAQUE) else m.group(0)
        ),
        text,
    )
    text = " ".join(text.split())
    if len(text) > _MAX_AWS_MESSAGE:
        text = text[: _MAX_AWS_MESSAGE - 3].rstrip() + "..."
    return text


def clean_code(code: object) -> str:
    """An error code or class name, limited to safe characters and length."""
    return _CODE_CHARS.sub("", str(code or ""))[:_MAX_CODE]


def category_for_code(
    code: str,
    *,
    scope: Scope = Scope.SERVICE,
    phase: str = "",
    service: str = "",
    http_status: Optional[int] = None,
    aws_message: str = "",
) -> Category:
    """Category of an AWS error code (tables E, D, C, the pattern, F)."""
    category = _lookup_code(code, phase, service, http_status, aws_message)
    if category is C.NOT_FOUND and Scope(scope) is not Scope.RESOURCE:
        # A listing cannot be "not found".
        return C.SERVICE_ERROR
    return category


def _lookup_code(code, phase, service, http_status, aws_message) -> Category:
    if (phase, code) in PHASE_CODES:
        return PHASE_CODES[(phase, code)]
    if (
        service == "ce"
        and code == "AccessDeniedException"
        and CE_NOT_ENABLED_TEXT in (aws_message or "").lower()
    ):
        return C.NOT_ENABLED
    if (service, code) in SERVICE_CODES:
        return SERVICE_CODES[(service, code)]
    if code in AWS_CODES:
        return AWS_CODES[code]
    if code and _NOT_FOUND_PATTERN.search(code):
        return C.NOT_FOUND
    if http_status in HTTP_STATUS:
        return HTTP_STATUS[http_status]
    return C.SERVICE_ERROR


def category_for_class_name(name: str) -> Optional[Category]:
    """Category of an exception known only by its class name (ledger entries)."""
    if name in OWN_CLASS_CATEGORIES:
        return OWN_CLASS_CATEGORIES[name]
    if name in BOTOCORE_CLASSES:
        return BOTOCORE_CLASSES[name]
    return None


def _own_category(exc: BaseException) -> Optional[Category]:
    declared = getattr(exc, "inventag_category", None)
    if declared:
        return Category(declared)
    for klass in type(exc).__mro__:
        if klass.__name__ in OWN_CLASS_CATEGORIES and klass.__module__.startswith(
            "inventag"
        ):
            return OWN_CLASS_CATEGORIES[klass.__name__]
    return None


def _client_error_parts(exc: BaseException) -> Optional[Tuple[str, Optional[int], str]]:
    """(code, HTTP status, message) of a botocore ClientError, else None."""
    try:
        from botocore.exceptions import ClientError
    except ImportError:  # pragma: no cover - botocore is a dependency
        return None
    if not isinstance(exc, ClientError):
        return None
    response = getattr(exc, "response", None) or {}
    error = response.get("Error") or {}
    status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None
    return str(error.get("Code") or ""), status, str(error.get("Message") or "")


def _botocore_category(exc: BaseException) -> Optional[Tuple[Category, str]]:
    for klass in type(exc).__mro__:
        if (
            klass.__module__.startswith("botocore")
            and klass.__name__ in BOTOCORE_CLASSES
        ):
            return BOTOCORE_CLASSES[klass.__name__], type(exc).__name__
    return None


def _builtin_category(
    exc: BaseException, scope: Scope, phase: str
) -> Tuple[Category, str]:
    name = type(exc).__name__
    if isinstance(exc, KeyboardInterrupt):
        return C.CANCELLED, name
    if isinstance(exc, (ssl.SSLError, socket.gaierror, ConnectionError)):
        return C.NETWORK, name
    if isinstance(exc, TimeoutError):
        return C.TIMEOUT, name
    if isinstance(exc, EOFError) and phase in ("credentials", "assume_role"):
        return C.CREDENTIALS, MFA_WITHOUT_TERMINAL
    if isinstance(exc, OSError) and scope is Scope.OUTPUT:
        code = errno.errorcode.get(exc.errno, name) if exc.errno else name
        return C.OUTPUT_FAILURE, code
    return C.INTERNAL_ERROR, name


def classify(
    exc: BaseException,
    *,
    scope: Scope,
    phase: str = "",
    account: str = "",
    region: str = "",
    service: str = "",
    operation: str = "",
    resource: str = "",
) -> Issue:
    """The :class:`Issue` for ``exc``. Never stores ``str(exc)``."""
    scope = Scope(scope)
    context = dict(
        scope=scope,
        phase=phase,
        account=account,
        region=region,
        service=service,
        operation=operation,
    )
    own = _own_category(exc)
    if own is not None:
        if own is C.CREDENTIALS and type(exc).__name__ == "AccountSessionError":
            cause = exc.__cause__
            if cause is not None and cause is not exc:
                return classify(
                    cause, **{**context, "phase": "credentials"}, resource=resource
                )
        return _issue(own, type(exc).__name__, "", context, resource)

    parts = _client_error_parts(exc)
    if parts is not None:
        code, status, message = parts
        aws_message = clean_aws_message(message)
        category = category_for_code(
            code,
            scope=scope,
            phase=phase,
            service=service,
            http_status=status,
            aws_message=message,
        )
        return _issue(
            category, code or str(status or ""), aws_message, context, resource
        )

    found = _botocore_category(exc)
    if found is not None:
        return _issue(found[0], found[1], "", context, resource)

    category, code = _builtin_category(exc, scope, phase)
    return _issue(category, code, "", context, resource)


def _issue(category, code, aws_message, context, resource) -> Issue:
    return Issue(
        category=category,
        code=clean_code(code),
        aws_message=aws_message,
        retryable=category in RETRYABLE,
        examples=(resource,) if resource else (),
        **context,
    )
