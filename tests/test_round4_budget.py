"""A11: the minimal-budget calculation is exact - its plan, executed in the real env, costs exactly the
computed number of calls and makes every ID of the evidence set 'seen'."""

import importlib.util

from auditenv.env.data import PublicData
from auditenv.env.env import AuditEnv
from auditenv.generator.episode import generate_episode
from auditenv.paths import ROOT
import pytest

pytestmark = pytest.mark.slow  # heavy round-4 check: in make check, not in make quick

_spec = importlib.util.spec_from_file_location("min_budget", ROOT / "tools" / "min_budget.py")
mb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mb)


def test_table_cost():
    assert mb.table_cost([]) == 0
    assert mb.table_cost([1, 1, 1]) == 1          # one page beats three gets
    assert mb.table_cost([5]) == 1                # one get beats five pages
    assert mb.table_cost([1, 2, 2, 7]) == 3       # two pages + one get


def _execute(ep, steps):
    env = AuditEnv(mode="train")
    env.reset(episode=ep)
    cursors = {}
    for kind, table, x in steps:
        if kind == "page":
            args = {"table": table, "limit": 50}
            if x > 1:
                args["cursor"] = cursors[table]
            obs = env.step({"tool": "list_records", "args": args})[0]
            cursors[table] = obs["result"]["next_cursor"]
        elif table in ("invoices", "payments"):
            obs = env.step({"tool": "get_document", "args": {"doc_id": x}})[0]
        else:
            obs = env.step({"tool": "get_record", "args": {"table": table, "id": x}})[0]
        assert "error" not in obs, (kind, table, x, obs)
    return env


def test_plan_is_executable_and_costs_exactly_the_minimum():
    checked = 0
    for seed, cfg in ((9008, "interaction-heavy"), (22, "dev-mixed"), (31, "dev-global")):
        ep = generate_episode(seed, cfg)
        pos = mb.positions(PublicData(ep.files))
        for iss in ep.truth["issues"]:
            best = min(iss["evidence_sets"], key=lambda s: mb.cost(s, pos))
            steps = mb.plan(best, pos)
            assert len(steps) == mb.cost(best, pos)
            env = _execute(ep, steps)
            assert set(best) <= env._seen and env.steps_used == len(steps)
            checked += 1
    assert checked >= 5


def test_budget_far_below_limit_on_a_sample():
    r = mb.run(12)
    assert max(x["episode"] for x in r["rows"]) <= 100
