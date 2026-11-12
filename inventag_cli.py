#!/usr/bin/env python3
"""
InvenTag CLI Entry Point

Main entry point for the InvenTag command-line interface.
This script provides comprehensive multi-account AWS cloud governance
with BOM generation, compliance checking, and advanced reporting.
"""

import sys

# Keep everything above the version check free of syntax newer than
# Python 2.7 / 3.0 (no f-strings, no annotations): an old interpreter must
# reach the message below, not a SyntaxError.
MIN_PYTHON = (3, 11)


def require_supported_python(version_info=None):
    """Exit with a plain message when run on Python older than MIN_PYTHON."""
    version_info = sys.version_info if version_info is None else version_info
    if tuple(version_info[:2]) < MIN_PYTHON:
        sys.exit(
            "Error: InvenTag requires Python %d.%d or later; this interpreter is "
            "Python %d.%d.\nInstall a newer Python (https://www.python.org/downloads/) "
            "and run InvenTag with it." % (MIN_PYTHON + tuple(version_info[:2]))
        )


def main():
    require_supported_python()

    from pathlib import Path

    # Add the current directory to Python path to ensure inventag package is found
    sys.path.insert(0, str(Path(__file__).parent))

    from inventag.cli.main import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
