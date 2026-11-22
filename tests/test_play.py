"""`python -m auditenv play`: a person goes through the same env, budget and grader as an agent."""

import io
import json

from auditenv.env.env import AuditEnv
from auditenv.paths import ROOT
from auditenv.play import play

DEV = sorted(p for p in (ROOT / "episodes" / "dev").iterdir() if (p / "grader" / "truth.json").exists())


def _run(ep, lines, max_steps=100):
    env = AuditEnv(mode="train", time_limit=1800.0, max_steps=max_steps)
    obs, _ = env.reset(episode_dir=ep)
    out, traj = io.StringIO(), io.StringIO()
    summary = play(env, obs, lines, stream=out, trajectory=traj)
    return summary, out.getvalue(), [json.loads(x) for x in traj.getvalue().splitlines()]


def _truth(ep):
    return json.loads((ep / "grader" / "truth.json").read_text("utf-8"))


def _flags(ep):
    t = _truth(ep)
    return [f"flag {i['type']} {','.join(i['affected_ids'])} {i['expected_amount_minor']} {','.join(i['evidence_sets'][0])}"
            for i in t["issues"]]


def test_correct_answers_typed_by_hand_score_like_the_oracle():
    ep = next(p for p in DEV if _truth(p)["issues"])
    summary, out, traj = _run(ep, _flags(ep) + ["draft", "submit"])
    n = len(_truth(ep)["issues"])
    assert (summary["tp"], summary["fp"], summary["fn"]) == (n, 0, 0)
    assert summary["reward"] == 1.0 and summary["steps"] == 1  # flag/draft are free, submit is the only step
    assert traj[0]["protocol"] == {"time_limit_s": 1800.0, "drafting_is_free": True}
    assert traj[-1]["terminated"] is True


def test_every_tool_command_costs_a_step_and_free_commands_do_not():
    ep = DEV[0]
    lines = ["help", "draft", "nonsense", "get policy", "ls ledger", "ls ledger next", "calc 1/0", "get ledger NOPE",
             "submit"]
    summary, out, traj = _run(ep, lines)
    assert summary["steps"] == 6  # get, ls, ls next, calc (error), get (error), submit
    assert [t["action"]["tool"] for t in traj[1:]] == ["get_record", "list_records", "list_records", "calculator",
                                                      "get_record", "submit"]
    assert traj[3]["action"]["args"]["cursor"] == traj[2]["observation"]["result"]["next_cursor"]
    assert "calc_error" in out and "not_found" in out


def test_nothing_from_the_grader_is_shown_before_the_episode_ends():
    for ep in DEV:
        t = _truth(ep)
        _, out, traj = _run(ep, ["get policy", "ls invoices", "ls payments", "submit"])
        before = out.split("=== разбор оценщика ===")[0]
        for issue in t["issues"]:
            assert issue["issue_id"] not in before
        assert "grader" not in before and str(ep) not in out
        for row in traj:
            assert "issue_id" not in json.dumps(row["observation"])


def test_budget_runs_out_like_for_an_agent():
    ep = next(e for e in DEV if json.loads((e / "grader" / "truth.json").read_text("utf-8"))["issues"])
    summary, out, traj = _run(ep, ["get policy"] * 150)
    assert summary["steps"] == 100 and summary["truncated"] is True
    assert summary["reward"] == -1.0  # empty answer, full budget charged
    assert traj[-1]["truncated"] is True


def test_end_of_input_without_submit_counts_as_truncated():
    summary, out, _ = _run(DEV[0], ["get policy"])
    assert summary["truncated"] is True and "без submit" in out
