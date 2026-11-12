"""
Logging setup for InvenTag CLI with account-specific logging capabilities.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..security.redaction import RedactingFormatter, install_log_record_redaction
from ..security.safe_output import ensure_private_dir, open_private

# Third-party loggers that can emit request/response details at DEBUG level.
AWS_SDK_LOGGERS = ("boto3", "botocore", "s3transfer", "urllib3")


class AccountSpecificFormatter(logging.Formatter):
    """Custom formatter that includes account context in log messages."""

    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        self.account_context = {}

    def set_account_context(self, account_id: str, account_name: str = ""):
        """Set the current account context for logging."""
        self.account_context = {
            "account_id": account_id,
            "account_name": account_name or account_id,
        }

    def clear_account_context(self):
        """Clear the account context."""
        self.account_context = {}

    def format(self, record):
        # Add account context to the record if available
        if self.account_context:
            account_info = f"[{self.account_context['account_name']}]"
            record.account_prefix = account_info
        else:
            record.account_prefix = ""

        return super().format(record)


def setup_logging(
    verbose: bool = False,
    debug: bool = False,
    log_file: Optional[str] = None,
    account_specific: bool = True,
) -> logging.Logger:
    """
    Set up comprehensive logging for InvenTag CLI.

    Args:
        verbose: Enable verbose logging (INFO level)
        debug: Enable debug logging (DEBUG level)
        log_file: Optional log file path
        account_specific: Enable account-specific logging format

    Returns:
        Configured logger instance
    """
    # Determine log level
    if debug:
        log_level = logging.DEBUG
    elif verbose:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    # Create logger
    logger = logging.getLogger("inventag")
    logger.setLevel(log_level)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatters
    if account_specific:
        console_format = (
            "%(asctime)s - %(account_prefix)s%(name)s - %(levelname)s - %(message)s"
        )
        file_format = "%(asctime)s - %(account_prefix)s%(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        console_formatter = AccountSpecificFormatter(console_format)
        file_formatter = AccountSpecificFormatter(file_format)
    else:
        console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        file_format = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        console_formatter = logging.Formatter(console_format)
        file_formatter = logging.Formatter(file_format)

    # Redact credentials, tokens and signed URLs from everything we log.
    install_log_record_redaction()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(RedactingFormatter(console_formatter))
    logger.addHandler(console_handler)

    # File handler (if specified). The log file is created owner-only (0600)
    # because debug logs describe the scanned accounts in detail.
    if log_file:
        log_path = Path(log_file)
        ensure_private_dir(log_path.parent)
        with open_private(log_path, "a"):
            pass

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always debug level for file
        file_handler.setFormatter(RedactingFormatter(file_formatter))
        logger.addHandler(file_handler)

    # AWS SDK logging. At --debug, botocore logs request headers and raw
    # response bodies (including sts:AssumeRole credentials). Route those
    # records only through our redacting handlers instead of letting them
    # propagate to a root handler that does not redact.
    for sdk_logger_name in AWS_SDK_LOGGERS:
        sdk_logger = logging.getLogger(sdk_logger_name)
        sdk_logger.setLevel(logging.DEBUG if debug else logging.WARNING)
        sdk_logger.handlers.clear()
        for handler in logger.handlers:
            sdk_logger.addHandler(handler)
        sdk_logger.propagate = False

    # Store formatters for account context updates
    logger._account_formatters = []
    for handler in logger.handlers:
        formatter = handler.formatter
        if isinstance(formatter, RedactingFormatter):
            formatter = formatter.inner
        if isinstance(formatter, AccountSpecificFormatter):
            logger._account_formatters.append(formatter)

    return logger


def set_account_context(
    logger: logging.Logger, account_id: str, account_name: str = ""
):
    """Set account context for all account-specific formatters."""
    if hasattr(logger, "_account_formatters"):
        for formatter in logger._account_formatters:
            formatter.set_account_context(account_id, account_name)


def clear_account_context(logger: logging.Logger):
    """Clear account context for all account-specific formatters."""
    if hasattr(logger, "_account_formatters"):
        for formatter in logger._account_formatters:
            formatter.clear_account_context()


class LoggingContext:
    """Context manager for account-specific logging."""

    def __init__(self, logger: logging.Logger, account_id: str, account_name: str = ""):
        self.logger = logger
        self.account_id = account_id
        self.account_name = account_name

    def __enter__(self):
        set_account_context(self.logger, self.account_id, self.account_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_account_context(self.logger)
