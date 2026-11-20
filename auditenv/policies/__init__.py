"""Baseline policy adapters."""

from .flag_all import FlagAll
from .random_explorer import RandomExplorer
from .simple_reconcile import SimpleReconcile
from .stress import Hung, StepBurner

AGENT_POLICIES = {"random_explorer": RandomExplorer, "simple_reconcile": SimpleReconcile, "flag_all": FlagAll,
                  "step_burner": StepBurner, "hung": Hung}
BASELINES = ["random_explorer", "simple_reconcile", "flag_all", "oracle"]


def make_policy(name: str, seed: int = 0):
    p = AGENT_POLICIES[name](seed)
    p.reset()
    return p
