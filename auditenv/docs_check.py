"""docs-check: numbers quoted in README/DESIGN/LIMITATIONS/FAILURES must match reality.

Every number that can go stale is wrapped in an invisible marker (rendered Markdown hides it):

    <!--fact:n_tests-->312<!--/fact-->

`python -m auditenv docs-check` recomputes every fact and fails on any mismatch or unknown fact
name; `--fix` rewrites the values in place. Facts come from the repository itself (pytest
collection, committed trajectories and episodes, the last self-check report, code constants),
so the check is offline and deterministic.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

from .paths import CONFIGS_DIR, EPISODES_DIR, ROOT

DOCS = ["README.md", "docs/DESIGN.md", "docs/LIMITATIONS.md", "docs/FAILURES.md", "docs/CONTRACT.md",
        "docs/ADAPTER.md", "docs/SUBMISSION.md", "docs/HOWTO_EXTEND.md", "docs/MANUAL_AUDIT.md",
        "docs/PROJECT.md", "docs/ATTACKS.md", "docs/EXPERIMENT.md", "README.en.md", "docs/DESIGN_SHORT.md",
        "docs/SAFETY.md", "docs/SUBMISSION_FORM.md", "docs/JURY.md", "docs/DATASHEET.md"]
FACT_RE = re.compile(r"<!--fact:([a-z0-9_]+)-->(.*?)<!--/fact-->", re.S)


def _n_tests() -> str:
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True,
                         text=True, timeout=600).stdout
    m = re.search(r"(\d+) tests? collected", out)
    if m:
        return m.group(1)
    per_file = re.findall(r"^tests/\S+: (\d+)$", out, re.M)  # pytest.ini adds -q, so output is per file
    return str(sum(map(int, per_file))) if per_file else "?"


def _traj():
    path = ROOT / "trajectories" / "trajectories.jsonl"
    lines = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]
    return lines


def _episode_sizes():
    led, docs, iss = [], [], []
    for split in ("train", "dev"):
        for e in json.loads((EPISODES_DIR / split / "index.json").read_text("utf-8")):
            m = json.loads((EPISODES_DIR / split / e["episode_id"] / "public" / "manifest.json").read_text("utf-8"))
            t = json.loads((EPISODES_DIR / split / e["episode_id"] / "grader" / "truth.json").read_text("utf-8"))
            led.append(m["counts"]["ledger"])
            docs.append(m["counts"]["invoices"] + m["counts"]["payments"])
            iss.append(len(t["issues"]))
    return led, docs, iss


def _rng(xs) -> str:
    return f"{min(xs)}–{max(xs)}"


def compute_facts(need: set) -> dict:
    facts = {}
    lazy = {}

    def get(name, fn):
        if name not in lazy:
            lazy[name] = fn()
        return lazy[name]

    for name in sorted(need):
        if name == "n_tests":
            facts[name] = _n_tests()
        elif name == "traj_lines":
            facts[name] = str(len(get("traj", _traj)))
        elif name == "traj_runs":
            facts[name] = str(len({x["run_id"] for x in get("traj", _traj)}))
        elif name == "traj_policies":
            facts[name] = ", ".join(sorted({x["policy"] for x in get("traj", _traj)}))
        elif name in ("ep_ledger_range", "ep_docs_range", "ep_issues_range", "ep_clean_count"):
            led, docs, iss = get("sizes", _episode_sizes)
            facts[name] = {"ep_ledger_range": _rng(led), "ep_docs_range": _rng(docs), "ep_issues_range": _rng(iss),
                           "ep_clean_count": str(sum(1 for i in iss if i == 0))}[name]
        elif name == "selfcheck_total":
            rep = json.loads((ROOT / "reports" / "selfcheck.json").read_text("utf-8"))
            facts[name] = f"{rep['total']:.0f}/{rep['max_total']}"
        elif name == "n_timezones":
            from .timeutil import TIMEZONES

            facts[name] = str(len(TIMEZONES))
        elif name == "n_distractors":
            from .generator.story import DISTRACTOR_KINDS

            facts[name] = str(len(DISTRACTOR_KINDS))
        elif name == "n_attacks":
            from .policies.attacks import ATTACKS

            facts[name] = str(len(ATTACKS))
        elif name == "n_error_types":
            from .generator.errors import REGISTRY

            facts[name] = str(len(REGISTRY))
        elif name == "period_months_range":
            from .config import load_config

            ms = []
            for p in sorted(CONFIGS_DIR.glob("*.json")):
                if _is_cfg(p):
                    pm = load_config(p)["period_months"]
                    ms += pm if isinstance(pm, list) else [pm]
            facts[name] = str(ms[0]) if min(ms) == max(ms) else _rng(ms)
        elif name == "mutation_killed":
            rep = json.loads((ROOT / "reports" / "mutation.json").read_text("utf-8"))
            facts[name] = f"{rep['killed']}/{rep['total']}"
        elif name == "verify_independent_episodes":
            from .cli import episode_dirs
            from .selfcheck import load_split

            facts[name] = str(len(episode_dirs()) + len(load_split("selfcheck")) + _check_seeds())
        elif name == "failures_closed":
            t = (ROOT / "docs" / "FAILURES.md").read_text("utf-8").split("## 2.", 1)[0]
            facts[name] = str(len(re.findall(r"^\| \d+ \|", t, re.M)))
        elif name == "jury_sim_open":
            facts[name] = str(len(_jury_sim_open()))
        elif name == "isolation_layers":
            from . import cli, runner

            layers = [getattr(runner, "harden_evaluator", None), getattr(runner, "_can_drop_privileges", None),
                      getattr(cli, "conceal_run_args", None)]
            facts[name] = str(sum(1 for x in layers if callable(x)))
        elif name == "n_wheels":
            facts[name] = str(len(list((ROOT / "vendor" / "wheels").glob("*.whl"))))
        elif name.startswith("ds_"):
            facts[name] = get("datasheet", _datasheet).get(name)
        elif name == "n_configs":
            facts[name] = str(sum(1 for p in CONFIGS_DIR.glob("*.json") if _is_cfg(p)))
        else:
            facts[name] = None
    return facts


def _datasheet() -> dict:
    """Numbers of docs/DATASHEET.md, all from the committed open episodes and their index files."""
    from collections import Counter

    eps = []
    for split in ("train", "dev"):
        for e in json.loads((EPISODES_DIR / split / "index.json").read_text("utf-8")):
            d = EPISODES_DIR / split / e["episode_id"]
            m = json.loads((d / "public" / "manifest.json").read_text("utf-8"))
            tr = json.loads((d / "grader" / "truth.json").read_text("utf-8"))
            pv = json.loads((d / "grader" / "provenance.json").read_text("utf-8"))
            size = sum(p.stat().st_size for p in (d / "public").iterdir())
            eps.append((split, e, m, tr, pv, size))

    def cnt(c):
        return ", ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))

    types = Counter(i["type"] for *_, tr, _, _ in eps for i in tr["issues"])
    variants = Counter(f"{mu['type']}/{mu.get('variant', '?')}" for *_, pv, _ in eps for mu in pv["mutations"])
    sets = [len(i["evidence_sets"]) for *_, tr, _, _ in eps for i in tr["issues"]]
    set_sizes = [len(s) for *_, tr, _, _ in eps for i in tr["issues"] for s in i["evidence_sets"]]
    amounts = [i["expected_amount_minor"] for *_, tr, _, _ in eps for i in tr["issues"]]
    starts = sorted(m["period_start"][:10] for _, _, m, *_ in eps)
    ends = sorted(m["period_end"][:10] for _, _, m, *_ in eps)
    return {
        "ds_n_episodes": str(len(eps)),
        "ds_n_train": str(sum(1 for x in eps if x[0] == "train")),
        "ds_n_dev": str(sum(1 for x in eps if x[0] == "dev")),
        "ds_configs": cnt(Counter(e["config"] for _, e, *_ in eps)),
        "ds_ledger_total": str(sum(m["counts"]["ledger"] for _, _, m, *_ in eps)),
        "ds_invoices_total": str(sum(m["counts"]["invoices"] for _, _, m, *_ in eps)),
        "ds_payments_total": str(sum(m["counts"]["payments"] for _, _, m, *_ in eps)),
        "ds_fx_total": str(sum(m["counts"]["fx"] for _, _, m, *_ in eps)),
        "ds_public_mb": f"{sum(x[5] for x in eps) / 1e6:.1f}",
        "ds_issues_total": str(sum(types.values())),
        "ds_issue_types": cnt(types),
        "ds_variants": str(len(variants)),
        "ds_base_currencies": cnt(Counter(m["base_currency"] for _, _, m, *_ in eps)),
        "ds_timezones": cnt(Counter(m["timezone"] for _, _, m, *_ in eps)),
        "ds_period_span": f"{starts[0]} … {ends[-1]}",
        "ds_evidence_sets_range": _rng(sets) if sets else "—",
        "ds_evidence_size_range": _rng(set_sizes) if set_sizes else "—",
        "ds_amount_range": f"{min(amounts)}–{max(amounts)}" if amounts else "—",
    }


def _check_seeds() -> int:
    """Fresh seeds that `make check` gives verify-independent (cmd_check: class V)."""
    src = (ROOT / "auditenv" / "cli.py").read_text("utf-8")
    return int(re.search(r'seeds = getattr\(a, "seeds", (\d+)\)', src).group(1))


def _jury_sim_open() -> list:
    """Rows of the status table in reports/jury_sim.md that are neither closed, verified nor a recorded decision."""
    t = (ROOT / "reports" / "jury_sim.md").read_text("utf-8")
    sec = t.split("## Статус после исправлений", 1)[1].split("\n## ", 1)[0]
    rows = [r for r in sec.splitlines() if re.match(r"^\| \d+ \|", r)]
    done = ("закрыто", "проверено", "осознанно", "оставлено")
    return [r for r in rows if not any(w in r.split("|")[3] for w in done)]


def _is_cfg(p) -> bool:
    raw = json.loads(p.read_text("utf-8"))
    return isinstance(raw, dict) and "name" in raw and "version" in raw


def scan():
    found = []
    for rel in DOCS:
        p = ROOT / rel
        if p.exists():
            for m in FACT_RE.finditer(p.read_text("utf-8")):
                found.append((rel, m.group(1), m.group(2)))
    return found


def main(argv=None) -> int:
    fix = "--fix" in (argv or sys.argv[1:])
    found = scan()
    facts = compute_facts({n for _, n, _ in found})
    bad = 0
    for rel, name, shown in found:
        want = facts[name]
        if want is None:
            print(f"docs-check: {rel}: unknown fact '{name}'")
            bad += 1
        elif shown != want and not fix:
            print(f"docs-check: {rel}: {name} says {shown!r}, reality is {want!r}")
            bad += 1
    if fix:
        for rel in DOCS:
            p = ROOT / rel
            if p.exists():
                t = p.read_text("utf-8")
                t2 = FACT_RE.sub(lambda m: f"<!--fact:{m.group(1)}-->{facts.get(m.group(1)) or m.group(2)}<!--/fact-->", t)
                if t2 != t:
                    p.write_text(t2, "utf-8")
                    print(f"docs-check: fixed {rel}")
    print(f"docs-check: {len(found)} facts in {len({r for r, _, _ in found})} documents, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
