#!/bin/bash

# InvenTag - AWS Cloud Governance Platform
# Wrapper script with automatic Python detection

# Function to detect the best Python command
detect_python() {
    # Check for python3 first (preferred for modern systems)
    if command -v python3 &> /dev/null; then
        # Verify it's Python 3.8+
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
            echo "python3"
            return 0
        fi
    fi
    
    # Check for python command
    if command -v python &> /dev/null; then
        # Verify it's Python 3.8+
        if python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
            echo "python"
            return 0
        fi
    fi
    
    echo ""
    return 1
}

# Detect Python command
PYTHON_CMD=$(detect_python)

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: No suitable Python interpreter found." >&2
    echo "InvenTag requires Python 3.8 or later." >&2
    echo "" >&2
    echo "Please install Python 3.8+ and ensure it's available as 'python3' or 'python':" >&2
    echo "  - On Ubuntu/Debian: sudo apt install python3" >&2
    echo "  - On macOS: brew install python3" >&2
    echo "  - On Windows: Download from https://python.org" >&2
    exit 1
fi

# Run InvenTag with detected Python command
exec "$PYTHON_CMD" "$(dirname "$0")/inventag_cli.py" "$@"