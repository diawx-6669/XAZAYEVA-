#!/usr/bin/env python3
"""Hand-written mutation testing of the grader (matcher / reward / normalize / schema / core).

Each mutation is one deliberate bug: an exact text replacement in one file. For every mutation the tool
copies the repository to a scratch directory, applies the bug, runs the FAST test suite
(`pytest -m "not slow" -x`) and records whether some test failed ("killed") and which test was first.
A surviving mutation means the tests cannot tell the bug from the real grader -> a test must be added.

    python tools/mutation_test.py [--jobs 4] [--only M01,M07] [--out reports/mutation.md]

Not part of `make check` (it re-runs the fast suite ~20 times); run it with `make mutation`.
Exit code 0 iff every mutation is killed and the unmutated baseline is green.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns(".git", ".venv", "__pycache__", ".hypothesis", ".pytest_cache")

M = "auditenv/grader/matcher.py"
R = "auditenv/grader/reward.py"
N = "auditenv/grader/normalize.py"
S = "auditenv/grader/schema.py"
C = "auditenv/grader/core.py"
J = "schemas/findings.schema.json"

# (id, file, old text, new text, what the bug means)
MUTATIONS = [
    ("M01", M, "issue[\"expected_amount_minor\"]) <= tol", "issue[\"expected_amount_minor\"]) < tol", "amount tolerance: <= becomes < (an exact-boundary claim is rejected)"),
    ("M02", M, '            and f["currency"] == issue["currency"]\n', "",
     "currency is not checked"),
    ("M03", M, '            and satisfied_set(f, issue) is not None)', "            )",
     "evidence is not checked"),
    ("M04", M, 'if set(s) <= f["evidence_ids"]:', 'if set(s) & f["evidence_ids"]:',
     "one ID of an evidence set is enough (subset -> intersection)"),
    ("M05", M, '    return (f["type"] == issue["type"]\n            and ', "    return (",
     "type is not checked"),
    ("M06", M, 'and f["affected_ids"] == sorted(issue["affected_ids"])',
     'and set(f["affected_ids"]) >= set(issue["affected_ids"])',
     "affected_ids: a superset is accepted instead of exact equality"),
    ("M07", M, '    for i in issues:\n        augment(i["issue_id"], set())',
     '    for i in issues:\n        for k in adj[i["issue_id"]]:\n            owner.setdefault(k, i["issue_id"])',
     "no one-to-one matching: every repeat of a correct finding is a TP"),
    ("M08", M, "if k not in owner or augment(owner[k], seen):", "if k not in owner:",
     "greedy matching instead of maximum matching (no augmenting paths)"),
    ("M09", M, 'issues = sorted(issues, key=lambda i: i["issue_id"])',
     'issues = sorted(issues, key=lambda i: i["issue_id"], reverse=True)',
     "tie-break: the LARGER issue_id wins instead of the smaller"),
    ("M10", N, "return sorted({str(s).strip() for s in ids if str(s).strip()})",
     "return sorted({str(s) for s in ids if str(s)})", "IDs are not stripped of whitespace"),
    ("M11", N, "return sorted({str(s).strip() for s in ids if str(s).strip()})",
     "return sorted([str(s).strip() for s in ids if str(s).strip()])", "repeated IDs are not de-duplicated"),
    ("M12", N, "return str(c).strip().upper()", "return str(c).strip()", "currency is not upper-cased"),
    ("M13", N, "return sorted({str(s).strip() for s in ids if str(s).strip()})",
     "return sorted({str(s).strip().upper() for s in ids if str(s).strip()})",
     "IDs are case-folded (the contract says case is preserved)"),
    ("M14", R, "    if n_truth == 0 and n_find == 0:\n        f1 = Fraction(1)",
     "    if n_truth == 0 and n_find == 0:\n        f1 = Fraction(0)", "F1 = 0 when truth and findings are both empty"),
    ("M15", R, "    elif n_truth == 0:\n        f1 = Fraction(0)", "    elif n_truth == 0:\n        f1 = Fraction(1)",
     "F1 = 1 when truth is empty but findings are not (accusing a clean book is free)"),
    ("M16", R, "STEP_COST = Fraction(2, 1000)", "STEP_COST = Fraction(1, 1000)", "step cost 0.001 instead of 0.002"),
    ("M17", R, "return float(max(Fraction(-1), min(Fraction(1), v)))", "return float(v)", "reward is not clipped to [-1, 1]"),
    ("M18", S, 'if type(f["claimed_amount_minor"]) is not int:', "if False:", "float amounts (5.0) are accepted"),
    ("M19", S, "    if obj[\"episode_id\"] != episode_id:\n        return \"episode_id_mismatch\"\n", "",
     "a foreign episode_id is accepted"),
    ("M20", C, "        if truncated:\n            submission = {\"episode_id\": self.episode_id, \"findings\": []}\n", "",
     "a truncated episode is graded on the agent's findings instead of the empty answer"),
    ("M21", J, '"maxItems": 30,', '"maxItems": 3000,', "the 30-findings cap is lifted"),
    ("M23", "auditenv/jsonschema_lite.py", "    if t == \"integer\":\n        return type(value) is int",
     "    if t == \"integer\":\n        return isinstance(value, (int, float))",
     "schema validator: \"integer\" accepts 5.0 and True"),
    ("M22", C, "if set(satisfied_set(findings[k], by_id[iid])) <= set(seen_ids))",
     "if True)", "experimental reward: evidence the agent never saw still counts"),
]

# What earlier runs found (kept in the report so the history of the suite is visible).
HISTORY = [
    "Раунд 3, первый прогон: 20/22 убито. Выжили M05 (тип не проверяется: перебор 4 типов всё равно даёт TP = 1, FP = 3, "
    "поэтому тесты не отличали баг) и M08 (жадное паросочетание вместо максимального: `test_tie_break_smallest_issue_then_index` "
    "заявлял эту проверку, но его пример жадный алгоритм тоже решает). M06 был убит только косвенно, через сканер "
    "совпадений генератора; M18 оказался синтаксически неверным мутантом (исправлен, теперь инструмент проверяет "
    "компиляцию каждого мутанта). Дописаны прямые тесты: `tests/test_mutation_kills.py`.",
    "Второй прогон: 21/22. Исправленный M18 выжил: проверка `type(...) is int` в `grader/schema.py` дублирует строгость "
    "`jsonschema_lite` (\"integer\" не принимает 5.0), поэтому ни один тест не видел второй слой отдельно. Добавлен тест "
    "`test_grader_int_check_works_even_if_the_schema_validator_accepted_floats` (валидатор подменён на «принимаю всё») и "
    "мутация M23 для самого валидатора.",
]

FAIL_RE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)


# Grader-facing test files run first, so the reported killer is the most specific test; then all the rest.
PRIORITY = ["tests/test_reward.py", "tests/test_contract.py", "tests/test_batch_a.py", "tests/test_contract_json.py",
            "tests/test_jsonschema_lite.py", "tests/test_mutation_kills.py"]


def test_files(work: Path) -> list:
    rest = sorted(str(p.relative_to(work)) for p in (work / "tests").glob("test_*.py"))
    first = [f for f in PRIORITY if (work / f).exists()]
    return first + [f for f in rest if f not in first]


def pytest_cmd(work: Path, targets=None, deselect=()):
    cmd = [sys.executable, "-m", "pytest", "-q", "-m", "not slow", "-x", "-rfE", "-p", "no:cacheprovider"]
    for d in deselect:
        cmd += ["--deselect", d]
    return cmd + (targets or test_files(work))


def _pytest(work: Path, cmd, timeout):
    env = {**os.environ, "PYTHONPATH": str(work), "PYTHONHASHSEED": "0", "TZ": "UTC"}
    env.pop("AUDITENV_SEED_SALT", None)
    try:
        p = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, ""
    return p.returncode, p.stdout + p.stderr


def run_tests(work: Path, timeout: int) -> tuple[bool, str, float, list]:
    """Fast suite with -x. A failing test is re-run ALONE on the same tree; if it passes alone it was a
    load-dependent flake: it is deselected and the suite continues. Returns (killed, killer, seconds, flakes)."""
    t0 = time.monotonic()
    flakes = []
    while True:
        code, out = _pytest(work, pytest_cmd(work, deselect=flakes), timeout)
        if code is None:
            return True, "timeout", time.monotonic() - t0, flakes
        if code == 0:
            return False, "", time.monotonic() - t0, flakes
        hits = FAIL_RE.findall(out)
        if not hits:
            return True, f"pytest exit {code}", time.monotonic() - t0, flakes
        killer = hits[0]
        code2, _ = _pytest(work, [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", killer], timeout)
        if code2 != 0:
            return True, killer, time.monotonic() - t0, flakes
        flakes.append(killer)
        if len(flakes) > 5:
            return True, "too many flaky tests: " + ", ".join(flakes), time.monotonic() - t0, flakes


def apply(work: Path, rel: str, old: str, new: str) -> str:
    path = work / rel
    text = path.read_text("utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"mutation target not unique/absent in {rel}: {old!r} (found {text.count(old)})")
    mutated = text.replace(old, new)
    # an invalid mutant (syntax error) would be "killed" by every test and prove nothing
    if rel.endswith(".py"):
        compile(mutated, rel, "exec")
    elif rel.endswith(".json"):
        json.loads(mutated)
    path.write_text(mutated, "utf-8")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--only", help="comma-separated mutation ids")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out", default=str(ROOT / "reports" / "mutation.md"))
    a = ap.parse_args(argv)
    muts = [m for m in MUTATIONS if not a.only or m[0] in a.only.split(",")]
    if not muts:
        raise SystemExit(f"no mutation matches --only {a.only}")
    for _, rel, old, new, _ in muts:  # fail fast on a stale or syntactically invalid mutation table
        text = (ROOT / rel).read_text("utf-8")
        if text.count(old) != 1:
            raise SystemExit(f"stale mutation target in {rel}: {old!r}")
        mutated = text.replace(old, new)
        compile(mutated, rel, "exec") if rel.endswith(".py") else json.loads(mutated)
    # The copies must be traversable by the sandboxed agent user (`nobody` when run as root), so they live in
    # /tmp (world-traversable) rather than a private TMPDIR, and are chmod 755.
    scratch = Path(tempfile.mkdtemp(prefix="auditenv-mut-", dir="/tmp" if os.path.isdir("/tmp") else None))
    scratch.chmod(0o755)
    works = []
    for k in range(max(1, a.jobs)):
        w = scratch / f"w{k}"
        shutil.copytree(ROOT, w, ignore=IGNORE)
        works.append(w)
    free = list(works)
    import threading

    lock = threading.Lock()

    def take():
        with lock:
            return free.pop()

    def give(w):
        with lock:
            free.append(w)

    def baseline():
        w = take()
        try:
            return run_tests(w, a.timeout)
        finally:
            give(w)

    def one(m):
        mid, rel, old, new, what = m
        w = take()
        try:
            orig = apply(w, rel, old, new)
            try:
                killed, by, dt, flakes = run_tests(w, a.timeout)
            finally:
                (w / rel).write_text(orig, "utf-8")
            print(f"{mid} {'killed' if killed else 'SURVIVED'} {by} ({dt:.0f}s)", flush=True)
            return {"id": mid, "file": rel, "what": what, "killed": killed, "killed_by": by, "seconds": round(dt, 1),
                    "flaky_deselected": flakes}
        finally:
            give(w)

    t0 = time.monotonic()
    b_failed, b_by, b_dt, _ = baseline()
    if b_failed:
        print(f"baseline is RED ({b_by}); mutation results would be meaningless", file=sys.stderr)
        shutil.rmtree(scratch, ignore_errors=True)
        return 2
    print(f"baseline green ({b_dt:.0f}s); {len(muts)} mutations, {len(works)} workers", flush=True)
    with ThreadPoolExecutor(max_workers=len(works)) as ex:
        res = list(ex.map(one, muts))
    shutil.rmtree(scratch, ignore_errors=True)
    killed = sum(r["killed"] for r in res)
    write_report(Path(a.out), res, killed, b_dt, time.monotonic() - t0)
    print(f"mutation: {killed}/{len(res)} killed -> {a.out}")
    return 0 if killed == len(res) else 1


def write_report(path: Path, res, killed, b_dt, total):
    lines = ["# Мутационное тестирование оценщика", "",
             "Генерируется `make mutation` (`python tools/mutation_test.py`), в `make check` не входит. Каждая мутация —",
             "одна намеренная ошибка в коде оценщика (точная замена текста); после неё прогоняются быстрые тесты",
             "(`pytest -m \"not slow\" -x`, сначала тесты оценщика). «Убита» — какой‑то тест упал; в таблице — первый",
             "упавший тест, **подтверждённый** повторным запуском этого теста отдельно на том же мутанте (тест, который",
             "отдельно проходит, считается флейком от нагрузки, исключается, и прогон продолжается).",
             "Выжившая мутация означает, что тесты не отличают баг от правильного оценщика.", "",
             f"**Итог: {killed}/{len(res)} мутаций убито** ({100 * killed // max(1, len(res))} %). "
             f"Базовый прогон без мутаций зелёный ({b_dt:.0f} с); всё вместе — {total:.0f} с.", "",
             "## История", ""] + [f"* {h}" for h in HISTORY] + ["", "## Текущий прогон", "",
             "| # | Файл | Мутация | Итог | Какой тест поймал |", "|---|---|---|---|---|"]
    for r in res:
        lines.append(f"| {r['id']} | `{r['file']}` | {r['what']} | {'убита' if r['killed'] else '**выжила**'} | "
                     f"{'`' + r['killed_by'] + '`' if r['killed'] else '—'} |")
    fl = sorted({f for r in res for f in r.get("flaky_deselected", [])})
    lines += ["", "Флейки, исключённые при перепроверке: " + (", ".join(f"`{f}`" for f in fl) if fl else "нет"), ""]
    lines += ["", "Время по мутациям (с): " + ", ".join(f"{r['id']} {r['seconds']:.0f}" for r in res), ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), "utf-8")
    (path.with_suffix(".json")).write_text(json.dumps({"killed": killed, "total": len(res), "results": res},
                                                      indent=1, sort_keys=True) + "\n", "utf-8")


if __name__ == "__main__":
    sys.exit(main())
