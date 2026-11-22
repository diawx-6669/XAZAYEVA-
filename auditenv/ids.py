"""Deterministic sub-seeds and unpredictable IDs.

Sub-seeds: sha256(f"{seed}:{stream}:{attempt}"). Streams are independent: story, errors,
naming, order, ... IDs come only from the `naming` stream and are random tokens (no
sequence numbers), so an agent cannot guess IDs or infer creation order.
"""

import hashlib
import os
import random

SALT_ENV = "AUDITENV_SEED_SALT"

ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"  # no 0/O/1/I/L/U confusion

PREFIX_CHOICES = {
    "entity": ["CUST", "CL", "CP"],
    "invoice": ["INV", "SF", "BL"],
    "payment": ["PMT", "RCV", "BNK"],
    "doc": ["DOC", "DC", "FD"],
    "row": ["GL", "JE", "LR"],
}


def derive_seed(seed, stream: str, attempt: int = 0) -> int:
    """sha256(f"{seed}:{stream}:{attempt}"). For closed runs the evaluator sets the secret
    AUDITENV_SEED_SALT: the generator is open source, so without a salt an agent could brute-force
    small seeds from the public episode_id and regenerate truth. The salt is never passed to
    the agent process (runner.py builds the child environment explicitly)."""
    salt = os.environ.get(SALT_ENV, "")
    key = f"{seed}:{stream}:{attempt}" if not salt else f"{salt}|{seed}:{stream}:{attempt}"
    h = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


def salted() -> bool:
    return bool(os.environ.get(SALT_ENV, ""))


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

    def episode_id(self, config_hash: str = "") -> str:
        """The naming stream gives the token; config_hash is mixed in so that one seed with two
        different configs never shares an episode_id (jury simulation finding #4). The RNG draw is
        the same either way, so every other ID of the episode is unaffected by this mixing."""
        tok = self.token(10)
        if config_hash:
            h = hashlib.sha256(f"{tok}:{config_hash}".encode("utf-8")).digest()
            tok = "".join(ALPHABET[b % len(ALPHABET)] for b in h[:10])
        s = "ep-" + tok.lower()
        self.used.add(s)
        return s
