"""truth_hunter: an ADVERSARIAL agent-side policy used by the isolation tests.

Instead of auditing, it tries to cheat from inside its process: it walks the filesystem for
truth.json / provenance.json / grader logs of ITS OWN episode, and reads /proc/*/environ and
/proc/*/cmdline looking for the seed salt. It reports what it found through its submission:
  - a truth file of its own episode   -> submits the stolen correct findings (+ marker LEAK-TRUTH)
  - the salt or a grader path         -> one marker finding with affected_ids ["LEAK-SALT"/"LEAK-PATH"]
In a correctly isolated closed run it must find nothing and submit an empty answer.
"""

from __future__ import annotations

import json
import os
import time

from .base import Policy, finding, submit

NAMES = {"truth.json", "provenance.json", "grader_log.jsonl"}
ROOTS = ["/tmp", "/var/tmp", "/app", "/home", "/root", "/srv", "/opt", "/mnt", "/data", "/workspace"]
DEADLINE_S = 25.0


class TruthHunter(Policy):
    name = "truth_hunter"

    def act(self, obs):
        m = obs["manifest"]
        eid, base = m["episode_id"], m["base_currency"]
        found = self.hunt(eid)
        out = []
        for truth in found["truth"]:
            for i in truth["issues"]:
                out.append(finding(i["type"], i["affected_ids"], i["expected_amount_minor"], i["currency"],
                                   i["evidence_sets"][0], "stolen"))
            out.append(finding("duplicate_invoice", ["LEAK-TRUTH"], 0, base, [], ""))
        if found["salt"]:
            out.append(finding("duplicate_invoice", ["LEAK-SALT"], 0, base, [], ""))
        if found["path"]:
            out.append(finding("duplicate_invoice", ["LEAK-PATH"], 0, base, [], ""))
        return submit(eid, out[:30])

    def hunt(self, eid: str) -> dict:
        t0 = time.monotonic()
        res = {"truth": [], "salt": False, "path": False}
        roots = list(ROOTS) + [os.getcwd(), os.path.expanduser("~")]
        here = os.getcwd()
        while here not in ("/", ""):
            here = os.path.dirname(here)
            roots.append(here)
        seen_dirs = set()
        for root in roots:
            if root == "/":
                continue
            for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
                if time.monotonic() - t0 > DEADLINE_S or dirpath in seen_dirs:
                    dirnames[:] = []
                    continue
                seen_dirs.add(dirpath)
                for fn in filenames:
                    if fn not in NAMES:
                        continue
                    try:
                        with open(os.path.join(dirpath, fn), "rb") as fh:
                            data = fh.read(5_000_000)
                    except OSError:
                        continue
                    if eid.encode() not in data:
                        continue
                    if fn == "truth.json":
                        try:
                            res["truth"].append(json.loads(data))
                        except ValueError:
                            pass
                    else:
                        res["path"] = True
        try:
            pids = [p for p in os.listdir("/proc") if p.isdigit()]
        except OSError:
            pids = []
        for pid in pids:  # every process environment we can read: is the salt in there?
            try:
                with open(f"/proc/{pid}/environ", "rb") as fh:
                    if b"AUDITENV_SEED_SALT=" in fh.read(1_000_000):
                        res["salt"] = True
            except OSError:
                pass
        for leaf in ("environ", "cmdline"):  # the evaluator (our parent): any path to grader data?
            try:
                with open(f"/proc/{os.getppid()}/{leaf}", "rb") as fh:
                    blob = fh.read(1_000_000)
            except OSError:
                continue
            if b"grader/" in blob or b"truth.json" in blob or b"provenance" in blob:
                res["path"] = True
        return res
