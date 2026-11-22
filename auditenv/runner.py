"""Run a policy against the env.

Agent policies run in a SEPARATE PROCESS and talk JSON lines over stdin/stdout; the env and
the grader stay in this (parent) process. The child gets an empty temp dir as cwd, a
cleared environment (no salt, no seed, no data paths), a read-only code-only copy of the package,
rlimits and (under root) the `nobody` uid; see ChildPolicy. Oracle and attacks are grader-side
and run in-process.

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


# ------------------------------------------------------------------ sandbox
AS_LIMIT = 1536 * 1024 * 1024  # 1.5 GiB address space (Python + a policy fit with room to spare)
CPU_LIMIT_S = 65  # a bit above the 60 s wall-clock budget
NOFILE_LIMIT = 64
NPROC_LIMIT = 64  # only enforced together with the unprivileged uid
MAX_LINE = 2 * 1024 * 1024  # one action line from the agent: at most ~2 MB
NOBODY = 65534

_CODE_DIR = None


def agent_code_dir() -> str:
    """A private copy of the auditenv package (code only: no schemas, configs, episodes or grader data),
    made once per evaluator process and made READ-ONLY (chmod -R a-w). The agent imports policies from
    here, never from the repository the grader runs from."""
    global _CODE_DIR
    if _CODE_DIR is None:
        d = tempfile.mkdtemp(prefix="auditenv-code-")
        shutil.copytree(ROOT / "auditenv", Path(d) / "auditenv", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for root, dirs, files in os.walk(d):
            for f in files:
                os.chmod(os.path.join(root, f), 0o444)
            os.chmod(root, 0o555)

        def _cleanup(path=d):
            for root, dirs, files in os.walk(path):
                os.chmod(root, 0o755)
            shutil.rmtree(path, ignore_errors=True)

        atexit.register(_cleanup)
        _CODE_DIR = d
    return _CODE_DIR


_readonly_code_copy = agent_code_dir  # older name used by tests


def harden_evaluator() -> bool:
    """Mark the evaluator process non-dumpable (Linux prctl PR_SET_DUMPABLE=0): its
    /proc/<pid>/environ, mem, fd and maps become unreadable for other non-root processes,
    so the agent cannot read the seed salt or open file handles of its parent."""
    if os.environ.get("AUDITENV_INSECURE_DUMPABLE") == "1":  # only for the isolation test's positive control
        return False
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(4, 0, 0, 0, 0) == 0  # PR_SET_DUMPABLE = 4
    except (OSError, AttributeError):
        return False


AGENT_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "TZ": "UTC", "LANG": "C.UTF-8"}
# A bare interpreter name at the start of --policy-cmd runs under the evaluator's own Python. AGENT_ENV's PATH
# often has no `python` (macOS, Debian without python-is-python3), so "python agent.py" from README would fail.
PYTHON_ALIASES = ("python", "python3")


def _can_drop_privileges() -> bool:
    return hasattr(os, "getuid") and os.getuid() == 0 and os.environ.get("AUDITENV_KEEP_UID") != "1"


def _apply_limits(drop: bool):
    """preexec_fn (runs in the child after fork, after setuid when `user=` is given)."""
    import resource
    import signal

    def lim(kind, value):
        try:
            resource.setrlimit(kind, (value, value))
        except (ValueError, OSError):
            pass

    lim(resource.RLIMIT_AS, AS_LIMIT)
    lim(resource.RLIMIT_CPU, CPU_LIMIT_S)
    lim(resource.RLIMIT_NOFILE, NOFILE_LIMIT)
    lim(resource.RLIMIT_CORE, 0)
    lim(resource.RLIMIT_FSIZE, 0)  # no file content can be written at all (pipes are not files)
    if drop:
        lim(resource.RLIMIT_NPROC, NPROC_LIMIT)
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)  # a write beyond FSIZE fails with EFBIG instead of killing


def _uid_processes(uid: int) -> list:
    out = []
    for pid in os.listdir("/proc") if os.path.isdir("/proc") else []:
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/status", encoding="utf-8") as fh:
                status = fh.read()
        except OSError:
            continue
        fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
        if fields.get("State", "").strip().startswith("Z"):
            continue  # already dead, waiting to be reaped
        if int(fields.get("Uid", "-1 0").split()[0]) == uid:
            out.append(int(pid))
    return out


def _sweep_uid(uid: int):
    """After an unprivileged agent: kill every process left under its uid (daemons that escaped the
    process group) and delete files it left in shared temp dirs (a channel to the next episode)."""
    import shutil
    import signal

    for _ in range(50):  # kill until none is left (a fork may race the first sweep), at most ~1 s
        pids = _uid_processes(uid)
        if not pids:
            break
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        time.sleep(0.02)
    for tmpdir in ("/tmp", "/var/tmp", "/dev/shm"):
        try:
            entries = os.listdir(tmpdir)
        except OSError:
            continue
        for name in entries:
            path = os.path.join(tmpdir, name)
            try:
                if os.lstat(path).st_uid == uid:
                    if os.path.isdir(path) and not os.path.islink(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.unlink(path)
            except OSError:
                pass


class ChildPolicy:
    """An agent in a separate, constrained process, talking JSON lines over stdin/stdout.

    Layers (all active together):
    - the evaluator marks itself non-dumpable (prctl): its /proc/<pid>/environ, mem, fd are closed to the agent;
    - `python -I -S` (no PYTHON* variables, no site-packages, no cwd on sys.path), environment = AGENT_ENV only
      (no salt, no seed, no paths); policy code from a private READ-ONLY copy of the package;
    - cwd = an empty private temp dir; own session (start_new_session) -> the whole group is killed on close;
    - rlimits: AS 1.5 GiB, CPU 65 s, 64 open files, no core dumps, FSIZE 0 (SIGXFSZ ignored);
    - when the evaluator runs as root: the agent runs as `nobody` (+ NPROC limit), so repository, truth,
      grader log and code are not writable; leftovers in /tmp and stray processes of that uid are swept;
    - an action line longer than ~2 MB ends the run like a dead policy.
    `cmd` runs an external agent (python -m auditenv run --policy-cmd ...) under the same sandbox.
    """

    def __init__(self, name: str | None = None, seed: int = 0, cmd=None, limits: bool = True):
        import shlex

        harden_evaluator()
        self.tmp = tempfile.TemporaryDirectory(prefix="auditenv-agent-")
        self.drop = limits and _can_drop_privileges()
        if self.drop:
            os.chown(self.tmp.name, NOBODY, NOBODY)
        env = dict(AGENT_ENV)
        if cmd:
            argv = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
            if argv and argv[0] in PYTHON_ALIASES:
                argv[0] = sys.executable
            argv = [os.path.abspath(x) if os.path.exists(x) and (i > 0 or os.sep in x) else x for i, x in enumerate(argv)]
        else:
            boot = (f"import sys; sys.path.insert(0, {agent_code_dir()!r}); "
                    f"from auditenv.runner import _child_main; _child_main({name!r}, {int(seed)})")
            argv = [sys.executable, "-I", "-S", "-c", boot]
        self.env = dict(env)  # kept for audits/tests: exactly what the agent process received
        kw = {}
        if self.drop:
            kw.update(user=NOBODY, group=NOBODY, extra_groups=[])
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     cwd=self.tmp.name, env=env, text=True, bufsize=1, close_fds=True,
                                     start_new_session=True,
                                     preexec_fn=(lambda: _apply_limits(self.drop)) if limits else None, **kw)
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.proc.stdout, selectors.EVENT_READ)

        self.sel = selectors.DefaultSelector()
        self.sel.register(self.proc.stdout, selectors.EVENT_READ)

    def act(self, obs, reward, terminated, truncated, timeout: float):
        try:
            self.proc.stdin.write(dumps({"observation": obs, "reward": reward, "terminated": terminated,
                                         "truncated": truncated}) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            return None
        if not self.sel.select(timeout=max(0.0, timeout)):
            return None
        try:
            line = self.proc.stdout.readline(MAX_LINE + 1)
        except (OSError, ValueError):
            return None
        if not line or (len(line) > MAX_LINE and not line.endswith("\n")):
            return None  # dead, or an over-long line: protocol violation
        try:
            msg = json.loads(line)
            return msg.get("action") if isinstance(msg, dict) else {"tool": "__invalid__"}
        except ValueError:
            return {"tool": "__invalid__"}

    def close(self):
        import signal

        try:
            self.proc.stdin.write(dumps({"close": True}) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)  # the whole session, grandchildren included
        except OSError:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        if self.drop:
            _sweep_uid(NOBODY)
        self.sel.close()
        for f in (self.proc.stdin, self.proc.stdout):
            try:
                f.close()
            except OSError:
                pass
        self.tmp.cleanup()


class InProcess:
    def __init__(self, policy):
        self.policy = policy

    def act(self, obs, reward, terminated, truncated, timeout):
        return self.policy.act(obs)

    def close(self):
        pass


def run_id(episode_id: str, policy: str, policy_rng: int, mode: str, repeat: int = 0) -> str:
    """Deterministic, unique per (episode, policy, policy RNG, mode, repeat): replays and audits can
    group trajectory lines by run without relying on line order. (No 'seed' in field names: leakscan.)"""
    from .canon import sha256_hex

    return "run-" + sha256_hex(f"{episode_id}|{policy}|{policy_rng}|{mode}|{repeat}".encode())[:16]


def run_metadata(env, mode: str) -> dict:
    from . import GENERATOR_VERSION, __version__

    m = env._data.manifest
    return {"env_version": __version__, "generator_version": m.get("generator_version", GENERATOR_VERSION),
            "config_hash": m.get("config_hash"), "mode": mode, "max_steps": env.max_steps,
            "time_limit_s": env.time_limit}


def run_episode(policy_name: str, *, episode=None, episode_dir=None, seed=None, config=None, mode="train",
                grader_log=None, policy_seed: int = 0, isolate: bool = True, record: bool = True,
                time_limit: float = 60.0, policy_obj=None, policy_cmd=None) -> dict:
    env = AuditEnv(mode=mode, grader_log=grader_log, time_limit=time_limit)
    env.run_meta = {"policy": policy_name}
    obs, info = env.reset(seed=seed, config=config, episode_dir=episode_dir, episode=episode)
    if policy_cmd is not None:
        agent = ChildPolicy(cmd=policy_cmd)
    elif policy_obj is not None:
        agent = InProcess(policy_obj)
    elif policy_name == "oracle":
        from .policies.oracle import Oracle

        agent = InProcess(Oracle(truth=env._grader._truth))
    elif policy_name == "oracle_observing":
        from .policies.oracle import OracleObserving

        agent = InProcess(OracleObserving(truth=env._grader._truth, public=env._data))
    elif isolate:
        agent = ChildPolicy(policy_name, policy_seed)
    else:
        from .policies import make_policy

        agent = InProcess(make_policy(policy_name, policy_seed))
    traj = []
    t0 = time.monotonic()
    eid = env.episode_id
    rid = run_id(eid, policy_name, policy_seed, mode)
    meta = run_metadata(env, mode)
    if record:
        traj.append({"episode_id": eid, "run_id": rid, "policy": policy_name, "step": 0, "action": None,
                     "observation": obs, "reward": 0.0, "terminated": False, "truncated": False, "run": meta})
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
                rec = {"episode_id": eid, "run_id": rid, "policy": policy_name, "step": env.steps_used,
                       "action": action, "observation": obs, "reward": reward, "terminated": terminated,
                       "truncated": truncated}
                if terminated or truncated:
                    rec["truncation_reason"] = env.truncation_reason
                traj.append(rec)
    finally:
        agent.close()
    elapsed = time.monotonic() - t0
    g = dict(env.last_grade or {})
    g["elapsed_s"] = round(elapsed, 4)
    g["steps"] = env.steps_used
    g["run_id"] = rid
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
