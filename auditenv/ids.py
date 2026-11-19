"""Deterministic sub-seeds and unpredictable IDs.

Sub-seeds: sha256(f"{seed}:{stream}:{attempt}"). Streams are independent: story, errors,
naming, order, ... IDs come only from the `naming` stream and are random tokens (no
sequence numbers), so an agent cannot guess IDs or infer creation order.
"""

import hashlib
import random

ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"  # no 0/O/1/I/L/U confusion

PREFIX_CHOICES = {
    "entity": ["CUST", "CL", "CP"],
    "invoice": ["INV", "SF", "BL"],
    "payment": ["PMT", "RCV", "BNK"],
    "doc": ["DOC", "DC", "FD"],
    "row": ["GL", "JE", "LR"],
}


def derive_seed(seed, stream: str, attempt: int = 0) -> int:
    h = hashlib.sha256(f"{seed}:{stream}:{attempt}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


def make_rng(seed, stream: str, attempt: int = 0) -> random.Random:
    return random.Random(derive_seed(seed, stream, attempt))


class IdFactory:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.prefix = {k: rng.choice(v) for k, v in sorted(PREFIX_CHOICES.items())}
        self.length = {k: rng.randint(6, 8) for k in sorted(PREFIX_CHOICES)}
        self.used = set()

    def token(self, n: int) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(n))

    def new(self, kind: str) -> str:
        while True:
            s = f"{self.prefix[kind]}-{self.token(self.length[kind])}"
            if s not in self.used:
                self.used.add(s)
                return s

    def episode_id(self) -> str:
        s = "ep-" + self.token(10).lower()
        self.used.add(s)
        return s
