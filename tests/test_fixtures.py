"""Round 3, item 1: hand-made companies (tests/fixtures/<name>/*.csv, format: auditenv/fixtures.py).

For every fixture folder: the public files pass the schemas; the in-repo solver (validate_truth) finds EXACTLY
the author's issues.csv (same types and IDs, amounts within tolerance, every evidence set recomputes the amount);
the independent verifier (tools/verify_independent.py, python -I, no auditenv imports) agrees; the oracle that
submits the author's answer gets reward 1.0 and the empty answer gets what the case says it should.
The importer itself is checked by a byte-exact round trip on all 20 committed episodes.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from auditenv.audit_export import export_one
from auditenv.env.data import PublicData
from auditenv.fixtures import FixtureError, load_fixture, read_tables
from auditenv.generator.export import read_public_files, write_episode
from auditenv.grader.validate_truth import validate
from auditenv.paths import EPISODES_DIR
from auditenv.runner import run_episode
from auditenv.schemas import validate_public

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
FOLDERS = sorted(p for p in FIXTURES.iterdir() if p.is_dir() and (p / "ledger.csv").exists()) if FIXTURES.exists() else []
# Ibra's three companies from his Google Sheet: a duplicate, a wrong FX rate, a clean book with rent.
IBRA = {"ibra_duplicate": ["duplicate_invoice"], "ibra_fx_rate": ["fx_rate"], "ibra_clean_rent": []}
COMMITTED = sorted(d for s in ("train", "dev") for d in (EPISODES_DIR / s).iterdir() if d.is_dir())


@pytest.mark.parametrize("src", COMMITTED, ids=lambda d: d.name)
def test_csv_import_round_trips_every_committed_episode_byte_exact(src, tmp_path):
    export_one(src, tmp_path / src.name)  # the very sheets a person edits in Google Sheets
    (tmp_path / src.name / "meta.csv").write_text(f"key,value\nepisode_id,{src.name}\n", "utf-8")
    ep = load_fixture(tmp_path / src.name)
    orig = read_public_files(src / "public")
    for name in ("ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv", "policy.json"):
        assert ep.files[name] == orig[name], name
    om, nm = json.loads(orig["manifest.json"]), json.loads(ep.files["manifest.json"])
    assert {k: v for k, v in om.items() if k not in ("config_hash", "config_version", "generator_version")} == \
           {k: v for k, v in nm.items() if k not in ("config_hash", "config_version", "generator_version")}
    assert ep.truth == json.loads((src / "grader" / "truth.json").read_text("utf-8"))


def test_import_errors_name_the_sheet_row_and_column(tmp_path):
    src = COMMITTED[0]
    export_one(src, tmp_path / "x")
    p = tmp_path / "x" / "ledger.csv"
    lines = p.read_text().splitlines()
    head, row = lines[0].split(","), lines[1].split(",")
    row[head.index("debit_minor")] = "12.50"
    p.write_text("\n".join([lines[0], ",".join(row)] + lines[2:]) + "\n")
    with pytest.raises(FixtureError, match=r"ledger.csv row 2: column 'debit_minor' must be an integer"):
        read_tables(tmp_path / "x")
    export_one(src, tmp_path / "y")
    (tmp_path / "y" / "fx.csv").unlink()
    with pytest.raises(FixtureError, match="missing sheet fx.csv"):
        read_tables(tmp_path / "y")


def check_fixture(folder: Path) -> dict:
    ep = load_fixture(folder)
    pd = PublicData(ep.files)
    assert validate_public(pd) == [], "public files do not pass the schemas"
    v = validate(pd, ep.truth)
    assert v["ok"], f"in-repo solver disagrees with the author's answer: {v}"
    with tempfile.TemporaryDirectory() as t:
        d = write_episode(ep, Path(t) / ep.episode_id)
        out = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "verify_independent.py"), "--json", str(d)],
                             capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, f"independent verifier disagrees: {out.stdout[-2000:]} {out.stderr[-500:]}"
    oracle = run_episode("oracle", episode=ep, record=False)["grade"]
    assert (oracle["tp"], oracle["fp"], oracle["fn"], oracle["reward"]) == (len(ep.truth["issues"]), 0, 0, 1.0)
    empty = run_episode("random_explorer", episode=ep, isolate=False, record=False)["grade"]  # submits nothing
    assert empty["tp"] == 0 and empty["f1"] == (1.0 if not ep.truth["issues"] else 0.0)
    return {"types": sorted(i["type"] for i in ep.truth["issues"]), "n_found": v["n_found"]}


@pytest.mark.parametrize("folder", sorted(p for p in (ROOT / "audit").iterdir() if p.is_dir()), ids=lambda p: p.name)
def test_committed_manual_audit_sheets_import_and_agree(folder):
    """The CSV sheets in audit/ (what a person opens in Google Sheets) go through the same fixture pipeline."""
    check_fixture(folder)


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda p: p.name)
def test_hand_made_fixture_solver_verifier_and_oracle_give_the_authors_answer(folder):
    check_fixture(folder)


@pytest.mark.parametrize("name", sorted(IBRA))
def test_ibra_companies(name):
    folder = FIXTURES / name
    if not (folder / "ledger.csv").exists():
        pytest.skip(f"tests/fixtures/{name}/ not added yet: export Ibra's sheets as CSV (tests/fixtures/README.md)")
    res = check_fixture(folder)
    assert res["types"] == IBRA[name]
