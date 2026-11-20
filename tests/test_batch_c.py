"""Round-2 package C: independent verification of truth and grader, sandboxed agents, tamper evidence,
external agents, server/client, transforms, determinism across interpreters, long loops."""

import hashlib
import json
import os
import subprocess
import sys
import tracemalloc
from pathlib import Path

import pytest

from auditenv.canon import dumps
from auditenv.env.env import AuditEnv
from auditenv.generator.episode import generate_episode
from auditenv.generator.export import write_episode
from auditenv.grader.log import GraderLog, verify_chain
from auditenv.grader.validate_truth import validate, verify_evidence
from auditenv.policies.oracle import JURY_ORACLES, jury_action, oracle_findings
from auditenv.runner import AS_LIMIT, CPU_LIMIT_S, ChildPolicy, run_episode

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
CASES = [(3, "interaction-heavy"), (9017, "dev-global"), (2, "clean-only"), (5, "dev-mixed"), (108, "train-global")]


@pytest.fixture(scope="module")
def eps():
    return [generate_episode(s, c) for s, c in CASES]


# ------------------------------------------------------- C1 independent tool
def test_independent_verifier_agrees_and_imports_nothing(tmp_path, eps):
    dirs = [str(write_episode(ep, tmp_path / ep.episode_id)) for ep in eps]
    out = subprocess.run([PY, "-I", str(ROOT / "tools" / "verify_independent.py"), "--json", *dirs],
                         capture_output=True, text=True)
    res = json.loads(out.stdout)
    assert out.returncode == 0 and res["summary"]["failed"] == 0 and res["summary"]["episodes"] == len(eps)
    import ast

    tree = ast.parse((ROOT / "tools" / "verify_independent.py").read_text())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"csv", "json", "os", "sys", "datetime", "decimal"}, mods


def test_independent_verifier_catches_a_wrong_truth(tmp_path, eps):
    ep = eps[0]
    bad = json.loads(json.dumps(ep.truth))
    bad["issues"][0]["expected_amount_minor"] += 50
    d = write_episode(ep, tmp_path / "e")
    (d / "grader" / "truth.json").write_text(dumps(bad))
    out = subprocess.run([PY, "-I", str(ROOT / "tools" / "verify_independent.py"), str(d)], capture_output=True, text=True)
    assert out.returncode == 1 and "1 failed" in out.stdout


# --------------------------------------------------------- C2 provenance
def test_verify_provenance(eps):
    from auditenv.verify_provenance import verify

    for ep in eps:
        r = verify(ep.files, ep.truth, ep.provenance)
        assert r["ok"], r


def test_verify_provenance_detects_a_lie(eps):
    from auditenv.verify_provenance import verify

    ep = eps[0]
    prov = json.loads(json.dumps(ep.provenance))
    prov["mutations"] = prov["mutations"][1:]  # hide one mutation
    assert not verify(ep.files, ep.truth if False else {**ep.truth, "issues": ep.truth["issues"][1:]}, prov)["ok"]


# ----------------------------------------------------------- C3 plausibility
def test_lint_only_truth_explains_implausibility(eps):
    from auditenv.lint import lint, unexplained

    for ep in eps:
        assert unexplained(ep.public(), ep.truth) == []
    ep = eps[0]
    hits = lint(ep.public())
    cut = [i for i in ep.truth["issues"] if i["type"] == "period_cutoff"]
    assert all(("outside_period", i["affected_ids"][0]) in hits for i in cut)
    assert unexplained(ep.public(), {"issues": []}) == [h for h in hits]  # without truth every hit is unexplained


# ------------------------------------------- C4 minimal + alternative evidence
def test_evidence_sets_are_minimal_and_alternatives_exist():
    alt = {"payment_allocation": 0, "fx_rate_payment": 0}
    for seed in range(30):
        ep = generate_episode(seed, "interaction-heavy" if seed % 2 else "dev-mixed")
        pd = ep.public()
        for iss in ep.truth["issues"]:
            for ev in iss["evidence_sets"]:
                assert verify_evidence(pd, iss, ev)[0]
                for k in range(len(ev)):
                    assert not verify_evidence(pd, iss, ev[:k] + ev[k + 1:])[0], (iss["type"], ev, k)
            if iss["type"] == "payment_allocation" and len(iss["evidence_sets"]) > 1:
                alt["payment_allocation"] += 1
            if iss["type"] == "fx_rate" and iss["affected_ids"][0] in pd.payment_by_id and len(iss["evidence_sets"]) > 1:
                alt["fx_rate_payment"] += 1
            assert len({x for s in iss["evidence_sets"] for x in s}) <= 10
    assert all(v >= 1 for v in alt.values()), alt


# ---------------------------------------------------------- C5 jury oracles
@pytest.mark.parametrize("name", JURY_ORACLES)
def test_jury_oracles_score_max(eps, name):
    for ep in eps:
        env = AuditEnv()
        env.reset(episode=ep)
        assert env.step(jury_action(name, ep.truth))[1] == 1.0, (name, ep.episode_id)


# --------------------------------------------------------- C6 process limits
def test_child_limits_are_applied_and_python_still_starts(eps):
    c = ChildPolicy("simple_reconcile")
    try:
        limits = Path(f"/proc/{c.proc.pid}/limits").read_text()
        row = {line[:26].strip(): line[26:].split() for line in limits.splitlines()[1:]}
        assert int(row["Max address space"][0]) == AS_LIMIT and int(row["Max cpu time"][0]) == CPU_LIMIT_S
        assert row["Max open files"][0] == "64" and row["Max core file size"][0] == "0"
        assert row["Max file size"][0] == "0"
        assert os.getpgid(c.proc.pid) == c.proc.pid  # own session / process group
        if os.getuid() == 0:
            assert os.stat(f"/proc/{c.proc.pid}").st_uid == 65534  # runs as nobody
    finally:
        c.close()
    g = run_episode("simple_reconcile", episode=eps[0])["grade"]
    assert g["steps"] > 5 and g["valid"]


def test_overlong_line_ends_the_run(tmp_path, eps):
    agent = tmp_path / "spam.py"
    agent.write_text("import sys\nfor line in sys.stdin:\n    sys.stdout.write('{\"action\":\"' + 'x' * 3_000_000 + '\"}\\n')\n"
                     "    sys.stdout.flush()\n")
    r = run_episode("external", episode=eps[0], policy_cmd=f"{PY} {agent}", time_limit=20)
    assert r["grade"]["truncated"] and r["grade"]["truncation_reason"] == "policy_unresponsive"


# ---------------------------------------------------------- C7 writer attack
@pytest.mark.skipif(not hasattr(os, "getuid") or os.getuid() != 0, reason="needs root to drop the agent to nobody")
def test_writer_attack_changes_nothing(tmp_path, eps):
    ep = eps[0]
    d = write_episode(ep, tmp_path / "ep")
    log = tmp_path / "grader_log.jsonl"
    GraderLog(log).write({"episode_id": "seed-record"})
    from auditenv.runner import _readonly_code_copy

    code_file = Path(_readonly_code_copy()) / "auditenv" / "grader" / "reward.py"
    targets = [str(log), str(d / "grader" / "truth.json"), str(d / "grader" / "provenance.json"), str(code_file),
               str(ROOT / "auditenv" / "grader" / "reward.py")]

    def digest():
        return {t: hashlib.sha256(Path(t).read_bytes()).hexdigest() for t in targets}

    before = digest()
    r = run_episode("external", episode_dir=d, grader_log=log,
                    policy_cmd=[PY, str(ROOT / "tests" / "agents" / "writer_agent.py"), *targets], time_limit=20)
    assert r["grade"]["valid"]  # the attacker still gets graded normally
    after = {t: hashlib.sha256(Path(t).read_bytes()).hexdigest() for t in targets if t != str(log)}
    assert after == {k: v for k, v in before.items() if k != str(log)}
    assert verify_chain(log)["ok"] and verify_chain(log)["records"] == 2  # only the grader's own record was added
    for tmpdir in ("/tmp", "/var/tmp", "/dev/shm"):
        assert not [n for n in os.listdir(tmpdir) if n.startswith("auditenv_leak")]
    from auditenv.runner import _uid_processes

    assert _uid_processes(65534) == []  # the forked daemon did not survive


# ------------------------------------------------------ C8 digest + log chain
def test_grader_digest_detects_tampered_truth(tmp_path):
    from auditenv.grader.core import EpisodeGrader, GraderIntegrityError

    split = tmp_path / "dev"
    src = sorted((ROOT / "episodes" / "dev").glob("ep-*"))[0]
    import shutil

    shutil.copytree(src, split / src.name)
    shutil.copy(ROOT / "episodes" / "dev" / "index.json", split / "index.json")
    EpisodeGrader.from_dir(split / src.name / "grader")
    t = json.loads((split / src.name / "grader" / "truth.json").read_text())
    t["issues"] = []
    (split / src.name / "grader" / "truth.json").write_text(dumps(t))
    with pytest.raises(GraderIntegrityError):
        EpisodeGrader.from_dir(split / src.name / "grader")


def test_log_chain_detects_edits(tmp_path):
    p = tmp_path / "log.jsonl"
    g = GraderLog(p)
    for i in range(5):
        g.write({"i": i})
    assert verify_chain(p) == {"ok": True, "records": 5, "head": g.head, "broken_at": None}
    lines = p.read_text().splitlines()
    for mutate in (lambda L: L[:2] + L[3:], lambda L: [L[1], L[0]] + L[2:], lambda L: L[:3] + [L[3].replace('"i":3', '"i":9')] + L[4:]):
        p.write_text("\n".join(mutate(list(lines))) + "\n")
        assert not verify_chain(p)["ok"]
    p.write_text("\n".join(lines[:-1] + [lines[-1].replace('"i":4', '"i":7')]) + "\n")
    assert not verify_chain(p, expected_head=g.head)["ok"]  # last line: caught against the published head


# ------------------------------------------------------- C9 external agents
def test_minimal_example_agent_runs():
    out = subprocess.run([PY, "-m", "auditenv", "run", "--policy-cmd", f"{PY} examples/minimal_agent.py", "--seed", "12",
                          "--config", "dev-mixed"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    res = json.loads(out.stdout)
    assert out.returncode == 0 and res["steps"] <= 100 and res["tp"] >= 1
    assert len((ROOT / "examples" / "minimal_agent.py").read_text().splitlines()) <= 45


# --------------------------------------------------------- C10 serve/client
def test_client_replays_trajectories_byte_identical():
    from auditenv.serve import AuditEnvClient

    lines = [json.loads(x) for x in (ROOT / "trajectories" / "trajectories.jsonl").read_text().splitlines()]
    runs = {}
    for rec in lines:
        runs.setdefault(rec["run_id"], []).append(rec)
    dirs = {p.name: p for split in ("train", "dev") for p in (ROOT / "episodes" / split).glob("ep-*")}
    picked = [r for r in runs.values() if r[0]["policy"] in ("random_explorer", "simple_reconcile", "flag_all")][:12]
    with AuditEnvClient(mode="train") as client:
        assert client.action_space["$id"].endswith("action.schema.json") and client.spec["max_steps"] == 100
        for recs in picked:
            local = AuditEnv(mode="train")
            o1, i1 = client.reset(episode_dir=str(dirs[recs[0]["episode_id"]]))
            o2, i2 = local.reset(episode_dir=dirs[recs[0]["episode_id"]])
            assert dumps([o1, i1]) == dumps([o2, i2]) == dumps([recs[0]["observation"], i2])
            for rec in recs[1:]:
                assert dumps(list(client.step(rec["action"]))) == dumps(list(local.step(rec["action"])))


def test_server_rejects_nan_and_garbage():
    p = subprocess.run([PY, "-m", "auditenv", "serve"], input='nonsense\n{"cmd": "teleport"}\n{"cmd": "reset", "seed": 1.5}\n'
                       '{"cmd": "step", "action": {"tool": "calculator", "args": {"expression": "1"}}}\n{"cmd":"close"}\n',
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    outs = [json.loads(x) for x in p.stdout.splitlines()]
    assert outs[:3] == [{"error": "bad_request"}] * 3 and outs[-1] == {"closed": True}
    assert "Traceback" not in p.stdout + p.stderr and "NaN" not in p.stdout


# ------------------------------------------------------------ C11 transform
def test_transform_cli_opaque_ids_keeps_rewards(tmp_path):
    src = sorted((ROOT / "episodes" / "dev").glob("ep-*"))[1]
    out = subprocess.run([PY, "-m", "auditenv", "transform", "--episode-dir", str(src), "--out", str(tmp_path / "t"),
                          "--seed", "11", "--opaque-ids"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0
    m = json.loads((tmp_path / "t" / "grader" / "id_map.json").read_text())
    assert m and all(12 <= len(v) <= 64 and "-" not in v for k, v in m.items() if not k.startswith("ep-"))
    for pol in ("oracle", "simple_reconcile"):
        a = run_episode(pol, episode_dir=src, isolate=False)["grade"]
        b = run_episode(pol, episode_dir=tmp_path / "t", isolate=False)["grade"]
        assert (a["reward"], a["f1"], a["tp"]) == (b["reward"], b["f1"], b["tp"])


# ------------------------------------------------------ C12 subprocess determinism
SCRIPT = r"""
import hashlib, json, sys
sys.path.insert(0, sys.argv[1])
from auditenv.canon import dumps, files_digest
from auditenv.generator.episode import generate_episode
from auditenv.runner import run_episode
ep = generate_episode(9008, "interaction-heavy")
h = hashlib.sha256()
h.update(files_digest(ep.files).encode()); h.update(dumps(ep.truth).encode())
for pol in ("simple_reconcile", "random_explorer"):
    r = run_episode(pol, episode=ep, isolate=False)
    h.update(dumps(r["trajectory"]).encode()); h.update(repr(r["grade"]["reward"]).encode())
print(h.hexdigest())
"""


def _interpreters():
    out = []
    for cand in [PY, "python3.11", "python3.12", "python3.13"]:
        try:
            ok = subprocess.run([cand, "-c", "import sys; print(sys.version_info[:2])"], capture_output=True,
                                text=True, timeout=30)
        except OSError:
            continue
        if ok.returncode == 0 and ok.stdout not in [o[1] for o in out]:
            out.append((cand, ok.stdout))
    return [c for c, _ in out]


@pytest.mark.slow
def test_bytes_identical_across_interpreters_hashseed_tz_lang_cwd(tmp_path):
    digests = set()
    variants = [("0", "UTC", "C.UTF-8"), ("12345", "Asia/Tokyo", "ru_RU.UTF-8"), ("random", "America/New_York", "C")]
    for py in _interpreters():
        for k, (hs, tz, lang) in enumerate(variants):
            cwd = tmp_path / f"cwd{k}"
            cwd.mkdir(exist_ok=True)
            env = {"PATH": os.environ["PATH"], "PYTHONHASHSEED": hs, "TZ": tz, "LANG": lang, "LC_ALL": lang}
            out = subprocess.run([py, "-c", SCRIPT, str(ROOT)], cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
            assert out.returncode == 0, out.stderr[-500:]
            digests.add(out.stdout.strip())
    assert len(digests) == 1


# -------------------------------------------------------- C13 diagnostics
def test_oracle_observing_sees_all_evidence(eps):
    for ep in eps:
        g = run_episode("oracle_observing", episode=ep)["grade"]
        assert g["reward_experimental"] == g["reward"] and g["f1"] == 1.0 and g["steps"] <= 100


# ----------------------------------------------------------- C14 schemas
def test_info_schema(eps):
    from auditenv.schemas import errors

    for mode in ("train", "eval"):
        env = AuditEnv(mode=mode)
        _, info = env.reset(episode=eps[0])
        infos = [info, env.step({"tool": "calculator", "args": {"expression": "1"}})[4],
                 env.step(jury_action("first_set", eps[0].truth))[4]]
        assert all(not errors("info", i) for i in infos)


def test_committed_artefacts_match_schemas():
    # the grader log is regenerated by `make check` AFTER pytest, so it is validated there, not here
    out = subprocess.run([PY, "-m", "auditenv", "check-schemas", "--no-log"], cwd=ROOT, capture_output=True, text=True,
                         timeout=300)
    assert out.returncode == 0, out.stdout[-1500:]


def test_trajectories_record_step_burner_and_hung():
    lines = [json.loads(x) for x in (ROOT / "trajectories" / "trajectories.jsonl").read_text().splitlines()]
    ends = {(x["policy"], x.get("truncation_reason")) for x in lines if x["terminated"] or x["truncated"]}
    assert ("step_burner", "max_steps") in ends and ("hung", "policy_unresponsive") in ends


# ------------------------------------------------------------ C16 long loop
def test_long_loop_memory_bounded_and_abandoned_logged(eps, tmp_path):
    log = GraderLog(tmp_path / "log.jsonl")
    env = AuditEnv(grader_log=log)
    ep = eps[0]

    def cycle(n):
        for i in range(n):
            env.reset(episode=ep)
            env.step({"tool": "calculator", "args": {"expression": "1+1"}})
            if i % 2:
                env.step(jury_action("first_set", ep.truth))  # finished; even cycles are abandoned by the next reset

    tracemalloc.start()
    cycle(200)
    base = tracemalloc.get_traced_memory()[0]
    cycle(1800)
    grown = tracemalloc.get_traced_memory()[0] - base
    tracemalloc.stop()
    assert grown < 2_000_000, grown
    assert len(log.records) <= 256 and log.count == 2000  # 1000 graded + 1000 abandoned by the next reset
    recs = [json.loads(x) for x in (tmp_path / "log.jsonl").read_text().splitlines()]
    assert sum(1 for r in recs if r.get("abandoned")) == 1000 and verify_chain(tmp_path / "log.jsonl")["ok"]
