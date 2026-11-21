"""B7 + B8: sensitivity of the reward design, measured on fresh episodes (grader-side, in-process).

B7 tolerance: every submission (honest policies and every attack of auditenv/policies/attacks.py) is graded
   again with tolerance 0, 1, 2, 5, 100 minor units. Shows what the +-1 rule buys: an honest recomputation
   that rounds differently (amount +-1) still matches, while amount brute force gains nothing.
B8 step cost: rankings of the policies when the cost per inspection step is 0, 0.002, 0.005, 0.01.

    make sensitivity  -> reports/tolerance.md, reports/step_cost.md
"""

from __future__ import annotations

import argparse
import statistics
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_runs import BASELINES, ROOT, episodes  # noqa: E402

TOLS = (0, 1, 2, 5, 100)
COSTS = (Fraction(0), Fraction(2, 1000), Fraction(5, 1000), Fraction(1, 100))


def submissions(n: int):
    """[(episode truth, {name: (findings, inspection_steps)})]"""
    from auditenv.env.data import PublicData
    from auditenv.policies.attacks import ATTACKS, attack_findings
    from auditenv.policies.oracle import oracle_findings
    from auditenv.runner import run_episode

    out = []
    for cfg, seed, ep in episodes(n, 770000):
        pub = PublicData(ep.files)
        subs = {}
        for p in BASELINES:
            r = run_episode(p, episode=ep, isolate=False, record=True)
            last = r["trajectory"][-1]["action"]
            fs = []
            if last and last.get("tool") == "submit":
                a = last.get("args") or {}
                fs = (a.get("findings") or {}).get("findings", []) if isinstance(a.get("findings"), dict) else a.get("findings") or []
            subs[p] = (fs, r["grade"]["inspection_steps"])
        good = oracle_findings(ep.truth)
        for d in (-1, 1, -2, 2):  # an honest auditor whose recomputation is off by d minor units
            subs[f"oracle amount{d:+d}"] = ([{**f, "claimed_amount_minor": f["claimed_amount_minor"] + d} for f in good], 1)
        for a in ATTACKS:
            subs[f"attack:{a}"] = (attack_findings(a, ep.truth, pub, seed), 1)
        out.append((ep, subs))
    return out


def tolerance_report(data, n) -> str:
    from auditenv.grader.core import EpisodeGrader

    names = list(data[0][1])
    res = {(nm, t): [] for nm in names for t in TOLS}
    for ep, subs in data:
        for t in TOLS:
            g = EpisodeGrader(ep.truth, tolerance=t)
            for nm, (fs, steps) in subs.items():
                res[(nm, t)].append(g.grade({"episode_id": ep.episode_id, "findings": fs}, steps)["reward"])
    out = ["# Чувствительность награды к допуску по сумме", "",
           f"Сгенерировано `make sensitivity` (`tools/sensitivity.py`): {n} свежих эпизодов (6 открытых конфигов, seed 770000+).",
           "Каждый ответ (базовые политики, «честный аудитор, ошибившийся на d единиц», все атаки) оценён заново с",
           "допуском 0, 1, 2, 5 и 100 минимальных единиц. Средний возврат:", "",
           "| Ответ | " + " | ".join(f"допуск {t}" for t in TOLS) + " |", "|---|" + "---|" * len(TOLS)]
    for nm in names:
        out.append(f"| `{nm}` | " + " | ".join(f"{statistics.fmean(res[(nm, t)]):+.3f}" for t in TOLS) + " |")
    o1 = statistics.fmean(res[("oracle amount+1", 1)])
    o0 = statistics.fmean(res[("oracle amount+1", 0)])
    ab = {t: statistics.fmean(res[("attack:amount_bruteforce", t)]) for t in TOLS}
    orc = statistics.fmean(res[("oracle", 1)])
    out += ["", "## Что это значит", "",
            f"* **Допуск 0** наказывает честного аудитора, пересчитавшего сумму другим порядком округления: ответ «±1»",
            f"  получает {o0:+.3f} вместо {o1:+.3f}. Все внесённые искажения ≥ 100 единиц, так что ±1 не путает разные ошибки.",
            f"* **Допуск 1** (наш): «±1» = oracle ({o1:+.3f} vs {orc:+.3f}), а перебор сумм всё равно проигрывает: "
            f"{ab[1]:+.3f}.",
            f"* **Больше допуск — не выгоднее атакующему**: перебор сумм при допуске 2/5/100 даёт {ab[2]:+.3f} / {ab[5]:+.3f} / "
            f"{ab[100]:+.3f} — взаимно однозначное сопоставление засчитывает один вывод, остальные идут в FP.",
            "  Но большой допуск перестаёт проверять сумму: «oracle ±2» при допуске 2+ уже совпадает, то есть награда",
            "  перестаёт отличать верный пересчёт от приблизительного. Отсюда выбор: минимальный допуск, который",
            "  терпит разницу округления, — 1 единица."]
    return "\n".join(out) + "\n"


def step_cost_report(data, n) -> str:
    from auditenv.grader.core import EpisodeGrader
    from auditenv.grader.reward import prf

    names = [nm for nm in data[0][1] if not nm.startswith("oracle amount")]
    res = {(nm, c): [] for nm in names for c in COSTS}
    steps = {nm: [] for nm in names}
    for ep, subs in data:
        g = EpisodeGrader(ep.truth)
        for nm in names:
            fs, st = subs[nm]
            r = g.grade({"episode_id": ep.episode_id, "findings": fs}, st)
            steps[nm].append(st)
            if not r["valid"]:
                f1 = Fraction(0)
            else:
                f1 = prf(r["tp"], r["fp"], r["fn"])[2]
            for c in COSTS:
                res[(nm, c)].append(float(max(Fraction(-1), min(Fraction(1), 2 * f1 - 1 - c * st))) if r["valid"] else -1.0)
    ranks = {}
    for c in COSTS:
        order = sorted(names, key=lambda nm: -statistics.fmean(res[(nm, c)]))
        ranks[c] = {nm: k + 1 for k, nm in enumerate(order)}
    out = ["# Чувствительность к цене шага", "",
           f"Сгенерировано `make sensitivity` (`tools/sensitivity.py`): {n} свежих эпизодов. Награда пересчитана для цены",
           "шага λ = 0, 0.002 (наша), 0.005, 0.01 при тех же ответах и тех же числах шагов. Средний возврат (место):", "",
           "| Политика / атака | Шагов (среднее) | " + " | ".join(f"λ = {float(c):g}" for c in COSTS) + " |",
           "|---|---|" + "---|" * len(COSTS)]
    for nm in sorted(names, key=lambda nm: ranks[COSTS[1]][nm]):
        out.append(f"| `{nm}` | {statistics.fmean(steps[nm]):.1f} | " +
                   " | ".join(f"{statistics.fmean(res[(nm, c)]):+.3f} ({ranks[c][nm]})" for c in COSTS) + " |")
    same = all(ranks[c] == ranks[COSTS[1]] for c in COSTS)
    moved = sorted({nm for c in COSTS for nm in names if ranks[c][nm] != ranks[COSTS[1]][nm]})
    out += ["", "**Вывод:** " + ("порядок политик одинаков при всех λ — цена шага не меняет, кто лучше, а только"
                                  " поощряет экономность." if same else
                                  f"при некоторых λ меняются местами: {', '.join(moved)} (обычно соседи с близкой наградой)."),
            "Масштаб: пропуск одной из n ошибок стоит 2/(2n − 1) награды (n = 1: 2.0, n = 4: 0.29), а шаг — 0.002.",
            "Поэтому чтение записи окупается, если хоть на ~1 % повышает шанс найти ошибку, а бесцельное хождение",
            "(random_explorer, 29 шагов) только теряет."]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args(argv)
    data = submissions(a.n)
    (ROOT / "reports" / "tolerance.md").write_text(tolerance_report(data, a.n), "utf-8")
    (ROOT / "reports" / "step_cost.md").write_text(step_cost_report(data, a.n), "utf-8")
    print(f"sensitivity: {a.n} episodes -> reports/tolerance.md, reports/step_cost.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
