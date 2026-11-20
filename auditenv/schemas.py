"""Load and validate against the published JSON Schemas in schemas/."""

from __future__ import annotations

import json
from functools import lru_cache

from .paths import SCHEMAS_DIR

NAMES = ["manifest", "ledger_row", "invoice", "payment", "fx", "policy", "action", "observation", "findings",
         "truth", "config", "trajectory", "grader_log", "info", "index"]


@lru_cache(maxsize=None)
def _registry():
    from referencing import Registry, Resource

    reg = Registry()
    for n in NAMES:
        s = json.loads((SCHEMAS_DIR / f"{n}.schema.json").read_text("utf-8"))
        reg = reg.with_resource(s["$id"], Resource.from_contents(s))
    return reg


@lru_cache(maxsize=None)
def validator(name: str):
    import jsonschema

    s = json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text("utf-8"))
    return jsonschema.Draft202012Validator(s, registry=_registry())


def errors(name: str, obj) -> list:
    return [e.message for e in validator(name).iter_errors(obj)]


def validate_public(pd) -> list:
    """Schema problems in an episode's public files (empty list = valid)."""
    out = [f"manifest: {m}" for m in errors("manifest", pd.manifest)]
    out += [f"policy: {m}" for m in errors("policy", pd.policy)]
    for name, rows, schema in (("ledger", pd.ledger, "ledger_row"), ("invoices", pd.invoices, "invoice"),
                               ("payments", pd.payments, "payment"), ("fx", pd.fx, "fx")):
        for r in rows:
            for m in errors(schema, r):
                out.append(f"{name}: {m}")
                break
    c = pd.manifest["counts"]
    if (c["ledger"], c["invoices"], c["payments"], c["fx"]) != (len(pd.ledger), len(pd.invoices), len(pd.payments),
                                                              len(pd.fx)):
        out.append("manifest counts do not match files")
    return out
