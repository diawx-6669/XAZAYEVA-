"""B13: reports/trajectory_stats.md - what the recorded trajectories contain, per policy: runs, tool calls,
error codes, steps until submit, how the runs ended. Reads only trajectories/trajectories.jsonl.

    python tools/trajectory_stats.py
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ["list_records", "get_record", "get_document", "calculator", "submit"]


def stats():
    runs = defaultdict(list)
    for line in (ROOT / "trajectories" / "trajectories.jsonl").read_text("utf-8").splitlines():
        rec = json.loads(line)
        runs[(rec["policy"], rec["run_id"])].append(rec)
    by = defaultdict(lambda: {"runs": 0, "tools": Counter(), "errors": Counter(), "steps": [], "end": Counter(),
                              "reward": [], "tables": Counter()})
    for (pol, _), recs in runs.items():
        s = by[pol]
        s["runs"] += 1
        for r in recs:
            a = r.get("action")
            if a:
                s["tools"][a.get("tool", "?") if a.get("tool") in TOOLS else "other/invalid"] += 1
                if a.get("tool") == "list_records":
                    s["tables"][(a.get("args") or {}).get("table", "?")] += 1
            err = (r.get("observation") or {}).get("error")
            if isinstance(err, dict):
                s["errors"][err.get("code", "?")] += 1
        last = recs[-1]
        s["steps"].append(last["step"])
        s["end"]["truncated: " + str(last.get("truncation_reason")) if last.get("truncated") else
                 ("submitted" if last.get("terminated") else "open")] += 1
        s["reward"].append(last.get("reward", 0.0))
    return by, sum(len(v) for v in runs.values())


def render() -> str:
    by, n = stats()
    out = ["# Статистика записанных траекторий", "",
           f"Сгенерировано `python tools/trajectory_stats.py` из `trajectories/trajectories.jsonl` ({n} строк, {sum(s['runs'] for s in by.values())} прогонов).",
           "Награда — терминальная в режиме train (как записана в траектории).", "",
           "| Политика | Прогонов | Шагов: медиана / макс | " + " | ".join(TOOLS) + " | Ошибки инструментов | Как закончился | Средняя награда |",
           "|---|---|---|" + "---|" * len(TOOLS) + "---|---|---|"]
    for pol in sorted(by):
        s = by[pol]
        errs = ", ".join(f"`{k}` {v}" for k, v in s["errors"].most_common()) or "—"
        ends = ", ".join(f"{k} {v}" for k, v in s["end"].most_common())
        out.append(f"| `{pol}` | {s['runs']} | {statistics.median(s['steps']):g} / {max(s['steps'])} | "
                   + " | ".join(str(s["tools"].get(t, 0)) for t in TOOLS)
                   + f" | {errs} | {ends} | {statistics.fmean(s['reward']):+.3f} |")
    out += ["", "## Какие таблицы листают", "", "| Политика | ledger | invoices | payments | fx |", "|---|---|---|---|---|"]
    for pol in sorted(by):
        t = by[pol]["tables"]
        if t:
            out.append(f"| `{pol}` | {t.get('ledger', 0)} | {t.get('invoices', 0)} | {t.get('payments', 0)} | {t.get('fx', 0)} |")
    out += ["", "Наблюдения: честный `simple_reconcile` читает все таблицы постранично и не делает ни одной ошибки инструмента;",
            "`random_explorer` тратит шаги и в том числе ошибается (каждая ошибка стоит шаг); `step_burner` и `hung` записаны",
            "специально — это контракт обрыва (100 шагов → `max_steps`, зависание → `policy_unresponsive`)."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    (ROOT / "reports" / "trajectory_stats.md").write_text(render(), "utf-8")
    print("trajectory-stats: wrote reports/trajectory_stats.md")
