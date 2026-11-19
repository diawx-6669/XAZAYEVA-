"""No closed data in observations, errors or paths."""

import json
from pathlib import Path

from auditenv.leakscan import scan_lines, scan_observation
from auditenv.runner import run_episode

ROOT = Path(__file__).parent.parent


def test_leakscan_on_fresh_trajectories(erroneous, clean):
    lines, truths = [], {}
    for ep in (erroneous, clean):
        truths[ep.episode_id] = ep.truth
        for pol in ("random_explorer", "simple_reconcile", "flag_all"):
            lines += run_episode(pol, episode=ep)["trajectory"]
    assert scan_lines(lines, truths) == []


def test_leakscan_detects_planted_leaks(erroneous):
    iss = erroneous.truth["issues"][0]
    bad = [{"result": {"note": iss["issue_id"]}, "steps_remaining": 5},
           {"result": {"hint": iss["type"], "id": iss["affected_ids"][0]}, "steps_remaining": 5},
           {"error": {"code": "not_found", "detail": "grader/truth.json"}, "steps_remaining": 5},
           {"result": {}, "steps_remaining": 5, "debug": 1}]
    for b in bad:
        assert scan_observation(b, erroneous.truth)


def test_committed_trajectories_are_clean():
    path = ROOT / "trajectories" / "trajectories.jsonl"
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    truths = {}
    for split in ("train", "dev"):
        for e in json.loads((ROOT / "episodes" / split / "index.json").read_text()):
            truths[e["episode_id"]] = json.loads((ROOT / "episodes" / split / e["episode_id"] / "grader" / "truth.json").read_text())
    assert lines and scan_lines(lines, truths) == []
    required = {"episode_id", "step", "action", "observation", "reward", "terminated", "truncated"}
    assert all(required <= set(x) for x in lines)
    assert {x["policy"] for x in lines} == {"random_explorer", "simple_reconcile", "flag_all"}  # no oracle


def test_env_never_reads_grader_dir_for_observations(tmp_path, erroneous):
    from auditenv.env.env import AuditEnv
    from auditenv.generator.export import write_episode

    d = write_episode(erroneous, tmp_path / "ep")
    env = AuditEnv()
    obs, _ = env.reset(episode_dir=d)
    assert str(tmp_path) not in json.dumps(obs)
    o = env.step({"tool": "get_document", "args": {"doc_id": "../grader/truth.json"}})[0]
    assert o["error"] == {"code": "not_found"}


def test_seed_salt_blocks_seed_bruteforce(monkeypatch):
    """Without a salt the open generator lets anyone map seed -> episode_id. With the evaluator's
    secret salt the same seed yields a different, unguessable episode."""
    from auditenv.generator.episode import generate_episode

    plain = generate_episode(5, "dev-mixed")
    monkeypatch.setenv("AUDITENV_SEED_SALT", "jury-secret-salt")
    salted = generate_episode(5, "dev-mixed")
    assert salted.episode_id != plain.episode_id and salted.files != plain.files
    assert salted.provenance["seed_salted"] is True and "jury-secret-salt" not in str(salted.provenance)
    # an attacker without the salt cannot reproduce it from small seeds
    monkeypatch.delenv("AUDITENV_SEED_SALT")
    from auditenv.ids import IdFactory, make_rng

    assert all(IdFactory(make_rng(s, "naming", 0)).episode_id() != salted.episode_id for s in range(2000))


def test_agent_process_gets_no_salt_and_no_paths(monkeypatch):
    from auditenv.runner import ChildPolicy

    monkeypatch.setenv("AUDITENV_SEED_SALT", "secret")
    c = ChildPolicy("random_explorer")
    try:
        assert "AUDITENV_SEED_SALT" not in c.proc.args and c.proc.pid
        env = open(f"/proc/{c.proc.pid}/environ", "rb").read().decode(errors="replace")
        assert "AUDITENV_SEED_SALT" not in env and "secret" not in env
    finally:
        c.close()


def test_manifest_has_no_config_name(clean):
    m = clean.public().manifest
    assert "config_name" not in m and "clean" not in str(m)
