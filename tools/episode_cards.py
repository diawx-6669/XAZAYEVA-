"""B12: reports/episode_cards.md - a card for each of the 20 open episodes (grader-side: reads grader/ of OPEN
episodes only): config and seed, base currency and foreign ones, time zone and offset, period, sizes,
injected errors with variants and scenarios, correct look-alikes (distractors), simple_reconcile result.

    python tools/episode_cards.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def cards() -> list:
    from auditenv.runner import run_episode
    from auditenv.timeutil import TIMEZONES

    out = []
    for split in ("train", "dev"):
        for e in json.loads((ROOT / "episodes" / split / "index.json").read_text("utf-8")):
            d = ROOT / "episodes" / split / e["episode_id"]
            m = json.loads((d / "public" / "manifest.json").read_text("utf-8"))
            tr = json.loads((d / "grader" / "truth.json").read_text("utf-8"))
            pv = json.loads((d / "grader" / "provenance.json").read_text("utf-8"))
            g = run_episode("simple_reconcile", episode_dir=str(d), isolate=False, record=False)["grade"]
            h, mi = TIMEZONES[m["timezone"]]
            out.append({"split": split, "id": e["episode_id"], "config": e["config"], "seed": e["seed"],
                        "base": m["base_currency"], "foreign": sorted(c for c in m["currencies"] if c != m["base_currency"]),
                        "tz": f"{m['timezone']} (UTC{h:+d}:{abs(mi):02d})", "period": f"{m['period_start'][:10]} … {m['period_end'][:10]}",
                        "counts": m["counts"], "scenarios": pv["plan"].get("scenarios", []),
                        "errors": [f"{mu['type']}/{mu.get('variant')}" for mu in pv["mutations"]],
                        "distractors": pv["story"].get("distractors", []),
                        "sr": f"TP {g['tp']} · FP {g['fp']} · FN {g['fn']} · reward {g['reward']:+.3f} · {g['steps']} шагов"})
    return out


def render() -> str:
    out = ["# Карточки открытых эпизодов", "",
           "Сгенерировано `python tools/episode_cards.py` (читает `grader/` **открытых** эпизодов — это и так опубликованный",
           "эталон). Для каждого из 20 эпизодов: откуда он, что в нём заложено и как с ним справляется честный",
           "`simple_reconcile` (режим train). Разбор ошибок «до/после» — `python -m auditenv explain episodes/<split>/<id>`.", "",
           "| Эпизод | Конфиг#seed | База / иностранные | Пояс | Проводок | Ошибки | simple_reconcile |", "|---|---|---|---|---|---|---|"]
    cs = cards()
    for c in cs:
        errs = ", ".join(c["errors"]) or "— (чистая книга)"
        out.append(f"| `{c['split']}/{c['id']}` | {c['config']}#{c['seed']} | {c['base']} / {', '.join(c['foreign']) or '—'} | "
                   f"{c['tz']} | {c['counts']['ledger']} | {errs} | {c['sr']} |")
    for c in cs:
        out += ["", f"## `{c['split']}/{c['id']}`", "",
                f"* Конфиг `{c['config']}`, seed {c['seed']}; период {c['period']}; пояс {c['tz']}.",
                f"* Размер: {c['counts']['ledger']} проводок, {c['counts']['invoices']} счетов, {c['counts']['payments']} платежей, "
                f"{c['counts']['fx']} курсов.",
                f"* Ошибки: {', '.join(c['errors']) or 'нет'}" + (f"; сценарии: {', '.join(c['scenarios'])}" if c["scenarios"] else "") + ".",
                f"* Корректные «двойники»: {', '.join(c['distractors']) or 'нет'}.",
                f"* simple_reconcile: {c['sr']}."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    (ROOT / "reports" / "episode_cards.md").write_text(render(), "utf-8")
    print("episode-cards: wrote reports/episode_cards.md")
