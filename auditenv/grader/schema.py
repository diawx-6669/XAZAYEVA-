"""JSON Schema validation of findings.json (additionalProperties: false everywhere)."""

import json
from functools import lru_cache

from ..paths import SCHEMAS_DIR


@lru_cache(maxsize=None)
def _validator():
    from ..jsonschema_lite import Validator

    schema = json.loads((SCHEMAS_DIR / "findings.schema.json").read_text("utf-8"))
    return Validator(schema)


def validate_findings(obj, episode_id: str):
    """Returns None if valid, else a short error code for the grader log."""
    try:
        json.dumps(obj, allow_nan=False)
    except (TypeError, ValueError):
        return "not_json"
    errors = sorted(_validator().iter_errors(obj), key=lambda e: [str(p) for p in e.path])
    if errors:
        e = errors[0]
        return "schema:" + "/".join(str(p) for p in e.path) + ":" + e.validator
    # JSON Schema treats 5.0 as an integer; money must be a real int (never float/bool).
    for k, f in enumerate(obj["findings"]):
        if type(f["claimed_amount_minor"]) is not int:
            return f"schema:findings/{k}/claimed_amount_minor:int_required"
    if obj["episode_id"] != episode_id:
        return "episode_id_mismatch"
    return None
