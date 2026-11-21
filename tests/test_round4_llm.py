"""A15: LLM tool definitions follow the action schema; few-shot transcripts are leak-free and replay;
the optional Gymnasium wrapper (skipped when gymnasium is not installed)."""

import importlib.util
import json

import pytest

from auditenv.env.env import AuditEnv
from auditenv.jsonschema_lite import validate
from auditenv.leakscan import scan_observation
from auditenv.paths import ROOT

pytestmark = pytest.mark.slow  # heavy round-4 check: in make check, not in make quick

LLM = ROOT / "tools" / "llm"
_spec = importlib.util.spec_from_file_location("llm_build", LLM / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def test_generated_files_up_to_date():
    for name, text in build.build().items():
        assert (LLM / name).read_text("utf-8") == text, f"run: python tools/llm/build.py ({name})"


def test_tool_definitions_cover_every_tool_in_both_formats():
    oa = json.loads((LLM / "openai_tools.json").read_text("utf-8"))
    an = json.loads((LLM / "anthropic_tools.json").read_text("utf-8"))
    names = ["list_records", "get_record", "get_document", "calculator", "submit"]
    assert [t["function"]["name"] for t in oa] == names == [t["name"] for t in an]
    for t in an:
        assert "$ref" not in json.dumps(t), "schemas must be self-contained for LLM APIs"
        assert t["input_schema"]["type"] == "object"


def test_every_fewshot_call_validates_against_its_tool_schema():
    an = {t["name"]: t["input_schema"] for t in json.loads((LLM / "anthropic_tools.json").read_text("utf-8"))}
    for name in build.FEWSHOT:
        for m in json.loads((LLM / name).read_text("utf-8"))["messages"]:
            if m["role"] == "assistant":
                validate(m["args"], an[m["tool"]])


def test_fewshot_has_no_answer_key_and_replays_to_the_same_observations():
    for name, eid in build.FEWSHOT.items():
        d = json.loads((LLM / name).read_text("utf-8"))
        ep_dir = ROOT / d["source"]
        truth = json.loads((ep_dir / "grader" / "truth.json").read_text("utf-8"))
        env = AuditEnv(mode="train")
        obs, _ = env.reset(episode_dir=str(ep_dir))
        envs = [m for m in d["messages"] if m["role"] == "env"]
        assert envs[0]["observation"] == json.loads(json.dumps(obs))
        for i, m in enumerate(envs):
            assert scan_observation(m["observation"], truth, first=(i == 0)) == [], (name, i)
        for m in d["messages"]:
            if m["role"] == "assistant":
                obs, reward, term, trunc, _ = env.step({"tool": m["tool"], "args": m["args"]})
        assert term and reward == d["reward"] > 0.9 or (truth["issues"] == [] and reward == 1.0)


def test_gym_wrapper():
    gym = pytest.importorskip("gymnasium")
    from examples.gym_wrapper import AuditGymEnv

    env = AuditGymEnv(config="dev-mixed")
    obs, info = env.reset(seed=7)
    assert env.observation_space.contains(obs) and "manifest" in json.loads(obs)
    obs, r, term, trunc, info = env.step('{"tool": "submit", "args": {"findings": []}}')
    assert term and isinstance(r, float)
    assert isinstance(env, gym.Env)
