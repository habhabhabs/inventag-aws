#!/usr/bin/env python3
"""
InvenTag CLI Entry Point

Main entry point for the InvenTag command-line interface.
This script provides comprehensive multi-account AWS cloud governance
with BOM generation, compliance checking, and advanced reporting.
"""

import sys
from pathlib import Path

# Add the current directory to Python path to ensure inventag package is found
sys.path.insert(0, str(Path(__file__).parent))

from inventag.cli.main import main

if __name__ == '__main__':
    main()