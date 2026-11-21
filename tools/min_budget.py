"""A11: minimal tool budget - how many tool calls are NECESSARY to see one full evidence set.

For every issue and every episode we compute the exact minimum number of tool calls after which every
ID of at least one evidence set has appeared in observations (what the experimental reward demands):
  * a ledger row / fx row / document can be fetched alone (get_record / get_document: 1 call each),
    or seen on a list_records page; page k (50 rows) costs k calls because cursors are sequential;
  * per table the optimum is min over j of (j pages + IDs beyond page j fetched one by one);
  * `policy` costs 1 call (get_record policy); it is not in the first observation as an ID;
  * a document (doc_id) is seen through get_document, get_record(invoices|payments) or a page of its table.
Episode budget = min over one evidence set per issue (all combinations) of the calls to see the union,
+ 1 for submit. Compared with the limit of 100 steps.

    make min-budget        -> reports/min_budget.md (500 episodes over 6 configs)
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PAGE = 50
LIMIT = 100
CONFIGS = ["train-easy", "train-global", "dev-mixed", "dev-global", "interaction-heavy", "clean-only"]


def positions(data) -> dict:
    """id -> (table, 1-based page) for every ID a tool can return."""
    pos = {"policy": ("policy", 1)}
    for i, r in enumerate(data.ledger):
        pos[r["row_id"]] = ("ledger", i // PAGE + 1)
    for i, r in enumerate(data.fx):
        pos[r["fx_id"]] = ("fx", i // PAGE + 1)
    for tbl in ("invoices", "payments"):
        for i, r in enumerate(data.table(tbl)):
            pos[r["doc_id"]] = (tbl, i // PAGE + 1)
    return pos


def table_cost(pages: list) -> int:
    """IDs of one table at these pages: paginate to page j and fetch the rest singly; minimise over j."""
    if not pages:
        return 0
    return min(j + sum(1 for p in pages if p > j) for j in range(0, max(pages) + 1))


def cost(ids, pos) -> int:
    by = {}
    for i in set(ids):
        t, p = pos[i]
        by.setdefault(t, []).append(p)
    return sum(1 if t == "policy" else table_cost(ps) for t, ps in by.items())


def plan(ids, pos) -> list:
    """A concrete plan of exactly cost(ids, pos) calls: ('page', table, k) / ('get', table, id)."""
    by = {}
    for i in sorted(set(ids)):
        t, p = pos[i]
        by.setdefault(t, []).append((p, i))
    out = []
    for t, items in sorted(by.items()):
        if t == "policy":
            out.append(("get", "policy", "policy"))
            continue
        pages = [p for p, _ in items]
        j = min(range(0, max(pages) + 1), key=lambda j: j + sum(1 for p in pages if p > j))
        out += [("page", t, k) for k in range(1, j + 1)]
        out += [("get", t, i) for p, i in items if p > j]
    return out


def episode_budget(truth: dict, pos: dict) -> dict:
    issues = truth["issues"]
    per_issue = [min(cost(s, pos) for s in iss["evidence_sets"]) for iss in issues]
    if not issues:
        return {"per_issue": [], "episode": 1, "sum_independent": 1}
    best = min(cost(set().union(*combo), pos) for combo in itertools.product(*[iss["evidence_sets"] for iss in issues]))
    return {"per_issue": per_issue, "episode": best + 1, "sum_independent": sum(per_issue) + 1}


def run(n: int) -> dict:
    from auditenv.env.data import PublicData
    from auditenv.generator.episode import generate_episode

    rows, by_type = [], {}
    for i in range(n):
        cfg, seed = CONFIGS[i % len(CONFIGS)], 610000 + i
        ep = generate_episode(seed, cfg)
        data = PublicData(ep.files)
        pos = positions(data)
        b = episode_budget(ep.truth, pos)
        variants = {m["issue_id"]: m.get("variant", "?") for m in ep.provenance["mutations"]}
        for iss, c in zip(ep.truth["issues"], b["per_issue"]):
            by_type.setdefault(f"{iss['type']} / {variants.get(iss['issue_id'], '?')}", []).append(c)
        rows.append({"config": cfg, "seed": seed, "issues": len(ep.truth["issues"]), "ledger": len(data.ledger), **b})
    return {"rows": rows, "by_type": by_type}


def _q(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1) + 0.5))]


def render(r: dict, n: int) -> str:
    eps = [x["episode"] for x in r["rows"]]
    lines = ["# Минимальный бюджет инструментов", "",
             f"Сгенерировано `make min-budget` (`tools/min_budget.py`) на {n} эпизодах ({', '.join(CONFIGS)}; seed 610000+).",
             "Для каждого issue — точный минимум вызовов инструментов, после которых **все** ID хотя бы одного набора",
             "доказательств появились в наблюдениях (так требует экспериментальная награда): отдельная запись — 1 вызов",
             "(`get_record`/`get_document`), страница `list_records` k стоит k вызовов (курсоры последовательны), `policy` — 1.",
             "Бюджет эпизода — минимум по выбору одного набора на каждый issue (перебор всех сочетаний) плюс 1 `submit`.", "",
             "## Эпизод целиком против лимита 100 шагов", "",
             "| Мин | Медиана | p95 | p99 | Макс | Эпизодов > 100 | Сумма по issue отдельно (медиана / макс) |",
             "|---|---|---|---|---|---|---|",
             f"| {min(eps)} | {statistics.median(eps):g} | {_q(eps, .95)} | {_q(eps, .99)} | {max(eps)} | "
             f"{sum(1 for e in eps if e > LIMIT)} | {statistics.median([x['sum_independent'] for x in r['rows']]):g} / "
             f"{max(x['sum_independent'] for x in r['rows'])} |", "",
             f"Запас: даже самый «дорогой» эпизод требует {max(eps)} из {LIMIT} шагов, если агент знает, куда смотреть. ",
             "Честному агенту нужно больше (он не знает ID заранее): `simple_reconcile` читает все таблицы постранично",
             "за 11–16 шагов — страницы дешевле точечных запросов, когда доказательств много.", "",
             "## По конфигам", "", "| Конфиг | Эпизодов | Issue на эпизод (медиана) | Бюджет: медиана | Макс |", "|---|---|---|---|---|"]
    for cfg in CONFIGS:
        xs = [x for x in r["rows"] if x["config"] == cfg]
        if xs:
            lines.append(f"| `{cfg}` | {len(xs)} | {statistics.median([x['issues'] for x in xs]):g} | "
                         f"{statistics.median([x['episode'] for x in xs]):g} | {max(x['episode'] for x in xs)} |")
    lines += ["", "## По вариантам ошибок (один issue)", "", "| Тип / вариант | n | Мин | Медиана | Макс |", "|---|---|---|---|---|"]
    for k in sorted(r["by_type"]):
        xs = r["by_type"][k]
        lines.append(f"| {k} | {len(xs)} | {min(xs)} | {statistics.median(xs):g} | {max(xs)} |")
    hist = {}
    for e in eps:
        b = (e - 1) // 5 * 5 + 1
        hist[b] = hist.get(b, 0) + 1
    lines += ["", "## Распределение бюджета эпизода", "", "| Шагов | Эпизодов |", "|---|---|"]
    lines += [f"| {b}–{b + 4} | {hist[b]} |" for b in sorted(hist)]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--out", default=str(ROOT / "reports" / "min_budget.md"))
    a = ap.parse_args(argv)
    r = run(a.n)
    Path(a.out).write_text(render(r, a.n), "utf-8")
    eps = [x["episode"] for x in r["rows"]]
    print(f"min-budget: {a.n} episodes, episode budget median {statistics.median(eps):g}, max {max(eps)}, "
          f"over {LIMIT}: {sum(1 for e in eps if e > LIMIT)} -> {a.out}")
    return 1 if max(eps) > LIMIT else 0


if __name__ == "__main__":
    sys.exit(main())
