"""grader_log.jsonl: one canonical JSON line per graded (or abandoned) episode, grader side only.

Tamper evidence: every record carries prev_hash = sha256 of the previous LINE (the first record
links to GENESIS). The head of the chain (hash of the last line) is printed by `make check` and
stored in reports/selfcheck.json; `python -m auditenv verify-log PATH` re-walks the chain, so an
edited, inserted, deleted or reordered line is detected.

Memory: only the last MEMORY_RECORDS records stay in memory (a bounded deque) - a long training
loop with millions of episodes writes to the file and does not grow the process.
"""

from __future__ import annotations

import hashlib
from collections import deque
from pathlib import Path

from ..canon import dumps

GENESIS = "0" * 64
MEMORY_RECORDS = 256


def line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


class GraderLog:
    def __init__(self, path=None, memory: int = MEMORY_RECORDS):
        self.path = Path(path) if path else None
        self.records = deque(maxlen=memory)
        self.count = 0
        self.head = GENESIS
        if self.path and self.path.exists():  # continue an existing chain
            last = None
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        last = line.rstrip("\n")
                        self.count += 1
            if last is not None:
                self.head = line_hash(last)

    def write(self, record: dict):
        rec = {**record, "prev_hash": self.head}
        line = dumps(rec)
        self.head = line_hash(line)
        self.count += 1
        self.records.append(rec)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")


def verify_chain(path, expected_head=None) -> dict:
    """{'ok', 'records', 'head', 'broken_at'}: broken_at is the 0-based line whose prev_hash is wrong.
    Editing the LAST line is only detectable against a published head: pass expected_head."""
    import json

    prev = GENESIS
    n = 0
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in (x.rstrip("\n") for x in fh if x.strip()):
            try:
                rec = json.loads(line)
            except ValueError:
                return {"ok": False, "records": n, "head": prev, "broken_at": n}
            if not isinstance(rec, dict) or rec.get("prev_hash") != prev or dumps(rec) != line:
                return {"ok": False, "records": n, "head": prev, "broken_at": n}
            prev = line_hash(line)
            n += 1
    ok = expected_head is None or expected_head == prev
    return {"ok": ok, "records": n, "head": prev, "broken_at": None if ok else n - 1}
