"""A23: site/attacks.html is generated from the committed reports, lists every attack, works offline and
is linked from site/index.html; no attack beats oracle."""

import importlib.util
import json
import re

from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("build_attacks", ROOT / "tools" / "build_attacks.py")
ba = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ba)


def test_attacks_page_up_to_date_and_complete():
    page = (ROOT / "site" / "attacks.html").read_text("utf-8")
    assert page == ba.build(), "run: python tools/build_attacks.py"
    sc = json.loads((ROOT / "reports" / "selfcheck.json").read_text("utf-8"))
    for r in sc["diagnostics"]:
        assert f"<code>{r['policy']}</code>" in page, r["policy"]
    assert "НЕ хуже oracle" not in page


def test_attacks_page_offline_and_linked():
    page = (ROOT / "site" / "attacks.html").read_text("utf-8")
    assert "<script" not in page and not re.search(r"(src|href)=['\"]https?://", page)
    index = (ROOT / "site" / "index.html").read_text("utf-8")
    assert 'href="attacks.html"' in index and 'href="explain/index.html"' in index
