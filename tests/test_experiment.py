"""E6 plumbing (the experiment itself is `make experiment`, not part of make check)."""

from auditenv.experiment import arms, paired_bootstrap, reward
from auditenv.generator.episode import generate_episode
from auditenv.policies.simple_reconcile import BASE_RULES
from auditenv.runner import run_episode


def test_arm_space_and_placebo_is_a_no_op():
    a = arms()
    assert len(a) == 256 and tuple(sorted(BASE_RULES)) in a
    for seed, cfg in ((1, "dev-mixed"), (2, "clean-only"), (3, "interaction-heavy")):
        ep = generate_episode(seed, cfg)
        base = reward(tuple(sorted(BASE_RULES)), ep)
        assert reward(tuple(sorted(BASE_RULES | {"placebo"})), ep) == base
        assert base == run_episode("simple_reconcile", episode=ep, isolate=False)["grade"]["reward"]


def test_paired_bootstrap_brackets_the_mean():
    lo, hi = paired_bootstrap([0.1, 0.2, 0.3, 0.4] * 10, b=500)
    assert lo <= 0.25 <= hi and paired_bootstrap([0.0] * 20, b=200) == (0.0, 0.0)


def test_e6v2_protocol_is_new_and_e6_is_frozen():
    from auditenv import experiment as ex

    e6, v2 = ex.PROTOCOLS["E6"], ex.PROTOCOLS["E6v2"]
    # E6 is frozen exactly as published in docs/EXPERIMENT.md
    assert e6["salt"] == "auditenv-E6-heldout-2026-11-20" and e6["out"] == "experiment.json"
    assert (e6["train_seeds"], e6["test_seeds"]) == (range(600000, 600020), range(700000, 700050))
    # v2: new salt, seed ranges disjoint from E6 and from each other, separate report
    assert v2["salt"] != e6["salt"] and v2["out"] != e6["out"]
    seeds = [set(e6["train_seeds"]), set(e6["test_seeds"]), set(v2["train_seeds"]), set(v2["test_seeds"])]
    assert all(not (a & b) for i, a in enumerate(seeds) for b in seeds[i + 1:])
    # the 'unseen' configs really are absent from selection and present in the held-out set
    assert not set(v2["unseen_configs"]) & set(v2["train_configs"])
    assert set(v2["unseen_configs"]) <= set(v2["test_configs"])
    assert len(v2["train_seeds"]) * len(v2["train_configs"]) == 120
    assert len(v2["test_seeds"]) * len(v2["test_configs"]) == 300
