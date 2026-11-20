"""Export episodes as plain CSV sheets for a MANUAL audit by non-programmers (Google Sheets / Excel).

python -m auditenv export-audit --out audit
Per episode folder: ledger.csv, invoices.csv (one row per line item), payments.csv, fx.csv,
policy.csv, issues.csv (the closed truth - this is OUR check of the grader), evidence.csv (every
evidence ID of every issue with the record's content, amounts also in major units) and
protocol.csv (an empty form to fill in). docs/MANUAL_AUDIT.md explains the procedure.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .env.data import PublicData
from .money import format_minor
from .paths import EPISODES_DIR

PICKS = [("1_interaction", "dev", "ep-vq9n3qwk8v"), ("2_clean", "dev", "ep-ap6e6dpf7p"),
         ("3_fx_weekend", "dev", "ep-vw9vceq4qf")]


def _w(path: Path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(["" if x is None else x for x in r])


def _major(pd, amount, cur):
    try:
        return format_minor(int(amount), cur)
    except (KeyError, TypeError, ValueError):
        return ""


def export_one(src: Path, out: Path) -> dict:
    pd = PublicData.from_dir(src / "public")
    truth = json.loads((src / "grader" / "truth.json").read_text("utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    base = pd.base
    _w(out / "ledger.csv", ["row_id", "timestamp", "local_time", "account", "debit_minor", "credit_minor", "debit", "credit",
                            "currency", "entity_id", "invoice_id", "payment_id"],
       [[r["row_id"], r["timestamp"], pd.local(r["timestamp"]).isoformat(), r["account"], r["debit_minor"], r["credit_minor"],
         _major(pd, r["debit_minor"], base), _major(pd, r["credit_minor"], base), r["currency"], r["entity_id"],
         r["invoice_id"], r["payment_id"]] for r in pd.ledger])
    rows = []
    for i in pd.invoices:
        for n, li in enumerate(i["line_items"], 1):
            rows.append([i["doc_id"], i["invoice_id"], i["entity_id"], i["issued_at"], pd.local(i["issued_at"]).isoformat(),
                         i["due_at"], i["currency"], i["total_minor"], _major(pd, i["total_minor"], i["currency"]), n,
                         li["description"], li["service_period"], li["quantity"], li["unit_price_minor"], li["amount_minor"]])
    _w(out / "invoices.csv", ["doc_id", "invoice_id", "entity_id", "issued_at", "local_time", "due_at", "currency",
                              "total_minor", "total", "line_no", "description", "service_period", "quantity",
                              "unit_price_minor", "amount_minor"], rows)
    _w(out / "payments.csv", ["doc_id", "payment_id", "timestamp", "local_time", "currency", "amount_minor", "amount",
                              "invoice_refs"],
       [[p["doc_id"], p["payment_id"], p["timestamp"], pd.local(p["timestamp"]).isoformat(), p["currency"],
         p["amount_minor"], _major(pd, p["amount_minor"], p["currency"]),
         "" if p["invoice_refs"] is None else ";".join(p["invoice_refs"])] for p in pd.payments])
    _w(out / "fx.csv", ["fx_id", "date", "weekday", "source_currency", "target_currency", "rate"],
       [[f["fx_id"], f["date"], __import__("datetime").date.fromisoformat(f["date"]).strftime("%A"), f["source_currency"],
         f["target_currency"], f["rate"]] for f in pd.fx])
    pol = dict(pd.policy)
    pol.update({f"period_boundary.{k}": v for k, v in pol.pop("period_boundary").items()})
    pol.update({f"account.{k}": v for k, v in pol.pop("accounts").items()})
    pol["currency_exponents"] = json.dumps(pd.exponents)
    pol["base_currency"] = base
    _w(out / "policy.csv", ["key", "value"], sorted(pol.items()))
    _w(out / "issues.csv", ["issue_id", "type", "affected_id", "expected_amount_minor", "expected_amount", "currency",
                            "tolerance_minor", "evidence_set_1", "evidence_set_2", "evidence_set_3"],
       [[i["issue_id"], i["type"], i["affected_ids"][0], i["expected_amount_minor"],
         _major(pd, i["expected_amount_minor"], i["currency"]), i["currency"], truth.get("tolerance_minor", 1)]
        + [";".join(s) for s in i["evidence_sets"]] + [""] * (3 - len(i["evidence_sets"])) for i in truth["issues"]])
    ev = []
    for i in truth["issues"]:
        for k, s in enumerate(i["evidence_sets"], 1):
            for x in s:
                kind, rec = pd.any_record(x)
                if kind == "policy":
                    what = "policy.json (rules: rate date, previous business day, period, rounding)"
                elif kind == "fx":
                    what = f"rate {rec['rate']} {rec['target_currency']} per 1 {rec['source_currency']} on {rec['date']}"
                elif kind == "ledger":
                    what = (f"account {rec['account']} Dr {_major(pd, rec['debit_minor'], base)} Cr "
                            f"{_major(pd, rec['credit_minor'], base)} {base} at {rec['timestamp']} invoice={rec['invoice_id']} "
                            f"payment={rec['payment_id']}")
                elif kind == "invoice":
                    what = (f"invoice {rec['invoice_id']} client {rec['entity_id']} issued {rec['issued_at']} "
                            f"(local {pd.local(rec['issued_at']).isoformat()}) total {_major(pd, rec['total_minor'], rec['currency'])} "
                            f"{rec['currency']}")
                else:
                    what = (f"payment {rec['payment_id']} at {rec['timestamp']} (local {pd.local(rec['timestamp']).isoformat()}) "
                            f"amount {_major(pd, rec['amount_minor'], rec['currency'])} {rec['currency']} refs {rec['invoice_refs']}")
                ev.append([i["issue_id"], i["type"], k, x, kind, what])
    _w(out / "evidence.csv", ["issue_id", "type", "evidence_set", "evidence_id", "record_kind", "what_it_says"], ev)
    proto = [[i["issue_id"], i["type"], "", "", "", "", "", ""] for i in truth["issues"]]
    if not truth["issues"]:
        proto = [["(clean book)", "-", "", "", "", "", "", ""]]
    _w(out / "protocol.csv", ["issue_id", "type", "evidence_set_used", "my_recomputed_amount", "matches_truth (yes/no)",
                              "comment", "auditor", "date"], proto)
    return {"episode_id": pd.episode_id, "issues": len(truth["issues"]), "out": str(out)}


def main(out="audit") -> list:
    res = []
    for label, split, eid in PICKS:
        res.append(export_one(EPISODES_DIR / split / eid, Path(out) / f"{label}_{eid}"))
    return res
