"""period_cutoff: an invoice that belongs to ANOTHER period (by its LOCAL issue date, the policy's
recognition date) is posted in this period's ledger.

Variants:
  utc_trap           issued just after the period end (or just before its start, for negative UTC
                     offsets) and written in UTC so the UTC date LOOKS inside the period
                     (2026-10-31T21:30:00+00:00 is already 1 November in Asia/Almaty);
  backdated_posting  the document is dated the 2nd of the next month, but its ledger rows are dated
                     the last day of this period: the ledger looks fine, the document does not;
  prior_period       issued a few days before the period start (no UTC trick). Base-currency invoices
                     that were PAID inside the period may get this variant: the receipt is real and
                     correct, only the invoice belongs to the previous period.
Line items' service_period always follows the new local issue month (before/after in provenance).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ...timeutil import is_business_day, month_str, offset_minutes
from .base import MIN_AMOUNT, ErrorType, register, special, weighted_choice, with_revenue_alternative

ALLOW = ("repeat_amount", "reissue", "weekend_fx")


@register
class PeriodCutoff(ErrorType):
    name = "period_cutoff"
    invariant = "period"

    def _paid_simply(self, book, inv) -> bool:
        pays = book.allocations_to(inv.key)
        return bool(pays) and inv.currency == book.base and all(p.refs == [inv.key] for p in pays)

    def applicable(self, book, used):
        out = []
        cancelled = {i.cancels for i in book.invoices.values() if i.cancels}
        for inv in book.invoices.values():
            if inv.key in used or special(inv, ALLOW) or inv.kind != "invoice" or inv.key in cancelled:
                continue
            if any(rf.invoice == inv.key for rf in book.refunds):
                continue
            if not (book.is_plain_unpaid(inv) or self._paid_simply(book, inv)):
                continue
            if book.invoice_base(inv) < MIN_AMOUNT:
                continue
            out.append(inv.key)
        return sorted(out)

    def _business_time(self, d, rng, tz):
        return datetime(d.year, d.month, d.day, rng.randint(9, 18), rng.randint(0, 59), rng.randint(0, 59), tzinfo=tz)

    def inject(self, book, target, rng, cfg, variant=None):
        inv = book.invoices[target]
        s = book.story
        off = offset_minutes(s.tz_name)
        paid = bool(book.allocations_to(target))
        if paid:
            variant = "prior_period"  # a receipt inside the period must come after the invoice
        elif variant is None:
            variant = weighted_choice(rng, cfg.get("cutoff_variants", {"utc_trap": 1.0})) or "utc_trap"
        before = [book.snapshot(("inv", target))]
        if variant == "utc_trap":
            if off > 0:  # just after the period end: UTC date still looks like the last day
                ts = s.period_end + timedelta(minutes=rng.randint(10, max(11, off - 10)), seconds=rng.randint(0, 59))
            else:  # just before the period start: UTC date already looks like the first day
                ts = s.period_start - timedelta(minutes=rng.randint(10, max(11, -off - 10)), seconds=rng.randint(0, 59))
            inv.issued_at = book.uniq(ts)
            if (off > 0 and inv.issued_at < s.period_end) or (off < 0 and inv.issued_at >= s.period_start):
                return None
            inv.utc_fmt = True
        elif variant == "backdated_posting":
            nd = s.period_end.date() + timedelta(days=1)  # the 2nd of the month after the period
            inv.issued_at = book.uniq(self._business_time(nd, rng, s.tz))
            ld = s.last_day
            inv.posted_at = book.uniq(self._business_time(ld, rng, s.tz))
        elif variant == "prior_period":
            d = s.first_day - timedelta(days=rng.randint(1, 5))
            if inv.currency != book.base:
                while not is_business_day(d):  # keep an exact-date rate for a foreign invoice
                    d -= timedelta(days=1)
            inv.issued_at = book.uniq(self._business_time(d, rng, s.tz))
        else:
            return None
        # The bill is genuinely for the local month it was issued in: service_period follows the new
        # local date, so line items never contradict the cutoff (before/after is in provenance).
        month = month_str(inv.issued_at.astimezone(s.tz).date())
        for li in inv.line_items:
            li["service_period"] = month
        book.post_invoice(inv)
        for p in book.allocations_to(target):  # base currency: AR relief unchanged, re-post for consistency
            book.post_payment(p)
        return self.finish(book, target, variant, [("inv", target)], before, touched=[target],
                           detail={"paid_in_period": True} if paid else {})

    def canonical_ids(self, book, target):
        return [book.invoices[target].invoice_id]

    def evidence_sets(self, book, target):
        inv = book.invoices[target]
        return with_revenue_alternative(book, ("inv", target), [inv.doc_id], ["policy"])

    def expected_amount(self, book, target, **kw):
        return book.row_of(("inv", target), "inv_ar").debit
