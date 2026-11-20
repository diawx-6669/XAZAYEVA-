"""Machine-readable environment contract (docs/CONTRACT.md, contract.json). Exposed as env.spec."""

from __future__ import annotations

import json

from .paths import ROOT

CONTRACT_PATH = ROOT / "contract.json"


def _load() -> dict:
    if CONTRACT_PATH.exists():
        return json.loads(CONTRACT_PATH.read_text("utf-8"))
    return {}


CONTRACT = _load()
