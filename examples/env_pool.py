"""A18: a pool of AuditEnv workers on multiprocessing + the benchmark behind `make bench`.

Each worker process generates its own episodes and runs a policy IN-PROCESS (no child agent process):
the fast path for training loops. Workers share nothing; results come back as small dicts.
(Closed runs with an agent process must not run in parallel under root - docs/LIMITATIONS.md.)

    from examples.env_pool import EnvPool
    with EnvPool(workers=2) as pool:
        grades = pool.run([(seed, "dev-mixed") for seed in range(100)], policy="simple_reconcile")

    python examples/env_pool.py          (= make bench) -> reports/bench.md
"""

from __future__ import annotations

import multiprocessing as mp
import os
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SIZES = {200: {"n_invoices": [20, 20]}, 1000: {"n_invoices": [110, 110]}, 2000: {"n_invoices": [230, 230]}}


def size_config(target: int) -> dict:
    from auditenv.config import load_config

    cfg = load_config("dev-mixed")
    cfg.update({"name": f"bench-{target}", "version": "bench", **SIZES[target]})
    return cfg


def _work(job):
    seed, config, policy = job
    from auditenv.generator.episode import generate_episode
    from auditenv.runner import run_episode

    t0 = time.perf_counter()
    ep = generate_episode(seed, config)
    t1 = time.perf_counter()
    g = run_episode(policy, episode=ep, isolate=False, record=False)["grade"]
    t2 = time.perf_counter()
    return {"seed": seed, "reward": g["reward"], "steps": g["steps"], "f1": g["f1"], "gen_s": t1 - t0, "run_s": t2 - t1}


class EnvPool:
    def __init__(self, workers: int = 2):
        self.workers = workers
        self._pool = mp.get_context("spawn" if os.name == "nt" else "fork").Pool(workers)

    def run(self, jobs, policy: str = "simple_reconcile") -> list:
        return self._pool.map(_work, [(s, c, policy) for s, c in jobs], chunksize=max(1, len(jobs) // (4 * self.workers)))

    def close(self):
        self._pool.close()
        self._pool.join()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ------------------------------------------------------------------------------------------ benchmark
def hardware() -> dict:
    model = "?"
    try:
        for ln in Path("/proc/cpuinfo").read_text().splitlines():
            if ln.startswith("model name"):
                model = ln.split(":", 1)[1].strip()
                break
    except OSError:
        model = platform.processor() or "?"
    mem = "?"
    try:
        kb = int(next(ln for ln in Path("/proc/meminfo").read_text().splitlines() if ln.startswith("MemTotal")).split()[1])
        mem = f"{kb / 1048576:.1f} GiB"
    except (OSError, StopIteration):
        pass
    try:
        avail = len(os.sched_getaffinity(0))
    except AttributeError:
        avail = os.cpu_count()
    return {"cpu": model, "cpus_visible": os.cpu_count(), "cpus_usable": avail, "memory": mem,
            "os": f"{platform.system()} {platform.release()}", "machine": platform.machine(),
            "python": platform.python_version()}


def bench_generation(target: int, n: int) -> dict:
    from auditenv.generator.episode import generate_episode

    cfg = size_config(target)
    ts, ledgers = [], []
    for s in range(n):
        t0 = time.perf_counter()
        ep = generate_episode(700000 + s, cfg)
        ts.append(time.perf_counter() - t0)
        ledgers.append(ep.files["ledger.csv"].count(b"\n") - 1)
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    keep = [generate_episode(710000 + s, cfg) for s in range(5)]
    from auditenv.env.env import AuditEnv

    envs = []
    for ep in keep:
        e = AuditEnv(mode="train")
        e.reset(episode=ep)
        envs.append(e)
    mem = (tracemalloc.get_traced_memory()[0] - base) / len(keep)
    tracemalloc.stop()
    del keep, envs
    return {"target": target, "ledger_median": statistics.median(ledgers), "gen_per_s": n / sum(ts),
            "gen_p50_ms": statistics.median(ts) * 1000, "mem_mb_per_episode": mem / 1e6}


def bench_steps(target: int, n_steps: int = 3000) -> dict:
    """Raw env.step throughput: list_records pages, get_record, calculator - no policy logic."""
    from auditenv.env.env import AuditEnv
    from auditenv.generator.episode import generate_episode

    ep = generate_episode(720000, size_config(target))
    env = AuditEnv(mode="train", time_limit=1e9)
    obs, _ = env.reset(episode=ep)
    rows = ep.files["ledger.csv"].decode().splitlines()[1:]
    ids = [r.split(",", 1)[0] for r in rows]
    acts = [{"tool": "list_records", "args": {"table": "ledger", "limit": 50}},
            {"tool": "get_record", "args": {"table": "ledger", "id": ids[0]}},
            {"tool": "calculator", "args": {"expression": "(123456 * 1.5) / 7"}}]
    done, t = 0, 0.0
    while done < n_steps:
        env.reset(episode=ep)
        for k in range(99):
            a = acts[k % 3] if k % 3 != 1 else {"tool": "get_record", "args": {"table": "ledger", "id": ids[k % len(ids)]}}
            t0 = time.perf_counter()
            env.step(a)
            t += time.perf_counter() - t0
            done += 1
    return {"target": target, "steps_per_s": done / t, "step_us": t / done * 1e6}


def bench_scaling(n: int = 60) -> list:
    out = []
    jobs = [(730000 + s, "dev-mixed") for s in range(n)]
    for w in (1, 2):
        t0 = time.perf_counter()
        with EnvPool(workers=w) as pool:
            res = pool.run(jobs)
        dt = time.perf_counter() - t0
        out.append({"workers": w, "episodes": n, "wall_s": dt, "episodes_per_s": n / dt,
                    "mean_reward": statistics.fmean(r["reward"] for r in res)})
    return out


def render(hw, gen, steps, scal) -> str:
    lines = ["# Производительность (бенчмарк)", "",
             "Сгенерировано `make bench` (`examples/env_pool.py`). Числа зависят от машины — это единственный отчёт раунда 4,",
             "который **не** детерминирован. Награды и шаги при этом детерминированы (столбец «средняя награда» одинаков",
             "для 1 и 2 воркеров).", "", "## Железо", "", "| Параметр | Значение |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in hw.items()]
    lines += ["", "## Генерация эпизодов и память (1 процесс)", "",
              "Размер задаётся числом счетов (`n_invoices`) поверх `dev-mixed`; память — tracemalloc на эпизод с поднятой средой.", "",
              "| Цель, проводок | Медиана проводок | Эпизодов/с | p50, мс | Память на эпизод + env, МБ |", "|---|---|---|---|---|"]
    lines += [f"| {g['target']} | {g['ledger_median']:g} | {g['gen_per_s']:.1f} | {g['gen_p50_ms']:.0f} | {g['mem_mb_per_episode']:.1f} |" for g in gen]
    lines += ["", "## Шаги среды (1 процесс, без логики политики)", "",
              "Смесь `list_records` (50 строк), `get_record`, `calculator`; эпизод перезапускается каждые 99 шагов.", "",
              "| Цель, проводок | Шагов/с | мкс на шаг |", "|---|---|---|"]
    lines += [f"| {s['target']} | {s['steps_per_s']:,.0f} | {s['step_us']:.0f} |".replace(",", " ") for s in steps]
    lines += ["", "## Масштабирование пула (генерация + simple_reconcile in-process, `dev-mixed`)", "",
              "| Воркеров | Эпизодов | Время, с | Эпизодов/с | Ускорение | Средняя награда |", "|---|---|---|---|---|---|"]
    base = scal[0]["episodes_per_s"]
    lines += [f"| {s['workers']} | {s['episodes']} | {s['wall_s']:.2f} | {s['episodes_per_s']:.1f} | ×{s['episodes_per_s'] / base:.2f} | {s['mean_reward']:+.4f} |" for s in scal]
    lines += ["", f"Лимит кейса — 60 с на эпизод. На этой машине эпизод на ~2 000 проводок генерируется за ~{gen[-1]['gen_p50_ms'] / 1000:.2f} с,",
              f"а шаг среды занимает ~{steps[-1]['step_us'] / 1000:.2f} мс: 100 шагов — меньше {100 * steps[-1]['step_us'] / 1e6 + 0.01:.2f} с. Время эпизода",
              "определяет сам агент, а не среда."]
    return "\n".join(lines) + "\n"


def main() -> int:
    hw = hardware()
    gen = [bench_generation(t, 20 if t == 200 else 6) for t in SIZES]
    bench_steps(200, 600)  # warm-up: imports, decimal contexts, CPU frequency
    steps = [bench_steps(t) for t in SIZES]
    scal = bench_scaling()
    out = ROOT / "reports" / "bench.md"
    out.write_text(render(hw, gen, steps, scal), "utf-8")
    print(f"bench: -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
