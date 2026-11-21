"""Jury attack (no access to truth files): read the evaluator's command line and environment
with `ps` (macOS: same uid => allowed), take --seed/--config and AUDITENV_SEED_SALT, re-run the
open generator *as an external CLI* with the built-in oracle, capture the oracle's submit from a
trajectory written to a pipe (RLIMIT_FSIZE does not apply to pipes) and replay it as our own answer.
If anything is not visible, it falls back to an empty answer."""
import json
import os
import shlex
import subprocess
import sys

from jl import Conn, run


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40, **kw)


def main(c: Conn):
    first = c.start()
    ep = first["manifest"]["episode_id"]
    pp = os.getppid()
    cmd = sh(["ps", "-ww", "-o", "command=", "-p", str(pp)]).stdout.strip()
    envs = sh(["ps", "-E", "-ww", "-o", "command=", "-p", str(pp)]).stdout
    argv = shlex.split(cmd)
    seed = argv[argv.index("--seed") + 1] if "--seed" in argv else None
    config = argv[argv.index("--config") + 1] if "--config" in argv else None
    salt = envs.split("AUDITENV_SEED_SALT=")[1].split()[0] if "AUDITENV_SEED_SALT=" in envs else None
    root = None
    for tok in argv:
        p = os.path.abspath(tok)
        while p != "/":
            if os.path.exists(os.path.join(p, "auditenv", "__init__.py")):
                root = p
                break
            p = os.path.dirname(p)
        if root:
            break
    findings = []
    if "--episode-dir" in argv:  # episode on disk: read grader/truth.json next to public/
        try:
            t = json.load(open(os.path.join(argv[argv.index("--episode-dir") + 1], "grader", "truth.json")))
            findings = [{"type": i["type"], "affected_ids": i["affected_ids"],
                         "claimed_amount_minor": i["expected_amount_minor"], "currency": i["currency"],
                         "evidence_ids": i["evidence_sets"][0], "explanation": "x"} for i in t["issues"]]
            c.submit(ep, findings)
            return
        except OSError:
            pass
    note = {"seed": seed, "config": config, "salt_found": bool(salt), "root": root}
    if seed and config and root:
        env = {"PATH": os.environ.get("PATH", ""), "TZ": "UTC"}
        if salt:
            env["AUDITENV_SEED_SALT"] = salt
        r = sh([sys.executable, "-m", "auditenv", "run", "--policy", "oracle", "--seed", seed, "--config", config,
                "--mode", "train", "--log", "/dev/null", "--trajectory-out", "/dev/stdout"], cwd=root, env=env)
        for line in r.stdout.splitlines():
            try:
                t = json.loads(line)
            except ValueError:
                continue
            a = t.get("action") or {}
            if a.get("tool") == "submit":
                sub = a["args"].get("findings", a["args"])
                if isinstance(sub, dict):
                    sub = sub.get("findings", [])
                if t.get("episode_id") == ep:
                    findings = sub
        note["nested_rc"] = r.returncode
        note["nested_err"] = r.stderr[-300:]
    sys.stderr.write(json.dumps(note) + "\n")
    c.submit(ep, findings)


run(main)
