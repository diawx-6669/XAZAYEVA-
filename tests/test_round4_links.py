"""B3: every relative Markdown link in README*.md and docs/*.md points to an existing file, and every
#anchor to an existing heading (GitHub slug rules). External links are not fetched (offline)."""

import re
import unicodedata

import pytest

from auditenv.paths import ROOT

DOCS = sorted([p.relative_to(ROOT).as_posix() for p in [*ROOT.glob("README*.md"), *(ROOT / "docs").glob("*.md"),
                                                         *(ROOT / "reports").glob("*.md")]])
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")


def slug(heading: str) -> str:
    h = re.sub(r"<[^>]+>", "", heading).strip().lower()
    h = "".join(ch for ch in h if ch in " -_" or unicodedata.category(ch)[0] in "LN")
    return h.replace(" ", "-")


def anchors(path):
    text = re.sub(r"```.*?```", "", path.read_text("utf-8"), flags=re.S)
    out, seen = set(), {}
    for m in re.finditer(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.M):
        s = slug(m.group(1))
        n = seen.get(s, 0)
        out.add(s if n == 0 else f"{s}-{n}")
        seen[s] = n + 1
    return out


def broken(src):
    text = re.sub(r"```.*?```", "", src.read_text("utf-8"), flags=re.S)
    bad = []
    for target in LINK.findall(text):
        if re.match(r"^[a-z]+:", target) or target.startswith("mailto:"):
            continue
        path, _, frag = target.partition("#")
        dest = (src.parent / path).resolve() if path else src
        if not dest.exists():
            bad.append(f"{target}: no such file")
        elif frag and dest.suffix == ".md" and frag not in anchors(dest):
            bad.append(f"{target}: no heading #{frag}")
    return bad


@pytest.mark.parametrize("doc", DOCS)
def test_relative_links_resolve(doc):
    bad = broken(ROOT / doc)
    assert not bad, f"{doc}: {bad}"


def test_positive_control(tmp_path):
    (tmp_path / "a.md").write_text("# Заголовок\n[ok](#заголовок) [bad](#нет) [file](missing.md) [ext](https://x.org)\n", "utf-8")
    assert broken(tmp_path / "a.md") == ["#нет: no heading #нет", "missing.md: no such file"]


def test_slug_rules():
    assert slug("Проверка за 5 минут") == "проверка-за-5-минут"
    assert slug("A2: `docs` (тест)") == "a2-docs-тест"
