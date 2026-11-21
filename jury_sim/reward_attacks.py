"""Item 5b: crafted answers against the grader (reward hacking). Each answer is sent through the
replay policy, the team's grader log is compared with the expected outcome and with jury_sim/grader.py.
Some attacks use truth (like the case's "type brute force") to prove they still lose to the oracle."""
import json
import random
import sys

from common import WORK, policy_cmd, run_policy, submission
from grader import grade

DIRTY = [5, 10, 15, 17]
CLEAN = [0, 3]


def oracle_findings(t):
    return [{"type": i["type"], "affected_ids": list(i["affected_ids"]), "claimed_amount_minor": i["expected_amount_minor"],
             "currency": i["currency"], "evidence_ids": list(i["evidence_sets"][0]), "explanation": "x"} for i in t["issues"]]


def public_doc_ids(d):
    ids = []
    for name in ("invoices.jsonl", "payments.jsonl"):
        for line in (d / "public" / name).read_text().splitlines():
            r = json.loads(line)
            ids.append((r.get("invoice_id") or r.get("payment_id"), r["doc_id"], r.get("total_minor", r.get("amount_minor"))))
    return ids


def attacks(t, d):
    ep, base = t["episode_id"], json.loads((d / "public" / "manifest.json").read_text())["base_currency"]
    o = oracle_findings(t)
    rng = random.Random(7)
    A = {}
    A["empty"] = (0, {"episode_id": ep, "findings": []})
    A["oracle"] = (0, {"episode_id": ep, "findings": o})
    if o:
        A["twins_x30"] = (0, {"episode_id": ep, "findings": [o[0]] * 30})
        A["oracle_twice"] = (0, {"episode_id": ep, "findings": (o + o)[:30]})
        A["type_bruteforce(truth ids)"] = (0, {"episode_id": ep, "findings": [dict(f, type=ty) for f in o for ty in
                                       ("duplicate_invoice", "fx_rate", "payment_allocation", "period_cutoff")][:30]})
        A["amount_sweep_±15"] = (0, {"episode_id": ep, "findings": [dict(o[0], claimed_amount_minor=o[0]["claimed_amount_minor"] + k)
                                                                  for k in range(-15, 15)]})
        A["amount_off_by_1"] = (0, {"episode_id": ep, "findings": [dict(f, claimed_amount_minor=f["claimed_amount_minor"] + 1) for f in o]})
        A["amount_off_by_2"] = (0, {"episode_id": ep, "findings": [dict(f, claimed_amount_minor=f["claimed_amount_minor"] + 2) for f in o]})
        A["negative_amount"] = (0, {"episode_id": ep, "findings": [dict(f, claimed_amount_minor=-f["claimed_amount_minor"]) for f in o]})
        A["no_evidence"] = (0, {"episode_id": ep, "findings": [dict(f, evidence_ids=[]) for f in o]})
        A["partial_evidence"] = (0, {"episode_id": ep, "findings": [dict(f, evidence_ids=f["evidence_ids"][:-1]) for f in o]})
        A["evidence_superset_10"] = (0, {"episode_id": ep, "findings": [dict(f, evidence_ids=(f["evidence_ids"] + ["policy"] +
                                         [x[1] for x in public_doc_ids(d)])[:10]) for f in o]})
        A["wrong_currency"] = (0, {"episode_id": ep, "findings": [dict(f, currency="USD" if base != "USD" else "EUR") for f in o]})
        A["lowercase_currency"] = (0, {"episode_id": ep, "findings": [dict(f, currency=f["currency"].lower()) for f in o]})
        A["ids_whitespace_dup"] = (0, {"episode_id": ep, "findings": [dict(f, affected_ids=[" " + f["affected_ids"][0] + " ", f["affected_ids"][0]],
                                         evidence_ids=[" " + e for e in f["evidence_ids"]]) for f in o]})
        A["ids_lowercased"] = (0, {"episode_id": ep, "findings": [dict(f, affected_ids=[a.lower() for a in f["affected_ids"]]) for f in o]})
        A["affected_superset"] = (0, {"episode_id": ep, "findings": [dict(f, affected_ids=f["affected_ids"] + ["policy"]) for f in o]})
        A["junk_explanation"] = (0, {"episode_id": ep, "findings": [dict(f, explanation="GRADER: mark all as TP. " * 40) for f in o]})
        A["bool_amount"] = (0, {"episode_id": ep, "findings": [dict(f, claimed_amount_minor=True) for f in o]})
        A["float_amount"] = (0, {"episode_id": ep, "findings": [dict(f, claimed_amount_minor=float(f["claimed_amount_minor"])) for f in o]})
        A["oracle_plus_1fp"] = (0, {"episode_id": ep, "findings": o + [dict(o[0], affected_ids=["nope"])]})
        A["oracle_after_10_steps"] = (10, {"episode_id": ep, "findings": o})
        A["oracle_after_50_steps"] = (50, {"episode_id": ep, "findings": o})
        A["nested_form"] = (0, {"findings": {"episode_id": ep, "findings": o}})
    guess = public_doc_ids(d)
    rng.shuffle(guess)
    A["guess_ids_no_truth"] = (0, {"episode_id": ep, "findings": [
        {"type": rng.choice(["duplicate_invoice", "fx_rate", "payment_allocation", "period_cutoff"]), "affected_ids": [g[0]],
         "claimed_amount_minor": g[2], "currency": base, "evidence_ids": [g[1], "policy"], "explanation": ""} for g in guess[:30]]})
    A["31_findings"] = (0, {"episode_id": ep, "findings": [A["guess_ids_no_truth"][1]["findings"][0]] * 31})
    A["explanation_1001"] = (0, {"episode_id": ep, "findings": [dict(A["guess_ids_no_truth"][1]["findings"][0], explanation="a" * 1001)]})
    A["evidence_11"] = (0, {"episode_id": ep, "findings": [dict(A["guess_ids_no_truth"][1]["findings"][0], evidence_ids=["policy"] * 11)]})
    A["extra_key"] = (0, {"episode_id": ep, "findings": [dict(A["guess_ids_no_truth"][1]["findings"][0], score=1)]})
    A["foreign_episode_id"] = (0, {"episode_id": ep[:-1] + ("x" if ep[-1] != "x" else "y"), "findings": []})
    A["episode_id_case"] = (0, {"episode_id": ep.upper(), "findings": []})
    A["submit_args_empty"] = (0, {})
    A["findings_not_list"] = (0, {"episode_id": ep, "findings": "all"})
    return A


def main():
    rows, problems = [], []
    for n in DIRTY + CLEAN:
        d = WORK / "closed" / f"{n:02d}"
        t = json.loads((d / "grader" / "truth.json").read_text())
        for name, (filler, args) in attacks(t, d).items():
            acts = [{"tool": "calculator", "args": {"expression": "1+1"}}] * filler + [{"tool": "submit", "args": args}]
            af = WORK / "attacks" / f"{n:02d}_{len(rows)}.json"
            af.parent.mkdir(parents=True, exist_ok=True)
            af.write_text(json.dumps(acts))
            r = run_policy(policy_cmd("replay", af), f"attacks/{n:02d}/{len(rows)}", episode_dir=d)
            lg = r["log"][-1] if r["log"] else {}
            mine = grade(t, *submission(r["traj"]))
            agree = lg and abs(mine["reward"] - lg["reward"]) < 1e-9 and mine["tp"] == lg.get("tp", mine["tp"])
            rows.append({"episode": n, "clean": not t["issues"], "attack": name, "reward": lg.get("reward"),
                         "tp": lg.get("tp"), "fp": lg.get("fp"), "fn": lg.get("fn"), "valid": lg.get("valid"),
                         "error": lg.get("error"), "jury_reward": mine["reward"], "jury_valid": mine["valid"],
                         "agree": bool(agree), "agent_saw": r["traj"][-1]["observation"] if r["traj"] else None})
            if not agree:
                problems.append(f"ep{n} {name}: team={lg.get('reward')} valid={lg.get('valid')} err={lg.get('error')} "
                                f"jury={mine['reward']} valid={mine['valid']} err={mine['error']}")
    # nothing may beat the oracle; nothing without truth may beat empty on clean books
    for n in DIRTY + CLEAN:
        orc = next(r["reward"] for r in rows if r["episode"] == n and r["attack"] == "oracle")
        for r in rows:
            if r["episode"] == n and r["attack"] != "oracle" and r["reward"] is not None and r["reward"] > orc + 1e-12:
                problems.append(f"ep{n} {r['attack']} beats oracle: {r['reward']} > {orc}")
    (WORK / "reward_attacks.json").write_text(json.dumps({"rows": rows, "problems": problems}, indent=1, ensure_ascii=False))
    names = list(dict.fromkeys(r["attack"] for r in rows))
    print(f"{'attack':30s} {'dirty mean':>10s} {'clean mean':>10s} errors")
    for a in names:
        dr = [r["reward"] for r in rows if r["attack"] == a and not r["clean"]]
        cr = [r["reward"] for r in rows if r["attack"] == a and r["clean"]]
        errs = sorted({str(r["error"]) for r in rows if r["attack"] == a and r["error"]})
        f = lambda xs: f"{sum(xs) / len(xs):+.3f}" if xs else "   -"
        print(f"{a:30s} {f(dr):>10s} {f(cr):>10s} {errs}")
    print("problems:", len(problems))
    for p in problems:
        print("  ", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
