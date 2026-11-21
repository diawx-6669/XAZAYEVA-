"""A4: the reproducibility certificate - committed hashes equal a fresh in-memory regeneration."""

import copy
import json

from auditenv.paths import ROOT

import importlib.util
import pytest

pytestmark = pytest.mark.slow  # heavy round-4 check: in make check, not in make quick

_spec = importlib.util.spec_from_file_location("repro_cert", ROOT / "tools" / "repro_cert.py")
repro_cert = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repro_cert)


def test_committed_certificate_matches_fresh_generation():
    fresh = repro_cert.compute()
    committed = json.loads(repro_cert.OUT_JSON.read_text("utf-8"))
    gen = [k for k in fresh["items"] if not k.startswith("selfcheck/")]
    assert len([k for k in gen if k.endswith("/public") and k.startswith("episode/")]) == 20
    assert {k: fresh["items"][k] for k in gen} == {k: committed["items"][k] for k in gen}
    assert all(fresh["items"][k] == "true" for k in gen if k.endswith("committed_index_match"))


def test_compare_reports_every_mismatch():
    cert = {"machine": {}, "items": {"a": "1", "b": "2"}}
    other = copy.deepcopy(cert)
    other["items"]["b"] = "3"
    other["items"]["c"] = "4"
    assert repro_cert.compare(cert, other) == ["b", "c"]
    assert repro_cert.compare(cert, cert) == []
