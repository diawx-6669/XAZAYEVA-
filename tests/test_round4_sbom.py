"""A14: reports/sbom.json lists the base image and every wheel with sha256; verify-sbom catches tampering."""

import copy
import json

from auditenv.paths import ROOT
from auditenv.supply import SBOM_PATH, build_sbom, verify_sbom


def test_committed_sbom_matches_disk_and_generator():
    sbom = json.loads(SBOM_PATH.read_text("utf-8"))
    assert verify_sbom(sbom) == []
    assert sbom == json.loads(json.dumps(build_sbom())), "run: python -m auditenv verify-sbom --write"


def test_sbom_detects_tampered_hash_missing_wheel_and_base_image():
    sbom = build_sbom()
    bad = copy.deepcopy(sbom)
    bad["components"][1]["hashes"][0]["content"] = "0" * 64
    assert any("sha256 mismatch" in p for p in verify_sbom(bad))
    bad = copy.deepcopy(sbom)
    del bad["components"][2]
    assert any("not in the SBOM" in p for p in verify_sbom(bad))
    bad = copy.deepcopy(sbom)
    bad["components"][0]["hashes"][0]["content"] = "f" * 64
    assert any("base image" in p for p in verify_sbom(bad))


def test_sbom_is_deterministic_and_has_no_timestamp():
    a = json.dumps(build_sbom(), sort_keys=True)
    assert a == json.dumps(build_sbom(), sort_keys=True)
    assert "timestamp" not in a and "serialNumber" not in a
    assert sum(1 for ln in (ROOT / "Dockerfile").read_text("utf-8").splitlines() if ln.startswith("FROM")) == 1
