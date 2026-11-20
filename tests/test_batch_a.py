"""Round-2 package A: submit robustness, Gymnasium compatibility, tolerance from config, cutoff
service periods, interaction independence, clean-decision stream, time zones, config errors."""

import copy
import json
from datetime import date, timedelta

import pytest

import auditenv
from auditenv.config import ConfigError, load_config
from auditenv.env.env import AuditEnv
from auditenv.generator.episode import generate_episode, is_clean_episode
from auditenv.grader.log import GraderLog
from auditenv.grader.validate_truth import validate
from auditenv.paths import CONFIGS_DIR
from auditenv.policies.base import finding, submit
from auditenv.policies.oracle import oracle_findings
from auditenv.timeutil import TIMEZONES, add_months, offset_minutes


# ------------------------------------------------------------------ A1 submit
@pytest.mark.parametrize("action", [
    {"tool": "submit"}, {"tool": "submit", "args": {}}, {"tool": "submit", "args": None},
    {"tool": "submit", "args": []}, {"tool": "submit", "args": {"findings": []}},
    {"tool": "submit", "args": {"findings": {"episode_id": "__EP__", "findings": "x"}}},
    {"tool": "submit", "args": {"findings": {"episode_id": "__EP__", "findings": [{"type": "fx_rate"}]}}},
    {"tool": "submit", "args": {"episode_id": "__EP__"}},
    {"tool": "submit", "args": {"episode_id": "__EP__", "findings": [], "extra": 1}},
    {"tool": "submit", "args": {"findings": {"episode_id": "__EP__", "findings": []}}, "junk": 1},
])
def test_malformed_submit_terminates_minus_one(erroneous, action):
    action = json.loads(json.dumps(action).replace("__EP__", erroneous.episode_id))
    log = GraderLog()
    env = AuditEnv(grader_log=log)
    env.reset(episode=erroneous)
    obs, r, term, trunc, _ = env.step(action)
    assert r == -1.0 and term and not trunc
    assert obs == {"result": {"submitted": True}, "steps_remaining": 99}  # nothing leaks to the agent
    assert log.records[0]["valid"] is False and log.records[0]["error"]


def test_flat_submit_equals_nested(erroneous):
    f = oracle_findings(erroneous.truth)
    rs = []
    for args in ({"findings": {"episode_id": erroneous.episode_id, "findings": f}},
                 {"episode_id": erroneous.episode_id, "findings": f}):
        env = AuditEnv()
        env.reset(episode=erroneous)
        rs.append(env.step({"tool": "submit", "args": args})[1])
    assert rs == [1.0, 1.0]


def test_malformed_submit_reason_is_logged(erroneous):
    log = GraderLog()
    env = AuditEnv(grader_log=log)
    env.reset(episode=erroneous)
    env.step({"tool": "submit", "args": {}})
    assert log.records[0]["error"] == "submit_args_malformed"


# ------------------------------------------------------------- A2 gymnasium
def test_gymnasium_surface(erroneous):
    with auditenv.make("dev-mixed", mode="train") as env:
        assert env.render() is None and isinstance(env.metadata, dict)
        assert env.action_space["$id"].endswith("action.schema.json")
        assert env.observation_space["$id"].endswith("observation.schema.json")
        o1, _ = env.reset()
        o2, _ = AuditEnv(config="dev-mixed").reset(seed=0)
        assert o1 == o2  # reset() without seed uses the deterministic default seed 0
    assert env.step({"tool": "calculator", "args": {"expression": "1"}})[0]["error"] == {"code": "episode_over"}


@pytest.mark.parametrize("seed", [True, 1.0, "1", 1.5])
def test_seed_must_be_int(seed):
    with pytest.raises(TypeError, match="seed must be an int"):
        AuditEnv().reset(seed=seed, config="dev-mixed")
    with pytest.raises(TypeError):
        generate_episode(seed, "dev-mixed")


# ------------------------------------------------------------- A3 tolerance
def test_tolerance_from_config_travels_to_grader_and_task():
    cfg = {"name": "tol3", "tolerance_minor": 3, "clean_probability": 0.0}
    ep = generate_episode(5, cfg)
    assert ep.truth["tolerance_minor"] == 3
    env = AuditEnv()
    obs, _ = env.reset(episode=ep)
    assert "tolerance: 3 minor units" in obs["task"]
    f = oracle_findings(ep.truth)
    for k, ok in ((3, True), (-3, True), (4, False), (-4, False)):
        env = AuditEnv()
        env.reset(episode=ep)
        shifted = [dict(x, claimed_amount_minor=x["claimed_amount_minor"] + k) for x in f]
        env.step(submit(ep.episode_id, shifted))
        assert (env.last_grade["tp"] == len(f)) is ok, k


def test_tolerance_schema_bounds():
    with pytest.raises(ConfigError):
        load_config({"tolerance_minor": 50})


# -------------------------------------------------- A4 cutoff service period
def test_cutoff_service_period_follows_local_month():
    cfg = {"name": "cut", "errors": {"duplicate_invoice": 0, "payment_allocation": 0, "fx_rate": 0, "period_cutoff": 1},
           "clean_probability": 0.0, "n_errors": [1, 3]}
    n = 0
    for seed in range(12):
        ep = generate_episode(seed, cfg)
        pd = ep.public()
        muts = {m["issue_id"]: m for m in ep.provenance["mutations"]}
        for iss in ep.truth["issues"]:
            inv = pd.invoice_by_id[iss["affected_ids"][0]]
            month = pd.local(inv["issued_at"]).strftime("%Y-%m")
            assert {li["service_period"] for li in inv["line_items"]} == {month}
            before = muts[iss["issue_id"]]["before"][0]["document"]["line_items"]
            after = muts[iss["issue_id"]]["after"][0]["document"]["line_items"]
            assert {li["service_period"] for li in before} != {month} and after == inv["line_items"]
            n += 1
    assert n >= 10


# ------------------------------------------- A5 interaction amounts independent
def _scenario_books(name, seeds=range(25)):
    from auditenv.generator.books import build_book
    from auditenv.generator.interactions import SCENARIOS
    from auditenv.generator.story import build_story
    from auditenv.ids import make_rng

    cfg = load_config({"name": "x", "interactions": {"partial_fx_cutoff": 1.0, "duplicate_fx": 1.0},
                       "foreign_currencies": ["USD", "EUR", "JPY", "KWD"], "n_foreign": [2, 3]})
    for seed in seeds:
        book = build_book(build_story(seed, cfg), seed)
        res = SCENARIOS[name](book, make_rng(seed, "t"), cfg, set())
        if res:
            yield book, res


def test_partial_fx_cutoff_amounts_independent_and_never_inverted():
    from auditenv.generator.errors import REGISTRY

    n = 0
    for book, (fx, al) in _scenario_books("partial_fx_cutoff"):
        assert fx.variant != "inverted"
        key = al.target
        no_fx = copy.deepcopy(book)
        no_fx.payments[key].cash_rate = None
        no_fx.post_payment(no_fx.payments[key])
        assert REGISTRY["payment_allocation"].expected_amount(no_fx, key) == al.expected_amount_minor
        no_al = copy.deepcopy(book)
        no_al.payments[key].posted_alloc = None
        no_al.post_payment(no_al.payments[key])
        assert REGISTRY["fx_rate"].expected_amount(no_al, f"pay:{key}") == fx.expected_amount_minor
        n += 1
    assert n >= 5


def test_duplicate_fx_amounts_independent():
    from auditenv.generator.errors import REGISTRY

    n = 0
    for book, (fx, dup) in _scenario_books("duplicate_fx"):
        orig = fx.target.split(":")[1]
        no_fx = copy.deepcopy(book)
        no_fx.invoices[orig].posted_rate = None
        no_fx.post_invoice(no_fx.invoices[orig])
        assert REGISTRY["duplicate_invoice"].expected_amount(no_fx, dup.target) == dup.expected_amount_minor
        no_dup = copy.deepcopy(book)
        del no_dup.invoices[dup.target]
        assert REGISTRY["fx_rate"].expected_amount(no_dup, fx.target) == fx.expected_amount_minor
        n += 1
    assert n >= 5


def test_task_explains_fx_payment_allocation_amount():
    obs, _ = AuditEnv().reset(seed=1, config="dev-mixed")
    assert "Unapplied Cash (2400)" in obs["task"] and "policy rate" in obs["task"]


# ---------------------------------------------------------- A7 clean stream
def test_clean_decision_does_not_depend_on_attempt():
    cfg = load_config("dev-mixed")
    for seed in range(40):
        ep = generate_episode(seed, cfg)
        assert (ep.truth["issues"] == []) == is_clean_episode(seed, cfg)


def test_clean_share_matches_probability():
    cfg = load_config({"name": "half", "clean_probability": 0.5})
    share = sum(is_clean_episode(s, cfg) for s in range(2000)) / 2000
    assert 0.46 < share < 0.54


# --------------------------------------------------------- A10 salt fixture
def test_open_tests_never_see_salt():
    import os

    assert "AUDITENV_SEED_SALT" not in os.environ


# --------------------------------------------------------------- A11 zones
def _all_config_periods():
    out = set()
    for p in CONFIGS_DIR.glob("*.json"):
        raw = json.loads(p.read_text())
        if "splits" in p.name or "LOCK" in p.name or "version" not in raw or "name" not in raw:
            continue
        cfg = load_config(p)
        for ps in cfg["period_starts"]:
            for tz in cfg["timezones"]:
                pm = cfg["period_months"]
                out.add((tz, ps, max(pm) if isinstance(pm, list) else pm))
    return sorted(out)


def test_fixed_offsets_match_zoneinfo():
    zoneinfo = pytest.importorskip("zoneinfo")
    from datetime import datetime, timezone

    checked = 0
    for tz, ps, months in _all_config_periods():
        try:
            z = zoneinfo.ZoneInfo(tz)
        except zoneinfo.ZoneInfoNotFoundError:
            pytest.skip("tzdata not installed")
        y, m = map(int, ps.split("-"))
        start = datetime(y, m, 1, tzinfo=timezone.utc)
        end = add_months(start, months)
        d = start - timedelta(days=15)  # a margin around the period (FX history, cutoff errors)
        while d < end + timedelta(days=15):
            off = d.astimezone(z).utcoffset()
            assert off == timedelta(minutes=offset_minutes(tz)), (tz, d.date())
            d += timedelta(days=1)
            checked += 1
    assert checked > 100


def test_policy_states_explicit_utc_offset():
    pd = generate_episode(3, "dev-mixed").public()
    pb = pd.policy["period_boundary"]
    off = offset_minutes(pb["timezone"])
    sign = "+" if off >= 0 else "-"
    assert pb["utc_offset"] == f"{sign}{abs(off) // 60:02d}:{abs(off) % 60:02d}"
    assert pb["start"].endswith(pb["utc_offset"])


# ------------------------------------------------- A6 infeasible configs
@pytest.mark.parametrize("raw,msg", [
    ({"errors": {"duplicate_invoice": 0, "payment_allocation": 0, "fx_rate": 1, "period_cutoff": 0},
      "foreign_currencies": [], "clean_probability": 0.0}, "no foreign currency"),
    ({"errors": {"duplicate_invoice": 0, "payment_allocation": 0, "fx_rate": 0, "period_cutoff": 0},
      "clean_probability": 0.5}, "every error weight"),
    ({"n_errors": [0, 0], "clean_probability": 0.5}, "n_errors"),
    ({"min_interactions": 2, "interactions": {"partial_fx_cutoff": 1.0, "duplicate_fx": 0.0}}, "min_interactions"),
    ({"min_interactions": 1, "interactions": {"partial_fx_cutoff": 1.0}, "foreign_currencies": []}, "foreign"),
    ({"n_invoices": [60, 40]}, "min > max"),
    ({"n_entities": [0, 3]}, "n_entities"),
    ({"timezones": ["Europe/Berlin"]}, "timezones"),
])
def test_infeasible_configs_fail_clearly(raw, msg):
    with pytest.raises(ConfigError, match=msg):
        load_config(dict(raw, name="bad"))


# ------------------------------------------------------ A12 report determinism
def test_report_deterministic_part_excludes_timing():
    from auditenv.selfcheck import deterministic_part, render_md

    rep = {"header": {"commit": "abc", "env_version": "0", "generator_version": "g", "python": "3.11", "platform": "x",
                      "config_hashes": {"a": "1"}},
           "blocks": {"contract": [{"name": "c", "ok": True, "error": None}]}, "score": {"contract": 25.0},
           "total": 25.0, "max_total": 25, "diagnostics": [], "episodes": ["a#1"],
           "failure_analysis": {"recall_by_type": {}, "fp_reasons": {}},
           "timing": {"elapsed_s": 1.0, "per_policy": [{"policy": "p", "mean_ms": 1, "p50_ms": 1, "p95_ms": 1, "max_ms": 1}]}}
    import copy as _c

    rep2 = _c.deepcopy(rep)
    rep2["timing"]["elapsed_s"] = 99.0
    rep2["timing"]["per_policy"][0]["max_ms"] = 999
    a, b = render_md(rep), render_md(rep2)
    assert a != b and deterministic_part(a) == deterministic_part(b)
    assert "commit `abc`" in a and "Python 3.11" in a


# ------------------------------------------------------------ A9 docs-check
def test_docs_check_detects_stale_and_unknown_facts(tmp_path, monkeypatch):
    import auditenv.docs_check as dc

    (tmp_path / "README.md").write_text("x <!--fact:n_timezones-->999<!--/fact--> y <!--fact:nope-->1<!--/fact-->")
    monkeypatch.setattr(dc, "ROOT", tmp_path)
    monkeypatch.setattr(dc, "DOCS", ["README.md"])
    assert dc.main([]) == 1
    dc.main(["--fix"])
    from auditenv.timeutil import TIMEZONES

    assert f"<!--fact:n_timezones-->{len(TIMEZONES)}<!--/fact-->" in (tmp_path / "README.md").read_text()


def test_committed_docs_facts_are_current():
    import auditenv.docs_check as dc

    # n_tests needs a nested pytest run, selfcheck_total the report that make check writes AFTER pytest
    # (reports/ is not even copied into the image): both are checked by `make docs-check` at the end
    found = [f for f in dc.scan() if f[1] not in ("n_tests", "selfcheck_total")]
    facts = dc.compute_facts({n for _, n, _ in found})
    assert found and all(facts[n] == shown for _, n, shown in found), [(r, n, s, facts[n]) for r, n, s in found
                                                                         if facts[n] != s]
