"""make experiment (round 2, E6, optional): does the environment give a LEARNABLE signal?

Protocol (fixed in docs/EXPERIMENT.md and committed BEFORE the run):
  arms      = simple_reconcile with every subset of its 4 detection rules x every subset of 4 refinements
              (256 arms; the official baseline is {dup, alloc, fx, cutoff})
  selection = successive halving on 120 TRAIN episodes (6 open configs x seeds 600000-600019, no salt)
  test      = ONE run on 300 HELD-OUT episodes (6 configs x seeds 700000-700049) with a NEW salt
  metric    = mean shared reward; paired bootstrap 95 % CI of (chosen - baseline), B = 10000, seed 12345
  control   = placebo arm (baseline + a rule with no effect) vs baseline: the difference must be exactly 0
No weights are trained; the claim is only "the reward signal is learnable", never "a model improved".
"""

from __future__ import annotations

import itertools
import json
import os
import random
import statistics

from .policies.simple_reconcile import BASE_RULES, OPTIONAL_RULES, SimpleReconcile

CONFIGS = ["train-easy", "train-global", "dev-mixed", "dev-global", "interaction-heavy", "clean-only"]
TRAIN_SEEDS = range(600000, 600020)
TEST_SEEDS = range(700000, 700050)
HELDOUT_SALT = "auditenv-E6-heldout-2026-11-20"
BOOT_B, BOOT_SEED = 10000, 12345


def arms() -> list:
    base = sorted(BASE_RULES)
    out = []
    for k in range(len(base) + 1):
        for det in itertools.combinations(base, k):
            for m in range(len(OPTIONAL_RULES) + 1):
                for opt in itertools.combinations(OPTIONAL_RULES, m):
                    out.append(tuple(sorted(det + opt)))
    return sorted(set(out))


def reward(rules, ep) -> float:
    from .runner import run_episode

    return run_episode("simple_reconcile", episode=ep, isolate=False, record=False,
                       policy_obj=SimpleReconcile(0, rules))["grade"]["reward"]


def successive_halving(train_eps, cand):
    cache = {}

    def score(a, n):
        for i in range(n):
            if (a, i) not in cache:
                cache[(a, i)] = reward(a, train_eps[i])
        return statistics.mean(cache[(a, i)] for i in range(n))

    n, rounds = 8, []
    while len(cand) > 1:
        n = min(n, len(train_eps))
        ranked = sorted(cand, key=lambda a: (-score(a, n), a))
        rounds.append({"arms": len(cand), "episodes": n, "leader": list(ranked[0]), "leader_reward": score(ranked[0], n)})
        cand = ranked[: max(1, len(cand) // 2)]
        n *= 2
    return cand[0], rounds, len(cache)


def paired_bootstrap(diffs, b=BOOT_B, seed=BOOT_SEED):
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(statistics.mean(diffs[rng.randrange(n)] for _ in range(n)) for _ in range(b))
    return means[int(0.025 * b)], means[int(0.975 * b) - 1]


def main(out_dir=None) -> dict:
    from pathlib import Path

    from .analysis import generate_many
    from .generator.episode import Episode
    from .paths import ROOT

    def eps(items):
        return [Episode(t["episode_id"], f, t, {}) for _, _, f, t, _ in generate_many(items)]

    train = eps([(c, s) for s in TRAIN_SEEDS for c in CONFIGS])
    chosen, rounds, n_eval = successive_halving(train, arms())
    old = os.environ.get("AUDITENV_SEED_SALT")
    os.environ["AUDITENV_SEED_SALT"] = HELDOUT_SALT  # inherited by the generator worker processes
    try:
        test = eps([(c, s) for s in TEST_SEEDS for c in CONFIGS])
    finally:
        if old is None:
            os.environ.pop("AUDITENV_SEED_SALT", None)
        else:
            os.environ["AUDITENV_SEED_SALT"] = old
    base = tuple(sorted(BASE_RULES))
    placebo = tuple(sorted(BASE_RULES | {"placebo"}))
    r_base = [reward(base, e) for e in test]
    r_chosen = [reward(chosen, e) for e in test]
    r_placebo = [reward(placebo, e) for e in test]
    d = [a - b for a, b in zip(r_chosen, r_base)]
    dp = [a - b for a, b in zip(r_placebo, r_base)]
    lo, hi = paired_bootstrap(d)
    plo, phi = paired_bootstrap(dp)
    res = {"chosen_rules": list(chosen), "baseline_rules": list(base), "selection_rounds": rounds,
           "train_evaluations": n_eval, "train_episodes": len(train), "test_episodes": len(test),
           "test": {"baseline_mean": statistics.mean(r_base), "chosen_mean": statistics.mean(r_chosen),
                    "diff_mean": statistics.mean(d), "diff_ci95": [lo, hi],
                    "placebo_diff_mean": statistics.mean(dp), "placebo_ci95": [plo, phi]},
           "verdict": ("learnable signal: CI of the paired difference excludes 0" if lo > 0
                       else "no evidence of a learnable signal at this budget (CI includes 0 or is negative)")}
    out = Path(out_dir or ROOT / "reports")
    out.mkdir(parents=True, exist_ok=True)
    (out / "experiment.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", "utf-8")
    return res
