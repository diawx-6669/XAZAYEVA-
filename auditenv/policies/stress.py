"""Policies that exercise the termination contract in recorded trajectories.

step_burner  reads the ledger page by page and never submits: always truncated at 100 steps
             (the trajectory shows truncation_reason = max_steps and an empty graded answer).
hung         answers the first observation never: the runner times out, truncates the episode
             (truncation_reason = policy_unresponsive) and grades an empty answer.
"""

import time

from .base import Policy


class StepBurner(Policy):
    name = "step_burner"

    def reset(self):
        super().reset()
        self.cursor = None

    def act(self, obs):
        res = obs.get("result") or {}
        if "next_cursor" in res:
            self.cursor = res["next_cursor"]
        if self.cursor:
            return {"tool": "list_records", "args": {"table": "ledger", "limit": 50, "cursor": self.cursor}}
        return {"tool": "list_records", "args": {"table": "ledger", "limit": 50}}


class Hung(Policy):
    name = "hung"

    def act(self, obs):
        time.sleep(10 ** 6)
