"""Independent solver: finds every issue from PUBLIC data only (no provenance, no truth),
then checks that truth agrees and that every evidence set is (a) reachable through the
tools and (b) sufficient on its own to recompute the issue amount.

An episode where the solver and truth disagree is a generator defect.
"""

from __future__ import annotations

from ..generator.invariants import billing_signature, check_all
from ..timeutil import parse_ts

TYPE_OF_INVARIANT = {
    "unique_billing": "duplicate_invoice",
    "allocation": "payment_allocation",
    "fx_conversion": "fx_rate",
    "period": "period_cutoff",
    "vat": "vat_error",
}


def solve(pd) -> dict:
    """Returns {"issues": [...], "structural": [...]} found from public data."""
    inv = check_all(pd)
    issues = []
    for name, typ in TYPE_OF_INVARIANT.items():
        for v in inv[name]:
            issues.append({"type": typ, "affected_ids": [v["id"]], "amount": v["amount"]})
    structural = inv["double_entry"] + inv["completeness"]
    issues.sort(key=lambda x: (x["type"], x["affected_ids"]))
    return {"issues": issues, "structural": structural}


# ------------------------------------------------------------ evidence checks
def _records(pd, ids):
    out = {}
    for i in ids:
        rec = pd.any_record(i)
        if rec is None:
            return None
        out[i] = rec
    return out


def _of(recs, kind):
    return [r for k, r in recs.values() if k == kind]


def posting_from_rows(rows, inv):
    """Invoice posting amount provable from the rows in an evidence set: its Dr/Cr 1200 row, or
    ALL its revenue rows (policy: one 4000 row per line item)."""
    own = [x for x in rows if x["invoice_id"] == inv["invoice_id"] and not x["payment_id"]]
    ar = [x for x in own if x["account"] == "1200"]
    if ar:
        return ar[0]["debit_minor"] + ar[0]["credit_minor"]
    rev = [x for x in own if x["account"] == "4000"]
    if rev and len({x["row_id"] for x in rev}) == len(inv["line_items"]):
        return sum(x["debit_minor"] + x["credit_minor"] for x in rev)
    return None


def verify_evidence(pd, issue: dict, ev: list):
    """Recompute the issue amount from the evidence records only. Returns (ok, reason, amount)."""
    if not (1 <= len(ev) <= 6):
        return False, "bad_size", None
    recs = _records(pd, ev)
    if recs is None:
        return False, "unreachable_id", None
    typ = issue["type"]
    aid = issue["affected_ids"][0]
    invoices, payments = _of(recs, "invoice"), _of(recs, "payment")
    rows, fxs, pols = _of(recs, "ledger"), _of(recs, "fx"), _of(recs, "policy")
    amount = None
    if typ == "duplicate_invoice":
        dup = [i for i in invoices if i["invoice_id"] == aid]
        if not dup:
            return False, "missing_document", None
        dup = dup[0]
        t_dup = parse_ts(dup["issued_at"])
        origs = [i for i in invoices if i["invoice_id"] != aid and billing_signature(i) == billing_signature(dup)
                 and (parse_ts(i["issued_at"]), i["invoice_id"]) < (t_dup, aid)]
        if not origs:
            return False, "missing_original", None
        amount = posting_from_rows(rows, dup)
        if amount is None:
            return False, "missing_ledger_row", None
    elif typ == "payment_allocation":
        p = [x for x in payments if x["payment_id"] == aid]
        if not p or not p[0]["invoice_refs"]:
            return False, "missing_document", None
        have = {i["invoice_id"] for i in invoices}
        if not set(p[0]["invoice_refs"]) <= have:
            return False, "missing_invoice", None
        refs = p[0]["invoice_refs"]
        r = [x for x in rows if x["payment_id"] == aid and x["account"] == "2400" and x["credit_minor"]]
        if not r:  # wrong_invoice: a Cr 1200 row of this receipt on an invoice it does not reference
            r = [x for x in rows if x["payment_id"] == aid and x["account"] == "1200" and x["credit_minor"]
                 and x["invoice_id"] and x["invoice_id"] not in refs]
        applied = [x for x in rows if x["payment_id"] == aid and x["account"] == "1200" and x["credit_minor"]
                   and x["invoice_id"] in refs]
        if r:
            amount = r[0]["credit_minor"]
        elif applied and p[0]["currency"] == pd.base:
            # alternative set: expected application (refs in order up to their totals) minus applied rows
            left, want = p[0]["amount_minor"], 0
            by_id = {i["invoice_id"]: i for i in invoices}
            for ref in refs:
                a = min(left, max(0, by_id[ref]["total_minor"]))
                want += a
                left -= a
            if {x["invoice_id"] for x in applied} != {ref for ref in refs if by_id[ref]["total_minor"] > 0} - (
                    set() if len(applied) == len(refs) else {refs[-1]}):
                return False, "missing_ledger_row", None
            amount = want - sum(x["credit_minor"] for x in applied)
            if amount <= 0:
                return False, "amount_not_reproduced", amount
        else:
            return False, "missing_ledger_row", None
    elif typ == "fx_rate":
        docs = [d for d in invoices if d["invoice_id"] == aid] + [d for d in payments if d["payment_id"] == aid]
        if not docs or not pols or not fxs:
            return False, "missing_document", None
        d = docs[0]
        is_inv = "invoice_id" in d
        ts = d["issued_at"] if is_inv else d["timestamp"]
        want = pd.calendar_rate_date(pd.local(ts).date()).isoformat()
        fx = [f for f in fxs if f["source_currency"] == d["currency"] and f["date"] == want]
        if not fx:
            return False, "wrong_rate_record", None
        amt_doc = abs(d["total_minor"]) if is_inv else d["amount_minor"]
        correct = pd.to_base(amt_doc, d["currency"], fx[0]["rate"])
        if is_inv:
            posted = posting_from_rows(rows, d)
        else:
            r = [x for x in rows if x["payment_id"] == aid and x["account"] == "1000" and x["debit_minor"]]
            posted = r[0]["debit_minor"] if r else None
            other = [x for x in rows if x["payment_id"] == aid and x["account"] in ("1200", "2400", "7900")]
            if posted is None and any(x["account"] == "1200" for x in other):
                # alternative set: cash = Cr 1200 + Cr 2400 + (Cr 7900 - Dr 7900)
                posted = sum(x["credit_minor"] - (x["debit_minor"] if x["account"] == "7900" else 0) for x in other)
        if posted is None:
            return False, "missing_ledger_row", None
        amount = abs(posted - correct)
    elif typ == "period_cutoff":
        d = [i for i in invoices if i["invoice_id"] == aid]
        if not d or not pols:
            return False, "missing_document", None
        pb = pols[0]["period_boundary"]
        t = parse_ts(d[0]["issued_at"])
        if parse_ts(pb["start"]) <= t < parse_ts(pb["end"]):
            return False, "not_outside_period", None
        amount = posting_from_rows(rows, d[0])
        if amount is None:
            return False, "missing_ledger_row", None
    elif typ == "vat_error":
        from ..generator.errors.vat_error import split_vat, vat_of

        d = [i for i in invoices if i["invoice_id"] == aid]
        if not d or not pols:
            return False, "missing_document", None
        vat, net = split_vat(d[0]["line_items"])
        if vat is None:
            return False, "no_vat_line", None
        amount = abs(vat["amount_minor"] - vat_of(net))
    else:
        return False, "unknown_type", None
    if abs(amount - issue["expected_amount_minor"]) > 1:
        return False, "amount_not_reproduced", amount
    return True, "ok", amount


def validate(pd, truth: dict, tolerance: int | None = None) -> dict:
    if tolerance is None:
        tolerance = truth.get("tolerance_minor", 1)
    found = solve(pd)
    want = {(i["type"], tuple(i["affected_ids"])): i for i in truth["issues"]}
    got = {(i["type"], tuple(i["affected_ids"])): i for i in found["issues"]}
    missing = sorted(k for k in want if k not in got)
    extra = sorted(k for k in got if k not in want)
    amount_mismatch = sorted(k for k in want if k in got
                             and abs(got[k]["amount"] - want[k]["expected_amount_minor"]) > tolerance)
    evidence_problems = []
    for iss in truth["issues"]:
        sets = iss["evidence_sets"]
        if not (1 <= len(sets) <= 3):
            evidence_problems.append((iss["issue_id"], "bad_number_of_sets"))
        for ev in sets:
            ok, reason, _ = verify_evidence(pd, iss, ev)
            if not ok:
                evidence_problems.append((iss["issue_id"], reason))
        if iss["currency"] != pd.base:
            evidence_problems.append((iss["issue_id"], "currency_not_base"))
        if len({x for s in sets for x in s}) > 10:  # "submit every set" must fit the 10 evidence_ids limit
            evidence_problems.append((iss["issue_id"], "evidence_union_over_10"))
    ok = not (missing or extra or amount_mismatch or evidence_problems or found["structural"])
    return {"ok": ok, "missing": missing, "extra": extra, "amount_mismatch": amount_mismatch,
            "evidence_problems": evidence_problems, "structural": found["structural"],
            "n_truth": len(want), "n_found": len(got)}
