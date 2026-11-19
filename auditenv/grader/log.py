"""grader_log.jsonl: one canonical JSON line per graded episode (grader side only)."""

from pathlib import Path

from ..canon import dumps


class GraderLog:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.records = []

    def write(self, record: dict):
        self.records.append(record)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(dumps(record) + "\n")
