#!/bin/sh
# The single verification command (used by `make check` and by the container).
set -e
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && [ -z "${PYTHON:-}" ] && PY=.venv/bin/python
export PYTHONPATH="$PWD" PYTHONHASHSEED=0 TZ=UTC
"$PY" --version
if [ -n "${AUDITENV_SEED_SALT:-}" ]; then
  echo "WARNING: AUDITENV_SEED_SALT is set. Open tests ignore it (conftest), but 'auditenv check' will" >&2
  echo "         generate SALTED episodes that differ from the committed open ones. Unset it for make check." >&2
fi
"$PY" -m pytest -q
"$PY" -m auditenv check
"$PY" -m auditenv docs-check
