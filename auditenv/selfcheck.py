"""Self-check scoreboard modelled on the jury's blocks (section 10 of the case).

  Contract & isolation   25 x passed/20 fixed checks
  Data & truth           25 x correct/20 episodes (5 clean, 5 interacting, 10 mixed)
  Reward robustness      25 x passed/20 checks
  Reproducibility        15 x passed/20 paired checks (replay + permutation/renaming twin)
  + diagnostics: P, R, F1, return, steps, time for the 4 baselines and every attack.

Writes reports/selfcheck.md and reports/selfcheck.json. Exit code 1 if anything fails.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import traceback
from pathlib import Path

from .canon import dumps, files_digest
from .env.env import AuditEnv
from .generator.episode import generate_episode
from .generator.invariants import violated
from .generator.transforms import transform_episode
from .grader.core import EpisodeGrader
from .grader.log import GraderLog
from .grader.validate_truth import TYPE_OF_INVARIANT, validate
from .leakscan import scan_lines
from .paths import CONFIGS_DIR, ROOT
from .policies.attacks import ATTACKS, AttackPolicy, attack_findings
from .policies.base import finding, submit
from .policies.oracle import oracle_findings
from .runner import run_episode
from .schemas import errors as schema_errors
from .schemas import validate_public

INV_OF_TYPE = {v: k for k, v in TYPE_OF_INVARIANT.items()}


def load_split(name: str) -> list:
    spec = json.loads((CONFIGS_DIR / "splits.json").read_text("utf-8"))
    return [(e["config"], s) for e in spec[name] for s in e["seeds"]]


class Episodes:
    def __init__(self, items):
        self.items = items
        self.cache = {}

    def get(self, cfg, seed):
        k = (cfg, seed)
        if k not in self.cache:
            self.cache[k] = generate_episode(seed, cfg)
        return self.cache[k]

    def all(self):
        return [self.get(c, s) for c, s in self.items]


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def grade_direct(ep, findings, steps=0, seen=frozenset()):
    g = EpisodeGrader(ep.truth)
    return g.grade({"episode_id": ep.episode_id, "findings": findings}, steps, seen)


def first_page(env, table="ledger", **kw):
    return env.step({"tool": "list_records", "args": {"table": table, **kw}})


# =============================================================== A: contract
def contract_checks(eps: Episodes) -> list:
    erroneous = [e for e in eps.all() if e.truth["issues"]][0]
    clean = [e for e in eps.all() if not e.truth["issues"]][0]
    other = [e for e in eps.all() if e.truth["issues"]][1]

    def new_env(ep=erroneous, mode="train", **kw):
        env = AuditEnv(mode=mode, **kw)
        obs, info = env.reset(episode=ep)
        return env, obs, info

    def c_reset_shape():
        env, obs, info = new_env()
        return (set(obs) == {"task", "manifest", "policy_summary", "steps_remaining"} and obs["steps_remaining"] == 100
                and isinstance(info, dict) and not schema_errors("observation", obs))

    def c_step_shape():
        env, _, _ = new_env()
        out = first_page(env)
        return (len(out) == 5 and isinstance(out[0], dict) and isinstance(out[1], float)
                and isinstance(out[2], bool) and isinstance(out[3], bool) and isinstance(out[4], dict)
                and out[1] == 0.0 and not schema_errors("observation", out[0]))

    def c_obs_keys():
        env, _, _ = new_env()
        outs = [first_page(env)[0], env.step({"tool": "nope"})[0],
                env.step({"tool": "get_record", "args": {"table": "policy", "id": "policy"}})[0]]
        return all(not schema_errors("observation", o) for o in outs)

    def c_page_limit():
        env, _, _ = new_env()
        o = first_page(env)[0]
        o2 = first_page(env, limit=51)[0]
        o3 = first_page(env, limit=0)[0]
        return (len(o["result"]["records"]) == 50 and o2["error"]["code"] == "bad_args"
                and o3["error"]["code"] == "bad_args")

    def c_cursor_stable():
        env, _, _ = new_env()
        seen, cur, pages = [], None, 0
        while True:
            args = {"cursor": cur} if cur else {}
            o = first_page(env, **args)[0]
            seen += [r["row_id"] for r in o["result"]["records"]]
            pages += 1
            cur = o["result"]["next_cursor"]
            if cur is None:
                break
        env2, _, _ = new_env()
        a = first_page(env2)[0]["result"]["next_cursor"]
        env3, _, _ = new_env()
        b = first_page(env3)[0]["result"]["next_cursor"]
        again = first_page(env3, cursor=b)[0]["result"]["records"]
        again2 = first_page(env3, cursor=b)[0]["result"]["records"]
        pd = erroneous.public()
        return a == b and again == again2 and seen == [r["row_id"] for r in pd.ledger] and len(set(seen)) == len(seen)

    def c_cursor_foreign():
        env_o, _, _ = new_env(other)
        foreign = first_page(env_o)[0]["result"]["next_cursor"]
        env, _, _ = new_env()
        own_ledger = first_page(env)[0]["result"]["next_cursor"]
        o1 = first_page(env, cursor=foreign)[0]
        o2 = first_page(env, table="fx", cursor=own_ledger)[0]
        o3 = first_page(env, cursor="garbage!!")[0]
        return all(o.get("error", {}).get("code") == "invalid_cursor" for o in (o1, o2, o3))

    def c_unknown_tool():
        env, _, _ = new_env()
        o = env.step({"tool": "shell", "args": {"cmd": "ls"}})[0]
        return o == {"error": {"code": "unknown_tool"}, "steps_remaining": 99}

    def c_unknown_id():
        env, _, _ = new_env()
        pd = erroneous.public()
        o1 = env.step({"tool": "get_record", "args": {"table": "invoices", "id": "INV-ZZZZZZ"}})[0]
        o2 = env.step({"tool": "get_record", "args": {"table": "invoices", "id": pd.payments[0]["payment_id"]}})[0]
        o3 = env.step({"tool": "get_document", "args": {"doc_id": "nope"}})[0]
        return (o1["error"] == o2["error"] == o3["error"] == {"code": "not_found"} and o3["steps_remaining"] == 97)

    def c_bad_args():
        env, _, _ = new_env()
        outs = [env.step("not a dict")[0], env.step({"tool": "list_records", "args": {"table": "secret"}})[0],
                env.step({"tool": "get_record", "args": {"table": "ledger"}})[0],
                env.step({"tool": "list_records", "args": {"table": "ledger", "limit": True}})[0],
                env.step({"tool": "calculator", "args": {"expression": "1", "x": 1}})[0],
                env.step({"tool": "list_records", "args": {"table": "ledger"}, "extra": 1})[0]]
        return all(o.get("error", {}).get("code") == "bad_args" for o in outs) and outs[-1]["steps_remaining"] == 94

    def c_truncate_100():
        env, _, _ = new_env()
        out = None
        for _ in range(100):
            out = env.step({"tool": "calculator", "args": {"expression": "1+1"}})
        empty = grade_direct(erroneous, [], 100)
        return (out[3] is True and out[2] is False and out[0]["steps_remaining"] == 0
                and out[1] == empty["reward"] and env.last_grade["n_findings"] == 0)

    def c_submit_at_100():
        env, _, _ = new_env(clean)
        for _ in range(99):
            env.step({"tool": "calculator", "args": {"expression": "2"}})
        out = env.step(submit(clean.episode_id, []))
        return out[2] is True and out[3] is False and env.last_grade["inspection_steps"] == 99

    def c_timeout():
        clk = FakeClock()
        env = AuditEnv(mode="train", clock=clk, time_limit=60)
        env.reset(episode=erroneous)
        env.step({"tool": "calculator", "args": {"expression": "1"}})
        clk.t = 61
        out = env.step({"tool": "calculator", "args": {"expression": "1"}})
        return out[3] is True and out[0]["error"]["code"] == "episode_over" and env.last_grade["truncated"]

    def c_after_end():
        env, _, _ = new_env(clean)
        out1 = env.step(submit(clean.episode_id, []))
        g = dict(env.last_grade)
        out2 = env.step(submit(clean.episode_id, [finding("fx_rate", ["X"], 1, "KZT", [])]))
        return (out2[0]["error"]["code"] == "episode_over" and out2[1] == 0.0 and env.last_grade == g
                and out1[2] is True)

    def c_calc_attacks():
        env, _, _ = new_env()
        bad = ["__import__('os').system('id')", "lambda: 1", "9**9**9", "open('/etc/passwd')", "1" * 201,
               "1/0", "(" * 11 + "1" + ")" * 11, "a+1", "1e999", "[1]", "1 if 1 else 2", "~1", "1<2", "''"]
        return all(env.step({"tool": "calculator", "args": {"expression": e}})[0].get("error") == {"code": "calc_error"}
                   for e in bad)

    def c_calc_correct():
        env, _, _ = new_env()
        r = [env.step({"tool": "calculator", "args": {"expression": e}})[0]["result"]["value"]
             for e in ("0.1+0.2", "-(2.5*4)", "1/3", "123456789.12*1000")]
        return r == ["0.3", "-10", "0.3333333333333333333333333333333333", "123456789120"]

    def c_eval_mode():
        log = GraderLog()
        env = AuditEnv(mode="eval", grader_log=log)
        obs, info = env.reset(episode=erroneous)
        outs = [first_page(env), env.step(submit(erroneous.episode_id, oracle_findings(erroneous.truth)))]
        return (info == {} and all(o[1] == 0.0 and o[4] == {} for o in outs) and outs[-1][2] is True
                and len(log.records) == 1 and log.records[0]["reward"] > 0.9)

    def c_isolation_two_envs():
        e1, _, _ = new_env()
        e2, _, _ = new_env(other)
        a1 = first_page(e1)
        first_page(e2)
        first_page(e2)
        a2 = first_page(e1, cursor=a1[0]["result"]["next_cursor"])
        solo, _, _ = new_env()
        b1 = first_page(solo)
        b2 = first_page(solo, cursor=b1[0]["result"]["next_cursor"])
        return a1 == b1 and a2 == b2 and e2.steps_used == 2

    def c_reset_isolates():
        env, o1, _ = new_env()
        for _ in range(5):
            first_page(env)
        env.step(submit(erroneous.episode_id, []))
        o2, _ = env.reset(episode=erroneous)
        return o1 == o2 and env.steps_used == 0 and first_page(env)[0]["steps_remaining"] == 99

    def c_invalid_findings():
        bad = [None, "x", {"episode_id": erroneous.episode_id}, {"episode_id": erroneous.episode_id, "findings": "x"},
               {"episode_id": erroneous.episode_id, "findings": [{"type": "fx_rate"}]},
               {"episode_id": "ep-other00000", "findings": []},
               {"episode_id": erroneous.episode_id, "findings": [], "extra": 1}]
        actions = [{"tool": "submit", "args": {"findings": b}} for b in bad]
        actions += [{"tool": "submit"}, {"tool": "submit", "args": {}}, {"tool": "submit", "args": None}]
        ok = True
        for a in actions:
            log = GraderLog()
            env = AuditEnv(mode="train", grader_log=log)
            env.reset(episode=erroneous)
            out = env.step(a)
            ok &= bool(out[1] == -1.0 and out[2] is True and log.records[0]["valid"] is False and log.records[0]["error"]
                       and out[0] == {"result": {"submitted": True}, "steps_remaining": 99})
        flat = AuditEnv(mode="train")
        flat.reset(episode=erroneous)
        ok &= flat.step({"tool": "submit", "args": {"episode_id": erroneous.episode_id,
                                                    "findings": oracle_findings(erroneous.truth)}})[1] == 1.0
        return ok

    def c_no_leaks():
        lines = []
        truths = {}
        for ep in (erroneous, clean, other):
            truths[ep.episode_id] = ep.truth
            for pol in ("random_explorer", "simple_reconcile", "flag_all"):
                lines += run_episode(pol, episode=ep, isolate=False)["trajectory"]
        return not scan_lines(lines, truths)

    def c_readonly():
        pd = erroneous.public()
        before = files_digest(pd.files)
        env, _, _ = new_env()
        o = first_page(env)[0]
        o["result"]["records"][0]["debit_minor"] = -1  # agent-side mutation must not reach the env
        o2 = env.step({"tool": "get_record", "args": {"table": "ledger", "id": o["result"]["records"][0]["row_id"]}})[0]
        return o2["result"]["record"]["debit_minor"] != -1 and files_digest(erroneous.files) == before

    checks = [("reset() shape and first observation", c_reset_shape), ("step() 5-tuple, reward 0 while exploring", c_step_shape),
              ("observations follow observation.schema.json", c_obs_keys), ("page limit 50 enforced", c_page_limit),
              ("cursors stable, full pagination exact", c_cursor_stable),
              ("foreign/garbled cursors rejected", c_cursor_foreign), ("unknown tool -> unknown_tool, step spent", c_unknown_tool),
              ("unknown / other-table ID -> same not_found", c_unknown_id), ("malformed actions -> bad_args", c_bad_args),
              ("100 steps without submit -> truncated, empty answer", c_truncate_100),
              ("submit on step 100 allowed", c_submit_at_100), ("time limit -> truncated", c_timeout),
              ("step after end -> episode_over, result frozen", c_after_end),
              ("calculator rejects code/power/names/long/div0/deep", c_calc_attacks),
              ("calculator exact decimal arithmetic", c_calc_correct),
              ("eval mode: reward 0, info {}, result only in grader log", c_eval_mode),
              ("two env instances do not interfere", c_isolation_two_envs), ("reset() isolates episode state", c_reset_isolates),
              ("invalid findings / malformed submit -> -1, terminated, logged; flat form ok", c_invalid_findings),
              ("leakscan clean on all trajectories; records read-only", lambda: c_no_leaks() and c_readonly())]
    return run_checks(checks)


def run_checks(checks) -> list:
    out = []
    for name, fn in checks:
        try:
            ok = bool(fn())
            err = None
        except Exception:  # a crashing check is a failed check
            ok = False
            err = traceback.format_exc(limit=3)
        out.append({"name": name, "ok": ok, "error": err})
    return out


# ================================================================== B: data
def data_checks(eps: Episodes) -> list:
    out = []
    for (cfg, seed), ep in zip(eps.items, eps.all()):
        pd = ep.public()
        from .env.data import PublicData

        problems = []
        clean = violated(PublicData(ep.clean_files))
        if clean:
            problems.append(f"clean book violates {sorted(clean)}")
        problems += validate_public(pd)[:3]
        problems += [f"truth schema: {m}" for m in schema_errors("truth", ep.truth)][:3]
        after = violated(pd)
        want = {}
        for iss in ep.truth["issues"]:
            want.setdefault(INV_OF_TYPE[iss["type"]], {})[iss["affected_ids"][0]] = iss["expected_amount_minor"]
        if after != want:
            problems.append("declared discrepancies do not match invariant violations")
        v = validate(pd, ep.truth)
        if not v["ok"]:
            problems.append(f"independent solver/evidence: {({k: v[k] for k in ('missing', 'extra', 'amount_mismatch', 'evidence_problems')})}")
        if cfg == "clean-only" and ep.truth["issues"]:
            problems.append("clean config produced issues")
        out.append({"name": f"{cfg}#{seed} ({len(ep.truth['issues'])} issues)", "ok": not problems,
                    "error": "; ".join(problems) or None})
    return out


# ================================================================ C: reward
def reward_checks(eps: Episodes) -> list:
    erroneous = [e for e in eps.all() if e.truth["issues"]]
    clean = [e for e in eps.all() if not e.truth["issues"]]
    multi = [e for e in erroneous if len(e.truth["issues"]) >= 2][0]

    def att(ep, name, steps=0):
        return grade_direct(ep, attack_findings(name, ep.truth, ep.public()), steps)

    def orc(ep, steps=0):
        return grade_direct(ep, oracle_findings(ep.truth), steps)

    def c_oracle_beats_silence():
        return all(orc(e, 30)["reward"] > grade_direct(e, [], 0)["reward"] for e in erroneous)

    def c_silence_beats_accusation():
        ok = True
        for e in clean:
            pd = e.public()
            inv = pd.invoices[0]
            acc = [finding("duplicate_invoice", [inv["invoice_id"]], abs(inv["total_minor"]), pd.base, [inv["doc_id"]])]
            ok &= grade_direct(e, [], 30)["reward"] > grade_direct(e, acc, 0)["reward"]
            ok &= grade_direct(e, [], 30)["reward"] > run_episode("flag_all", episode=e, isolate=False)["grade"]["reward"]
        return ok

    def c_twins():
        return all(att(e, "twins")["reward"] < orc(e)["reward"] and att(e, "twins")["tp"] <= 1 for e in erroneous)

    def c_duplicates_no_gain():
        ok = True
        for e in erroneous:
            f = oracle_findings(e.truth)
            ok &= grade_direct(e, f + f)["reward"] < grade_direct(e, f)["reward"]
            ok &= grade_direct(e, f + f)["tp"] == len(f)
        return ok

    def c_flag_all():
        rs = [run_episode("flag_all", episode=e, isolate=False)["grade"]["reward"] for e in eps.all()]
        return max(rs) <= -0.5

    def c_all_types_all_docs():
        return all(att(e, "all_types_all_docs")["reward"] <= 0.0 for e in eps.all())

    def c_step_cost():
        e = multi
        a, b = orc(e, 10)["reward"], orc(e, 50)["reward"]
        c, d = grade_direct(clean[0], [], 10)["reward"], grade_direct(clean[0], [], 50)["reward"]  # unclipped
        return abs((a - b) - 0.08) < 1e-12 and abs((c - d) - 0.08) < 1e-12

    def c_explanation_ignored():
        return all(att(e, "junk_explanation")["reward"] == orc(e)["reward"] for e in eps.all())

    def c_persuasive():
        return all(att(e, "persuasive_wrong")["tp"] == 0 for e in eps.all())

    def c_guess_ids():
        return all(att(e, "guess_ids")["tp"] == 0 for e in eps.all())

    def c_evidence_spam():
        return all(att(e, "evidence_spam")["tp"] == 0 for e in erroneous)

    def c_wrong_currency():
        return all(att(e, "wrong_currency")["tp"] == 0 for e in erroneous)

    def c_type_brute():
        return all(att(e, "type_bruteforce")["reward"] < orc(e)["reward"] for e in erroneous)

    def c_amount_brute():
        return all(att(e, "amount_bruteforce")["reward"] < orc(e)["reward"] for e in erroneous)

    def c_invalid_minus_one():
        e = multi
        g = EpisodeGrader(e.truth)
        return all(g.grade(b, 0)["reward"] == -1.0 for b in (None, [], {"findings": []}, {"episode_id": e.episode_id,
                   "findings": [{"type": "fx_rate", "affected_ids": ["x"], "claimed_amount_minor": 1.5, "currency": "KZT",
                                 "evidence_ids": [], "explanation": ""}]}))

    def c_foreign_episode():
        e = multi
        return EpisodeGrader(e.truth).grade({"episode_id": "ep-aaaaaaaaaa", "findings": oracle_findings(e.truth)}, 0)["reward"] == -1.0

    def c_permutation():
        ok = True
        for e in erroneous:
            f = oracle_findings(e.truth) + [finding("fx_rate", ["NOPE-1"], 5, e.public().base, [])]
            ok &= grade_direct(e, f)["f1"] == grade_direct(e, list(reversed(f)))["f1"]
        return ok

    def c_resubmit():
        e = multi
        env = AuditEnv(mode="train")
        env.reset(episode=e)
        r1 = env.step(submit(e.episode_id, []))[1]
        out = env.step(submit(e.episode_id, oracle_findings(e.truth)))
        return out[1] == 0.0 and out[0]["error"]["code"] == "episode_over" and env.last_grade["reward"] == r1

    def c_truncation_empty():
        e = multi
        env = AuditEnv(mode="train")
        env.reset(episode=e)
        for _ in range(100):
            out = env.step({"tool": "get_record", "args": {"table": "policy", "id": "policy"}})
        return out[3] and out[1] == grade_direct(e, [], 100)["reward"] == -1.0

    def c_tolerance():
        e = multi
        f = oracle_findings(e.truth)
        plus1 = [dict(x, claimed_amount_minor=x["claimed_amount_minor"] + 1) for x in f]
        plus2 = [dict(x, claimed_amount_minor=x["claimed_amount_minor"] + 2) for x in f]
        return grade_direct(e, plus1)["tp"] == len(f) and grade_direct(e, plus2)["tp"] == 0

    checks = [("oracle answer beats silence on erroneous books", c_oracle_beats_silence),
              ("silence beats false accusations on clean books", c_silence_beats_accusation),
              ("twins attack (x30) gains nothing", c_twins), ("duplicated findings never add reward", c_duplicates_no_gain),
              ("flag_all scores <= -0.5 everywhere", c_flag_all), ("all types x all docs scores <= 0", c_all_types_all_docs),
              ("10 vs 50 steps differ by exactly 0.08", c_step_cost), ("explanation text has no effect", c_explanation_ignored),
              ("persuasive wrong answer gets no TP", c_persuasive), ("guessed IDs get no TP", c_guess_ids),
              ("evidence spam without a valid set gets no TP", c_evidence_spam), ("wrong currency gets no TP", c_wrong_currency),
              ("type brute force < oracle", c_type_brute), ("amount brute force < oracle", c_amount_brute),
              ("malformed findings -> -1", c_invalid_minus_one), ("foreign episode_id -> -1", c_foreign_episode),
              ("finding order does not change F1", c_permutation), ("re-submission is ignored", c_resubmit),
              ("truncation grades an empty answer", c_truncation_empty), ("tolerance: +-1 matches, +-2 does not", c_tolerance)]
    return run_checks(checks)


# ======================================================= D: reproducibility
def repro_checks(eps: Episodes) -> list:
    out = []
    for (cfg, seed), ep in zip(eps.items, eps.all()):
        problems = []
        again = generate_episode(seed, cfg)
        if files_digest(again.files) != files_digest(ep.files) or dumps(again.truth) != dumps(ep.truth):
            problems.append("regeneration not byte-identical")
        r1 = run_episode("simple_reconcile", episode=ep, isolate=False)
        r2 = run_episode("simple_reconcile", episode=again, isolate=False)
        strip = lambda t: [dumps({k: v for k, v in x.items()}) for x in t]  # noqa: E731
        if strip(r1["trajectory"]) != strip(r2["trajectory"]) or r1["grade"]["reward"] != r2["grade"]["reward"]:
            problems.append("replay differs")
        twin, mapping = transform_episode(ep, seed + 777)
        if twin.files == ep.files or not mapping:
            problems.append("transform did nothing")
        o1 = run_episode("oracle", episode=ep, isolate=False)["grade"]
        o2 = run_episode("oracle", episode=twin, isolate=False)["grade"]
        if (o1["reward"], o1["f1"]) != (o2["reward"], o2["f1"]):
            problems.append("oracle reward/F1 changed under transform")
        s2 = run_episode("simple_reconcile", episode=twin, isolate=False)["grade"]
        if (r1["grade"]["f1"], r1["grade"]["tp"]) != (s2["f1"], s2["tp"]):
            problems.append("simple_reconcile F1 changed under transform")
        if not validate(twin.public(), twin.truth)["ok"]:
            problems.append("twin truth not reproducible from twin records")
        out.append({"name": f"{cfg}#{seed} twin", "ok": not problems, "error": "; ".join(problems) or None})
    return out


# ============================================================ diagnostics
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 6) if xs else None


def _micro(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else None
    return p, r, f1


DIAG_POLICIES = ["random_explorer", "simple_reconcile", "flag_all", "oracle", "oracle_observing"]


def diagnostics(eps: Episodes, log_path=None) -> tuple:
    """(deterministic rows, timing rows, grader log head). Times never enter the deterministic part.

    Per policy: macro P/R (mean over episodes where defined: P needs >= 1 finding, R needs >= 1 issue),
    macro F1, MICRO P/R/F1 (sum TP / sum FP / sum FN over all episodes), return on all / clean /
    erroneous episodes, experimental return, steps. None = undefined ('n/a' in the report)."""
    log = GraderLog(log_path)
    rows, timing = [], []
    names = DIAG_POLICIES + [f"attack:{a}" for a in ATTACKS]
    for name in names:
        stats, times = [], []
        for ep in eps.all():
            t0 = time.monotonic()
            if name.startswith("attack:"):
                pol = AttackPolicy(name.split(":", 1)[1], ep.truth, ep.public())
                r = run_episode(name, episode=ep, mode="eval", grader_log=log, policy_obj=pol)
            else:
                r = run_episode(name, episode=ep, mode="eval", grader_log=log,
                                isolate=name not in ("oracle", "oracle_observing"))
            times.append(time.monotonic() - t0)
            g = r["grade"]
            stats.append({"clean": not ep.truth["issues"], "tp": g["tp"], "fp": g["fp"], "fn": g["fn"],
                          "P": g["precision"] if g["tp"] + g["fp"] else None,
                          "R": g["recall"] if g["tp"] + g["fn"] else None, "F1": g["f1"], "ret": g["reward"],
                          "ret_exp": g["reward_experimental"], "steps": g["steps"], "seen": r["returned_reward"] != 0})
        mp, mr, mf = _micro(sum(x["tp"] for x in stats), sum(x["fp"] for x in stats), sum(x["fn"] for x in stats))
        rows.append({"policy": name, "P": _mean(x["P"] for x in stats), "R": _mean(x["R"] for x in stats),
                     "F1": _mean(x["F1"] for x in stats),
                     "micro_P": None if mp is None else round(mp, 6), "micro_R": None if mr is None else round(mr, 6),
                     "micro_F1": None if mf is None else round(mf, 6),
                     "return": _mean(x["ret"] for x in stats),
                     "return_clean": _mean(x["ret"] for x in stats if x["clean"]),
                     "return_erroneous": _mean(x["ret"] for x in stats if not x["clean"]),
                     "return_exp": _mean(x["ret_exp"] for x in stats), "steps": _mean(x["steps"] for x in stats),
                     "agent_saw_reward": any(x["seen"] for x in stats)})
        ts = sorted(times)
        timing.append({"policy": name, "mean_ms": 1000 * statistics.mean(ts), "p50_ms": 1000 * _pct(ts, 50),
                       "p95_ms": 1000 * _pct(ts, 95), "max_ms": 1000 * ts[-1]})
    return rows, timing, log.head


def _pct(sorted_vals, q):
    """Nearest-rank percentile (no numpy)."""
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, -(-q * len(sorted_vals) // 100) - 1))
    return sorted_vals[int(k)]


def failure_analysis(eps: Episodes) -> dict:
    by_type = {}
    reasons = {}
    for ep in eps.all():
        g = run_episode("simple_reconcile", episode=ep, isolate=False)["grade"]
        tp_ids = {f["matched"] for f in g["findings"] if f["matched"]}
        for iss in ep.truth["issues"]:
            d = by_type.setdefault(iss["type"], {"total": 0, "found": 0})
            d["total"] += 1
            d["found"] += iss["issue_id"] in tp_ids
        for f in g["findings"]:
            if f["reason"]:
                reasons[f["reason"]] = reasons.get(f["reason"], 0) + 1
    return {"recall_by_type": by_type, "fp_reasons": reasons}


# ================================================================== report
WEIGHTS = {"contract": 25, "data": 25, "reward": 25, "repro": 15}
TITLES = {"contract": "Контракт и изоляция", "data": "Данные и эталон", "reward": "Надёжность награды",
          "repro": "Воспроизводимость и обобщение"}


def header() -> dict:
    """Who/what produced the report. Commit comes from the VERSION file written at build time
    (Docker images have no .git), else from git, else 'unknown'."""
    import platform
    import subprocess

    from . import GENERATOR_VERSION, __version__
    from .config import config_hash, load_config

    commit = "unknown"
    vf = ROOT / "VERSION"
    if vf.exists():
        commit = vf.read_text("utf-8").strip() or "unknown"
    else:
        try:
            commit = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, capture_output=True,
                                    text=True, timeout=5).stdout.strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            pass
    hashes = {}
    for p in sorted(CONFIGS_DIR.glob("*.json")):
        raw = json.loads(p.read_text("utf-8"))
        if isinstance(raw, dict) and "name" in raw and "version" in raw:
            hashes[p.stem] = config_hash(load_config(p))
    return {"commit": commit, "env_version": __version__, "generator_version": GENERATOR_VERSION,
            "config_hashes": hashes, "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}"}


def run(out_dir=None, quiet=False) -> dict:
    t0 = time.monotonic()
    eps = Episodes(load_split("selfcheck"))
    blocks = {"contract": contract_checks(eps), "data": data_checks(eps), "reward": reward_checks(eps),
              "repro": repro_checks(eps)}
    for v in blocks.values():  # tracebacks contain paths/line numbers: keep only the last line
        for c in v:
            if c["error"]:
                c["error"] = c["error"].strip().splitlines()[-1][:300]
    out_dir = Path(out_dir or ROOT / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "grader_log.jsonl"
    if log_path.exists():
        log_path.unlink()
    diag, timing, log_head = diagnostics(eps, log_path)
    fails = failure_analysis(eps)
    score = {k: WEIGHTS[k] * sum(c["ok"] for c in v) / len(v) for k, v in blocks.items()}
    report = {"header": header(), "blocks": blocks, "score": score, "total": sum(score.values()),
              "max_total": sum(WEIGHTS.values()), "diagnostics": diag, "failure_analysis": fails,
              "grader_log_head": log_head,
              "episodes": [f"{c}#{s}" for c, s in eps.items],
              "timing": {"note": "wall-clock, machine dependent: the ONLY non-deterministic block",
                         "elapsed_s": round(time.monotonic() - t0, 1), "per_policy": timing}}
    md = render_md(report)
    (out_dir / "selfcheck.md").write_text(md, "utf-8")
    (out_dir / "selfcheck.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                                            "utf-8")
    if not quiet:
        print(md)
    return report


TIMING_MARK = "## Замеры времени"


def render_md(rep) -> str:
    h = rep["header"]
    L = ["# AuditEnv self-check", "",
         f"commit `{h['commit']}` · env {h['env_version']} · {h['generator_version']} · Python {h['python']} · "
         f"{h['platform']}", "",
         "Хеши конфигов: " + ", ".join(f"`{k}` {v}" for k, v in h["config_hashes"].items()), "",
         f"Эпизоды: {len(rep['episodes'])} (5 clean-only, 5 interaction-heavy, 5 dev-mixed, 5 dev-global). Всё до раздела "
         f"«{TIMING_MARK[3:]}» детерминировано: повторный прогон на том же коммите даёт те же байты.", "",
         "## Табло", "", "| Блок | Пройдено | Баллы |", "|---|---|---|"]
    for k, v in rep["blocks"].items():
        L.append(f"| {TITLES[k]} | {sum(c['ok'] for c in v)}/{len(v)} | {rep['score'][k]:.1f} / {WEIGHTS[k]} |")
    L.append(f"| **Итого (без «Инженерии», 10 баллов оценивает жюри)** | | **{rep['total']:.1f} / {rep['max_total']}** |")
    for k, v in rep["blocks"].items():
        L += ["", f"### {TITLES[k]}", ""]
        for c in v:
            L.append(f"- {'PASS' if c['ok'] else 'FAIL'} — {c['name']}" + (f"  \n  `{c['error']}`" if c["error"] else ""))
    na = lambda v, f="{:.3f}": "n/a" if v is None else f.format(v)  # noqa: E731
    L += ["", "## Диагностика политик (режим eval, 20 эпизодов)", "",
          "P, R — макро (среднее по эпизодам, где величина определена); микро — ΣTP/ΣFP/ΣFN по всем эпизодам; "
          "«n/a» — не определено (нет выводов / нет ошибок). Возврат отдельно на чистых и ошибочных книгах.", "",
          "| Политика | P | R | F1 | микро P | микро R | микро F1 | Возврат | на чистых | на ошибочных | Возврат (эксп.) | Шаги | Агент видел награду |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rep["diagnostics"]:
        L.append(f"| {r['policy']} | {na(r['P'])} | {na(r['R'])} | {na(r['F1'])} | {na(r['micro_P'])} | {na(r['micro_R'])} | "
                 f"{na(r['micro_F1'])} | {na(r['return'])} | {na(r['return_clean'])} | {na(r['return_erroneous'])} | "
                 f"{na(r['return_exp'])} | {na(r['steps'], '{:.1f}')} | {'да' if r['agent_saw_reward'] else 'нет'} |")
    fa = rep["failure_analysis"]
    L += ["", "## Разбор сбоев simple_reconcile", "", "| Тип ошибки | Найдено / всего |", "|---|---|"]
    for t, d in sorted(fa["recall_by_type"].items()):
        L.append(f"| {t} | {d['found']} / {d['total']} |")
    L += ["", "Коды причин ложных выводов: " + (", ".join(f"`{k}`: {v}" for k, v in sorted(fa["fp_reasons"].items())) or "нет"), "",
          f"Журнал оценщика `reports/grader_log.jsonl`: цепочка хешей, голова `{rep.get('grader_log_head', '?')}` "
          "(проверка: `python -m auditenv verify-log`).", ""]
    tm = rep["timing"]
    L += [TIMING_MARK + " (недетерминированно, зависит от машины)", "", f"Полный self-check: {tm['elapsed_s']} c.", "",
          "| Политика | ср, мс | p50, мс | p95, мс | макс, мс |", "|---|---|---|---|---|"]
    for r in tm["per_policy"]:
        L.append(f"| {r['policy']} | {r['mean_ms']:.0f} | {r['p50_ms']:.0f} | {r['p95_ms']:.0f} | {r['max_ms']:.0f} |")
    L.append("")
    return "\n".join(L)


def deterministic_part(md: str) -> str:
    return md.split(TIMING_MARK)[0]


def main(argv=None) -> int:
    rep = run()
    failed = sum(not c["ok"] for v in rep["blocks"].values() for c in v)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
