"""Round 3: site/replay.html, `jury-pairs`, and that docs/JURY.md + README.en.md only reference real things."""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
sys.path.insert(0, str(ROOT / "tools"))

import build_replay  # noqa: E402

from auditenv.cli import _truths  # noqa: E402
from auditenv.leakscan import scan_lines  # noqa: E402


# ------------------------------------------------------------------ 7) site/replay.html
def _embedded():
    html = (ROOT / "site" / "replay.html").read_text("utf-8")
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    assert m, "embedded data block missing"
    return html, json.loads(m.group(1).replace("<\\/", "</"))


def test_replay_html_is_up_to_date():
    html = build_replay.render(build_replay.build_data(build_replay.TRAJ.read_text("utf-8").splitlines()))
    assert (ROOT / "site" / "replay.html").read_text("utf-8") == html, "run: python tools/build_replay.py"


def test_replay_has_five_episodes_and_exactly_the_recorded_steps():
    _, data = _embedded()
    assert len(data["episodes"]) == 5 and len({e["episode_id"] for e in data["episodes"]}) == 5
    recorded = [json.loads(x) for x in build_replay.TRAJ.read_text("utf-8").splitlines()]
    for e in data["episodes"]:
        runs = {r["run_id"]: r for r in e["runs"]}
        mine = [x for x in recorded if x["episode_id"] == e["episode_id"]]
        assert runs and len(mine) == sum(len(r["steps"]) for r in runs.values())
        for x in mine:
            s = runs[x["run_id"]]["steps"]
            assert any(st["step"] == x["step"] and st["observation"] == x["observation"] and st["action"] == x["action"]
                       and st["reward"] == x["reward"] for st in s)


def test_replay_contains_no_answer_key_and_no_network():
    html, data = _embedded()
    lines = [dict(st, episode_id=e["episode_id"]) for e in data["episodes"] for r in e["runs"] for st in r["steps"]]
    assert scan_lines(lines, _truths()) == []  # the same leak scanner as for trajectories, with the real truths
    blob = json.dumps(data)
    for word in ("evidence_sets", "expected_amount", "issue_id", "provenance", "grader/", "ISS-"):
        assert word not in blob
    for e in data["episodes"]:  # labels describe the public setting, never an error
        for t in ("duplicate", "allocation", "fx_rate", "cutoff", "clean", "чист", "ошиб", "дубл"):
            assert t not in e["label"].lower()
    assert not re.search(r"https?://", html)
    assert not re.search(r"<script[^>]+src=|<link[^>]+href=|@import|url\(", html)


# ------------------------------------------------------------------ 3) jury-pairs
def test_jury_pairs_command_equal_on_opaque_twins(tmp_path):
    out = subprocess.run([PY, "-m", "auditenv", "jury-pairs", "--policy", "simple_reconcile", "--n", "2",
                          "--config", "interaction-heavy", "--json", str(tmp_path / "p.json")],
                         cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "jury-pairs: 2/2 pairs equal" in out.stdout
    rows = json.loads((tmp_path / "p.json").read_text())
    assert len(rows) == 2 and all(r["equal"] and r["reward"] == r["reward_twin"] for r in rows)


# ------------------------------------------------------------------ 3), 4) docs reference only real things
DOCS = ["docs/JURY.md", "README.en.md",
        # round 4: every command, make target, test name and path these documents cite must exist
        "docs/FAQ.md", "docs/AGENT_GUIDE.md", "docs/HOTFIX.md", "docs/SAFETY.md", "docs/DESIGN_SHORT.md",
        "docs/AI_USAGE.md", "docs/DATASHEET.md", "docs/GLOSSARY.md", "docs/SUBMISSION_FORM.md", "README.md"]


def _subcommands():
    src = (ROOT / "auditenv" / "cli.py").read_text("utf-8")
    return set(re.findall(r'sub\.add_parser\("([a-z-]+)"', src)) | {"replay", "leakscan"}


def _test_names(path):
    tree = ast.parse((ROOT / path).read_text("utf-8"))
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}


def _k_selects(expr, names):
    """pytest -k semantics on test names: substring per identifier, combined with and/or/not."""
    py = re.sub(r"[\w\[\]\-.]+", lambda m: m.group(0) if m.group(0) in ("and", "or", "not") else f"({m.group(0)!r} in n)",
                expr)
    return [n for n in names if eval(py, {}, {"n": n})]  # noqa: S307 - expression built from the doc above


@pytest.mark.parametrize("doc", DOCS)
def test_doc_commands_tests_and_paths_exist(doc):
    text = (ROOT / doc).read_text("utf-8")
    subs = _subcommands()
    for cmd in re.findall(r"python -m auditenv ([a-z-]+)", text):
        assert cmd in subs, f"{doc}: unknown subcommand {cmd}"
    for target in re.findall(r"make ([a-z][a-z0-9-]+)", text):
        assert re.search(rf"^{re.escape(target)}:", (ROOT / "Makefile").read_text(), re.M), f"{doc}: no make {target}"
    for path, name in re.findall(r"(tests/test_\w+\.py)::(test_\w+)", text):
        assert name in _test_names(path), f"{doc}: {path}::{name} does not exist"
    for path, expr in re.findall(r'pytest -q (tests/test_\w+\.py) -k "?([^"`]+?)"?`', text):
        assert _k_selects(expr.strip(), _test_names(path)), f"{doc}: -k {expr!r} selects nothing in {path}"
    for path in re.findall(r"`((?:docs|tools|tests|auditenv|examples|configs|schemas|reports|site)/[\w./-]+)`", text):
        if "<" in path or path.endswith("/"):
            continue
        assert (ROOT / path).exists() or path.startswith("reports/"), f"{doc}: {path} does not exist"
    # every bare test name in a table row of JURY.md must exist in the file named in the same row
    if doc.endswith("JURY.md"):
        for row in [ln for ln in text.splitlines() if ln.startswith("| ") and "tests/test_" in ln]:
            files = re.findall(r"tests/test_\w+\.py", row)
            pool = set().union(*(_test_names(f) for f in files))
            for name in re.findall(r"`(test_\w+)`", row):
                assert name in pool, f"{doc}: {name} not in {files}"


# ------------------------------------------------------------------ 6) the vat_error rehearsal patch stays applicable
def test_vat_rehearsal_patch_is_merged():
    """v1.1: the rehearsal patch (a 5th error type added by one module + registry) is merged into main and
    switched on in the configs; the patch file stays as the record of how long that took."""
    patch = ROOT / "docs" / "rehearsal" / "vat_error.patch"
    text = patch.read_text("utf-8")
    assert "auditenv/generator/errors/vat_error.py" in text and text.count("diff --git") >= 20
    assert (ROOT / "auditenv" / "generator" / "errors" / "vat_error.py").exists()
    from auditenv.config import DEFAULT_CONFIG
    from auditenv.generator.errors import REGISTRY

    assert "vat_error" in REGISTRY and DEFAULT_CONFIG["errors"]["vat_error"] > 0 and DEFAULT_CONFIG["vat_share"] > 0
