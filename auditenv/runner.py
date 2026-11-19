"""Run a policy against the env.

Agent policies run in a SEPARATE PROCESS and talk JSON lines over stdin/stdout; the env and
the grader stay in this (parent) process. The child gets an empty temp dir as cwd, a
cleared environment (no salt, no seed, no data paths) and a code-only copy of the package. Oracle and attacks are grader-side and run in-process.

Protocol: parent -> child  {"observation": ..., "reward": r, "terminated": b, "truncated": b}
          child  -> parent {"action": {...}}
          parent -> child  {"close": true}
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shutil
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .canon import dumps
from .env.env import AuditEnv
from .paths import ROOT


_CODE_DIR = None


def agent_code_dir() -> str:
    """A private copy of the auditenv package (code only: no schemas, configs, episodes or
    grader data), made once per evaluator process. The agent imports policies from here."""
    global _CODE_DIR
    if _CODE_DIR is None:
        d = tempfile.mkdtemp(prefix="auditenv-code-")
        shutil.copytree(ROOT / "auditenv", Path(d) / "auditenv",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        atexit.register(shutil.rmtree, d, True)
        _CODE_DIR = d
    return _CODE_DIR


def harden_evaluator() -> bool:
    """Mark the evaluator process non-dumpable (Linux prctl PR_SET_DUMPABLE=0): its
    /proc/<pid>/environ, mem, fd and maps become unreadable for other non-root processes,
    so the agent cannot read the seed salt or open file handles of its parent."""
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(4, 0, 0, 0, 0) == 0  # PR_SET_DUMPABLE = 4
    except (OSError, AttributeError):
        return False


AGENT_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "TZ": "UTC", "LANG": "C.UTF-8"}


class ChildPolicy:
    """Agent process: `python -I -S` (ignores every PYTHON* variable, no site-packages, no cwd
    on sys.path), cwd = a fresh EMPTY temp dir, environment = AGENT_ENV only (no salt, no seed,
    no paths to episodes or grader files)."""

    def __init__(self, name: str, seed: int = 0):
        harden_evaluator()
        self.tmp = tempfile.TemporaryDirectory(prefix="auditenv-agent-")
        boot = (f"import sys; sys.path.insert(0, {agent_code_dir()!r}); "
                f"from auditenv.runner import _child_main; _child_main({name!r}, {int(seed)})")
        self.proc = subprocess.Popen([sys.executable, "-I", "-S", "-c", boot], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=self.tmp.name,
                                     env=dict(AGENT_ENV), text=True, bufsize=1, close_fds=True)
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.proc.stdout, selectors.EVENT_READ)

    def act(self, obs, reward, terminated, truncated, timeout: float):
        try:
            self.proc.stdin.write(dumps({"observation": obs, "reward": reward, "terminated": terminated,
                                         "truncated": truncated}) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            return None
        if not self.sel.select(timeout=max(0.0, timeout)):
            return None
        line = self.proc.stdout.readline()
        if not line:
            return None
        try:
            return json.loads(line).get("action")
        except (ValueError, AttributeError):
            return {"tool": "__invalid__"}

    def close(self):
        try:
            self.proc.stdin.write(dumps({"close": True}) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.sel.close()
        self.tmp.cleanup()


class InProcess:
    def __init__(self, policy):
        self.policy = policy

    def act(self, obs, reward, terminated, truncated, timeout):
        return self.policy.act(obs)

    def close(self):
        pass


def run_episode(policy_name: str, *, episode=None, episode_dir=None, seed=None, config=None, mode="train",
                grader_log=None, policy_seed: int = 0, isolate: bool = True, record: bool = True,
                time_limit: float = 60.0, policy_obj=None) -> dict:
    env = AuditEnv(mode=mode, grader_log=grader_log, time_limit=time_limit)
    env.run_meta = {"policy": policy_name}
    obs, info = env.reset(seed=seed, config=config, episode_dir=episode_dir, episode=episode)
    if policy_obj is not None:
        agent = InProcess(policy_obj)
    elif policy_name == "oracle":
        from .policies.oracle import Oracle

        agent = InProcess(Oracle(truth=env._grader._truth))
    elif isolate:
        agent = ChildPolicy(policy_name, policy_seed)
    else:
        from .policies import make_policy

        agent = InProcess(make_policy(policy_name, policy_seed))
    traj = []
    t0 = time.monotonic()
    eid = env.episode_id
    if record:
        traj.append({"episode_id": eid, "policy": policy_name, "step": 0, "action": None, "observation": obs,
                     "reward": 0.0, "terminated": False, "truncated": False})
    reward, terminated, truncated = 0.0, False, False
    try:
        while not (terminated or truncated):
            remaining = time_limit - (time.monotonic() - t0)
            action = agent.act(obs, reward, terminated, truncated, remaining)
            if action is None:  # hung or dead policy process
                out = env.truncate_now()
                if out is None:
                    break
                obs, reward, terminated, truncated, info = out
                action = None
            else:
                obs, reward, terminated, truncated, info = env.step(action)
            if record:
                traj.append({"episode_id": eid, "policy": policy_name, "step": env.steps_used, "action": action,
                             "observation": obs, "reward": reward, "terminated": terminated,
                             "truncated": truncated})
    finally:
        agent.close()
    elapsed = time.monotonic() - t0
    g = dict(env.last_grade or {})
    g["elapsed_s"] = round(elapsed, 4)
    g["steps"] = env.steps_used
    return {"grade": g, "trajectory": traj, "returned_reward": reward}


def _child_main(policy: str, seed: int):
    from .policies import make_policy

    pol = make_policy(policy, seed)
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("close"):
            break
        action = pol.act(msg["observation"])
        sys.stdout.write(dumps({"action": action}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--policy", required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.child:
        _child_main(a.policy, a.seed)
