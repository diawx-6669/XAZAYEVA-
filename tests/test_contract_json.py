"""C15: contract.json == code constants == observed behaviour; env.spec exposes it."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from auditenv.env.env import DEFAULT_SEED, MAX_STEPS, TIME_LIMIT_S, AuditEnv
from auditenv.env.errors import CODES
from auditenv.env.tools import ALLOWED_ARGS, GET_TABLES, LIST_TABLES, PAGE_MAX
from auditenv.generator.export import parse_files
from auditenv.grader.reward import STEP_COST
from auditenv.policies.base import submit

ROOT = Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "contract.json").read_text())
I = C["interpretations"]


def test_constants_match_code():
    assert C["max_steps"] == MAX_STEPS and C["page_max"] == PAGE_MAX and C["time_limit_s"] == TIME_LIMIT_S
    assert Fraction(C["step_cost"]) == STEP_COST and C["default_seed"] == DEFAULT_SEED
    assert C["error_codes"] == list(CODES)
    for tool, spec in C["tools"].items():
        req, allowed = ALLOWED_ARGS[tool]
        assert set(spec["required"]) == req and set(spec["required"]) | set(spec["optional"]) == allowed
    assert C["tools"]["list_records"]["tables"] == list(LIST_TABLES)
    assert C["tools"]["get_record"]["tables"] == list(GET_TABLES)
    f = json.loads((ROOT / "schemas" / "findings.schema.json").read_text())["properties"]["findings"]
    assert f["maxItems"] == C["findings_limits"]["max_findings"]
    assert f["items"]["properties"]["evidence_ids"]["maxItems"] == C["findings_limits"]["max_evidence_ids"]
    assert f["items"]["properties"]["explanation"]["maxLength"] == C["findings_limits"]["max_explanation_chars"]


def test_env_spec_is_the_contract():
    assert AuditEnv().spec == C


def test_behaviour_matches_interpretations(erroneous, clean):
    env = AuditEnv()
    env.reset(episode=clean)
    for _ in range(100):
        out = env.step({"tool": "calculator", "args": {"expression": "1"}})
    assert out[3] and env.last_grade["inspection_steps"] == I["inspection_steps_on_step_limit"]
    assert out[1] == I["truncated_clean_book_reward"]
    env = AuditEnv()
    env.reset(episode=erroneous)
    env.step({"tool": "calculator", "args": {"expression": "1"}})
    env.step(submit(erroneous.episode_id, []))
    assert env.last_grade["inspection_steps"] == 1  # submit not counted
    for lim in (51, 0):
        e = AuditEnv()
        e.reset(episode=erroneous)
        assert e.step({"tool": "list_records", "args": {"table": "ledger", "limit": lim}})[0]["error"]["code"] == I[
            "limit_over_page_max"]
    e = AuditEnv()
    e.reset(episode=erroneous)
    o, r, term, *_ = e.step({"tool": "submit", "args": {}})
    assert (r, term, o["result"]) == (I["malformed_submit"]["reward"], I["malformed_submit"]["terminated"],
                                      I["malformed_submit"]["observation"]["result"])
    o, r, *_ = e.step({"tool": "calculator", "args": {"expression": "1"}})
    assert o["error"]["code"] == I["step_after_end"]["error"] and r == I["step_after_end"]["reward"]


def test_empty_csv_cell_is_null(clean):
    t = parse_files(clean.files)
    assert any(r["payment_id"] is I["csv_empty_cell"] for r in t["ledger"])
    assert b",," in clean.files["ledger.csv"] or b",\n" in clean.files["ledger.csv"]
