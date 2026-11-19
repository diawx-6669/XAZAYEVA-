#!/bin/sh
# The single verification command (used by `make check` and by the container).
set -e
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && [ -z "${PYTHON:-}" ] && PY=.venv/bin/python
export PYTHONPATH="$PWD" PYTHONHASHSEED=0 TZ=UTC
"$PY" --version
"$PY" -m pytest -q
"$PY" -m auditenv check
