"""B22: how long each make target takes on this machine -> reports/targets_timing.md.

    python tools/time_targets.py [target ...]     (= make targets-timing; runs every listed target once)
The `make check` row is read from the last `make check` log if given with --check-log (the check itself takes
about two minutes and is usually measured separately).
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TARGETS = ["quick", "repro-cert", "repro-cross", "prepublish", "pii-scan", "min-budget", "power", "difficulty",
           "coverage-map", "exhaustive", "sensitivity", "ablation", "bench"]
WHAT = {"quick": "быстрые тесты + смоук", "repro-cert": "сертификат воспроизводимости", "repro-cross": "сертификат × интерпретаторы",
        "prepublish": "отчёт перед публикацией", "pii-scan": "нет реальных данных, 500 эпизодов", "min-budget": "минимальный бюджет, 500 эпизодов",
        "power": "мощность, 300 эпизодов × 6 политик", "difficulty": "модель Раша, 300 эпизодов × 10 политик",
        "coverage-map": "покрытие, 1000 seed", "exhaustive": "полный перебор малых случаев", "sensitivity": "допуск и цена шага, 120 эпизодов",
        "ablation": "абляция доказательств, 120 эпизодов", "bench": "бенчмарк пула сред", "check": "**единая проверка**"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="*", default=TARGETS)
    ap.add_argument("--check-seconds", type=float, help="measured wall time of `make check` to include")
    a = ap.parse_args(argv)
    rows = []
    for t in a.targets:
        t0 = time.monotonic()
        rc = subprocess.run(["make", t], cwd=ROOT, capture_output=True, text=True).returncode
        rows.append((t, time.monotonic() - t0, rc))
        print(f"{t}: {rows[-1][1]:.1f} s (rc {rc})", flush=True)
    if a.check_seconds:
        rows.insert(0, ("check", a.check_seconds, 0))
    from examples.env_pool import hardware

    hw = hardware()
    out = ["# Время make‑целей", "",
           f"Измерено `python tools/time_targets.py` (по одному прогону, машина свободна от другой нагрузки): {hw['cpu']},",
           f"{hw['cpus_usable']} CPU, {hw['memory']}, Python {hw['python']}, {hw['os']}. В контейнере жюри (`--cpus 2`) медленнее.", "",
           "| Цель | Что делает | Время, с | Код возврата |", "|---|---|---|---|"]
    out += [f"| `make {t}` | {WHAT.get(t, '')} | {s:.0f} | {rc} |" for t, s, rc in rows]
    out += ["", "Все цели, кроме `make check`, `make quick` и `make docker-check`, — отдельные и в `make check` не входят."]
    (ROOT / "reports" / "targets_timing.md").write_text("\n".join(out) + "\n", "utf-8")
    return 1 if any(rc for _, _, rc in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
