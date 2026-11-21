"""Jury policy: random explorer with a fixed seed. Random valid actions, then empty submit."""
import random
import sys

from jl import Conn, run

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20261122
N_ACTIONS = int(sys.argv[2]) if len(sys.argv) > 2 else 20


def main(c: Conn):
    rng = random.Random(SEED)
    first = c.start()
    ep = first["manifest"]["episode_id"]
    seen = []
    cursors = {}
    for _ in range(N_ACTIONS):
        k = rng.randrange(4)
        if k == 0:
            t = rng.choice(["ledger", "invoices", "payments", "fx"])
            args = {"table": t, "limit": rng.randint(1, 50)}
            if t in cursors and rng.random() < 0.5:
                args["cursor"] = cursors[t]
            obs = c.call("list_records", **args)
            res = obs.get("result") or {}
            for r in res.get("records", []):
                seen.append(r.get("doc_id") or r.get("row_id"))
            if res.get("next_cursor"):
                cursors[t] = res["next_cursor"]
        elif k == 1 and seen:
            c.call("get_document", doc_id=rng.choice(seen))
        elif k == 2:
            c.call("get_record", table="policy", id="policy")
        else:
            c.call("calculator", expression=f"{rng.randint(1, 999)} * {rng.randint(1, 99)} / 7")
    c.submit(ep, [])


run(main)
