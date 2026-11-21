"""Independent jury grader, written from section 05 of docs/CASE.md only (no auditenv import).

grade(truth, submit_args, inspection_steps, truncated) -> dict with tp/fp/fn/P/R/F1/reward.
"""
FINDING_KEYS = {"type", "affected_ids", "claimed_amount_minor", "currency", "evidence_ids", "explanation"}


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _str_list(x, max_len=None):
    return isinstance(x, list) and all(isinstance(e, str) for e in x) and (max_len is None or len(x) <= max_len)


def unwrap(args):
    """Both submit shapes from docs/CONTRACT.md: {findings: {episode_id, findings}} and flat."""
    if isinstance(args, dict) and isinstance(args.get("findings"), dict) and set(args) == {"findings"}:
        return args["findings"]
    return args


def validate(sub, episode_id):
    if not isinstance(sub, dict) or set(sub) != {"episode_id", "findings"}:
        return "structure"
    if sub["episode_id"] != episode_id:
        return "episode_id"
    fs = sub["findings"]
    if not isinstance(fs, list) or len(fs) > 30:
        return "findings"
    for f in fs:
        if not isinstance(f, dict) or set(f) != FINDING_KEYS:
            return "finding_keys"
        if not isinstance(f["type"], str) or not isinstance(f["currency"], str):
            return "finding_types"
        if not _is_int(f["claimed_amount_minor"]):
            return "amount"
        if not _str_list(f["affected_ids"]) or not _str_list(f["evidence_ids"], 10):
            return "ids"
        if not isinstance(f["explanation"], str) or len(f["explanation"]) > 1000:
            return "explanation"
    return None


def norm_ids(ids):
    return sorted({i.strip() for i in ids})


def can_match(f, issue, tol):
    if f["type"] != issue["type"]:
        return False
    if norm_ids(f["affected_ids"]) != norm_ids(issue["affected_ids"]):
        return False
    if abs(f["claimed_amount_minor"] - issue["expected_amount_minor"]) > tol:
        return False
    if f["currency"].strip().upper() != issue["currency"].upper():
        return False
    ev = set(norm_ids(f["evidence_ids"]))
    return any(set(s) <= ev for s in issue["evidence_sets"])


def max_matching(n_f, n_i, adj):
    """Kuhn's augmenting paths; returns matching size."""
    match_i = [-1] * n_i

    def try_f(u, seen):
        for v in adj[u]:
            if v in seen:
                continue
            seen.add(v)
            if match_i[v] == -1 or try_f(match_i[v], seen):
                match_i[v] = u
                return True
        return False

    return sum(1 for u in range(n_f) if try_f(u, set()))


def grade(truth, submit_args, inspection_steps, truncated=False):
    issues = truth["issues"]
    tol = truth.get("tolerance_minor", 1)
    if truncated or submit_args is None:
        findings, err = [], None
    else:
        sub = unwrap(submit_args)
        err = validate(sub, truth["episode_id"])
        findings = [] if err else sub["findings"]
    if err:
        return {"valid": False, "error": err, "tp": 0, "fp": 0, "fn": len(issues), "precision": 0.0,
                "recall": 0.0, "f1": 0.0, "reward": -1.0, "inspection_steps": inspection_steps}
    adj = [[j for j, i in enumerate(issues) if can_match(f, i, tol)] for f in findings]
    tp = max_matching(len(findings), len(issues), adj)
    fp, fn = len(findings) - tp, len(issues) - tp
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    if not issues and not findings:
        f1 = 1.0
    elif not issues:
        f1 = 0.0
    else:
        f1 = 2 * tp / (2 * tp + fp + fn)
    reward = max(-1.0, min(1.0, 2 * f1 - 1 - 0.002 * inspection_steps))
    return {"valid": True, "error": None, "tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r,
            "f1": f1, "reward": reward, "inspection_steps": inspection_steps}
