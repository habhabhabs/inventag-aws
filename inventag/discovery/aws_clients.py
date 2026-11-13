"""One place for how discovery creates boto3 clients.

Every discovery client gets the same retry settings, so a throttled call
(``Throttling``, ``TooManyRequestsException``, ``RequestLimitExceeded`` ...)
is retried with backoff instead of losing that service's resources.

- Retry mode ``standard`` with up to 10 attempts in total, the first call
  included (botocore's default is
  ``legacy`` with 5). ``standard`` retries throttling and transient errors
  with exponential backoff and jitter.
- If the user set ``AWS_RETRY_MODE`` or ``AWS_MAX_ATTEMPTS`` in the
  environment, those values win and InvenTag does not override them.
  (Values set only in ``~/.aws/config`` are overridden by the settings above.)

boto3 sessions are not thread-safe, but discovery creates clients from
worker threads. Client creation is serialised with a lock; the clients
themselves are thread-safe and are used without the lock.
"""

import os
import threading
from typing import Optional

from botocore.config import Config

RETRY_MODE = "standard"
MAX_ATTEMPTS = 10

_CREATE_LOCK = threading.RLock()


def retry_config() -> Config:
    """The botocore ``Config`` used for every discovery client."""
    if os.environ.get("AWS_RETRY_MODE") or os.environ.get("AWS_MAX_ATTEMPTS"):
        return Config()
    return Config(retries={"mode": RETRY_MODE, "total_max_attempts": MAX_ATTEMPTS})


def create_client(session, service_name: str, region_name: Optional[str] = None):
    """Create a client with the shared retry settings, thread-safely."""
    with _CREATE_LOCK:
        if region_name:
            return session.client(
                service_name, region_name=region_name, config=retry_config()
            )
        return session.client(service_name, config=retry_config())
