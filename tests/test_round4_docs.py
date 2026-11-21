"""Round-4 documents: form texts fit their limits, required docs exist and link to real files."""

import re

from auditenv.paths import ROOT

ROUND4_DOCS = ["docs/HOTFIX.md", "docs/SUBMISSION_FORM.md", "docs/AI_USAGE.md", "docs/DESIGN_SHORT.md"]  # ROUND4_IDEAS.md is a plan: it names files before they exist


def test_submission_form_lengths():
    t = (ROOT / "docs" / "SUBMISSION_FORM.md").read_text("utf-8")
    found = re.findall(r"<!--desc:(\d+)-->\n(.*?)\n<!--/desc-->", t, re.S)
    assert [int(n) for n, _ in found] == [100, 300, 1000]
    for n, body in found:
        assert 0 < len(body) <= int(n), (n, len(body))
    for who in ("Ералы", "Бекназар", "Ибрагим", "Алдик"):
        assert who in t


def test_round4_docs_exist_and_reference_real_paths():
    for rel in ROUND4_DOCS:
        t = (ROOT / rel).read_text("utf-8")
        for path in re.findall(r"`((?:docs|tests|tools|reports|auditenv|jury_sim|scripts|site|examples)/[\w./-]+)`", t):
            path = path.split("::")[0].rstrip(".")
            assert (ROOT / path).exists() or "<" in path, f"{rel}: {path} does not exist"


def test_design_short_is_short():
    t = (ROOT / "docs" / "DESIGN_SHORT.md").read_text("utf-8")
    assert len(t.split()) < 1100, "1-2 pages"
    assert "DESIGN.md" in t
