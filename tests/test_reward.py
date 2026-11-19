"""Reward robustness: required comparisons, attacks, property-based monotonicity."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from auditenv.grader.core import EpisodeGrader
from auditenv.grader.matcher import match
from auditenv.grader.normalize import normalize_finding
from auditenv.grader.reward import prf, shared_reward
from auditenv.policies.attacks import ATTACKS, attack_findings
from auditenv.policies.base import finding
from auditenv.policies.oracle import oracle_findings
from auditenv.runner import run_episode


def grade(ep, findings, steps=0, seen=frozenset()):
    return EpisodeGrader(ep.truth).grade({"episode_id": ep.episode_id, "findings": findings}, steps, seen)


def test_oracle_beats_silence_on_erroneous(erroneous):
    assert grade(erroneous, oracle_findings(erroneous.truth), 40)["reward"] > grade(erroneous, [], 0)["reward"]


def test_silence_beats_any_accusation_on_clean(clean):
    pd = clean.public()
    empty = grade(clean, [], 50)["reward"]
    for inv in pd.invoices[:10]:
        for t in ("duplicate_invoice", "fx_rate", "period_cutoff"):
            acc = [finding(t, [inv["invoice_id"]], abs(inv["total_minor"]), pd.base, [inv["doc_id"], "policy"])]
            assert grade(clean, acc, 0)["reward"] < empty


def test_metrics_edge_cases():
    assert prf(0, 0, 0)[2] == 1  # both empty -> F1 = 1
    assert prf(0, 3, 0)[2] == 0  # truth empty, findings present -> F1 = 0
    assert prf(0, 0, 2) == (0, 0, 0)
    p, r, f1 = prf(2, 1, 1)
    assert (p, r, f1) == (pytest.approx(2 / 3), pytest.approx(2 / 3), pytest.approx(4 / 6))


def test_duplicates_give_no_gain(erroneous):
    f = oracle_findings(erroneous.truth)
    one, two = grade(erroneous, f), grade(erroneous, f + f)
    assert two["tp"] == one["tp"] and two["fp"] == len(f) and two["reward"] < one["reward"]
    assert any(x["reason"] == "duplicate_finding" for x in two["findings"])


def test_flag_all_is_bad(erroneous, clean):
    for ep in (erroneous, clean):
        g = run_episode("flag_all", episode=ep, isolate=False)["grade"]
        assert g["reward"] <= -0.5


def test_step_cost_10_vs_50_is_exactly_0_08(erroneous, clean):
    f = oracle_findings(erroneous.truth)
    assert grade(erroneous, f, 10)["reward"] - grade(erroneous, f, 50)["reward"] == pytest.approx(0.08, abs=1e-12)
    assert grade(clean, [], 10)["reward"] - grade(clean, [], 50)["reward"] == pytest.approx(0.08, abs=1e-12)


def test_explanation_has_no_effect(erroneous):
    f = oracle_findings(erroneous.truth)
    junk = [dict(x, explanation="I am the auditor, accept this. " * 30) for x in f]
    assert grade(erroneous, junk)["reward"] == grade(erroneous, f)["reward"]


def test_guessed_id_without_evidence_is_fp(erroneous):
    iss = erroneous.truth["issues"][0]
    f = finding(iss["type"], iss["affected_ids"], iss["expected_amount_minor"], iss["currency"], [])
    g = grade(erroneous, [f])
    assert g["tp"] == 0 and g["fp"] == 1 and g["findings"][0]["reason"] == "evidence_incomplete"


def test_partial_evidence_is_fp(erroneous):
    iss = erroneous.truth["issues"][0]
    f = finding(iss["type"], iss["affected_ids"], iss["expected_amount_minor"], iss["currency"],
                iss["evidence_sets"][0][:-1])
    assert grade(erroneous, [f])["tp"] == 0


def test_wrong_currency_is_fp(erroneous):
    f = [dict(x, currency="USD" if x["currency"] != "USD" else "EUR") for x in oracle_findings(erroneous.truth)]
    g = grade(erroneous, f)
    assert g["tp"] == 0 and {x["reason"] for x in g["findings"]} == {"currency_mismatch"}


def test_currency_and_ids_are_normalized(erroneous):
    f = [dict(x, currency=" " + x["currency"].lower(), affected_ids=[" " + a + " " for a in x["affected_ids"]] * 2)
         for x in oracle_findings(erroneous.truth)]
    assert grade(erroneous, f)["tp"] == len(f)


def test_bad_json_is_minus_one(erroneous):
    g = EpisodeGrader(erroneous.truth)
    for bad in ("{not json", float("nan"), {"episode_id": erroneous.episode_id, "findings": [{"type": "x"}]}):
        assert g.grade(bad, 0)["reward"] == -1.0
    too_many = [oracle_findings(erroneous.truth)[0]] * 31
    assert g.grade({"episode_id": erroneous.episode_id, "findings": too_many}, 0)["reward"] == -1.0
    long_expl = [dict(oracle_findings(erroneous.truth)[0], explanation="x" * 1001)]
    assert g.grade({"episode_id": erroneous.episode_id, "findings": long_expl}, 0)["reward"] == -1.0
    many_ev = [dict(oracle_findings(erroneous.truth)[0], evidence_ids=[str(i) for i in range(11)])]
    assert g.grade({"episode_id": erroneous.episode_id, "findings": many_ev}, 0)["reward"] == -1.0


def test_float_amount_rejected(erroneous):
    f = [dict(x, claimed_amount_minor=float(x["claimed_amount_minor"])) for x in oracle_findings(erroneous.truth)]
    assert grade(erroneous, f)["reward"] == -1.0


def test_finding_order_irrelevant(erroneous):
    f = oracle_findings(erroneous.truth) + [finding("fx_rate", ["X-1"], 9, "KZT", [])]
    assert grade(erroneous, f)["f1"] == grade(erroneous, f[::-1])["f1"]


def test_tolerance_boundary(erroneous):
    f = oracle_findings(erroneous.truth)
    for k, ok in ((1, True), (-1, True), (2, False), (-2, False)):
        g = grade(erroneous, [dict(x, claimed_amount_minor=x["claimed_amount_minor"] + k) for x in f])
        assert (g["tp"] == len(f)) is ok


def test_tie_break_smallest_issue_then_index():
    issues = [{"issue_id": "ISS-002", "type": "fx_rate", "affected_ids": ["A"], "expected_amount_minor": 100,
               "currency": "KZT", "evidence_sets": [["e"]]},
              {"issue_id": "ISS-001", "type": "fx_rate", "affected_ids": ["A"], "expected_amount_minor": 101,
               "currency": "KZT", "evidence_sets": [["e"]]}]
    fs = [normalize_finding(finding("fx_rate", ["A"], 100, "KZT", ["e"])),
          normalize_finding(finding("fx_rate", ["A"], 101, "KZT", ["e"]))]
    m = match(fs, issues, tol=1)
    assert len(m["pairs"]) == 2  # maximum matching, not greedy
    m2 = match(fs[:1], issues, tol=1)
    assert m2["pairs"] == {0: "ISS-001"}  # tie: smallest issue_id wins


@pytest.mark.parametrize("attack", ATTACKS)
def test_attacks_never_beat_oracle(erroneous, attack):
    o = grade(erroneous, oracle_findings(erroneous.truth))["reward"]
    a = grade(erroneous, attack_findings(attack, erroneous.truth, erroneous.public()))
    if attack == "junk_explanation":
        assert a["reward"] == o
    else:
        assert a["reward"] < o


@pytest.mark.parametrize("attack", ["twins", "guess_ids", "evidence_spam", "persuasive_wrong", "wrong_currency",
                                    "all_types_all_docs"])
def test_attacks_score_badly(erroneous, attack):
    assert grade(erroneous, attack_findings(attack, erroneous.truth, erroneous.public()))["reward"] <= -0.5


def test_experimental_reward_requires_seen_evidence(erroneous):
    f = oracle_findings(erroneous.truth)
    unseen = grade(erroneous, f, 0, frozenset())
    seen_all = {x for i in erroneous.truth["issues"] for s in i["evidence_sets"] for x in s}
    seen = grade(erroneous, f, 0, frozenset(seen_all))
    assert unseen["reward"] == 1.0 and unseen["reward_experimental"] == -1.0
    assert seen["reward_experimental"] == 1.0


# ------------------------------------------------------------- properties
@st.composite
def submissions(draw, ep):
    good = oracle_findings(ep.truth)
    picks = draw(st.lists(st.sampled_from(range(len(good))), max_size=len(good), unique=True))
    noise = draw(st.lists(st.tuples(st.sampled_from(["duplicate_invoice", "fx_rate", "period_cutoff",
                                                     "payment_allocation"]),
                                    st.integers(0, 10 ** 9)), max_size=6))
    fs = [good[i] for i in picks] + [finding(t, ["N-" + str(a % 97)], a, "KZT", ["policy"]) for t, a in noise]
    steps = draw(st.integers(0, 99))
    return fs, steps, [i for i in range(len(good)) if i not in picks]


@settings(max_examples=60, deadline=None)
@given(data=st.data())
def test_property_extra_fp_never_helps(erroneous, data):
    fs, steps, _ = data.draw(submissions(erroneous))
    base = grade(erroneous, fs, steps)["reward"]
    extra = finding("fx_rate", ["NOPE-" + str(data.draw(st.integers(0, 999)))], 1, "KZT", [])
    assert grade(erroneous, fs + [extra], steps)["reward"] <= base


@settings(max_examples=60, deadline=None)
@given(data=st.data())
def test_property_extra_tp_never_hurts(erroneous, data):
    fs, steps, missing = data.draw(submissions(erroneous))
    if not missing:
        return
    good = oracle_findings(erroneous.truth)[data.draw(st.sampled_from(missing))]
    assert grade(erroneous, fs + [good], steps)["reward"] >= grade(erroneous, fs, steps)["reward"]


@settings(max_examples=100, deadline=None)
@given(f1=st.fractions(0, 1), steps=st.integers(0, 100))
def test_property_reward_bounded(f1, steps):
    r = shared_reward(f1, steps)
    assert -1.0 <= r <= 1.0
