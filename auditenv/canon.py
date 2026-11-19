"""Canonical JSON and hashing helpers (single source of byte-level determinism)."""

import hashlib
import json


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def dumps_bytes(obj) -> bytes:
    return (dumps(obj) + "\n").encode("utf-8")


def jsonl_bytes(rows) -> bytes:
    return "".join(dumps(r) + "\n" for r in rows).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def files_digest(files: dict) -> str:
    """Digest of a {name: bytes} mapping, independent of dict order."""
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode("utf-8") + b"\0")
        h.update(hashlib.sha256(files[name]).digest())
    return h.hexdigest()
