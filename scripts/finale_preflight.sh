#!/bin/sh
# Offline finale pre-flight (<= 1 minute, no network): image -> contract tests -> demo.
# Run it on the finale laptop BEFORE the talk: make finale-preflight
set -e
cd "$(dirname "$0")/.."
t0=$(date +%s)
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && PY=.venv/bin/python
TESTS="tests/test_contract.py tests/test_contract_json.py tests/test_calculator.py"
if command -v docker >/dev/null 2>&1 && docker image inspect auditenv >/dev/null 2>&1; then
  echo "[1/3] image auditenv: $(docker image inspect -f '{{.Id}}' auditenv | cut -c1-19)..., built $(docker image inspect -f '{{.Created}}' auditenv | cut -c1-19)"
  echo "[2/3] contract + reward smoke tests (offline container)"
  docker run --rm --network none --cpus 2 --memory 4g auditenv python -m pytest -q -x -m "not slow" $TESTS
  echo "[3/3] demo: interacting errors step by step"
  docker run --rm --network none --cpus 2 --memory 4g auditenv python -m auditenv demo --seed 9008 --config interaction-heavy | tail -12
else
  echo "[1/3] no docker image 'auditenv' (offline: docker load -i auditenv.tar) - running locally with $PY"
  echo "[2/3] contract + reward smoke tests"
  PYTHONPATH=. PYTHONHASHSEED=0 TZ=UTC "$PY" -m pytest -q -x -m "not slow" $TESTS
  echo "[3/3] demo: interacting errors step by step"
  PYTHONPATH=. PYTHONHASHSEED=0 TZ=UTC "$PY" -m auditenv demo --seed 9008 --config interaction-heavy | tail -12
fi
t1=$(date +%s)
echo "finale-preflight: OK in $(expr "$t1" - "$t0") s"
