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

    assert (Decimal("2764.444") * Decimal("1492.36")).quantize(Decimal("0.01"), ROUND_HALF_EVEN) == Decimal("4125545.65")
    assert Decimal("4125545.65") - Decimal("4123057.65") == Decimal("2488.00")
    issues = list(csv.DictReader((ROOT / "audit" / "3_fx_weekend_ep-xt9h93jnn2" / "issues.csv").open()))
    assert issues[0]["affected_id"] == "BNK-6QF7D6" and issues[0]["expected_amount"] == "2488.00"
    text = (ROOT / "docs" / "MANUAL_AUDIT.md").read_text()
    assert "2 488.00" in text and "1 492.36" in text
