"""duplicate_invoice: the same bill entered twice (new doc_id/invoice_id, same entity and
line items, issued 0-2 days later, always in business hours). Both copies are posted. The later
one is the duplicate.

Variants: copy (only the duplicate invoice) and paid_twice (the client also paid the duplicate:
an extra, correctly posted receipt; the error is still the duplicate invoice).
Cosmetic differences that do NOT make it a different bill: line items in another order, another
payment term (due_at), the other timestamp offset format (local vs UTC). They are recorded in
provenance (mutation.detail).
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta

from .base import MIN_AMOUNT, ErrorType, register, special, weighted_choice, with_revenue_alternative

ALLOW = ("recurring_rent", "repeat_amount", "reissue", "night_fx", "weekend_fx", "overpayment")


@register
class DuplicateInvoice(ErrorType):
    name = "duplicate_invoice"
    invariant = "unique_billing"

    def applicable(self, book, used):
        end = book.story.period_end - timedelta(days=3)
        out = []
        for inv in book.invoices.values():
            if inv.key in used or inv.kind != "invoice" or special(inv, ALLOW) or inv.issued_at >= end:
                continue
            if any(i.cancels == inv.key for i in book.invoices.values()):
                continue
            if book.invoice_base(inv) < MIN_AMOUNT:
                continue
            out.append(inv.key)
        return sorted(out)

    def _dup_time(self, book, orig, rng):
        """0-2 days later, local business hours (9:00-18:59), strictly after the original."""
        tz = book.tz
        lo = orig.issued_at.astimezone(tz)
        for _ in range(20):
            d = lo.date() + timedelta(days=rng.randint(0, 2))
            t = datetime(d.year, d.month, d.day, rng.randint(9, 18), rng.randint(0, 59), rng.randint(0, 59), tzinfo=tz)
            if t > lo + timedelta(minutes=4):
                return t
        d = lo.date() + timedelta(days=1)
        return datetime(d.year, d.month, d.day, 9, rng.randint(0, 59), rng.randint(0, 59), tzinfo=tz)

    def inject(self, book, target, rng, cfg, base_amount=None, variant=None):
        from ..books import InvoiceDoc, PaymentDoc

        orig = book.invoices[target]
        if variant is None:
            variant = weighted_choice(rng, cfg.get("duplicate_variants", {"copy": 1.0})) or "copy"
        issued = book.uniq(self._dup_time(book, orig, rng))
        if issued >= book.story.period_end - timedelta(hours=1):
            return None
        key = f"{target}d"
        lines = copy.deepcopy(orig.line_items)
        detail = {}
        if len(lines) > 1 and rng.random() < 0.5:
            rng.shuffle(lines)
            detail["reordered_lines"] = True
        due_days = orig.due_days
        if rng.random() < 0.4:
            due_days = rng.choice([d for d in (14, 30, 45, 60) if d != orig.due_days])
            detail["different_due"] = True
        utc_fmt = rng.random() < book.story.utc_share / 100
        if rng.random() < 0.4:
            utc_fmt = not orig.utc_fmt
            detail["offset_format"] = "utc" if utc_fmt else "local"
        dup = InvoiceDoc(key=key, doc_id=book.ids.new("doc"), invoice_id=book.ids.new("invoice"),
                         entity_id=orig.entity_id, issued_at=issued, due_days=due_days, currency=orig.currency,
                         line_items=lines, kind="invoice", cancels=None, utc_fmt=utc_fmt, tags=["duplicate"])
        dup.posted_base = base_amount
        book.invoices[key] = dup
        book.post_invoice(dup)
        owners = [("inv", key)]
        if variant == "paid_twice":
            pay_at = issued + timedelta(days=rng.randint(1, 10), hours=rng.randint(0, 6), minutes=rng.randint(0, 59))
            if pay_at >= book.story.period_end - timedelta(hours=2):
                variant = "copy"  # no room left in the period for the second receipt
            else:
                pkey = f"p_{key}"
                p = PaymentDoc(key=pkey, doc_id=book.ids.new("doc"), payment_id=book.ids.new("payment"),
                               entity_id=orig.entity_id, timestamp=book.uniq(pay_at), currency=orig.currency,
                               amount=dup.total, refs=[key], alloc=[(key, dup.total)], fee=0,
                               utc_fmt=rng.random() < book.story.utc_share / 100, tags=["duplicate_payment"])
                book.payments[pkey] = p
                book.post_payment(p)
                owners.append(("pay", pkey))
        return self.finish(book, key, variant, owners, [{"document": None, "rows": []} for _ in owners],
                           touched=[target, key], detail=detail)

    def canonical_ids(self, book, target):
        return [book.invoices[target].invoice_id]

    def evidence_sets(self, book, target):
        dup = book.invoices[target]
        orig = book.invoices[target[:-1]]
        return with_revenue_alternative(book, ("inv", target), [orig.doc_id, dup.doc_id], [])

    def expected_amount(self, book, target, **kw):
        return book.row_of(("inv", target), "inv_ar").debit
