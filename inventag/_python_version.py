"""
Minimum supported Python version.

This module is imported first by ``inventag/__init__.py``. Keep it free of
syntax newer than Python 2.7 / 3.0 (no f-strings, no annotations), so that an
old interpreter reaches the plain error message below instead of failing with
a SyntaxError somewhere else in the package.
"""

import sys

MIN_PYTHON = (3, 11)


def unsupported_python_message(version_info=None):
    """Return an error message if ``version_info`` is too old, else ``None``."""
    version_info = sys.version_info if version_info is None else version_info
    if tuple(version_info[:2]) >= MIN_PYTHON:
        return None
    return (
        "InvenTag requires Python %d.%d or later; this interpreter is Python %d.%d. "
        "Install a newer Python (https://www.python.org/downloads/) and run "
        "InvenTag with it." % (MIN_PYTHON + tuple(version_info[:2]))
    )


def check_python_version(version_info=None):
    """Raise ``ImportError`` with a plain message on an unsupported Python."""
    message = unsupported_python_message(version_info)
    if message:
        raise ImportError(message)
