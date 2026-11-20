"""period_cutoff: an invoice issued outside the period (by LOCAL time) is posted in this
period's ledger. The timestamp is written in UTC so that it *looks* inside the period
(UTC trap: 2026-10-31T21:30:00+00:00 is already 1 November in Asia/Almaty)."""

from __future__ import annotations

from datetime import timedelta

from ...timeutil import month_str, offset_minutes
from .base import MIN_AMOUNT, ErrorType, register, special


@register
class PeriodCutoff(ErrorType):
    name = "period_cutoff"
    invariant = "period"

    def applicable(self, book, used):
        out = []
        for inv in book.invoices.values():
            if inv.key in used or special(inv) or not book.is_plain_unpaid(inv):
                continue
            if book.invoice_base(inv) < MIN_AMOUNT:
                continue
            out.append(inv.key)
        return sorted(out)

    def inject(self, book, target, rng, cfg, variant="utc_trap"):
        inv = book.invoices[target]
        s = book.story
        off = offset_minutes(s.tz_name)
        before = [book.snapshot(("inv", target))]
        if off > 0:  # just after the period end: UTC date still looks like the last day
            ts = s.period_end + timedelta(minutes=rng.randint(10, max(11, off - 10)), seconds=rng.randint(0, 59))
        else:  # just before the period start: UTC date already looks like the first day
            ts = s.period_start - timedelta(minutes=rng.randint(10, max(11, -off - 10)), seconds=rng.randint(0, 59))
        inv.issued_at = book.uniq(ts)
        if (off > 0 and inv.issued_at < s.period_end) or (off < 0 and inv.issued_at >= s.period_start):
            return None
        inv.utc_fmt = True
        # The bill is genuinely for the local month it was issued in: service_period follows the new
        # local date, so line items never contradict the cutoff (before/after is in provenance).
        month = month_str(inv.issued_at.astimezone(s.tz).date())
        for li in inv.line_items:
            li["service_period"] = month
        book.post_invoice(inv)
        return self.finish(book, target, variant, [("inv", target)], before)

    def canonical_ids(self, book, target):
        return [book.invoices[target].invoice_id]

    def evidence_sets(self, book, target):
        inv = book.invoices[target]
        o = ("inv", target)
        return [[inv.doc_id, book.row_of(o, "inv_ar").row_id, "policy"],
                [inv.doc_id, book.row_of(o, "inv_rev").row_id, "policy"]]

    def expected_amount(self, book, target, **kw):
        return book.row_of(("inv", target), "inv_ar").debit
