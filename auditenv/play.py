"""`python -m auditenv play` - a person plays the auditor through the SAME environment as an agent.

Same five tools, same 100-step budget (every tool command, even a failed one, uses a step), same grader and
reward. Only two things differ from an agent run, and both are written into the trajectory header:
the wall-clock limit is 30 minutes instead of 60 s (people read slower than programs), and drafting findings
(`flag`, `draft`, `drop`, `help`) is free - it is note-taking, not an action in the environment.

After `submit` (or when the budget runs out) the grader's verdict is printed per finding: TP and the issue it
matched, or FP with the reason code (wrong_type, ids_mismatch, amount_out_of_tolerance, currency_mismatch,
evidence_incomplete, duplicate_finding, unmatched), then the issues that were missed. Nothing from the
grader is shown before the episode ends.

Used for the human baseline (docs/HUMAN_BASELINE.md) and for the jury's "play the auditor" mode.
"""

from __future__ import annotations

import json
import shlex
import sys
import time

from .env.env import AuditEnv

HUMAN_TIME_LIMIT_S = 1800.0
TABLES = ("ledger", "invoices", "payments", "fx")
TYPES = ("duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff")

HELP = """\
Команды (каждая команда среды = 1 шаг из 100; черновик выводов бесплатный):
  ls <table> [next]                 list_records; table: ledger | invoices | payments | fx; next = следующая страница
  get <table> <id>                  get_record; table: ledger | invoices | payments | fx | policy  (get policy)
  doc <doc_id>                      get_document
  calc <expression>                 calculator, например: calc (125000 - 124000) * 2
  raw <json>                        любое действие как JSON: {"tool": ..., "args": {...}}
  flag <type> <ids> <amount> <evidence> [explanation]
                                    добавить вывод в черновик (0 шагов); ids и evidence через запятую;
                                    type: duplicate_invoice | payment_allocation | fx_rate | period_cutoff
  draft | drop <n>                  показать черновик / убрать вывод n (0 шагов)
  submit                            отправить черновик (1 шаг) и увидеть разбор оценщика
  help | quit"""


def _out(stream, text=""):
    stream.write(text + "\n")
    stream.flush()


def _show_result(stream, obs):
    if "error" in obs:
        _out(stream, f"  error: {obs['error']['code']}")
        return
    res = obs.get("result")
    if isinstance(res, dict) and "records" in res:
        for rec in res["records"]:
            _out(stream, "  " + json.dumps(rec, ensure_ascii=False, sort_keys=True))
        more = "есть, наберите: ls <table> next" if res.get("next_cursor") else "нет"
        _out(stream, f"  ({len(res['records'])} записей; следующая страница: {more})")
    else:
        _out(stream, "  " + json.dumps(res, ensure_ascii=False, sort_keys=True, indent=1).replace("\n", "\n  "))


def _verdict(stream, env, reward):
    g = env.last_grade or {}
    _out(stream, "")
    _out(stream, "=== разбор оценщика ===")
    if not g.get("valid", True):
        _out(stream, f"  неверная отправка ({g.get('error')}) -> награда -1")
    for f in g.get("findings", []):
        _out(stream, f"  #{f['index']}: " + (f"TP -> {f['matched']}" if f.get("matched") else f"FP ({f.get('reason')})"))
    for iid in g.get("missed", []):
        _out(stream, f"  пропущено: {iid}")
    _out(stream, f"  TP={g.get('tp')} FP={g.get('fp')} FN={g.get('fn')}  F1={g.get('f1', 0):.3f}  "
                 f"шагов до submit={g.get('inspection_steps', '?')}  награда={reward:+.3f}")
    if g.get("truncation_reason"):
        _out(stream, f"  эпизод обрезан: {g['truncation_reason']} (ответ пустой, списан весь бюджет)")


def play(env: AuditEnv, obs: dict, lines, stream=sys.stdout, player: str = "human", trajectory=None,
         clock=time.monotonic) -> dict:
    """Run one episode from text commands. `lines` is any iterable of input lines; returns a summary."""
    episode_id = obs["manifest"]["episode_id"]
    m = obs["manifest"]
    _out(stream, f"Эпизод {episode_id}: период {m['period_start']} .. {m['period_end']} ({m['timezone']}), "
                 f"базовая валюта {m['base_currency']}, строк: {json.dumps(m['counts'], sort_keys=True)}")
    _out(stream, "Политика: " + json.dumps(obs["policy_summary"], ensure_ascii=False, sort_keys=True))
    _out(stream, HELP)
    draft: list = []
    cursors: dict = {}
    step = 0
    reward, terminated, truncated = 0.0, False, False
    t0 = clock()
    if trajectory is not None:
        trajectory.write(json.dumps({"episode_id": episode_id, "step": 0, "player": player, "observation": obs,
                                     "protocol": {"time_limit_s": env.time_limit, "drafting_is_free": True}},
                                    ensure_ascii=False, sort_keys=True) + "\n")
    remaining = obs["steps_remaining"]
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            parts = shlex.split(line)
        except ValueError:
            _out(stream, "  не разобрал кавычки")
            continue
        cmd, rest = parts[0].lower(), parts[1:]
        action = None
        if cmd in ("quit", "exit"):
            break
        if cmd == "help":
            _out(stream, HELP)
            continue
        if cmd == "draft":
            for i, f in enumerate(draft, 1):
                _out(stream, f"  {i}. " + json.dumps(f, ensure_ascii=False, sort_keys=True))
            _out(stream, f"  ({len(draft)} выводов в черновике)")
            continue
        if cmd == "drop":
            try:
                draft.pop(int(rest[0]) - 1)
                _out(stream, f"  убрал; в черновике {len(draft)}")
            except (IndexError, ValueError):
                _out(stream, "  drop <номер из draft>")
            continue
        if cmd == "flag":
            if len(rest) < 4 or rest[0] not in TYPES:
                _out(stream, "  flag <type> <ids> <amount> <evidence> [explanation]; type: " + " | ".join(TYPES))
                continue
            try:
                amount = int(rest[2].replace("_", ""))
            except ValueError:
                _out(stream, "  сумма - целое число в минимальных единицах базовой валюты")
                continue
            draft.append({"type": rest[0], "affected_ids": [s for s in rest[1].split(",") if s],
                          "claimed_amount_minor": amount, "currency": m["base_currency"],
                          "evidence_ids": [s for s in rest[3].split(",") if s],
                          "explanation": " ".join(rest[4:])[:1000]})
            _out(stream, f"  в черновике {len(draft)} (шаг не потрачен)")
            continue
        if cmd == "ls" and rest and rest[0] in TABLES:
            args = {"table": rest[0], "limit": 50}
            if rest[1:2] == ["next"]:
                if not cursors.get(rest[0]):
                    _out(stream, "  следующей страницы нет; начните с: ls " + rest[0])
                    continue
                args["cursor"] = cursors[rest[0]]
            action = {"tool": "list_records", "args": args}
        elif cmd == "get" and rest == ["policy"]:
            action = {"tool": "get_record", "args": {"table": "policy", "id": "policy"}}
        elif cmd == "get" and len(rest) == 2:
            action = {"tool": "get_record", "args": {"table": rest[0], "id": rest[1]}}
        elif cmd == "doc" and len(rest) == 1:
            action = {"tool": "get_document", "args": {"doc_id": rest[0]}}
        elif cmd == "calc" and rest:
            action = {"tool": "calculator", "args": {"expression": line.split(None, 1)[1]}}
        elif cmd == "submit":
            action = {"tool": "submit", "args": {"findings": {"episode_id": episode_id, "findings": list(draft)}}}
        elif cmd == "raw" and rest:
            try:
                action = json.loads(line.split(None, 1)[1])
            except ValueError:
                _out(stream, "  raw: нужен JSON")
                continue
        else:
            _out(stream, "  не понял команду (шаг не потрачен); help - список команд")
            continue
        obs, reward, terminated, truncated, _info = env.step(action)
        step += 1
        remaining = obs.get("steps_remaining", remaining)
        if action["tool"] == "list_records" and "result" in obs:
            cursors[action["args"]["table"]] = obs["result"].get("next_cursor")
        if trajectory is not None:
            trajectory.write(json.dumps({"episode_id": episode_id, "step": step, "player": player, "action": action,
                                         "observation": obs, "reward": reward, "terminated": terminated,
                                         "truncated": truncated}, ensure_ascii=False, sort_keys=True) + "\n")
        _show_result(stream, obs)
        _out(stream, f"  [осталось шагов: {remaining}]")
        if terminated or truncated:
            break
    if not (terminated or truncated):
        _out(stream, "Ввод закончился без submit: эпизод не отправлен (для протокола считается обрезанным).")
        env.truncate_now()
        reward, truncated = (env.last_grade or {}).get("reward", -1.0), True
    _verdict(stream, env, reward)
    g = env.last_grade or {}
    return {"episode_id": episode_id, "player": player, "steps": step, "wall_s": round(clock() - t0, 1),
            "tp": g.get("tp"), "fp": g.get("fp"), "fn": g.get("fn"), "f1": g.get("f1"), "reward": reward,
            "terminated": terminated, "truncated": truncated or bool(g.get("truncation_reason"))}


def main(a) -> int:
    env = AuditEnv(mode="train", time_limit=a.time_limit)
    if a.episode_dir:
        obs, _ = env.reset(episode_dir=a.episode_dir)
    else:
        from .config import load_config

        obs, _ = env.reset(seed=a.seed, config=load_config(a.config))
    traj = open(a.out, "a", encoding="utf-8") if a.out else None
    try:
        summary = play(env, obs, sys.stdin, player=a.player, trajectory=traj)
    finally:
        if traj:
            traj.close()
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False, sort_keys=True) + "\n")
    return 0
