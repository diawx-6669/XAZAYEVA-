"""A2: the code examples in the documentation actually work.

Every ```bash / ```sh / ```python block of the four entry documents is classified in
tests/docs_examples.json: either run here (with documented substitutions of placeholders, a timeout,
exit code 0 and an expected substring) or skipped with a written reason. Unclassified blocks fail.
Identical blocks (after substitution) run once; blocks run in parallel to keep make check fast."""

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from auditenv.paths import ROOT

DOCS = ["README.md", "README.en.md", "docs/JURY.md", "docs/ADAPTER.md"]
SPEC = json.loads((ROOT / "tests" / "docs_examples.json").read_text("utf-8"))
TIMEOUT = 60


def blocks():
    out = []
    for doc in DOCS:
        for m in re.finditer(r"```(bash|sh|python)\n(.*?)```", (ROOT / doc).read_text("utf-8"), re.S):
            out.append((doc, m.group(1), m.group(2).strip()))
    return out


def rule_for(body):
    first = substitute(body, "{TMP}", "{EPISODE}").splitlines()[0].strip()
    hits = [r for r in SPEC["rules"] if first.startswith(r["first_line"])]
    return max(hits, key=lambda r: len(r["first_line"])) if hits else None


def substitute(body, tmp, episode):
    for k, v in SPEC["substitutions"].items():
        body = body.replace(k, v)
    return body.replace("{TMP}", str(tmp)).replace("{EPISODE}", episode)


def test_every_block_is_classified():
    missing = [(d, b.splitlines()[0]) for d, _, b in blocks() if rule_for(b) is None]
    assert not missing, f"classify these blocks in tests/docs_examples.json: {missing}"
    for r in SPEC["rules"]:
        assert r["action"] in ("run", "skip") and (r["action"] == "run" or len(r.get("reason", "")) > 20), r


def _run(lang, body, rule, tmp):
    env = {**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
           "PYTHONPATH": str(ROOT)}
    env.pop("AUDITENV_SEED_SALT", None)
    if lang == "python":
        cmd = [sys.executable, "-c", body]
    else:
        cmd = ["bash", "-e", "-c", body]
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, input=rule.get("stdin", ""), capture_output=True, text=True,
                           timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"timeout after {TIMEOUT} s"
    if p.returncode != 0:
        return f"exit {p.returncode}: {p.stderr[-800:]}"
    if rule.get("expect") and rule["expect"] not in p.stdout:
        return f"expected {rule['expect']!r} in output, got: {p.stdout[-500:]}"
    return None


def test_runnable_blocks_work(tmp_path):
    episode = json.loads((ROOT / "episodes" / "dev" / "index.json").read_text("utf-8"))[0]["episode_id"]
    jobs, seen = [], set()
    for doc, lang, body in blocks():
        rule = rule_for(body)
        if rule is None or rule["action"] != "run":
            continue
        work = tmp_path / f"b{len(jobs)}"
        sub = substitute(body, work, episode)
        key = re.sub(r"\s+#.*$", "", substitute(body, "T", episode), flags=re.M)
        if key in seen:
            continue
        seen.add(key)
        work.mkdir()
        jobs.append((doc, lang, sub, rule, work))
    assert len(jobs) >= 8
    # as root every closed run ends by killing ALL processes of `nobody` (runner._sweep_uid), which would kill
    # the agent of a concurrent run: parallel only when not root (docs/LIMITATIONS.md)
    with ThreadPoolExecutor(max_workers=1 if os.geteuid() == 0 else 4) as ex:
        results = list(ex.map(lambda j: _run(j[1], j[2], j[3], j[4]), jobs))
    failed = [(j[0], j[2].splitlines()[0], r) for j, r in zip(jobs, results) if r]
    assert not failed, failed


@pytest.mark.parametrize("rule", [r for r in SPEC["rules"] if r["action"] == "run"], ids=lambda r: r["first_line"][:40])
def test_every_run_rule_is_used(rule):
    assert any(rule_for(b) is rule for _, _, b in blocks()), "stale rule: no block matches it"
