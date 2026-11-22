"""careful_reconcile: the reference auditor with every refinement on. It must stay silent on clean books
and must not do worse than the weak baseline: the distractors are separable by correct bookkeeping."""

import pytest

from auditenv.generator.episode import generate_episode
from auditenv.runner import run_episode

pytestmark = pytest.mark.slow


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_silent_on_clean_books(seed):
    ep = generate_episode(seed, "clean-only")
    g = run_episode("careful_reconcile", episode=ep, isolate=False, record=False)["grade"]
    assert g["n_truth"] == 0 and g["fp"] == 0 and g["reward"] > 0.9


def test_not_worse_than_simple_reconcile():
    tot = {"simple_reconcile": 0.0, "careful_reconcile": 0.0}
    for seed in range(21, 27):
        ep = generate_episode(seed, "dev-mixed")
        for pol in tot:
            tot[pol] += run_episode(pol, episode=ep, isolate=False, record=False)["grade"]["reward"]
    assert tot["careful_reconcile"] >= tot["simple_reconcile"]
