"""
Security controls shared across InvenTag.

* :mod:`.redaction` - remove credentials, tokens and signed URLs from logs
* :mod:`.read_only_guard` - block non-read-only AWS API calls (botocore hook)
* :mod:`.arn` - validate role names/ARNs and build role ARNs per account
* :mod:`.safe_output` - private file permissions, safe file names,
  spreadsheet formula neutralisation
* :mod:`.iam_policy` - least-privilege read-only IAM policy
"""

from .read_only_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    install_global_guard,
    uninstall_global_guard,
    get_installed_guard,
)
from .redaction import redact, register_secret, install_log_record_redaction

__all__ = [
    "ReadOnlyGuard",
    "ReadOnlyViolationError",
    "install_global_guard",
    "uninstall_global_guard",
    "get_installed_guard",
    "redact",
    "register_secret",
    "install_log_record_redaction",
]
