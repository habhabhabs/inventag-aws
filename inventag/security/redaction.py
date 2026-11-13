"""
Secret redaction for log output.

botocore's DEBUG logging writes request headers (``X-Amz-Security-Token``,
``Authorization``), canonical requests and raw response bodies (for example the
``SecretAccessKey`` and ``SessionToken`` returned by ``sts:AssumeRole``).
InvenTag's own messages may also contain presigned URLs or webhook URLs.

This module removes that material before anything is written:

* :func:`redact` rewrites a string, replacing known secret patterns.
* :func:`register_secret` adds an exact value (for example a secret key read
  from an accounts file) that must never be logged.
* :class:`RedactingFormatter` wraps a formatter so the *final* text, including
  tracebacks, is redacted.
* :func:`install_log_record_redaction` installs a log-record factory so every
  record created in the process has its message redacted, whatever handler
  ends up writing it.

Secret values inside discovered resource data (environment variables,
passwords, user data...) are hidden by :mod:`inventag.security.secret_values`,
which holds the one deny-list for discovery, reports, snapshots and logs.
"""

import logging
import re
import threading
from typing import Iterable, Optional

from .secret_values import is_secret_key

REDACTED = "***REDACTED***"

# Field names whose values are secret, as they appear in AWS XML/JSON bodies,
# boto3 keyword arguments and InvenTag's own config files.
_SECRET_FIELD_NAMES = (
    "SecretAccessKey",
    "SessionToken",
    "SecretKey",
    "SecurityToken",
    "Password",
    "PasswordData",
    "SecretString",
    "SecretBinary",
    "AuthorizationToken",
    "aws_secret_access_key",
    "aws_session_token",
    "secret_access_key",
    "session_token",
    "secretAccessKey",
    "sessionToken",
    "accessToken",
    "password",
    # Google service-account keys and OAuth tokens
    "private_key",
    "private_key_id",
    "client_secret",
    "refresh_token",
    "access_token",
    "id_token",
    # SSO OIDC and ``aws login`` token exchange bodies
    "refreshToken",
    "clientSecret",
    "idToken",
    # Web identity sign-in (AssumeRoleWithWebIdentity request)
    "WebIdentityToken",
    "SAMLAssertion",
)

_FIELDS = "|".join(re.escape(f) for f in _SECRET_FIELD_NAMES)

_PATTERNS = [
    # XML bodies: <SecretAccessKey>...</SecretAccessKey>
    (
        re.compile(r"<(%s)>[^<]*</\1>" % _FIELDS),
        lambda m: "<%s>%s</%s>" % (m.group(1), REDACTED, m.group(1)),
    ),
    # JSON / Python repr: "SecretAccessKey": "..."  or 'session_token': '...'
    (
        re.compile(r"""(["'])(%s)\1(\s*:\s*)(b?)(["'])(?:\\.|(?!\5).)*\5""" % _FIELDS),
        lambda m: "%s%s%s%s%s%s%s%s"
        % (
            m.group(1),
            m.group(2),
            m.group(1),
            m.group(3),
            m.group(4),
            m.group(5),
            REDACTED,
            m.group(5),
        ),
    ),
    # key=value pairs in reprs/kwargs: aws_secret_access_key='...'
    (
        re.compile(r"""\b(%s)=(["'])[^"']*\2""" % _FIELDS),
        lambda m: "%s=%s%s%s" % (m.group(1), m.group(2), REDACTED, m.group(2)),
    ),
    # HTTP header dicts as botocore logs them: 'X-Amz-Security-Token': b'...'
    (
        re.compile(
            r"""(["'](?:X-Amz-Security-Token|Authorization|X-Amz-Content-Sha256-Token)["']"""
            r"""\s*:\s*b?)(["'])[^"']*\2""",
            re.IGNORECASE,
        ),
        lambda m: "%s%s%s%s" % (m.group(1), m.group(2), REDACTED, m.group(2)),
    ),
    # Raw header lines / canonical request lines: x-amz-security-token:VALUE
    (
        re.compile(r"(?im)^(\s*x-amz-security-token\s*:\s*)\S+"),
        lambda m: m.group(1) + REDACTED,
    ),
    (
        re.compile(r"(?im)^(\s*authorization\s*:\s*)\S.*$"),
        lambda m: m.group(1) + REDACTED,
    ),
    # SigV4 Authorization header value anywhere in a line
    (
        re.compile(
            r"AWS4-HMAC-SHA256\s+Credential=[^\s,'\"]+,\s*SignedHeaders=[^\s,'\"]+,\s*Signature=[0-9a-fA-F]+"
        ),
        lambda m: "AWS4-HMAC-SHA256 " + REDACTED,
    ),
    # Presigned URL query parameters (SigV4 and SigV2)
    (
        re.compile(
            r"((?:[?&]|\b)(?:X-Amz-Security-Token|X-Amz-Signature|X-Amz-Credential|"
            r"Signature|AWSAccessKeyId|x-amz-security-token)=)[^&\s'\"<>]+",
            re.IGNORECASE,
        ),
        lambda m: m.group(1) + REDACTED,
    ),
    # Form-encoded STS request bodies: ...&WebIdentityToken=eyJ...&...
    (
        re.compile(r"((?:^|[&?\s'\"])(?:WebIdentityToken|SAMLAssertion)=)[^&\s'\"]+"),
        lambda m: m.group(1) + REDACTED,
    ),
    # Name -> value maps of the shared deny-list (Lambda and App Runner
    # environment, Glue job arguments and connection properties) in a raw
    # response body or a dict repr: the names stay, the values go.
    (
        re.compile(
            r"""(["'])(Variables|RuntimeEnvironmentVariables|EnvironmentVariables|"""
            r"""DefaultArguments|NonOverridableArguments|Arguments|"""
            r"""ConnectionProperties)"""
            r"""\1(\s*:\s*)"""
            r"""\{(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^{}"'])*\}"""
        ),
        lambda m: m.group(1)
        + m.group(2)
        + m.group(1)
        + m.group(3)
        + _redact_flat_mapping_values(m.group(0)[m.group(0).index("{") :]),
    ),
    # [{"name": "X", "value": "..."}] environment lists (ECS, CodeBuild)
    (
        re.compile(
            r"""(?i)((["'])name\2\s*:\s*(["'])(?:\\.|(?!\3).)*\3\s*,\s*"""
            r"""(["'])value\4\s*:\s*)(["'])(?:\\.|(?!\5).)*\5"""
        ),
        lambda m: m.group(1) + m.group(5) + REDACTED + m.group(5),
    ),
    # Any other field the shared deny-list (inventag.security.secret_values)
    # treats as secret, in XML (<ParameterValue>...</ParameterValue>) ...
    (
        re.compile(r"<([A-Za-z][A-Za-z0-9_]*)>([^<]+)</\1>"),
        lambda m: (
            "<%s>%s</%s>" % (m.group(1), REDACTED, m.group(1))
            if is_secret_key(m.group(1)) and m.group(2) != REDACTED
            else m.group(0)
        ),
    ),
    # ... and in JSON or a Python repr ("ParameterValue": "...").
    (
        re.compile(
            r"""(["'])([A-Za-z_][A-Za-z0-9_\-]*)\1(\s*:\s*)(b?)(["'])"""
            r"""((?:\\.|(?!\5).)*)\5"""
        ),
        lambda m: (
            "%s%s%s%s%s%s%s%s"
            % (
                m.group(1),
                m.group(2),
                m.group(1),
                m.group(3),
                m.group(4),
                m.group(5),
                REDACTED,
                m.group(5),
            )
            if is_secret_key(m.group(2)) and m.group(6) not in ("", REDACTED)
            else m.group(0)
        ),
    ),
    # ... and JSON kept as text inside a JSON string, where the quotes are
    # escaped: "Input": "{\"Password\": \"...\"}".
    (
        re.compile(
            r"""(\\+)(["'])([A-Za-z_][A-Za-z0-9_\-]*)\1\2(\s*:\s*)\1\2"""
            r"""((?:(?!\1\2).)*)\1\2"""
        ),
        lambda m: (
            "%s%s%s%s%s%s%s%s%s%s"
            % (
                m.group(1),
                m.group(2),
                m.group(3),
                m.group(1),
                m.group(2),
                m.group(4),
                m.group(1),
                m.group(2),
                REDACTED,
                m.group(1) + m.group(2),
            )
            if is_secret_key(m.group(3)) and m.group(5) not in ("", REDACTED)
            else m.group(0)
        ),
    ),
    # PEM private keys (a Google service-account key as it appears in a log)
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)",
            re.DOTALL,
        ),
        lambda m: REDACTED,
    ),
    # Google OAuth access tokens (ya29.*) and refresh tokens (1//*)
    (
        re.compile(r"\bya29\.[A-Za-z0-9_\-.]{20,}"),
        lambda m: REDACTED,
    ),
    (
        re.compile(r"\b1//[A-Za-z0-9_\-]{20,}"),
        lambda m: REDACTED,
    ),
    # Bearer tokens in an Authorization-style string
    (
        re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]{16,}"),
        lambda m: m.group(1) + REDACTED,
    ),
    # Slack incoming-webhook and Teams/Office webhook URLs carry their secret in the path
    (
        re.compile(
            r"(https://hooks\.slack\.com/(?:services|workflows|triggers)/)[^\s'\"<>]+"
        ),
        lambda m: m.group(1) + REDACTED,
    ),
    (
        re.compile(
            r"(https://[A-Za-z0-9.-]*(?:webhook\.office\.com|logic\.azure\.com)(?::\d+)?/)"
            r"[^\s'\"<>]+"
        ),
        lambda m: m.group(1) + REDACTED,
    ),
]

_FLAT_PAIR = re.compile(
    r"""(["'])((?:\\.|(?!\1).)*)\1(\s*:\s*)(["'])(?:\\.|(?!\4).)*\4"""
)


def _redact_flat_mapping_values(text: str) -> str:
    """``{"A": "x", "B": "y"}`` -> ``{"A": "***REDACTED***", ...}``."""
    return _FLAT_PAIR.sub(
        lambda m: "%s%s%s%s%s%s%s"
        % (
            m.group(1),
            m.group(2),
            m.group(1),
            m.group(3),
            m.group(4),
            REDACTED,
            m.group(4),
        ),
        text,
    )


_registered_secrets = set()
_registered_lock = threading.Lock()

# Secrets shorter than this are not registered: replacing very short strings
# would mangle ordinary log text without protecting anything meaningful.
_MIN_REGISTERED_SECRET_LENGTH = 8


def register_secret(value: Optional[str]) -> None:
    """Never log ``value`` verbatim from now on (process-wide)."""
    if not value or not isinstance(value, str):
        return
    if len(value) < _MIN_REGISTERED_SECRET_LENGTH:
        return
    with _registered_lock:
        _registered_secrets.add(value)


def register_secrets(values: Iterable[Optional[str]]) -> None:
    for value in values:
        register_secret(value)


def clear_registered_secrets() -> None:
    """Forget registered secrets (used by tests)."""
    with _registered_lock:
        _registered_secrets.clear()


def redact(text: object) -> str:
    """Return ``text`` with credentials, tokens and signed URLs removed."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    with _registered_lock:
        secrets = sorted(_registered_secrets, key=len, reverse=True)
    for secret in secrets:
        if secret in text:
            text = text.replace(secret, REDACTED)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFormatter(logging.Formatter):
    """Formatter wrapper that redacts the fully formatted record (incl. tracebacks)."""

    def __init__(self, inner: Optional[logging.Formatter] = None):
        super().__init__()
        self.inner = inner or logging.Formatter()

    def format(self, record: logging.LogRecord) -> str:
        return redact(self.inner.format(record))

    # Keep attribute access (e.g. account-context helpers) working on the inner formatter.
    def __getattr__(self, name):
        return getattr(self.inner, name)


class RedactingFilter(logging.Filter):
    """Filter that redacts a record's message in place."""

    def filter(self, record: logging.LogRecord) -> bool:
        _redact_record(record)
        return True


def _redact_record(record: logging.LogRecord) -> None:
    try:
        message = record.getMessage()
    except Exception:  # pragma: no cover - malformed format args
        message = str(record.msg)
    record.msg = redact(message)
    record.args = ()


_factory_lock = threading.Lock()
_original_factory = None


def install_log_record_redaction() -> None:
    """Redact every log record created in this process (idempotent)."""
    global _original_factory
    with _factory_lock:
        if _original_factory is not None:
            return
        _original_factory = logging.getLogRecordFactory()
        original = _original_factory

        def factory(*args, **kwargs):
            record = original(*args, **kwargs)
            _redact_record(record)
            return record

        logging.setLogRecordFactory(factory)


def uninstall_log_record_redaction() -> None:
    """Restore the log record factory (used by tests)."""
    global _original_factory
    with _factory_lock:
        if _original_factory is None:
            return
        logging.setLogRecordFactory(_original_factory)
        _original_factory = None
