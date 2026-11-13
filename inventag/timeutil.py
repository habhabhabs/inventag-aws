"""
UTC timestamp helpers.

InvenTag writes timestamps as ISO 8601 strings in UTC **with** an explicit
offset, for example ``2026-11-12T10:42:47.647344+00:00``
(``datetime.now(timezone.utc).isoformat()``).

Releases up to v4.2.27 wrote some fields (``discovered_at`` on resources,
``check_timestamp`` in compliance results) with the deprecated
``datetime.utcnow`` call, which produces the same instant **without** an offset:
``2026-11-12T10:42:47.647344``. Those strings are still present in existing
state snapshots and reports, so anything that reads a stored timestamp must go
through :func:`parse_timestamp`, which treats a string without an offset as
UTC. Python refuses to compare or subtract naive and aware datetimes, so do
not call ``datetime.fromisoformat`` on stored values directly.

Both forms sort correctly as plain strings against each other, because they
share the same ``YYYY-MM-DDTHH:MM:SS[.ffffff]`` prefix and are both UTC.
"""

from datetime import datetime, timezone
from typing import Union

__all__ = ["utc_now", "utc_now_iso", "parse_timestamp"]


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Current UTC time as an ISO 8601 string with a ``+00:00`` offset."""
    return utc_now().isoformat()


def parse_timestamp(value: Union[str, datetime]) -> datetime:
    """Parse a stored timestamp into a timezone-aware UTC datetime.

    Accepts the current format (with offset), the legacy format without an
    offset (taken as UTC) and a trailing ``Z``. Other offsets are converted
    to UTC. Raises ``ValueError`` for text that is not an ISO 8601 timestamp
    and ``TypeError`` for other types.
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    else:
        raise TypeError(
            f"timestamp must be str or datetime, not {type(value).__name__}"
        )

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
