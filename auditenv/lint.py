"""Plausibility linter (round 2, C3): the books must look like a real company's, except exactly
where truth declares an error.

Rules (on PUBLIC data):
  pay_before_invoice   a receipt is not dated before an invoice it references
  refund_over_paid     refunds of an invoice do not exceed what was applied to it
  due_before_issue     due_at >= issued_at
  credit_note_early    a credit note is issued after the invoice it cancels
  client_mismatch      the client on a receipt's ledger rows is the client of its invoices
  outside_period       documents/rows outside the period only where truth declares period_cutoff
  service_period_far   every service_period is within the local issue month +-1
A finding is allowed only if its id is an affected_id of a truth issue.
"""

from __future__ import annotations

from .generator.invariants import cancelled_invoice_id


def _month_index(ym: str) -> int:
    y, m = ym.split("-")
    return int(y) * 12 + int(m) - 1


def lint(pd) -> list:
    out = []
    inv = pd.invoice_by_id
    applied, refunded, pay_entities = {}, {}, {}
    for r in pd.ledger:
        if r["account"] == "1200" and r["payment_id"] and r["invoice_id"]:
            applied[r["invoice_id"]] = applied.get(r["invoice_id"], 0) + r["credit_minor"] - r["debit_minor"]
        if r["account"] == "4100" and r["invoice_id"]:
            refunded[r["invoice_id"]] = refunded.get(r["invoice_id"], 0) + r["debit_minor"]
        if r["payment_id"] and r["entity_id"]:
            pay_entities.setdefault(r["payment_id"], set()).add(r["entity_id"])
    for p in pd.payments:
        t = pd.local(p["timestamp"])
        for ref in p["invoice_refs"] or []:
            if ref in inv and t < pd.local(inv[ref]["issued_at"]):
                out.append(("pay_before_invoice", p["payment_id"]))
            if ref in inv and pay_entities.get(p["payment_id"], set()) - {inv[ref]["entity_id"]}:
                out.append(("client_mismatch", p["payment_id"]))
    for iid, amt in refunded.items():
        if amt > applied.get(iid, 0):
            out.append(("refund_over_paid", iid))
    for i in pd.invoices:
        if pd.local(i["due_at"]) < pd.local(i["issued_at"]):
            out.append(("due_before_issue", i["invoice_id"]))
        ref = cancelled_invoice_id(i)
        if ref and ref in inv and pd.local(i["issued_at"]) <= pd.local(inv[ref]["issued_at"]):
            out.append(("credit_note_early", i["invoice_id"]))
        if not pd.in_period(i["issued_at"]):
            out.append(("outside_period", i["invoice_id"]))
        m = _month_index(pd.local(i["issued_at"]).strftime("%Y-%m"))
        if any(abs(_month_index(li["service_period"]) - m) > 1 for li in i["line_items"]):
            out.append(("service_period_far", i["invoice_id"]))
    for r in pd.ledger:
        if not pd.in_period(r["timestamp"]):
            out.append(("outside_period", r["invoice_id"] or r["payment_id"] or r["row_id"]))
    return sorted(set(out))


def unexplained(pd, truth) -> list:
    """Lint findings NOT covered by a truth issue (must be empty)."""
    allowed = {a for i in truth["issues"] for a in i["affected_ids"]}
    cutoff = {a for i in truth["issues"] if i["type"] == "period_cutoff" for a in i["affected_ids"]}
    bad = []
    for rule, rid in lint(pd):
        if rule == "outside_period":
            if rid not in cutoff:
                bad.append((rule, rid))
        elif rid not in allowed:
            bad.append((rule, rid))
    return bad
