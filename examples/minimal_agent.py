"""Minimal AuditEnv agent (~35 lines, stdlib only). Protocol: docs/ADAPTER.md.

Run:  python -m auditenv run --policy-cmd "python examples/minimal_agent.py" --seed 7 --config dev-mixed
It pages through the ledger and payments, reports receipts that reference invoices but sit on
Unapplied Cash (2400), and submits. Every line it reads is {"observation", "reward", "terminated",
"truncated"} or {"close": true}; every line it writes is {"action": {...}}.
"""
import json
import sys

TABLES = ["payments", "invoices", "ledger"]
state = {"episode_id": None, "tables": list(TABLES), "cursor": None, "rows": {t: [] for t in TABLES}}


def act(obs):
    if "manifest" in obs:
        state["episode_id"], state["base"] = obs["manifest"]["episode_id"], obs["manifest"]["base_currency"]
    elif "result" in obs and "records" in obs["result"]:
        state["rows"][obs["result"]["table"]] += obs["result"]["records"]
        state["cursor"] = obs["result"]["next_cursor"]
        if state["cursor"] is None:
            state["tables"].pop(0)
    if state["tables"] and obs.get("steps_remaining", 0) > 1:
        args = {"table": state["tables"][0], "limit": 50, **({"cursor": state["cursor"]} if state["cursor"] else {})}
        return {"tool": "list_records", "args": args}
    pays = {p["payment_id"]: p for p in state["rows"]["payments"] if p["invoice_refs"]}
    inv_doc = {i["invoice_id"]: i["doc_id"] for i in state["rows"]["invoices"]}
    found = [{"type": "payment_allocation", "affected_ids": [r["payment_id"]], "claimed_amount_minor": r["credit_minor"],
              "currency": state["base"], "explanation": "receipt with invoice refs left on 2400",
              "evidence_ids": [pays[r["payment_id"]]["doc_id"]] + [inv_doc.get(x, x) for x in pays[r["payment_id"]]["invoice_refs"]]
              + [r["row_id"]]} for r in state["rows"]["ledger"] if r["account"] == "2400" and r["payment_id"] in pays]
    return {"tool": "submit", "args": {"episode_id": state["episode_id"], "findings": found[:30]}}


for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("close"):
        break
    print(json.dumps({"action": act(msg["observation"])}), flush=True)
