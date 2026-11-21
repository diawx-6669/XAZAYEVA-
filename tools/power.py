"""A12: statistical power - how many episodes are needed to tell two policies apart.

Runs the 4 baseline policies + 2 close variants of simple_reconcile on N fresh episodes (paired: same
episodes), then for Δ = 0.05 / 0.1 / 0.2 in mean reward, α = 0.05 (two-sided), power 0.8:
  * analytic sample size, paired:   n = ((z_{1-α/2} + z_{0.8}) · σ_d / Δ)²
  * analytic sample size, unpaired: n per policy = 2 · ((z_{1-α/2} + z_{0.8}) · σ / Δ)²
  * bootstrap power at n = 20 (the hidden set): resample 20 paired differences, shift them to mean Δ,
    reject H0 if the 95 % bootstrap percentile CI of the mean excludes 0; power = share of rejections.
All randomness is random.Random(fixed seed): the report is deterministic.

    make power   -> reports/power.md
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_runs import BASELINES, ROOT, episodes, grade  # noqa: E402

ALPHA, POWER, HIDDEN_N = 0.05, 0.8, 20
DELTAS = (0.05, 0.1, 0.2)


def z(p: float) -> float:
    return statistics.NormalDist().inv_cdf(p)


def n_paired(sd_d: float, delta: float) -> int:
    return max(2, math.ceil(((z(1 - ALPHA / 2) + z(POWER)) * sd_d / delta) ** 2))


def n_unpaired(sd: float, delta: float) -> int:
    return max(2, math.ceil(2 * ((z(1 - ALPHA / 2) + z(POWER)) * sd / delta) ** 2))


def boot_power(diffs: list, delta: float, n: int = HIDDEN_N, reps: int = 400, inner: int = 400, seed: int = 7) -> float:
    rng = random.Random(seed)
    mu = statistics.fmean(diffs)
    shifted = [d - mu + delta for d in diffs]
    rejected = 0
    for _ in range(reps):
        sample = [rng.choice(shifted) for _ in range(n)]
        means = sorted(statistics.fmean(rng.choice(sample) for _ in range(n)) for _ in range(inner))
        lo, hi = means[int(0.025 * inner)], means[int(0.975 * inner) - 1]
        rejected += not (lo <= 0 <= hi)
    return rejected / reps


def collect(n: int) -> dict:
    from auditenv.policies.simple_reconcile import SimpleReconcile

    variants = {"simple_reconcile+fx_prev_business_day": {"fx_prev_business_day"},
                "simple_reconcile+credit_note_aware": {"credit_note_aware"}}
    rewards = {p: [] for p in BASELINES + list(variants)}
    for cfg, seed, ep in episodes(n, 620000):
        for p in BASELINES:
            rewards[p].append(grade(p, ep)["reward"])
        for name, extra in variants.items():
            pol = SimpleReconcile(rules={"dup", "alloc", "fx", "cutoff"} | extra)
            pol.name = name
            rewards[name].append(grade(pol, ep)["reward"])
    return rewards


def render(rw: dict, n: int) -> str:
    out = ["# Статистическая мощность: сколько эпизодов нужно, чтобы различить политики", "",
           f"Сгенерировано `make power` (`tools/power.py`): {n} свежих эпизодов (6 открытых конфигов, seed 620000+),",
           "все политики на одних и тех же эпизодах (парный план). α = 0.05 (двусторонний), мощность 0.8.",
           "Bootstrap — только stdlib (`random.Random(7)`), отчёт детерминирован.", "",
           "## Награда политик", "", "| Политика | Среднее | σ | Мин | Макс |", "|---|---|---|---|---|"]
    for p, xs in rw.items():
        out.append(f"| `{p}` | {statistics.fmean(xs):+.3f} | {statistics.stdev(xs):.3f} | {min(xs):+.3f} | {max(xs):+.3f} |")
    pairs = [("simple_reconcile+fx_prev_business_day", "simple_reconcile"),
             ("simple_reconcile+credit_note_aware", "simple_reconcile"),
             ("simple_reconcile", "random_explorer"), ("oracle", "simple_reconcile"), ("random_explorer", "flag_all")]
    out += ["", "## Пары политик: нужно эпизодов при Δ средней награды", "",
            "Парный план: σ_d — стандартное отклонение разности наград на одном эпизоде. «Без пар» — если политики",
            "оцениваются на разных эпизодах (σ — среднее двух σ). Последние колонки — bootstrap‑мощность на 20 эпизодах.", "",
            "| Пара (A − B) | Δ наблюдаемая | σ_d | n парный Δ=0.05 / 0.1 / 0.2 | n без пар Δ=0.05 / 0.1 / 0.2 | мощность на 20: Δ=0.05 / 0.1 / 0.2 | на 20 при наблюдаемой Δ |",
            "|---|---|---|---|---|---|---|"]
    verdict = []
    for a, b in pairs:
        d = [x - y for x, y in zip(rw[a], rw[b])]
        sd_d = statistics.stdev(d)
        sd = (statistics.stdev(rw[a]) + statistics.stdev(rw[b])) / 2
        obs = statistics.fmean(d)
        pw = [boot_power(d, dl) for dl in DELTAS]
        pw_obs = boot_power(d, obs) if abs(obs) > 1e-12 else 0.0
        out.append(f"| `{a}` − `{b}` | {obs:+.3f} | {sd_d:.3f} | " + " / ".join(str(n_paired(sd_d, dl)) for dl in DELTAS)
                   + " | " + " / ".join(str(n_unpaired(sd, dl)) for dl in DELTAS) + " | "
                   + " / ".join(f"{x:.2f}" for x in pw) + f" | {pw_obs:.2f} |")
        verdict.append((a, b, obs, n_paired(sd_d, abs(obs)) if abs(obs) > 1e-12 else None))
    out += ["", "## Хватает ли 20 скрытых эпизодов", ""]
    for a, b, obs, need in verdict:
        if need is None:
            out.append(f"* `{a}` vs `{b}`: разницы нет (Δ = 0) — различать нечего.")
        else:
            out.append(f"* `{a}` vs `{b}`: наблюдаемая Δ = {obs:+.3f}; парному тесту нужно ≈ {need} эпизодов — "
                       + ("**20 хватает**." if need <= HIDDEN_N else "**20 мало**, нужен больший набор."))
    ok = [v for v in verdict if v[3] is not None and v[3] <= HIDDEN_N]
    big = max(verdict, key=lambda v: statistics.stdev([x - y for x, y in zip(rw[v[0]], rw[v[1]])]))
    out += ["", f"**Вывод (посчитан, не задан руками).** 20 скрытых эпизодов хватает для {len(ok)} из {len(verdict)} пар "
            "(аналитический парный тест при наблюдаемой Δ). Разброс разности σ_d определяют прежде всего **чистые книги**:",
            "на них одна политика получает ≈ +1 за пустой ответ, а другая −1 за ложное обвинение, поэтому разность",
            f"скачет на 2 балла (максимальный σ_d = {statistics.stdev([x - y for x, y in zip(rw[big[0]], rw[big[1]])]):.2f} у пары "
            f"`{big[0]}` − `{big[1]}`). Близкие политики, отличающиеся одним правилом, имеют малый σ_d (разность",
            "почти всегда 0), и их различить проще, чем кажется по средним.", "",
            "Bootstrap‑мощность и аналитическая формула расходятся там, где разности дискретны (почти все 0 и редкие ±2):",
            "процентильный bootstrap на 20 точках в таком случае оптимистичен, аналитическая формула — ориентир сверху.",
            "Мы опираемся на аналитическую.", "",
            "Рекомендация жюри: сравнивать политики **на одних и тех же** эпизодах (парный план требует в разы меньше",
            "эпизодов, чем раздельный — столбцы «парный» и «без пар») и, если разница меньше ≈ 0.3, генерировать больше",
            "закрытых эпизодов той же солью: `run --seed` дёшев (≈ 0.1 с на эпизод и политику)."]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", default=str(ROOT / "reports" / "power.md"))
    a = ap.parse_args(argv)
    rw = collect(a.n)
    Path(a.out).write_text(render(rw, a.n), "utf-8")
    print(f"power: {a.n} episodes x {len(rw)} policies -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
