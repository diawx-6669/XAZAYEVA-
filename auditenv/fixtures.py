"""Hand-made companies from spreadsheets -> AuditEnv episodes (round 3, tests/fixtures/).

A fixture folder holds CSV sheets in the SAME layout as the manual-audit export (`python -m auditenv
export-audit`, docs/MANUAL_AUDIT.md), so a company built by hand in Google Sheets is saved sheet by sheet
("File -> Download -> CSV") and dropped in as is:

    ledger.csv    row_id, timestamp, account, debit_minor, credit_minor, currency, entity_id, invoice_id, payment_id
                  (extra columns such as local_time / debit / credit are ignored)
    invoices.csv  one row per line item: doc_id, invoice_id, entity_id, issued_at, due_at, currency, total_minor,
                  line_no, description, service_period, quantity, unit_price_minor, amount_minor[, cancels_invoice_id]
    payments.csv  doc_id, payment_id, timestamp, currency, amount_minor, invoice_refs (";"-separated, empty = null)
    fx.csv        date, source_currency, target_currency, rate
    policy.csv    key, value (period_boundary.* / account.* flattened; base_currency; currency_exponents as JSON)
    issues.csv    THE AUTHOR'S ANSWER: issue_id, type, affected_id (";" for several), expected_amount_minor, currency,
                  [tolerance_minor], evidence_set_1..3 (";"-separated IDs); no data rows = a clean company
    meta.csv      optional key, value: episode_id (default: ep- + sha256(folder name)[:10]), author, source, note

Nothing is inferred or "fixed": a cell that does not parse is an error naming the sheet, row and column.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from . import SCHEMA_VERSION
from .generator.episode import Episode
from .generator.export import serialize_tables

SHEETS = ("ledger.csv", "invoices.csv", "payments.csv", "fx.csv", "policy.csv", "issues.csv")


class FixtureError(ValueError):
    pass


def _rows(folder: Path, name: str) -> list:
    path = folder / name
    if not path.exists():
        raise FixtureError(f"{folder.name}: missing sheet {name}")
    text = path.read_text("utf-8-sig")  # Google Sheets / Excel may add a BOM
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(text))]


def _int(sheet, n, row, col):
    try:
        return int(row[col])
    except (KeyError, ValueError):
        raise FixtureError(f"{sheet} row {n + 2}: column {col!r} must be an integer, got {row.get(col)!r}") from None


def _need(sheet, n, row, col):
    if not row.get(col):
        raise FixtureError(f"{sheet} row {n + 2}: column {col!r} is empty")
    return row[col]


def _bool(s: str):
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    return s


def read_tables(folder: Path) -> tuple[dict, dict, dict]:
    """-> (tables for serialize_tables, truth, meta)."""
    folder = Path(folder)
    meta = {}
    if (folder / "meta.csv").exists():
        meta = {r["key"]: r["value"] for r in _rows(folder, "meta.csv")}
    # Schema-valid identifiers derived from the folder itself: episode_id from its name, config_hash from the bytes
    # of its sheets (a hand-made company has no generator config; the hash still changes when a sheet changes).
    episode_id = meta.get("episode_id") or "ep-" + hashlib.sha256(folder.name.encode()).hexdigest()[:10]
    content = hashlib.sha256()
    for name in SHEETS:
        if (folder / name).exists():
            content.update(name.encode() + b"\0" + (folder / name).read_bytes() + b"\0")

    pol_kv = {_need("policy.csv", n, r, "key"): r.get("value", "") for n, r in enumerate(_rows(folder, "policy.csv"))}
    base = pol_kv.pop("base_currency", None)
    if not base:
        raise FixtureError("policy.csv: key base_currency is required")
    try:
        exps = {k: int(v) for k, v in json.loads(pol_kv.pop("currency_exponents")).items()}
    except (KeyError, ValueError, TypeError, AttributeError):
        raise FixtureError('policy.csv: currency_exponents must be JSON like {"KZT": 2, "USD": 2}') from None
    policy, pb, accounts = {}, {}, {}
    for k, v in sorted(pol_kv.items()):
        if k.startswith("period_boundary."):
            pb[k.split(".", 1)[1]] = _bool(v)
        elif k.startswith("account."):
            accounts[k.split(".", 1)[1]] = v
        else:
            policy[k] = v
    for k in ("start", "end", "timezone", "utc_offset"):
        if k not in pb:
            raise FixtureError(f"policy.csv: period_boundary.{k} is required")
    policy["period_boundary"] = pb
    policy["accounts"] = accounts
    policy.setdefault("policy_id", "policy")

    ledger = []
    for n, r in enumerate(_rows(folder, "ledger.csv")):
        ledger.append({"row_id": _need("ledger.csv", n, r, "row_id"), "timestamp": _need("ledger.csv", n, r, "timestamp"),
                       "account": _need("ledger.csv", n, r, "account"),
                       "debit_minor": _int("ledger.csv", n, r, "debit_minor"),
                       "credit_minor": _int("ledger.csv", n, r, "credit_minor"),
                       "currency": _need("ledger.csv", n, r, "currency"), "entity_id": r.get("entity_id") or None,
                       "invoice_id": r.get("invoice_id") or None, "payment_id": r.get("payment_id") or None})

    invoices, by_doc = [], {}
    for n, r in enumerate(_rows(folder, "invoices.csv")):
        doc = _need("invoices.csv", n, r, "doc_id")
        if doc not in by_doc:
            by_doc[doc] = {"doc_id": doc, "invoice_id": _need("invoices.csv", n, r, "invoice_id"),
                           "entity_id": _need("invoices.csv", n, r, "entity_id"),
                           "issued_at": _need("invoices.csv", n, r, "issued_at"), "due_at": _need("invoices.csv", n, r, "due_at"),
                           "currency": _need("invoices.csv", n, r, "currency"),
                           "total_minor": _int("invoices.csv", n, r, "total_minor"), "line_items": [], "_lines": []}
            invoices.append(by_doc[doc])
        li = {"description": r.get("description", ""), "service_period": _need("invoices.csv", n, r, "service_period"),
              "quantity": _int("invoices.csv", n, r, "quantity"),
              "unit_price_minor": _int("invoices.csv", n, r, "unit_price_minor"),
              "amount_minor": _int("invoices.csv", n, r, "amount_minor")}
        if r.get("cancels_invoice_id"):
            li["cancels_invoice_id"] = r["cancels_invoice_id"]
        by_doc[doc]["_lines"].append((_int("invoices.csv", n, r, "line_no") if r.get("line_no") else n, li))
    for inv in invoices:
        inv["line_items"] = [li for _, li in sorted(inv.pop("_lines"), key=lambda x: x[0])]
        if sum(li["amount_minor"] for li in inv["line_items"]) != inv["total_minor"]:
            raise FixtureError(f"invoices.csv: lines of {inv['invoice_id']} do not sum to total_minor")

    payments = []
    for n, r in enumerate(_rows(folder, "payments.csv")):
        refs = r.get("invoice_refs", "")
        payments.append({"doc_id": _need("payments.csv", n, r, "doc_id"), "payment_id": _need("payments.csv", n, r, "payment_id"),
                         "timestamp": _need("payments.csv", n, r, "timestamp"),
                         "currency": _need("payments.csv", n, r, "currency"),
                         "amount_minor": _int("payments.csv", n, r, "amount_minor"),
                         "invoice_refs": [x.strip() for x in refs.split(";") if x.strip()] or None})

    fx = [{"date": _need("fx.csv", n, r, "date"), "source_currency": _need("fx.csv", n, r, "source_currency"),
           "target_currency": _need("fx.csv", n, r, "target_currency"), "rate": _need("fx.csv", n, r, "rate")}
          for n, r in enumerate(_rows(folder, "fx.csv"))]

    issues, tol = [], None
    for n, r in enumerate(_rows(folder, "issues.csv")):
        if not any(r.values()):
            continue
        sets = [[x.strip() for x in r[k].split(";") if x.strip()] for k in ("evidence_set_1", "evidence_set_2", "evidence_set_3")
                if r.get(k)]
        if not sets:
            raise FixtureError(f"issues.csv row {n + 2}: at least evidence_set_1 is required")
        issues.append({"issue_id": _need("issues.csv", n, r, "issue_id"), "type": _need("issues.csv", n, r, "type"),
                       "affected_ids": sorted(x.strip() for x in _need("issues.csv", n, r, "affected_id").split(";")),
                       "expected_amount_minor": _int("issues.csv", n, r, "expected_amount_minor"),
                       "currency": _need("issues.csv", n, r, "currency"), "evidence_sets": sets})
        if r.get("tolerance_minor"):
            tol = _int("issues.csv", n, r, "tolerance_minor")
    truth = {"episode_id": episode_id, "issues": sorted(issues, key=lambda i: i["issue_id"]),
             "tolerance_minor": 1 if tol is None else tol}

    manifest = {"schema_version": SCHEMA_VERSION, "episode_id": episode_id, "base_currency": base, "currencies": exps,
                "period_start": pb["start"], "period_end": pb["end"], "timezone": pb["timezone"],
                "counts": {"ledger": len(ledger), "invoices": len(invoices), "payments": len(payments), "fx": len(fx)},
                "rounding": {"mode": policy.get("rounding", "ROUND_HALF_EVEN"), "fx_conversion": "per_document"},
                "config_hash": meta.get("config_hash", content.hexdigest()[:16]), "config_version": meta.get("config_version", "fixture"),
                "generator_version": meta.get("generator_version", "hand-made-csv")}
    tables = {"manifest": manifest, "policy": policy, "ledger": ledger, "invoices": invoices, "payments": payments, "fx": fx}
    return tables, truth, meta


def load_fixture(folder) -> Episode:
    tables, truth, meta = read_tables(Path(folder))
    files = serialize_tables(tables)
    return Episode(truth["episode_id"], files, truth, {"source": "hand-made fixture", "meta": meta}, meta={"fixture": True})
