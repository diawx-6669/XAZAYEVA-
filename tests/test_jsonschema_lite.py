"""The built-in JSON Schema validator (replaces the jsonschema package)."""

import json

import pytest

from auditenv.jsonschema_lite import Validator, validate
from auditenv.paths import SCHEMAS_DIR
from auditenv.schemas import NAMES, validator

S = {"type": "object", "additionalProperties": False, "required": ["a"],
     "properties": {"a": {"type": "integer", "minimum": 0, "maximum": 10},
                    "b": {"type": ["string", "null"], "pattern": "^x+$", "maxLength": 3},
                    "c": {"type": "array", "maxItems": 2, "items": {"enum": ["p", "q"]}},
                    "d": {"$ref": "#/$defs/k"}},
     "$defs": {"k": {"const": True}}}


@pytest.mark.parametrize("value", [{"a": 0}, {"a": 10, "b": None}, {"a": 1, "b": "xx", "c": ["p", "q"], "d": True}])
def test_valid(value):
    assert Validator(S).is_valid(value)


@pytest.mark.parametrize("value,keyword", [
    ({}, "required"), ({"a": 1, "z": 1}, "additionalProperties"), ({"a": True}, "type"), ({"a": 5.0}, "type"),
    ({"a": -1}, "minimum"), ({"a": 11}, "maximum"), ({"a": 1, "b": "y"}, "pattern"), ({"a": 1, "b": "xxxx"}, "maxLength"),
    ({"a": 1, "c": ["p", "p", "p"]}, "maxItems"), ({"a": 1, "c": ["r"]}, "enum"), ({"a": 1, "d": 1}, "const"),
    ([], "type"), ("x", "type")])
def test_invalid(value, keyword):
    errs = list(Validator(S).iter_errors(value))
    assert errs and errs[0].validator == keyword


def test_one_of_and_cross_file_ref():
    v = validator("action")
    good = {"tool": "submit", "args": {"findings": {"episode_id": "ep-x", "findings": []}}}
    assert v.is_valid(good)
    assert not v.is_valid({"tool": "submit", "args": {"findings": {"episode_id": "ep-x", "findings": "no"}}})
    assert not v.is_valid({"tool": "list_records", "args": {"table": "ledger", "limit": 51}})
    assert v.is_valid({"tool": "list_records", "args": {"table": "ledger", "limit": 50}})


def test_every_project_schema_loads_and_uses_only_supported_keywords():
    for n in NAMES:
        validator(n)
    with pytest.raises(ValueError):
        Validator({"type": "string", "format": "email"})  # unsupported keyword must not be ignored silently


def test_findings_limits():
    v = validator("findings")
    f = {"type": "fx_rate", "affected_ids": ["X"], "claimed_amount_minor": 1, "currency": "KZT", "evidence_ids": [],
         "explanation": ""}
    assert v.is_valid({"episode_id": "e", "findings": [f] * 30})
    assert not v.is_valid({"episode_id": "e", "findings": [f] * 31})
    assert not v.is_valid({"episode_id": "e", "findings": [dict(f, evidence_ids=["a"] * 11)]})
    assert not v.is_valid({"episode_id": "e", "findings": [dict(f, explanation="x" * 1001)]})
    assert not v.is_valid({"episode_id": "e", "findings": [dict(f, extra=1)]})


def test_validate_raises_with_path():
    with pytest.raises(ValueError, match="a"):
        validate({"a": "x"}, S)


def test_no_jsonschema_import_anywhere():
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent / "auditenv"
    for p in root.rglob("*.py"):
        text = p.read_text()
        assert "import jsonschema" not in text and "from jsonschema" not in text and "referencing" not in text, p
    assert json.loads((SCHEMAS_DIR / "findings.schema.json").read_text())["$id"]


def test_vendor_wheels_are_pure_python_and_match_requirements():
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    reqs = {}
    for line in (root / "requirements.txt").read_text().splitlines():
        if line.strip():
            name, ver = line.strip().split("==")
            reqs[re.sub(r"[-_.]+", "_", name).lower()] = ver
    wheels = sorted((root / "vendor" / "wheels").glob("*.whl"))
    got = {}
    for w in wheels:
        name, ver, *_, py, abi, plat = w.stem.split("-")
        assert abi == "none" and plat == "any" and "py3" in py.split("."), w.name  # no compiled wheels
        got[re.sub(r"[-_.]+", "_", name).lower()] = ver
    assert got == reqs
    assert "jsonschema" not in got and "rpds_py" not in got
