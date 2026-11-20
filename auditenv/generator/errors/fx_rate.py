"""fx_rate: a foreign-currency document posted with the wrong rate.

Variants (rate actually used instead of the policy rate of the LOCAL transaction date):
  adjacent_day     the neighbouring business day
  utc_date         the rate of the UTC calendar date (a night document in a non-UTC zone)
  inverted         1/rate
  historical_rate  a receipt converted at its invoice's rate (so no 7900 line appears)
  wrong_pair       another foreign currency's rate for the same date
  due_date         an invoice converted at the rate of its due date
Paid invoices are valid targets: Accounts Receivable is relieved at the correct invoice-date rate,
so only the invoice posting itself differs (one invariant, one amount).
"""

from __future__ import annotations

from datetime import timezone

from ...money import invert_rate
from ...timeutil import next_business_day, policy_rate_date, prev_business_day
from .base import MIN_AMOUNT, ErrorType, register, special, weighted_choice, with_revenue_alternative

ALLOW_INV = ("reissue", "repeat_amount", "night_fx", "weekend_fx")
ALLOW_PAY = ("rounding_residual", "overpayment")


@register
class FxRate(ErrorType):
    name = "fx_rate"
    invariant = "fx_conversion"

    def applicable(self, book, used):
        out = []
        cancelled = {i.cancels for i in book.invoices.values() if i.cancels}
        for inv in book.invoices.values():
            if inv.key in used or inv.currency == book.base or inv.kind != "invoice" or inv.key in cancelled:
                continue
            if special(inv, ALLOW_INV):
                continue
            out.append(f"inv:{inv.key}")
        for p in book.payments.values():
            if p.key in used or p.currency == book.base or special(p, ALLOW_PAY):
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

    def _rate(self, book, d, cur):
        return book.story.rates.get((d.isoformat(), cur))

    def wrong_rates(self, book, target) -> dict:
        kind, key, doc, ts, cur, amount = self._doc(book, target)
        good_d = book.rate_date(ts)
        good = book.rate_on(good_d, cur)
        correct = book.to_base(amount, cur, good)
        cands = {}

        def offer(name, rate):
            if rate is not None and rate != good and abs(book.to_base(amount, cur, rate) - correct) >= MIN_AMOUNT:
                cands.setdefault(name, rate)

        for d in (prev_business_day(good_d), next_business_day(good_d)):
            offer("adjacent_day", self._rate(book, d, cur))
        utc_d = policy_rate_date(ts.astimezone(timezone.utc).date())
        if utc_d != good_d:
            offer("utc_date", self._rate(book, utc_d, cur))
        offer("inverted", invert_rate(good))
        if kind == "pay" and doc.refs and len(doc.refs) == 1:
            inv = book.invoices[doc.refs[0]]
            if inv.currency == cur and book.rate_date(inv.issued_at) != good_d:
                offer("historical_rate", self._rate(book, book.rate_date(inv.issued_at), cur))
        for other in sorted(c for c in book.story.foreign if c != cur):
            offer("wrong_pair", self._rate(book, good_d, other))
        if kind == "inv":
            due_d = policy_rate_date(doc.due_at.astimezone(book.tz).date())
            if due_d != good_d:
                offer("due_date", self._rate(book, due_d, cur))
        return cands

    def inject(self, book, target, rng, cfg, prefer=None, exclude=()):
        kind, key, doc, _, _, _ = self._doc(book, target)
        cands = {k: v for k, v in self.wrong_rates(book, target).items() if k not in exclude}
        if not cands:
            return None
        variant = prefer if prefer in cands else weighted_choice(rng, cfg["fx_variants"], allowed=set(cands))
        if variant is None and exclude:  # configured weights allow none of the remaining variants
            variant = weighted_choice(rng, {k: 1 for k in cands})
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
        paid = kind == "inv" and bool(book.allocations_to(key))
        return self.finish(book, target, variant, [owner], before, touched=[key], detail={"paid": paid} if paid else {})

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
        sets = [[doc.doc_id, book.row_of((kind, key), "pay_cash").row_id, fxid, "policy"]]
        # Alternative for a receipt: the other side of the cash line. Cash posted = credits to 1200 and
        # 2400 plus the 7900 difference, so 1200 (+2400) (+7900) rows replace the 1000 row.
        other = [r.row_id for r in book.rows_of((kind, key))
                 if r.role.startswith("pay_ar:") or r.role in ("pay_unapplied", "pay_fx")]
        if other and len(other) + 3 <= 6:
            sets.append([doc.doc_id] + other + [fxid, "policy"])
        return sets

    def expected_amount(self, book, target, **kw):
        kind, key, doc, ts, cur, amount = self._doc(book, target)
        posted = book.row_of((kind, key), self._primary_role(kind)).debit
        return abs(posted - book.to_base(amount, cur, book.correct_rate(ts, cur)))
