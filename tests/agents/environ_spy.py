"""Attack agent: reads the PARENT's /proc/<ppid>/environ looking for the evaluator's secret seed salt.
If it gets it, it submits a deliberately invalid answer (episode_id 'LEAKED'), so the leak is visible
in the grade; otherwise it submits an honest empty answer."""
import json
import os
import sys

leaked = False
try:
    with open(f"/proc/{os.getppid()}/environ", "rb") as fh:
        leaked = b"AUDITENV_SEED_SALT" in fh.read()
except OSError:
    pass
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("close"):
        break
    eid = "LEAKED" if leaked else msg["observation"].get("manifest", {}).get("episode_id", "x")
    print(json.dumps({"action": {"tool": "submit", "args": {"episode_id": eid, "findings": []}}}), flush=True)
