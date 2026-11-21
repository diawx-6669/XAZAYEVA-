"""Item 4: same seed + same config + same actions -> byte-identical records, transitions, rewards."""
import hashlib
import json
import sys

from common import JURY, WORK, cli, policy_cmd, run_policy


def tree_hash(d):
    h = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            h[str(p.relative_to(d))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return h


def canon(traj):
    return [json.dumps({k: t.get(k) for k in ("step", "action", "observation", "reward", "terminated", "truncated")},
                       sort_keys=True) for t in traj]


def main():
    res, problems = [], []
    from closed_run import PLAN
    for n, (cfg, seed) in enumerate(PLAN):
        cfgp = JURY / "configs" / f"{cfg}.json"
        a, b = WORK / "replay" / f"{n:02d}a", WORK / "replay" / f"{n:02d}b"
        cli("generate", "--seed", seed, "--config", cfgp, "--out", a)
        cli("generate", "--seed", seed, "--config", cfgp, "--out", b)
        c = {"generate_bytes_equal": tree_hash(a) == tree_hash(b),
             "equals_closed_copy": tree_hash(a) == tree_hash(WORK / "closed" / f"{n:02d}")}
        pol = ["random_explorer", "simple_reconcile"][n % 2]
        r1 = run_policy(policy_cmd(pol), f"replay/{n:02d}/r1", seed=seed, config=cfgp)
        r2 = run_policy(policy_cmd(pol), f"replay/{n:02d}/r2", seed=seed, config=cfgp)
        c["policy_rerun_traj_equal"] = canon(r1["traj"]) == canon(r2["traj"])
        acts = [t["action"] for t in r1["traj"] if t.get("action") is not None]
        af = WORK / "replay" / f"{n:02d}_actions.json"
        af.write_text(json.dumps(acts))
        r3 = run_policy(policy_cmd("replay", af), f"replay/{n:02d}/r3", seed=seed, config=cfgp)
        r4 = run_policy(policy_cmd("replay", af), f"replay/{n:02d}/r4", episode_dir=a)
        c["replayed_actions_traj_equal"] = canon(r1["traj"]) == canon(r3["traj"])
        c["seed_vs_episode_dir_equal"] = canon(r3["traj"]) == canon(r4["traj"])
        k = ("tp", "fp", "fn", "f1", "reward", "inspection_steps")
        c["grader_result_equal"] = all([x["log"][-1][j] for j in k] == [r1["log"][-1][j] for j in k] for x in (r2, r3, r4))
        c["traj_file_bytes_equal"] = r1["traj_path"].read_bytes() == r3["traj_path"].read_bytes()
        ok = all(c.values())
        res.append({"n": n, "policy": pol, "ok": ok, "checks": c, "n_actions": len(acts)})
        if not ok:
            problems.append(f"{n}: {[x for x, v in c.items() if not v]}")
    # salt matters: same seed without/with other salt -> other episode
    s1 = WORK / "replay" / "nosalt"
    cli("generate", "--seed", PLAN[0][1], "--config", JURY / "configs" / "jury-clean.json", "--out", s1, with_salt=False)
    salt_differs = tree_hash(s1) != tree_hash(WORK / "closed" / "00")
    (WORK / "replay_check.json").write_text(json.dumps({"results": res, "problems": problems,
                                                         "salt_changes_episode": salt_differs}, indent=1))
    print(f"replay passed: {sum(r['ok'] for r in res)}/20; salt changes episode: {salt_differs}")
    for p in problems:
        print("  ", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
