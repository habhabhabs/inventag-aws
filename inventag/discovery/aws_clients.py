"""One place for how discovery creates boto3 clients.

Every discovery client gets the same retry settings, so a throttled call
(``Throttling``, ``TooManyRequestsException``, ``RequestLimitExceeded`` ...)
is retried with backoff instead of losing that service's resources.

- Retry mode ``standard`` with up to 10 attempts in total, the first call
  included (botocore's default is also ``standard``, with 3 attempts).
  ``standard`` retries throttling and transient errors with exponential
  backoff and jitter.
- If the user set ``AWS_RETRY_MODE`` or ``AWS_MAX_ATTEMPTS`` in the
  environment, those values win and InvenTag does not override them.
  (Values set only in ``~/.aws/config`` are overridden by the settings above.)

boto3 sessions are not thread-safe, but discovery creates clients from
worker threads. Client creation is serialised with a lock; the clients
themselves are thread-safe and are used without the lock.

Client cache: after :func:`enable_client_cache` on a session, that session
gets one client per (service, region, retry settings), created under the
lock and shared by threads, so threads on one API share one connection pool
(and one SDK retry quota). A paginator or page iterator is never shared:
create one per call. Sessions without the cache get a new client per call.
"""

import os
import threading
import weakref
from typing import Optional

from botocore.config import Config

RETRY_MODE = "standard"
MAX_ATTEMPTS = 10

_CREATE_LOCK = threading.RLock()
# session -> {(service, region, retry environment): client}; under _CREATE_LOCK
_CACHES: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def retry_config() -> Config:
    """The botocore ``Config`` used for every discovery client."""
    if os.environ.get("AWS_RETRY_MODE") or os.environ.get("AWS_MAX_ATTEMPTS"):
        return Config()
    return Config(retries={"mode": RETRY_MODE, "total_max_attempts": MAX_ATTEMPTS})


def enable_client_cache(session) -> None:
    """Share one client per service, region and retry settings on ``session``."""
    with _CREATE_LOCK:
        _CACHES.setdefault(session, {})


def _new_client(session, service_name: str, region_name: Optional[str]):
    if region_name:
        return session.client(
            service_name, region_name=region_name, config=retry_config()
        )
    return session.client(service_name, config=retry_config())


def create_client(session, service_name: str, region_name: Optional[str] = None):
    """Create a client with the shared retry settings, thread-safely.

    With the session's cache turned on, return the cached client instead.
    """
    with _CREATE_LOCK:
        cache = _CACHES.get(session)
        if cache is None:
            return _new_client(session, service_name, region_name)
        key = (
            service_name,
            region_name or None,
            os.environ.get("AWS_RETRY_MODE"),
            os.environ.get("AWS_MAX_ATTEMPTS"),
        )
        client = cache.get(key)
        if client is None:
            client = _new_client(session, service_name, region_name)
            cache[key] = client
        return client
