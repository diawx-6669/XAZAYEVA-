"""JSON Schema validation of findings.json (additionalProperties: false everywhere)."""

import json
from functools import lru_cache

from ..paths import SCHEMAS_DIR


@lru_cache(maxsize=None)
def _validator():
    import jsonschema

    schema = json.loads((SCHEMAS_DIR / "findings.schema.json").read_text("utf-8"))
    return jsonschema.Draft202012Validator(schema)


def validate_findings(obj, episode_id: str):
    """Returns None if valid, else a short error code for the grader log."""
    try:
        json.dumps(obj, allow_nan=False)
    except (TypeError, ValueError):
        return "not_json"
    errors = sorted(_validator().iter_errors(obj), key=lambda e: list(e.absolute_path))
    if errors:
        e = errors[0]
        return "schema:" + "/".join(str(p) for p in e.absolute_path) + ":" + e.validator
    if obj["episode_id"] != episode_id:
        return "episode_id_mismatch"
    return None
