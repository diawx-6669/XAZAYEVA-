"""Random explorer with a fixed seed: random (mostly valid) tool calls, then an empty submit."""

from .base import Policy, submit

TABLES = ["ledger", "invoices", "payments", "fx"]


class RandomExplorer(Policy):
    name = "random_explorer"

    def reset(self):
        super().reset()
        self.ids = []
        self.docs = []
        self.cursors = {}
        self.budget = self.rng.randint(5, 40)
        self.steps = 0

    def act(self, obs):
        if "manifest" in obs:
            self.manifest = obs["manifest"]
        res = obs.get("result") or {}
        for r in res.get("records", []):
            self.ids.append(("ledger", r["row_id"]) if "row_id" in r else ("fx", r["fx_id"]) if "fx_id" in r else
                            ("invoices", r["invoice_id"]) if "invoice_id" in r else ("payments", r["payment_id"]))
            if "doc_id" in r:
                self.docs.append(r["doc_id"])
        if res.get("next_cursor"):
            self.cursors[res["table"]] = res["next_cursor"]
        self.steps += 1
        if self.steps > self.budget:
            return submit(self.manifest["episode_id"], [])
        x = self.rng.random()
        if x < 0.45:
            t = self.rng.choice(TABLES)
            args = {"table": t, "limit": self.rng.randint(1, 50)}
            if t in self.cursors and self.rng.random() < 0.6:
                args["cursor"] = self.cursors[t]
            return {"tool": "list_records", "args": args}
        if x < 0.65 and self.ids:
            t, i = self.rng.choice(self.ids)
            return {"tool": "get_record", "args": {"table": t, "id": i}}
        if x < 0.8 and self.docs:
            return {"tool": "get_document", "args": {"doc_id": self.rng.choice(self.docs)}}
        if x < 0.9:
            a, b = self.rng.randint(1, 10 ** 6), self.rng.randint(1, 10 ** 4)
            return {"tool": "calculator", "args": {"expression": f"{a}*{b}/100"}}
        if x < 0.95:
            return {"tool": "get_record", "args": {"table": "invoices", "id": "INV-NOPE"}}
        return {"tool": "no_such_tool", "args": {}}
