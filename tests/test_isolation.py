"""Closed-run isolation: the episode lives only in the evaluator's memory, nothing of grader/ is
written to disk, and an adversarial policy that hunts for truth on disk / in /proc finds nothing."""

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def evaluator(args, cwd, salt=None, extra=None):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT), "PYTHONHASHSEED": "0", "TZ": "UTC",
           **(extra or {})}
    if salt:
        env["AUDITENV_SEED_SALT"] = salt
    return subprocess.run([sys.executable, "-m", "auditenv", "run", *args], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=120)


def submitted(traj_path):
    lines = [json.loads(x) for x in Path(traj_path).read_text().splitlines()]
    sub = [x["action"] for x in lines if x["action"] and x["action"].get("tool") == "submit"]
    return sub[0]["args"]["findings"]["findings"] if sub else []


def all_files(d):
    return sorted(str(p.relative_to(d)) for p in Path(d).rglob("*") if p.is_file())


def test_closed_run_hunter_finds_nothing(tmp_path):
    before = set(all_files("/tmp")) if os.access("/tmp", os.R_OK) else set()
    r = evaluator(["--policy", "truth_hunter", "--seed", "424242", "--config", "dev-mixed", "--mode", "eval",
                   "--log", str(tmp_path / "grader_log.jsonl"), "--trajectory-out", str(tmp_path / "traj.jsonl")],
                  cwd=tmp_path, salt="jury-" + secrets.token_hex(16))  # fresh salt: never-seen episode
    assert r.returncode == 0, r.stderr
    found = submitted(tmp_path / "traj.jsonl")
    markers = {tuple(f["affected_ids"]) for f in found}
    assert ("LEAK-TRUTH",) not in markers and ("LEAK-PATH",) not in markers
    if os.geteuid() != 0:  # root can read any /proc/*/environ; the jury runs as non-root user
        assert ("LEAK-SALT",) not in markers
        assert found == []
    # nothing of grader/ was written: only our log and trajectory appear in the work dir
    assert all_files(tmp_path) == ["grader_log.jsonl", "traj.jsonl"]
    new_tmp = set(all_files("/tmp")) - before
    assert not [f for f in new_tmp if f.endswith(("truth.json", "provenance.json"))]
    log = json.loads((tmp_path / "grader_log.jsonl").read_text())
    assert log["valid"] and log["tp"] == 0


def test_hunter_positive_control_finds_truth_written_to_disk(tmp_path):
    """Sanity check of the hunter itself: if an episode WITH grader/ is on disk, it is found."""
    from auditenv.generator.episode import generate_episode
    from auditenv.generator.export import write_episode

    ep = generate_episode(4242, "interaction-heavy")
    d = write_episode(ep, tmp_path / "leaky_episode")
    # AUDITENV_KEEP_UID=1: the agent keeps the evaluator's uid (no `nobody` layer), so it CAN read the
    # leaky episode - this checks the hunter, not the sandbox.
    r = evaluator(["--policy", "truth_hunter", "--episode-dir", str(d), "--mode", "eval", "--log",
                   str(tmp_path / "log.jsonl"), "--trajectory-out", str(tmp_path / "traj.jsonl")], cwd=tmp_path,
                  extra={"AUDITENV_KEEP_UID": "1"})
    assert r.returncode == 0, r.stderr
    markers = {tuple(f["affected_ids"]) for f in submitted(tmp_path / "traj.jsonl")}
    assert ("LEAK-TRUTH",) in markers
    assert json.loads((tmp_path / "log.jsonl").read_text())["tp"] == len(ep.truth["issues"])


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() != 0, reason="the nobody layer needs a root evaluator")
def test_nobody_layer_hides_a_leaky_episode_from_the_hunter(tmp_path):
    """Same leaky episode on disk (private dir of the evaluator), default sandbox: the agent runs as
    `nobody` and cannot read it - the hunter finds nothing and scores no TP."""
    from auditenv.generator.episode import generate_episode
    from auditenv.generator.export import write_episode

    os.chmod(tmp_path, 0o700)
    d = write_episode(generate_episode(4242, "interaction-heavy"), tmp_path / "leaky_episode")
    r = evaluator(["--policy", "truth_hunter", "--episode-dir", str(d), "--mode", "eval", "--log",
                   str(tmp_path / "log.jsonl"), "--trajectory-out", str(tmp_path / "traj.jsonl")], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert submitted(tmp_path / "traj.jsonl") == [] and json.loads((tmp_path / "log.jsonl").read_text())["tp"] == 0


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads every /proc/*/environ; run as non-root (Docker: auditor)")
def test_salt_positive_control_without_hardening(tmp_path):
    """Without PR_SET_DUMPABLE=0 the same hunter DOES read the salt from its parent: the
    protection, not luck, is what keeps the salt secret in the test above."""
    r = evaluator(["--policy", "truth_hunter", "--seed", "7", "--config", "dev-mixed", "--mode", "eval",
                   "--log", str(tmp_path / "log.jsonl"), "--trajectory-out", str(tmp_path / "traj.jsonl")],
                  cwd=tmp_path, salt="jury-" + secrets.token_hex(16), extra={"AUDITENV_INSECURE_DUMPABLE": "1",
                                                                           "AUDITENV_NO_CONCEAL": "1"})
    assert r.returncode == 0, r.stderr
    assert ("LEAK-SALT",) in {tuple(f["affected_ids"]) for f in submitted(tmp_path / "traj.jsonl")}


def test_agent_process_environment_is_clean(monkeypatch):
    from auditenv.runner import AGENT_ENV, ChildPolicy

    monkeypatch.setenv("AUDITENV_SEED_SALT", "secret")
    c = ChildPolicy("random_explorer")
    try:
        assert c.env == AGENT_ENV  # exactly what the process was started with
        try:  # the kernel's view, when readable (root without CAP_SYS_PTRACE cannot read a `nobody` agent)
            env = Path(f"/proc/{c.proc.pid}/environ").read_bytes().split(b"\0")
            env = dict(x.decode().split("=", 1) for x in env if b"=" in x)
            assert env == AGENT_ENV
            assert os.listdir(Path(f"/proc/{c.proc.pid}/cwd")) == []
        except PermissionError:
            assert os.listdir(c.tmp.name) == []
        assert "-I" in c.proc.args and "-S" in c.proc.args
        assert str(ROOT) not in " ".join(c.proc.args[1:])  # code is a private copy, not the repo
    finally:
        c.close()


@pytest.mark.skipif(sys.platform != "linux", reason="prctl is Linux-only")
def test_evaluator_is_not_dumpable():
    code = ("from auditenv.runner import harden_evaluator; import os; assert harden_evaluator(); "
            "st = os.stat(f'/proc/{os.getpid()}/environ'); print(st.st_uid)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT,
                       env={"PYTHONPATH": str(ROOT), "PATH": os.environ.get("PATH", "")})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0"  # /proc/<pid>/environ now belongs to root -> unreadable for the agent user
