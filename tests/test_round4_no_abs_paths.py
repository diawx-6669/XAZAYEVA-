"""B5: recorded trajectories and committed artefacts carry no absolute paths or user names of the machine
that produced them (a leak of the evaluator's environment beyond what leakscan looks for, and a sign of
non-portable output)."""

import re

import pytest

from auditenv.paths import ROOT

PATTERN = re.compile(r"(/home/[a-z_][\w.-]*|/Users/[A-Za-z][\w.-]*|/root/|\b[A-Z]:\\\\(?:Users|Documents)|/private/var/"
                     r"|/var/folders/|/tmp/pytest-of-|/tmp/auditenv-agent-)")
TARGETS = ["trajectories/trajectories.jsonl", "reports", "site", "tools/llm", "episodes", "audit"]


def files():
    out = []
    for t in TARGETS:
        p = ROOT / t
        out += [p] if p.is_file() else [q for q in sorted(p.rglob("*")) if q.is_file() and q.suffix in
                                        (".json", ".jsonl", ".md", ".html", ".csv", ".svg")]
    return out


@pytest.mark.parametrize("target", TARGETS)
def test_no_absolute_paths(target):
    bad = []
    for f in files():
        if not f.relative_to(ROOT).as_posix().startswith(target):
            continue
        for m in PATTERN.finditer(f.read_text("utf-8", errors="replace")):
            bad.append(f"{f.relative_to(ROOT)}: {m.group(0)}")
    assert not bad, bad[:10]


def test_pattern_positive_control():
    for s in ["/home/alice/x", "/Users/bob/repo", "/root/.cache", "C:\\\\Users\\\\x", "/tmp/pytest-of-root/1",
              "/tmp/auditenv-agent-abc"]:
        assert PATTERN.search(s), s
    for s in ["/app/reports", "episodes/dev/ep-x/public", "fx:2026-10-30:KWD:KZT"]:
        assert not PATTERN.search(s), s
