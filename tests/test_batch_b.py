"""Round-2 package B: the generator against cheap tricks (new variants, errors on paid and on
distractor documents, look-alikes, wider configs, extreme time zones)."""

import collections

import pytest

from auditenv.env.data import PublicData
from auditenv.generator.episode import generate_episode
from auditenv.generator.invariants import violated
from auditenv.generator.story import LOOKALIKES
from auditenv.grader.validate_truth import TYPE_OF_INVARIANT, validate
from auditenv.runner import run_episode
from auditenv.timeutil import TIMEZONES

INV = {v: k for k, v in TYPE_OF_INVARIANT.items()}
TYPES = sorted(INV)


def only(typ, **kw):
    cfg = {"name": f"only-{typ}", "errors": {t: (1.0 if t == typ else 0.0) for t in TYPES}, "n_errors": [2, 4],
           "clean_probability": 0.0, "foreign_currencies": ["USD", "EUR", "JPY", "KWD"], "n_foreign": [2, 3],
           "foreign_share": 0.45}
    cfg.update(kw)
    return cfg


def mutations(cfg, seeds):
    for seed in seeds:
        ep = generate_episode(seed, cfg)
        for m in ep.provenance["mutations"]:
            yield ep, m


def check_variant(cfg, typ, variant, seeds=range(15), need=2, pred=None):
    n = 0
    for ep, m in mutations(cfg, seeds):
        if m["type"] == typ and m["variant"] == variant and (pred is None or pred(ep, m)):
            n += 1
    assert n >= need, (typ, variant, n)
    return n


def all_valid(cfg, seeds):
    for seed in seeds:
        ep = generate_episode(seed, cfg)
        v = validate(ep.public(), ep.truth)
        assert v["ok"], (seed, v)
        assert violated(PublicData(ep.clean_files)) == {}
        assert run_episode("oracle", episode=ep, isolate=False)["grade"]["reward"] == 1.0
        want = {}
        for iss in ep.truth["issues"]:
            want.setdefault(INV[iss["type"]], {})[iss["affected_ids"][0]] = iss["expected_amount_minor"]
        assert violated(ep.public()) == want


# ---------------------------------------------------------------- B1 paid
def test_duplicate_paid_twice():
    cfg = only("duplicate_invoice", duplicate_variants={"copy": 0.0, "paid_twice": 1.0})
    all_valid(cfg, range(8))
    for ep, m in mutations(cfg, range(6)):
        if m["variant"] == "paid_twice":
            pd = ep.public()
            dup = m["after"][0]["document"]["invoice_id"]
            assert any(p["invoice_refs"] == [dup] for p in pd.payments)
            return
    pytest.fail("paid_twice never applied")


def test_fx_on_paid_invoice_relieves_ar_at_correct_rate():
    cfg = only("fx_rate", n_errors=[4, 6])
    all_valid(cfg, range(8))
    check_variant(cfg, "fx_rate", "adjacent_day", pred=lambda ep, m: m["detail"].get("paid"), need=1, seeds=range(25))


def test_cutoff_on_invoice_paid_in_period():
    cfg = only("period_cutoff")
    all_valid(cfg, range(8))
    n = 0
    for ep, m in mutations(cfg, range(10)):
        if m["detail"].get("paid_in_period"):
            pd = ep.public()
            iid = m["after"][0]["document"]["invoice_id"]
            pays = [p for p in pd.payments if p["invoice_refs"] and iid in p["invoice_refs"]]
            assert pays and all(pd.in_period(p["timestamp"]) for p in pays)
            assert not pd.in_period(m["after"][0]["document"]["issued_at"])
            n += 1
    assert n >= 3


# --------------------------------------------------- B2 night distractors
def test_night_fx_distractor_is_correct_and_utc_date_differs():
    seen = 0
    for seed in range(12):
        ep = generate_episode(seed, {"name": "night", "distractors": {"night_fx": 1.0}, "n_foreign": [1, 2]})
        pd = PublicData(ep.clean_files)
        assert violated(pd) == {}
        for ev in ep.provenance["story"]["events"]:
            if "night_fx" in ev.get("tags", []):
                inv = pd.invoice_by_id[ev["invoice_id"]]
                assert inv["issued_at"].endswith("+00:00") and inv["issued_at"][:10] != pd.local(inv["issued_at"]).date().isoformat()
                seen += 1
    assert seen >= 10


def test_duplicate_shift_stays_in_business_hours():
    for ep, m in mutations(only("duplicate_invoice"), range(10)):
        if m["type"] == "duplicate_invoice":
            pd = ep.public()
            assert 9 <= pd.local(m["after"][0]["document"]["issued_at"]).hour <= 18


# -------------------------------------------- B4 errors on distractor docs
def test_errors_reach_distractor_documents():
    tags = collections.Counter()
    cfg = {"name": "d", "clean_probability": 0.0, "n_errors": [5, 8], "foreign_currencies": ["USD", "EUR"],
           "n_invoices": [8, 12], "period_months": 3,
           "distractors": {"recurring_rent": 1.0, "credit_note_reissue": 1.0, "repeat_amount": 1.0, "night_fx": 1.0}}
    for seed in range(25):
        ep = generate_episode(seed, cfg)
        assert validate(ep.public(), ep.truth)["ok"]
        ev = {e.get("invoice_id"): e.get("tags", []) for e in ep.provenance["story"]["events"] if e.get("invoice_id")}
        for m in ep.provenance["mutations"]:
            doc = (m["before"][0]["document"] or m["after"][0]["document"])
            if doc and doc.get("invoice_id") in ev:
                for t in ev[doc["invoice_id"]]:
                    tags[(m["type"], t)] += 1
            if m["type"] == "duplicate_invoice":  # the original of a duplicate
                orig = [k for k, v in ev.items() if "recurring_rent" in v]
                lines = m["after"][0]["document"]["line_items"]
                if any(li["description"] == "Office rent" for li in lines):
                    tags[("duplicate_invoice", "recurring_rent")] += 1
    assert tags[("duplicate_invoice", "recurring_rent")] >= 1, tags
    assert any(t == "reissue" for (_, t) in tags), tags


# ------------------------------------------------------- B5 look-alikes
def test_every_episode_has_lookalikes_for_every_type():
    for cfg in ("dev-mixed", "clean-only", "interaction-heavy"):
        for seed in range(8):
            ep = generate_episode(seed, cfg)
            present = set(ep.provenance["story"]["distractors"])
            foreign = bool(ep.provenance["story"]["foreign_currencies"])
            for typ, kinds in LOOKALIKES.items():
                if typ == "fx_rate" and not foreign:
                    continue
                assert present & set(kinds), (cfg, seed, typ)


# -------------------------------------------------------- B6 wrong_invoice
def test_wrong_invoice_allocation():
    cfg = only("payment_allocation", allocation_variants={"unallocated": 0, "partial": 0, "wrong_invoice": 1.0},
               n_entities=[3, 4], n_invoices=[50, 60])
    all_valid(cfg, range(8))
    n = 0
    for ep, m in mutations(cfg, range(10)):
        if m["variant"] == "wrong_invoice":
            pd = ep.public()
            pay = m["after"][0]["document"]
            rows = [r for r in m["after"][0]["rows"] if r["account"] == "1200"]
            assert rows and all(r["invoice_id"] not in pay["invoice_refs"] for r in rows)
            assert all(r["entity_id"] == pd.invoice_by_id[r["invoice_id"]]["entity_id"] for r in rows)
            n += 1
    assert n >= 3


# ----------------------------------------------------------- B7 overpayment
def test_overpayment_is_clean_and_policy_says_so():
    ep = generate_episode(3, {"name": "op", "distractors": {"overpayment": 1.0}, "clean_probability": 1.0, "n_errors": [0, 0]})
    pd = ep.public()
    assert "overpayment" in pd.policy["unapplied_cash"] and violated(pd) == {}
    over = [p for p in pd.payments if p["invoice_refs"] and p["amount_minor"] > sum(
        pd.invoice_by_id[r]["total_minor"] for r in p["invoice_refs"])]
    assert over
    rows = [r for r in pd.ledger if r["payment_id"] == over[0]["payment_id"] and r["account"] == "2400"]
    assert rows and rows[0]["credit_minor"] > 0


# ------------------------------------------------------ B8 / B9 variants
@pytest.mark.parametrize("variant", ["historical_rate", "wrong_pair", "due_date", "adjacent_day", "utc_date"])
def test_fx_variants(variant):
    fv = {k: (1.0 if k == variant else 0.0) for k in ("adjacent_day", "utc_date", "inverted", "historical_rate",
                                                     "wrong_pair", "due_date")}
    cfg = only("fx_rate", fx_variants=fv, n_errors=[3, 5])
    if variant == "utc_date":  # needs a document whose UTC date differs from the local one: UTC+14 makes it common
        cfg["timezones"] = ["Pacific/Kiritimati"]
    all_valid(cfg, range(5))
    check_variant(cfg, "fx_rate", variant, seeds=range(12), need=2)


def test_historical_rate_has_no_7900_line():
    fv = {"adjacent_day": 0, "utc_date": 0, "inverted": 0, "historical_rate": 1.0, "wrong_pair": 0, "due_date": 0}
    for ep, m in mutations(only("fx_rate", fx_variants=fv, n_errors=[3, 5]), range(12)):
        if m["variant"] == "historical_rate":
            accounts = {r["account"] for r in m["after"][0]["rows"]}
            assert "7900" not in accounts and "1000" in accounts
            return
    pytest.fail("no historical_rate")


@pytest.mark.parametrize("variant", ["utc_trap", "backdated_posting", "prior_period"])
def test_cutoff_variants(variant):
    cv = {k: (1.0 if k == variant else 0.0) for k in ("utc_trap", "backdated_posting", "prior_period")}
    cfg = only("period_cutoff", cutoff_variants=cv)
    all_valid(cfg, range(5))
    check_variant(cfg, "period_cutoff", variant, need=2)


def test_backdated_posting_ledger_inside_document_outside():
    cv = {"utc_trap": 0, "backdated_posting": 1.0, "prior_period": 0}
    for ep, m in mutations(only("period_cutoff", cutoff_variants=cv), range(8)):
        if m["variant"] == "backdated_posting":
            pd = ep.public()
            doc = m["after"][0]["document"]
            assert not pd.in_period(doc["issued_at"]) and pd.local(doc["issued_at"]).day == 2
            assert all(pd.in_period(r["timestamp"]) for r in m["after"][0]["rows"])
            return
    pytest.fail("no backdated_posting")


# ------------------------------------------------- B10 cosmetic duplicates
def test_duplicate_cosmetic_variants():
    seen = collections.Counter()
    for ep, m in mutations(only("duplicate_invoice"), range(20)):
        seen.update(k for k in m["detail"])
    assert {"reordered_lines", "different_due", "offset_format"} <= set(seen), seen


# -------------------------------------------- B11 / B12 zones and configs
@pytest.mark.parametrize("tz", ["Asia/Kathmandu", "Pacific/Kiritimati", "Pacific/Pago_Pago"])
def test_extreme_timezones(tz):
    cfg = {"name": "tz", "timezones": [tz], "clean_probability": 0.0, "n_errors": [3, 5],
           "interactions": {"partial_fx_cutoff": 1.0, "duplicate_fx": 1.0}, "min_interactions": 1}
    all_valid(cfg, range(4))
    assert generate_episode(1, cfg).public().manifest["timezone"] == tz


@pytest.mark.parametrize("base", ["USD", "JPY", "KWD"])
def test_other_base_currencies(base):
    cfg = {"name": "b", "base_currencies": [base], "foreign_currencies": ["KZT", "USD", "EUR", "JPY", "KWD"],
           "clean_probability": 0.0, "n_errors": [3, 5], "period_starts": ["2026-11", "2026-02"], "period_months": [1, 3]}
    all_valid(cfg, range(4))


def test_open_configs_cover_new_ground():
    from auditenv.config import load_config
    from auditenv.paths import CONFIGS_DIR
    import json

    bases, zones, starts, months = set(), set(), set(), set()
    for p in CONFIGS_DIR.glob("*.json"):
        raw = json.loads(p.read_text())
        if not ("name" in raw and "version" in raw):
            continue
        c = load_config(p)
        bases.update(c["base_currencies"])
        zones.update(c["timezones"])
        starts.update(s[5:] for s in c["period_starts"])
        pm = c["period_months"]
        months.update(range(pm[0], pm[1] + 1) if isinstance(pm, list) else [pm])
    assert {"USD", "JPY", "KWD", "KZT"} <= bases
    assert {"Asia/Kathmandu", "Pacific/Kiritimati", "Pacific/Pago_Pago"} <= zones
    assert {"11", "02"} <= starts and {1, 2, 3} <= months
    assert set(TIMEZONES) == zones | (set(TIMEZONES) - zones)
