"""payment_allocation: a receipt that references invoices is (a) not applied at all
(Cr 2400 instead of 1200) or (b) applied only partially (rest on 2400)."""

from __future__ import annotations

from .base import MIN_AMOUNT, ErrorType, register, special, weighted_choice


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
        return True

    def applicable(self, book, used):
        out = []
        for p in book.payments.values():
            if special(p) or not self.eligible(book, p, used):
                continue
            if book.to_base(p.amount, p.currency, book.correct_rate(p.timestamp, p.currency)) < MIN_AMOUNT * 4:
                continue
            out.append(p.key)
        return sorted(out)

    def inject(self, book, target, rng, cfg, variant=None):
        p = book.payments[target]
        variant = variant or weighted_choice(rng, cfg["allocation_variants"])
        before = [book.snapshot(("pay", target))]
        if variant == "unallocated":
            alloc = []
        else:
            alloc = [list(x) for x in p.alloc]
            k, a = alloc[-1]
            part = a * rng.randint(30, 80) // 100
            alloc[-1] = [k, part]
            alloc = [tuple(x) for x in alloc if x[1] > 0]
        p.posted_alloc = alloc  # p.cash_rate (if an fx_rate mutation ran first) is kept
        book.post_payment(p)
        if book.row_of(("pay", target), "pay_unapplied").credit < MIN_AMOUNT:
            return None
        return self.finish(book, target, variant, [("pay", target)], before)

    def canonical_ids(self, book, target):
        return [book.payments[target].payment_id]

    def evidence_sets(self, book, target):
        p = book.payments[target]
        un = book.row_of(("pay", target), "pay_unapplied").row_id
        return [[p.doc_id] + [book.invoices[k].doc_id for k in p.refs] + [un]]

    def expected_amount(self, book, target, **kw):
        return book.row_of(("pay", target), "pay_unapplied").credit
