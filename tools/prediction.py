"""A10: a forecast, written down BEFORE the jury runs its policies on hidden episodes.

For each of the 4 organiser policy kinds we forecast the mean reward, mean F1 and mean steps over a
hidden set of 20 episodes, as a 90 % interval: bootstrap of 20-episode means drawn from N fresh salted
episodes over all open configs (our implementation of the policy). Where an independent implementation
exists (jury_sim/, written from the case text by Beknazar without importing auditenv) its 20-episode
result is shown next to ours; the forecast interval for simple_reconcile spans both implementations,
because the organisers' honest reconciler may be weaker (ours) or complete (Beknazar's).

    python tools/prediction.py      -> docs/PREDICTION.md (date and SHA of the commit it is based on)
"""

from __future__ import annotations

import json
import os
import random
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_runs import BASELINES, ROOT, episodes, grade  # noqa: E402

N, HIDDEN, REPS = 300, 20, 4000


def boot_interval(xs, n=HIDDEN, reps=REPS, seed=11):
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choice(xs) for _ in range(n)) for _ in range(reps))
    return means[int(0.05 * reps)], means[int(0.95 * reps) - 1]


def collect():
    os.environ["AUDITENV_SEED_SALT"] = "round4-prediction"  # hidden episodes are salted; ours too
    try:
        rows = {p: [] for p in BASELINES}
        for cfg, seed, ep in episodes(N, 640000):
            for p in BASELINES:
                g = grade(p, ep)
                rows[p].append((g["reward"], g["f1"], g["steps"], len(ep.truth["issues"]) == 0))
        return rows
    finally:
        os.environ.pop("AUDITENV_SEED_SALT", None)


def jury_sim():
    p = ROOT / "jury_sim" / "work" / "closed_run.json"
    return json.loads(p.read_text("utf-8"))["summary"] if p.exists() else None


def render(rows, js) -> str:
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    date = subprocess.run(["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M %z"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    out = ["# Прогноз результатов политик организаторов на скрытых эпизодах", "",
           "> **Это прогноз, а не результат.** Записан до прогона жюри, чтобы после него можно было честно сравнить.",
           f"> Основан на коммите `{sha}` ({date}). Сгенерирован `python tools/prediction.py`.", "",
           "## Как считали", "",
           f"* Наши реализации 4 политик на {N} свежих **солёных** эпизодах (все 6 открытых конфигов поровну), режим train.",
           f"* Интервал — 90 % bootstrap для **среднего по {HIDDEN} эпизодам** (предполагаем 20 скрытых эпизодов):",
           f"  {REPS} раз выбираем {HIDDEN} эпизодов с возвращением и берём 5‑й и 95‑й процентили среднего.",
           "* Независимая проверка — симуляция жюри `jury_sim/` (Бекназар, 20 закрытых эпизодов на своих конфигах,",
           "  свои политики без `import auditenv`), см. `reports/jury_sim.md`.",
           "* Состав скрытых конфигов нам неизвестен: доля чистых книг и число ошибок сдвигают средние сильнее всего.", "",
           "## Прогноз (среднее по 20 скрытым эпизодам, 90 % интервал)", "",
           "| Политика | Награда | F1 (макро) | Шагов | Наши: среднее награды на чистых / ошибочных | jury_sim: награда, F1 микро, шаги |",
           "|---|---|---|---|---|---|"]
    for p in BASELINES:
        rw = [r[0] for r in rows[p]]
        f1 = [r[1] for r in rows[p]]
        st = [r[2] for r in rows[p]]
        lo, hi = boot_interval(rw)
        if p == "simple_reconcile" and js:
            hi = max(hi, js[p]["return_mean"])
        flo, fhi = boot_interval(f1)
        if p == "simple_reconcile" and js:
            fhi = max(fhi, js[p]["F1_macro"])
        slo, shi = boot_interval(st)
        clean = [r[0] for r in rows[p] if r[3]]
        dirty = [r[0] for r in rows[p] if not r[3]]
        j = js.get(p) if js else None
        jtxt = f"{j['return_mean']:+.3f}, {j['F1_micro']:.2f}, {j['steps_mean']:g}" if j else "—"
        out.append(f"| `{p}` | [{lo:+.2f}; {hi:+.2f}] | [{flo:.2f}; {fhi:.2f}] | [{slo:.1f}; {shi:.1f}] | "
                   f"{statistics.fmean(clean):+.3f} / {statistics.fmean(dirty):+.3f} | {jtxt} |")
    out += ["", "## Что мы ожидаем увидеть (качественно)", "",
            "* `oracle`: +1.00 на каждом эпизоде (1 шаг, F1 = 1). Любое отклонение — ошибка среды или оценщика.",
            "* `flag_all`: −1.00 везде (много FP, F1 = 0; на чистых книгах тоже −1).",
            "* `random_explorer`: около +0.96 на чистых и −1 на ошибочных; среднее зависит от доли чистых книг.",
            "* `simple_reconcile`: самый широкий интервал. Наш вариант намеренно упрощён (нет правила",
            "  previous_business_day, не читает credit note, считает переплату ошибкой — `docs/FAILURES.md`),",
            "  поэтому ложно обвиняет на части чистых книг; полная реализация жюри (Бекназара) решила все 59 из 59.",
            "  Верх интервала — полная реализация, низ — наша.",
            "* Ожидаемый порядок средних: oracle > simple_reconcile > random_explorer > flag_all. Пару",
            "  simple_reconcile vs random_explorer 20 эпизодов могут перепутать, если наш упрощённый вариант встретит",
            "  много чистых книг (`reports/power.md`: этой паре нужно больше 20 эпизодов).", "",
            "## Как сверить после прогона жюри", "",
            "Сравнить средние жюри с колонками «Награда», «F1», «Шагов». Попадание в интервал — прогноз верен; промах",
            "у `oracle` или `flag_all` — повод искать ошибку у нас (`docs/HOTFIX.md`); промах у `simple_reconcile` /",
            "`random_explorer` — скорее другой состав скрытых конфигов или другая реализация политики."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    rows = collect()
    (ROOT / "docs" / "PREDICTION.md").write_text(render(rows, jury_sim()), "utf-8")
    print("prediction: wrote docs/PREDICTION.md")
