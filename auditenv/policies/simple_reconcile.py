"""simple_reconcile: an honest scripted auditor (also the demo policy).

Uses only what the tools return. Reads the policy and every table page by page, then:
  - duplicates: same entity + currency + identical line items -> the later one;
  - allocation: a receipt that references invoices but has an Unapplied Cash (2400) credit;
  - fx: re-converts every foreign document with the rate of its LOCAL transaction date;
  - cutoff: invoice issued outside the period by LOCAL time.
Known, deliberate simplifications (measured in docs/FAILURES.md):
  - ignores credit notes when looking for duplicates (a re-issued invoice looks duplicated);
  - needs an exact-date FX rate: weekend documents (previous_business_day rule) are skipped;
  - does not exclude duplicates from the FX check (a duplicate copied at a wrong rate is also
    reported as fx_rate).
"""

from __future__ import annotations

import json

from ..money import convert_minor
from ..timeutil import parse_ts, tzinfo_for
from .base import Policy, TableReader, finding, submit


class SimpleReconcile(Policy):
    name = "simple_reconcile"

    def reset(self):
        super().reset()
        self.reader = None
        self.policy = None
        self.asked_policy = False
        self.log = []

    def act(self, obs):
        if "manifest" in obs:
            self.manifest = obs["manifest"]
            self.steps_left = obs["steps_remaining"]
            self.reader = TableReader(["ledger", "invoices", "payments", "fx"])
            self.asked_policy = True
            return {"tool": "get_record", "args": {"table": "policy", "id": "policy"}}
        self.steps_left = obs.get("steps_remaining", 0)
        if self.policy is None and self.asked_policy:
            self.policy = (obs.get("result") or {}).get("record") or {}
            self.asked_policy = False
        else:
            self.reader.feed(obs)
        if self.steps_left > 1:
            a = self.reader.next_action()
            if a is not None:
                return a
        return submit(self.manifest["episode_id"], self.analyse())

    # --------------------------------------------------------------- analysis
    def analyse(self) -> list:
        m = self.manifest
        base = m["base_currency"]
        exps = m["currencies"]
        tz = tzinfo_for(m["timezone"])
        start, end = parse_ts(m["period_start"]), parse_ts(m["period_end"])
        led = self.reader.data["ledger"]
        invs = self.reader.data["invoices"]
        pays = self.reader.data["payments"]
        rates = {(r["date"], r["source_currency"]): r for r in self.reader.data["fx"]}
        inv_rows, pay_rows = {}, {}
        for r in led:
            if r["payment_id"]:
                pay_rows.setdefault(r["payment_id"], []).append(r)
            elif r["invoice_id"] and r["account"] in ("1200", "4000"):
                inv_rows.setdefault(r["invoice_id"], []).append(r)
        out = []

        def ar_row(iid):
            rows = [r for r in inv_rows.get(iid, []) if r["account"] == "1200" and r["debit_minor"] > 0]
            return rows[0] if rows else None

        # duplicates
        groups = {}
        for i in invs:
            if i["total_minor"] <= 0:
                continue
            items = sorted(json.dumps(li, sort_keys=True) for li in i["line_items"])
            groups.setdefault((i["entity_id"], i["currency"], tuple(items)), []).append(i)
        for key in sorted(groups):
            g = sorted(groups[key], key=lambda i: (parse_ts(i["issued_at"]), i["invoice_id"]))
            for dup in g[1:]:
                row = ar_row(dup["invoice_id"])
                if row:
                    out.append(finding("duplicate_invoice", [dup["invoice_id"]], row["debit_minor"], base,
                                       [g[0]["doc_id"], dup["doc_id"], row["row_id"]], "same entity and line items"))
        # allocation
        inv_doc = {i["invoice_id"]: i["doc_id"] for i in invs}
        for p in pays:
            if not p["invoice_refs"]:
                continue
            un = [r for r in pay_rows.get(p["payment_id"], []) if r["account"] == "2400" and r["credit_minor"] > 0]
            if un:
                ev = [p["doc_id"]] + [inv_doc[x] for x in p["invoice_refs"] if x in inv_doc] + [un[0]["row_id"]]
                out.append(finding("payment_allocation", [p["payment_id"]], un[0]["credit_minor"], base, ev,
                                   "receipt with invoice refs left on unapplied cash"))
        # fx
        for d in invs + pays:
            if d["currency"] == base:
                continue
            is_inv = "invoice_id" in d
            ts = d["issued_at"] if is_inv else d["timestamp"]
            day = parse_ts(ts).astimezone(tz).date().isoformat()
            fx = rates.get((day, d["currency"]))
            if fx is None:
                continue  # simplification: no previous-business-day fallback
            amount = abs(d["total_minor"]) if is_inv else d["amount_minor"]
            correct = convert_minor(amount, d["currency"], base, fx["rate"], exponents=exps)
            if is_inv:
                row = ar_row(d["invoice_id"])
                cr = [r for r in inv_rows.get(d["invoice_id"], []) if r["account"] == "1200" and r["credit_minor"] > 0]
                row = row or (cr[0] if cr else None)
                posted = (row["debit_minor"] + row["credit_minor"]) if row else None
            else:
                rows = [r for r in pay_rows.get(d["payment_id"], []) if r["account"] == "1000" and r["debit_minor"] > 0]
                row = rows[0] if rows else None
                posted = row["debit_minor"] if row else None
            if row is not None and abs(posted - correct) > 1:
                ids = [d["invoice_id"] if is_inv else d["payment_id"]]
                out.append(finding("fx_rate", ids, abs(posted - correct), base,
                                   [d["doc_id"], row["row_id"], fx["fx_id"], "policy"], "re-converted at local-date rate"))
        # cutoff
        for i in invs:
            t = parse_ts(i["issued_at"])
            if not (start <= t < end):
                row = ar_row(i["invoice_id"])
                if row:
                    out.append(finding("period_cutoff", [i["invoice_id"]], row["debit_minor"], base,
                                       [i["doc_id"], row["row_id"], "policy"], "issued outside the period (local time)"))
        return out[:30]
