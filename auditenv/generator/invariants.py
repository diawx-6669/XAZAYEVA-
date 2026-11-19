"""Accounting invariants over PUBLIC data only.

Each check returns a list of violations {invariant, id, amount}. In a clean book every
list is empty. Each error type breaks exactly one invariant, by exactly its
expected_amount_minor (see docs/DESIGN.md, "Invariants"):

  double_entry        always holds (all mutations keep postings balanced)
  completeness        always holds (every document posted, every reference resolves)
  allocation          payment_allocation
  fx_conversion       fx_rate
  period              period_cutoff
  unique_billing      duplicate_invoice
"""

from __future__ import annotations

from ..canon import dumps

INVARIANTS = ["double_entry", "completeness", "allocation", "fx_conversion", "period", "unique_billing"]


def _v(name, rid, amount, **detail):
    return {"invariant": name, "id": rid, "amount": amount, **detail}


def invoice_rows(pd) -> dict:
    """invoice_id -> rows of its own posting (accounts 1200/4000, no payment_id)."""
    out = {}
    for r in pd.ledger:
        if r["invoice_id"] and not r["payment_id"] and r["account"] in ("1200", "4000"):
            out.setdefault(r["invoice_id"], []).append(r)
    return out


def payment_rows(pd) -> dict:
    out = {}
    for r in pd.ledger:
        if r["payment_id"]:
            out.setdefault(r["payment_id"], []).append(r)
    return out


def invoice_posted_amount(rows) -> int:
    """Amount of the invoice posting: Dr 1200 (invoice) or Cr 1200 (credit note)."""
    return sum(r["debit_minor"] + r["credit_minor"] for r in rows if r["account"] == "1200")


def cancelled_by(inv):
    """invoice_id cancelled by this credit note (the reference lives inside line_items), else None."""
    refs = {li.get("cancels_invoice_id") for li in inv["line_items"]} - {None}
    return sorted(refs)[0] if refs else None


def is_credit_note(inv) -> bool:
    return cancelled_by(inv) is not None


def check_double_entry(pd) -> list:
    out = []
    td = sum(r["debit_minor"] for r in pd.ledger)
    tc = sum(r["credit_minor"] for r in pd.ledger)
    if td != tc:
        out.append(_v("double_entry", "__ledger__", abs(td - tc)))
    groups = {}
    for r in pd.ledger:
        key = (r["timestamp"], r["payment_id"] or r["invoice_id"] or r["row_id"])
        g = groups.setdefault(key, [0, 0])
        g[0] += r["debit_minor"]
        g[1] += r["credit_minor"]
    for key in sorted(groups):
        d, c = groups[key]
        if d != c:
            out.append(_v("double_entry", key[1], abs(d - c)))
    for r in pd.ledger:
        if (r["debit_minor"] > 0) == (r["credit_minor"] > 0) or r["debit_minor"] < 0 or r["credit_minor"] < 0:
            out.append(_v("double_entry", r["row_id"], 0, detail="row must have exactly one positive side"))
        if r["currency"] != pd.base:
            out.append(_v("double_entry", r["row_id"], 0, detail="ledger row not in base currency"))
    return out


def check_completeness(pd) -> list:
    out = []
    irows = invoice_rows(pd)
    prow = payment_rows(pd)
    for inv in pd.invoices:
        rows = irows.get(inv["invoice_id"], [])
        ar = [r for r in rows if r["account"] == "1200"]
        rev = [r for r in rows if r["account"] == "4000"]
        if len(ar) != 1 or len(rev) != len(inv["line_items"]):
            out.append(_v("completeness", inv["invoice_id"], 0, detail="invoice must be posted exactly once"))
        elif sum(r["debit_minor"] + r["credit_minor"] for r in rev) != ar[0]["debit_minor"] + ar[0]["credit_minor"]:
            out.append(_v("completeness", inv["invoice_id"], 0, detail="revenue lines do not sum to receivable"))
        refs = {li.get("cancels_invoice_id") for li in inv["line_items"]} - {None}
        if len(refs) > 1 or (refs and next(iter(refs)) not in pd.invoice_by_id):
            out.append(_v("completeness", inv["invoice_id"], 0, detail="credit note cancels unknown invoice"))
        if sum(li["amount_minor"] for li in inv["line_items"]) != inv["total_minor"]:
            out.append(_v("completeness", inv["invoice_id"], 0, detail="line items do not sum to total"))
    for p in pd.payments:
        if not prow.get(p["payment_id"]):
            out.append(_v("completeness", p["payment_id"], 0, detail="payment not posted"))
        for ref in p["invoice_refs"] or []:
            if ref not in pd.invoice_by_id:
                out.append(_v("completeness", p["payment_id"], 0, detail="unknown invoice ref"))
    for r in pd.ledger:
        if r["invoice_id"] and r["invoice_id"] not in pd.invoice_by_id:
            out.append(_v("completeness", r["row_id"], 0, detail="row references unknown invoice"))
        if r["payment_id"] and r["payment_id"] not in pd.payment_by_id:
            out.append(_v("completeness", r["row_id"], 0, detail="row references unknown payment"))
    return out


def expected_allocations(pd) -> dict:
    """payment_id -> [(invoice_id, amount in document currency)] under the policy rule:
    invoice_refs in order, each up to its open balance, payments in chronological order."""
    open_bal = {i["invoice_id"]: i["total_minor"] for i in pd.invoices if not is_credit_note(i)}
    pays = sorted(pd.payments, key=lambda p: (pd.local(p["timestamp"]).timestamp(), p["payment_id"]))
    out = {}
    for p in pays:
        remaining = p["amount_minor"]
        alloc = []
        for ref in p["invoice_refs"] or []:
            a = min(remaining, max(0, open_bal.get(ref, 0)))
            open_bal[ref] = open_bal.get(ref, 0) - a
            remaining -= a
            alloc.append((ref, a))
        out[p["payment_id"]] = (alloc, remaining)
    return out


def check_allocation(pd) -> list:
    out = []
    prow = payment_rows(pd)
    exp = expected_allocations(pd)
    for p in sorted(pd.payments, key=lambda p: p["payment_id"]):
        pid = p["payment_id"]
        rows = prow.get(pid, [])
        cr1200 = sum(r["credit_minor"] - r["debit_minor"] for r in rows if r["account"] == "1200")
        cr2400 = sum(r["credit_minor"] - r["debit_minor"] for r in rows if r["account"] == "2400")
        if p["invoice_refs"] is None:
            if cr1200 != 0:
                out.append(_v("allocation", pid, abs(cr1200)))
            continue
        alloc, remaining = exp[pid]
        exp1200 = 0
        for ref, a in alloc:
            inv = pd.invoice_by_id.get(ref)
            if inv is None:
                continue
            rate, _ = pd.correct_rate(inv["issued_at"], inv["currency"])
            if rate is None:
                continue
            exp1200 += pd.to_base(a, p["currency"], rate)
        if remaining == 0:
            if cr2400 != 0:
                out.append(_v("allocation", pid, abs(cr2400)))
            elif cr1200 != exp1200:
                out.append(_v("allocation", pid, abs(exp1200 - cr1200)))
        else:
            rate, _ = pd.correct_rate(p["timestamp"], p["currency"])
            exp2400 = pd.to_base(remaining, p["currency"], rate) if rate else 0
            if cr2400 != exp2400 or cr1200 != exp1200:
                out.append(_v("allocation", pid, abs(cr2400 - exp2400) or abs(cr1200 - exp1200)))
    return out


def check_fx(pd, skip_invoice_ids=()) -> list:
    out = []
    irows = invoice_rows(pd)
    prow = payment_rows(pd)
    skip = set(skip_invoice_ids)
    for inv in sorted(pd.invoices, key=lambda i: i["invoice_id"]):
        if inv["invoice_id"] in skip:
            continue
        rate, _ = pd.correct_rate(inv["issued_at"], inv["currency"])
        if rate is None:
            out.append(_v("fx_conversion", inv["invoice_id"], 0, detail="no rate available"))
            continue
        expected = pd.to_base(abs(inv["total_minor"]), inv["currency"], rate)
        posted = invoice_posted_amount(irows.get(inv["invoice_id"], []))
        if posted != expected:
            out.append(_v("fx_conversion", inv["invoice_id"], abs(posted - expected)))
    for p in sorted(pd.payments, key=lambda p: p["payment_id"]):
        rate, _ = pd.correct_rate(p["timestamp"], p["currency"])
        if rate is None:
            out.append(_v("fx_conversion", p["payment_id"], 0, detail="no rate available"))
            continue
        expected = pd.to_base(p["amount_minor"], p["currency"], rate)
        posted = sum(r["debit_minor"] for r in prow.get(p["payment_id"], []) if r["account"] == "1000")
        if posted != expected:
            out.append(_v("fx_conversion", p["payment_id"], abs(posted - expected)))
    return out


def check_period(pd) -> list:
    groups = {}
    for r in pd.ledger:
        if not pd.in_period(r["timestamp"]):
            key = r["invoice_id"] if (r["invoice_id"] and not r["payment_id"]) else (r["payment_id"] or r["row_id"])
            groups.setdefault(key, []).append(r)
    out = []
    for key in sorted(groups):
        rows = groups[key]
        amt = sum(r["debit_minor"] for r in rows if r["account"] == "1200") or sum(r["debit_minor"] for r in rows)
        out.append(_v("period", key, amt))
    return out


def billing_signature(inv) -> str:
    items = sorted(dumps({k: li[k] for k in ("description", "service_period", "quantity", "unit_price_minor",
                                             "amount_minor")}) for li in inv["line_items"])
    return dumps([inv["entity_id"], inv["currency"], items])


def duplicate_invoices(pd) -> list:
    """[(duplicate invoice, original invoice)]; the later issued_at is the duplicate."""
    cancelled = {cancelled_by(i) for i in pd.invoices if is_credit_note(i)}
    groups = {}
    for inv in pd.invoices:
        if is_credit_note(inv) or inv["invoice_id"] in cancelled:
            continue
        groups.setdefault(billing_signature(inv), []).append(inv)
    out = []
    for sig in sorted(groups):
        invs = sorted(groups[sig], key=lambda i: (pd.local(i["issued_at"]).timestamp(), i["invoice_id"]))
        for dup in invs[1:]:
            out.append((dup, invs[0]))
    return out


def check_unique(pd) -> list:
    irows = invoice_rows(pd)
    return [_v("unique_billing", dup["invoice_id"], invoice_posted_amount(irows.get(dup["invoice_id"], [])),
               original=orig["invoice_id"]) for dup, orig in duplicate_invoices(pd)]


def check_all(pd) -> dict:
    uniq = check_unique(pd)
    return {
        "double_entry": check_double_entry(pd),
        "completeness": check_completeness(pd),
        "allocation": check_allocation(pd),
        "fx_conversion": check_fx(pd, skip_invoice_ids=[v["id"] for v in uniq]),
        "period": check_period(pd),
        "unique_billing": uniq,
    }


def violated(pd) -> dict:
    """{invariant: {id: amount}} for violated invariants only."""
    return {k: {v["id"]: v["amount"] for v in vs} for k, vs in check_all(pd).items() if vs}
