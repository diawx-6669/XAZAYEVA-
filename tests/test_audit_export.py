"""E2: the manual-audit export matches the committed episodes and the worked example is right."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_export_matches_truth(tmp_path):
    from auditenv.audit_export import main

    for r in main(tmp_path):
        out = Path(r["out"])
        eid = r["episode_id"]
        truth = json.loads(next((ROOT / "episodes").glob(f"*/{eid}/grader/truth.json")).read_text())
        rows = list(csv.DictReader((out / "issues.csv").open()))
        assert [(x["issue_id"], int(x["expected_amount_minor"])) for x in rows] == [
            (i["issue_id"], i["expected_amount_minor"]) for i in truth["issues"]]
        ev = list(csv.DictReader((out / "evidence.csv").open()))
        assert {x["evidence_id"] for x in ev} == {x for i in truth["issues"] for s in i["evidence_sets"] for x in s}
        committed = ROOT / "audit" / out.name
        for f in ("issues.csv", "evidence.csv", "ledger.csv"):
            assert (committed / f).read_bytes() == (out / f).read_bytes(), (out.name, f)


def test_worked_example_in_manual():
    from decimal import ROUND_HALF_EVEN, Decimal

    assert (Decimal("4494.00") * Decimal("533.546")).quantize(Decimal("0.01"), ROUND_HALF_EVEN) == Decimal("2397755.72")
    assert Decimal("2403768.70") - Decimal("2397755.72") == Decimal("6012.98")
    text = (ROOT / "docs" / "MANUAL_AUDIT.md").read_text()
    assert "6 012.98" in text and "533.546" in text
