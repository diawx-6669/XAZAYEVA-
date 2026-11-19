"""Oracle: GRADER-SIDE ONLY. Reads the closed truth and submits the correct findings with the
first evidence set on the very first step. Checks the reward maximum, not agent ability."""

from .base import Policy, finding, submit


def oracle_findings(truth: dict) -> list:
    return [finding(i["type"], i["affected_ids"], i["expected_amount_minor"], i["currency"], i["evidence_sets"][0],
                    "oracle") for i in truth["issues"]]


class Oracle(Policy):
    name = "oracle"
    needs_truth = True

    def __init__(self, seed=0, truth=None):
        super().__init__(seed)
        self.truth = truth

    def act(self, observation):
        return submit(self.truth["episode_id"], oracle_findings(self.truth))
