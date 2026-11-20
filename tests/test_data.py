"""Data & truth: clean-book invariants, one invariant per error type, evidence reachability,
independent solver agreement, clean episodes, distractors."""

import pytest

from auditenv.env.data import PublicData
from auditenv.env.env import AuditEnv
from auditenv.generator.episode import generate_episode
from auditenv.generator.invariants import violated
from auditenv.grader.validate_truth import TYPE_OF_INVARIANT, solve, validate
from auditenv.schemas import errors as schema_errors
from auditenv.schemas import validate_public

INV = {v: k for k, v in TYPE_OF_INVARIANT.items()}
TYPES = sorted(INV)


def single(typ):
    return {"name": f"only-{typ}", "errors": {t: (1.0 if t == typ else 0.0) for t in TYPES}, "n_errors": [1, 2],
            "clean_probability": 0.0, "foreign_currencies": ["USD", "EUR", "JPY", "KWD"], "n_foreign": [2, 3],
            "foreign_share": 0.4}


@pytest.mark.parametrize("seed", range(50))
def test_clean_book_invariants(seed):
    ep = generate_episode(seed, "dev-mixed")
    assert violated(PublicData(ep.clean_files)) == {}
    assert not validate_public(ep.public())


@pytest.mark.parametrize("typ", TYPES)
@pytest.mark.parametrize("seed", range(8))
def test_error_breaks_exactly_its_invariant(typ, seed):
    ep = generate_episode(seed, single(typ))
    assert ep.truth["issues"] and {i["type"] for i in ep.truth["issues"]} == {typ}
    want = {INV[typ]: {i["affected_ids"][0]: i["expected_amount_minor"] for i in ep.truth["issues"]}}
    assert violated(ep.public()) == want
    assert violated(PublicData(ep.clean_files)) == {}
    for i in ep.truth["issues"]:
        assert i["expected_amount_minor"] >= 100 and i["currency"] == ep.public().base


@pytest.mark.parametrize("cfg", ["dev-mixed", "interaction-heavy"])
@pytest.mark.parametrize("seed", range(6))
def test_every_evidence_id_reachable_through_tools(cfg, seed):
    ep = generate_episode(seed, cfg)
    env = AuditEnv()
    env.reset(episode=ep)
    env.max_steps = 10 ** 6  # this test only checks reachability, not the budget
    pd = ep.public()
    for iss in ep.truth["issues"]:
        assert 1 <= len(iss["evidence_sets"]) <= 3
        for s in iss["evidence_sets"]:
            assert 1 <= len(s) <= 6
            for x in s:
                if x == "policy":
                    a = {"tool": "get_record", "args": {"table": "policy", "id": "policy"}}
                elif x.startswith("fx:"):
                    a = {"tool": "get_record", "args": {"table": "fx", "id": x}}
                elif x in pd.doc_by_id:
                    a = {"tool": "get_document", "args": {"doc_id": x}}
                else:
                    a = {"tool": "get_record", "args": {"table": "ledger", "id": x}}
                assert "result" in env.step(a)[0], x


@pytest.mark.slow
@pytest.mark.parametrize("cfg", ["train-easy", "dev-mixed", "interaction-heavy", "clean-only"])
def test_validate_truth_agrees_on_50_seeds(cfg):
    bad = []
    for seed in range(50):
        ep = generate_episode(seed, cfg)
        v = validate(ep.public(), ep.truth)
        if not v["ok"]:
            bad.append((seed, v))
    assert not bad


@pytest.mark.parametrize("seed", range(10))
def test_validate_truth_quick(seed):
    ep = generate_episode(seed, "interaction-heavy")
    assert validate(ep.public(), ep.truth)["ok"]


@pytest.mark.parametrize("seed", range(10))
def test_clean_episodes_have_empty_truth_and_solver_finds_nothing(seed):
    ep = generate_episode(seed, "clean-only")
    assert ep.truth["issues"] == []
    found = solve(ep.public())
    assert found["issues"] == [] and found["structural"] == []


def test_truth_schema_and_fields(erroneous):
    assert not schema_errors("truth", erroneous.truth)
    for i in erroneous.truth["issues"]:
        assert i["affected_ids"] == sorted(i["affected_ids"])


def test_interaction_scenarios_present():
    seen = set()
    for seed in range(30):
        ep = generate_episode(seed, "interaction-heavy")
        seen.update(ep.provenance["plan"]["scenarios"])
        if ep.provenance["plan"]["scenarios"]:
            assert len(ep.truth["issues"]) >= 2
    assert seen == {"partial_fx_cutoff", "duplicate_fx"}


def test_partial_fx_cutoff_gives_two_issues_on_one_payment():
    for seed in range(40):
        ep = generate_episode(seed, {"name": "pfc", "interactions": {"partial_fx_cutoff": 1.0, "duplicate_fx": 0.0},
                                     "min_interactions": 1, "clean_probability": 0.0, "n_errors": [2, 2],
                                     "foreign_currencies": ["EUR"], "n_foreign": [1, 1]})
        if "partial_fx_cutoff" in ep.provenance["plan"]["scenarios"]:
            by = {}
            for i in ep.truth["issues"]:
                by.setdefault(tuple(i["affected_ids"]), set()).add(i["type"])
            assert {"payment_allocation", "fx_rate"} in by.values()
            assert validate(ep.public(), ep.truth)["ok"]
            return
    pytest.fail("scenario never applied")


def test_distractors_are_generated_and_clean():
    kinds = set()
    for seed in range(15):
        ep = generate_episode(seed, "clean-only")
        kinds.update(ep.provenance["story"]["distractors"])
        assert ep.truth["issues"] == []
    assert kinds >= {"recurring_rent", "split_payment", "multi_invoice_payment", "refund", "bank_fee",
                     "rounding_residual", "boundary_time", "credit_note_reissue", "unidentified_receipt"}


def test_utc_trap_in_cutoff():
    """period_cutoff timestamps are written in UTC and look inside the period by their UTC date."""
    n = 0
    for seed in range(30):
        ep = generate_episode(seed, single("period_cutoff"))
        pd = ep.public()
        variant = {m["issue_id"]: m["variant"] for m in ep.provenance["mutations"]}
        for i in ep.truth["issues"]:
            inv = pd.invoice_by_id[i["affected_ids"][0]]
            if variant[i["issue_id"]] != "utc_trap":
                assert not pd.in_period(inv["issued_at"])
                continue
            assert inv["issued_at"].endswith("+00:00")
            utc_date = inv["issued_at"][:10]
            assert pd.policy["period_boundary"]["start"][:10] <= utc_date < pd.policy["period_boundary"]["end"][:10]
            assert not pd.in_period(inv["issued_at"])
            n += 1
    assert n > 5


def test_varied_names_ids_currencies_timezones():
    tzs, bases, prefixes = set(), set(), set()
    for seed in range(20):
        pd = generate_episode(seed, "dev-mixed").public()
        tzs.add(pd.manifest["timezone"])
        bases.update(pd.manifest["currencies"])
        prefixes.add(pd.invoices[0]["invoice_id"].split("-")[0])
    assert len(tzs) >= 4 and len(bases) >= 4 and len(prefixes) >= 2


def test_null_references_are_explicit(episodes):
    pd = episodes(4, "clean-only").public()
    assert any(r["invoice_id"] is None for r in pd.ledger)
    assert all("invoice_refs" in p for p in pd.payments)
    raw = pd.files["payments.jsonl"].decode()
    assert '"invoice_refs":null' in raw or all(p["invoice_refs"] for p in pd.payments)


CASE_INVOICE_FIELDS = {"doc_id", "invoice_id", "entity_id", "issued_at", "due_at", "currency", "total_minor", "line_items"}


@pytest.mark.parametrize("seed", range(10))
def test_invoice_fields_exactly_as_in_case(seed):
    pd = generate_episode(seed, "clean-only").public()
    assert all(set(i) == CASE_INVOICE_FIELDS for i in pd.invoices)
    cns = [i for i in pd.invoices if any("cancels_invoice_id" in li for li in i["line_items"])]
    for cn in cns:  # the credit-note reference lives inside line_items and resolves
        assert cn["total_minor"] < 0
        assert {li["cancels_invoice_id"] for li in cn["line_items"]} <= set(pd.invoice_by_id)


def test_credit_notes_exist_and_solver_handles_them():
    seen = 0
    for seed in range(20):
        ep = generate_episode(seed, "clean-only")
        pd = ep.public()
        seen += sum(1 for i in pd.invoices if any("cancels_invoice_id" in li for li in i["line_items"]))
        assert solve(pd)["issues"] == []  # re-issued invoice is not a duplicate
    assert seen >= 5


def test_revenue_split_is_exact():
    from auditenv.generator.books import split_by_lines

    assert split_by_lines(100, [1, 1, 1]) == [34, 33, 33]
    assert split_by_lines(500, [100, 200, 200]) == [100, 200, 200]
    for total, w in ((12345, [3, 7, 11]), (1, [5, 5]), (999, [1])):
        assert sum(split_by_lines(total, w)) == total


@pytest.mark.parametrize("cfg", ["train-easy", "dev-mixed", "clean-only", "interaction-heavy"])
def test_episode_sizes_in_target_range(cfg):
    for seed in range(15):
        pd = generate_episode(seed, cfg).public()
        assert 200 <= len(pd.ledger) <= 450, len(pd.ledger)
        assert 30 <= len(pd.invoices) + len(pd.payments) <= 80


@pytest.mark.parametrize("cfg", ["dev-mixed", "interaction-heavy", "clean-only"])
def test_oracle_and_simple_reconcile_fit_in_100_steps(cfg):
    from auditenv.runner import run_episode

    for seed in range(8):
        ep = generate_episode(seed, cfg)
        for pol in ("oracle", "simple_reconcile"):
            g = run_episode(pol, episode=ep, isolate=False)["grade"]
            assert g["steps"] <= 100 and not g["truncated"]
