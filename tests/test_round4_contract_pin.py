"""B16: the agent-facing contract cannot change without bumping SCHEMA_VERSION."""

import copy
import importlib.util
import json

from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("contract_fingerprint", ROOT / "tools" / "contract_fingerprint.py")
cf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cf)


def test_contract_matches_pin_or_schema_version_was_bumped():
    pin = json.loads(cf.PIN.read_text("utf-8"))
    s = cf.surface()
    if s["schema_version"] == pin["schema_version"]:
        assert cf.fingerprint(s) == pin["sha256"], (
            "the agent-facing contract changed: bump auditenv.SCHEMA_VERSION and run python tools/contract_fingerprint.py")


def test_fingerprint_reacts_to_every_part():
    s = cf.surface()
    base = cf.fingerprint(s)
    for key, mut in [("page_max", 51), ("error_codes", s["error_codes"][:-1]), ("step_cost", "1/1000"),
                     ("task_text", s["task_text"] + " ")]:
        t = copy.deepcopy(s)
        t[key] = mut
        assert cf.fingerprint(t) != base, key
    t = copy.deepcopy(s)
    t["schemas"]["findings"]["properties"]["findings"]["maxItems"] = 31
    assert cf.fingerprint(t) != base
    t = copy.deepcopy(s)
    t["schema_version"] = "9.9"
    assert cf.fingerprint(t) == base, "the version itself is not part of the hash"
