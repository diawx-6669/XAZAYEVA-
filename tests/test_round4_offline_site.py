"""B4: the static site works offline - no scripts, images, frames or data loaded from the network.

Allowed: plain hyperlinks a reader may click (<a href="https://...">), the SVG namespace, and the optional
Google Fonts stylesheet of site/index.html (the page declares system-font fallbacks, so offline it only
changes the typeface). Everything else (script src, img src, iframe, fetch/XMLHttpRequest, @import) fails."""

import re

import pytest

from auditenv.paths import ROOT

PAGES = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "site").rglob("*.html"))
FONT_HOSTS = ("https://fonts.googleapis.com", "https://fonts.gstatic.com")


def network_loads(html: str) -> list:
    bad = []
    for m in re.finditer(r"<(script|img|iframe|source|video|audio|embed|object)\b[^>]*\b(?:src|data)=['\"](https?:)?//", html, re.I):
        bad.append(m.group(0)[:80])
    for m in re.finditer(r"<link\b[^>]*href=['\"](https?://[^'\"]+)", html, re.I):
        if not m.group(1).startswith(FONT_HOSTS):
            bad.append(m.group(0)[:80])
    for m in re.finditer(r"\b(fetch\s*\(|XMLHttpRequest|new\s+WebSocket|@import\s+url\(\s*['\"]?https?:)", html):
        bad.append(m.group(0))
    return bad


@pytest.mark.parametrize("page", PAGES)
def test_page_loads_nothing_from_the_network(page):
    html = (ROOT / page).read_text("utf-8")
    assert network_loads(html) == [], page
    if "fonts.googleapis.com" in html:
        assert re.search(r"(--body|--display|font-family)\s*:[^;]*(system-ui|sans-serif)", html), "web fonts need a system fallback"


def test_positive_control():
    assert network_loads('<script src="https://cdn.x/y.js"></script>') and network_loads("fetch('/api')")
    assert network_loads('<link rel="stylesheet" href="https://cdn.x/a.css">')
    assert not network_loads('<a href="https://github.com/x">repo</a><link href="https://fonts.googleapis.com/css2">')
