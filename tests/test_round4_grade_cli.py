"""B2: `python -m auditenv grade` grades a hand-written findings file with a reason per finding."""

import json

from auditenv.cli import main
from auditenv.paths import ROOT

EP = ROOT / "episodes" / "dev" / "ep-xt9h93jnn2"


def _answer():
    t = json.loads((EP / "grader" / "truth.json").read_text("utf-8"))
    return [{"type": i["type"], "affected_ids": i["affected_ids"], "claimed_amount_minor": i["expected_amount_minor"],
             "currency": i["currency"], "evidence_ids": i["evidence_sets"][0], "explanation": ""} for i in t["issues"]]


def test_grade_list_form_with_reasons(tmp_path, capsys):
    fs = _answer()
    fs.append({**fs[0], "currency": "USD"})
    p = tmp_path / "f.json"
    p.write_text(json.dumps(fs), "utf-8")
    assert main(["grade", str(EP), str(p), "--steps", "10"]) == 0
    out = capsys.readouterr().out
    assert "TP -> ISS-001" in out and "FP (currency_mismatch)" in out and "reward=+0.580" in out


def test_grade_json_and_invalid(tmp_path, capsys):
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"episode_id": "ep-xt9h93jnn2", "findings": _answer()}), "utf-8")
    assert main(["grade", str(EP), str(p), "--json"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["tp"] == 2 and r["reward"] == 1.0
    p.write_text(json.dumps({"episode_id": "other", "findings": []}), "utf-8")
    main(["grade", str(EP), str(p)])
    assert "INVALID" in capsys.readouterr().out
