"""Jury policy: simple reconciliation written from the case text and the task/policy summary only.

Reads every table page by page (~15 steps), then:
* duplicate_invoice  - same entity, currency, total and line items (incl. service_period),
                       issued within 3 days; the later one is the duplicate; cancelled
                       invoices (credit notes) are skipped;
* payment_allocation - receipt with invoice_refs that has cash on 2400 while a referenced
                       invoice is still open, or Cr 1200 applied to an invoice not in refs;
* fx_rate            - recompute base amount by policy (local date, previous business day,
                       ROUND_HALF_EVEN) and compare with the posted 1200 / 1000 amount;
* period_cutoff      - invoice issued (as an instant) outside [start, end) but posted.
"""
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal

from jl import Conn, run


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def tz_of(offset):
    sign = -1 if offset.startswith("-") else 1
    h, m = offset.lstrip("+-").split(":")
    return timezone(sign * timedelta(hours=int(h), minutes=int(m)))


def main(c: Conn):
    first = c.start()
    m, pol = first["manifest"], first["policy_summary"]
    ep, base, exps = m["episode_id"], m["base_currency"], m["currencies"]
    pb = pol["period_boundary"]
    tz = tz_of(pb.get("utc_offset", "+00:00"))
    p_start, p_end = parse_ts(pb["start"]), parse_ts(pb["end"])

    invoices = c.list_all("invoices")
    payments = c.list_all("payments")
    fx = c.list_all("fx")
    ledger = c.list_all("ledger")

    rates = {}
    for r in fx:
        rates.setdefault((r["source_currency"], r["target_currency"]), {})[r["date"]] = r["rate"]

    def rate_for(cur, ts):
        d = parse_ts(ts).astimezone(tz).date().isoformat()
        table = rates.get((cur, base), {})
        cands = [x for x in table if x <= d]
        if not cands:
            return None, None
        day = max(cands)
        return Decimal(table[day]), f"fx:{day}:{cur}:{base}"

    def to_base(amount, cur, ts):
        if cur == base:
            return amount, None
        rate, fid = rate_for(cur, ts)
        if rate is None:
            return None, None
        q = Decimal(amount) * rate * (Decimal(10) ** (exps[base] - exps[cur]))
        return int(q.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)), fid

    by_inv, by_pay = {}, {}
    for r in ledger:
        if r.get("payment_id"):
            by_pay.setdefault(r["payment_id"], []).append(r)
        elif r.get("invoice_id"):
            by_inv.setdefault(r["invoice_id"], []).append(r)

    def amt(r, side):
        return int(r[side] or 0)

    inv_by_id = {i["invoice_id"]: i for i in invoices}
    cancelled = {li.get("cancels_invoice_id") for i in invoices for li in i["line_items"]
                 if li.get("cancels_invoice_id")}
    findings = []

    def add(t, aid, amount, ev):
        ev = list(dict.fromkeys(e for e in ev if e))[:10]
        findings.append({"type": t, "affected_ids": [aid], "claimed_amount_minor": int(amount),
                         "currency": base, "evidence_ids": ev, "explanation": "reconcile"})

    # duplicate_invoice
    def key(i):
        items = tuple(sorted((li["description"], li.get("service_period"), li["quantity"],
                              li["unit_price_minor"], li["amount_minor"]) for li in i["line_items"]))
        return (i["entity_id"], i["currency"], i["total_minor"], items)

    dups = set()
    groups = {}
    for i in invoices:
        if i["invoice_id"] in cancelled or any(li.get("cancels_invoice_id") for li in i["line_items"]):
            continue
        groups.setdefault(key(i), []).append(i)
    for g in groups.values():
        g.sort(key=lambda i: (parse_ts(i["issued_at"]), i["invoice_id"]))
        for orig, dup in zip(g, g[1:]):
            if parse_ts(dup["issued_at"]) - parse_ts(orig["issued_at"]) > timedelta(days=3):
                continue
            rows = by_inv.get(dup["invoice_id"], [])
            posted = sum(amt(r, "debit_minor") for r in rows if r["account"] == "1200")
            if posted:
                dups.add(dup["invoice_id"])
                ar = [r["row_id"] for r in rows if r["account"] == "1200"]
                add("duplicate_invoice", dup["invoice_id"], posted,
                    [orig["doc_id"], dup["doc_id"]] + ar)

    # period_cutoff
    for i in invoices:
        t = parse_ts(i["issued_at"])
        rows = by_inv.get(i["invoice_id"], [])
        if (t < p_start or t >= p_end) and rows:
            posted = sum(amt(r, "debit_minor") - amt(r, "credit_minor") for r in rows if r["account"] == "1200")
            ar = [r["row_id"] for r in rows if r["account"] == "1200"]
            add("period_cutoff", i["invoice_id"], abs(posted), [i["doc_id"]] + ar + ["policy"])

    # fx_rate on invoices
    for i in invoices:
        if i["currency"] == base or i["invoice_id"] in dups:
            continue
        rows = by_inv.get(i["invoice_id"], [])
        ar = [r for r in rows if r["account"] == "1200"]
        if not ar:
            continue
        posted = abs(sum(amt(r, "debit_minor") - amt(r, "credit_minor") for r in ar))
        want, fid = to_base(abs(i["total_minor"]), i["currency"], i["issued_at"])
        if want is not None and abs(posted - want) > 1:
            add("fx_rate", i["invoice_id"], abs(posted - want),
                [i["doc_id"]] + [r["row_id"] for r in ar] + [fid, "policy"])

    # AR balance per invoice from the ledger (as posted)
    ar_bal = {}
    for r in ledger:
        if r["account"] == "1200" and r.get("invoice_id"):
            ar_bal[r["invoice_id"]] = ar_bal.get(r["invoice_id"], 0) + amt(r, "debit_minor") - amt(r, "credit_minor")

    for p in payments:
        rows = by_pay.get(p["payment_id"], [])
        refs = p.get("invoice_refs") or []
        # fx_rate on payments: cash received
        if p["currency"] != base and rows:
            cash = sum(amt(r, "debit_minor") for r in rows if r["account"] == "1000")
            want, fid = to_base(p["amount_minor"], p["currency"], p["timestamp"])
            if want is not None and cash and abs(cash - want) > 1:
                cash_rows = [r["row_id"] for r in rows if r["account"] == "1000" and amt(r, "debit_minor")]
                add("fx_rate", p["payment_id"], abs(cash - want),
                    [p["doc_id"]] + cash_rows + [fid, "policy"])
        if not refs or not rows:
            continue
        unapplied = sum(amt(r, "credit_minor") - amt(r, "debit_minor") for r in rows if r["account"] == "2400")
        wrong = [r for r in rows if r["account"] == "1200" and r.get("invoice_id") and r["invoice_id"] not in refs]
        open_refs = sum(max(ar_bal.get(x, 0), 0) for x in refs)
        ref_docs = [inv_by_id[x]["doc_id"] for x in refs if x in inv_by_id]
        if wrong:
            moved = sum(amt(r, "credit_minor") for r in wrong)
            add("payment_allocation", p["payment_id"], moved,
                [p["doc_id"]] + ref_docs + [r["row_id"] for r in wrong])
        elif unapplied > 0 and open_refs > 1:
            claim = min(unapplied, open_refs)
            if p["currency"] != base:
                # task text: the unapplied part is converted at the PAYMENT's policy rate.
                # Recover the applied part in payment currency through each invoice's own rate.
                applied = Decimal(0)
                for r in rows:
                    if r["account"] == "1200" and r.get("invoice_id") in inv_by_id:
                        iv = inv_by_id[r["invoice_id"]]
                        rate, _ = rate_for(iv["currency"], iv["issued_at"]) if iv["currency"] != base else (None, None)
                        if rate:
                            applied += Decimal(amt(r, "credit_minor")) / (rate * Decimal(10) ** (exps[base] - exps[iv["currency"]]))
                left = Decimal(p["amount_minor"]) - applied
                left = int(left.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
                conv, _ = to_base(left, p["currency"], p["timestamp"])
                if conv is not None:
                    claim = conv
            r2400 = [r["row_id"] for r in rows if r["account"] == "2400"]
            add("payment_allocation", p["payment_id"], claim, [p["doc_id"]] + ref_docs + r2400)

    c.submit(ep, findings[:30])


run(main)
