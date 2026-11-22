"""Tests written because `make mutation` (tools/mutation_test.py) found grader bugs the suite could not see.

Round 3, first mutation run: 20/22 killed. Survivors and weak kills, each pinned down here directly:
  M05  type not checked             - survived: a type brute force still gets TP=1, FP=3 either way, so only a
                                      LONE wrong-type finding tells the difference;
  M06  superset of affected_ids     - killed only indirectly (through the generator's coincidence scanner);
  M08  greedy instead of maximum    - survived: test_tie_break_smallest_issue_then_index claimed to check this,
                                      but its instance is solved by greedy matching too.
"""

from auditenv.grader.core import EpisodeGrader
from auditenv.grader.matcher import match
from auditenv.grader.normalize import normalize_finding
from auditenv.policies.base import finding
from auditenv.policies.oracle import oracle_findings


def _issue(iid, typ, ids, amount, sets):
    return {"issue_id": iid, "type": typ, "affected_ids": ids, "expected_amount_minor": amount, "currency": "KZT",
            "evidence_sets": sets}


def _grade(truth_issues, findings):
    g = EpisodeGrader({"episode_id": "ep-mut", "issues": truth_issues, "tolerance_minor": 1})
    return g.grade({"episode_id": "ep-mut", "findings": findings}, 0)


def test_lone_wrong_type_is_fp_with_reason_wrong_type():  # kills M05
    iss = [_issue("ISS-001", "fx_rate", ["SF-1"], 500, [["DC-1", "policy"]])]
    ok = _grade(iss, [finding("fx_rate", ["SF-1"], 500, "KZT", ["DC-1", "policy"])])
    bad = _grade(iss, [finding("period_cutoff", ["SF-1"], 500, "KZT", ["DC-1", "policy"])])
    assert ok["tp"] == 1 and ok["reward"] == 1.0
    assert bad["tp"] == 0 and bad["fp"] == 1 and bad["reward"] == -1.0
    assert bad["findings"][0]["reason"] == "wrong_type"


def test_wrong_type_on_real_episode_never_matches(erroneous):  # kills M05 on generated data too
    types = ["duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff", "vat_error"]
    good = oracle_findings(erroneous.truth)
    swapped = [dict(f, type=types[(types.index(f["type"]) + 1) % len(types)]) for f in good]
    g = EpisodeGrader(erroneous.truth).grade({"episode_id": erroneous.episode_id, "findings": swapped}, 0)
    assert g["tp"] == 0 and g["fp"] == len(good)


def test_superset_of_affected_ids_is_fp():  # kills M06
    iss = [_issue("ISS-001", "payment_allocation", ["BNK-1"], 700, [["DC-P"]])]
    g = _grade(iss, [finding("payment_allocation", ["BNK-1", "SF-9"], 700, "KZT", ["DC-P"])])
    assert g["tp"] == 0 and g["fp"] == 1 and g["findings"][0]["reason"] == "ids_mismatch"
    sub = _grade([_issue("ISS-001", "duplicate_invoice", ["SF-1", "SF-2"], 700, [["DC-P"]])],
                 [finding("duplicate_invoice", ["SF-1"], 700, "KZT", ["DC-P"])])
    assert sub["tp"] == 0  # and a subset is not enough either


def test_matching_is_maximum_not_greedy():  # kills M08
    # ISS-001 is tried first and greedily grabs finding 0, which is the ONLY candidate of ISS-002.
    # A maximum matching re-routes ISS-001 to finding 1 (augmenting path) and matches both.
    issues = [_issue("ISS-001", "fx_rate", ["A"], 100, [["x"]]), _issue("ISS-002", "fx_rate", ["A"], 101, [["y"]])]
    f0 = normalize_finding(finding("fx_rate", ["A"], 100, "KZT", ["x", "y"]))  # candidate of both
    f1 = normalize_finding(finding("fx_rate", ["A"], 99, "KZT", ["x"]))        # candidate of ISS-001 only
    m = match([f0, f1], issues, tol=1)
    assert m["pairs"] == {0: "ISS-002", 1: "ISS-001"} and m["missed"] == []
    g = _grade(issues, [finding("fx_rate", ["A"], 100, "KZT", ["x", "y"]), finding("fx_rate", ["A"], 99, "KZT", ["x"])])
    assert (g["tp"], g["fp"], g["fn"], g["f1"]) == (2, 0, 0, 1.0)


def test_grader_int_check_works_even_if_the_schema_validator_accepted_floats(monkeypatch):  # kills M18
    # Defence in depth: jsonschema_lite already rejects 5.0 for "integer" (M23 covers that layer), so the grader's own
    # `type(...) is int` check was invisible to every test. Here the validator is replaced by one that accepts anything.
    from auditenv.grader import schema

    class AcceptAll:
        def iter_errors(self, obj):
            return iter(())

    monkeypatch.setattr(schema, "_validator", lambda: AcceptAll())
    sub = {"episode_id": "ep-mut", "findings": [finding("fx_rate", ["A"], 5, "KZT", ["x"])]}
    assert schema.validate_findings(sub, "ep-mut") is None
    for bad in (5.0, True):
        sub["findings"][0]["claimed_amount_minor"] = bad
        assert schema.validate_findings(sub, "ep-mut") == "schema:findings/0/claimed_amount_minor:int_required"
