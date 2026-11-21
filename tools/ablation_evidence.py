"""B9: why the evidence requirement exists - the same answers graded with and without it.

The real grader is used twice: as is, and with `matcher.satisfied_set` patched IN THIS PROCESS ONLY to
accept any evidence (the core files are not touched). Answers: honest policies, simple_reconcile with its
evidence stripped ("knows the answer, proves nothing"), the automatic-exploit-search best strategy (no
answer key), and the attacks that read the answer key but cite wrong evidence.

    make ablation  -> reports/ablation_evidence.md
"""

from __future__ import annotations

import argparse
import contextlib
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_runs import ROOT, episodes  # noqa: E402


@contextlib.contextmanager
def evidence_ignored():
    import auditenv.grader.core as core
    import auditenv.grader.matcher as matcher

    saved = (matcher.satisfied_set, core.satisfied_set if hasattr(core, "satisfied_set") else None)
    any_set = lambda f, issue: issue["evidence_sets"][0]  # noqa: E731
    matcher.satisfied_set = any_set
    if saved[1] is not None:
        core.satisfied_set = any_set
    try:
        yield
    finally:
        matcher.satisfied_set = saved[0]
        if saved[1] is not None:
            core.satisfied_set = saved[1]


def _submitted(traj) -> list:
    a = traj[-1]["action"] or {}
    if a.get("tool") != "submit":
        return []
    args = a.get("args") or {}
    f = args.get("findings")
    return f.get("findings", []) if isinstance(f, dict) else (f or [])


def answers(n: int):
    from auditenv.env.data import PublicData
    from auditenv.policies.attacks import attack_findings, cem_best_policy
    from auditenv.runner import run_episode

    out = []
    for cfg, seed, ep in episodes(n, 780000):
        pub = PublicData(ep.files)
        a = {}
        for p in ("oracle", "simple_reconcile", "flag_all", "random_explorer"):
            r = run_episode(p, episode=ep, isolate=False, record=True)
            a[p] = (_submitted(r["trajectory"]), r["grade"]["inspection_steps"])
        sr, st = a["simple_reconcile"]
        a["simple_reconcile, evidence stripped"] = ([{**f, "evidence_ids": []} for f in sr], st)
        pol = cem_best_policy(seed)
        r = run_episode("attack:cem_best", episode=ep, policy_obj=pol, record=True)
        a["attack:cem_best (no answer key)"] = (_submitted(r["trajectory"]), r["grade"]["inspection_steps"])
        for name in ("evidence_spam", "guess_ids", "type_bruteforce"):
            a[f"attack:{name}"] = (attack_findings(name, ep.truth, pub, seed), 0)
        out.append((ep, a))
    return out


def grade_all(data, ignore: bool) -> dict:
    from auditenv.grader.core import EpisodeGrader

    res = {}
    ctx = evidence_ignored() if ignore else contextlib.nullcontext()
    with ctx:
        for ep, a in data:
            g = EpisodeGrader(ep.truth)
            for name, (fs, st) in a.items():
                r = g.grade({"episode_id": ep.episode_id, "findings": fs}, st)
                res.setdefault(name, []).append((r["reward"], r["tp"]))
    return res


def render(data, n) -> str:
    on, off = grade_all(data, False), grade_all(data, True)
    out = ["# Абляция: награда без требования доказательств", "",
           f"Сгенерировано `make ablation` (`tools/ablation_evidence.py`): {n} свежих эпизодов (seed 780000+). Те же ответы",
           "оценены настоящим оценщиком дважды: как есть и с отключённой проверкой набора доказательств (подмена",
           "`matcher.satisfied_set` только в процессе инструмента; файлы ядра не меняются).", "",
           "| Ответ | Возврат с доказательствами | без доказательств | Δ | TP с / без |", "|---|---|---|---|---|"]
    for name in on:
        a = statistics.fmean(x[0] for x in on[name])
        b = statistics.fmean(x[0] for x in off[name])
        out.append(f"| `{name}` | {a:+.3f} | {b:+.3f} | {b - a:+.3f} | {sum(x[1] for x in on[name])} / {sum(x[1] for x in off[name])} |")
    gain = {k: statistics.fmean(x[0] for x in off[k]) - statistics.fmean(x[0] for x in on[k]) for k in on}
    top = max(gain, key=gain.get)
    out += ["", "## Вывод", "",
            f"* Больше всего от отмены доказательств выигрывает `{top}` (Δ = {gain[top]:+.3f}): ответ, который **знает** суммы",
            f"  и ID, но ничего не доказывает, получает {sum(x[1] for x in off[top])} TP — столько же, сколько oracle "
            f"({sum(x[1] for x in off['oracle'])}).",
            "* «Знать ответ — не значит доказать»: `simple_reconcile` без доказательств получает столько же, сколько с ними, только",
            "  если доказательства не требуются; с требованием — 0 TP. Награда учит агента ссылаться на записи.",
            "* Стратегии без доступа к эталону (`attack:cem_best`, `flag_all`, `random_explorer`) почти не выигрывают: их",
            "  сдерживают тип, ID и сумма. Доказательства закрывают именно путь «узнал ответ в обход инструментов»."]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args(argv)
    data = answers(a.n)
    (ROOT / "reports" / "ablation_evidence.md").write_text(render(data, a.n), "utf-8")
    print(f"ablation: {a.n} episodes -> reports/ablation_evidence.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
