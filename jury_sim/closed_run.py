"""Item 2: closed run on 20 new episodes (salted seeds, jury configs), 4 jury policies,
metrics recomputed by jury_sim/grader.py and compared with the team's grader log."""
import csv
import json
import statistics
import sys

from common import JURY, WORK, cli, policy_cmd, run_policy, submission
from grader import grade

PLAN = ([("jury-clean", 910001 + k) for k in range(5)] + [("jury-interact", 920001 + k) for k in range(5)]
        + [("jury-skew", 930001 + k) for k in range(5)] + [("jury-cutoff", 940001 + k) for k in range(5)])
POLICIES = ["random_explorer", "simple_reconcile", "flag_all", "oracle"]


def public_ids(d):
    ids = {"policy"}
    for name in ("invoices.jsonl", "payments.jsonl"):
        for line in (d / "public" / name).read_text().splitlines():
            ids.add(json.loads(line)["doc_id"])
    with open(d / "public" / "ledger.csv", newline="") as f:
        ids |= {r["row_id"] for r in csv.DictReader(f)}
    with open(d / "public" / "fx.csv", newline="") as f:
        ids |= {f"fx:{r['date']}:{r['source_currency']}:{r['target_currency']}" for r in csv.DictReader(f)}
    return ids


def main():
    rows, problems, episodes = [], [], []
    for n, (cfg, seed) in enumerate(PLAN):
        d = WORK / "closed" / f"{n:02d}"
        cfgp = JURY / "configs" / f"{cfg}.json"
        cli("generate", "--seed", seed, "--config", cfgp, "--out", d)
        truth = json.loads((d / "grader" / "truth.json").read_text())
        prov = json.loads((d / "grader" / "provenance.json").read_text())
        man = json.loads((d / "public" / "manifest.json").read_text())
        scen = prov.get("plan", {}).get("scenarios") or []
        ep = {"n": n, "config": cfg, "seed": seed, "episode_id": truth["episode_id"], "n_issues": len(truth["issues"]),
              "types": sorted(i["type"] for i in truth["issues"]), "scenarios": scen, "salted": prov.get("seed_salted"),
              "counts": man["counts"], "base": man["base_currency"], "tz": man["timezone"]}
        episodes.append(ep)
        if cfg == "jury-clean" and truth["issues"]:
            problems.append(f"ep{n}: clean config but {len(truth['issues'])} issues")
        if cfg == "jury-interact" and len(scen) < 1:
            problems.append(f"ep{n}: interaction config without scenarios")
        pub = public_ids(d)
        for i in truth["issues"]:
            for s in i["evidence_sets"]:
                miss = [x for x in s if x not in pub]
                if miss or len(s) > 6:
                    problems.append(f"ep{n} {i['issue_id']}: evidence not public / >6: {miss}")
            if not 1 <= len(i["evidence_sets"]) <= 3:
                problems.append(f"ep{n} {i['issue_id']}: {len(i['evidence_sets'])} evidence sets")
        for pol in POLICIES:
            tag = f"closed/{n:02d}/{pol}"
            if pol == "oracle":
                res = run_policy(policy_cmd("oracle", d / "grader" / "truth.json"), tag, episode_dir=d)
            else:
                res = run_policy(policy_cmd(pol), tag, seed=seed, config=cfgp)
            if res["rc"] != 0 or not res["log"]:
                problems.append(f"ep{n} {pol}: rc={res['rc']} log={len(res['log'])} {res['stderr'][-300:]}")
                continue
            got_ep = res["traj"][0]["observation"]["manifest"]["episode_id"]
            if got_ep != truth["episode_id"]:
                problems.append(f"ep{n} {pol}: --seed run episode {got_ep} != generated {truth['episode_id']}")
            args, steps, trunc = submission(res["traj"])
            mine = grade(truth, args, steps, trunc)
            theirs = res["log"][-1]
            diff = {k: (mine[k], theirs.get(k)) for k in ("tp", "fp", "fn", "inspection_steps")
                    if mine[k] != theirs.get(k)}
            for k in ("f1", "reward", "precision", "recall"):
                if abs(mine[k] - float(theirs.get(k, 99))) > 1e-9:
                    diff[k] = (mine[k], theirs.get(k))
            if diff:
                problems.append(f"ep{n} {pol}: grader mismatch {diff}")
            rows.append({"n": n, "config": cfg, "policy": pol, "clean": not truth["issues"], **mine,
                         "team": {k: theirs.get(k) for k in ("tp", "fp", "fn", "f1", "reward", "inspection_steps")},
                         "wall": res["wall"], "n_actions": sum(1 for t in res["traj"] if t.get("action") is not None)})
    summary = {}
    for pol in POLICIES:
        rs = [r for r in rows if r["policy"] == pol]
        if not rs:
            continue
        tp, fp, fn = (sum(r[k] for r in rs) for k in ("tp", "fp", "fn"))
        defined_p = [r["precision"] for r in rs if r["tp"] + r["fp"]]
        defined_r = [r["recall"] for r in rs if r["tp"] + r["fn"]]
        summary[pol] = {
            "episodes": len(rs), "TP": tp, "FP": fp, "FN": fn,
            "P_micro": tp / (tp + fp) if tp + fp else 0.0, "R_micro": tp / (tp + fn) if tp + fn else 0.0,
            "F1_micro": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1.0,
            "P_macro": statistics.mean(defined_p) if defined_p else None,
            "R_macro": statistics.mean(defined_r) if defined_r else None,
            "F1_macro": statistics.mean(r["f1"] for r in rs),
            "return_mean": statistics.mean(r["reward"] for r in rs),
            "return_clean": statistics.mean(r["reward"] for r in rs if r["clean"]),
            "return_dirty": statistics.mean(r["reward"] for r in rs if not r["clean"]),
            "steps_mean": statistics.mean(r["n_actions"] for r in rs),
            "wall_p50": statistics.median(r["wall"] for r in rs), "wall_max": max(r["wall"] for r in rs),
        }
    out = {"episodes": episodes, "summary": summary, "problems": problems, "rows": rows}
    (WORK / "closed_run.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1))
    print("problems:", len(problems))
    for p in problems:
        print("  ", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
