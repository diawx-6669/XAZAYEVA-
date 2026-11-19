"""fx_rate: a foreign-currency document posted with the wrong rate:
adjacent_day (neighbouring business day), utc_date (rate of the UTC calendar date instead of
the local one) or inverted (1/rate)."""

from __future__ import annotations

from datetime import timezone

from ...money import invert_rate
from ...timeutil import next_business_day, policy_rate_date, prev_business_day
from .base import MIN_AMOUNT, ErrorType, register, special, weighted_choice, with_revenue_alternative


@register
class FxRate(ErrorType):
    name = "fx_rate"
    invariant = "fx_conversion"

    def applicable(self, book, used):
        out = []
        for inv in book.invoices.values():
            if inv.key in used or inv.currency == book.base or special(inv) or not book.is_plain_unpaid(inv):
                continue
            out.append(f"inv:{inv.key}")
        for p in book.payments.values():
            if p.key in used or p.currency == book.base or special(p):
                continue
            out.append(f"pay:{p.key}")
        return sorted(out)

    # -------------------------------------------------------------- helpers
    def _doc(self, book, target):
        kind, key = target.split(":", 1)
        if kind == "inv":
            inv = book.invoices[key]
            return kind, key, inv, inv.issued_at, inv.currency, abs(inv.total)
        p = book.payments[key]
        return kind, key, p, p.timestamp, p.currency, p.amount

    def wrong_rates(self, book, target) -> dict:
        _, _, _, ts, cur, amount = self._doc(book, target)
        good_d = book.rate_date(ts)
        good = book.rate_on(good_d, cur)
        correct = book.to_base(amount, cur, good)
        cands = {}
        for d in (prev_business_day(good_d), next_business_day(good_d)):
            rate = book.rate_on(d, cur)
            if abs(book.to_base(amount, cur, rate) - correct) >= MIN_AMOUNT:
                cands.setdefault("adjacent_day", rate)
        utc_d = policy_rate_date(ts.astimezone(timezone.utc).date())
        if utc_d != good_d:
            rate = book.rate_on(utc_d, cur)
            if abs(book.to_base(amount, cur, rate) - correct) >= MIN_AMOUNT:
                cands["utc_date"] = rate
        inv_rate = invert_rate(good)
        if abs(book.to_base(amount, cur, inv_rate) - correct) >= MIN_AMOUNT:
            cands["inverted"] = inv_rate
        return cands

    def inject(self, book, target, rng, cfg, prefer=None):
        kind, key, doc, _, _, _ = self._doc(book, target)
        cands = self.wrong_rates(book, target)
        if not cands:
            return None
        variant = prefer if prefer in cands else weighted_choice(rng, cfg["fx_variants"], allowed=set(cands))
        if variant is None:
            variant = sorted(cands)[0]
        rate = cands[variant]
        owner = (kind, key)
        before = [book.snapshot(owner)]
        if kind == "inv":
            doc.posted_rate = rate
            book.post_invoice(doc)
        else:
            doc.cash_rate = rate
            book.post_payment(doc)
        return self.finish(book, target, variant, [owner], before)

    def canonical_ids(self, book, target):
        kind, key, doc, *_ = self._doc(book, target)
        return [doc.invoice_id if kind == "inv" else doc.payment_id]

    def _primary_role(self, kind):
        return "inv_ar" if kind == "inv" else "pay_cash"

    def evidence_sets(self, book, target):
        kind, key, doc, ts, cur, _ = self._doc(book, target)
        fxid = f"fx:{book.rate_date(ts).isoformat()}:{cur}:{book.base}"
        if kind == "inv":
            return with_revenue_alternative(book, (kind, key), [doc.doc_id], [fxid, "policy"])
        return [[doc.doc_id, book.row_of((kind, key), "pay_cash").row_id, fxid, "policy"]]

    def expected_amount(self, book, target, **kw):
        kind, key, doc, ts, cur, amount = self._doc(book, target)
        posted = book.row_of((kind, key), self._primary_role(kind)).debit
        return abs(posted - book.to_base(amount, cur, book.correct_rate(ts, cur)))
