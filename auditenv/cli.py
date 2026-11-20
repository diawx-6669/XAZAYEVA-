"""python -m auditenv {generate,export,run,trajectories,replay,leakscan,check,quick,demo,golden}"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from .canon import dumps, files_digest
from .paths import EPISODES_DIR, ROOT

TRAJ_PATH = ROOT / "trajectories" / "trajectories.jsonl"
AGENT_BASELINES = ["random_explorer", "simple_reconcile", "flag_all"]


def cmd_generate(a):
    from .generator.episode import generate_episode
    from .generator.export import write_episode

    ep = generate_episode(a.seed, a.config)
    out = write_episode(ep, a.out)
    print(f"{ep.episode_id}: {len(ep.truth['issues'])} issues -> {out}")


def cmd_export(a):
    from .generator.episode import generate_episode
    from .generator.export import write_episode
    from .selfcheck import load_split

    for split in ("train", "dev"):
        root = EPISODES_DIR / split
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        index = []
        for cfg, seed in load_split(split):
            ep = generate_episode(seed, cfg)
            write_episode(ep, root / ep.episode_id)
            index.append({"episode_id": ep.episode_id, "config": cfg, "seed": seed, "public_digest": files_digest(ep.files)})
        (root / "index.json").write_text(json.dumps(index, indent=1) + "\n", "utf-8")
        print(f"{split}: {len(index)} episodes -> {root}")


def episode_dirs(splits=("train", "dev")):
    out = []
    for split in splits:
        idx = json.loads((EPISODES_DIR / split / "index.json").read_text("utf-8"))
        out += [(split, EPISODES_DIR / split / e["episode_id"]) for e in idx]
    return out


def cmd_run(a):
    from .runner import run_episode

    kw = {"episode_dir": a.episode_dir} if a.episode_dir else {"seed": a.seed, "config": a.config}
    r = run_episode(a.policy, mode=a.mode, grader_log=a.log, **kw)
    if a.trajectory_out:
        Path(a.trajectory_out).write_text("".join(dumps(x) + "\n" for x in r["trajectory"]), "utf-8")
    print(json.dumps({k: r["grade"][k] for k in ("episode_id", "tp", "fp", "fn", "f1", "reward", "steps")}
                     if a.mode == "train" else {"episode_id": r["grade"]["episode_id"], "returned_reward": r["returned_reward"],
                                                "note": "eval mode: see grader log"}))


def cmd_trajectories(a):
    from .runner import run_episode

    TRAJ_PATH.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with TRAJ_PATH.open("w", encoding="utf-8") as fh:
        for split, d in episode_dirs():
            for pol in AGENT_BASELINES:
                r = run_episode(pol, episode_dir=d, mode="train")
                for rec in r["trajectory"]:
                    fh.write(dumps({**rec, "split": split}) + "\n")
                    n += 1
    print(f"wrote {n} steps -> {TRAJ_PATH}")


def _truths():
    out = {}
    for _, d in episode_dirs():
        t = json.loads((d / "grader" / "truth.json").read_text("utf-8"))
        out[t["episode_id"]] = t
    return out


def cmd_leakscan(a):
    from .leakscan import scan_lines

    path = Path(a.trajectories)
    lines = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]
    probs = scan_lines(lines, _truths())
    print(f"leakscan: {len(lines)} observations, {len(probs)} problems")
    for p in probs[:20]:
        print(" ", p)
    return 1 if probs else 0


def cmd_replay(a):
    """Re-play recorded actions and compare observations/rewards byte-for-byte."""
    from .env.env import AuditEnv

    lines = [json.loads(x) for x in Path(a.trajectories).read_text("utf-8").splitlines() if x.strip()]
    dirs = {d.name: d for _, d in episode_dirs()}
    runs, bad = {}, 0
    for rec in lines:
        runs.setdefault(rec["run_id"], []).append(rec)
    for rid, recs in sorted(runs.items()):
        recs.sort(key=lambda r: r["step"])
        eid = recs[0]["episode_id"]
        env = AuditEnv(mode=recs[0]["run"]["mode"])
        obs, _ = env.reset(episode_dir=dirs[eid])
        ok = dumps(obs) == dumps(recs[0]["observation"])
        for rec in recs[1:]:
            # action None = the policy hung/died; the runner then truncated the episode itself
            out = env.truncate_now() if rec["action"] is None else env.step(rec["action"])
            ok &= dumps(out[0]) == dumps(rec["observation"]) and out[1] == rec["reward"]
            ok &= out[2] == rec["terminated"] and out[3] == rec["truncated"]
            if "truncation_reason" in rec:
                ok &= env.truncation_reason == rec["truncation_reason"]
        bad += not ok
    print(f"replay: {len(runs)} runs, {bad} mismatches")
    return 1 if bad else 0


def cmd_check(a):
    from . import selfcheck

    rc = selfcheck.main()
    if TRAJ_PATH.exists():
        class A:
            trajectories = str(TRAJ_PATH)

        rc |= cmd_leakscan(A)
        rc |= cmd_replay(A)
    return rc


def cmd_quick(a):
    from .generator.episode import generate_episode
    from .grader.validate_truth import validate
    from .runner import run_episode

    t0 = time.monotonic()
    rc = 0
    for cfg, seed in (("dev-mixed", 1), ("interaction-heavy", 2), ("clean-only", 3)):
        ep = generate_episode(seed, cfg)
        v = validate(ep.public(), ep.truth)
        row = [f"{cfg}#{seed}", f"issues={len(ep.truth['issues'])}", "truth_ok" if v["ok"] else "TRUTH_BAD"]
        rc |= not v["ok"]
        for pol in ("random_explorer", "simple_reconcile", "flag_all", "oracle"):
            g = run_episode(pol, episode=ep, mode="train")["grade"]
            row.append(f"{pol}={g['reward']:+.3f}")
            if pol == "oracle" and g["reward"] != 1.0:
                rc = 1
        print("  ".join(row))
    print(f"quick smoke: {time.monotonic() - t0:.1f}s")
    return rc


def cmd_demo(a):
    from .generator.episode import generate_episode
    from .policies import make_policy
    from .env.env import AuditEnv

    ep = generate_episode(a.seed, a.config)
    env = AuditEnv(mode="train")
    obs, _ = env.reset(episode=ep)
    pol = make_policy("simple_reconcile")
    print(f"episode {ep.episode_id}  ({obs['manifest']['timezone']}, base {obs['manifest']['base_currency']}, "
          f"{obs['manifest']['counts']})")
    done = False
    while not done:
        action = pol.act(obs)
        obs, r, term, trunc, info = env.step(action)
        done = term or trunc
        if action["tool"] == "submit":
            print(f"step {env.steps_used:3d}: submit {len(action['args']['findings']['findings'])} findings")
            for f in action["args"]["findings"]["findings"]:
                print(f"           - {f['type']:<19} {f['affected_ids']} {f['claimed_amount_minor']} {f['currency']}"
                      f"  evidence={f['evidence_ids']}")
        else:
            res = obs.get("result", {})
            what = f"{len(res.get('records', []))} records" if "records" in res else ("record" if res else obs.get("error"))
            print(f"step {env.steps_used:3d}: {action['tool']}({ {k: v for k, v in action['args'].items() if k != 'cursor'} }) -> {what}")
    print(f"result: reward={r:+.3f} info={info}")


def cmd_analyze(a):
    from .analysis import main as analysis_main

    print(analysis_main(a.n, a.out, a.docs))


def cmd_golden(a):
    from .generator.episode import generate_episode

    out = {}
    for cfg, seed in (("train-easy", 11), ("dev-mixed", 22), ("interaction-heavy", 33)):
        ep = generate_episode(seed, cfg)
        out[f"{cfg}#{seed}"] = {"public": files_digest(ep.files),
                                "truth": __import__("hashlib").sha256(dumps(ep.truth).encode()).hexdigest()}
    p = ROOT / "tests" / "golden_hashes.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", "utf-8")
    print(f"wrote {p}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m auditenv")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--seed", type=int, required=True)
    g.add_argument("--config", default="dev-mixed")
    g.add_argument("--out", required=True)
    sub.add_parser("export")
    r = sub.add_parser("run")
    r.add_argument("--policy", required=True, choices=["random_explorer", "simple_reconcile", "flag_all", "oracle"])
    r.add_argument("--episode-dir")
    r.add_argument("--seed", type=int)
    r.add_argument("--config", default="dev-mixed")
    r.add_argument("--mode", default="train", choices=["train", "eval"])
    r.add_argument("--log")
    r.add_argument("--trajectory-out")
    sub.add_parser("trajectories")
    for name in ("replay", "leakscan"):
        p = sub.add_parser(name)
        p.add_argument("--trajectories", default=str(TRAJ_PATH))
    sub.add_parser("check")
    sub.add_parser("quick")
    d = sub.add_parser("demo")
    d.add_argument("--seed", type=int, default=9008)
    d.add_argument("--config", default="interaction-heavy")
    sub.add_parser("golden")
    an = sub.add_parser("analyze")
    an.add_argument("--n", type=int, default=300)
    an.add_argument("--out")
    an.add_argument("--docs", action="store_true", help="update the generated tables in docs/")
    dc = sub.add_parser("docs-check")
    dc.add_argument("--fix", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "docs-check":
        from .docs_check import main as docs_main

        return docs_main(["--fix"] if a.fix else [])
    fn = globals()["cmd_" + a.cmd]
    return fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
