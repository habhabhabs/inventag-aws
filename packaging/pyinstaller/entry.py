"""PyInstaller entry point: the same function as the ``inventag`` console script."""

import sys

from inventag.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
