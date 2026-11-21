"""A19: coverage-map factors are extracted correctly and every uncovered pair gets a reason."""

import importlib.util
import sys

from auditenv.paths import ROOT

sys.path.insert(0, str(ROOT / "tools"))
_spec = importlib.util.spec_from_file_location("coverage_map", ROOT / "tools" / "coverage_map.py")
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)


def test_factors_on_a_sample():
    rows = cm.collect(12)
    assert rows
    for r in rows:
        for f, dom in cm.DOMAINS.items():
            assert r[f] in dom, (f, r[f])


def test_interaction_labels_pair_up():
    rows = [r for r in cm.collect(18) if r["interaction"] != "none"]
    for s in ("partial_fx_cutoff", "duplicate_fx"):
        kinds = sorted(r["variant"].split("/")[0] for r in rows if r["interaction"] == s)
        assert len(kinds) % 2 == 0
        if s == "partial_fx_cutoff" and kinds:
            assert set(kinds) == {"fx_rate", "payment_allocation"}


def test_structural_reasons():
    b = {"KZT", "USD"}
    assert cm.reason("base", "EUR", "weekend", "no", b).startswith("конфиги")
    assert cm.reason("variant", "period_cutoff/utc_trap", "interaction", "duplicate_fx", b).startswith("структура")
    assert cm.reason("variant", "fx_rate/inverted", "interaction", "partial_fx_cutoff", b).startswith("генератор")
