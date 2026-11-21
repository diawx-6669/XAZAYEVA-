#!/bin/sh
# A8: report before making the repository public / tagging. Read-only: nothing is deleted or rewritten.
# Lists branches other than main, scans the WHOLE git history for secrets (tokens, keys, a real
# AUDITENV_SEED_SALT value, jury_sim/work/), checks .gitignore and blobs > 5 MB. Exit code 1 on findings.
set -e
cd "$(dirname "$0")/.."
git fetch --quiet origin 2>/dev/null || echo "(offline: remote branches as of the last fetch)"
exec "${PYTHON:-python3}" tools/prepublish.py
