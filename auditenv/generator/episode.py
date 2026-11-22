"""generate_episode(seed, config) -> Episode(public files, truth, provenance).

Pipeline per attempt: story -> clean book -> coincidence scan (independent solver must find
nothing in the clean book, otherwise regenerate with the next sub-seed) -> error injection
in a fixed order -> export. Every random choice comes from a named sub-seed stream.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .. import GENERATOR_VERSION, SCHEMA_VERSION
from ..config import config_hash, load_config
from ..ids import make_rng
from ..timeutil import fmt_ts
from .books import build_book
from .errors import ORDER, REGISTRY
from .errors.base import weighted_choice
from .export import book_tables, serialize_tables
from .interactions import SCENARIO_TYPES, SCENARIOS
from .story import build_story


class GenerationError(RuntimeError):
    pass


@dataclass
class Episode:
    episode_id: str
    files: dict
    truth: dict
    provenance: dict
    clean_files: dict | None = None
    meta: dict = field(default_factory=dict)

    def public(self):
        from ..env.data import PublicData

        return PublicData(self.files)


def _export(book, cfg, chash, seed, attempt) -> dict:
    return serialize_tables(book_tables(book, cfg, chash, make_rng(seed, "order", attempt)))


def _try_inject(book, fn):
    """Run a mutation on a copy; keep it only if it succeeded (mutations are atomic)."""
    trial = copy.deepcopy(book)
    res = fn(trial)
    if res is None:
        return book, None
    return trial, res


def is_clean_episode(seed, cfg) -> bool:
    """Clean or not is decided ONCE per seed from its own stream, without `attempt`: a regeneration
    (coincidence scan, failed injection) must not flip the episode between clean and erroneous,
    otherwise the clean share would drift away from clean_probability."""
    return make_rng(seed, "clean").random() < cfg["clean_probability"]


def inject_errors(book, seed, cfg, attempt, clean=None):
    r = make_rng(seed, "errors", attempt)
    if clean if clean is not None else is_clean_episode(seed, cfg):
        return book, [], {"clean": True, "ordered": {}, "injected": {}}
    lo, hi = cfg["n_errors"]
    n_target = r.randint(max(lo, 1), max(hi, 1))
    used: set = set()
    injected = []
    plan = {"clean": False, "n_target": n_target, "scenarios": [], "singles": []}
    # 1) interaction scenarios, fixed (alphabetical) order
    wanted = [s for s in sorted(SCENARIOS) if r.random() < cfg["interactions"].get(s, 0.0)]
    if len(wanted) < cfg["min_interactions"]:
        rest = [s for s in sorted(SCENARIOS) if s not in wanted and cfg["interactions"].get(s, 0.0) > 0]
        r.shuffle(rest)
        wanted = sorted(wanted + rest[: cfg["min_interactions"] - len(wanted)])
    for name in wanted:
        if len(injected) + 2 > max(n_target, 2 * cfg["min_interactions"]):
            break
        book, res = _try_inject(book, lambda b: SCENARIOS[name](b, r, cfg, used))
        if res:
            injected.extend(res)
            plan["scenarios"].append(name)
    if len(plan["scenarios"]) < cfg["min_interactions"]:
        return book, None, plan
    # 2) independent errors: choose the multiset of types, then apply in the fixed ORDER
    weights = {k: v for k, v in cfg["errors"].items() if v > 0}
    picks = [weighted_choice(r, weights) for _ in range(max(0, n_target - len(injected)))]
    picks = [p for p in picks if p]
    ordered = {}
    for name in plan["scenarios"]:
        for t in SCENARIO_TYPES[name]:
            ordered[t] = ordered.get(t, 0) + 1
    for t in picks:
        ordered[t] = ordered.get(t, 0) + 1
    for typ in ORDER:
        for _ in range(picks.count(typ)):
            et = REGISTRY[typ]
            cands = et.applicable(book, used)
            if not cands:
                continue
            target = r.choice(cands)

            def run(b, et=et, target=target):
                kw = {"used": frozenset(used)} if typ == "payment_allocation" else {}
                res = et.inject(b, target, r, cfg, **kw)
                return None if res is None else [res]

            book, res = _try_inject(book, run)
            if res:
                injected.extend(res)
                plan["singles"].append(typ)
                used.add(target.split(":")[-1])  # fx_rate targets look like "inv:i012"
                used.update(res[0].touched)
    plan["ordered"] = dict(sorted(ordered.items()))
    got = {}
    for inj in injected:
        got[inj.type] = got.get(inj.type, 0) + 1
    plan["injected"] = dict(sorted(got.items()))
    if not injected:
        return book, None, plan
    return book, injected, plan


def _story_summary(book) -> dict:
    s = book.story
    events = []
    for inv in book.invoices.values():
        events.append({"key": inv.key, "kind": inv.kind, "doc_id": inv.doc_id, "invoice_id": inv.invoice_id,
                       "currency": inv.currency, "total_minor": inv.total, "tags": inv.tags})
    for p in book.payments.values():
        events.append({"key": p.key, "kind": "payment", "doc_id": p.doc_id, "payment_id": p.payment_id,
                       "currency": p.currency, "amount_minor": p.amount, "tags": p.tags,
                       "planned_allocation": [[book.invoices[k].invoice_id, a] for k, a in p.alloc]})
    for rf in book.refunds:
        events.append({"key": rf.key, "kind": "refund", "invoice_id": book.invoices[rf.invoice].invoice_id,
                       "amount_minor": rf.amount})
    return {"timezone": s.tz_name, "base_currency": s.base, "foreign_currencies": s.foreign,
            "period_start": fmt_ts(s.period_start), "period_end": fmt_ts(s.period_end),
            "utc_share_percent": s.utc_share, "distractors": s.distractors, "events": events}


def generate_episode(seed, config=None) -> Episode:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError(f"seed must be an int, got {type(seed).__name__}")
    cfg = load_config(config)
    chash = config_hash(cfg)
    clean = is_clean_episode(seed, cfg)
    rejections = []
    for attempt in range(cfg["max_attempts"]):
        story = build_story(seed, cfg, attempt)
        book = build_book(story, seed, attempt, chash)
        clean_files = _export(book, cfg, chash, seed, attempt)
        from ..env.data import PublicData
        from ..grader.validate_truth import solve

        found = solve(PublicData(clean_files))
        if found["issues"] or found["structural"]:
            rejections.append({"attempt": attempt, "reason": "coincidence_in_clean_book",
                               "found": sorted({i["type"] for i in found["issues"]}) or ["structural"]})
            continue
        book, injected, plan = inject_errors(book, seed, cfg, attempt, clean=clean)
        if injected is None:
            rejections.append({"attempt": attempt, "reason": "injection_failed", "plan": plan})
            continue
        files = _export(book, cfg, chash, seed, attempt)
        issues, mutations = [], []
        for inj in injected:
            # Evidence is read from the FINAL books: a later mutation of the same document (partial_fx_cutoff)
            # may add/replace rows that an earlier issue's alternative set refers to. Amounts stay as measured
            # right before each mutation.
            inj.evidence_sets = REGISTRY[inj.type].evidence_sets(book, inj.target)
        for n, inj in enumerate(injected, start=1):
            iid = f"ISS-{n:03d}"
            issues.append({"issue_id": iid, "type": inj.type, "affected_ids": sorted(inj.affected_ids),
                           "expected_amount_minor": inj.expected_amount_minor, "currency": inj.currency,
                           "evidence_sets": [list(e) for e in inj.evidence_sets]})
            mutations.append({"issue_id": iid, "type": inj.type, "variant": inj.variant, "order": n,
                              "detail": inj.detail, "before": inj.before, "after": inj.after})
        truth = {"episode_id": book.episode_id, "issues": issues, "tolerance_minor": cfg["tolerance_minor"]}
        from ..ids import salted

        provenance = {"seed": seed, "seed_salted": salted(), "attempt": attempt, "rejections": rejections, "config": cfg,
                      "config_hash": chash, "generator_version": GENERATOR_VERSION,
                      "schema_version": SCHEMA_VERSION, "plan": plan, "story": _story_summary(book),
                      "mutations": mutations}
        return Episode(book.episode_id, files, truth, provenance, clean_files=clean_files,
                       meta={"attempt": attempt, "config_name": cfg["name"]})
    raise GenerationError(f"no valid episode for seed={seed} after {cfg['max_attempts']} attempts")
