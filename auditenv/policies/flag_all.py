"""flag_all attack: reads invoices and payments, then accuses as many documents as the
limits allow (30 findings), rotating through the error types, claiming the document total."""

from ..env.data import TABLES  # noqa: F401
from .base import Policy, TableReader, finding, submit

TYPES = ["duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff", "vat_error"]


class FlagAll(Policy):
    name = "flag_all"

    def reset(self):
        super().reset()
        self.reader = None

    def act(self, obs):
        if "manifest" in obs:
            self.manifest = obs["manifest"]
            self.reader = TableReader(["invoices", "payments"])
        else:
            self.reader.feed(obs)
        a = self.reader.next_action()
        if a is not None:
            return a
        out = []
        docs = [("inv", d) for d in self.reader.data["invoices"]] + [("pay", d) for d in self.reader.data["payments"]]
        for k, (kind, d) in enumerate(docs[:30]):
            typ = TYPES[k % 4]
            ids = [d["invoice_id"]] if kind == "inv" else [d["payment_id"]]
            amt = abs(d.get("total_minor", d.get("amount_minor", 0)))
            out.append(finding(typ, ids, amt, self.manifest["base_currency"], [d["doc_id"], "policy"], "suspicious"))
        return submit(self.manifest["episode_id"], out)
