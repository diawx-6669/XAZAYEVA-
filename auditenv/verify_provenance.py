"""verify-provenance: the recorded causal history must explain the books exactly.

From public/ + grader/provenance.json alone:
  1. undo the mutations in REVERSE order (each mutation stores before/after snapshots of every
     document and ledger row it touched) -> the reconstructed clean book;
  2. the reconstructed book must equal the clean book regenerated from (seed, config) record by
     record, and satisfy every invariant;
  3. re-apply the mutations one at a time: after mutation k the violated invariants must be exactly
     those of mutations 1..k, each by its expected_amount_minor (from truth.json).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from .canon import dumps
from .env.data import PublicData
from .generator.export import parse_files, read_public_files, serialize_tables
from .generator.invariants import violated
from .grader.validate_truth import TYPE_OF_INVARIANT

INV_OF_TYPE = {v: k for k, v in TYPE_OF_INVARIANT.items()}


def _apply(t: dict, src: dict, dst: dict) -> None:
    """Replace snapshot `src` (document + rows) by snapshot `dst` in tables t."""
    for snap, add in ((src, False), (dst, True)):
        doc = snap.get("document")
        rows = snap.get("rows") or []
        if not add:
            if doc is not None:
                table = "invoices" if "invoice_id" in doc else "payments"
                t[table] = [d for d in t[table] if d["doc_id"] != doc["doc_id"]]
            ids = {r["row_id"] for r in rows}
            t["ledger"] = [r for r in t["ledger"] if r["row_id"] not in ids]
        else:
            if doc is not None:
                t["invoices" if "invoice_id" in doc else "payments"].append(copy.deepcopy(doc))
            t["ledger"].extend(copy.deepcopy(rows))


def _pd(t: dict) -> PublicData:
    t = copy.deepcopy(t)
    t["manifest"]["counts"] = {"ledger": len(t["ledger"]), "invoices": len(t["invoices"]),
                               "payments": len(t["payments"]), "fx": len(t["fx"])}
    return PublicData(serialize_tables(t))


def _record_set(t: dict) -> dict:
    return {k: sorted(dumps(r) for r in t[k]) for k in ("ledger", "invoices", "payments", "fx")}


def verify(files: dict, truth: dict, provenance: dict, regenerate: bool = True) -> dict:
    problems = []
    t = parse_files(files)
    muts = sorted(provenance["mutations"], key=lambda m: m["order"])
    issues = {i["issue_id"]: i for i in truth["issues"]}
    for m in reversed(muts):
        for before, after in zip(m["before"], m["after"]):
            _apply(t, after, before)
    clean = copy.deepcopy(t)
    if violated(_pd(clean)):
        problems.append(f"reconstructed clean book violates {sorted(violated(_pd(clean)))}")
    if regenerate and not provenance.get("seed_salted"):
        from .generator.episode import generate_episode

        ep = generate_episode(provenance["seed"], provenance["config"])
        if _record_set(parse_files(ep.clean_files)) != _record_set(clean):
            problems.append("reconstructed clean book differs from the regenerated one")
    want: dict = {}
    for m in muts:
        for before, after in zip(m["before"], m["after"]):
            _apply(t, before, after)
        iss = issues[m["issue_id"]]
        want.setdefault(INV_OF_TYPE[iss["type"]], {})[iss["affected_ids"][0]] = iss["expected_amount_minor"]
        got = violated(_pd(t))
        if got != want:
            problems.append(f"after {m['issue_id']} ({m['type']}/{m['variant']}): violations {got} != declared {want}")
            break
    if _record_set(t) != _record_set(parse_files(files)):
        problems.append("re-applying the mutations does not give the published books")
    return {"episode_id": truth["episode_id"], "mutations": len(muts), "ok": not problems, "problems": problems}


def verify_dir(d) -> dict:
    d = Path(d)
    files = read_public_files(d / "public")
    truth = json.loads((d / "grader" / "truth.json").read_text("utf-8"))
    prov = json.loads((d / "grader" / "provenance.json").read_text("utf-8"))
    return verify(files, truth, prov)
