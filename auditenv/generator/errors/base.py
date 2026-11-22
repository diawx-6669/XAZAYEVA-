"""Common interface and registry for error types.

A new error type is one module that subclasses ErrorType and calls @register.
Contract:
  applicable(book, used)          -> sorted list of candidate targets (internal keys)
  inject(book, target, rng, cfg)  -> Injected | None (mutates the book, records before/after)
  canonical_ids(book, target)     -> affected_ids exactly as the grader expects them
  evidence_sets(book, target)     -> 1-3 alternative minimal sets (<= 6 IDs each)
  expected_amount(book, target)   -> |distortion| in base currency minor units
"""

from __future__ import annotations

from dataclasses import dataclass, field

MIN_AMOUNT = 100  # every injected distortion is >= 100x the default tolerance (1 minor unit)

REGISTRY: dict = {}
ORDER = ["duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff", "vat_error"]


def register(cls):
    REGISTRY[cls.name] = cls()
    return cls


@dataclass
class Injected:
    type: str
    affected_ids: list
    expected_amount_minor: int
    currency: str
    evidence_sets: list
    variant: str
    target: str
    owners: list = field(default_factory=list)
    before: list = field(default_factory=list)
    after: list = field(default_factory=list)
    touched: list = field(default_factory=list)  # internal keys no later mutation may reuse
    detail: dict = field(default_factory=dict)  # cosmetic / sub-variant facts for provenance


def weighted_choice(rng, weights: dict, allowed=None):
    items = [(k, w) for k, w in sorted(weights.items()) if w > 0 and (allowed is None or k in allowed)]
    if not items:
        return None
    total = sum(w for _, w in items)
    x = rng.random() * total
    for k, w in items:
        x -= w
        if x < 0:
            return k
    return items[-1][0]


class ErrorType:
    name = ""
    invariant = ""

    def applicable(self, book, used: set) -> list:
        raise NotImplementedError

    def inject(self, book, target, rng, cfg, **kw):
        raise NotImplementedError

    def canonical_ids(self, book, target) -> list:
        raise NotImplementedError

    def evidence_sets(self, book, target) -> list:
        raise NotImplementedError

    def expected_amount(self, book, target, **kw) -> int:
        raise NotImplementedError

    # helper used by every type
    def finish(self, book, target, variant, owners, before, touched=(), detail=None, **kw) -> Injected:
        return Injected(
            touched=list(touched),
            detail=dict(detail or {}),
            type=self.name,
            affected_ids=self.canonical_ids(book, target),
            expected_amount_minor=self.expected_amount(book, target, **kw),
            currency=book.base,
            evidence_sets=self.evidence_sets(book, target),
            variant=variant,
            target=target,
            owners=owners,
            before=before,
            after=[book.snapshot(o) for o in owners],
        )


def revenue_rows(book, owner) -> list:
    return [r.row_id for r in book.rows_of(owner) if r.role.startswith(("inv_rev:", "cn_rev:"))]


def with_revenue_alternative(book, owner, head: list, tail: list) -> list:
    """Primary set uses the 1200 row; the alternative uses ALL revenue rows when it fits in 6 IDs."""
    ar = book.row_of(owner, "inv_ar").row_id
    sets = [head + [ar] + tail]
    rev = revenue_rows(book, owner)
    if len(head) + len(rev) + len(tail) <= 6:
        sets.append(head + rev + tail)
    return sets


def special(doc, allow=()) -> bool:
    """Documents of distractors/carriers are protected from independent errors, EXCEPT the tags an error
    type explicitly allows (where the error stays solvable from the documents): otherwise "this document
    is a distractor" would itself prove "this document is clean"."""
    return bool(set(doc.tags) - {"split_payment", "partial_open", "multi_invoice_payment"} - set(allow))
