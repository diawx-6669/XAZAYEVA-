"""B10: the reward in closed form - a lookup table for every small (TP, FP, FN) and a few step counts.

Values come from auditenv/grader/reward.py (prf + shared_reward); tests/test_round4_reward_table.py recomputes
them with an independent formula and checks the committed file.

    python tools/reward_table.py   -> reports/reward_table.md
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STEPS = (0, 10, 15, 50, 99)
TRUTHS = (0, 1, 2, 3, 4)
MAX_FP = 3


def rows():
    from auditenv.grader.reward import prf, shared_reward

    for n in TRUTHS:
        for tp in range(n + 1):
            for fp in range(MAX_FP + 1):
                fn = n - tp
                f1 = prf(tp, fp, fn)[2]
                yield n, tp, fp, fn, float(f1), [shared_reward(f1, s) for s in STEPS]


def render() -> str:
    out = ["# Таблица наград", "",
           "Сгенерировано `python tools/reward_table.py` из `auditenv/grader/reward.py`; тест сверяет каждое число с независимой",
           "формулой `clip(2·F1 − 1 − 0.002·шаги, −1, 1)`, F1 = 2TP / (2TP + FP + FN), F1 = 1 при пустых эталоне и ответе,",
           "F1 = 0 при пустом эталоне и непустом ответе. «Шаги» — шаги осмотра до `submit` (без самого `submit`);",
           "любой обрыв (лимит шагов, тайм‑аут) — пустой ответ и 100 шагов.", ""]
    cur = None
    for n, tp, fp, fn, f1, rs in rows():
        if n != cur:
            cur = n
            out += ["", f"## Эталон: {n} ошибок", "", "| TP | FP | FN | F1 | " + " | ".join(f"{s} шагов" for s in STEPS) + " |",
                    "|---|---|---|---|" + "---|" * len(STEPS)]
        out.append(f"| {tp} | {fp} | {fn} | {f1:.3f} | " + " | ".join(f"{r:+.3f}" for r in rs) + " |")
    out += ["", "Читать так: найти все ошибки за 15 шагов без ложных — +0.970; одна ложная при одной найденной из одной — F1 = 0.667,",
            "за 15 шагов +0.303; пустой ответ на книге с ошибками — −1 при любом числе шагов."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    (ROOT / "reports" / "reward_table.md").write_text(render(), "utf-8")
    print("reward-table: wrote reports/reward_table.md")
