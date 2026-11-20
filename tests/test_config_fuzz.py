"""A6: property-based fuzz over the CONFIG space (not just actions).

Corners: one entity, fx_rate enabled without foreign currencies, up to 12 errors, every
distractor at 0 and at 1, a single time zone, the stress preset. A config that load_config
accepts must ALWAYS generate: no crash, clean-book invariants hold, the independent solver
agrees with truth, the oracle scores 1.0, provenance records ordered vs injected per type,
and one episode takes well under the 60 s budget.
"""

import time

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from auditenv.config import ConfigError, load_config
from auditenv.env.data import PublicData
from auditenv.generator.episode import generate_episode
from auditenv.generator.invariants import violated
from auditenv.generator.story import DISTRACTOR_KINDS
from auditenv.grader.validate_truth import validate
from auditenv.runner import run_episode
from auditenv.timeutil import TIMEZONES

TYPES = ["duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff"]
CURS = ["KZT", "USD", "EUR", "JPY", "KWD"]


@st.composite
def configs(draw):
    base = draw(st.sampled_from(CURS))
    foreign = draw(st.sampled_from([[], [c for c in CURS if c != base][:1], [c for c in CURS if c != base]]))
    d_mode = draw(st.sampled_from(["zero", "one", "mixed"]))
    distractors = {k: (0.0 if d_mode == "zero" else 1.0 if d_mode == "one" else draw(st.sampled_from([0.0, 0.5, 1.0])))
                   for k in DISTRACTOR_KINDS}
    lo = draw(st.integers(0, 12))
    hi = draw(st.integers(lo, 12))
    weights = {t: draw(st.sampled_from([0.0, 1.0, 3.0])) for t in TYPES}
    inter = {"partial_fx_cutoff": draw(st.sampled_from([0.0, 1.0])), "duplicate_fx": draw(st.sampled_from([0.0, 1.0]))}
    tzs = draw(st.lists(st.sampled_from(sorted(TIMEZONES)), min_size=1, max_size=3, unique=True))
    n_ent = draw(st.sampled_from([[1, 1], [2, 3], [8, 14]]))
    n_inv = draw(st.sampled_from([[20, 30], [45, 60]]))
    return {"name": "fuzz", "base_currencies": [base], "foreign_currencies": foreign, "n_foreign": [0, len(foreign)],
            "foreign_share": draw(st.sampled_from([0.0, 0.3, 1.0])), "timezones": tzs, "n_entities": n_ent,
            "n_invoices": n_inv, "distractors": distractors, "clean_probability": draw(st.sampled_from([0.0, 0.3, 1.0])),
            "n_errors": [lo, hi], "errors": weights, "interactions": inter,
            "min_interactions": draw(st.integers(0, 2)), "period_months": draw(st.integers(1, 3)),
            "period_starts": [draw(st.sampled_from(["2026-01", "2026-02", "2026-07", "2026-11", "2026-12"]))]}


def check_episode(cfg, seed):
    t0 = time.monotonic()
    ep = generate_episode(seed, cfg)
    elapsed = time.monotonic() - t0
    assert violated(PublicData(ep.clean_files)) == {}
    v = validate(ep.public(), ep.truth)
    assert v["ok"], v
    g = run_episode("oracle", episode=ep, isolate=False)["grade"]
    assert g["reward"] == 1.0
    plan = ep.provenance["plan"]
    assert "ordered" in plan and "injected" in plan
    got = {}
    for i in ep.truth["issues"]:
        got[i["type"]] = got.get(i["type"], 0) + 1
    assert plan["injected"] == dict(sorted(got.items()))
    assert elapsed < 60
    return ep


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(raw=configs(), seed=st.integers(0, 10 ** 6))
def test_config_space_fuzz(raw, seed):
    try:
        cfg = load_config(raw)
    except ConfigError:
        return  # infeasible configs are rejected up front with a clear message (tested in test_batch_a)
    check_episode(cfg, seed)


def test_corner_one_entity_all_distractors():
    cfg = load_config({"name": "one", "n_entities": [1, 1], "distractors": {k: 1.0 for k in DISTRACTOR_KINDS},
                       "clean_probability": 0.0, "n_errors": [3, 6]})
    for seed in range(4):
        check_episode(cfg, seed)


def test_corner_fx_enabled_without_foreign_currency():
    cfg = load_config({"name": "nofx", "foreign_currencies": [], "clean_probability": 0.0})
    for seed in range(4):
        ep = check_episode(cfg, seed)
        assert ep.provenance["plan"]["injected"].get("fx_rate", 0) == 0


def test_corner_twelve_errors_and_stress():
    ep = check_episode(load_config({"name": "twelve", "n_errors": [12, 12], "clean_probability": 0.0}), 1)
    assert sum(ep.provenance["plan"]["ordered"].values()) == 12
    check_episode(load_config("stress"), 2)
