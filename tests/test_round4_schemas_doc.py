"""B14/B15: docs/SCHEMAS.md is generated from schemas/ and no schema is dead."""

import importlib.util

from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("schemas_doc", ROOT / "tools" / "schemas_doc.py")
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)


def test_schemas_doc_up_to_date():
    assert (ROOT / "docs" / "SCHEMAS.md").read_text("utf-8") == sd.render(), "run: python tools/schemas_doc.py"


def test_no_dead_schema():
    assert sd.unreferenced() == []


def test_every_schema_has_a_section():
    text = (ROOT / "docs" / "SCHEMAS.md").read_text("utf-8")
    for p in (ROOT / "schemas").glob("*.json"):
        assert f"## `{p.name}`" in text
