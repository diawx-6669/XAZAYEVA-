#!/usr/bin/env python3
"""Builds site/replay.html: a static, offline trajectory viewer with 5 embedded episodes.

    python tools/build_replay.py            # writes site/replay.html
    python tools/build_replay.py --check    # exit 1 if site/replay.html is stale

Only what the AGENT saw goes in: the recorded trajectories (actions, observations, rewards, flags) from
trajectories/trajectories.jsonl. No truth.json, no provenance, no grader log. The output is byte-stable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAJ = ROOT / "trajectories" / "trajectories.jsonl"
TEMPLATE = ROOT / "tools" / "replay_template.html"
OUT = ROOT / "site" / "replay.html"

# (episode_id, label) — chosen to show different situations; labels describe the PUBLIC setting only.
EPISODES = [
    ("ep-vq9n3qwk8v", "KWD, экспонента 3"),
    ("ep-vw9vceq4qf", ""),
    ("ep-ap6e6dpf7p", ""),
    ("ep-p2ndc2nyey", "+ обрыв политик"),
    ("ep-wtma6rce3f", ""),
]
POLICY_ORDER = ["simple_reconcile", "random_explorer", "flag_all", "step_burner", "hung"]
STEP_KEYS = ("step", "action", "observation", "reward", "terminated", "truncated", "truncation_reason")


def build_data(lines) -> dict:
    wanted = [e for e, _ in EPISODES]
    runs = {}
    first = {}
    split = {}
    for line in lines:
        r = json.loads(line)
        eid = r["episode_id"]
        if eid not in wanted:
            continue
        split[eid] = r["split"]
        key = (eid, r["run_id"])
        runs.setdefault(key, {"policy": r["policy"], "run_id": r["run_id"], "steps": []})
        s = {k: r[k] for k in STEP_KEYS if k in r}
        if r["step"] == 0:
            first.setdefault(eid, r["observation"])  # the episode card (manifest) uses the first run's
        runs[key]["steps"].append(s)
    out = []
    for eid, label in EPISODES:
        rs = sorted((v for (e, _), v in runs.items() if e == eid),
                    key=lambda v: (POLICY_ORDER.index(v["policy"]) if v["policy"] in POLICY_ORDER else 99, v["run_id"]))
        if eid not in first or not rs:
            raise SystemExit(f"{eid}: not in {TRAJ}")
        for v in rs:
            v["steps"].sort(key=lambda s: s["step"])
        out.append({"episode_id": eid, "label": label, "split": split[eid], "first": first[eid], "runs": rs})
    return {"episodes": out, "source": "trajectories/trajectories.jsonl"}


def render(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    blob = blob.replace("</", "<\\/")  # cannot close the <script> element early
    html = TEMPLATE.read_text("utf-8")
    if html.count("/*__DATA__*/") != 1:
        raise SystemExit("template must contain exactly one /*__DATA__*/ placeholder")
    return html.replace("/*__DATA__*/", blob)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    html = render(build_data(TRAJ.read_text("utf-8").splitlines()))
    if a.check:
        ok = OUT.exists() and OUT.read_text("utf-8") == html
        print("replay.html is up to date" if ok else "replay.html is STALE: run python tools/build_replay.py")
        return 0 if ok else 1
    OUT.write_text(html, "utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(html.encode())} bytes, {len(EPISODES)} episodes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
