"""Shared helper for round-4 measurement tools: run policies in-process on fresh episodes (stdlib only).

In-process runs (no child process) give exactly the same grade as isolated runs - the policy code and
the env are the same, only the process boundary differs (tests/test_runner.py) - and are ~50x faster."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIGS = ["train-easy", "train-global", "dev-mixed", "dev-global", "interaction-heavy", "clean-only"]
BASELINES = ["random_explorer", "simple_reconcile", "flag_all", "oracle"]


def episodes(n: int, base_seed: int, configs=CONFIGS):
    from auditenv.generator.episode import generate_episode

    for i in range(n):
        cfg = configs[i % len(configs)]
        yield cfg, base_seed + i, generate_episode(base_seed + i, cfg)


def grade(policy, ep, mode: str = "train") -> dict:
    """policy: a baseline name or a Policy object."""
    from auditenv.runner import run_episode

    if isinstance(policy, str):
        return run_episode(policy, episode=ep, isolate=False, record=False, mode=mode)["grade"]
    policy.reset()
    return run_episode(getattr(policy, "name", "custom"), episode=ep, policy_obj=policy, record=False, mode=mode)["grade"]
