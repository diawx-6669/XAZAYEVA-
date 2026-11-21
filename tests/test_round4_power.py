"""A12: power analysis formulas and the bootstrap are correct and deterministic."""

import importlib.util
import sys

from auditenv.paths import ROOT
import pytest

pytestmark = pytest.mark.slow  # heavy round-4 check: in make check, not in make quick

sys.path.insert(0, str(ROOT / "tools"))
_spec = importlib.util.spec_from_file_location("power", ROOT / "tools" / "power.py")
pw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pw)


def test_sample_size_formulas():
    assert pw.n_paired(1.0, 0.1) == 785          # ((1.95996 + 0.84162) / 0.1)^2 = 784.9
    assert pw.n_unpaired(1.0, 0.1) == 1570
    assert pw.n_paired(0.0, 0.1) == 2


def test_bootstrap_power_is_deterministic_and_monotone():
    diffs = [0.0] * 15 + [2.0, -2.0, 1.0, -1.0, 0.5]
    a = pw.boot_power(diffs, 0.2, reps=60, inner=60)
    assert a == pw.boot_power(diffs, 0.2, reps=60, inner=60)
    assert pw.boot_power(diffs, 1.0, reps=60, inner=60) >= a >= pw.boot_power(diffs, 0.0, reps=60, inner=60)


def test_collect_is_paired_on_the_same_episodes():
    rw = pw.collect(4)
    assert {len(v) for v in rw.values()} == {4}
    assert all(x == 1.0 for x in rw["oracle"])
