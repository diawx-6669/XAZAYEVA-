#!/usr/bin/env python3
"""Independent verifier of AuditEnv episodes. NO imports from auditenv: stdlib csv/json/decimal/datetime only.

Written from the case text (docs/CASE.md) and the episode's own policy.json, not from the generator:
  1. re-derives every error from the PUBLIC files (public/*) with its own reading of the rules;
  2. compares with grader/truth.json: same (type, affected_ids), amount within truth.tolerance_minor;
  3. for every evidence set recomputes the amount from the records IN THAT SET ONLY;
  4. on clean books finds nothing.
Usage:  python -I tools/verify_independent.py EPISODE_DIR [EPISODE_DIR ...] [--json]
(-I: isolated mode, PYTHONPATH and the user site are ignored, so auditenv cannot sneak in.)
Exit code 0 iff every episode verifies.
"""

import csv
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext

ROUNDING = {"ROUND_HALF_EVEN": ROUND_HALF_EVEN, "ROUND_HALF_UP": ROUND_HALF_UP}
CN_PREFIX = "Credit note for "


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def _read_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class Episode:
    def __init__(self, d):
        pub = os.path.join(d, "public")
        self.manifest = _read_json(os.path.join(pub, "manifest.json"))
        self.policy = _read_json(os.path.join(pub, "policy.json"))
        self.ledger = []
        for r in _read_csv(os.path.join(pub, "ledger.csv")):
            self.ledger.append({"row_id": r["row_id"], "ts": r["timestamp"], "account": r["account"],
                                "dr": int(r["debit_minor"]), "cr": int(r["credit_minor"]),
                                "inv": r["invoice_id"] or None, "pay": r["payment_id"] or None,
                                "entity": r["entity_id"] or None})
        self.invoices = _read_jsonl(os.path.join(pub, "invoices.jsonl"))
        self.payments = _read_jsonl(os.path.join(pub, "payments.jsonl"))
        self.rates = {}
        for r in _read_csv(os.path.join(pub, "fx.csv")):
            self.rates[(r["date"], r["source_currency"])] = r["rate"]
        self.base = self.manifest["base_currency"]
        self.exp = self.manifest["currencies"]
        pb = self.policy["period_boundary"]
        sign = -1 if pb["utc_offset"][0] == "-" else 1
        hh, mm = pb["utc_offset"][1:].split(":")
        self.tz = timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))
        self.start = datetime.fromisoformat(pb["start"])
        self.end = datetime.fromisoformat(pb["end"])
        self.rounding = ROUNDING[self.policy["rounding"]]
        self.inv = {i["invoice_id"]: i for i in self.invoices}
        self.pay = {p["payment_id"]: p for p in self.payments}
        self.docs = {x["doc_id"]: x for x in self.invoices + self.payments}
        self.rows = {r["row_id"]: r for r in self.ledger}
        truth_path = os.path.join(d, "grader", "truth.json")
        self.truth = _read_json(truth_path) if os.path.exists(truth_path) else None

    # ---- rules from the case + policy.json
    def local_day(self, ts):
        return datetime.fromisoformat(ts).astimezone(self.tz).date()

    @staticmethod
    def rate_day(d):
        """fx_missing_rate = previous_business_day (business days are Monday-Friday)."""
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d

    def rate(self, cur, ts):
        if cur == self.base:
            return "1"
        return self.rates.get((self.rate_day(self.local_day(ts)).isoformat(), cur))

    def conv(self, amount, cur, rate):
        if cur == self.base:
            return amount
        with localcontext() as ctx:
            ctx.prec = 50
            v = Decimal(amount) * Decimal(rate) * (Decimal(10) ** (self.exp[self.base] - self.exp[cur]))
            return int(v.quantize(Decimal(1), rounding=self.rounding))

    def in_period(self, ts):
        t = datetime.fromisoformat(ts)
        return self.start <= t < self.end

    @staticmethod
    def cancelled_ref(inv):
        if inv["total_minor"] >= 0:
            return None
        refs = set()
        for li in inv["line_items"]:
            if not li["description"].startswith(CN_PREFIX):
                return None
            refs.add(li["description"][len(CN_PREFIX):].split(": ", 1)[0])
        return refs.pop() if len(refs) == 1 else None

    @staticmethod
    def bill_key(inv):
        lines = sorted((li["description"], li["service_period"], li["quantity"], li["unit_price_minor"], li["amount_minor"])
                       for li in inv["line_items"])
        return (inv["entity_id"], inv["currency"], tuple(lines))

    def invoice_posting(self, iid):
        """Amount of the invoice's own posting (1200 side, no payment_id)."""
        return sum(r["dr"] + r["cr"] for r in self.ledger if r["inv"] == iid and not r["pay"] and r["account"] == "1200")

    # ---- the solver
    def solve(self):
        found = {}
        cancelled = {self.cancelled_ref(i) for i in self.invoices} - {None}
        groups = {}
        for i in self.invoices:
            if self.cancelled_ref(i) or i["invoice_id"] in cancelled:
                continue
            groups.setdefault(self.bill_key(i), []).append(i)
        dups = set()
        for invs in groups.values():
            invs.sort(key=lambda i: (datetime.fromisoformat(i["issued_at"]), i["invoice_id"]))
            for d in invs[1:]:
                dups.add(d["invoice_id"])
                found[("duplicate_invoice", d["invoice_id"])] = self.invoice_posting(d["invoice_id"])
        # allocation (policy: invoice_refs in order up to the open balance; payments in time order)
        open_bal = {i["invoice_id"]: i["total_minor"] for i in self.invoices if not self.cancelled_ref(i)}
        for p in sorted(self.payments, key=lambda p: (datetime.fromisoformat(p["timestamp"]), p["payment_id"])):
            rows = [r for r in self.ledger if r["pay"] == p["payment_id"]]
            applied = {}
            for r in rows:
                if r["account"] == "1200":
                    applied[r["inv"]] = applied.get(r["inv"], 0) + r["cr"] - r["dr"]
            cr2400 = sum(r["cr"] - r["dr"] for r in rows if r["account"] == "2400")
            if p["invoice_refs"] is None:
                if any(applied.values()):
                    found[("payment_allocation", p["payment_id"])] = abs(sum(applied.values()))
                continue
            left, want = p["amount_minor"], {}
            for ref in p["invoice_refs"]:
                a = min(left, max(0, open_bal.get(ref, 0)))
                open_bal[ref] = open_bal.get(ref, 0) - a
                left -= a
                inv = self.inv.get(ref)
                if inv is not None:
                    want[ref] = want.get(ref, 0) + self.conv(a, p["currency"], self.rate(inv["currency"], inv["issued_at"]))
            exp2400 = self.conv(left, p["currency"], self.rate(p["currency"], p["timestamp"])) if left else 0
            misapplied = max(0, cr2400 - exp2400) + abs(sum(v for k, v in applied.items() if k not in want))
            diff = sum(abs(applied.get(k, 0) - want.get(k, 0)) for k in set(applied) | set(want))
            if misapplied:
                found[("payment_allocation", p["payment_id"])] = misapplied
            elif diff or cr2400 != exp2400:
                found[("payment_allocation", p["payment_id"])] = diff or abs(cr2400 - exp2400)
        # fx conversion (policy: local transaction date, previous business day, once per document)
        for i in self.invoices:
            if i["invoice_id"] in dups:
                continue
            rate = self.rate(i["currency"], i["issued_at"])
            want = self.conv(abs(i["total_minor"]), i["currency"], rate)
            got = self.invoice_posting(i["invoice_id"])
            if got != want:
                found[("fx_rate", i["invoice_id"])] = abs(got - want)
        for p in self.payments:
            want = self.conv(p["amount_minor"], p["currency"], self.rate(p["currency"], p["timestamp"]))
            got = sum(r["dr"] for r in self.ledger if r["pay"] == p["payment_id"] and r["account"] == "1000")
            if got != want:
                found[("fx_rate", p["payment_id"])] = abs(got - want)
        # period (recognition = invoice issue date; every row dated inside the period)
        posted_inv = {r["inv"] for r in self.ledger if r["inv"] and not r["pay"]}
        for i in self.invoices:
            if i["invoice_id"] in posted_inv and not self.in_period(i["issued_at"]):
                found[("period_cutoff", i["invoice_id"])] = self.invoice_posting(i["invoice_id"])
        for r in self.ledger:
            if not self.in_period(r["ts"]):
                key = r["inv"] if (r["inv"] and not r["pay"]) else (r["pay"] or r["row_id"])
                found.setdefault(("period_cutoff", key), r["dr"] or r["cr"])
        return found

    # ---- evidence: recompute from the set ONLY
    def evidence_amount(self, issue, ids):
        recs = {}
        for x in ids:
            if x == "policy":
                recs[x] = ("policy", self.policy)
            elif x.startswith("fx:"):
                _, d, src, tgt = x.split(":")
                if (d, src) not in self.rates or tgt != self.base:
                    return None, "unknown_fx_id"
                recs[x] = ("fx", {"date": d, "cur": src, "rate": self.rates[(d, src)]})
            elif x in self.docs:
                recs[x] = ("invoice" if "invoice_id" in self.docs[x] else "payment", self.docs[x])
            elif x in self.rows:
                recs[x] = ("row", self.rows[x])
            else:
                return None, "unknown_id"
        of = lambda k: [v for kind, v in recs.values() if kind == k]  # noqa: E731
        invs, pays, rows, fxs, pol = of("invoice"), of("payment"), of("row"), of("fx"), of("policy")
        typ, aid = issue["type"], issue["affected_ids"][0]
        if typ == "duplicate_invoice":
            dup = [i for i in invs if i["invoice_id"] == aid]
            if not dup:
                return None, "no_duplicate_doc"
            t = (datetime.fromisoformat(dup[0]["issued_at"]), aid)
            if not any(self.bill_key(i) == self.bill_key(dup[0]) and (datetime.fromisoformat(i["issued_at"]), i["invoice_id"]) < t
                       for i in invs if i["invoice_id"] != aid):
                return None, "no_original_doc"
            r = [x for x in rows if x["inv"] == aid and not x["pay"] and x["account"] in ("1200", "4000")]
            return (r[0]["dr"] + r[0]["cr"], "ok") if r else (None, "no_posting_row")
        if typ == "payment_allocation":
            p = [x for x in pays if x["payment_id"] == aid]
            if not p or not p[0]["invoice_refs"]:
                return None, "no_payment_doc"
            p = p[0]
            have = {i["invoice_id"]: i for i in invs}
            if not set(p["invoice_refs"]) <= set(have):
                return None, "missing_invoice_doc"
            mine = [x for x in rows if x["pay"] == aid]
            r2400 = [x for x in mine if x["account"] == "2400" and x["cr"]]
            wrong = [x for x in mine if x["account"] == "1200" and x["cr"] and x["inv"] not in p["invoice_refs"]]
            right = [x for x in mine if x["account"] == "1200" and x["cr"] and x["inv"] in p["invoice_refs"]]
            if r2400:
                return r2400[0]["cr"], "ok"
            if wrong:
                return wrong[0]["cr"], "ok"
            if right and p["currency"] == self.base:
                left, want = p["amount_minor"], 0
                for ref in p["invoice_refs"]:
                    a = min(left, max(0, have[ref]["total_minor"]))
                    want, left = want + a, left - a
                applied = {x["inv"] for x in right}
                expected_rows = [ref for ref in p["invoice_refs"] if have[ref]["total_minor"] > 0]
                if not (applied == set(expected_rows) or applied == set(expected_rows[:-1])):
                    return None, "incomplete_applied_rows"
                amt = want - sum(x["cr"] for x in right)
                return (amt, "ok") if amt > 0 else (None, "nothing_misapplied")
            return None, "no_misapplied_row"
        if typ == "fx_rate":
            d = [i for i in invs if i["invoice_id"] == aid] + [x for x in pays if x["payment_id"] == aid]
            if not d or not pol:
                return None, "no_document_or_policy"
            d = d[0]
            ts = d.get("issued_at") or d["timestamp"]
            day = self.rate_day(self.local_day(ts)).isoformat()
            fx = [f for f in fxs if f["cur"] == d["currency"] and f["date"] == day]
            if not fx:
                return None, "no_policy_rate_record"
            amount = abs(d["total_minor"]) if "invoice_id" in d else d["amount_minor"]
            want = self.conv(amount, d["currency"], fx[0]["rate"])
            if "invoice_id" in d:
                r = [x for x in rows if x["inv"] == aid and not x["pay"] and x["account"] in ("1200", "4000")]
                got = r[0]["dr"] + r[0]["cr"] if r else None
            else:
                r = [x for x in rows if x["pay"] == aid and x["account"] == "1000" and x["dr"]]
                got = r[0]["dr"] if r else None
                other = [x for x in rows if x["pay"] == aid and x["account"] in ("1200", "2400", "7900")]
                if got is None and any(x["account"] == "1200" for x in other):
                    got = sum(x["cr"] - (x["dr"] if x["account"] == "7900" else 0) for x in other)
            return (abs(got - want), "ok") if got is not None else (None, "no_posting_row")
        if typ == "period_cutoff":
            d = [i for i in invs if i["invoice_id"] == aid]
            if not d or not pol:
                return None, "no_document_or_policy"
            if self.in_period(d[0]["issued_at"]):
                return None, "document_inside_period"
            r = [x for x in rows if x["inv"] == aid and not x["pay"] and x["account"] in ("1200", "4000")]
            return (r[0]["dr"] + r[0]["cr"], "ok") if r else (None, "no_posting_row")
        return None, "unknown_type"


def verify(d) -> dict:
    ep = Episode(d)
    problems = []
    found = ep.solve()
    truth = ep.truth or {"issues": []}
    tol = truth.get("tolerance_minor", 1)
    want = {(i["type"], i["affected_ids"][0]): i for i in truth["issues"]}
    for k in sorted(set(found) - set(want)):
        problems.append(f"extra {k[0]} {k[1]} ({found[k]})")
    for k in sorted(set(want) - set(found)):
        problems.append(f"missing {k[0]} {k[1]}")
    for k in sorted(set(want) & set(found)):
        if abs(found[k] - want[k]["expected_amount_minor"]) > tol:
            problems.append(f"amount {k[0]} {k[1]}: solver {found[k]} vs truth {want[k]['expected_amount_minor']}")
    n_sets = 0
    for iss in truth["issues"]:
        for s in iss["evidence_sets"]:
            n_sets += 1
            amt, why = ep.evidence_amount(iss, s)
            if amt is None:
                problems.append(f"evidence {iss['issue_id']}: {why}")
            elif abs(amt - iss["expected_amount_minor"]) > tol:
                problems.append(f"evidence {iss['issue_id']}: recomputes {amt}, truth {iss['expected_amount_minor']}")
    return {"episode_id": ep.manifest["episode_id"], "issues": len(truth["issues"]), "evidence_sets": n_sets,
            "clean": not truth["issues"], "ok": not problems, "problems": problems}


def main(argv):
    as_json = "--json" in argv
    dirs = [a for a in argv if a != "--json"]
    assert not any(m == "auditenv" or m.startswith("auditenv.") for m in sys.modules), "auditenv must not be imported"
    results = [verify(d) for d in dirs]
    bad = [r for r in results if not r["ok"]]
    summary = {"episodes": len(results), "clean": sum(r["clean"] for r in results),
               "issues": sum(r["issues"] for r in results), "evidence_sets": sum(r["evidence_sets"] for r in results),
               "failed": len(bad), "auditenv_imported": False}
    if as_json:
        print(json.dumps({"summary": summary, "failed": bad[:20]}, sort_keys=True))
    else:
        print(f"verify_independent: {summary['episodes']} episodes ({summary['clean']} clean), {summary['issues']} issues, "
              f"{summary['evidence_sets']} evidence sets, {summary['failed']} failed")
        for r in bad[:20]:
            print(" ", r["episode_id"], r["problems"][:5])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
