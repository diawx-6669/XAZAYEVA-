"""Item 5a: sandbox attacks. leak_probe (what the agent process sees) and regen_attack
(ps -> seed/config/salt -> rerun the open generator as a CLI -> oracle answer without truth files)."""
import json

from closed_run import PLAN
from common import JURY, WORK, policy_cmd, run_policy, salt


def main():
    out = {}
    r = run_policy(policy_cmd("leak_probe"), "attack/leak_probe", seed=PLAN[0][1], config=JURY / "configs/jury-clean.json")
    sub = [t for t in r["traj"] if t.get("action") and t["action"]["tool"] == "submit"][0]["action"]["args"]
    info = json.loads("".join(f["explanation"] for f in sub["findings"]))
    info["salt_value_is_real_salt"] = info.pop("salt_value") == salt()
    info["parent_chain"] = info["parent_chain"][:1]
    out["leak_probe"] = info
    rows = []
    for n in range(5, 20):
        cfg, seed = PLAN[n]
        a = run_policy(policy_cmd("regen_attack"), f"attack/regen/{n}", seed=seed, config=JURY / f"configs/{cfg}.json")
        b = run_policy(policy_cmd("regen_attack"), f"attack/regen_dir/{n}", episode_dir=WORK / "closed" / f"{n:02d}")
        rows.append({"n": n, "seed_mode": {k: a["log"][-1].get(k) for k in ("tp", "fp", "fn", "reward")},
                     "episode_dir_mode": {k: b["log"][-1].get(k) for k in ("tp", "fp", "fn", "reward")}})
    out["regen_attack"] = rows
    out["regen_seed_mode_full_marks"] = sum(x["seed_mode"]["reward"] == 1.0 for x in rows)
    out["regen_dir_mode_full_marks"] = sum(x["episode_dir_mode"]["reward"] == 1.0 for x in rows)
    (WORK / "attack_isolation.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in out.items() if k != "regen_attack"}, indent=1, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
