"""make train: the learned policy is trained by RL on the env reward, reproducibly, and it uses only
what an agent sees (docs/TRAINING.md)."""

import pytest

from auditenv.generator.episode import generate_episode
from auditenv.policies.learned import FEATURES, LearnedReconcile, load_weights
from auditenv.runner import run_episode


def test_weights_file_matches_features_and_learned_the_look_alikes():
    w = dict(zip(FEATURES, load_weights()))
    # learned from reward alone: credit-note context and overpayments mark look-alikes
    assert w["credit_note_context"] < -1 and w["overpayment"] < -1


@pytest.mark.slow
def test_committed_weights_reproduce_byte_exact():
    from auditenv.train import main

    assert main(["--check"]) == 0


def test_learned_policy_runs_through_the_env_like_any_agent():
    ep = generate_episode(13, "clean-only")
    g = run_episode("learned_reconcile", episode=ep, isolate=True, record=False)["grade"]
    assert g["n_truth"] == 0 and g["fp"] == 0 and g["reward"] > 0.9


@pytest.mark.slow
def test_untrained_weights_do_worse_than_trained():
    eps = [generate_episode(s, "dev-mixed") for s in range(31, 37)]
    trained = sum(run_episode("x", episode=e, isolate=False, record=False,
                              policy_obj=LearnedReconcile(0))["grade"]["reward"] for e in eps)
    zero = sum(run_episode("x", episode=e, isolate=False, record=False,
                           policy_obj=LearnedReconcile(0, weights=[0.0] * len(FEATURES)))["grade"]["reward"]
               for e in eps)
    assert trained > zero
