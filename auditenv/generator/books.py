"""Story -> documents and double-entry ledger (the clean book).

Each document "owns" a set of ledger rows with internal roles. Re-posting a document
(used by error mutations) regenerates its rows from the same posting rules with
explicit overrides, keeping row IDs for roles that survive. Roles never leave the
generator: they are not exported.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime

from ..ids import IdFactory, make_rng
from ..money import convert_minor
from ..timeutil import fmt_ts, policy_rate_date

ACCOUNTS = {
    "1000": "Cash",
    "1200": "Accounts Receivable",
    "2400": "Unapplied Cash",
    "4000": "Revenue",
    "4100": "Refunds",
    "6500": "Bank Fees",
    "7900": "FX Gain/Loss",
}


@dataclass
class InvoiceDoc:
    key: str
    doc_id: str
    invoice_id: str
    entity_id: str
    issued_at: datetime
    due_days: int
    currency: str
    line_items: list
    kind: str
    cancels: str | None
    utc_fmt: bool
    tags: list
    posted_rate: str | None = None  # set only by an fx_rate mutation
    posted_base: int | None = None  # set only by a duplicate copied "as posted"
    posted_at: datetime | None = None  # set only by period_cutoff/backdated_posting: ledger date != document date

    @property
    def total(self) -> int:
        return sum(li["amount_minor"] for li in self.line_items)

    @property
    def due_at(self) -> datetime:
        from datetime import timedelta

        return self.issued_at + timedelta(days=self.due_days)


@dataclass
class PaymentDoc:
    key: str
    doc_id: str
    payment_id: str
    entity_id: str | None
    timestamp: datetime
    currency: str
    amount: int
    refs: list | None
    alloc: list
    fee: int
    utc_fmt: bool
    tags: list
    cash_rate: str | None = None  # set only by an fx_rate mutation
    posted_alloc: list | None = None  # set only by a payment_allocation mutation


@dataclass
class RefundRec:
    key: str
    invoice: str
    entity_id: str
    timestamp: datetime
    amount: int
    utc_fmt: bool


@dataclass
class Row:
    row_id: str
    ts: datetime
    utc_fmt: bool
    account: str
    debit: int
    credit: int
    entity_id: str | None
    invoice_key: str | None
    payment_key: str | None
    role: str
    owner: tuple


def split_by_lines(total: int, weights: list) -> list:
    """Split an integer base amount across line items proportionally (largest remainder,
    ties -> lower index). Exact: sum(parts) == total. Equal to the line amounts when the
    document is already in base currency (total == sum(weights))."""
    w = sum(weights)
    if w == 0:
        return [total] + [0] * (len(weights) - 1)
    base = [total * x // w for x in weights]
    rem = total - sum(base)
    order = sorted(range(len(weights)), key=lambda i: (-(total * weights[i] % w), i))
    for i in order[:rem]:
        base[i] += 1
    return base


class Book:
    def __init__(self, story, ids: IdFactory, episode_id: str):
        self.story = story
        self.ids = ids
        self.episode_id = episode_id
        self.base = story.base
        self.tz = story.tz
        self.invoices: dict = {}
        self.payments: dict = {}
        self.refunds: list = []
        self.rows: dict = {}
        self.owner_rows: dict = {}
        self.used_instants = story.used_instants

    # ------------------------------------------------------------------ rates
    def rate_date(self, dt: datetime):
        return policy_rate_date(dt.astimezone(self.tz).date())

    def rate_on(self, d, cur) -> str:
        if cur == self.base:
            return "1"
        return self.story.rates[(d.isoformat(), cur)]

    def correct_rate(self, dt: datetime, cur: str) -> str:
        return self.rate_on(self.rate_date(dt), cur)

    def to_base(self, amount: int, cur: str, rate: str) -> int:
        return convert_minor(amount, cur, self.base, rate)

    def uniq(self, dt: datetime) -> datetime:
        from datetime import timedelta

        while int(dt.timestamp()) in self.used_instants:
            dt = dt + timedelta(minutes=1)
        self.used_instants.add(int(dt.timestamp()))
        return dt

    # ---------------------------------------------------------------- posting
    def post(self, owner: tuple, ts, utc_fmt, entity_id, specs):
        """specs: list of (role, account, debit, credit, invoice_key, payment_key)."""
        old = {self.rows[rid].role: rid for rid in self.owner_rows.get(owner, [])}
        new_ids = []
        for role, account, dr, cr, inv_key, pay_key in specs:
            rid = old.pop(role, None) or self.ids.new("row")
            self.rows[rid] = Row(rid, ts, utc_fmt, account, dr, cr, entity_id, inv_key, pay_key, role, owner)
            new_ids.append(rid)
        for rid in old.values():
            del self.rows[rid]
        self.owner_rows[owner] = new_ids

    def invoice_base(self, inv: InvoiceDoc, rate=None) -> int:
        return self.to_base(abs(inv.total), inv.currency, rate or self.correct_rate(inv.issued_at, inv.currency))

    def post_invoice(self, inv: InvoiceDoc):
        """Dr 1200 for the document total; Cr 4000 once per line item (credit note: reversed)."""
        amt = inv.posted_base if inv.posted_base is not None else self.invoice_base(inv, inv.posted_rate)
        k = inv.key
        parts = split_by_lines(amt, [abs(li["amount_minor"]) for li in inv.line_items])
        if inv.kind == "credit_note":
            specs = [(f"cn_rev:{i}", "4000", p, 0, k, None) for i, p in enumerate(parts)]
            specs.append(("cn_ar", "1200", 0, amt, k, None))
        else:
            specs = [("inv_ar", "1200", amt, 0, k, None)]
            specs += [(f"inv_rev:{i}", "4000", 0, p, k, None) for i, p in enumerate(parts)]
        ts = inv.posted_at or inv.issued_at  # posted_at: only period_cutoff/backdated_posting
        self.post(("inv", k), ts, inv.utc_fmt, inv.entity_id, specs)

    def post_payment(self, p: PaymentDoc):
        alloc = p.alloc if p.posted_alloc is None else p.posted_alloc
        rate = p.cash_rate or self.correct_rate(p.timestamp, p.currency)
        cash = self.to_base(p.amount, p.currency, rate)
        k = p.key
        specs = [("pay_cash", "1000", cash, 0, None, k)]
        ar_total = 0
        for inv_key, a in alloc:
            inv = self.invoices[inv_key]
            ar = self.to_base(a, p.currency, self.correct_rate(inv.issued_at, inv.currency))
            specs.append((f"pay_ar:{inv_key}", "1200", 0, ar, inv_key, k))
            ar_total += ar
        allocated = sum(a for _, a in alloc)
        un_doc = p.amount - allocated
        un_base = 0
        if un_doc > 0:
            # Unapplied part at the payment's POLICY rate: a wrong cash rate (fx_rate) then shows up only
            # in 1000/7900, so an allocation error and an fx error on one receipt have independent amounts.
            good = self.correct_rate(p.timestamp, p.currency)
            un_base = cash if allocated == 0 else self.to_base(un_doc, p.currency, good)
            specs.append(("pay_unapplied", "2400", 0, un_base, None, k))
        fx = cash - ar_total - un_base
        if fx > 0:
            specs.append(("pay_fx", "7900", 0, fx, None, k))
        elif fx < 0:
            specs.append(("pay_fx", "7900", -fx, 0, None, k))
        if p.fee:
            specs.append(("fee_exp", "6500", p.fee, 0, None, k))
            specs.append(("fee_cash", "1000", 0, p.fee, None, k))
        self.post(("pay", k), p.timestamp, p.utc_fmt, p.entity_id, specs)

    def post_refund(self, rf: RefundRec):
        specs = [("ref_exp", "4100", rf.amount, 0, rf.invoice, None), ("ref_cash", "1000", 0, rf.amount, rf.invoice, None)]
        self.post(("ref", rf.key), rf.timestamp, rf.utc_fmt, rf.entity_id, specs)

    def post_all(self):
        for inv in self.invoices.values():
            self.post_invoice(inv)
        for p in self.payments.values():
            self.post_payment(p)
        for rf in self.refunds:
            self.post_refund(rf)

    # ---------------------------------------------------------------- queries
    def row_of(self, owner: tuple, role: str) -> Row:
        for rid in self.owner_rows[owner]:
            if self.rows[rid].role == role:
                return self.rows[rid]
        raise KeyError(role)

    def rows_of(self, owner: tuple) -> list:
        return [self.rows[rid] for rid in self.owner_rows.get(owner, [])]

    def allocations_to(self, inv_key: str) -> list:
        return [p for p in self.payments.values() if any(k == inv_key for k, _ in p.alloc)]

    def referenced_by(self, inv_key: str) -> list:
        return [p for p in self.payments.values() if p.refs and inv_key in p.refs]

    def is_plain_unpaid(self, inv: InvoiceDoc) -> bool:
        return (inv.kind == "invoice" and not self.referenced_by(inv.key)
                and not any(rf.invoice == inv.key for rf in self.refunds)
                and not any(i.cancels == inv.key for i in self.invoices.values()))

    # -------------------------------------------------------------- snapshots
    def inv_public(self, inv: InvoiceDoc) -> dict:
        lines = copy.deepcopy(inv.line_items)
        if inv.cancels:  # a credit note names the cancelled invoice inside each of its lines
            for li in lines:
                li["cancels_invoice_id"] = self.invoices[inv.cancels].invoice_id
        return {
            "doc_id": inv.doc_id,
            "invoice_id": inv.invoice_id,
            "entity_id": inv.entity_id,
            "issued_at": fmt_ts(inv.issued_at, inv.utc_fmt),
            "due_at": fmt_ts(inv.due_at, inv.utc_fmt),
            "currency": inv.currency,
            "total_minor": inv.total,
            "line_items": lines,
        }

    def pay_public(self, p: PaymentDoc) -> dict:
        return {
            "doc_id": p.doc_id,
            "payment_id": p.payment_id,
            "timestamp": fmt_ts(p.timestamp, p.utc_fmt),
            "currency": p.currency,
            "amount_minor": p.amount,
            "invoice_refs": [self.invoices[k].invoice_id for k in p.refs] if p.refs is not None else None,
        }

    def row_public(self, row: Row) -> dict:
        return {
            "row_id": row.row_id,
            "timestamp": fmt_ts(row.ts, row.utc_fmt),
            "account": row.account,
            "debit_minor": row.debit,
            "credit_minor": row.credit,
            "currency": self.base,
            "entity_id": row.entity_id,
            "invoice_id": self.invoices[row.invoice_key].invoice_id if row.invoice_key else None,
            "payment_id": self.payments[row.payment_key].payment_id if row.payment_key else None,
        }

    def snapshot(self, owner: tuple) -> dict:
        kind, key = owner
        doc = None
        if kind == "inv" and key in self.invoices:
            doc = self.inv_public(self.invoices[key])
        elif kind == "pay" and key in self.payments:
            doc = self.pay_public(self.payments[key])
        return {"document": doc, "rows": [self.row_public(r) for r in self.rows_of(owner)]}


def build_book(story, seed, attempt: int = 0) -> Book:
    ids = IdFactory(make_rng(seed, "naming", attempt))
    episode_id = ids.episode_id()
    book = Book(story, ids, episode_id)
    ent = {e: ids.new("entity") for e in story.entities}
    for inv in story.invoices.values():
        book.invoices[inv.key] = InvoiceDoc(
            key=inv.key, doc_id=ids.new("doc"), invoice_id=ids.new("invoice"), entity_id=ent[inv.entity],
            issued_at=inv.issued_at, due_days=inv.due_days, currency=inv.currency,
            line_items=copy.deepcopy(inv.line_items), kind=inv.kind, cancels=inv.cancels, utc_fmt=inv.utc_fmt,
            tags=list(inv.tags))
    for p in story.payments.values():
        book.payments[p.key] = PaymentDoc(
            key=p.key, doc_id=ids.new("doc"), payment_id=ids.new("payment"),
            entity_id=ent[p.entity] if p.entity else None, timestamp=p.timestamp, currency=p.currency,
            amount=p.amount, refs=list(p.refs) if p.refs is not None else None, alloc=list(p.alloc), fee=p.fee,
            utc_fmt=p.utc_fmt, tags=list(p.tags))
    for rf in story.refunds:
        book.refunds.append(RefundRec(rf.key, rf.invoice, ent[rf.entity], rf.timestamp, rf.amount, rf.utc_fmt))
    book.post_all()
    return book
