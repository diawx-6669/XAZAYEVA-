"""EpisodeGrader: holds the closed truth and scores a submission. Lives in the
evaluator's process; the agent only ever sees what the env puts into observations."""

from __future__ import annotations

import json
from pathlib import Path

from .matcher import match, satisfied_set
from .normalize import normalize_finding
from .reward import prf, shared_reward
from .schema import validate_findings


class EpisodeGrader:
    def __init__(self, truth: dict, tolerance: int = 1):
        self._truth = truth
        self.tolerance = tolerance

    @classmethod
    def from_dir(cls, grader_dir, tolerance: int = 1) -> "EpisodeGrader":
        truth = json.loads((Path(grader_dir) / "truth.json").read_text("utf-8"))
        return cls(truth, tolerance)

    @property
    def episode_id(self) -> str:
        return self._truth["episode_id"]

    def grade(self, submission, inspection_steps: int, seen_ids=frozenset(), truncated: bool = False) -> dict:
        issues = self._truth["issues"]
        base = {"episode_id": self.episode_id, "inspection_steps": inspection_steps, "truncated": truncated,
                "n_truth": len(issues)}
        if truncated:
            submission = {"episode_id": self.episode_id, "findings": []}
        err = validate_findings(submission, self.episode_id)
        if err is not None:
            return {**base, "valid": False, "error": err, "tp": 0, "fp": 0, "fn": len(issues), "n_findings": 0,
                    "precision": 0.0, "recall": 0.0, "f1": 0.0, "reward": -1.0, "reward_experimental": -1.0,
                    "findings": []}
        findings = [normalize_finding(f) for f in submission["findings"]]
        m = match(findings, issues, self.tolerance)
        tp = len(m["pairs"])
        fp = len(findings) - tp
        fn = len(issues) - tp
        p, r, f1 = prf(tp, fp, fn)
        by_id = {i["issue_id"]: i for i in issues}
        tp_exp = sum(1 for k, iid in m["pairs"].items()
                     if set(satisfied_set(findings[k], by_id[iid])) <= set(seen_ids))
        miss = tp - tp_exp
        _, _, f1e = prf(tp_exp, fp + miss, fn + miss)
        per = []
        for k in range(len(findings)):
            if k in m["pairs"]:
                per.append({"index": k, "matched": m["pairs"][k], "reason": None})
            else:
                per.append({"index": k, "matched": None, "reason": m["reasons"][k]})
        return {**base, "valid": True, "error": None, "tp": tp, "fp": fp, "fn": fn, "n_findings": len(findings),
                "precision": float(p), "recall": float(r), "f1": float(f1),
                "reward": shared_reward(f1, inspection_steps), "reward_experimental": shared_reward(f1e, inspection_steps),
                "tp_experimental": tp_exp, "missed": m["missed"], "findings": per}
