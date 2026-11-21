"""A16: difficulty of every error variant on one scale (Rasch model, stdlib only).

Persons = a panel of 10 truncated/extended variants of simple_reconcile (rules switched on and off).
Items   = error variants (type / variant). A response = "this issue instance was matched (TP)".
Model:  P(solve) = 1 / (1 + exp(-(theta_person - b_item))), estimated by penalised joint maximum
likelihood (Newton-Raphson per parameter, weak N(0, 3^2) prior so that items solved by everyone or
by no one stay finite; identification: mean item difficulty = 0). Intervals: b +- 1.96 / sqrt(information).

    make difficulty   -> reports/difficulty.md   (300 episodes over the 6 open configs)
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_runs import ROOT, episodes, grade  # noqa: E402

BASE = {"dup", "alloc", "fx", "cutoff"}
OPT = {"fx_prev_business_day", "credit_note_aware", "overpayment_aware", "skip_dup_in_fx"}
PANEL = {
    "full (all rules)": BASE | OPT,
    "official baseline": BASE,
    "baseline - dup": BASE - {"dup"},
    "baseline - alloc": BASE - {"alloc"},
    "baseline - fx": BASE - {"fx"},
    "baseline - cutoff": BASE - {"cutoff"},
    "baseline + prev_business_day": BASE | {"fx_prev_business_day"},
    "full - prev_business_day": (BASE | OPT) - {"fx_prev_business_day"},
    "full - credit_note_aware": (BASE | OPT) - {"credit_note_aware"},
    "fx specialist": {"fx", "fx_prev_business_day"},
}
PRIOR_SD = 3.0


def collect(n: int) -> dict:
    """counts[(person, item)] = [solved, total]"""
    from auditenv.policies.simple_reconcile import SimpleReconcile

    counts = {}
    for cfg, seed, ep in episodes(n, 660000):
        variant = {m["issue_id"]: f"{m['type']} / {m.get('variant', '?')}" for m in ep.provenance["mutations"]}
        if not ep.truth["issues"]:
            continue
        for person, rules in PANEL.items():
            pol = SimpleReconcile(rules=rules)
            g = grade(pol, ep)
            solved = {f["matched"] for f in g["findings"] if f.get("matched")}
            for iss in ep.truth["issues"]:
                c = counts.setdefault((person, variant[iss["issue_id"]]), [0, 0])
                c[0] += iss["issue_id"] in solved
                c[1] += 1
    return counts


def fit(counts: dict, iters: int = 200):
    persons = sorted({p for p, _ in counts}, key=list(PANEL).index)
    items = sorted({i for _, i in counts})
    th = {p: 0.0 for p in persons}
    b = {i: 0.0 for i in items}
    sig = lambda x: 1.0 / (1.0 + math.exp(-x))  # noqa: E731
    for _ in range(iters):
        for p in persons:  # Newton step on theta_p
            g, h = -th[p] / PRIOR_SD ** 2, 1 / PRIOR_SD ** 2
            for i in items:
                k, n = counts.get((p, i), (0, 0))
                if n:
                    pr = sig(th[p] - b[i])
                    g += k - n * pr
                    h += n * pr * (1 - pr)
            th[p] += max(-1.0, min(1.0, g / h))
        for i in items:
            g, h = -b[i] / PRIOR_SD ** 2, 1 / PRIOR_SD ** 2
            for p in persons:
                k, n = counts.get((p, i), (0, 0))
                if n:
                    pr = sig(th[p] - b[i])
                    g -= k - n * pr
                    h += n * pr * (1 - pr)
            b[i] += max(-1.0, min(1.0, g / h))
        mean_b = sum(b.values()) / len(b)
        for i in items:
            b[i] -= mean_b
        for p in persons:
            th[p] -= mean_b
    se = {}
    for i in items:
        info = 1 / PRIOR_SD ** 2 + sum(n * sig(th[p] - b[i]) * (1 - sig(th[p] - b[i]))
                                       for p in persons for k, n in [counts.get((p, i), (0, 0))] if n)
        se[i] = 1 / math.sqrt(info)
    return th, b, se


def render(counts, th, b, se, n) -> str:
    items = sorted(b, key=lambda i: b[i])
    n_item = {i: counts.get(("official baseline", i), (0, 0))[1] for i in items}
    out = ["# Сложность вариантов ошибок (модель Раша)", "",
           f"Сгенерировано `make difficulty` (`tools/rasch.py`): {n} свежих эпизодов (6 открытых конфигов, seed 660000+),",
           f"панель из {len(PANEL)} вариантов `simple_reconcile` с выключаемыми правилами, ответ = «этот issue получил TP».",
           "Модель: P(решил) = σ(θ_политики − b_варианта); штрафованное совместное ML (Ньютон, априорное N(0, 3²)),",
           "среднее b = 0. Интервал — b ± 1.96 / √информации. Чем **больше b, тем труднее** вариант для панели.", "",
           "Оговорка: панель — 10 близких скриптовых политик, а не люди и не LLM; модель одномерная, а правила",
           "многомерны (выключенное правило обнуляет целый тип). Шкала показывает, какие варианты требуют **больше",
           "правил и аккуратности** для этой панели, а не «абсолютную» трудность для агентов вообще.", "",
           "## Шкала сложности", "",
           "| Вариант | n (issue) | Решено официальной базой | b | 95 % интервал | Шкала |", "|---|---|---|---|---|---|"]
    lo_all = min(b[i] - 1.96 * se[i] for i in items)
    hi_all = max(b[i] + 1.96 * se[i] for i in items)

    def bar(i):
        w = 30
        pos = lambda x: int(round((x - lo_all) / (hi_all - lo_all) * (w - 1)))  # noqa: E731
        cells = [" "] * w
        for k in range(pos(b[i] - 1.96 * se[i]), pos(b[i] + 1.96 * se[i]) + 1):
            cells[k] = "─"
        cells[pos(b[i])] = "●"
        return "`" + "".join(cells) + "`"

    for i in reversed(items):
        k, nn = counts.get(("official baseline", i), (0, 0))
        out.append(f"| {i} | {n_item[i]} | {k}/{nn} | {b[i]:+.2f} | [{b[i] - 1.96 * se[i]:+.2f}; {b[i] + 1.96 * se[i]:+.2f}] | {bar(i)} |")
    out += ["", "## Способность политик панели (θ)", "", "| Политика | Правила | θ | Решено всего |", "|---|---|---|---|"]
    for p in sorted(th, key=lambda p: -th[p]):
        k = sum(v[0] for (pp, _), v in counts.items() if pp == p)
        nn = sum(v[1] for (pp, _), v in counts.items() if pp == p)
        out.append(f"| {p} | {', '.join(sorted(PANEL[p]))} | {th[p]:+.2f} | {k}/{nn} |")
    out += ["", "## Как читать", "",
            "* Варианты внизу шкалы решает почти любая политика, у которой включено правило своего типа.",
            "* Вверху — варианты, которые требуют дополнительных правил (`previous_business_day` для выходных курсов,",
            "  учёт credit note и переплаты) или которые простые правила вообще не видят (`wrong_invoice`).",
            "* Широкий интервал — мало примеров варианта (см. столбец n): вариант редкий в открытых конфигах."]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", default=str(ROOT / "reports" / "difficulty.md"))
    a = ap.parse_args(argv)
    counts = collect(a.n)
    th, b, se = fit(counts)
    Path(a.out).write_text(render(counts, th, b, se, a.n), "utf-8")
    print(f"difficulty: {len(b)} variants x {len(th)} policies on {a.n} episodes -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
