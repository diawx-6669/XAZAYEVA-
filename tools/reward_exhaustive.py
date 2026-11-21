"""A20: exhaustive enumeration of small grading cases (the real grader, no mocks).

Universe: a pool of up to 3 issues of different types, each with 1-2 evidence sets; a finding universe
derived from the pool - for every issue the correct finding and its near misses (wrong type, amount
+1 = inside tolerance, amount +2 = outside, wrong currency, incomplete evidence, evidence of the
other set) plus a guessed ID. Truth = every subset of the pool; submission = every MULTISET of
findings up to size K. For every (truth, submission):
  1. no dominating dishonest strategy: the honest answer scores >= any submission, and a submission
     scores as much only if it is TP-equivalent to it (all issues matched, no FP);
  2. monotone in TP/FP: adding one finding that is an FP never raises the reward; adding one that
     raises TP without adding an FP never lowers it (checked on every edge of the enumeration tree);
  3. order invariance: reversed and rotated submissions give identical reward and F1;
  4. step cost: reward(k) - reward(k + 1) = 0.002 exactly (unless clipped), at k = 0 and k = 50.

    make exhaustive                       -> level "full" + reports/reward_exhaustive.md
    pytest tests/test_reward_exhaustive.py   (in make check: level "small")
"""

from __future__ import annotations

import itertools
import sys
import time
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POOL = [
    {"type": "duplicate_invoice", "affected_ids": ["INV-A"], "expected_amount_minor": 100,
     "evidence_sets": [["DOC-A1", "DOC-A2", "JE-A"]]},
    {"type": "fx_rate", "affected_ids": ["PAY-B"], "expected_amount_minor": 250,
     "evidence_sets": [["DOC-B", "JE-B", "fx:2026-01-05:USD:KZT", "policy"], ["DOC-B", "JE-B2", "fx:2026-01-05:USD:KZT", "policy"]]},
    {"type": "payment_allocation", "affected_ids": ["PAY-C"], "expected_amount_minor": 400,
     "evidence_sets": [["DOC-C", "DOC-C2", "JE-C"]]},
]
LEVELS = {"tiny": {"pool": 2, "k": 2}, "small": {"pool": 2, "k": 3}, "full": {"pool": 3, "k": 4}}


def correct(iss: dict) -> dict:
    return {"type": iss["type"], "affected_ids": list(iss["affected_ids"]), "claimed_amount_minor": iss["expected_amount_minor"],
            "currency": "KZT", "evidence_ids": list(iss["evidence_sets"][0]), "explanation": ""}


def universe(pool: list) -> list:
    """(label, finding, is_honest_match_of_pool_index or None)"""
    out = []
    other = {"duplicate_invoice": "fx_rate", "fx_rate": "period_cutoff", "payment_allocation": "duplicate_invoice"}
    for k, iss in enumerate(pool):
        c = correct(iss)
        out.append((f"I{k}:correct", c))
        out.append((f"I{k}:amount+1", {**c, "claimed_amount_minor": c["claimed_amount_minor"] + 1}))
        out.append((f"I{k}:amount+2", {**c, "claimed_amount_minor": c["claimed_amount_minor"] + 2}))
        out.append((f"I{k}:wrong_type", {**c, "type": other[iss["type"]]}))
        out.append((f"I{k}:wrong_currency", {**c, "currency": "USD"}))
        out.append((f"I{k}:evidence_missing_one", {**c, "evidence_ids": c["evidence_ids"][:-1]}))
        if len(iss["evidence_sets"]) > 1:
            out.append((f"I{k}:other_set", {**c, "evidence_ids": list(iss["evidence_sets"][1])}))
    out.append(("guess", {"type": "duplicate_invoice", "affected_ids": ["INV-Z"], "claimed_amount_minor": 100,
                          "currency": "KZT", "evidence_ids": ["DOC-Z"], "explanation": ""}))
    return out


def run(level: str = "small") -> dict:
    from auditenv.grader.core import EpisodeGrader

    cfg = LEVELS[level]
    pool = POOL[: cfg["pool"]]
    U = universe(pool)
    stats = {"level": level, "truths": 0, "submissions": 0, "grades": 0, "edges": 0, "orders": 0, "step_checks": 0,
             "universe": len(U), "max_findings": cfg["k"], "violations": []}
    t0 = time.perf_counter()
    for r in range(len(pool) + 1):
        for subset in itertools.combinations(range(len(pool)), r):
            issues = [{**pool[i], "issue_id": f"ISS-{n + 1:03d}", "currency": "KZT"} for n, i in enumerate(subset)]
            g = EpisodeGrader({"episode_id": "ep-x", "issues": issues, "tolerance_minor": 1})
            stats["truths"] += 1

            def grade(fs, steps=0):
                stats["grades"] += 1
                return g.grade({"episode_id": "ep-x", "findings": [f for _, f in fs]}, inspection_steps=steps)

            honest = grade([(None, correct(pool[i])) for i in subset])
            cache = {}
            for k in range(cfg["k"] + 1):
                for combo in itertools.combinations_with_replacement(range(len(U)), k):
                    fs = [U[i] for i in combo]
                    res = grade(fs)
                    cache[combo] = res
                    stats["submissions"] += 1
                    # 1. no dominating dishonest strategy
                    if res["reward"] > honest["reward"] or (res["reward"] == honest["reward"] and not (res["fp"] == 0 and res["fn"] == 0)):
                        stats["violations"].append(("dominates_honest", subset, [l for l, _ in fs]))
                    # 2. monotone along the edge parent -> combo (combo = parent + one finding)
                    if k:
                        par = cache[combo[:-1]]
                        stats["edges"] += 1
                        if res["tp"] == par["tp"] and res["reward"] > par["reward"]:
                            stats["violations"].append(("fp_raised_reward", subset, [l for l, _ in fs]))
                        if res["tp"] > par["tp"] and res["fp"] == par["fp"] and res["reward"] < par["reward"]:
                            stats["violations"].append(("tp_lowered_reward", subset, [l for l, _ in fs]))
                    # 3. order invariance
                    if k >= 2:
                        for perm in (fs[::-1], fs[1:] + fs[:1]):
                            o = grade(perm)
                            stats["orders"] += 1
                            if (o["reward"], o["f1"], o["tp"]) != (res["reward"], res["f1"], res["tp"]):
                                stats["violations"].append(("order", subset, [l for l, _ in fs]))
                    # 4. exactly 0.002 per inspection step (where the clip does not bind)
                    if k <= 2:
                        for s in (0, 50):
                            a, b = grade(fs, s), grade(fs, s + 1)
                            stats["step_checks"] += 1
                            raw = 2 * Fraction(res["f1"]).limit_denominator(1000) - 1 - Fraction(2, 1000) * (s + 1)
                            if -1 < raw < 1 and abs((a["reward"] - b["reward"]) - 0.002) > 1e-12:
                                stats["violations"].append(("step_cost", subset, [l for l, _ in fs], s))
    stats["seconds"] = round(time.perf_counter() - t0, 2)
    return stats


def render(st: dict) -> str:
    return "\n".join([
        "# Полный перебор малых случаев награды", "",
        "Сгенерировано `make exhaustive` (`tools/reward_exhaustive.py`, уровень `full`); в `make check` идёт уровень `small`",
        "(`tests/test_reward_exhaustive.py`). Оценщик — настоящий (`auditenv/grader/core.py::EpisodeGrader`), без заглушек.", "",
        "| Что | Число |", "|---|---|",
        f"| Эталонов (все подмножества пула из {LEVELS[st['level']]['pool']} issue разных типов) | {st['truths']} |",
        f"| Выводов во вселенной (верный + 5–6 «почти верных» на issue + угаданный ID) | {st['universe']} |",
        f"| Ответов на эталон: все мультимножества до {st['max_findings']} выводов | {st['submissions'] // max(1, st['truths'])} |",
        f"| Проверено пар (эталон, ответ) | {st['submissions']} |",
        f"| Рёбер «ответ + 1 вывод» (монотонность по TP/FP) | {st['edges']} |",
        f"| Перестановок (инвариантность к порядку) | {st['orders']} |",
        f"| Проверок цены шага (ровно 0.002) | {st['step_checks']} |",
        f"| Всего вызовов оценщика | {st['grades']} |",
        f"| Нарушений | **{len(st['violations'])}** |",
        f"| Время | {st['seconds']} с |", "",
        "Проверяемые свойства: (1) нет доминирующей нечестной стратегии — честный ответ не хуже любого, а равный ему",
        "результат дают только ответы без FP и FN; (2) лишний FP не повышает награду, лишний TP без нового FP не понижает;",
        "(3) порядок выводов не влияет; (4) каждый шаг осмотра стоит ровно 0.002, пока не упёрлись в −1/1.", ""])


if __name__ == "__main__":
    st = run(sys.argv[1] if len(sys.argv) > 1 else "full")
    (ROOT / "reports" / "reward_exhaustive.md").write_text(render(st), "utf-8")
    for v in st["violations"][:10]:
        print("  VIOLATION", v)
    print(f"reward-exhaustive[{st['level']}]: {st['submissions']} cases, {st['grades']} grades, "
          f"{len(st['violations'])} violations, {st['seconds']} s")
    sys.exit(1 if st["violations"] else 0)
