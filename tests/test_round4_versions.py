"""B17: one version everywhere - package, schema, generator, committed manifests and trajectories metadata,
SBOM, contract.json and the self-check header agree."""

import json

import auditenv
from auditenv.cli import episode_dirs
from auditenv.paths import ROOT


def test_versions_agree():
    assert auditenv.GENERATOR_VERSION == "auditenv-gen-" + auditenv.__version__
    for _, d in episode_dirs():
        m = json.loads((d / "public" / "manifest.json").read_text("utf-8"))
        assert m["schema_version"] == auditenv.SCHEMA_VERSION and m["generator_version"] == auditenv.GENERATOR_VERSION, d
    sbom = json.loads((ROOT / "reports" / "sbom.json").read_text("utf-8"))
    assert sbom["metadata"]["component"]["version"] == auditenv.__version__
    contract = json.loads((ROOT / "contract.json").read_text("utf-8"))
    assert contract["contract_version"] == auditenv.SCHEMA_VERSION
    sc = json.loads((ROOT / "reports" / "selfcheck.json").read_text("utf-8"))["header"]
    assert sc["env_version"] == auditenv.__version__ and sc["generator_version"] == auditenv.GENERATOR_VERSION
    pin = json.loads((ROOT / "tests" / "contract_fingerprint.json").read_text("utf-8"))
    assert pin["schema_version"] == auditenv.SCHEMA_VERSION


def test_contract_json_limits_match_code():
    from auditenv.env import env as envmod
    from auditenv.env import errors, tools

    c = json.loads((ROOT / "contract.json").read_text("utf-8"))
    assert c["max_steps"] == envmod.MAX_STEPS and c["page_max"] == tools.PAGE_MAX
    assert float(c["time_limit_s"]) == envmod.TIME_LIMIT_S
    assert sorted(c["error_codes"]) == sorted(errors.CODES)
