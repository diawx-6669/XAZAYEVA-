"""learned_reconcile: a policy whose decisions come from WEIGHTS TRAINED BY REINFORCEMENT LEARNING on the
environment's own reward (`make train`, auditenv/train.py, docs/TRAINING.md).

What is fixed (hand-written): the reader (pages through every table like simple_reconcile) and an
over-generating candidate generator - the naive rules of simple_reconcile plus the previous-business-day
FX rule. On clean books those candidates contain the look-alikes (re-issued invoices, overpayments,
duplicates copied at a wrong rate), so submitting all of them is punished by the reward.

What is learned: a logistic model p(submit | candidate) = sigmoid(w . x) over FEATURES (type one-hot and
context flags read from the records). Nobody tells the model which flag means "look-alike": it learns that
from the terminal reward alone (REINFORCE). The weights live in learned_weights.json next to this file.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from ..timeutil import parse_ts, tzinfo_for
from .base import submit
from .simple_reconcile import BASE_RULES, SimpleReconcile

WEIGHTS_FILE = Path(__file__).with_name("learned_weights.json")
CANDIDATE_RULES = BASE_RULES | {"fx_prev_business_day"}
TYPES = ["duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff", "vat_error"]
FEATURES = ["bias"] + [f"type:{t}" for t in TYPES] + [
    "credit_note_context",   # duplicate: one of the two invoices is cancelled by / is a credit note re-issue
    "overpayment",           # allocation: the receipt exceeds the totals of the invoices it references
    "also_duplicate",        # fx: the same invoice is also a duplicate candidate
    "no_exact_rate",         # fx: no rate on the local date (weekend), previous business day used
    "foreign_payment",       # fx: the document is a receipt (not an invoice)
    "log_amount",            # log10(claimed amount in minor units) / 10
]


def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


class _Data:  # SimpleReconcile.analyse only needs reader.data
    def __init__(self, data):
        self.data = data


def analyse_with(data: dict, manifest: dict, policy: dict, rules) -> list:
    """Findings of SimpleReconcile with `rules` on the records an agent read (no environment calls)."""
    gen = SimpleReconcile(0, rules)
    gen.manifest, gen.policy, gen.reader = manifest, policy, _Data(data)
    return gen.analyse()


def candidates(data: dict, manifest: dict, policy: dict) -> list:
    """(finding, feature vector) for every candidate the fixed generator proposes. Pure function of the
    records the agent read, so training can cache it per episode."""
    found = analyse_with(data, manifest, policy, CANDIDATE_RULES)
    invs, pays = data["invoices"], data["payments"]
    tz = tzinfo_for(manifest["timezone"])
    by_doc = {i["doc_id"]: i for i in invs}
    by_inv = {i["invoice_id"]: i for i in invs}
    cancelled = {li["cancels_invoice_id"] for i in invs for li in i["line_items"] if li.get("cancels_invoice_id")}
    cn_entities = {i["entity_id"] for i in invs if any(li.get("cancels_invoice_id") for li in i["line_items"])}
    dup_ids = {f["affected_ids"][0] for f in found if f["type"] == "duplicate_invoice"}
    rate_days = {(r["date"], r["source_currency"]) for r in data["fx"]}
    pay_by_id = {p["payment_id"]: p for p in pays}
    out = []
    for f in found:
        x = dict.fromkeys(FEATURES, 0.0)
        x["bias"] = 1.0
        x[f"type:{f['type']}"] = 1.0
        aid = f["affected_ids"][0]
        if f["type"] == "duplicate_invoice":
            orig = by_doc.get(f["evidence_ids"][0], {})
            dup = by_inv.get(aid, {})
            if (orig.get("invoice_id") in cancelled or aid in cancelled
                    or (dup.get("entity_id") in cn_entities and orig.get("entity_id") in cn_entities)):
                x["credit_note_context"] = 1.0
        elif f["type"] == "payment_allocation":
            p = pay_by_id.get(aid, {})
            refs = p.get("invoice_refs") or []
            if p and p["amount_minor"] > sum(by_inv[r]["total_minor"] for r in refs if r in by_inv):
                x["overpayment"] = 1.0
        elif f["type"] == "fx_rate":
            doc = by_inv.get(aid) or pay_by_id.get(aid) or {}
            if aid in dup_ids:
                x["also_duplicate"] = 1.0
            if aid in pay_by_id:
                x["foreign_payment"] = 1.0
            ts = doc.get("issued_at") or doc.get("timestamp")
            if ts and (parse_ts(ts).astimezone(tz).date().isoformat(), doc.get("currency")) not in rate_days:
                x["no_exact_rate"] = 1.0
        x["log_amount"] = math.log10(max(1, f["claimed_amount_minor"])) / 10.0
        out.append((f, [x[k] for k in FEATURES]))
    return out


def load_weights(path=WEIGHTS_FILE) -> list:
    w = json.loads(Path(path).read_text("utf-8"))
    assert w["features"] == FEATURES, "learned_weights.json was trained on other features: run make train"
    return w["weights"]


class LearnedReconcile(SimpleReconcile):
    name = "learned_reconcile"

    def __init__(self, seed: int = 0, weights=None):
        super().__init__(seed, rules=CANDIDATE_RULES)
        self.weights = list(weights) if weights is not None else load_weights()

    def act(self, obs):
        a = super().act(obs)
        if a["tool"] != "submit":
            return a
        data = self.reader.data
        cands = candidates(data, self.manifest, self.policy or {})
        keep = [f for f, x in cands if sigmoid(sum(wi * xi for wi, xi in zip(self.weights, x))) >= 0.5]
        return submit(self.manifest["episode_id"], keep[:30])
