"""Measurements over many generated episodes (no truth is used by the features themselves).

1. Surface-feature detector (round 2, B3): for every invoice/payment we compute cheap features a
   lazy agent might key on ("paid", "night", "UTC-formatted time", "service_period differs from the
   written issue month", "rent text", "exactly one payment", "unusual ID prefix", ...) and measure how
   well each feature ALONE separates erroneous documents (the affected_ids of truth) from correct
   ones: precision = P(error | feature), recall = P(feature | error). A feature with both above the
   threshold would be a shortcut; tests/test_surface.py fails if one appears.
2. Variant table: how often each type/variant occurs and simple_reconcile's recall on it.

    python -m auditenv analyze --n 300            # prints both tables (markdown)
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

MIX = ["dev-mixed", "interaction-heavy", "dev-global", "clean-only", "train-easy", "train-global"]
THRESHOLD = 0.6


def plan(n: int, base_seed: int = 70000) -> list:
    """n (config, seed) pairs cycling through the open configs (never the committed split seeds)."""
    return [(MIX[i % len(MIX)], base_seed + i) for i in range(n)]


def _gen(item):
    from .generator.episode import generate_episode

    cfg, seed = item
    ep = generate_episode(seed, cfg)
    return cfg, seed, ep.files, ep.truth, ep.provenance["mutations"]


def generate_many(items, workers=None):
    workers = workers or min(4, os.cpu_count() or 1)
    if workers <= 1:
        return [_gen(x) for x in items]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(_gen, items, chunksize=8))


# ----------------------------------------------------------------- features
def doc_features(pd) -> dict:
    """{doc key (invoice_id/payment_id): {feature: bool}} from PUBLIC data only."""
    from collections import Counter

    pays_for = Counter()
    for p in pd.payments:
        for ref in p["invoice_refs"] or []:
            pays_for[ref] += 1
    prefix = Counter(i["invoice_id"].split("-")[0] for i in pd.invoices)
    pprefix = Counter(p["payment_id"].split("-")[0] for p in pd.payments)
    out = {}

    def common(ts):
        loc = pd.local(ts)
        return {"night": loc.hour < 7 or loc.hour >= 22, "utc_format": ts.endswith("+00:00"),
                "weekend": loc.weekday() >= 5, "last_3_days": (pd.period_end - loc).days < 3}

    for inv in pd.invoices:
        f = common(inv["issued_at"])
        written_month = inv["issued_at"][:7]
        f.update({
            "paid": pays_for[inv["invoice_id"]] > 0,
            "single_payment": pays_for[inv["invoice_id"]] == 1,
            "service_period_ne_issue_month": any(li["service_period"] != written_month for li in inv["line_items"]),
            "rent_text": any("rent" in li["description"].lower() for li in inv["line_items"]),
            "foreign_currency": inv["currency"] != pd.base,
            "odd_id_prefix": prefix[inv["invoice_id"].split("-")[0]] < max(prefix.values()),
        })
        out[inv["invoice_id"]] = f
    for p in pd.payments:
        f = common(p["timestamp"])
        f.update({"paid": bool(p["invoice_refs"]), "single_payment": bool(p["invoice_refs"]) and len(p["invoice_refs"]) == 1,
                  "service_period_ne_issue_month": False, "rent_text": False,
                  "foreign_currency": p["currency"] != pd.base,
                  "odd_id_prefix": pprefix[p["payment_id"].split("-")[0]] < max(pprefix.values())})
        out[p["payment_id"]] = f
    return out


FEATURES = ["paid", "night", "utc_format", "service_period_ne_issue_month", "rent_text", "single_payment",
            "odd_id_prefix", "weekend", "last_3_days", "foreign_currency"]
TYPES = ["duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff"]


def surface_table(results) -> dict:
    """{(feature, scope): (tp, fp, fn, precision, recall)}; scope = 'any' or an error type."""
    from .env.data import PublicData

    counts = {}
    for _, _, files, truth, _ in results:
        pd = PublicData(files)
        feats = doc_features(pd)
        labels = {}
        for iss in truth["issues"]:
            for a in iss["affected_ids"]:
                labels.setdefault(a, set()).add(iss["type"])
        for key, f in feats.items():
            lab = labels.get(key, set())
            for feat in FEATURES:
                for scope in ["any"] + TYPES:
                    pos = bool(lab) if scope == "any" else scope in lab
                    c = counts.setdefault((feat, scope), [0, 0, 0])
                    if f[feat] and pos:
                        c[0] += 1
                    elif f[feat]:
                        c[1] += 1
                    elif pos:
                        c[2] += 1
    out = {}
    for k, (tp, fp, fn) in counts.items():
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        out[k] = (tp, fp, fn, p, r)
    return out


def shortcuts(table, threshold=THRESHOLD) -> list:
    return sorted(k for k, (_, _, _, p, r) in table.items() if p > threshold and r > threshold)


def variant_table(results) -> dict:
    """{(type, variant): [count, found_by_simple_reconcile]}"""
    from .generator.episode import Episode
    from .runner import run_episode

    out = {}
    for cfg, seed, files, truth, muts in results:
        ep = Episode(truth["episode_id"], files, truth, {})
        g = run_episode("simple_reconcile", episode=ep, isolate=False, record=False)["grade"]
        found = {f["matched"] for f in g["findings"] if f["matched"]}
        for m in muts:
            c = out.setdefault((m["type"], m["variant"]), [0, 0])
            c[0] += 1
            c[1] += m["issue_id"] in found
    return out


def render_surface(n, surface) -> str:
    L = [f"Замер: {n} эпизодов (`python -m auditenv analyze --n {n} --docs`), документы = счета и платежи.", "",
         f"Признак «отделяет» ошибки, если и precision, и recall > {THRESHOLD}. Столбцы: P/R по всем ошибкам и "
         "лучший P/R по отдельному типу.", "",
         "| Признак | P (все) | R (все) | худший тип | P | R | ярлык? |", "|---|---|---|---|---|---|---|"]
    for feat in FEATURES:
        _, _, _, p, r = surface[(feat, "any")]
        worst = max(TYPES, key=lambda t: min(surface[(feat, t)][3], surface[(feat, t)][4]))
        _, _, _, pt, rt = surface[(feat, worst)]
        flag = "ДА" if (p > THRESHOLD and r > THRESHOLD) or (pt > THRESHOLD and rt > THRESHOLD) else "нет"
        L.append(f"| {feat} | {p:.2f} | {r:.2f} | {worst} | {pt:.2f} | {rt:.2f} | {flag} |")
    return "\n".join(L)


def render_variants(n, variants) -> str:
    L = [f"Замер: {n} эпизодов (`python -m auditenv analyze --n {n} --docs`), режим train.", "",
         "| Тип / вариант | Встречается | Найдено simple_reconcile | Recall |", "|---|---|---|---|"]
    for (t, v), (c, f) in sorted(variants.items()):
        L.append(f"| {t} / {v} | {c} | {f} | {f / c:.0%} |")
    tot = sum(c for c, _ in variants.values())
    fnd = sum(f for _, f in variants.values())
    L += [f"| **итого** | **{tot}** | **{fnd}** | **{fnd / tot:.0%}** |" if tot else ""]
    return "\n".join(L)


BLOCKS = {"surface": "docs/LIMITATIONS.md", "variants": "docs/FAILURES.md"}


def write_docs(blocks: dict):
    """Replace <!--generated:NAME--> ... <!--/generated--> blocks in the docs."""
    import re

    from .paths import ROOT

    for name, rel in BLOCKS.items():
        p = ROOT / rel
        t = p.read_text("utf-8")
        pat = re.compile(r"(<!--generated:%s-->\n).*?(<!--/generated-->)" % name, re.S)
        if not pat.search(t):
            raise SystemExit(f"{rel}: no <!--generated:{name}--> block")
        p.write_text(pat.sub(lambda m: m.group(1) + blocks[name] + "\n" + m.group(2), t), "utf-8")


def main(n=300, out=None, docs=False) -> str:
    res = generate_many(plan(n))
    blocks = {"surface": render_surface(n, surface_table(res)), "variants": render_variants(n, variant_table(res))}
    md = "## Поверхностные признаки\n\n" + blocks["surface"] + "\n\n## Типы и варианты\n\n" + blocks["variants"] + "\n"
    if out:
        from pathlib import Path

        Path(out).write_text(md, "utf-8")
    if docs:
        write_docs(blocks)
    return md
