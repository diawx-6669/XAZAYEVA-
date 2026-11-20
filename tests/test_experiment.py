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
