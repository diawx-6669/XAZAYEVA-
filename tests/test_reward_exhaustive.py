"""A20: exhaustive small-case enumeration of the real grader (level 'small' here; `make exhaustive` = 'full')."""

import importlib.util
import os

from auditenv.paths import ROOT
import pytest

pytestmark = pytest.mark.slow  # heavy round-4 check: in make check, not in make quick

_spec = importlib.util.spec_from_file_location("reward_exhaustive", ROOT / "tools" / "reward_exhaustive.py")
rx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rx)


def test_reward_exhaustive_small():
    st = rx.run(os.environ.get("AUDITENV_EXHAUSTIVE", "small"))
    assert st["violations"] == [], st["violations"][:5]
    assert st["submissions"] > 1000 and st["edges"] and st["orders"] and st["step_checks"]


def test_universe_contains_near_misses_that_must_not_match():
    from auditenv.grader.core import EpisodeGrader

    iss = {**rx.POOL[0], "issue_id": "ISS-001", "currency": "KZT"}
    g = EpisodeGrader({"episode_id": "ep-x", "issues": [iss], "tolerance_minor": 1})
    tp = {label: g.grade({"episode_id": "ep-x", "findings": [f]}, 0)["tp"] for label, f in rx.universe([rx.POOL[0]])}
    assert tp == {"I0:correct": 1, "I0:amount+1": 1, "I0:amount+2": 0, "I0:wrong_type": 0, "I0:wrong_currency": 0,
                  "I0:evidence_missing_one": 0, "guess": 0}


def test_positive_control_a_grader_that_ignores_false_positives_is_caught(monkeypatch):
    import auditenv.grader.core as core

    real = core.prf
    monkeypatch.setattr(core, "prf", lambda tp, fp, fn: real(tp, 0, fn))
    st = rx.run("tiny")
    assert {v[0] for v in st["violations"]} >= {"dominates_honest"}
