"""Shortcut probe (tools/shortcut_probe.py): format-only features of the records must not give the errors away.

The positive control proves the probe can see a planted tell; the real AUC must stay far from it. The one
weak tell the probe found (00 seconds on the partial_fx_cutoff receipt) was fixed in v1.1; the test below
keeps it fixed."""

import importlib.util
import json

import pytest

from auditenv.paths import ROOT

pytestmark = pytest.mark.slow

_spec = importlib.util.spec_from_file_location("shortcut_probe", ROOT / "tools" / "shortcut_probe.py")
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)


@pytest.fixture(scope="module")
def small():
    return sp.run(n_train=6, n_test=6)


def test_positive_control_is_caught(small):
    assert small["positive_control"]["auc"] > 0.9


def test_no_strong_shortcut_in_real_episodes(small):
    assert small["real"]["auc"] < 0.7


def test_seconds_tell_is_fixed(small):
    """Before v1.1: 36.5% of payment_allocation receipts had 00 seconds vs 8.0% of clean ones."""
    kt = sp.known_tell(small)
    assert kt["payment_allocation_seconds_zero"] is None or kt["payment_allocation_seconds_zero"] <= 0.10
    assert kt["clean_payment_seconds_zero"] <= 0.10


def test_auc_is_the_mann_whitney_statistic():
    assert sp.auc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0
    assert sp.auc([4, 3, 2, 1], [0, 0, 1, 1]) == 0.0
    assert sp.auc([1, 1, 1, 1], [0, 1, 0, 1]) == 0.5


def test_committed_report_matches_its_json():
    r = json.loads((ROOT / "reports" / "shortcut_probe.json").read_text("utf-8"))
    md = (ROOT / "reports" / "shortcut_probe.md").read_text("utf-8")
    assert md == sp.render(r)
    assert r["positive_control"]["auc"] > 0.9 and r["real"]["auc"] < 0.7
