"""One-to-one matching of findings to truth issues.

A finding is a *candidate* for an issue iff: same type; normalized affected_ids equal the
canonical ids exactly; |claimed - expected| <= tolerance; same currency; and at least one
evidence set is fully contained in evidence_ids.

Maximum bipartite matching (Kuhn's augmenting paths). Tie-break: issues are processed in
increasing issue_id, and each issue tries its candidate findings in increasing index, so
the smallest issue_id wins first, then the smallest finding index. Unmatched findings
(including repeats of an already matched issue) are FP; unmatched issues are FN.
"""

REASONS = ("wrong_type", "ids_mismatch", "amount_out_of_tolerance", "currency_mismatch", "evidence_incomplete",
           "duplicate_finding", "unmatched")


def satisfied_set(f: dict, issue: dict):
    for s in issue["evidence_sets"]:
        if set(s) <= f["evidence_ids"]:
            return s
    return None


def is_candidate(f: dict, issue: dict, tol: int) -> bool:
    return (f["type"] == issue["type"]
            and f["affected_ids"] == sorted(issue["affected_ids"])
            and abs(f["claimed_amount_minor"] - issue["expected_amount_minor"]) <= tol
            and f["currency"] == issue["currency"]
            and satisfied_set(f, issue) is not None)


def miss_reason(f: dict, issues: list, tol: int) -> str:
    same = [i for i in issues if i["type"] == f["type"] and sorted(i["affected_ids"]) == f["affected_ids"]]
    if not same:
        if any(sorted(i["affected_ids"]) == f["affected_ids"] for i in issues):
            return "wrong_type"
        if any(i["type"] == f["type"] for i in issues):
            return "ids_mismatch"
        return "unmatched"
    i = same[0]
    if f["currency"] != i["currency"]:
        return "currency_mismatch"
    if abs(f["claimed_amount_minor"] - i["expected_amount_minor"]) > tol:
        return "amount_out_of_tolerance"
    if satisfied_set(f, i) is None:
        return "evidence_incomplete"
    return "duplicate_finding"


def match(findings: list, issues: list, tol: int = 1) -> dict:
    issues = sorted(issues, key=lambda i: i["issue_id"])
    adj = {i["issue_id"]: [k for k, f in enumerate(findings) if is_candidate(f, i, tol)] for i in issues}
    owner = {}  # finding index -> issue_id

    def augment(iid, seen):
        for k in adj[iid]:
            if k in seen:
                continue
            seen.add(k)
            if k not in owner or augment(owner[k], seen):
                owner[k] = iid
                return True
        return False

    for i in issues:
        augment(i["issue_id"], set())
    pairs = {k: iid for k, iid in sorted(owner.items())}
    reasons = {k: miss_reason(f, issues, tol) for k, f in enumerate(findings) if k not in pairs}
    matched = set(pairs.values())
    return {"pairs": pairs, "reasons": reasons, "missed": [i["issue_id"] for i in issues if i["issue_id"] not in matched]}
