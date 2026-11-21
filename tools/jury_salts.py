"""B30: the black-box jury simulation's closed run and contract checks under many salts.

The non-canonical cursor (docs/FAILURES.md item 18) showed up only for about a quarter of the salts: one salt
per run is not enough. This runs jury_sim/closed_run.py and jury_sim/contract_check.py (Beknazar's black-box
code, unchanged) once per salt and tabulates the results. The original jury_sim/work/salt.txt is restored.

    make jury-salts    -> reports/jury_salts.md   (8 salts, a few minutes)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "jury_sim" / "work"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    a = ap.parse_args(argv)
    WORK.mkdir(parents=True, exist_ok=True)
    salt_file = WORK / "salt.txt"
    saved = salt_file.read_text() if salt_file.exists() else None
    rows = []
    try:
        for k in range(a.n):
            salt_file.write_text(f"round4-multisalt-{k:02d}\n")
            r1 = subprocess.run([sys.executable, "closed_run.py"], cwd=ROOT / "jury_sim", capture_output=True, text=True)
            r2 = subprocess.run([sys.executable, "contract_check.py"], cwd=ROOT / "jury_sim", capture_output=True, text=True)
            closed = json.loads((WORK / "closed_run.json").read_text("utf-8"))
            m = re.search(r"passed (\d+)/(\d+)", r2.stdout)
            fails = [ln[5:] for ln in r2.stdout.splitlines() if ln.startswith("FAIL ")]
            s = closed["summary"]
            rows.append({"salt": k, "closed_rc": r1.returncode, "problems": len(closed["problems"]),
                         "oracle": s["oracle"]["return_mean"], "flag_all": s["flag_all"]["return_mean"],
                         "sr_tp": s["simple_reconcile"]["TP"], "sr_fn": s["simple_reconcile"]["FN"],
                         "contract": f"{m.group(1)}/{m.group(2)}" if m else "?", "fails": fails, "contract_rc": r2.returncode})
            print(f"salt {k}: closed problems {rows[-1]['problems']}, contract {rows[-1]['contract']}", flush=True)
    finally:
        if saved is None:
            salt_file.unlink(missing_ok=True)
        else:
            salt_file.write_text(saved)
    ok = sum(1 for r in rows if r["problems"] == 0 and r["contract"] == "20/20")
    out = ["# Симуляция жюри на многих солях", "",
           f"Сгенерировано `make jury-salts` (`tools/jury_salts.py`): закрытый прогон (20 эпизодов × 4 политики жюри) и 20",
           f"проверок контракта из `jury_sim/` (код Бекназара без изменений, без `import auditenv`) при {a.n} разных солях.", "",
           "| Соль | Проблемы оценщика | oracle | flag_all | simple_reconcile жюри TP / FN | Контракт | Провалы |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| `round4-multisalt-{r['salt']:02d}` | {r['problems']} | {r['oracle']:+.3f} | {r['flag_all']:+.3f} | "
                   f"{r['sr_tp']} / {r['sr_fn']} | {r['contract']} | {'; '.join(r['fails']) or '—'} |")
    out += ["", f"**Итог: {ok} из {len(rows)} солей — 0 проблем и контракт 20/20.**", ""]
    (ROOT / "reports" / "jury_salts.md").write_text("\n".join(out), "utf-8")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
