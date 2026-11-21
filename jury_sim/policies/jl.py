"""Tiny JSON-lines driver shared by the jury policies (stdlib only, no auditenv).

Protocol (docs/ADAPTER.md): env -> {"observation", "reward", "terminated", "truncated"} or
{"close": true}; agent -> {"action": {"tool", "args"}} exactly once per observation.
"""
import json
import sys


class Conn:
    def __init__(self):
        self.first = None
        self.steps_remaining = 100

    def _read(self):
        line = sys.stdin.readline()
        if not line:
            raise EOFError
        msg = json.loads(line)
        if msg.get("close"):
            raise EOFError
        obs = msg.get("observation", {})
        if "steps_remaining" in obs:
            self.steps_remaining = obs["steps_remaining"]
        return msg

    def start(self):
        self.first = self._read()["observation"]
        return self.first

    def call(self, tool, **args):
        sys.stdout.write(json.dumps({"action": {"tool": tool, "args": args}}) + "\n")
        sys.stdout.flush()
        return self._read()["observation"]

    def submit(self, episode_id, findings):
        sys.stdout.write(json.dumps({"action": {"tool": "submit", "args": {
            "episode_id": episode_id, "findings": findings}}}) + "\n")
        sys.stdout.flush()
        try:
            self._read()
        except EOFError:
            pass

    def list_all(self, table, reserve=2):
        rows, cursor = [], None
        while self.steps_remaining > reserve:
            args = {"table": table, "limit": 50}
            if cursor:
                args["cursor"] = cursor
            obs = self.call("list_records", **args)
            res = obs.get("result")
            if not res:
                break
            rows.extend(res["records"])
            cursor = res.get("next_cursor")
            if not cursor:
                break
        return rows


def run(main):
    try:
        main(Conn())
    except EOFError:
        pass
