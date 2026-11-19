"""Read-only, parsed view of an episode's PUBLIC files (what tools can expose)."""

from __future__ import annotations

import bisect
from pathlib import Path

from ..canon import files_digest
from ..generator.export import parse_files, read_public_files
from ..money import convert_minor
from ..timeutil import parse_ts, policy_rate_date, tzinfo_for

TABLES = ("ledger", "invoices", "payments", "fx")


def fx_id(rec: dict) -> str:
    return f"fx:{rec['date']}:{rec['source_currency']}:{rec['target_currency']}"


class PublicData:
    def __init__(self, files: dict):
        self.files = dict(files)
        t = parse_files(files)
        self.manifest = t["manifest"]
        self.policy = t["policy"]
        self.ledger = t["ledger"]
        self.invoices = t["invoices"]
        self.payments = t["payments"]
        self.fx = [dict(r, fx_id=fx_id(r)) for r in t["fx"]]
        self.digest = files_digest(files)
        self.episode_id = self.manifest["episode_id"]
        self.base = self.manifest["base_currency"]
        self.exponents = self.manifest["currencies"]
        self.tz = tzinfo_for(self.manifest["timezone"])
        self.period_start = parse_ts(self.policy["period_boundary"]["start"])
        self.period_end = parse_ts(self.policy["period_boundary"]["end"])
        self.ledger_by_id = {r["row_id"]: r for r in self.ledger}
        self.invoice_by_id = {r["invoice_id"]: r for r in self.invoices}
        self.payment_by_id = {r["payment_id"]: r for r in self.payments}
        self.doc_by_id = {r["doc_id"]: r for r in self.invoices}
        self.doc_by_id.update({r["doc_id"]: r for r in self.payments})
        self.fx_by_id = {r["fx_id"]: r for r in self.fx}
        self._fx_dates = {}
        for r in self.fx:
            self._fx_dates.setdefault(r["source_currency"], []).append(r["date"])
        for v in self._fx_dates.values():
            v.sort()
        self._fx_rate = {(r["date"], r["source_currency"]): r["rate"] for r in self.fx}

    @classmethod
    def from_dir(cls, public_dir) -> "PublicData":
        return cls(read_public_files(Path(public_dir)))

    # -------------------------------------------------------------- lookups
    def table(self, name: str) -> list:
        return getattr(self, name)

    def record_by_id(self, table: str, rid: str):
        if table == "ledger":
            return self.ledger_by_id.get(rid)
        if table == "invoices":
            return self.invoice_by_id.get(rid)
        if table == "payments":
            return self.payment_by_id.get(rid)
        if table == "fx":
            return self.fx_by_id.get(rid)
        if table == "policy":
            return self.policy if rid == "policy" else None
        return None

    def any_record(self, rid: str):
        """Resolve an evidence ID: doc_id, row_id, fx id or 'policy'."""
        if rid == "policy":
            return ("policy", self.policy)
        if rid in self.doc_by_id:
            d = self.doc_by_id[rid]
            return ("invoice" if "invoice_id" in d else "payment", d)
        if rid in self.ledger_by_id:
            return ("ledger", self.ledger_by_id[rid])
        if rid in self.fx_by_id:
            return ("fx", self.fx_by_id[rid])
        return None

    # ------------------------------------------------------------ time / fx
    def local(self, ts: str):
        return parse_ts(ts).astimezone(self.tz)

    def in_period(self, ts: str) -> bool:
        t = parse_ts(ts)
        return self.period_start <= t < self.period_end

    def rate_record(self, cur: str, local_date):
        """Latest available rate on or before local_date (previous_business_day rule)."""
        dates = self._fx_dates.get(cur, [])
        i = bisect.bisect_right(dates, local_date.isoformat())
        if i == 0:
            return None
        d = dates[i - 1]
        return self.fx_by_id[f"fx:{d}:{cur}:{self.base}"]

    def correct_rate(self, ts: str, cur: str):
        if cur == self.base:
            return "1", None
        rec = self.rate_record(cur, self.local(ts).date())
        return (rec["rate"], rec) if rec else (None, None)

    def to_base(self, amount: int, cur: str, rate: str) -> int:
        return convert_minor(amount, cur, self.base, rate, exponents=self.exponents)

    @staticmethod
    def calendar_rate_date(local_date):
        return policy_rate_date(local_date)
