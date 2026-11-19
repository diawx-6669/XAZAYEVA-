"""duplicate_invoice: the same bill entered twice (new doc_id/invoice_id, same entity and
line items, issued 0-2 days later). Both copies are posted. The later one is the duplicate."""

from __future__ import annotations

import copy
from datetime import timedelta

from .base import MIN_AMOUNT, ErrorType, register, special


@register
class DuplicateInvoice(ErrorType):
    name = "duplicate_invoice"
    invariant = "unique_billing"

    def applicable(self, book, used):
        end = book.story.period_end - timedelta(days=3)
        out = []
        for inv in book.invoices.values():
            if inv.key in used or inv.kind != "invoice" or special(inv) or inv.issued_at >= end:
                continue
            if any(i.cancels == inv.key for i in book.invoices.values()):
                continue
            if book.invoice_base(inv) < MIN_AMOUNT:
                continue
            out.append(inv.key)
        return sorted(out)

    def inject(self, book, target, rng, cfg, base_amount=None, variant="copy"):
        from ..books import InvoiceDoc

        orig = book.invoices[target]
        shift = timedelta(days=rng.randint(0, 2), minutes=rng.randint(5, 600), seconds=rng.randint(-29, 29))
        issued = book.uniq(orig.issued_at + shift)
        if issued >= book.story.period_end - timedelta(hours=1):
            return None
        key = f"{target}d"
        dup = InvoiceDoc(key=key, doc_id=book.ids.new("doc"), invoice_id=book.ids.new("invoice"),
                         entity_id=orig.entity_id, issued_at=issued, due_days=orig.due_days, currency=orig.currency,
                         line_items=copy.deepcopy(orig.line_items), kind="invoice", cancels=None,
                         utc_fmt=rng.random() < book.story.utc_share / 100, tags=["duplicate"])
        dup.posted_base = base_amount
        book.invoices[key] = dup
        book.post_invoice(dup)
        return self.finish(book, key, variant, [("inv", key)], [{"document": None, "rows": []}],
                           original=target)

    def canonical_ids(self, book, target):
        return [book.invoices[target].invoice_id]

    def evidence_sets(self, book, target):
        dup = book.invoices[target]
        orig = book.invoices[target[:-1]]
        ar = book.row_of(("inv", target), "inv_ar").row_id
        rev = book.row_of(("inv", target), "inv_rev").row_id
        return [[orig.doc_id, dup.doc_id, ar], [orig.doc_id, dup.doc_id, rev]]

    def expected_amount(self, book, target, **kw):
        return book.row_of(("inv", target), "inv_ar").debit
