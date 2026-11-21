"""B20: the reproducibility certificate across interpreters and environments on ONE machine.

Runs tools/repro_cert.py under every Python 3.11+ found on PATH (each with a different PYTHONHASHSEED, TZ and
LANG) and compares the generator items (20 open episodes, golden, configs) with the reference run.

    make repro-cross   -> reports/repro_cross_python.md
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ["python3.11", "python3.12", "python3.13", "python3.14", "python3"]
ENVS = [{"PYTHONHASHSEED": "0", "TZ": "UTC", "LANG": "C.UTF-8"},
        {"PYTHONHASHSEED": "12345", "TZ": "Asia/Almaty", "LANG": "ru_RU.UTF-8"},
        {"PYTHONHASHSEED": "random", "TZ": "America/Bogota", "LANG": "C"}]


def interpreters() -> list:
    seen, out = set(), [sys.executable]
    for c in CANDIDATES:
        p = shutil.which(c)
        if p:
            real = os.path.realpath(p)
            v = subprocess.run([p, "-c", "import sys;print(sys.version_info[:2] >= (3, 11))"], capture_output=True, text=True).stdout.strip()
            if v == "True" and real not in seen and real != os.path.realpath(sys.executable):
                seen.add(real)
                out.append(p)
    return out


def run(interp: str, env: dict, out: Path) -> dict:
    e = {**{k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "AUDITENV_SEED_SALT")}, **env}
    subprocess.run([interp, str(ROOT / "tools" / "repro_cert.py"), "--out", str(out)], cwd=ROOT, env=e, check=True,
                   capture_output=True, text=True)
    return json.loads(out.read_text("utf-8"))


def main() -> int:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        ref = None
        for k, interp in enumerate(interpreters()):
            for j, env in enumerate(ENVS):
                cert = run(interp, env, Path(tmp) / f"c{k}{j}.json")
                items = {x: v for x, v in cert["items"].items() if not x.startswith("selfcheck/")}
                ref = ref or items
                diff = sorted(x for x in set(ref) | set(items) if ref.get(x) != items.get(x))
                rows.append((cert["machine"]["python"], interp, env, len(items), len(diff), diff[:3]))
    bad = sum(1 for r in rows if r[4])
    lines = ["# Воспроизводимость между интерпретаторами", "",
             "Сгенерировано `make repro-cross` (`tools/repro_cross.py`): сертификат `tools/repro_cert.py` пересчитан каждым",
             "найденным Python 3.11+ при трёх разных окружениях (`PYTHONHASHSEED`, `TZ`, `LANG`) и сравнён с первым прогоном.",
             "Сравниваются хеши, которые зависят только от генератора: 20 открытых эпизодов (public и grader), 3 golden‑эпизода",
             "и хеши конфигов; часть self‑check берётся из одного и того же файла и здесь не сравнивается.", "",
             "| Python | Интерпретатор | PYTHONHASHSEED | TZ | LANG | Хешей | Расхождений |", "|---|---|---|---|---|---|---|"]
    for py, interp, env, n, nd, ex in rows:
        lines.append(f"| {py} | `{Path(interp).name}` | {env['PYTHONHASHSEED']} | {env['TZ']} | {env['LANG']} | {n} | {nd}"
                     + (f" ({', '.join(ex)})" if ex else "") + " |")
    lines += ["", f"**Итог: {len(rows) - bad} из {len(rows)} прогонов побайтно совпали с эталонным.**", ""]
    (ROOT / "reports" / "repro_cross_python.md").write_text("\n".join(lines), "utf-8")
    print(f"repro-cross: {len(rows)} runs, {bad} with differences -> reports/repro_cross_python.md")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
