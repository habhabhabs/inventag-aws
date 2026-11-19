#!/usr/bin/env bash
# Run what the CI workflows run, on this host. See scripts/dev/ci_local.py --help.
#   scripts/dev/ci-local.sh env --venv .ci-venv --create
#   scripts/dev/ci-local.sh run application --venv .ci-venv
exec "${PYTHON:-python3}" "$(dirname "$0")/ci_local.py" "$@"
