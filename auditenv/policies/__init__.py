"""Baseline policy adapters."""

from .flag_all import FlagAll
from .random_explorer import RandomExplorer
from .simple_reconcile import SimpleReconcile
from .truth_hunter import TruthHunter

AGENT_POLICIES = {"random_explorer": RandomExplorer, "simple_reconcile": SimpleReconcile, "flag_all": FlagAll,
                  "truth_hunter": TruthHunter}  # truth_hunter: adversary for isolation tests only
BASELINES = ["random_explorer", "simple_reconcile", "flag_all", "oracle"]


def make_policy(name: str, seed: int = 0):
    p = AGENT_POLICIES[name](seed)
    p.reset()
    return p
