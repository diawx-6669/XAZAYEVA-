"""Harmless transforms: row permutation and ID renaming, carried over into truth.

A transformed twin describes exactly the same books, so the oracle's reward and F1 must be
unchanged once IDs are mapped. Prefixes are kept; only the random token is replaced.
"""

from __future__ import annotations

import copy

from ..ids import ALPHABET, make_rng
from .books import CREDIT_NOTE_PREFIX
from .episode import Episode
from .export import parse_files, serialize_tables


def _collect_ids(t: dict) -> list:
    ids = {t["manifest"]["episode_id"]}
    for r in t["ledger"]:
        ids.update(x for x in (r["row_id"], r["entity_id"], r["invoice_id"], r["payment_id"]) if x)
    for i in t["invoices"]:
        ids.update(x for x in (i["doc_id"], i["invoice_id"], i["entity_id"]) if x)
    for p in t["payments"]:
        ids.update((p["doc_id"], p["payment_id"]))
    return sorted(ids)


def make_mapping(t: dict, seed) -> dict:
    rng = make_rng(seed, "transform-naming")
    old = _collect_ids(t)
    taken = set(old)
    mapping = {}
    for x in old:
        prefix, _, tok = x.rpartition("-")
        while True:
            alphabet = ALPHABET.lower() if tok.islower() else ALPHABET
            new = f"{prefix}-" + "".join(rng.choice(alphabet) for _ in range(len(tok)))
            if new not in taken:
                taken.add(new)
                mapping[x] = new
                break
    return mapping


def transform_tables(t: dict, mapping: dict, seed) -> dict:
    t = copy.deepcopy(t)
    m = lambda x: mapping.get(x, x) if x is not None else None  # noqa: E731
    t["manifest"]["episode_id"] = m(t["manifest"]["episode_id"])
    for r in t["ledger"]:
        for k in ("row_id", "entity_id", "invoice_id", "payment_id"):
            r[k] = m(r[k])
    for i in t["invoices"]:
        for k in ("doc_id", "invoice_id", "entity_id"):
            i[k] = m(i[k])
        for li in i["line_items"]:  # credit notes reference the cancelled invoice in the line text
            if li["description"].startswith(CREDIT_NOTE_PREFIX):
                ref, sep, rest = li["description"][len(CREDIT_NOTE_PREFIX):].partition(": ")
                li["description"] = f"{CREDIT_NOTE_PREFIX}{m(ref)}{sep}{rest}"
    for p in t["payments"]:
        p["doc_id"], p["payment_id"] = m(p["doc_id"]), m(p["payment_id"])
        if p["invoice_refs"] is not None:
            p["invoice_refs"] = [m(x) for x in p["invoice_refs"]]
    rng = make_rng(seed, "transform-order")
    for k in ("ledger", "invoices", "payments", "fx"):
        rng.shuffle(t[k])
    return t


def transform_truth(truth: dict, mapping: dict) -> dict:
    m = lambda x: mapping.get(x, x)  # noqa: E731
    out = copy.deepcopy(truth)
    out["episode_id"] = m(out["episode_id"])
    for i in out["issues"]:
        i["affected_ids"] = sorted(m(x) for x in i["affected_ids"])
        i["evidence_sets"] = [[m(x) for x in s] for s in i["evidence_sets"]]
    return out


def transform_episode(ep: Episode, seed) -> tuple:
    t = parse_files(ep.files)
    mapping = make_mapping(t, seed)
    t2 = transform_tables(t, mapping, seed)
    files = serialize_tables(t2)
    truth = transform_truth(ep.truth, mapping)
    prov = {"transformed_from": ep.episode_id, "transform_seed": seed}
    return Episode(t2["manifest"]["episode_id"], files, truth, prov), mapping
