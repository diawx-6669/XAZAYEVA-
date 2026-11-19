"""Run a policy against the env.

Agent policies run in a SEPARATE PROCESS and talk JSON lines over stdin/stdout; the env and
the grader stay in this (parent) process. The child gets an empty temp dir as cwd, no
episode paths and no seed. Oracle and attacks are grader-side and run in-process.

Protocol: parent -> child  {"observation": ..., "reward": r, "terminated": b, "truncated": b}
          child  -> parent {"action": {...}}
          parent -> child  {"close": true}
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import subprocess
import sys
import tempfile
import time

from .canon import dumps
from .env.env import AuditEnv
from .paths import ROOT


class ChildPolicy:
    def __init__(self, name: str, seed: int = 0):
        self.tmp = tempfile.TemporaryDirectory(prefix="auditenv-agent-")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT), "PYTHONHASHSEED": "0", "TZ": "UTC"}
        self.proc = subprocess.Popen([sys.executable, "-m", "auditenv.runner", "--child", "--policy", name,
                                      "--seed", str(seed)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, cwd=self.tmp.name, env=env, text=True, bufsize=1)
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
