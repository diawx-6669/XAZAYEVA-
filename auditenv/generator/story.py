"""Hidden company story: entities, FX rates and business events (all fictional).

The story is the single source of truth for the clean books: documents and ledger
postings are *derived* from it in books.py. Only the `story` RNG stream is used here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext

from ..ids import make_rng
from ..money import EXPONENTS, convert_minor, quantize_sig, rate_str
from ..timeutil import add_months, is_business_day, month_str, offset_minutes, policy_rate_date, tzinfo_for

CATALOG = [
    "Consulting services", "Software license", "Cloud hosting", "Equipment lease",
    "Maintenance contract", "Logistics services", "Staff training", "Marketing services",
    "Data processing", "Technical support", "Translation services", "Audit preparation",
]
RENT_DESC = "Office rent"

PRICE_MAJOR = {"KZT": (5000, 400000), "USD": (10, 900), "EUR": (10, 800), "JPY": (1500, 130000), "KWD": (3, 280)}
REF_PER_USD = {"USD": "1", "KZT": "480", "EUR": "0.92", "JPY": "150", "KWD": "0.307"}

FEE_MAJOR = {"KZT": (300, 2500), "USD": (1, 8), "EUR": (1, 8), "JPY": (100, 1200), "KWD": (1, 3)}

DISTRACTOR_KINDS = [
    "recurring_rent", "repeat_amount", "split_payment", "multi_invoice_payment", "partial_open",
    "refund", "bank_fee", "rounding_residual", "boundary_time", "credit_note_reissue", "unidentified_receipt",
    "night_fx", "overpayment", "weekend_fx",
]
# Correct look-alikes of each error type (config.min_lookalikes_per_type forces at least N of them into EVERY
# episode, clean or not, so "a look-alike exists" never tells clean from erroneous books).
LOOKALIKES = {
    "duplicate_invoice": ["recurring_rent", "repeat_amount", "credit_note_reissue"],
    "payment_allocation": ["unidentified_receipt", "overpayment", "partial_open", "split_payment"],
    "fx_rate": ["night_fx", "weekend_fx", "rounding_residual"],
    "period_cutoff": ["boundary_time"],
}
NEEDS_FOREIGN = {"night_fx", "weekend_fx", "rounding_residual"}
# Invoices with these tags never get an automatically planned payment.
NO_PAY_TAGS = {"cancelled", "credit_note", "boundary_end", "carrier_pfc", "carrier_dfx"}


@dataclass
class InvoiceEv:
    key: str
    entity: str
    issued_at: datetime
    currency: str
    line_items: list
    kind: str = "invoice"  # "invoice" | "credit_note"
    cancels: str | None = None
    utc_fmt: bool = False
    due_days: int = 30
    tags: list = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(li["amount_minor"] for li in self.line_items)


@dataclass
class PaymentEv:
    key: str
    entity: str | None
    timestamp: datetime
    currency: str
    amount: int
    refs: list | None
    alloc: list  # [(invoice_key, amount in payment currency minor)]
    fee: int = 0
    utc_fmt: bool = False
    tags: list = field(default_factory=list)


@dataclass
class RefundEv:
    key: str
    invoice: str
    entity: str
    timestamp: datetime
    amount: int  # base currency minor
    utc_fmt: bool = False


@dataclass
class Story:
    tz_name: str
    tz: object
    base: str
    foreign: list
    period_start: datetime
    period_end: datetime
    entities: list
    invoices: dict
    payments: dict
    refunds: list
    rates: dict  # (date_iso, currency) -> rate string (units of base per 1 unit)
    utc_share: int
    distractors: list
    used_instants: set

    @property
    def first_day(self) -> date:
        return self.period_start.date()

    @property
    def last_day(self) -> date:
        return (self.period_end - timedelta(days=1)).date()

    def rate_for(self, dt: datetime, cur: str) -> str:
        if cur == self.base:
            return "1"
        d = policy_rate_date(dt.astimezone(self.tz).date())
        return self.rates[(d.isoformat(), cur)]

    def to_base(self, amount: int, cur: str, rate: str) -> int:
        return convert_minor(amount, cur, self.base, rate)


class StoryBuilder:
    def __init__(self, seed, cfg: dict, attempt: int):
        self.r = make_rng(seed, "story", attempt)
        self.cfg = cfg
        self.used = set()
        self.invoices: dict = {}
        self.payments: dict = {}
        self.refunds: list = []

    # ---------------------------------------------------------------- helpers
    def chance(self, p) -> bool:
        return self.r.random() < p

    def uniq(self, dt: datetime) -> datetime:
        while int(dt.timestamp()) in self.used:
            dt = dt + timedelta(minutes=1)
        self.used.add(int(dt.timestamp()))
        return dt

    def utc(self) -> bool:
        return self.r.randrange(100) < self.utc_share

    def rand_dt(self, lo: date, hi: date, h0: int = 9, h1: int = 18) -> datetime:
        if hi < lo:
            hi = lo
        d = lo + timedelta(days=self.r.randint(0, (hi - lo).days))
        return datetime(d.year, d.month, d.day, self.r.randint(h0, h1), self.r.randint(0, 59),
                        self.r.randint(0, 59), tzinfo=self.tz)

    def after(self, dt: datetime, max_days: int = 25):
        lo = dt.astimezone(self.tz).date() + timedelta(days=1)
        if lo > self.last_day:
            return None
        hi = min(lo + timedelta(days=max_days), self.last_day)
        return self.rand_dt(lo, hi)

    def price(self, cur: str) -> int:
        lo, hi = PRICE_MAJOR[cur]
        e = EXPONENTS[cur]
        minor = self.r.randint(lo, hi) * 10 ** e
        if e and self.chance(0.6):
            minor += self.r.randrange(10 ** e)
        return minor

    def lines(self, cur: str, period: str, n: int | None = None) -> list:
        descs = self.r.sample(CATALOG, n or self.r.randint(*self.cfg["line_items"]))
        out = []
        for desc in descs:
            q = self.r.randint(1, 6)
            u = self.price(cur)
            out.append({"description": desc, "service_period": period, "quantity": q,
                        "unit_price_minor": u, "amount_minor": q * u})
        return out

    def night_time(self, d: date) -> datetime:
        """A local time on day d whose UTC calendar date is a different day (needs offset != 0)."""
        off = offset_minutes(self.tz_name)
        midnight = datetime(d.year, d.month, d.day, tzinfo=self.tz)
        if off > 0:
            mins = self.r.randint(10, max(11, off - 10))
        else:
            mins = 24 * 60 + off + self.r.randint(10, max(11, -off - 10))
        return midnight + timedelta(minutes=mins, seconds=self.r.randint(0, 59))

    def add_invoice(self, entity, dt, cur, lines, utc_fmt=None, **kw) -> InvoiceEv:
        key = f"i{len(self.invoices):03d}"
        inv = InvoiceEv(key=key, entity=entity, issued_at=self.uniq(dt), currency=cur, line_items=lines,
                        utc_fmt=self.utc() if utc_fmt is None else utc_fmt,
                        due_days=self.r.choice([14, 30, 45]), **kw)
        self.invoices[key] = inv
        return inv

    def add_payment(self, entity, dt, cur, amount, refs, alloc, utc_fmt=None, tags=None) -> PaymentEv:
        key = f"p{len(self.payments):03d}"
        p = PaymentEv(key=key, entity=entity, timestamp=self.uniq(dt), currency=cur, amount=amount,
                      refs=refs, alloc=alloc, utc_fmt=self.utc() if utc_fmt is None else utc_fmt,
                      tags=list(tags or []))
        self.payments[key] = p
        return p

    def regular_invoice(self, lo: date, hi: date, cur=None, entity=None, tags=None) -> InvoiceEv:
        cur = cur or self.pick_currency()
        dt = self.rand_dt(lo, hi)
        return self.add_invoice(entity or self.r.choice(self.entities), dt, cur,
                                self.lines(cur, month_str(dt.date())), tags=list(tags or []))

    def pick_currency(self) -> str:
        if self.foreign and self.chance(self.cfg["foreign_share"]):
            return self.r.choice(self.foreign)
        return self.base

    # ------------------------------------------------------------------ rates
    def gen_rates(self) -> dict:
        rates = {}
        d0 = self.first_day - timedelta(days=14)
        d1 = self.last_day + timedelta(days=7)
        with localcontext() as ctx:
            ctx.prec = 28
            for cur in self.foreign:
                level = Decimal(REF_PER_USD[self.base]) / Decimal(REF_PER_USD[cur])
                level = level * Decimal(10000 + self.r.randint(-500, 500)) / Decimal(10000)
                d = d0
                while d <= d1:
                    if is_business_day(d):
                        level = level * Decimal(10000 + self.r.randint(-40, 40)) / Decimal(10000)
                        rates[(d.isoformat(), cur)] = rate_str(quantize_sig(level, 6))
                    d += timedelta(days=1)
        return rates

    def rate_for(self, dt, cur):
        if cur == self.base:
            return "1"
        d = policy_rate_date(dt.astimezone(self.tz).date())
        return self.rates[(d.isoformat(), cur)]

    # ------------------------------------------------------------------ build
    def build(self) -> Story:
        cfg, r = self.cfg, self.r
        self.tz_name = r.choice(sorted(cfg["timezones"]))
        self.tz = tzinfo_for(self.tz_name)
        self.base = r.choice(cfg["base_currencies"])
        pool = sorted(c for c in cfg["foreign_currencies"] if c != self.base)
        k = min(r.randint(*cfg["n_foreign"]), len(pool))
        self.foreign = sorted(r.sample(pool, k)) if k > 0 else []
        y, m = (int(x) for x in r.choice(cfg["period_starts"]).split("-"))
        pm = cfg["period_months"]
        months = r.randint(*pm) if isinstance(pm, list) else pm
        self.period_start = datetime(y, m, 1, tzinfo=self.tz)
        self.period_end = add_months(self.period_start, months)
        self.first_day = self.period_start.date()
        self.last_day = (self.period_end - timedelta(days=1)).date()
        self.utc_share = r.randint(*cfg["utc_share"])
        self.entities = [f"e{i:02d}" for i in range(r.randint(*cfg["n_entities"]))]
        self.rates = self.gen_rates()
        present = [k for k in DISTRACTOR_KINDS if self.chance(cfg["distractors"].get(k, 0.0))]
        need = cfg.get("min_lookalikes_per_type", 0)
        for typ in sorted(LOOKALIKES):
            kinds = [k for k in LOOKALIKES[typ] if self.foreign or k not in NEEDS_FOREIGN]
            missing = [k for k in kinds if k not in present]
            r.shuffle(missing)
            while sum(k in present for k in kinds) < min(need, len(kinds)) and missing:
                present.append(missing.pop())
        present = [k for k in DISTRACTOR_KINDS if k in present]  # stable order
        self.present = present

        n_inv = r.randint(*cfg["n_invoices"])
        for _ in range(n_inv):
            self.regular_invoice(self.first_day, self.last_day - timedelta(days=2))

        if "recurring_rent" in present:
            ent = r.choice(self.entities)
            unit = self.price(self.base)
            month = self.period_start
            while month < self.period_end:
                d = month.date()
                while not is_business_day(d):
                    d += timedelta(days=1)
                dt = datetime(d.year, d.month, d.day, 10, r.randint(0, 59), 0, tzinfo=self.tz)
                self.add_invoice(ent, dt, self.base, [{"description": RENT_DESC, "service_period": month_str(d),
                                 "quantity": 1, "unit_price_minor": unit, "amount_minor": unit}],
                                 tags=["recurring_rent"])
                month = add_months(month, 1)

        if "repeat_amount" in present:
            src = r.choice([i for i in self.invoices.values() if not i.tags])
            others = [e for e in self.entities if e != src.entity]
            if others:  # a repeat for the SAME client would be a real duplicate, not a distractor
                other = r.choice(others)
                dt = self.rand_dt(self.first_day, self.last_day - timedelta(days=2))
                lines = [dict(li, service_period=month_str(dt.date())) for li in src.line_items]  # same amounts, own month
                self.add_invoice(other, dt, src.currency, lines, tags=["repeat_amount"])
            else:
                present.remove("repeat_amount")

        if "credit_note_reissue" in present:
            mid = self.first_day + (self.last_day - self.first_day) // 2
            cn_cur = r.choice(self.foreign) if self.foreign and self.chance(0.5) else self.base
            x = self.regular_invoice(self.first_day, mid, cur=cn_cur, tags=["cancelled"])
            cn_dt = x.issued_at + timedelta(days=r.randint(1, 3), hours=r.randint(0, 5))
            cn_lines = [{"description": li["description"], "service_period": li["service_period"],
                         "quantity": li["quantity"], "unit_price_minor": -li["unit_price_minor"],
                         "amount_minor": -li["amount_minor"]} for li in x.line_items]
            cn = self.add_invoice(x.entity, cn_dt, cn_cur, cn_lines, kind="credit_note", cancels=x.key,
                                  tags=["credit_note"])
            re_dt = cn.issued_at + timedelta(hours=r.randint(1, 30))
            self.add_invoice(x.entity, re_dt, cn_cur, [dict(li) for li in x.line_items], tags=["reissue"])

        if "night_fx" in present and self.foreign:
            # Correct foreign document at local night: the UTC calendar date differs from the local one, the
            # posting uses the LOCAL date rate. A UTC-date reader would wrongly call it an fx_rate error.
            for _ in range(r.randint(1, 2)):
                cur = r.choice(self.foreign)
                d = self.first_day + timedelta(days=r.randint(1, max(1, (self.last_day - self.first_day).days - 3)))
                self.add_invoice(r.choice(self.entities), self.night_time(d), cur, self.lines(cur, month_str(d)),
                                 utc_fmt=True, tags=["night_fx"])

        if "weekend_fx" in present and self.foreign:
            # Foreign document dated on a weekend: no rate for that date, previous_business_day applies.
            d = self.first_day + timedelta(days=r.randint(0, max(0, (self.last_day - self.first_day).days - 3)))
            while is_business_day(d):
                d += timedelta(days=1)
            if d <= self.last_day - timedelta(days=2):
                cur = r.choice(self.foreign)
                dt = datetime(d.year, d.month, d.day, r.randint(9, 18), r.randint(0, 59), r.randint(0, 59), tzinfo=self.tz)
                self.add_invoice(r.choice(self.entities), dt, cur, self.lines(cur, month_str(d)), tags=["weekend_fx"])

        if "boundary_time" in present:
            ld = self.last_day
            dt = datetime(ld.year, ld.month, ld.day, 23, 50, 0, tzinfo=self.tz) + timedelta(minutes=r.randint(0, 4))
            self.add_invoice(r.choice(self.entities), dt, self.base, self.lines(self.base, month_str(ld)),
                             utc_fmt=True, tags=["boundary_end"])
            fd = self.first_day
            dt = datetime(fd.year, fd.month, fd.day, 0, 5, 0, tzinfo=self.tz) + timedelta(minutes=r.randint(0, 15))
            self.add_invoice(r.choice(self.entities), dt, self.base, self.lines(self.base, month_str(fd)),
                             utc_fmt=True, tags=["boundary_start"])

        # Carriers: clean set-ups that interaction scenarios can later corrupt.
        if self.foreign and cfg["interactions"].get("partial_fx_cutoff", 0) > 0:
            cur = r.choice(self.foreign)
            inv = self.regular_invoice(self.first_day, self.last_day - timedelta(days=10), cur=cur,
                                       tags=["carrier_pfc"])
            off = offset_minutes(self.tz_name)
            ld = self.last_day
            midnight = datetime(ld.year, ld.month, ld.day, tzinfo=self.tz)
            if off > 0:
                mins = r.randint(10, off - 10)
            else:
                mins = 24 * 60 + off + r.randint(10, -off - 10)
            mins = min(mins, 24 * 60 - 1)
            self.add_payment(inv.entity, midnight + timedelta(minutes=mins), cur, inv.total, [inv.key],
                             [(inv.key, inv.total)], utc_fmt=True, tags=["carrier_pfc"])
        if self.foreign and cfg["interactions"].get("duplicate_fx", 0) > 0:
            self.regular_invoice(self.first_day, self.last_day - timedelta(days=5), cur=r.choice(self.foreign),
                                 tags=["carrier_dfx"])

        self.plan_payments(present)

        if "unidentified_receipt" in present:
            dt = self.rand_dt(self.first_day, self.last_day)
            amt = self.price(self.base) * r.randint(1, 3)
            self.add_payment(None, dt, self.base, amt, None, [], tags=["unidentified_receipt"])

        if "bank_fee" in present:
            pays = [p for p in self.payments.values() if p.refs]
            got = False
            lo, hi = FEE_MAJOR[self.base]
            for p in pays:
                if self.chance(0.3):
                    p.fee = r.randint(lo, hi) * 10 ** EXPONENTS[self.base]
                    got = True
            if pays and not got:
                r.choice(pays).fee = r.randint(lo, hi) * 10 ** EXPONENTS[self.base]

        if "refund" in present:
            self.plan_refunds()

        return Story(tz_name=self.tz_name, tz=self.tz, base=self.base, foreign=self.foreign,
                     period_start=self.period_start, period_end=self.period_end, entities=self.entities,
                     invoices=self.invoices, payments=self.payments, refunds=self.refunds, rates=self.rates,
                     utc_share=self.utc_share, distractors=present, used_instants=self.used)

    def plan_payments(self, present):
        r = self.r
        elig = [i for i in self.invoices.values() if i.kind == "invoice" and not (set(i.tags) & NO_PAY_TAGS)]
        r.shuffle(elig)
        planned = set()

        def take(pred):
            for inv in elig:
                if inv.key not in planned and pred(inv):
                    planned.add(inv.key)
                    return inv
            return None

        def pay(inv_list, amount, ts, tags):
            refs = [i.key for i in inv_list]
            if len(inv_list) == 1:
                alloc = [(inv_list[0].key, amount)]
            else:
                alloc = [(i.key, i.total) for i in inv_list]
            return self.add_payment(inv_list[0].entity, ts, inv_list[0].currency, amount, refs, alloc, tags=tags)

        if "multi_invoice_payment" in present:
            groups = {}
            for inv in elig:
                groups.setdefault((inv.entity, inv.currency), []).append(inv)
            for gk in sorted(groups):
                invs = sorted(groups[gk], key=lambda i: i.issued_at)
                if len(invs) >= 2:
                    chosen = invs[: r.randint(2, min(3, len(invs)))]
                    ts = self.after(max(i.issued_at for i in chosen))
                    if ts is None:
                        continue
                    planned.update(i.key for i in chosen)
                    pay(chosen, sum(i.total for i in chosen), ts, ["multi_invoice_payment"])
                    break

        if "split_payment" in present:
            for _ in range(r.randint(1, 2)):
                inv = take(lambda i: True)
                if inv is None:
                    break
                t1 = self.after(inv.issued_at, 12)
                if t1 is None:
                    continue
                p1 = inv.total * r.randint(30, 70) // 100
                pay([inv], p1, t1, ["split_payment"])
                t2 = self.after(t1, 12)
                if t2 is not None:
                    pay([inv], inv.total - p1, t2, ["split_payment"])

        if "rounding_residual" in present and self.foreign:
            inv = take(lambda i: i.currency != self.base)
            if inv is not None:
                rate = self.rate_for(inv.issued_at, inv.currency)
                full = convert_minor(inv.total, inv.currency, self.base, rate)
                ks = list(range(25, 76))
                r.shuffle(ks)
                for k in ks:
                    p1 = inv.total * k // 100
                    p2 = inv.total - p1
                    if p1 <= 0 or p2 <= 0:
                        continue
                    res = (convert_minor(p1, inv.currency, self.base, rate)
                           + convert_minor(p2, inv.currency, self.base, rate) - full)
                    if res != 0:
                        t1 = self.after(inv.issued_at, 10)
                        t2 = self.after(t1, 10) if t1 else None
                        if t1 and t2:
                            pay([inv], p1, t1, ["rounding_residual"])
                            pay([inv], p2, t2, ["rounding_residual"])
                        break

        if "overpayment" in present:
            # The client pays more than the invoice: the invoice is closed, the excess legitimately sits on 2400.
            inv = take(lambda i: True)
            if inv is not None:
                ts = self.after(inv.issued_at)
                if ts is not None:
                    extra = max(1, inv.total * r.randint(5, 30) // 100)
                    self.add_payment(inv.entity, ts, inv.currency, inv.total + extra, [inv.key], [(inv.key, inv.total)],
                                     tags=["overpayment"])

        if "partial_open" in present:
            for _ in range(r.randint(1, 2)):
                inv = take(lambda i: True)
                if inv is None:
                    break
                ts = self.after(inv.issued_at)
                if ts is not None:
                    pay([inv], max(1, inv.total * r.randint(30, 80) // 100), ts, ["partial_open"])

        if "boundary_time" in present:
            inv = take(lambda i: i.currency == self.base)
            if inv is not None:
                ld = self.last_day
                ts = datetime(ld.year, ld.month, ld.day, 23, 40, 0, tzinfo=self.tz) + timedelta(minutes=r.randint(0, 9))
                p = pay([inv], inv.total, ts, ["boundary_time"])
                p.utc_fmt = True

        for inv in elig:
            if inv.key in planned:
                continue
            if self.chance(0.55):
                ts = self.after(inv.issued_at)
                if ts is not None:
                    pay([inv], inv.total, ts, [])

    def plan_refunds(self):
        r = self.r
        paid = {}
        for p in self.payments.values():
            for k, a in p.alloc:
                paid.setdefault(k, []).append((p.timestamp, a))
        cands = [self.invoices[k] for k in sorted(paid)
                 if self.invoices[k].currency == self.base and sum(a for _, a in paid[k]) == self.invoices[k].total]
        r.shuffle(cands)
        for inv in cands[: r.randint(1, 2)]:
            last = max(t for t, _ in paid[inv.key])
            ts = self.after(last, 5)
            if ts is None:
                continue
            key = f"r{len(self.refunds):03d}"
            self.refunds.append(RefundEv(key, inv.key, inv.entity, self.uniq(ts),
                                         max(1, inv.total * r.randint(10, 40) // 100), utc_fmt=self.utc()))


def build_story(seed, cfg: dict, attempt: int = 0) -> Story:
    return StoryBuilder(seed, cfg, attempt).build()
