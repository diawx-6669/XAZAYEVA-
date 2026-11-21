"""A16: the stdlib Rasch fit recovers known parameters and is identified (mean b = 0)."""

import importlib.util
import math
import sys

from auditenv.paths import ROOT

sys.path.insert(0, str(ROOT / "tools"))
_spec = importlib.util.spec_from_file_location("rasch", ROOT / "tools" / "rasch.py")
rasch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rasch)


def test_fit_recovers_known_difficulties_from_expected_counts():
    persons = list(rasch.PANEL)[:6]
    theta = dict(zip(persons, [-1.5, -0.5, 0.0, 0.5, 1.0, 2.0]))
    b_true = {"easy": -1.0, "mid": 0.0, "hard": 1.0}
    n = 10000
    counts = {(p, i): [round(n / (1 + math.exp(-(theta[p] - b)))), n] for p in persons for i, b in b_true.items()}
    th, b, se = rasch.fit(counts)
    assert abs(sum(b.values())) < 1e-9
    for i, v in b_true.items():
        assert abs(b[i] - v) < 0.05 and se[i] < 0.05, (i, b[i])
    assert th[persons[-1]] > th[persons[0]]


def test_extreme_items_stay_finite():
    counts = {("full (all rules)", "all"): [10, 10], ("full (all rules)", "none"): [0, 10],
              ("official baseline", "all"): [10, 10], ("official baseline", "none"): [0, 10]}
    th, b, se = rasch.fit(counts)
    assert all(math.isfinite(x) for x in list(b.values()) + list(th.values()))
    assert b["none"] > b["all"]
