"""Fuzz: arbitrary JSON actions never crash the env and always produce contract-shaped output."""

from hypothesis import given, settings
from hypothesis import strategies as st

from auditenv.env.env import AuditEnv
from auditenv.schemas import errors as schema_errors

json_values = st.recursive(st.none() | st.booleans() | st.integers() | st.floats(allow_nan=True) | st.text(max_size=20),
                           lambda c: st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=8), c, max_size=4),
                           max_leaves=12)
tools = st.sampled_from(["list_records", "get_record", "get_document", "calculator", "submit", "rm", ""])
actions = st.one_of(json_values, st.fixed_dictionaries({"tool": tools, "args": json_values}),
                    st.fixed_dictionaries({"tool": tools, "args": st.dictionaries(
                        st.sampled_from(["table", "id", "doc_id", "cursor", "limit", "expression", "findings"]),
                        json_values, max_size=3)}))


@settings(max_examples=150, deadline=None)
@given(seq=st.lists(actions, min_size=1, max_size=8))
def test_fuzz_actions(erroneous, seq):
    env = AuditEnv(mode="eval")
    env.reset(episode=erroneous)
    for a in seq:
        obs, r, term, trunc, info = env.step(a)
        assert r == 0.0 and info == {}
        assert set(obs) <= {"result", "error", "steps_remaining"}
        if "error" in obs:
            assert set(obs["error"]) == {"code"}
        if not term and not trunc:
            assert not schema_errors("observation", obs)
        if term or trunc:
            break
