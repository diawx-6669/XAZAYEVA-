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
    cmd = [sys.executable, "-m", "auditenv", "run", "--policy-cmd",
           f"{sys.executable} {ROOT / 'tests' / 'agents' / 'environ_spy.py'}", "--seed", "1", "--config", "clean-only"]
    # third layer alone (jury sim fix: the salt is handed over a pipe, never in the exec-time environment):
    # same uid AND a dumpable evaluator, and the spy still cannot read the salt
    env["AUDITENV_KEEP_UID"] = "1"
    env["AUDITENV_INSECURE_DUMPABLE"] = "1"
    out = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert json.loads(out.stdout)["reward"] == 1.0
    # control: with ALL THREE layers off (same uid, dumpable evaluator, salt in the exec-time environment)
    # the spy DOES get the salt - each layer alone is enough to stop it
    env["AUDITENV_NO_CONCEAL"] = "1"
    out = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert json.loads(out.stdout)["reward"] == -1.0


def test_every_dependency_is_pinned_and_installed_as_pinned():
    """No jsonschema / referencing / rpds-py (a compiled Rust extension): JSON Schema is checked by
    auditenv/jsonschema_lite.py. Only pytest + hypothesis and their pure-Python dependencies, pinned
    with == (requirements.txt = pip freeze), each with a pure-Python wheel in vendor/wheels, installed
    offline with --no-index --no-deps on a digest-pinned base image."""
    pins = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            assert "==" in line, line
            name, ver = line.split("==")
            pins[name.lower().replace("_", "-")] = ver
    assert {"pytest", "hypothesis"} <= set(pins)
    assert not {"jsonschema", "referencing", "rpds-py", "jsonschema-specifications"} & set(pins)
    for name, ver in pins.items():
        assert version(name) == ver, (name, version(name), ver)
    wheels = sorted(p.name for p in (ROOT / "vendor" / "wheels").glob("*.whl"))
    assert all(w.endswith("-none-any.whl") and "py3" in w.split("-")[-3] for w in wheels), wheels  # pure Python
    for name, ver in pins.items():
        assert any(w.lower().replace("_", "-").startswith(f"{name}-{ver}-") for w in wheels), (name, ver)
    assert len(wheels) == len(pins)
    df = (ROOT / "Dockerfile").read_text()
    assert "--no-index" in df and "--no-deps" in df and "vendor/wheels" in df
    assert "@sha256:" in df.split("\nFROM", 1)[1].splitlines()[0]
    import importlib.util

    assert importlib.util.find_spec("jsonschema") is None and importlib.util.find_spec("rpds") is None


def test_manifest_and_invoice_have_only_case_fields(clean):
    case_invoice = {"doc_id", "invoice_id", "entity_id", "issued_at", "due_at", "currency", "total_minor", "line_items"}
    case_payment = {"doc_id", "payment_id", "timestamp", "currency", "amount_minor", "invoice_refs"}
    pd = clean.public()
    assert all(set(i) == case_invoice for i in pd.invoices)
    assert all(set(p) == case_payment for p in pd.payments)
    assert pd.files["ledger.csv"].splitlines()[0] == (b"row_id,timestamp,account,debit_minor,credit_minor,currency,"
                                                      b"entity_id,invoice_id,payment_id")
    assert pd.files["fx.csv"].splitlines()[0] == b"date,source_currency,target_currency,rate"
