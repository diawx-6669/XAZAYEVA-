#!/bin/sh
# Jury simulation: all items 2-6. Black box: only CLI calls, no `import auditenv` in jury_sim/.
# Salt: jury_sim/work/salt.txt (created once, random). Results: jury_sim/work/*.json
set -e
cd "$(dirname "$0")"
PY=${PY:-python3}
$PY closed_run.py
$PY transform_check.py
$PY replay_check.py
$PY reward_attacks.py
$PY contract_check.py
$PY timing_probe.py
$PY attack_isolation.py
