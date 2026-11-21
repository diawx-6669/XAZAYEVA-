"""A5: THIRD_PARTY_NOTICES.md is generated from requirements.txt and the wheel METADATA."""

from auditenv.supply import NOTICES_PATH, render_notices, requirements, wheels


def test_third_party_notices_up_to_date():
    assert NOTICES_PATH.read_text("utf-8") == render_notices(), "run: python tools/third_party.py"


def test_every_pin_has_exactly_one_wheel_with_a_known_licence():
    ws = wheels()
    reqs = requirements()
    assert len(ws) == len(reqs)
    for w in ws:
        assert w["license"] and w["license"] != "UNKNOWN", w["file"]
        assert w["file"].endswith("-none-any.whl"), "only pure-Python wheels"
