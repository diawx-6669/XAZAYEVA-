"""The narrow tool interface. Pure functions over read-only PublicData.

list_records(table, cursor=None, limit=50)  table in {ledger, invoices, payments, fx}
get_record(table, id)                       table in {ledger, invoices, payments, fx, policy}
get_document(doc_id)                        invoice or payment document
calculator(expression)                      safe decimal arithmetic
submit(findings)                            handled by the env (terminates the episode)
"""

from __future__ import annotations

import copy

from .calculator import CalcError, evaluate
from .errors import BAD_ARGS, CALC_ERROR, INVALID_CURSOR, NOT_FOUND, ToolError

LIST_TABLES = ("ledger", "invoices", "payments", "fx")
GET_TABLES = ("ledger", "invoices", "payments", "fx", "policy")
PAGE_MAX = 50
TOOLS = ("list_records", "get_record", "get_document", "calculator", "submit")
ALLOWED_ARGS = {
    "list_records": ({"table"}, {"table", "cursor", "limit"}),
    "get_record": ({"table", "id"}, {"table", "id"}),
    "get_document": ({"doc_id"}, {"doc_id"}),
    "calculator": ({"expression"}, {"expression"}),
    "submit": ({"findings"}, {"findings"}),
}


def check_args(tool: str, args) -> None:
    if not isinstance(args, dict):
        raise ToolError(BAD_ARGS)
    required, allowed = ALLOWED_ARGS[tool]
    keys = set(args)
    if not required <= keys or not keys <= allowed:
        raise ToolError(BAD_ARGS)


def record_ids(table: str, rec: dict) -> list:
    """Primary IDs a returned record makes 'seen' (used by the experimental reward)."""
    if table == "ledger":
        return [rec["row_id"]]
    if table in ("invoices", "payments", "document"):
        return [rec["doc_id"]]
    if table == "fx":
        return [rec["fx_id"]]
    if table == "policy":
        return ["policy"]
    return []


def list_records(data, codec, args):
    table = args["table"]
    if table not in LIST_TABLES:
        raise ToolError(BAD_ARGS)
    limit = args.get("limit", PAGE_MAX)
    if isinstance(limit, bool) or not isinstance(limit, int) or not (1 <= limit <= PAGE_MAX):
        raise ToolError(BAD_ARGS)
    cursor = args.get("cursor")
    rows = data.table(table)
    if cursor is None:
        offset = 0
    else:
        offset = codec.decode(table, cursor)
        if offset is None or offset > len(rows):
            raise ToolError(INVALID_CURSOR)
    page = [copy.deepcopy(r) for r in rows[offset: offset + limit]]
    nxt = offset + len(page)
    return {"table": table, "records": page, "next_cursor": codec.encode(table, nxt) if nxt < len(rows) else None}, \
        [i for r in page for i in record_ids(table, r)]


def get_record(data, codec, args):
    table, rid = args["table"], args["id"]
    if table not in GET_TABLES or not isinstance(rid, str):
        raise ToolError(BAD_ARGS)
    rec = data.record_by_id(table, rid)
    if rec is None:
        raise ToolError(NOT_FOUND)
    return {"table": table, "record": copy.deepcopy(rec)}, record_ids(table, rec)


def get_document(data, codec, args):
    doc_id = args["doc_id"]
    if not isinstance(doc_id, str):
        raise ToolError(BAD_ARGS)
    rec = data.doc_by_id.get(doc_id)
    if rec is None:
        raise ToolError(NOT_FOUND)
    kind = "invoice" if "invoice_id" in rec else "payment"
    return {"kind": kind, "document": copy.deepcopy(rec)}, record_ids("document", rec)


def calculator(data, codec, args):
    try:
        return {"value": evaluate(args["expression"])}, []
    except CalcError:
        raise ToolError(CALC_ERROR)


DISPATCH = {"list_records": list_records, "get_record": get_record, "get_document": get_document,
            "calculator": calculator}
