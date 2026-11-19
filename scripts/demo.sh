#!/usr/bin/env bash
# Demo: check -> interacting-error episode solved step by step by simple_reconcile ->
# flag_all attack -> transformed twin with the same reward.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)}"
export PYTHONPATH="$PWD" PYTHONHASHSEED=0 TZ=UTC

if [ "${SKIP_CHECK:-0}" != "1" ]; then
  echo "=== 1. make check (scoreboard) ==="
  make -s check | sed -n '/## Табло/,/^$/p;/| \*\*Итого/p'
fi

echo; echo "=== 2. interacting errors (interaction-heavy #9008), simple_reconcile step by step ==="
$PY -m auditenv demo --seed 9008 --config interaction-heavy

echo; echo "=== 3. truth for the same episode (grader side only) ==="
$PY - <<'PYEOF'
from auditenv.generator.episode import generate_episode
ep = generate_episode(9008, "interaction-heavy")
print("scenarios:", ep.provenance["plan"]["scenarios"])
for i in ep.truth["issues"]:
    print(f"  {i['issue_id']} {i['type']:<19} {i['affected_ids']} {i['expected_amount_minor']} {i['currency']}")
PYEOF

echo; echo "=== 4. flag_all attack on the same episode ==="
$PY - <<'PYEOF'
from auditenv.generator.episode import generate_episode
from auditenv.runner import run_episode
ep = generate_episode(9008, "interaction-heavy")
for pol in ("flag_all", "oracle"):
    g = run_episode(pol, episode=ep)["grade"]
    print(f"  {pol:<10} TP={g['tp']} FP={g['fp']} FN={g['fn']} F1={g['f1']:.3f} reward={g['reward']:+.3f}")
PYEOF

echo; echo "=== 5. twin after transforms (rows permuted, every ID renamed) ==="
$PY - <<'PYEOF'
from auditenv.generator.episode import generate_episode
from auditenv.generator.transforms import transform_episode
from auditenv.runner import run_episode
ep = generate_episode(9008, "interaction-heavy")
twin, mapping = transform_episode(ep, 4242)
print(f"  {ep.episode_id} -> {twin.episode_id}, {len(mapping)} IDs renamed")
for name, e in (("original", ep), ("twin", twin)):
    o = run_episode("oracle", episode=e)["grade"]
    s = run_episode("simple_reconcile", episode=e)["grade"]
    print(f"  {name:<8} oracle reward={o['reward']:+.3f} F1={o['f1']:.3f} | simple_reconcile reward={s['reward']:+.3f} F1={s['f1']:.3f}")
PYEOF
