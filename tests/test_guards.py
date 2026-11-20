"""Guards for the vulnerabilities listed in docs/FAILURES.md ("found and closed")."""

import json
import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.salt
@pytest.mark.skipif(not hasattr(os, "getuid") or os.getuid() != 0, reason="the agent is dropped to nobody only under root")
def test_agent_cannot_read_parent_environ_salt():
    env = dict(os.environ, AUDITENV_SEED_SALT="jury-secret", PYTHONPATH=str(ROOT))
    out = subprocess.run([sys.executable, "-m", "auditenv", "run", "--policy-cmd",
                          f"{sys.executable} {ROOT / 'tests' / 'agents' / 'environ_spy.py'}", "--seed", "1",
                          "--config", "clean-only"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    res = json.loads(out.stdout)
    assert res["reward"] == 1.0  # honest empty answer on a clean book: the salt was NOT readable
    # control: with the old behaviour (same uid as the evaluator) the spy DOES get the salt
    env["AUDITENV_KEEP_UID"] = "1"
    out = subprocess.run([sys.executable, "-m", "auditenv", "run", "--policy-cmd",
                          f"{sys.executable} {ROOT / 'tests' / 'agents' / 'environ_spy.py'}", "--seed", "1",
                          "--config", "clean-only"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert json.loads(out.stdout)["reward"] == -1.0


def test_every_dependency_is_pinned_and_installed_as_pinned():
    """jsonschema pulls referencing -> rpds-py (a compiled Rust extension). Every transitive dependency is
    pinned with == and installed with --no-deps, so no resolver can bring in another build."""
    pins = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            assert "==" in line, line
            name, ver = line.split("==")
            pins[name.lower().replace("_", "-")] = ver
    for name in ("jsonschema", "referencing", "rpds-py", "jsonschema-specifications", "attrs", "hypothesis", "pytest"):
        assert name in pins, name
    for name, ver in pins.items():
        assert version(name) == ver, (name, version(name), ver)
    assert "--no-deps" in (ROOT / "Dockerfile").read_text()
    assert "@sha256:" in (ROOT / "Dockerfile").read_text().split("FROM", 1)[1].splitlines()[0]


def test_manifest_and_invoice_have_only_case_fields(clean):
    case_invoice = {"doc_id", "invoice_id", "entity_id", "issued_at", "due_at", "currency", "total_minor", "line_items"}
    case_payment = {"doc_id", "payment_id", "timestamp", "currency", "amount_minor", "invoice_refs"}
    pd = clean.public()
    assert all(set(i) == case_invoice for i in pd.invoices)
    assert all(set(p) == case_payment for p in pd.payments)
    assert pd.files["ledger.csv"].splitlines()[0] == (b"row_id,timestamp,account,debit_minor,credit_minor,currency,"
                                                      b"entity_id,invoice_id,payment_id")
    assert pd.files["fx.csv"].splitlines()[0] == b"date,source_currency,target_currency,rate"
