"""Interacting-error scenarios. Each applies two mutations in a fixed order; the amount of
each issue is measured against the state right before *its own* mutation.

partial_fx_cutoff: a foreign-currency receipt on the last day of the period (local early
  morning / late evening, written in UTC so the UTC date differs) is posted at the wrong
  rate (the UTC-date rate, else an adjacent business day; never inverted) AND applied only
  partially. The two amounts are independent: fx = |Dr 1000 - correct cash| and allocation =
  Cr 2400, where the unapplied part is always converted at the payment's POLICY rate.
  -> fx_rate[payment_id] + payment_allocation[payment_id] (same ids, different types).
duplicate_fx: a foreign invoice is posted at the wrong rate, then entered a second time
  copying the wrong posted amount.
  -> fx_rate[original invoice_id] + duplicate_invoice[duplicate invoice_id].
"""

from __future__ import annotations

from .errors import REGISTRY


def partial_fx_cutoff(book, rng, cfg, used):
    pays = sorted(p.key for p in book.payments.values() if "carrier_pfc" in p.tags and p.key not in used)
    if not pays:
        return None
    key = pays[0]
    # inverted is excluded here: 1/rate on a partially applied receipt makes the two amounts hard to
    # tell apart for a reader; adjacent_day is the fallback when the UTC date has the same rate.
    fx = REGISTRY["fx_rate"].inject(book, f"pay:{key}", rng, cfg, prefer="utc_date", exclude={"inverted"})
    if fx is None:
        return None
    al = REGISTRY["payment_allocation"].inject(book, key, rng, cfg, variant="partial")
    if al is None:
        return None
    used.add(key)
    used.update(book.payments[key].refs)
    return [fx, al]


def duplicate_fx(book, rng, cfg, used):
    invs = sorted(i.key for i in book.invoices.values() if "carrier_dfx" in i.tags and i.key not in used)
    if not invs:
        return None
    key = invs[0]
    fx = REGISTRY["fx_rate"].inject(book, f"inv:{key}", rng, cfg)
    if fx is None:
        return None
    posted = book.row_of(("inv", key), "inv_ar").debit
    dup = REGISTRY["duplicate_invoice"].inject(book, key, rng, cfg, base_amount=posted, variant="copy_as_posted")
    if dup is None:
        return None
    used.add(key)
    used.add(f"{key}d")
    return [fx, dup]


SCENARIOS = {"duplicate_fx": duplicate_fx, "partial_fx_cutoff": partial_fx_cutoff}
SCENARIO_TYPES = {"duplicate_fx": ["duplicate_invoice", "fx_rate"],
                  "partial_fx_cutoff": ["fx_rate", "payment_allocation"]}
