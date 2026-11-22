"""make train: policy improvement on the environment's reward (docs/TRAINING.md). Pure Python, deterministic.

Protocol
  model     = logistic policy over candidate features (auditenv/policies/learned.py), w = 0 at start
  train     = 160 episodes: train-easy, train-global, dev-mixed, interaction-heavy x seeds 800000-800039
              (open configs, no salt)
  held-out  = 180 episodes: all 6 open configs x seeds 810000-810029, NEW salt (never used before);
              dev-global and clean-only are never seen in training
  update    = policy improvement from the env reward: for every candidate i, advantage
              A_i = R(greedy answer with i) - R(greedy answer without i) (two grader calls = two rollouts
              from the same state); w += lr * |A_i| * (1[A_i > 0] - p_i) * x_i (advantage-weighted
              logistic regression). The model never sees labels or the answer key, only rewards.
  report    = greedy policy (p >= 0.5) on train and held-out every few epochs; final paired bootstrap
              95 % CI of (learned - simple_reconcile) on held-out, B = 10000
The grader is used exactly as the env uses it: the model only ever receives the scalar reward.
"""

from __future__ import annotations

import json
import os
import random
import statistics
from pathlib import Path

from .generator.episode import generate_episode
from .grader.core import EpisodeGrader
from .paths import ROOT
from .policies.base import Policy, TableReader, submit
from .policies.learned import FEATURES, WEIGHTS_FILE, analyse_with, candidates, sigmoid
from .policies.simple_reconcile import BASE_RULES, OPTIONAL_RULES

TRAIN_CONFIGS = ["train-easy", "train-global", "dev-mixed", "interaction-heavy"]
TRAIN_SEEDS = range(800000, 800040)
HELDOUT_CONFIGS = ["train-easy", "train-global", "dev-mixed", "interaction-heavy", "dev-global", "clean-only"]
HELDOUT_SEEDS = range(810000, 810030)
HELDOUT_SALT = "auditenv-train-heldout-2026-11-22"
EPOCHS, LR, SEED = 30, 0.5, 20261122
SALT_ENV = "AUDITENV_SEED_SALT"


class _Collector(Policy):
    """Reads like simple_reconcile and submits nothing: we only want what an agent would have seen."""

    name = "collector"

    def reset(self):
        super().reset()
        self.reader, self.policy, self.asked = None, None, False

    def act(self, obs):
        if "manifest" in obs:
            self.manifest = obs["manifest"]
            self.reader = TableReader(["ledger", "invoices", "payments", "fx"])
            self.asked = True
            return {"tool": "get_record", "args": {"table": "policy", "id": "policy"}}
        if self.asked:
            self.policy = (obs.get("result") or {}).get("record") or {}
            self.asked = False
        else:
            self.reader.feed(obs)
        a = self.reader.next_action()
        return a if a is not None else submit(self.manifest["episode_id"], [])


def prepare(configs, seeds, salt=None) -> list:
    """Per episode: candidates (finding, x), the grader, and the inspection steps an agent spends reading."""
    from .runner import run_episode

    old = os.environ.get(SALT_ENV)
    if salt:
        os.environ[SALT_ENV] = salt
    try:
        out = []
        for cfg in configs:
            for s in seeds:
                ep = generate_episode(s, cfg)
                col = _Collector(0)
                col.reset()
                r = run_episode("collector", episode=ep, isolate=False, record=False, policy_obj=col)
                d, m, pol = col.reader.data, col.manifest, col.policy or {}
                out.append({"config": cfg, "seed": s, "episode_id": ep.episode_id,
                            "cands": candidates(d, m, pol),
                            "simple": analyse_with(d, m, pol, BASE_RULES),
                            "careful": analyse_with(d, m, pol, BASE_RULES | frozenset(OPTIONAL_RULES)),
                            "grader": EpisodeGrader(ep.truth), "steps": r["grade"]["inspection_steps"]})
        return out
    finally:
        if salt:
            if old is None:
                os.environ.pop(SALT_ENV, None)
            else:
                os.environ[SALT_ENV] = old


def reward_of(ep, chosen) -> float:
    sub = {"episode_id": ep["episode_id"], "findings": [f for f, _ in chosen][:30]}
    return ep["grader"].grade(sub, inspection_steps=ep["steps"])["reward"]


def greedy(ep, w):
    return [(f, x) for f, x in ep["cands"] if sigmoid(sum(a * b for a, b in zip(w, x))) >= 0.5]


def mean_greedy(eps, w) -> float:
    return statistics.fmean(reward_of(e, greedy(e, w)) for e in eps)


def train(train_eps, heldout_eps, epochs=EPOCHS, lr=LR, seed=SEED, log_every=5):
    """Policy improvement from counterfactual rewards. For each candidate i of an episode the grader is asked
    twice (like two rollouts of the env from the same state): reward of the current greedy answer WITH i and
    WITHOUT i. The advantage A_i = R(with) - R(without) is the exact gradient of the expected reward with
    respect to p_i for this factorised policy; the logistic model is then moved toward submitting i when
    A_i > 0 and away when A_i < 0, weighted by |A_i| (advantage-weighted regression). Unlike plain
    REINFORCE this does not stall when p_i saturates near 0 or 1."""
    rng = random.Random(seed)
    w = [0.0] * len(FEATURES)
    curve = [{"epoch": 0, "train": mean_greedy(train_eps, w), "heldout": mean_greedy(heldout_eps, w)}]
    order = list(range(len(train_eps)))
    for ep_no in range(1, epochs + 1):
        rng.shuffle(order)
        for i in order:
            e = train_eps[i]
            ps = [sigmoid(sum(a * b for a, b in zip(w, x))) for _, x in e["cands"]]
            chosen = [p >= 0.5 for p in ps]
            for j, ((_, x), p) in enumerate(zip(e["cands"], ps)):
                with_j = [c for k, c in enumerate(e["cands"]) if chosen[k] or k == j]
                without_j = [c for k, c in enumerate(e["cands"]) if chosen[k] and k != j]
                adv = reward_of(e, with_j) - reward_of(e, without_j)
                if adv:
                    g = abs(adv) * ((1.0 if adv > 0 else 0.0) - p)
                    for k in range(len(w)):
                        w[k] += lr * g * x[k]
        if ep_no <= 5 or ep_no % log_every == 0 or ep_no == epochs:
            curve.append({"epoch": ep_no, "train": mean_greedy(train_eps, w), "heldout": mean_greedy(heldout_eps, w)})
    return w, curve


def bootstrap_ci(diffs, b=10000, seed=12345):
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(statistics.fmean(diffs[rng.randrange(n)] for _ in range(n)) for _ in range(b))
    return means[int(0.025 * b)], means[int(0.975 * b) - 1]


def evaluate(heldout_eps, w) -> dict:
    """Held-out rewards of the learned policy and of fixed references, per episode (paired)."""
    rows = []
    for e in heldout_eps:
        rows.append({"config": e["config"], "empty": reward_of(e, []), "submit_all": reward_of(e, e["cands"]),
                     "simple_reconcile": reward_of(e, [(f, None) for f in e["simple"]]),
                     "careful_reconcile": reward_of(e, [(f, None) for f in e["careful"]]),
                     "learned": reward_of(e, greedy(e, w))})
    return {"rows": rows}


def summarize(rows) -> dict:
    keys = ["empty", "submit_all", "simple_reconcile", "careful_reconcile", "learned"]
    out = {"all": {k: statistics.fmean(r[k] for r in rows) for k in keys}}
    for cfg in sorted({r["config"] for r in rows}):
        sub = [r for r in rows if r["config"] == cfg]
        out[cfg] = {k: statistics.fmean(r[k] for r in sub) for k in keys}
    diffs = [r["learned"] - r["simple_reconcile"] for r in rows]
    out["ci95_learned_minus_simple"] = bootstrap_ci(diffs)
    out["n_heldout"] = len(rows)
    return out


def render(res) -> str:
    s, curve, w = res["summary"], res["curve"], res["weights"]
    lo, hi = s["ci95_learned_minus_simple"]
    lines = [
        "# Обучение политики с подкреплением на награде AuditEnv",
        "",
        "Сгенерировано `make train` (`auditenv/train.py`), детерминированно. Протокол и оговорки — `docs/TRAINING.md`.",
        "",
        f"Модель: логистическая политика, {len(w)} весов, старт с нуля. Метод: REINFORCE по терминальной награде "
        f"среды, {res['epochs']} эпох по {res['n_train']} эпизодам (`train-easy`, `train-global`, `dev-mixed`, "
        f"`interaction-heavy`). Проверка: {s['n_heldout']} отложенных эпизодов с новой солью по всем 6 конфигам, "
        "из них `dev-global` и `clean-only` **при обучении не встречались**.",
        "",
        "## Кривая обучения (жадная политика p ≥ 0.5, средняя награда)",
        "",
        "| Эпоха | train | отложенные |",
        "|---|---|---|",
    ]
    lines += [f"| {c['epoch']} | {c['train']:+.3f} | {c['heldout']:+.3f} |" for c in curve]
    lines += [
        "",
        "## Итог на отложенных эпизодах (средняя награда)",
        "",
        "| Набор | пустой ответ | все кандидаты | simple_reconcile | **обученная** | careful_reconcile (ручные правила) |",
        "|---|---|---|---|---|---|",
    ]
    for k in ["all"] + sorted(x for x in s if x not in ("all", "ci95_learned_minus_simple", "n_heldout")):
        v = s[k]
        name = "**все**" if k == "all" else f"`{k}`"
        lines.append(f"| {name} | {v['empty']:+.3f} | {v['submit_all']:+.3f} | {v['simple_reconcile']:+.3f} | "
                     f"**{v['learned']:+.3f}** | {v['careful_reconcile']:+.3f} |")
    verdict = "обученная политика лучше simple_reconcile" if lo > 0 else "нет свидетельств улучшения"
    lines += [
        "",
        f"Разность «обученная − simple_reconcile», парный бутстрап 95 %: **[{lo:+.3f}, {hi:+.3f}]** → {verdict}.",
        "",
        "## Выученные веса",
        "",
        "| Признак | Вес |",
        "|---|---|",
    ]
    lines += [f"| `{k}` | {v:+.3f} |" for k, v in zip(FEATURES, w)]
    lines += [
        "",
        "Отрицательный вес — «такой кандидат чаще ложная тревога». Значения признаков модели никто не "
        "подсказывал: связь «контекст credit note → двойник», «переплата → не ошибка» и т. п. выучена только "
        "из награды.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--check", action="store_true", help="retrain and compare with the committed weights")
    a = ap.parse_args(argv)
    tr = prepare(TRAIN_CONFIGS, TRAIN_SEEDS)
    ho = prepare(HELDOUT_CONFIGS, HELDOUT_SEEDS, salt=HELDOUT_SALT)
    w, curve = train(tr, ho, epochs=a.epochs)
    w = [round(v, 6) for v in w]
    rows = evaluate(ho, w)["rows"]
    res = {"features": FEATURES, "weights": w, "epochs": a.epochs, "lr": LR, "seed": SEED,
           "n_train": len(tr), "train_configs": TRAIN_CONFIGS, "train_seeds": [TRAIN_SEEDS.start, TRAIN_SEEDS.stop],
           "heldout_configs": HELDOUT_CONFIGS, "heldout_seeds": [HELDOUT_SEEDS.start, HELDOUT_SEEDS.stop],
           "heldout_salt": HELDOUT_SALT, "curve": [{k: (round(v, 4) if isinstance(v, float) else v)
                                                    for k, v in c.items()} for c in curve],
           "summary": summarize(rows)}
    res["summary"]["ci95_learned_minus_simple"] = [round(x, 4) for x in res["summary"]["ci95_learned_minus_simple"]]
    for k, v in list(res["summary"].items()):
        if isinstance(v, dict):
            res["summary"][k] = {kk: round(vv, 4) for kk, vv in v.items()}
    text = json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if a.check:
        same = WEIGHTS_FILE.read_text("utf-8") == text
        print(f"train --check: {'weights reproduce byte-exact' if same else 'DIFFERENT from the committed weights'}")
        return 0 if same else 1
    WEIGHTS_FILE.write_text(text, "utf-8")
    (ROOT / "reports" / "training.md").write_text(render(res), "utf-8")
    s = res["summary"]["all"]
    print(f"train: {len(tr)} train / {len(ho)} held-out episodes, {a.epochs} epochs; held-out reward "
          f"learned {s['learned']:+.3f} vs simple_reconcile {s['simple_reconcile']:+.3f}; "
          f"CI95 {res['summary']['ci95_learned_minus_simple']} -> {WEIGHTS_FILE.name}, reports/training.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
