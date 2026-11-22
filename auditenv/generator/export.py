"""Book -> public tables -> files. Public and grader files are written to separate dirs."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from .. import GENERATOR_VERSION, SCHEMA_VERSION
from ..canon import dumps_bytes, jsonl_bytes
from ..money import EXPONENTS
from ..timeutil import fmt_ts, utc_offset_str
from .books import ACCOUNTS

LEDGER_COLUMNS = ["row_id", "timestamp", "account", "debit_minor", "credit_minor", "currency", "entity_id",
                  "invoice_id", "payment_id"]
FX_COLUMNS = ["date", "source_currency", "target_currency", "rate"]
PUBLIC_FILES = ["manifest.json", "policy.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv"]


def make_policy(book) -> dict:
    s = book.story
    return {
        "policy_id": "policy",
        "fx_rate_date": "transaction_date",
        "fx_rate_date_basis": "local calendar date in the company timezone; invoice: issued_at, payment: timestamp",
        "fx_missing_rate": "previous_business_day",
        "fx_rate_meaning": "units of target_currency per 1 unit of source_currency",
        "fx_conversion": "base_minor = round(amount_minor * rate * 10^(exp_base - exp_src)), once per document",
        "period_boundary": {
            "start": fmt_ts(s.period_start),
            "end": fmt_ts(s.period_end),
            "timezone": s.tz_name,
            "utc_offset": utc_offset_str(s.tz_name),
            "inclusive_start": True,
            "inclusive_end": False,
        },
        "rounding": "ROUND_HALF_EVEN",
        "recognition": "invoice_issue_date",
        "payment_allocation": "invoice_refs_in_order_up_to_open_balance",
        "ar_relief_rate": "rate of the invoice transaction date",
        "fx_difference_account": "7900",
        "unapplied_cash": ("account 2400 holds only cash that cannot be applied: a whole receipt with invoice_refs = null, "
                           "or the part of a receipt exceeding the open balance of the invoices it references "
                           "(overpayment), converted at the payment's policy rate"),
        "credit_notes": "an invoice whose line_items carry cancels_invoice_id cancels that invoice; both stay in the books",
        "revenue_posting": "Dr 1200 = document base amount; one Cr 4000 row per line item, the base amount split by "
                           "line amounts with largest remainder (ties to the earlier line)",
        "vat": ("a line item with description 'VAT 12%' must equal round_half_even(12% x the sum of the other "
                "line items of the same invoice), in the invoice currency's minor units"),
        "accounts": dict(ACCOUNTS),
    }


def book_tables(book, cfg: dict, cfg_hash: str, order_rng) -> dict:
    s = book.story
    # Ledger: chronological, ties broken by the `order` stream.
    rids = sorted(book.rows)
    tie = {rid: order_rng.random() for rid in rids}
    rows = sorted(book.rows.values(), key=lambda r: (r.ts.timestamp(), tie[r.row_id]))
    ledger = [book.row_public(r) for r in rows]
    invoices = [book.inv_public(i) for i in sorted(book.invoices.values(), key=lambda i: i.doc_id)]
    order_rng.shuffle(invoices)
    payments = [book.pay_public(p) for p in sorted(book.payments.values(), key=lambda p: p.doc_id)]
    order_rng.shuffle(payments)
    fx = [{"date": d, "source_currency": c, "target_currency": s.base, "rate": r}
          for (d, c), r in sorted(s.rates.items())]
    currencies = {c: EXPONENTS[c] for c in sorted({s.base, *s.foreign})}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "episode_id": book.episode_id,
        "base_currency": s.base,
        "currencies": currencies,
        "period_start": fmt_ts(s.period_start),
        "period_end": fmt_ts(s.period_end),
        "timezone": s.tz_name,
        "counts": {"ledger": len(ledger), "invoices": len(invoices), "payments": len(payments), "fx": len(fx)},
        "rounding": {"mode": "ROUND_HALF_EVEN", "fx_conversion": "per_document"},
        "config_version": cfg["version"],
        "config_hash": cfg_hash,
        "generator_version": GENERATOR_VERSION,
    }
    return {"manifest": manifest, "policy": make_policy(book), "ledger": ledger, "invoices": invoices,
            "payments": payments, "fx": fx}


def _csv_bytes(columns, rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(columns)
    for r in rows:
        w.writerow(["" if r[c] is None else r[c] for c in columns])
    return buf.getvalue().encode("utf-8")


def serialize_tables(t: dict) -> dict:
    return {
        "manifest.json": dumps_bytes(t["manifest"]),
        "policy.json": dumps_bytes(t["policy"]),
        "ledger.csv": _csv_bytes(LEDGER_COLUMNS, t["ledger"]),
        "invoices.jsonl": jsonl_bytes(t["invoices"]),
        "payments.jsonl": jsonl_bytes(t["payments"]),
        "fx.csv": _csv_bytes(FX_COLUMNS, t["fx"]),
    }


def parse_files(files: dict) -> dict:
    """Inverse of serialize_tables. Empty CSV cells become None."""

    def csv_rows(b):
        return list(csv.DictReader(io.StringIO(b.decode("utf-8"))))

    ledger = []
    for r in csv_rows(files["ledger.csv"]):
        ledger.append({
            "row_id": r["row_id"],
            "timestamp": r["timestamp"],
            "account": r["account"],
            "debit_minor": int(r["debit_minor"]),
            "credit_minor": int(r["credit_minor"]),
            "currency": r["currency"],
            "entity_id": r["entity_id"] or None,
            "invoice_id": r["invoice_id"] or None,
            "payment_id": r["payment_id"] or None,
        })
    fx = [dict(r) for r in csv_rows(files["fx.csv"])]
    jl = lambda b: [json.loads(line) for line in b.decode("utf-8").splitlines() if line.strip()]  # noqa: E731
    return {
        "manifest": json.loads(files["manifest.json"]),
        "policy": json.loads(files["policy.json"]),
        "ledger": ledger,
        "invoices": jl(files["invoices.jsonl"]),
        "payments": jl(files["payments.jsonl"]),
        "fx": fx,
    }


def write_episode(ep, out_dir) -> Path:
    out = Path(out_dir)
    (out / "public").mkdir(parents=True, exist_ok=True)
    (out / "grader").mkdir(parents=True, exist_ok=True)
    for name, data in ep.files.items():
        (out / "public" / name).write_bytes(data)
    (out / "grader" / "truth.json").write_bytes(dumps_bytes(ep.truth))
    (out / "grader" / "provenance.json").write_bytes(dumps_bytes(ep.provenance))
    return out


def grader_files(ep) -> dict:
    return {"truth.json": dumps_bytes(ep.truth), "provenance.json": dumps_bytes(ep.provenance)}


def grader_digest_of_dir(grader_dir) -> str:
    from ..canon import files_digest

    g = Path(grader_dir)
    return files_digest({n: (g / n).read_bytes() for n in ("truth.json", "provenance.json")})


def read_public_files(public_dir) -> dict:
    p = Path(public_dir)
    return {name: (p / name).read_bytes() for name in PUBLIC_FILES}
