"""Contract tests: reset/step shapes, paging, cursors, errors, limits, modes, isolation."""

import pytest

from auditenv.env.env import AuditEnv
from auditenv.grader.log import GraderLog
from auditenv.policies.base import submit
from auditenv.policies.oracle import oracle_findings
from auditenv.schemas import errors as schema_errors


def make(ep, mode="train", **kw):
    env = AuditEnv(mode=mode, **kw)
    obs, info = env.reset(episode=ep)
    return env, obs, info


def lst(env, table="ledger", **kw):
    return env.step({"tool": "list_records", "args": {"table": table, **kw}})


def test_reset_shape(erroneous):
    env, obs, info = make(erroneous)
    assert set(obs) == {"task", "manifest", "policy_summary", "steps_remaining"}
    assert obs["steps_remaining"] == 100 and isinstance(info, dict)
    assert not schema_errors("observation", obs)
    assert "seed" not in str(obs) and "truth" not in str(obs)


def test_reset_by_seed_and_config_is_same_as_episode(erroneous):
    from auditenv.generator.episode import generate_episode

    ep = generate_episode(7, "dev-mixed")
    a = AuditEnv().reset(seed=7, config="dev-mixed")[0]
    b = AuditEnv().reset(episode=ep)[0]
    assert a == b


def test_step_shape_and_zero_reward(erroneous):
    env, _, _ = make(erroneous)
    obs, r, term, trunc, info = lst(env)
    assert isinstance(obs, dict) and r == 0.0 and term is False and trunc is False and info == {}
    assert set(obs) == {"result", "steps_remaining"} and obs["steps_remaining"] == 99


def test_page_limit_50(erroneous):
    env, _, _ = make(erroneous)
    assert len(lst(env)[0]["result"]["records"]) == 50
    assert lst(env, limit=51)[0]["error"] == {"code": "bad_args"}
    over = lst(env, limit=1000)[0]  # no silent truncation to 50: an error, and the step is spent
    assert over == {"error": {"code": "bad_args"}, "steps_remaining": 97}
    assert lst(env, limit=0)[0]["error"] == {"code": "bad_args"}
    assert len(lst(env, limit=7)[0]["result"]["records"]) == 7


def test_cursors_stable_and_complete(erroneous):
    env, _, _ = make(erroneous)
    rows, cur, curs = [], None, []
    while True:
        o = lst(env, **({"cursor": cur} if cur else {}))[0]
        rows += o["result"]["records"]
        cur = o["result"]["next_cursor"]
        if not cur:
            break
        curs.append(cur)
    assert [r["row_id"] for r in rows] == [r["row_id"] for r in erroneous.public().ledger]
    env2, _, _ = make(erroneous)
    o = lst(env2)[0]
    assert o["result"]["next_cursor"] == curs[0]
    assert lst(env2, cursor=curs[0])[0] ["result"] == lst(env2, cursor=curs[0])[0]["result"]


def test_cursor_from_other_episode_or_table(erroneous, episodes):
    other = episodes(3, "dev-mixed")
    e2, _, _ = make(other)
    foreign = lst(e2)[0]["result"]["next_cursor"]
    env, _, _ = make(erroneous)
    own = lst(env)[0]["result"]["next_cursor"]
    assert lst(env, cursor=foreign)[0]["error"] == {"code": "invalid_cursor"}
    assert lst(env, table="fx", cursor=own)[0]["error"] == {"code": "invalid_cursor"}
    assert lst(env, cursor="AAAA")[0]["error"] == {"code": "invalid_cursor"}
    assert lst(env, cursor=123)[0]["error"] == {"code": "invalid_cursor"}


def test_unknown_tool_and_ids_consume_steps(erroneous):
    env, _, _ = make(erroneous)
    pd = erroneous.public()
    o1 = env.step({"tool": "sql", "args": {"q": "select *"}})[0]
    o2 = env.step({"tool": "get_record", "args": {"table": "ledger", "id": "GL-NOPE"}})[0]
    o3 = env.step({"tool": "get_record", "args": {"table": "ledger", "id": pd.invoices[0]["invoice_id"]}})[0]
    o4 = env.step({"tool": "get_document", "args": {"doc_id": pd.ledger[0]["row_id"]}})[0]
    assert o1 == {"error": {"code": "unknown_tool"}, "steps_remaining": 99}
    assert o2["error"] == o3["error"] == o4["error"] == {"code": "not_found"}
    assert o4["steps_remaining"] == 96


@pytest.mark.parametrize("action", ["x", 5, None, [], {"tool": 1}, {"args": {}}, {"tool": "get_record", "args": []},
                                    {"tool": "list_records", "args": {"table": "secrets"}},
                                    {"tool": "list_records", "args": {"table": "ledger", "path": "/etc"}},
                                    {"tool": "calculator", "args": {}},
                                    {"tool": "get_record", "args": {"table": "ledger", "id": 5}}])
def test_bad_args(erroneous, action):
    env, _, _ = make(erroneous)
    obs, r, term, trunc, _ = env.step(action)
    assert obs == {"error": {"code": "bad_args"}, "steps_remaining": 99} and not term and not trunc


def test_records_retrievable_by_every_tool(erroneous):
    env, _, _ = make(erroneous)
    pd = erroneous.public()
    assert env.step({"tool": "get_record", "args": {"table": "policy", "id": "policy"}})[0]["result"]["record"] == pd.policy
    fx = pd.fx[0]
    assert env.step({"tool": "get_record", "args": {"table": "fx", "id": fx["fx_id"]}})[0]["result"]["record"] == fx
    inv = pd.invoices[0]
    assert env.step({"tool": "get_document", "args": {"doc_id": inv["doc_id"]}})[0]["result"]["document"] == inv
    assert env.step({"tool": "get_record", "args": {"table": "invoices", "id": inv["invoice_id"]}})[0]["result"]["record"] == inv


def test_100_steps_truncated(erroneous):
    env, _, _ = make(erroneous)
    for k in range(99):
        assert env.step({"tool": "calculator", "args": {"expression": "1"}})[3] is False
    obs, r, term, trunc, info = env.step({"tool": "calculator", "args": {"expression": "1"}})
    assert trunc is True and term is False and obs["steps_remaining"] == 0
    assert env.last_grade["n_findings"] == 0 and env.last_grade["inspection_steps"] == 100
    assert r == -1.0  # empty answer on erroneous books, 100 inspection steps


def test_submit_on_step_100_is_allowed(clean):
    env, _, _ = make(clean)
    for _ in range(99):
        env.step({"tool": "calculator", "args": {"expression": "1"}})
    obs, r, term, trunc, _ = env.step(submit(clean.episode_id, []))
    assert term and not trunc and r == pytest.approx(1 - 0.002 * 99)


def test_timeout_truncates(erroneous):
    t = [0.0]
    env = AuditEnv(clock=lambda: t[0], time_limit=60)
    env.reset(episode=erroneous)
    env.step({"tool": "calculator", "args": {"expression": "1"}})
    t[0] = 60.5
    obs, r, term, trunc, _ = env.step(submit(erroneous.episode_id, oracle_findings(erroneous.truth)))
    assert trunc and not term and obs["error"] == {"code": "episode_over"}
    assert env.last_grade["n_findings"] == 0  # the late answer is NOT graded


def test_step_after_end(clean):
    env, _, _ = make(clean)
    env.step(submit(clean.episode_id, []))
    g = dict(env.last_grade)
    obs, r, term, trunc, info = env.step({"tool": "list_records", "args": {"table": "ledger"}})
    assert obs["error"] == {"code": "episode_over"} and r == 0.0 and term and info == {}
    assert env.last_grade == g


def test_step_before_reset():
    obs, r, term, trunc, info = AuditEnv().step({"tool": "submit", "args": {"findings": {}}})
    assert obs["error"] == {"code": "episode_over"} and term


def test_eval_mode_hides_reward_and_info(erroneous, tmp_path):
    log = GraderLog(tmp_path / "grader_log.jsonl")
    env = AuditEnv(mode="eval", grader_log=log)
    obs, info = env.reset(episode=erroneous)
    assert info == {}
    out = [lst(env), env.step(submit(erroneous.episode_id, oracle_findings(erroneous.truth)))]
    assert all(o[1] == 0.0 and o[4] == {} for o in out)
    assert out[-1][0] == {"result": {"submitted": True}, "steps_remaining": 98}
    lines = (tmp_path / "grader_log.jsonl").read_text().splitlines()
    assert len(lines) == 1 and '"reward":' in lines[0]


def test_train_mode_returns_terminal_reward(erroneous):
    env, _, _ = make(erroneous)
    obs, r, term, trunc, info = env.step(submit(erroneous.episode_id, oracle_findings(erroneous.truth)))
    assert r == 1.0 and term and info["f1"] == 1.0


def test_two_envs_isolated(erroneous, episodes):
    a, _, _ = make(erroneous)
    b, _, _ = make(episodes(5, "dev-mixed"))
    x1 = lst(a)
    lst(b)
    lst(b, table="fx")
    x2 = lst(a, cursor=x1[0]["result"]["next_cursor"])
    solo, _, _ = make(erroneous)
    y1 = lst(solo)
    assert x1 == y1 and x2 == lst(solo, cursor=y1[0]["result"]["next_cursor"])


def test_reset_isolates_state(erroneous):
    env, first, _ = make(erroneous)
    lst(env)
    env.step(submit(erroneous.episode_id, []))
    again, _ = env.reset(episode=erroneous)
    assert again == first and env.steps_used == 0
    assert lst(env)[0]["steps_remaining"] == 99


def test_observation_is_a_copy(erroneous):
    env, _, _ = make(erroneous)
    rec = lst(env, limit=1)[0]["result"]["records"][0]
    rec["debit_minor"] = -999
    again = env.step({"tool": "get_record", "args": {"table": "ledger", "id": rec["row_id"]}})[0]["result"]["record"]
    assert again["debit_minor"] != -999


@pytest.mark.parametrize("findings", [None, "x", 1, {"episode_id": "ep-other00000", "findings": []}, {"findings": []},
                                      {"episode_id": "__EP__", "findings": [{"type": "fx_rate"}]},
                                      {"episode_id": "__EP__", "findings": [], "note": "x"}])
def test_invalid_structure_minus_one(erroneous, findings):
    if isinstance(findings, dict) and findings.get("episode_id") == "__EP__":
        findings = dict(findings, episode_id=erroneous.episode_id)
    log = GraderLog()
    env = AuditEnv(grader_log=log)
    env.reset(episode=erroneous)
    obs, r, term, trunc, _ = env.step({"tool": "submit", "args": {"findings": findings}})
    assert r == -1.0 and term and log.records[0]["valid"] is False and log.records[0]["error"]
    assert obs == {"result": {"submitted": True}, "steps_remaining": 99}  # no diagnostics leak to the agent


def test_timeout_on_clean_book_is_charged_full_budget(clean):
    # jury sim finding #5: a hung agent on a clean book must not tie with oracle (1.0)
    t = [0.0]
    env = AuditEnv(clock=lambda: t[0], time_limit=60)
    env.reset(episode=clean)
    t[0] = 60.5
    obs, r, term, trunc, _ = env.step({"tool": "calculator", "args": {"expression": "1"}})
    assert trunc and not term
    assert env.last_grade["inspection_steps"] == 100
    assert r == pytest.approx(0.8)


def test_hung_policy_is_charged_full_budget(clean):
    env, _, _ = make(clean)
    env.truncate_now()
    assert env.last_grade["inspection_steps"] == 100
    assert env.last_grade["reward"] == pytest.approx(0.8)


def test_negative_claimed_amount_is_a_false_positive_not_invalid(erroneous):
    # jury sim finding #6: a negative integer is a valid structure; it just cannot match
    env, _, _ = make(erroneous)
    good = oracle_findings(erroneous.truth)
    bad = dict(good[0], claimed_amount_minor=-abs(good[0]["claimed_amount_minor"]) - 5)
    obs, r, term, trunc, _ = env.step(submit(erroneous.episode_id, good + [bad]))
    g = env.last_grade
    assert term and g["tp"] == len(good) and g["fp"] == 1
    assert r > -1.0
