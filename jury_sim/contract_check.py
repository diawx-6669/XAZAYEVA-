"""Item 6: what the jury checks in section 10 - reset/step contract, limits, bad input, timeout, leaks.
Drives `python -m auditenv serve` (JSON lines) and `python -m auditenv run` as external programs."""
import json
import subprocess
import sys
import time

from common import JURY, PY, ROOT, WORK, env, policy_cmd, read_jsonl, run_policy, salt

CHECKS = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


class Serve:
    def __init__(self, mode="train"):
        self.p = subprocess.Popen([PY, "-m", "auditenv", "serve", "--mode", mode], cwd=ROOT, env=env(),
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def send(self, obj, raw=None):
        self.p.stdin.write((raw if raw is not None else json.dumps(obj)) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def reset(self, n=5, **kw):
        kw = kw or {"episode_dir": str(WORK / "closed" / f"{n:02d}")}
        return self.send({"cmd": "reset", **kw})

    def step(self, tool, **args):
        return self.send({"cmd": "step", "action": {"tool": tool, "args": args}})

    def close(self):
        try:
            self.send({"cmd": "close"})
        except Exception:  # noqa
            pass
        self.p.kill()


def err(r):
    return (r.get("observation") or {}).get("error", {}).get("code")


@check("reset: (observation, info); keys task/manifest/policy_summary/steps_remaining=100")
def c_reset(s):
    r = s.reset()
    o = r["observation"]
    return set(o) == {"task", "manifest", "policy_summary", "steps_remaining"} and o["steps_remaining"] == 100 \
        and "info" in r, sorted(o)


@check("step: 5-tuple, obs only {result|error, steps_remaining}, reward 0 during play")
def c_step(s):
    s.reset()
    r = s.step("list_records", table="ledger")
    o = r["observation"]
    ok = set(r) >= {"observation", "reward", "terminated", "truncated", "info"} and set(o) == {"result", "steps_remaining"} \
        and r["reward"] == 0 and o["steps_remaining"] == 99
    r2 = s.step("get_record", table="ledger", id="nope")
    ok &= set(r2["observation"]) == {"error", "steps_remaining"} and r2["observation"]["error"] == {"code": "not_found"}
    return ok, [sorted(o), r2["observation"]]


@check("list_records: page <= 50; limit 51 / 0 / '50' -> bad_args")
def c_limit(s):
    s.reset()
    a = s.step("list_records", table="ledger", limit=50)
    b = s.step("list_records", table="ledger", limit=51)
    c = s.step("list_records", table="ledger", limit=0)
    d = s.step("list_records", table="ledger", limit="50")
    e = s.step("list_records", table="ledger")
    n = len(a["observation"]["result"]["records"])
    return n == 50 and err(b) == err(c) == err(d) == "bad_args" and len(e["observation"]["result"]["records"]) <= 50, \
        [n, err(b), err(c), err(d), len(e["observation"]["result"]["records"])]


@check("cursors: stable, full walk = manifest counts, no repeats, for all 4 tables")
def c_cursor(s):
    o = s.reset()["observation"]
    out, ok = {}, True
    for t in ("ledger", "invoices", "payments", "fx"):
        ids, cur, curs = [], None, []
        while True:
            args = {"table": t, "limit": 37}
            if cur:
                args["cursor"] = cur
            r = s.step("list_records", **args)["observation"]["result"]
            ids += [x.get("row_id") or x.get("doc_id") or f"fx:{x['date']}:{x['source_currency']}:{x['target_currency']}"
                    for x in r["records"]]
            cur = r["next_cursor"]
            if not cur:
                break
            curs.append(cur)
        again = s.step("list_records", table=t, limit=37, cursor=curs[0])["observation"]["result"] if curs else None
        first2 = s.step("list_records", table=t, limit=37, cursor=curs[0])["observation"]["result"] if curs else None
        ok &= len(ids) == len(set(ids)) == o["manifest"]["counts"][t] and again == first2
        out[t] = (len(ids), o["manifest"]["counts"][t])
    return ok, out


@check("cursor: garbage / other table / other limit tampering -> invalid_cursor")
def c_cursor_bad(s):
    s.reset()
    cur = s.step("list_records", table="ledger", limit=10)["observation"]["result"]["next_cursor"]
    a = s.step("list_records", table="invoices", cursor=cur)
    b = s.step("list_records", table="ledger", cursor="AAAA")
    c = s.step("list_records", table="ledger", cursor=cur[:-1] + ("A" if cur[-1] != "A" else "B"))
    return err(a) == err(b) == err(c) == "invalid_cursor", [err(a), err(b), err(c), cur]


@check("cursor from another episode (other seed) -> invalid_cursor")
def c_cursor_other(s):
    s.reset(n=5)
    cur = s.step("list_records", table="ledger", limit=10)["observation"]["result"]["next_cursor"]
    s.reset(n=6)
    a = s.step("list_records", table="ledger", cursor=cur)
    return err(a) == "invalid_cursor", err(a)


@check("cursor from a SAME-seed episode of another config (same episode_id!) -> invalid_cursor")
def c_cursor_same_id(s):
    d1 = WORK / "probe_sameid" / "a"
    d2 = WORK / "probe_sameid" / "b"
    for d, cfg in ((d1, "jury-skew"), (d2, "jury-cutoff")):
        subprocess.run([PY, "-m", "auditenv", "generate", "--seed", "990001", "--config", str(JURY / "configs" / f"{cfg}.json"),
                        "--out", str(d)], cwd=ROOT, env=env(), capture_output=True, check=True)
    e1 = s.reset(episode_dir=str(d1))["observation"]["manifest"]["episode_id"]
    cur = s.step("list_records", table="ledger", limit=10)["observation"]["result"]["next_cursor"]
    e2 = s.reset(episode_dir=str(d2))["observation"]["manifest"]["episode_id"]
    a = s.step("list_records", table="ledger", cursor=cur)
    return err(a) == "invalid_cursor", {"episode_ids": [e1, e2], "code": err(a) or "ACCEPTED"}


@check("unknown tool / unknown id / id of other table / doc_id of ledger row -> code only, step spent")
def c_unknown(s):
    s.reset()
    led = s.step("list_records", table="ledger", limit=1)["observation"]["result"]["records"][0]["row_id"]
    inv = s.step("list_records", table="invoices", limit=1)["observation"]["result"]["records"][0]["doc_id"]
    a = s.step("rm_rf")
    b = s.step("get_record", table="ledger", id="LR-NOPE")
    c = s.step("get_record", table="ledger", id=inv)
    d = s.step("get_document", doc_id=led)
    e = s.step("get_record", table="truth", id="x")
    f = s.step("list_records", table="../grader/truth")
    steps = [x["observation"]["steps_remaining"] for x in (a, b, c, d, e, f)]
    ok = err(a) == "unknown_tool" and err(b) == err(c) == err(d) == "not_found" and err(e) == err(f) == "bad_args" \
        and steps == [97, 96, 95, 94, 93, 92]
    return ok, [err(x) for x in (a, b, c, d, e, f)] + [steps]


@check("bad args shapes (args not object, extra arg, missing arg) -> bad_args, no crash")
def c_badargs(s):
    s.reset()
    a = s.send({"cmd": "step", "action": {"tool": "get_document", "args": "x"}})
    b = s.step("get_document", doc_id="x", extra=1)
    c = s.step("get_record", table="ledger")
    d = s.send({"cmd": "step", "action": {"tool": "list_records"}})
    e = s.send({"cmd": "step", "action": ["list_records"]})
    codes = [err(x) for x in (a, b, c, d, e)]
    return all(x in ("bad_args", "unknown_tool") for x in codes), codes


@check("calculator: arithmetic ok; __import__, lambda, names, **, 9**9**9, 1/0, >200 chars, >10 nesting -> calc_error")
def c_calc(s):
    s.reset()
    ok_r = s.step("calculator", expression="(0.1 + 0.2) * -3 / 4")
    bad = ["__import__('os').system('id')", "(lambda: 1)()", "x+1", "2**3", "9**9**9", "1/0", "1+" * 101 + "1",
           "(" * 11 + "1" + ")" * 11, "open('/etc/passwd')", "().__class__", "1e999999999", "[1,2]", "'a'*9"]
    codes = [err(s.step("calculator", expression=b)) for b in bad]
    deep10 = s.step("calculator", expression="(" * 10 + "1" + ")" * 10)
    return codes == ["calc_error"] * len(bad) and "result" in ok_r["observation"], \
        {"ok": ok_r["observation"].get("result"), "codes": dict(zip(bad, codes)), "depth10": deep10["observation"]}


@check("100 steps without submit -> truncated at step 100; empty answer graded (train reward)")
def c_100(s):
    s.reset(n=0)
    for k in range(99):
        r = s.step("calculator", expression="1+1")
        if r["terminated"] or r["truncated"]:
            return False, f"ended early at {k + 1}"
    r = s.step("calculator", expression="1+1")
    after = s.step("calculator", expression="1+1")
    return r["truncated"] and not r["terminated"] and abs(r["reward"] - 0.8) < 1e-9 and err(after) == "episode_over", \
        {"reward_clean_truncated": r["reward"], "after": after["observation"]}


@check("submit on step 100 is accepted (terminated, not truncated)")
def c_submit100(s):
    o = s.reset(n=0)["observation"]
    for _ in range(99):
        s.step("calculator", expression="1")
    r = s.step("submit", episode_id=o["manifest"]["episode_id"], findings=[])
    return r["terminated"] and not r["truncated"] and abs(r["reward"] - (1 - 0.002 * 99)) < 1e-9, r["reward"]


@check("step after submit -> episode_over, result unchanged (resubmission ignored)")
def c_after(s):
    o = s.reset(n=0)["observation"]
    ep = o["manifest"]["episode_id"]
    r1 = s.step("submit", episode_id=ep, findings=[])
    r2 = s.step("submit", episode_id=ep, findings=[{"type": "fx_rate", "affected_ids": ["x"], "claimed_amount_minor": 1,
                                                     "currency": "X", "evidence_ids": [], "explanation": ""}])
    return err(r2) == "episode_over" and r2["reward"] == 0 and r1["reward"] == 1.0, [r1["reward"], r2["observation"]]


@check("invalid submit structure -> terminated, -1, agent sees only {submitted: true}")
def c_badsubmit(s):
    s.reset(n=0)
    r = s.step("submit", findings="nope")
    return r["terminated"] and r["reward"] == -1 and r["observation"]["result"] == {"submitted": True}, r["observation"]


@check("eval mode (serve): reward 0, info {} on every step incl. terminal")
def c_eval(_):
    s = Serve("eval")
    try:
        o = s.reset(n=5)
        rs = [s.step("list_records", table="ledger"), s.step("submit", episode_id=o["observation"]["manifest"]["episode_id"],
                                                             findings=[])]
        return o["info"] == {} and all(r["reward"] == 0 and r["info"] == {} for r in rs), [r["info"] for r in rs]
    finally:
        s.close()


@check("eval mode (run): child gets reward 0, grader log holds the result")
def c_eval_run(_):
    r = run_policy(policy_cmd("oracle", WORK / "closed" / "05" / "grader" / "truth.json"), "contract/eval",
                   episode_dir=WORK / "closed" / "05", mode="eval")
    return all(t.get("reward") == 0 for t in r["traj"]) and r["log"][-1]["reward"] == 1.0, \
        [t.get("reward") for t in r["traj"]] + [r["log"][-1]["reward"]]


@check("timeout: silent agent -> truncated, policy_unresponsive, empty answer graded")
def c_timeout(_):
    sl = WORK / "sleeper.py"
    sl.write_text("import sys,time\nsys.stdin.readline()\ntime.sleep(30)\n")
    t0 = time.monotonic()
    r = run_policy(f"{PY} {sl}", "contract/timeout", episode_dir=WORK / "closed" / "00", time_limit=3)
    dt = time.monotonic() - t0
    lg = r["log"][-1] if r["log"] else {}
    return lg.get("truncated") and lg.get("truncation_reason") == "policy_unresponsive" and dt < 15, \
        {"wall": round(dt, 1), "log": {k: lg.get(k) for k in ("truncated", "truncation_reason", "reward", "inspection_steps")}}


@check("non-JSON line from agent -> unknown_tool, step spent, run continues")
def c_nonjson(_):
    bad = WORK / "nonjson.py"
    bad.write_text("import sys,json\nsys.stdin.readline()\nprint('hello', flush=True)\nm=json.loads(sys.stdin.readline())\n"
                   "sys.stderr.write(json.dumps(m))\nprint(json.dumps({'action':{'tool':'submit','args':{}}}),flush=True)\n"
                   "sys.stdin.readline()\n")
    r = run_policy(f"{PY} {bad}", "contract/nonjson", episode_dir=WORK / "closed" / "00")
    o = r["traj"][1]["observation"] if len(r["traj"]) > 1 else {}
    return o.get("error", {}).get("code") == "unknown_tool" and o.get("steps_remaining") == 99, o


@check("reset isolates: same episode after a dirty episode gives identical first observation and pages")
def c_iso(s):
    a = s.reset(n=5)
    p1 = s.step("list_records", table="payments")
    s.reset(n=6)
    s.step("list_records", table="ledger")
    b = s.reset(n=5)
    p2 = s.step("list_records", table="payments")
    return a == b and p1 == p2, None


@check("errors carry only a code; no observation mentions grader/truth/provenance/ISS-/seed/salt/paths")
def c_leaks(_):
    bad = ["truth", "provenance", "grader", "ISS-", "issue_id", str(ROOT), "/Users/", salt(), "910001", "920001", "Traceback",
           "expected_amount", "evidence_sets"]
    hits, n_obs, codes = {}, 0, set()
    for f in (WORK / "runs").rglob("traj.jsonl"):
        if "attack" in str(f) or "contract" in str(f):
            continue
        for t in read_jsonl(f):
            o = t.get("observation") or {}
            n_obs += 1
            if "error" in o:
                codes.add(json.dumps(o["error"], sort_keys=True))
            blob = json.dumps(o, ensure_ascii=False)
            for b in bad:
                if b in blob:
                    hits[b] = hits.get(b, 0) + 1
    only_codes = all(set(json.loads(c)) == {"code"} for c in codes)
    return not hits and only_codes, {"observations": n_obs, "hits": hits, "error_shapes": sorted(codes)}


def main():
    res = []
    for name, fn in CHECKS:
        s = Serve()
        try:
            ok, detail = fn(s)
        except Exception as e:  # noqa
            ok, detail = False, f"EXC {type(e).__name__}: {e}"
        finally:
            s.close()
        res.append({"check": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            print("     ", json.dumps(detail, ensure_ascii=False)[:600])
    (WORK / "contract_check.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    print(f"passed {sum(r['ok'] for r in res)}/{len(res)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
