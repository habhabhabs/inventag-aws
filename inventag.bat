@echo off
REM InvenTag - AWS Cloud Governance Platform
REM Wrapper script with automatic Python detection

setlocal enabledelayedexpansion

REM Function to detect the best Python command
set PYTHON_CMD=

REM Check for python3 first (preferred for modern systems)
python3 --version >nul 2>&1
if !errorlevel! == 0 (
    REM Verify it's Python 3.8+
    python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
    if !errorlevel! == 0 (
        set PYTHON_CMD=python3
        goto :run_inventag
    )
)

REM Check for python command
python --version >nul 2>&1
if !errorlevel! == 0 (
    REM Verify it's Python 3.8+
    python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
    if !errorlevel! == 0 (
        set PYTHON_CMD=python
        goto :run_inventag
    )
)

REM Check for py launcher (Windows Python Launcher)
py -3 --version >nul 2>&1
if !errorlevel! == 0 (
    REM Verify it's Python 3.8+
    py -3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
    if !errorlevel! == 0 (
        set PYTHON_CMD=py -3
        goto :run_inventag
    )
)

REM No suitable Python found
echo Error: No suitable Python interpreter found.
echo InvenTag requires Python 3.8 or later.
echo.
echo Please install Python 3.8+ and ensure it's available:
echo   - Download from https://python.org
echo   - Or install from Microsoft Store
echo   - Make sure Python is added to PATH during installation
echo.
echo Available Python commands tried: python3, python, py -3
exit /b 1

:run_inventag
REM Run InvenTag with detected Python command
!PYTHON_CMD! "%~dp0inventag_cli.py" %*