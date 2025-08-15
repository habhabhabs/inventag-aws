"""
Logging setup for InvenTag CLI with account-specific logging capabilities.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


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

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always debug level for file
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Set up AWS SDK logging
    boto_logger = logging.getLogger("boto3")
    boto_logger.setLevel(logging.WARNING if not debug else logging.DEBUG)

    botocore_logger = logging.getLogger("botocore")
    botocore_logger.setLevel(logging.WARNING if not debug else logging.DEBUG)

    # Store formatters for account context updates
    logger._account_formatters = []
    for handler in logger.handlers:
        if isinstance(handler.formatter, AccountSpecificFormatter):
            logger._account_formatters.append(handler.formatter)

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
