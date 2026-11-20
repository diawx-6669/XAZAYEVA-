"""Leak scanner: closed data must never appear in observations.

Flags: issue IDs; words that only exist on the grader side (truth, provenance, grader/,
issue_id, evidence_sets, expected_amount, seed); an error type name in the same
observation as a truth affected_id; observations with keys outside the contract; error
objects carrying anything but a code.
"""

from __future__ import annotations

import json
import re

from .canon import dumps
from .env.errors import CODES

FORBIDDEN = ["truth", "provenance", "grader/", "issue_id", "evidence_sets", "expected_amount", "seed",
             "Traceback", "/home/", "/app/", "episodes/"]
TYPES = ["duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff"]
ISSUE_RE = re.compile(r"ISS-[0-9]{3}")
FIRST_KEYS = {"task", "manifest", "policy_summary", "steps_remaining"}


def scan_observation(obs, truth=None, first=False) -> list:
    problems = []
    if not isinstance(obs, dict):
        return ["observation_not_object"]
    keys = set(obs)
    if first:
        if keys != FIRST_KEYS:
            problems.append("bad_first_keys")
    else:
        if not ("steps_remaining" in keys and len(keys) == 2 and (("result" in keys) ^ ("error" in keys))):
            problems.append("bad_keys")
        if "error" in obs and (not isinstance(obs["error"], dict) or set(obs["error"]) != {"code"}
                               or obs["error"]["code"] not in CODES):
            problems.append("error_with_payload")
    text = dumps(obs)
    scan = text if not first else dumps({k: v for k, v in obs.items() if k != "task"})
    for w in FORBIDDEN:
        if w in scan:
            problems.append(f"forbidden:{w}")
    if ISSUE_RE.search(text):
        problems.append("issue_id_pattern")
    if truth:
        for iss in truth["issues"]:
            if iss["issue_id"] in text:
                problems.append("issue_id")
            if not first and any(t in text for t in TYPES) and any(a in text for a in iss["affected_ids"]):
                problems.append("type_next_to_affected_id")
    return sorted(set(problems))


def scan_lines(lines, truths: dict) -> list:
    out = []
    for n, rec in enumerate(lines):
        if isinstance(rec, (str, bytes)):
            rec = json.loads(rec)
        first = rec["step"] == 0 and "truncation_reason" not in rec  # a hung policy is truncated at step 0
        probs = scan_observation(rec["observation"], truths.get(rec["episode_id"]), first=first)
        if probs:
            out.append({"line": n, "episode_id": rec["episode_id"], "step": rec["step"], "problems": probs})
    return out
