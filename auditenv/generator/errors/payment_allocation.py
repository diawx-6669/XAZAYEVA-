"""payment_allocation: a receipt that references invoices is
  unallocated    not applied at all (Cr 2400 instead of 1200),
  partial        applied only partially (the rest on 2400), or
  wrong_invoice  applied to ANOTHER open invoice of the same client (Cr 1200 on INV-B while the
                 receipt references INV-A; base currency only, so the amount is unambiguous).
The amount is the misapplied part in base currency: the 2400 credit (converted at the payment's
policy rate) or the 1200 credit on the wrong invoice.
"""

from __future__ import annotations

from .base import MIN_AMOUNT, ErrorType, register, special, weighted_choice

ALLOW = ("rounding_residual",)


@register
class PaymentAllocation(ErrorType):
    name = "payment_allocation"
    invariant = "allocation"

    def eligible(self, book, p, used) -> bool:
        if p.key in used or not p.refs or not p.alloc:
            return False
        for k in p.refs:
            if k in used or len(book.allocations_to(k)) != 1:
                return False
            if any(rf.invoice == k for rf in book.refunds):  # a refund must never exceed what was applied
                return False
        return True

    def applicable(self, book, used):
        out = []
        for p in book.payments.values():
            if special(p, ALLOW) or not self.eligible(book, p, used):
                continue
            if book.to_base(p.amount, p.currency, book.correct_rate(p.timestamp, p.currency)) < MIN_AMOUNT * 4:
                continue
            out.append(p.key)
        return sorted(out)

    def wrong_invoice_for(self, book, p, used):
        """Another open invoice of the same client in the same (base) currency, issued before the receipt."""
        if p.currency != book.base or len(p.refs) != 1:
            return None
        cancelled = {i.cancels for i in book.invoices.values() if i.cancels}
        cands = [i.key for i in book.invoices.values()
                 if i.entity_id == p.entity_id and i.currency == p.currency and i.kind == "invoice"
                 and i.key not in p.refs and i.key not in used and i.key not in cancelled
                 and not book.allocations_to(i.key) and not book.referenced_by(i.key) and not i.tags
                 and i.issued_at < p.timestamp and not any(rf.invoice == i.key for rf in book.refunds)]
        return sorted(cands)

    def inject(self, book, target, rng, cfg, variant=None, used=frozenset()):
        p = book.payments[target]
        variant = variant or weighted_choice(rng, cfg["allocation_variants"])
        touched = [target] + list(p.refs)
        if variant == "wrong_invoice":
            others = self.wrong_invoice_for(book, p, used)
            if not others:
                variant = "partial"
            else:
                wrong = rng.choice(others)
                touched.append(wrong)
        before = [book.snapshot(("pay", target))]
        if variant == "unallocated":
            alloc = []
        elif variant == "wrong_invoice":
            alloc = [(wrong, a) for _, a in p.alloc]
        else:
            alloc = [list(x) for x in p.alloc]
            k, a = alloc[-1]
            part = a * rng.randint(30, 80) // 100
            alloc[-1] = [k, part]
            alloc = [tuple(x) for x in alloc if x[1] > 0]
        p.posted_alloc = alloc  # p.cash_rate (if an fx_rate mutation ran first) is kept
        book.post_payment(p)
        if self.expected_amount(book, target) < MIN_AMOUNT:
            return None
        return self.finish(book, target, variant, [("pay", target)], before, touched=touched)

    def _misapplied_rows(self, book, target):
        p = book.payments[target]
        rows = []
        for r in book.rows_of(("pay", target)):
            if r.role == "pay_unapplied":
                rows.append(r)
            elif r.role.startswith("pay_ar:") and r.invoice_key not in (p.refs or []):
                rows.append(r)
        return rows

    def canonical_ids(self, book, target):
        return [book.payments[target].payment_id]

    def evidence_sets(self, book, target):
        p = book.payments[target]
        docs = [p.doc_id] + [book.invoices[k].doc_id for k in p.refs]
        sets = [docs + [self._misapplied_rows(book, target)[0].row_id]]
        # Alternative (base-currency partial allocation): the Cr 1200 rows that WERE applied. Expected
        # application (refs in order up to their totals) minus what was applied = the misapplied part.
        applied = [r.row_id for r in book.rows_of(("pay", target))
                   if r.role.startswith("pay_ar:") and r.invoice_key in (p.refs or [])]
        unapplied = [r for r in book.rows_of(("pay", target)) if r.role == "pay_unapplied"]
        if p.currency == book.base and applied and unapplied and len(docs) + len(applied) <= 6:
            sets.append(docs + applied)
        return sets

    def expected_amount(self, book, target, **kw):
        return sum(r.credit for r in self._misapplied_rows(book, target))
