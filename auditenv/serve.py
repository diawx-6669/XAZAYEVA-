"""AuditEnv as a JSON-lines server, and a client with the same API as AuditEnv.

    python -m auditenv serve [--mode train|eval] [--log grader_log.jsonl]

Requests (one JSON object per line on stdin) -> one response line on stdout:
    {"cmd": "reset", "seed": 7, "config": "dev-mixed"}        -> {"observation": ..., "info": ...}
    {"cmd": "reset", "episode_dir": "episodes/dev/<id>"}       -> same
    {"cmd": "step", "action": {"tool": ..., "args": ...}}      -> {"observation", "reward", "terminated", "truncated", "info"}
    {"cmd": "spaces"}                                          -> {"action_space": ..., "observation_space": ..., "spec": ...}
    {"cmd": "close"}                                           -> {"closed": true}   (server exits)
A malformed request gets {"error": "bad_request"} - never a traceback. Output uses
json.dumps(..., allow_nan=False): NaN/Infinity can never reach a client.

The env, the truth and the grader log live in the SERVER process; an agent framework uses
AuditEnvClient (Gymnasium-style reset/step/close) and never has the episode's grader files in
its own memory.
"""

from __future__ import annotations

import json
import subprocess
import sys

from .paths import ROOT


def _dump(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def serve(mode: str = "train", log=None, stdin=None, stdout=None) -> int:
    from .env.env import AuditEnv

    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    env = AuditEnv(mode=mode, grader_log=log)
    for line in stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            cmd = req.get("cmd") if isinstance(req, dict) else None
            if cmd == "reset":
                kw = {k: req[k] for k in ("seed", "config", "episode_dir", "options") if k in req}
                obs, info = env.reset(**kw)
                out = {"observation": obs, "info": info}
            elif cmd == "step":
                obs, r, term, trunc, info = env.step(req.get("action"))
                out = {"observation": obs, "reward": r, "terminated": term, "truncated": trunc, "info": info}
            elif cmd == "spaces":
                out = {"action_space": env.action_space, "observation_space": env.observation_space, "spec": env.spec}
            elif cmd == "close":
                env.close()
                stdout.write(_dump({"closed": True}) + "\n")
                stdout.flush()
                return 0
            else:
                out = {"error": "bad_request"}
        except Exception:  # noqa: BLE001 - the contract: no tracebacks, no details
            out = {"error": "bad_request"}
        stdout.write(_dump(out) + "\n")
        stdout.flush()
    return 0


class AuditEnvClient:
    """Same calls as AuditEnv, served by `python -m auditenv serve` in a child process."""

    def __init__(self, mode: str = "train", grader_log=None, python: str | None = None):
        argv = [python or sys.executable, "-m", "auditenv", "serve", "--mode", mode]
        if grader_log:
            argv += ["--log", str(grader_log)]
        import os

        env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONHASHSEED="0", TZ="UTC")
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, bufsize=1, cwd=str(ROOT), env=env)
        self.mode = mode
        sp = self._call({"cmd": "spaces"})
        self.action_space, self.observation_space, self.spec = sp["action_space"], sp["observation_space"], sp["spec"]
        self.metadata = {"render_modes": [], "render_fps": None, "contract": "auditenv-json-1"}

    def _call(self, req: dict) -> dict:
        self.proc.stdin.write(_dump(req) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("auditenv server exited")
        out = json.loads(line)
        if "error" in out and set(out) == {"error"}:
            raise ValueError(out["error"])
        return out

    def reset(self, seed=None, config=None, *, episode_dir=None, options=None):
        req = {"cmd": "reset"}
        for k, v in (("seed", seed), ("config", config), ("episode_dir", episode_dir), ("options", options)):
            if v is not None:
                req[k] = str(v) if k == "episode_dir" else v
        out = self._call(req)
        return out["observation"], out["info"]

    def step(self, action):
        out = self._call({"cmd": "step", "action": action})
        return out["observation"], out["reward"], out["terminated"], out["truncated"], out["info"]

    def render(self):
        return None

    def close(self):
        if self.proc.poll() is None:
            try:
                self._call({"cmd": "close"})
            except (RuntimeError, ValueError, OSError):
                pass
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        for f in (self.proc.stdin, self.proc.stdout):
            try:
                f.close()
            except OSError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
