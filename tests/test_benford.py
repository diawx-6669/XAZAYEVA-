"""Benford check (tools/benford.py): the math, and the committed report stays in sync with its JSON."""

import importlib.util
import json
import math

from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("benford", ROOT / "tools" / "benford.py")
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)


def test_benford_shares_and_mad():
    assert abs(sum(bf.BENFORD) - 1) < 1e-12 and abs(bf.BENFORD[0] - math.log10(2)) < 1e-12
    assert bf.mad(bf.BENFORD) == 0
    assert [bf.first_digit(x) for x in (7, 70, 123456, -905, 0)] == [7, 7, 1, 9, None]
    assert bf.band(0.005) == "close" and bf.band(0.02) == "nonconformity"


def test_errors_do_not_move_the_digits_on_a_small_run():
    r = bf.run(8)  # few affected rows on a small run: the bound is loose, the committed report is the real check
    assert r["affected_vs_clean_mad"] < 0.04
    assert r["groups"]["ledger amounts (base)"]["n"] > 1000


def test_committed_report_matches_its_json():
    r = json.loads((ROOT / "reports" / "benford.json").read_text("utf-8"))
    assert (ROOT / "reports" / "benford.md").read_text("utf-8") == bf.render(r)
    assert r["affected_vs_clean_mad"] < 0.01
