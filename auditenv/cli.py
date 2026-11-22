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
            from .generator.export import grader_files

            index.append({"episode_id": ep.episode_id, "config": cfg, "seed": seed, "public_digest": files_digest(ep.files),
                          "grader_digest": files_digest(grader_files(ep))})
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
    if not a.policy and not a.policy_cmd:
        raise SystemExit("run: give --policy NAME or --policy-cmd 'python my_agent.py'")
    r = run_episode(a.policy or "external", mode=a.mode, grader_log=a.log, policy_cmd=a.policy_cmd,
                    time_limit=a.time_limit, **kw)
    if a.trajectory_out:
        Path(a.trajectory_out).write_text("".join(dumps(x) + "\n" for x in r["trajectory"]), "utf-8")
    print(json.dumps({k: r["grade"][k] for k in ("episode_id", "tp", "fp", "fn", "f1", "reward", "steps")}
                     if a.mode == "train" else {"episode_id": r["grade"]["episode_id"], "returned_reward": r["returned_reward"],
                                                "note": "eval mode: see grader log"}))


def cmd_trajectories(a):
    from .runner import run_episode

    TRAJ_PATH.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    dirs = episode_dirs()
    with TRAJ_PATH.open("w", encoding="utf-8") as fh:
        for split, d in dirs:
            for pol in AGENT_BASELINES:
                r = run_episode(pol, episode_dir=d, mode="train")
                for rec in r["trajectory"]:
                    fh.write(dumps({**rec, "split": split}) + "\n")
                    n += 1
        # termination contract on record: a policy that burns all 100 steps (truncated, max_steps) and a
        # hung policy (truncated, policy_unresponsive) - one train and one dev episode each
        for split, d in (dirs[0], dirs[-1]):
            for pol, tl in (("step_burner", 60.0), ("hung", 1.0)):
                r = run_episode(pol, episode_dir=d, mode="train", time_limit=tl)
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


def cmd_check_schemas(a):
    """Every committed JSON artefact against its published schema: trajectories (each line), grader log
    (each line), episodes/*/index.json, public files and truth.json of every committed episode."""
    from .env.data import PublicData
    from .schemas import errors, validate_public

    problems = []
    n = 0
    if TRAJ_PATH.exists():
        for k, line in enumerate(TRAJ_PATH.read_text("utf-8").splitlines()):
            n += 1
            for m in errors("trajectory", json.loads(line))[:1]:
                problems.append(f"trajectories.jsonl:{k + 1}: {m}")
    log = ROOT / "reports" / "grader_log.jsonl"
    if log.exists() and not getattr(a, "no_log", False):
        for k, line in enumerate(log.read_text("utf-8").splitlines()):
            n += 1
            for m in errors("grader_log", json.loads(line))[:1]:
                problems.append(f"grader_log.jsonl:{k + 1}: {m}")
    for split in ("train", "dev"):
        n += 1
        for m in errors("index", json.loads((EPISODES_DIR / split / "index.json").read_text("utf-8")))[:1]:
            problems.append(f"{split}/index.json: {m}")
    for _, d in episode_dirs():
        n += 1
        problems += [f"{d.name}: {m}" for m in validate_public(PublicData.from_dir(d / "public"))[:2]]
        problems += [f"{d.name}/truth: {m}" for m in errors("truth", json.loads((d / "grader" / "truth.json").read_text()))[:2]]
    print(f"check-schemas: {n} artefacts/lines validated, {len(problems)} problems")
    for p in problems[:10]:
        print(" ", p)
    return 1 if problems else 0


def cmd_lint(a):
    from .env.data import PublicData
    from .generator.episode import generate_episode
    from .lint import lint, unexplained
    from .selfcheck import load_split

    eps = []
    for _, d in episode_dirs():
        eps.append((PublicData.from_dir(d / "public"), json.loads((d / "grader" / "truth.json").read_text("utf-8"))))
    for cfg, seed in load_split("selfcheck"):
        ep = generate_episode(seed, cfg)
        eps.append((ep.public(), ep.truth))
    hits = sum(len(lint(pd)) for pd, _ in eps)
    bad = [(pd.episode_id, u) for pd, t in eps for u in [unexplained(pd, t)] if u]
    print(f"lint: {len(eps)} episodes, {hits} plausibility findings, all explained by truth" if not bad
          else f"lint: {len(bad)} episodes with UNEXPLAINED implausibilities")
    for b in bad[:10]:
        print(" ", b)
    return 1 if bad else 0


def cmd_check(a):
    """The single verification command (after pytest): scoreboard + every independent cross-check."""
    from . import selfcheck

    class T:
        trajectories = str(TRAJ_PATH)

    class V:
        seeds = getattr(a, "seeds", 500)

    class L:
        path = str(ROOT / "reports" / "grader_log.jsonl")
        head = None

    steps = [("selfcheck", lambda: selfcheck.main()), ("leakscan", lambda: cmd_leakscan(T)),
             ("replay", lambda: cmd_replay(T)), ("verify-log", lambda: cmd_verify_log(L)),
             ("verify-provenance", lambda: cmd_verify_provenance(a)), ("verify-independent", lambda: cmd_verify_independent(V)),
             ("lint", lambda: cmd_lint(a)), ("check-schemas", lambda: cmd_check_schemas(a))]
    rc = 0
    for name, fn in steps:
        r = fn() or 0
        rc |= r
    print("check: " + ("ALL GREEN" if rc == 0 else "FAILED"))
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


def cmd_serve(a):
    from .serve import serve

    return serve(a.mode, a.log)


def cmd_transform(a):
    from .generator.episode import Episode
    from .generator.export import read_public_files, write_episode
    from .generator.transforms import transform_episode

    src = Path(a.episode_dir)
    truth = json.loads((src / "grader" / "truth.json").read_text("utf-8"))
    prov = json.loads((src / "grader" / "provenance.json").read_text("utf-8"))
    ep = Episode(truth["episode_id"], read_public_files(src / "public"), truth, prov)
    twin, mapping = transform_episode(ep, a.seed, opaque=a.opaque_ids)
    out = write_episode(twin, a.out)
    (out / "grader" / "id_map.json").write_text(dumps(dict(sorted(mapping.items()))) + "\n", "utf-8")
    print(f"{ep.episode_id} -> {twin.episode_id}: {len(mapping)} IDs renamed{' (opaque)' if a.opaque_ids else ''} -> {out}")


def cmd_jury_pairs(a):
    """N paired transforms for ANY policy (docs/JURY.md): each episode is generated in the evaluator's memory
    (closed if AUDITENV_SEED_SALT is set), its twin gets shuffled rows and opaque IDs (transform --opaque-ids),
    the policy runs on both in a separate process; reward and F1 must be equal. Nothing is written to disk."""
    from .generator.episode import generate_episode
    from .generator.transforms import transform_episode
    from .runner import run_episode

    if not a.policy and not a.policy_cmd:
        raise SystemExit("jury-pairs: give --policy NAME or --policy-cmd 'python my_agent.py'")
    name = a.policy or "external"
    rows, bad = [], 0
    for k in range(a.n):
        seed = a.seed_start + k
        ep = generate_episode(seed, a.config)
        twin, _ = transform_episode(ep, a.transform_seed + k, opaque=True)
        g = [run_episode(name, episode=e, policy_cmd=a.policy_cmd, record=False)["grade"] for e in (ep, twin)]
        same = g[0]["reward"] == g[1]["reward"] and g[0]["f1"] == g[1]["f1"]
        bad += not same
        rows.append({"pair": k + 1, "seed": seed, "issues": g[0]["n_truth"], "reward": g[0]["reward"],
                     "reward_twin": g[1]["reward"], "f1": g[0]["f1"], "f1_twin": g[1]["f1"], "equal": same})
        print(f"{k + 1:2d}  {g[0]['n_truth']} issues  reward {g[0]['reward']:+.3f} / {g[1]['reward']:+.3f}  "
              f"F1 {g[0]['f1']:.3f} / {g[1]['f1']:.3f}  {'OK' if same else 'MISMATCH'}", flush=True)
    salted = bool(__import__("os").environ.get("AUDITENV_SEED_SALT"))
    print(f"jury-pairs: {a.n - bad}/{a.n} pairs equal (policy {name}, config {a.config}, "
          f"{'salted' if salted else 'UNSALTED (open)'} episodes)")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", "utf-8")
    return 1 if bad else 0


def cmd_import_csv(a):
    """A hand-made company (CSV sheets in the manual-audit layout, tests/fixtures/README.md) -> episode dir."""
    from .fixtures import load_fixture
    from .generator.export import write_episode

    ep = load_fixture(a.src)
    out = write_episode(ep, a.out)
    print(f"{ep.episode_id}: {len(ep.truth['issues'])} issues (author's answer) -> {out}")


def cmd_verify_independent(a):
    """Committed train/dev episodes + the 20 self-check episodes + N fresh seeds, all checked by
    tools/verify_independent.py in an ISOLATED interpreter (python -I): it cannot import auditenv."""
    import subprocess
    import tempfile

    from .analysis import plan, write_many
    from .selfcheck import load_split

    dirs = [str(d) for _, d in episode_dirs()]
    with tempfile.TemporaryDirectory(prefix="auditenv-indep-") as tmp:
        items = load_split("selfcheck") + plan(a.seeds, base_seed=50000)
        dirs += write_many(items, tmp)
        out = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "verify_independent.py"), *dirs],
                             capture_output=True, text=True)
    print(out.stdout.strip() + f"  [committed 20 + selfcheck 20 + {a.seeds} seeds]")
    if out.returncode and out.stderr:
        print(out.stderr.strip()[-2000:])
    return out.returncode


def cmd_verify_provenance(a):
    from .generator.episode import generate_episode
    from .selfcheck import load_split
    from .verify_provenance import verify, verify_dir

    results = [verify_dir(d) for _, d in episode_dirs()]
    for cfg, seed in load_split("selfcheck"):
        ep = generate_episode(seed, cfg)
        results.append(verify(ep.files, ep.truth, ep.provenance))
    bad = [r for r in results if not r["ok"]]
    print(f"verify-provenance: {len(results)} episodes, {sum(r['mutations'] for r in results)} mutations undone and "
          f"replayed, {len(bad)} failed")
    for r in bad[:10]:
        print(" ", r["episode_id"], r["problems"][:3])
    return 1 if bad else 0


def cmd_export_audit(a):
    from .audit_export import main as audit_main

    for r in audit_main(a.out):
        print(f"export-audit: {r['episode_id']} ({r['issues']} issues) -> {r['out']}")


def cmd_exploit_search(a):
    from .exploit_search import main as es_main

    r = es_main()
    print(json.dumps({k: r[k] for k in ("train", "dev_heldout", "best_theta", "evaluations")}, indent=1, sort_keys=True))


def cmd_experiment(a):
    from .experiment import main as ex_main

    r = ex_main(protocol=a.protocol)
    keys = ("chosen_rules", "test", "verdict", "train_evaluations") + (("unseen_configs",) if a.protocol != "E6" else ())
    print(json.dumps({k: r[k] for k in keys}, indent=1, sort_keys=True))


def cmd_lock_configs(a):
    from .config import lock_entries

    p = ROOT / "configs" / "LOCK.json"
    entries = lock_entries()
    p.write_text(json.dumps(entries, indent=1) + "\n", "utf-8")
    print(f"lock-configs: {len(entries)} configs -> {p}")


def cmd_verify_log(a):
    from .grader.log import verify_chain

    head = a.head
    if head is None:
        rep = ROOT / "reports" / "selfcheck.json"
        if Path(a.path).resolve() == (ROOT / "reports" / "grader_log.jsonl").resolve() and rep.exists():
            head = json.loads(rep.read_text("utf-8")).get("grader_log_head")
    r = verify_chain(a.path, head)
    print(f"verify-log: {r['records']} records, head {r['head'][:16]}…, "
          + ("chain OK" + (" (matches published head)" if head else "") if r["ok"] else f"BROKEN at line {r['broken_at']}"))
    return 0 if r["ok"] else 1


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


CONCEALED_CMD = "__run_concealed"
NO_CONCEAL_ENV = "AUDITENV_NO_CONCEAL"  # only for the leak test's positive control


def conceal_run_args(argv: list) -> None:
    """Re-exec `python -m auditenv run ...` so that the agent cannot read the seed, the config, data
    paths or the salt from the evaluator's process information.

    The agent runs under the same uid as a non-root evaluator, so it can read the evaluator's command
    line (`ps`, /proc/<pid>/cmdline on every OS) and, on macOS, its initial environment (`ps -E`,
    which prctl cannot hide). We hand the real arguments and the salt over an anonymous pipe and exec
    ourselves with a neutral argv and an environment without AUDITENV_SEED_SALT. Both `ps` and /proc
    show the strings captured at exec time, so restoring the salt into os.environ afterwards
    (putenv) is invisible to them. Never returns on success."""
    import os

    from .ids import SALT_ENV

    if os.name != "posix" or os.environ.get(NO_CONCEAL_ENV) == "1":
        return
    payload = json.dumps({"argv": argv, "salt": os.environ.get(SALT_ENV)}).encode("utf-8")
    if len(payload) > 16384:  # must fit the pipe buffer: we write before exec, nobody reads yet
        return
    r, w = os.pipe()
    os.write(w, payload)
    os.close(w)
    os.set_inheritable(r, True)
    env = {k: v for k, v in os.environ.items() if k != SALT_ENV}
    orig = list(getattr(sys, "orig_argv", []) or [])
    flags = orig[1:orig.index("-m")] if "-m" in orig else []
    sys.stdout.flush()
    sys.stderr.flush()
    os.execve(sys.executable, [sys.executable, *flags, "-m", "auditenv", CONCEALED_CMD, str(r)], env)


def _read_concealed(fd: str) -> list:
    import os

    from .ids import SALT_ENV

    chunks, fd = [], int(fd)
    while True:
        b = os.read(fd, 65536)
        if not b:
            break
        chunks.append(b)
    os.close(fd)
    payload = json.loads(b"".join(chunks).decode("utf-8"))
    if payload.get("salt"):
        os.environ[SALT_ENV] = payload["salt"]  # putenv after exec: not in the exec-time env block
    return payload["argv"]


def main(argv=None) -> int:
    if argv is None and sys.argv[1:2] == [CONCEALED_CMD] and len(sys.argv) == 3:
        argv = _read_concealed(sys.argv[2])
    elif argv is None and sys.argv[1:2] == ["run"]:
        conceal_run_args(sys.argv[1:])
    ap = argparse.ArgumentParser(prog="python -m auditenv")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--seed", type=int, required=True)
    g.add_argument("--config", default="dev-mixed")
    g.add_argument("--out", required=True)
    sub.add_parser("export")
    r = sub.add_parser("run")
    r.add_argument("--policy", choices=["random_explorer", "simple_reconcile", "flag_all", "oracle", "step_burner",
                                        "truth_hunter"])
    r.add_argument("--policy-cmd", help="your agent as a command speaking JSON lines (docs/ADAPTER.md)")
    r.add_argument("--time-limit", type=float, default=60.0)
    r.add_argument("--episode-dir")
    r.add_argument("--seed", type=int, default=None)
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
    sv = sub.add_parser("serve")
    sv.add_argument("--mode", default="train", choices=["train", "eval"])
    sv.add_argument("--log")
    tf = sub.add_parser("transform")
    tf.add_argument("--episode-dir", required=True)
    tf.add_argument("--out", required=True)
    tf.add_argument("--seed", type=int, required=True)
    tf.add_argument("--opaque-ids", action="store_true", help="IDs without prefixes, random length 12-64")
    jp = sub.add_parser("jury-pairs", help="N paired transforms (original vs opaque-ID twin) for any policy")
    jp.add_argument("--policy", choices=["random_explorer", "simple_reconcile", "flag_all", "oracle"])
    jp.add_argument("--policy-cmd")
    jp.add_argument("--n", type=int, default=20)
    jp.add_argument("--config", default="dev-mixed")
    jp.add_argument("--seed-start", type=int, default=880000)
    jp.add_argument("--transform-seed", type=int, default=5)
    jp.add_argument("--json", help="write the per-pair table here")
    ic = sub.add_parser("import-csv", help="hand-made company from CSV sheets -> episode dir")
    ic.add_argument("--src", required=True)
    ic.add_argument("--out", required=True)
    vi = sub.add_parser("verify-independent")
    vi.add_argument("--seeds", type=int, default=500)
    sub.add_parser("verify-provenance")
    sub.add_parser("lock-configs")
    sub.add_parser("exploit-search")
    ex = sub.add_parser("experiment")
    ex.add_argument("--protocol", default="E6", choices=["E6", "E6v2"])
    ea = sub.add_parser("export-audit")
    ea.add_argument("--out", default=str(ROOT / "audit"))
    cs = sub.add_parser("check-schemas")
    cs.add_argument("--no-log", action="store_true")
    sub.add_parser("lint")
    vl = sub.add_parser("verify-log")
    vl.add_argument("path", nargs="?", default=str(ROOT / "reports" / "grader_log.jsonl"))
    vl.add_argument("--head", help="expected chain head (e.g. from reports/selfcheck.json)")
    an = sub.add_parser("analyze")
    an.add_argument("--n", type=int, default=300)
    an.add_argument("--out")
    an.add_argument("--docs", action="store_true", help="update the generated tables in docs/")
    dc = sub.add_parser("docs-check")
    dc.add_argument("--fix", action="store_true")
    vs = sub.add_parser("verify-sbom", help="check reports/sbom.json: wheel sha256, versions, licences, base image")
    vs.add_argument("--write", action="store_true", help="regenerate reports/sbom.json first")
    vc = sub.add_parser("validate-config", help="check a config file, list every problem in plain words")
    vc.add_argument("files", nargs="*")
    vc.add_argument("--write-reference", action="store_true", help="regenerate docs/CONFIG_REFERENCE.md")
    xp = sub.add_parser("explain", help="GRADER TOOL: before/after HTML of every injected error of an OPEN episode")
    xp.add_argument("episode_dir", nargs="?")
    xp.add_argument("issue_id", nargs="?")
    xp.add_argument("--out")
    xp.add_argument("--examples", action="store_true", help="regenerate site/explain/ (3 dev episodes + index)")
    gr = sub.add_parser("grade", help="GRADER TOOL: grade a findings JSON file against an open episode, reason per finding")
    gr.add_argument("episode_dir")
    gr.add_argument("findings")
    gr.add_argument("--steps", type=int, default=0, help="inspection steps to charge (default 0)")
    gr.add_argument("--json", action="store_true")
    pl = sub.add_parser("play", help="a person plays the auditor: same tools, 100 steps, same grader (docs/HUMAN_BASELINE.md)")
    pl.add_argument("--episode-dir")
    pl.add_argument("--seed", type=int, default=1)
    pl.add_argument("--config", default="train-easy")
    pl.add_argument("--player", default="human", help="name for the human-baseline protocol")
    pl.add_argument("--time-limit", type=float, default=1800.0, help="wall-clock limit, s (agents: 60)")
    pl.add_argument("--out", help="append the trajectory (JSON lines) here")
    pl.add_argument("--summary", help="append a one-line result (TP/FP/FN/F1/reward/steps/time) here")
    a = ap.parse_args(argv)
    if a.cmd == "play":
        from .play import main as play_main

        return play_main(a)
    if a.cmd == "grade":
        from .grade_cli import main as grade_main

        return grade_main(a.episode_dir, a.findings, a.steps, a.json)
    if a.cmd == "explain":
        from .explain import main as explain_main, write_examples

        if a.examples:
            print("explain: " + ", ".join(str(p.relative_to(ROOT)) for p in write_examples(ROOT)))
            return 0
        if not a.episode_dir:
            raise SystemExit("explain: give an episode directory (or --examples)")
        return explain_main(a.episode_dir, a.issue_id, a.out)
    if a.cmd == "validate-config":
        from .config_doc import main as vc_main

        return vc_main(a.files + (["--write-reference"] if a.write_reference else []))
    if a.cmd == "verify-sbom":
        from .supply import main_verify

        return main_verify(["--write"] if a.write else [])
    if a.cmd == "docs-check":
        from .docs_check import main as docs_main

        return docs_main(["--fix"] if a.fix else [])
    fn = globals()["cmd_" + a.cmd.replace("-", "_")]
    return fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
