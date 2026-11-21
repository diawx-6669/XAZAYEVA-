"""Item 3: 20 paired checks. transform (row shuffle + new IDs, every 2nd with --opaque-ids) ->
* truth of the twin == truth of the original mapped through id_map (types, amounts, evidence);
* public data of the twin == original mapped through id_map (as multisets: only order/IDs change);
* oracle answer of the ORIGINAL translated through id_map gets the same reward/F1 on the twin;
* simple_reconcile gets the same TP/FP/FN/F1 on the twin (its reward may differ only by steps).
"""
import csv
import json
import sys

from common import WORK, cli, policy_cmd, run_policy, submission
from grader import grade


def load_public(d, idmap=None):
    tr = (lambda x: idmap.get(x, x) if isinstance(x, str) else x) if idmap else (lambda x: x)

    def deep(o):
        if isinstance(o, dict):
            return {k: deep(v) for k, v in o.items()}
        if isinstance(o, list):
            return [deep(v) for v in o]
        return tr(o)

    out = {}
    for name in ("invoices.jsonl", "payments.jsonl"):
        out[name] = sorted(json.dumps(deep(json.loads(x)), sort_keys=True)
                           for x in (d / "public" / name).read_text().splitlines())
    for name in ("ledger.csv", "fx.csv"):
        with open(d / "public" / name, newline="") as f:
            out[name] = sorted(json.dumps(deep(dict(r)), sort_keys=True) for r in csv.DictReader(f))
    return out


def canon_truth(t, idmap=None):
    tr = (lambda x: idmap.get(x, x)) if idmap else (lambda x: x)
    return sorted(json.dumps({"type": i["type"], "affected": sorted(tr(a) for a in i["affected_ids"]),
                              "amount": i["expected_amount_minor"], "currency": i["currency"],
                              "ev": sorted(sorted(tr(e) for e in s) for s in i["evidence_sets"])}, sort_keys=True)
                  for i in t["issues"])


def main():
    results, problems = [], []
    for n in range(20):
        src = WORK / "closed" / f"{n:02d}"
        dst = WORK / "twins" / f"{n:02d}"
        opaque = n % 2 == 1
        args = ["transform", "--episode-dir", src, "--out", dst, "--seed", 5000 + n]
        if opaque:
            args.append("--opaque-ids")
        cli(*args)
        idmap = json.loads((dst / "grader" / "id_map.json").read_text())
        t0 = json.loads((src / "grader" / "truth.json").read_text())
        t1 = json.loads((dst / "grader" / "truth.json").read_text())
        checks = {}
        checks["truth_maps"] = canon_truth(t0, idmap) == canon_truth(t1)
        checks["public_maps"] = load_public(src, idmap) == load_public(dst)
        checks["ids_changed"] = load_public(src) != load_public(dst)
        checks["order_changed"] = (src / "public" / "ledger.csv").read_text().splitlines()[1:6] != \
            [l for l in (dst / "public" / "ledger.csv").read_text().splitlines()[1:6]]
        checks["episode_id_changed"] = t0["episode_id"] != t1["episode_id"]
        o0 = run_policy(policy_cmd("oracle", src / "grader" / "truth.json"), f"twins/{n:02d}/oracle0", episode_dir=src)
        o1 = run_policy(policy_cmd("oracle", src / "grader" / "truth.json", dst / "grader" / "id_map.json"),
                        f"twins/{n:02d}/oracle1", episode_dir=dst)
        g0 = grade(t0, *submission(o0["traj"]))
        g1 = grade(t1, *submission(o1["traj"]))
        l0, l1 = o0["log"][-1], o1["log"][-1]
        checks["oracle_reward_same"] = l0["reward"] == l1["reward"] and l0["f1"] == l1["f1"] and g0["reward"] == g1["reward"]
        checks["oracle_full_marks"] = l1["tp"] == len(t1["issues"]) and l1["fp"] == 0
        s0 = run_policy(policy_cmd("simple_reconcile"), f"twins/{n:02d}/sr0", episode_dir=src)
        s1 = run_policy(policy_cmd("simple_reconcile"), f"twins/{n:02d}/sr1", episode_dir=dst)
        a, b = s0["log"][-1], s1["log"][-1]
        checks["simple_reconcile_same"] = all(a[k] == b[k] for k in ("tp", "fp", "fn", "f1", "reward"))
        ok = all(checks.values())
        results.append({"n": n, "opaque": opaque, "ok": ok, "checks": checks, "renamed": len(idmap),
                        "oracle_reward": l1["reward"], "sr_reward": (a["reward"], b["reward"])})
        if not ok:
            problems.append(f"pair {n}: {[k for k, v in checks.items() if not v]}")
    (WORK / "transform_check.json").write_text(json.dumps({"results": results, "problems": problems}, indent=1))
    print(f"pairs passed: {sum(r['ok'] for r in results)}/20")
    for p in problems:
        print("  ", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
