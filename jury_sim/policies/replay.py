"""Jury policy: replays a recorded list of actions (JSON file in argv[1]) one per observation."""
import json
import sys

actions = json.load(open(sys.argv[1], encoding="utf-8"))
for line, act in zip(sys.stdin, actions + [None]):
    msg = json.loads(line)
    if msg.get("close") or act is None:
        break
    sys.stdout.write(json.dumps({"action": act}) + "\n")
    sys.stdout.flush()
