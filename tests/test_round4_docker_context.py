"""Docker build context: every committed file that tests or docs-check read must reach the image.
Regression: .dockerignore excluded all of reports/, so tests reading committed reports passed locally and
would have failed inside the jury's container (found by a trial docker build in round 4)."""

import fnmatch
import subprocess

import pytest

from auditenv.paths import ROOT


def _patterns():
    out = []
    for ln in (ROOT / ".dockerignore").read_text("utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and not ln.startswith("!"):
            out.append(ln.rstrip("/"))
    return out


def _ignored(path: str, pats) -> bool:
    for p in pats:
        p2 = p[3:] if p.startswith("**/") else p
        parts = path.split("/")
        for k in range(1, len(parts) + 1):
            head = "/".join(parts[:k])
            if fnmatch.fnmatch(head, p) or (p.startswith("**/") and fnmatch.fnmatch(parts[k - 1], p2)):
                return True
    return False


def test_committed_inputs_are_in_the_build_context():
    if not (ROOT / ".git").exists():  # inside the image (.git is not copied): nothing to compare
        pytest.skip("not a git checkout")
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    pats = _patterns()
    needed = [f for f in files if f.startswith(("reports/", "episodes/", "trajectories/", "tools/", "tests/", "site/",
                                                "docs/", "schemas/", "configs/", "vendor/", "examples/", "jury_sim/"))
              or f in ("README.md", "contract.json", "Dockerfile", "THIRD_PARTY_NOTICES.md", "requirements.txt")]
    missing = [f for f in needed if _ignored(f, pats)]
    assert not missing, f".dockerignore drops committed files the checks read: {missing[:10]}"


def test_matcher_sanity():
    assert _ignored("reports/x.md", ["reports"]) and _ignored("a/__pycache__/b.pyc", ["**/__pycache__"])
    assert not _ignored("reports/x.md", ["reports/tmp"])
