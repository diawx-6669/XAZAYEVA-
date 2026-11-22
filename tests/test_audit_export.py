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

    assert (Decimal("2660.000") * Decimal("1610.87")).quantize(Decimal("0.01"), ROUND_HALF_EVEN) == Decimal("4284914.20")
    assert Decimal("4284914.20") - Decimal("4277652.40") == Decimal("7261.80")
    issues = list(csv.DictReader((ROOT / "audit" / "3_fx_weekend_ep-xt9h93jnn2" / "issues.csv").open()))
    assert issues[0]["affected_id"] == "BNK-TAM4YY" and issues[0]["expected_amount"] == "7261.80"
    text = (ROOT / "docs" / "MANUAL_AUDIT.md").read_text()
    assert "7 261.80" in text and "1 610.87" in text
