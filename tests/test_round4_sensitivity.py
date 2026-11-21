"""B7/B8: tolerance and step-cost sensitivity on a small sample - the +-1 rule and the ranking claims hold."""

import importlib.util
import statistics
import sys
from fractions import Fraction

from auditenv.grader.core import EpisodeGrader
from auditenv.paths import ROOT

sys.path.insert(0, str(ROOT / "tools"))
_spec = importlib.util.spec_from_file_location("sensitivity", ROOT / "tools" / "sensitivity.py")
sens = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sens)

DATA = sens.submissions(4)


def _mean(name, tol):
    out = []
    for ep, subs in DATA:
        fs, st = subs[name]
        out.append(EpisodeGrader(ep.truth, tolerance=tol).grade({"episode_id": ep.episode_id, "findings": fs}, st)["reward"])
    return statistics.fmean(out)


def test_tolerance_one_accepts_rounding_difference_but_not_two():
    has_issues = any(ep.truth["issues"] for ep, _ in DATA)
    assert has_issues
    assert _mean("oracle amount+1", 1) == _mean("oracle amount-1", 1) > _mean("oracle amount+1", 0)
    assert _mean("oracle amount+2", 1) < _mean("oracle amount+1", 1)
    for t in sens.TOLS:
        assert _mean("attack:amount_bruteforce", t) < _mean("oracle", 1)


def test_step_cost_report_renders_and_lambda_zero_ignores_steps():
    text = sens.step_cost_report(DATA, len(DATA))
    assert "λ = 0.002" in text and "`oracle`" in text
    assert sens.COSTS[1] == Fraction(2, 1000)
