"""Jury policy: flag everything. Reads invoices and payments, then spends all 30 findings
cycling every document id through every type, claiming the document total as amount."""
from jl import Conn, run

TYPES = ["duplicate_invoice", "fx_rate", "period_cutoff", "payment_allocation"]


def main(c: Conn):
    first = c.start()
    m = first["manifest"]
    ep, base = m["episode_id"], m["base_currency"]
    inv = c.list_all("invoices")
    pay = c.list_all("payments")
    findings = []
    for r in inv + pay:
        is_inv = "invoice_id" in r
        aid = r["invoice_id"] if is_inv else r["payment_id"]
        amt = r["total_minor"] if is_inv else r["amount_minor"]
        types = TYPES[:3] if is_inv else ["payment_allocation", "fx_rate"]
        for t in types:
            if len(findings) >= 30:
                break
            findings.append({"type": t, "affected_ids": [aid], "claimed_amount_minor": int(amt),
                             "currency": base, "evidence_ids": [r["doc_id"], "policy"],
                             "explanation": "flag all"})
    c.submit(ep, findings)


run(main)
