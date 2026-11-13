"""
The account a log line belongs to, kept per thread of execution.

``AccountSpecificFormatter`` prints the account name in front of each log line
(``--disable-account-logging`` turns that off). Accounts are scanned in
parallel, so the name is a context variable: each worker sets its own.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, Iterator, Optional

_current_account: ContextVar[Optional[Dict[str, str]]] = ContextVar(
    "inventag_log_account", default=None
)


def current_account() -> Optional[Dict[str, str]]:
    """The account context of the running code, or None."""
    return _current_account.get()


@contextmanager
def account_log_context(account_id: str, account_name: str = "") -> Iterator[None]:
    """Prefix log lines written inside the block with the account name."""
    token = _current_account.set(
        {"account_id": account_id, "account_name": account_name or account_id}
    )
    try:
        yield
    finally:
        _current_account.reset(token)
