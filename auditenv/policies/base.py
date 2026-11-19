"""Policy adapter interface: act(observation) -> action. Policies keep their own state and see
only observations (the oracle and the attacks are the documented exceptions: grader-side only)."""

import random


class Policy:
    name = "base"
    needs_truth = False

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.rng = random.Random(seed)

    def reset(self):
        self.rng = random.Random(self.seed)

    def act(self, observation: dict) -> dict:
        raise NotImplementedError


def submit(episode_id, findings):
    return {"tool": "submit", "args": {"findings": {"episode_id": episode_id, "findings": findings}}}


def finding(typ, ids, amount, currency, evidence, explanation=""):
    return {"type": typ, "affected_ids": list(ids), "claimed_amount_minor": int(amount), "currency": currency,
            "evidence_ids": list(evidence)[:10], "explanation": explanation[:1000]}


class TableReader:
    """Helper: pages through tables in order, then hands control back."""

    def __init__(self, tables):
        self.queue = list(tables)
        self.data = {t: [] for t in tables}
        self.cursor = None
        self.current = None

    def next_action(self):
        if self.current is None:
            if not self.queue:
                return None
            self.current = self.queue.pop(0)
            self.cursor = None
        args = {"table": self.current, "limit": 50}
        if self.cursor:
            args["cursor"] = self.cursor
        return {"tool": "list_records", "args": args}

    def feed(self, obs):
        res = obs.get("result")
        if not res or "records" not in res:
            self.current = None  # give up on this table
            return
        self.data[self.current].extend(res["records"])
        self.cursor = res["next_cursor"]
        if self.cursor is None:
            self.current = None
