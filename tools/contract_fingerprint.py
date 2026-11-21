"""B16: a fingerprint of the agent-facing contract, pinned in tests/contract_fingerprint.json.

Covered: tool names, list/get tables, page size, step and time limits, error codes, the task text, the
reward step cost, and the schemas an agent depends on (action, observation, findings, info, policy,
manifest, invoice, payment, ledger row, fx). Any change to these changes the hash; the test then fails
unless auditenv.SCHEMA_VERSION was bumped too - so the contract cannot change silently.

    python tools/contract_fingerprint.py      -> rewrite the pin (after bumping SCHEMA_VERSION on purpose)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PIN = ROOT / "tests" / "contract_fingerprint.json"
AGENT_SCHEMAS = ["action", "observation", "findings", "info", "policy", "manifest", "invoice", "payment", "ledger_row", "fx"]


def surface() -> dict:
    from auditenv import SCHEMA_VERSION
    from auditenv.env import env as envmod
    from auditenv.env import errors, tools
    from auditenv.grader.reward import STEP_COST

    return {
        "tools": sorted(tools.DISPATCH), "list_tables": list(tools.LIST_TABLES), "get_tables": list(tools.GET_TABLES),
        "page_max": tools.PAGE_MAX, "max_steps": envmod.MAX_STEPS, "time_limit_s": envmod.TIME_LIMIT_S,
        "error_codes": list(errors.CODES), "task_text": envmod.task_text(1), "step_cost": str(STEP_COST),
        "schemas": {n: json.loads((ROOT / "schemas" / f"{n}.schema.json").read_text("utf-8")) for n in AGENT_SCHEMAS},
        "schema_version": SCHEMA_VERSION,
    }


def fingerprint(s: dict) -> str:
    body = {k: v for k, v in s.items() if k != "schema_version"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


if __name__ == "__main__":
    s = surface()
    PIN.write_text(json.dumps({"schema_version": s["schema_version"], "sha256": fingerprint(s),
                               "covers": sorted(k for k in s if k != "schema_version")}, indent=1) + "\n", "utf-8")
    print(f"contract-fingerprint: {fingerprint(s)[:16]}… pinned for SCHEMA_VERSION {s['schema_version']}")
