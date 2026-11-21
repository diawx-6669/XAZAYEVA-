"""B10: the committed reward table equals the grader's formula, recomputed independently here."""

import importlib.util

from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("reward_table", ROOT / "tools" / "reward_table.py")
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)


def independent(tp, fp, fn, steps):
    if tp + fn == 0:
        f1 = 1.0 if fp == 0 else 0.0
    else:
        f1 = 2 * tp / (2 * tp + fp + fn)
    return max(-1.0, min(1.0, 2 * f1 - 1 - 0.002 * steps))


def test_table_matches_independent_formula_and_file():
    n = 0
    for _, tp, fp, fn, f1, rs in rt.rows():
        for s, r in zip(rt.STEPS, rs):
            assert abs(r - independent(tp, fp, fn, s)) < 1e-12, (tp, fp, fn, s)
            n += 1
    assert n > 200
    assert (ROOT / "reports" / "reward_table.md").read_text("utf-8") == rt.render()
