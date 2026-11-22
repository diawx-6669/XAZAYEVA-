"""vat_error: the 'VAT 12%' line of a base-currency invoice is computed at a wrong rate (10 % or 20 %);
the total follows the lines, so the ledger is internally consistent and only the document contradicts
the policy's VAT rule. Amount = |VAT line - round(12 % x net)|.

Variants: `unpaid` (no receipt references the invoice) and, since v1.1, `paid_in_full` - the client paid
the invoice as issued with one receipt that references only this invoice, so that receipt's amount
follows the wrong total too. Without the second variant every VAT error sat on an unpaid invoice
(100 % against 38 % of correct VAT lines): a format tell."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from .base import MIN_AMOUNT, ErrorType, register, special

VAT_DESC = "VAT 12%"
VAT_RATE = Decimal("0.12")


def vat_of(net: int, rate=VAT_RATE) -> int:
    return int((Decimal(net) * rate).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def split_vat(lines):
    vat = [li for li in lines if li["description"] == VAT_DESC]
    net = sum(li["amount_minor"] for li in lines if li["description"] != VAT_DESC)
    return (vat[0] if vat else None), net


@register
class VatError(ErrorType):
    name = "vat_error"
    invariant = "vat"

    def applicable(self, book, used):
        out = []
        for inv in book.invoices.values():
            vat, net = split_vat(inv.line_items)
            if inv.key in used or vat is None or inv.kind != "invoice" or inv.currency != book.base or special(inv):
                continue
            if not (book.is_plain_unpaid(inv) or self.sole_payment(book, inv, used) is not None):
                continue
            if abs(vat_of(net, Decimal("0.20")) - vat["amount_minor"]) >= MIN_AMOUNT:
                out.append(inv.key)
        return sorted(out)

    @staticmethod
    def sole_payment(book, inv, used=()):
        """The one receipt that pays this invoice in full and nothing else (base currency, no refund,
        not cancelled, not already used by another mutation), or None."""
        if inv.kind != "invoice" or inv.key in used:
            return None
        if any(rf.invoice == inv.key for rf in book.refunds) or any(i.cancels == inv.key for i in book.invoices.values()):
            return None
        pays = [p for p in book.payments.values() if p.refs and inv.key in p.refs]
        if len(pays) != 1:
            return None
        p = pays[0]
        if (p.key in used or p.refs != [inv.key] or p.currency != book.base or p.posted_alloc is not None
                or p.cash_rate is not None or p.alloc != [(inv.key, inv.total)] or p.amount != inv.total
                or set(p.tags) - {"split_payment", "partial_open", "multi_invoice_payment"}):
            return None
        return p

    def inject(self, book, target, rng, cfg):
        inv = book.invoices[target]
        pay = None if book.is_plain_unpaid(inv) else self.sole_payment(book, inv)
        owners = [("inv", target)] + ([("pay", pay.key)] if pay else [])
        before = [book.snapshot(o) for o in owners]
        vat, net = split_vat(inv.line_items)
        wrong = rng.choice([Decimal("0.10"), Decimal("0.20")])
        vat["unit_price_minor"] = vat["amount_minor"] = vat_of(net, wrong)
        if abs(vat["amount_minor"] - vat_of(net)) < MIN_AMOUNT:
            return None
        book.post_invoice(inv)
        touched = [target]
        if pay is not None:  # the client paid the invoice as issued
            pay.amount = inv.total
            pay.alloc = [(inv.key, inv.total)]
            book.post_payment(pay)
            touched.append(pay.key)
        variant = f"{'paid_in_full' if pay else 'unpaid'}_rate_{int(wrong * 100)}"
        return self.finish(book, target, variant, owners, before, touched=touched)

    def canonical_ids(self, book, target):
        return [book.invoices[target].invoice_id]

    def evidence_sets(self, book, target):
        return [[book.invoices[target].doc_id, "policy"]]

    def expected_amount(self, book, target, **kw):
        vat, net = split_vat(book.invoices[target].line_items)
        return abs(vat["amount_minor"] - vat_of(net))
