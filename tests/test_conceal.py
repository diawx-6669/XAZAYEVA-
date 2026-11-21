"""The agent must not learn the seed, the config, data paths or the salt from the evaluator's
process information (`ps`, /proc/<ppid>/cmdline, `ps -E` / environ): `python -m auditenv run`
re-execs itself with a neutral argv and hands the real arguments and the salt over a pipe."""
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPY = ROOT / "tests" / "agents" / "ps_spy.py"

pytestmark = pytest.mark.skipif(os.name != "posix", reason="exec/ps semantics are POSIX")


def spy_run(tmp_path, extra=None):
    salt = "jury-" + secrets.token_hex(16)
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT), "PYTHONHASHSEED": "0", "TZ": "UTC",
           "AUDITENV_SEED_SALT": salt, **(extra or {})}
    traj = tmp_path / "traj.jsonl"
    r = subprocess.run([sys.executable, "-m", "auditenv", "run", "--policy-cmd", f"{sys.executable} {SPY}",
                        "--seed", "987654321", "--config", "dev-mixed", "--mode", "eval",
                        "--log", str(tmp_path / "log.jsonl"), "--trajectory-out", str(traj)],
                       cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    sub = [json.loads(x)["action"] for x in traj.read_text().splitlines()]
    sub = [a for a in sub if a and a.get("tool") == "submit"][0]["args"]
    sub = sub["findings"] if isinstance(sub.get("findings"), dict) else sub
    return salt, "".join(f["explanation"] for f in sub["findings"]), r


def test_agent_sees_no_seed_config_paths_or_salt(tmp_path):
    salt, seen, r = spy_run(tmp_path)
    assert "__run_concealed" in seen  # the spy did read the parent: only the neutral argv is there
    for secret in ("987654321", "dev-mixed", "--seed", str(tmp_path), salt, "AUDITENV_SEED_SALT"):
        assert secret not in seen, secret


def test_positive_control_without_concealment_seed_is_visible(tmp_path):
    """Without the re-exec the same spy reads the seed from the evaluator's command line: the
    concealment, not luck, is what hides it in the test above."""
    salt, seen, _ = spy_run(tmp_path, {"AUDITENV_NO_CONCEAL": "1"})
    assert "987654321" in seen and "dev-mixed" in seen
    if sys.platform == "darwin":  # `ps -E` shows a same-uid process's initial environment
        assert salt in seen


def test_salt_still_reaches_the_generator(tmp_path):
    """After the re-exec the episode is still generated WITH the salt (otherwise the fix would
    silently turn the closed run into the open, brute-forceable seed space)."""
    _, _, r_salted = spy_run(tmp_path)
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT), "PYTHONHASHSEED": "0", "TZ": "UTC"}
    out = subprocess.run([sys.executable, "-m", "auditenv", "generate", "--seed", "987654321", "--config", "dev-mixed",
                          "--out", str(tmp_path / "open")], cwd=tmp_path, env=env, capture_output=True, text=True,
                         timeout=120)
    open_id = out.stdout.split(":")[0]
    salted_id = json.loads(r_salted.stdout.splitlines()[-1])["episode_id"]
    assert open_id.startswith("ep-") and salted_id != open_id
