"""B9: the evidence ablation patches the matcher only temporarily and shows what evidence buys."""

import importlib.util
import sys

import auditenv.grader.core as core
import auditenv.grader.matcher as matcher
from auditenv.paths import ROOT
import pytest

pytestmark = pytest.mark.slow  # heavy round-4 check: in make check, not in make quick

sys.path.insert(0, str(ROOT / "tools"))
_spec = importlib.util.spec_from_file_location("ablation_evidence", ROOT / "tools" / "ablation_evidence.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)


def test_stripped_evidence_scores_only_without_the_requirement_and_patch_is_undone():
    orig = (matcher.satisfied_set, core.satisfied_set)
    data = ab.answers(3)
    on, off = ab.grade_all(data, False), ab.grade_all(data, True)
    assert (matcher.satisfied_set, core.satisfied_set) == orig
    name = "simple_reconcile, evidence stripped"
    assert sum(x[1] for x in on[name]) == 0
    assert sum(x[1] for x in off[name]) == sum(x[1] for x in on["simple_reconcile"])
