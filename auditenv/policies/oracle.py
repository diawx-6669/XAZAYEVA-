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


# ------------------------------------------------------------- jury oracles
# Every equivalent way of writing the CORRECT answer must score the maximum: the matcher must not
# reward one surface form over another (round 2, C5).
JURY_ORACLES = ["first_set", "last_set", "union_of_sets", "shuffled_order", "repeated_affected_ids",
                "lowercase_currency", "empty_explanation", "flat_submit"]


def jury_findings(name: str, truth: dict, seed: int = 0):
    """(findings, flat) for one jury oracle variant."""
    import random

    rng = random.Random(seed)
    issues = truth["issues"]
    if name == "first_set":
        return oracle_findings(truth), False
    if name == "last_set":
        return [finding(i["type"], i["affected_ids"], i["expected_amount_minor"], i["currency"], i["evidence_sets"][-1])
                for i in issues], False
    if name == "union_of_sets":
        return [finding(i["type"], i["affected_ids"], i["expected_amount_minor"], i["currency"],
                        sorted({x for s in i["evidence_sets"] for x in s})) for i in issues], False
    if name == "shuffled_order":
        out = []
        for i in issues:
            ev = list(i["evidence_sets"][0])
            rng.shuffle(ev)
            out.append(finding(i["type"], i["affected_ids"], i["expected_amount_minor"], i["currency"], ev))
        rng.shuffle(out)
        return out, False
    if name == "repeated_affected_ids":
        return [dict(f, affected_ids=f["affected_ids"] * 3) for f in oracle_findings(truth)], False
    if name == "lowercase_currency":
        return [dict(f, currency=f["currency"].lower()) for f in oracle_findings(truth)], False
    if name == "empty_explanation":
        return [dict(f, explanation="") for f in oracle_findings(truth)], False
    if name == "flat_submit":
        return oracle_findings(truth), True
    raise KeyError(name)


def jury_action(name: str, truth: dict) -> dict:
    fs, flat = jury_findings(name, truth)
    if flat:
        return {"tool": "submit", "args": {"episode_id": truth["episode_id"], "findings": fs}}
    return submit(truth["episode_id"], fs)


class OracleObserving(Policy):
    """GRADER-SIDE. Like the oracle, but first OPENS every ID of each issue's first evidence set through
    the tools (get_document / get_record), then submits: the experimental reward (TP only for evidence
    the agent has actually seen) then equals the shared one. Fits in 100 steps: <= 12 issues x 6 IDs."""

    name = "oracle_observing"
    needs_truth = True

    def __init__(self, seed=0, truth=None, public=None):
        super().__init__(seed)
        self.truth = truth
        self.public = public
        ids = []
        for i in truth["issues"]:
            for x in i["evidence_sets"][0]:
                if x not in ids:
                    ids.append(x)
        self.queue = [self._open(x) for x in ids]

    def _open(self, x):
        if x == "policy":
            return {"tool": "get_record", "args": {"table": "policy", "id": "policy"}}
        if x.startswith("fx:"):
            return {"tool": "get_record", "args": {"table": "fx", "id": x}}
        if x in self.public.doc_by_id:
            return {"tool": "get_document", "args": {"doc_id": x}}
        return {"tool": "get_record", "args": {"table": "ledger", "id": x}}

    def act(self, observation):
        if self.queue and observation.get("steps_remaining", 0) > 1:
            return self.queue.pop(0)
        return submit(self.truth["episode_id"], oracle_findings(self.truth))
