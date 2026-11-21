"""Jury harness helpers: run the CLI as an external program. No auditenv import (black box)."""
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JURY = ROOT / "jury_sim"
WORK = JURY / "work"
POL = JURY / "policies"
PY = sys.executable


def salt():
    p = WORK / "salt.txt"
    if not p.exists():
        WORK.mkdir(parents=True, exist_ok=True)
        p.write_text("jury-" + os.urandom(12).hex() + "\n")
    return p.read_text().strip()


def env(with_salt=True):
    e = dict(os.environ)
    e.pop("AUDITENV_SEED_SALT", None)
    if with_salt:
        e["AUDITENV_SEED_SALT"] = salt()
    e["TZ"] = "UTC"
    return e


def cli(*args, with_salt=True, check=True, timeout=600):
    r = subprocess.run([PY, "-m", "auditenv", *map(str, args)], cwd=ROOT, env=env(with_salt),
                       capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"auditenv {args} failed rc={r.returncode}: {r.stderr[-2000:]}")
    return r


def policy_cmd(name, *args):
    return " ".join([shlex.quote(PY), shlex.quote(str(POL / f"{name}.py"))] + [shlex.quote(str(a)) for a in args])


def read_jsonl(p):
    p = Path(p)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def run_policy(cmd, tag, episode_dir=None, seed=None, config=None, mode="train", time_limit=None,
               with_salt=True):
    out = WORK / "runs" / tag
    out.mkdir(parents=True, exist_ok=True)
    traj, log = out / "traj.jsonl", out / "log.jsonl"
    for f in (traj, log):
        if f.exists():
            f.unlink()
    args = ["run", "--policy-cmd", cmd, "--mode", mode, "--log", log, "--trajectory-out", traj]
    if episode_dir:
        args += ["--episode-dir", episode_dir]
    else:
        args += ["--seed", seed, "--config", config]
    if time_limit:
        args += ["--time-limit", time_limit]
    t0 = time.monotonic()
    r = cli(*args, with_salt=with_salt, check=False)
    wall = time.monotonic() - t0
    return {"rc": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "wall": wall,
            "traj": read_jsonl(traj), "log": read_jsonl(log), "traj_path": traj, "log_path": log}


def submission(traj):
    """(submit_args or None, inspection_steps, truncated) from a trajectory."""
    steps = [t for t in traj if t.get("action") is not None]
    for k, t in enumerate(steps):
        a = t["action"]
        if isinstance(a, dict) and a.get("tool") == "submit":
            return a.get("args"), k, False
    trunc = any(t.get("truncated") for t in traj)
    return None, len(steps), trunc
