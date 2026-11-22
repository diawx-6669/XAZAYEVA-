"""Shortcut probe: can a model find the injected errors from the FORM of the records, without accounting?

If the generator left a tell - injected documents sit at the end of the file, get later-sorting IDs, have
round seconds, another UTC-offset style, rounder amounts - an agent could score without auditing. This tool
trains a learner on format-only features of every document and ledger row of open-style episodes (label: the
record belongs to an affected document of truth.json) and measures ROC AUC on held-out seeds.

  AUC ~ 0.5  -> the form of the records carries no information about where the errors are.
  AUC >> 0.5 -> a shortcut; the feature table below names it.

An AUC of 0.5 proves nothing if the learner is weak, so the same pipeline runs a POSITIVE CONTROL: the
held-out and training data get a planted tell (affected records moved to the last tenth of their file,
which is what a generator that appends injected documents would do). The probe must catch it (AUC > 0.9).

Features are deliberately not accounting: no accounts, no amounts compared across records, no dates compared
to the period, no currencies. Those carry legitimate signal - that is the audit itself.

Stdlib only (logistic regression by gradient descent, rank AUC, episode-level bootstrap).

    python tools/shortcut_probe.py [--train 120] [--test 120] [--out reports/shortcut_probe.md]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auditenv.config import load_config  # noqa: E402
from auditenv.env.data import PublicData  # noqa: E402
from auditenv.generator.episode import generate_episode  # noqa: E402

CONFIGS = ("dev-mixed", "interaction-heavy", "train-easy")
FEATURES = ("position_in_file", "id_rank", "doc_id_rank", "id_length", "seconds", "seconds_is_zero", "minute",
            "utc_offset_written_as_zero", "amount_trailing_zeros", "n_line_items")


def _trailing_zeros(n: int) -> int:
    n, k = abs(int(n)), 0
    if n == 0:
        return 0
    while n % 10 == 0:
        n //= 10
        k += 1
    return k


def _ts_parts(ts: str):
    # "2026-08-03T10:13:00+04:00" -> seconds, minute, offset-is-zero; independent of the period and zone
    sec, minute = int(ts[17:19]), int(ts[14:16])
    return sec, minute, ts.endswith("+00:00") or ts.endswith("Z")


def _rank(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    r = [0.0] * len(values)
    for k, i in enumerate(order):
        r[i] = k / max(1, len(values) - 1)
    return r


def records(data: PublicData, affected: dict):
    """(table, features, label) for every invoice, payment and ledger row; label = issue type or None."""
    out = []
    tables = (("invoices", data.invoices, "invoice_id", "issued_at", "total_minor"),
              ("payments", data.payments, "payment_id", "timestamp", "amount_minor"))
    for name, rows, key, ts_key, amt_key in tables:
        if not rows:
            continue
        id_rank, doc_rank = _rank([r[key] for r in rows]), _rank([r["doc_id"] for r in rows])
        for i, r in enumerate(rows):
            sec, minute, z = _ts_parts(r[ts_key])
            out.append((name, [i / max(1, len(rows) - 1), id_rank[i], doc_rank[i], len(r[key]), sec / 59,
                               float(sec == 0), minute / 59, float(z), _trailing_zeros(r[amt_key]),
                               len(r.get("line_items") or [])], affected.get(r[key])))
    rows = data.ledger
    id_rank = _rank([r["row_id"] for r in rows])
    for i, r in enumerate(rows):
        sec, minute, z = _ts_parts(r["timestamp"])
        amt = int(r["debit_minor"] or 0) or int(r["credit_minor"] or 0)
        label = affected.get(r.get("invoice_id")) or affected.get(r.get("payment_id"))
        out.append(("ledger", [i / max(1, len(rows) - 1), id_rank[i], id_rank[i], len(r["row_id"]), sec / 59,
                               float(sec == 0), minute / 59, float(z), _trailing_zeros(amt), 0.0], label))
    return out


def dataset(seeds, configs=CONFIGS):
    """List of episodes, each a list of (table, x, y)."""
    eps = []
    for cname in configs:
        cfg = load_config(cname)
        for s in seeds:
            ep = generate_episode(s, cfg)
            # later issues on the same id (partial_fx_cutoff: fx_rate + payment_allocation) keep the last type
            affected = {a: i["type"] for i in ep.truth["issues"] for a in i["affected_ids"]}
            eps.append(records(PublicData(ep.files), affected))
    return eps


def plant_tell(eps, seed=0):
    """Positive control: affected records moved into the last tenth of their file (position feature)."""
    rng = random.Random(seed)
    return [[(t, ([0.9 + 0.1 * rng.random()] + x[1:]) if y else x, y) for t, x, y in ep] for ep in eps]


def known_tell(r) -> dict:
    """The one format tell this probe found (see the report): seconds == 0 on partially applied receipts."""
    rates = r["real"]["rates"]
    alloc, clean = rates.get("payments:payment_allocation"), rates["payments:clean"]
    return {"payment_allocation_seconds_zero": alloc["seconds_zero"] / alloc["n"] if alloc else None,
            "clean_payment_seconds_zero": clean["seconds_zero"] / clean["n"]}


def _standardize(train_x, test_x):
    k = len(train_x[0])
    mu = [sum(x[j] for x in train_x) / len(train_x) for j in range(k)]
    sd = [math.sqrt(sum((x[j] - mu[j]) ** 2 for x in train_x) / len(train_x)) or 1.0 for j in range(k)]
    f = lambda xs: [[(x[j] - mu[j]) / sd[j] for j in range(k)] for x in xs]  # noqa: E731
    return f(train_x), f(test_x)


def _expand(x):
    # squares let a linear learner catch "near the end" / "near the start" tells, not only monotone ones
    return x + [v * v for v in x]


def fit_logreg(xs, ys, iters=300, lr=0.5, l2=1e-3):
    k = len(xs[0])
    w, b = [0.0] * k, 0.0
    pos = sum(ys) or 1
    neg = (len(ys) - sum(ys)) or 1
    cw = [0.5 / pos if y else 0.5 / neg for y in ys]  # class-balanced
    for _ in range(iters):
        gw, gb = [l2 * v for v in w], 0.0
        for x, y, c in zip(xs, ys, cw):
            z = b + sum(wi * xi for wi, xi in zip(w, x))
            p = 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))
            e = (p - y) * c
            gb += e
            for j in range(k):
                gw[j] += e * x[j]
        b -= lr * gb
        w = [wi - lr * g for wi, g in zip(w, gw)]
    return w, b


def auc(scores, labels):
    """Rank (Mann-Whitney) AUC with ties counted as 1/2."""
    pairs = sorted(zip(scores, labels))
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if not n_pos or not n_neg:
        return float("nan")
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg = (i + j + 1) / 2
        rank_sum += avg * sum(1 for t in range(i, j) if pairs[t][1])
        i = j
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def evaluate(train_eps, test_eps, boot=200, seed=0):
    tr = [r for ep in train_eps for r in ep]
    tx, ty = [_expand(x) for _, x, _ in tr], [int(bool(y)) for _, _, y in tr]
    test_flat = [(i, r) for i, ep in enumerate(test_eps) for r in ep]
    vx = [_expand(r[1]) for _, r in test_flat]
    sx, svx = _standardize(tx, vx)
    w, b = fit_logreg(sx, ty)
    scores = [b + sum(wi * xi for wi, xi in zip(w, x)) for x in svx]
    labels = [int(bool(r[2])) for _, r in test_flat]
    point = auc(scores, labels)
    by_ep = {}
    for (i, _), s, y in zip(test_flat, scores, labels):
        by_ep.setdefault(i, []).append((s, y))
    rng, ids, vals = random.Random(seed), sorted(by_ep), []
    for _ in range(boot):
        pick = [rng.choice(ids) for _ in ids]
        ss = [p for i in pick for p in by_ep[i]]
        a = auc([s for s, _ in ss], [y for _, y in ss])
        if a == a:
            vals.append(a)
    vals.sort()
    lo, hi = vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]
    # univariate AUC of every raw feature on the test set (direction-free: max(a, 1-a))
    uni = {}
    for j, name in enumerate(FEATURES):
        a = auc([r[1][j] for _, r in test_flat], labels)
        uni[name] = max(a, 1 - a) if a == a else float("nan")
    rates = {}
    for _, (table, x, y) in test_flat:
        k = rates.setdefault(f"{table}:{y or 'clean'}", {"n": 0, "seconds_zero": 0, "utc_written": 0, "round_2": 0})
        k["n"] += 1
        k["seconds_zero"] += x[5] == 1.0
        k["utc_written"] += x[7] == 1.0
        k["round_2"] += x[8] >= 2
    return {"auc": point, "ci95": [lo, hi], "n_test_records": len(labels), "n_test_positive": sum(labels),
            "univariate_auc": uni, "rates": rates}


def run(n_train=120, n_test=120):
    train = dataset(range(700000, 700000 + n_train))
    test = dataset(range(800000, 800000 + n_test))
    real = evaluate(train, test)
    control = evaluate(plant_tell(train, 1), plant_tell(test, 2))
    return {"n_train_seeds": n_train, "n_test_seeds": n_test, "configs": list(CONFIGS), "real": real,
            "positive_control": control}


def render(r) -> str:
    real, ctl = r["real"], r["positive_control"]
    weak = real["auc"] < 0.7
    verdict = ("no shortcut found" if real["ci95"][0] <= 0.5 <= real["ci95"][1] else
               "weak format signal, explained below (no strong shortcut)" if weak else
               "STRONG SHORTCUT: fix the generator")
    kt = known_tell(r)
    lines = [
        "# Shortcut probe: do the records give the errors away by their form?",
        "",
        "Generated by `python tools/shortcut_probe.py` (`make shortcut-probe`). Deterministic: fixed seeds.",
        "",
        f"Learner: logistic regression on {len(FEATURES)} format-only features (+ squares), trained on "
        f"{r['n_train_seeds']} seeds x {len(r['configs'])} configs ({', '.join(r['configs'])}), tested on "
        f"{r['n_test_seeds']} other seeds x the same configs. Label: the record is an affected document of "
        "truth.json or a ledger row posting it. 95% interval: bootstrap over test episodes.",
        "",
        "| Run | ROC AUC | 95% interval | test records | of them affected |",
        "|---|---|---|---|---|",
        f"| real episodes | **{real['auc']:.3f}** | {real['ci95'][0]:.3f} - {real['ci95'][1]:.3f} | "
        f"{real['n_test_records']} | {real['n_test_positive']} |",
        f"| positive control (planted tell: affected records at the end of the file) | **{ctl['auc']:.3f}** | "
        f"{ctl['ci95'][0]:.3f} - {ctl['ci95'][1]:.3f} | {ctl['n_test_records']} | {ctl['n_test_positive']} |",
        "",
        f"Verdict: **{verdict}**. The control shows the probe is strong enough to see a tell when one exists.",
        "",
        "## Each feature on its own (real episodes, max(AUC, 1 - AUC))",
        "",
        "| Feature | AUC |",
        "|---|---|",
    ]
    for name in FEATURES:
        lines.append(f"| `{name}` | {real['univariate_auc'][name]:.3f} |")
    lines += [
        "",
        "Not used on purpose (legitimate audit signal, not a shortcut): accounts (2400 means unapplied cash), "
        "currencies (an FX error needs a foreign document), dates against the period boundary (that is the "
        "cutoff test), amounts compared between records (that is the duplicate test).",
        "",
        "## Where the signal comes from (test episodes)",
        "",
        "| Records | n | seconds = 00 | written in UTC (+00:00) | amount ends in >= 2 zeros |",
        "|---|---|---|---|---|",
    ]
    for key in sorted(real["rates"]):
        v = real["rates"][key]
        lines.append(f"| {key} | {v['n']} | {v['seconds_zero'] / v['n']:.1%} | {v['utc_written'] / v['n']:.1%} | "
                     f"{v['round_2'] / v['n']:.1%} |")
    lines += [
        "",
        "Three sources, two of them legitimate:",
        "",
        "1. **Written in UTC** is part of the error, not a tell: a `period_cutoff` utc_trap exists only because the "
        "invoice time is written in UTC and its UTC date differs from the local one; the `partial_fx_cutoff` "
        "receipt is the same trap on a payment. The generator writes the look-alikes `boundary_end`, "
        "`boundary_start` and `night_fx` in UTC too, so UTC writing alone is a weak signal (see the rates).",
        "2. **Round amounts** are a currency proxy: foreign documents are converted, so their base-currency "
        "postings are rarely round; an FX error needs a foreign document. Legitimate.",
        "3. **Seconds = 00 on partially applied receipts is a real tell.** The carrier payment of "
        "`partial_fx_cutoff` (`auditenv/generator/story.py`, carriers block) is timestamped "
        "`midnight + timedelta(minutes=...)` without seconds, so its seconds are always 00: "
        f"{kt['payment_allocation_seconds_zero']:.1%} of `payment_allocation` receipts vs "
        f"{kt['clean_payment_seconds_zero']:.1%} of clean receipts. The same 00 seconds also mark records "
        "built at a fixed minute that are NOT errors - the look-alikes `boundary_end` / `boundary_start` "
        "(23:50 and 00:05 local) - which is why clean invoices have more 00-second timestamps than "
        "duplicates. So it is weak as a strategy: most 00-second records are clean, and flagging them "
        "costs false positives (one FP outweighs 333 steps, `docs/AUDIT_STANDARDS.md` section 3); it does "
        "not touch the grader. Fix for v1.1: draw the seconds like every other timestamp. Not fixed in "
        "the submission because it changes the bytes of committed episodes, golden hashes and trajectories; "
        "`tests/test_shortcut_probe.py` pins it, so the fix will show up as a deliberate test change.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=120)
    ap.add_argument("--test", type=int, default=120)
    ap.add_argument("--out", default=str(ROOT / "reports" / "shortcut_probe.md"))
    a = ap.parse_args(argv)
    r = run(a.train, a.test)
    Path(a.out).write_text(render(r), "utf-8")
    Path(a.out).with_suffix(".json").write_text(json.dumps(r, sort_keys=True, indent=1) + "\n", "utf-8")
    print(f"shortcut-probe: real AUC {r['real']['auc']:.3f} [{r['real']['ci95'][0]:.3f}, {r['real']['ci95'][1]:.3f}], "
          f"positive control {r['positive_control']['auc']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
