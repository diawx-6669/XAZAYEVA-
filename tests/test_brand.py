"""Brand kit (tools/brand.py): the poster "Анатомия ошибки" is built from a real open episode and the real grader,
so it cannot drift from the code."""

import importlib.util
from datetime import datetime

from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("brand", ROOT / "tools" / "brand.py")
brand = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(brand)
_cspec = importlib.util.spec_from_file_location("cards", ROOT / "tools" / "cards.py")
cards = importlib.util.module_from_spec(_cspec)
_cspec.loader.exec_module(cards)


def test_committed_poster_and_logo_are_up_to_date():
    f = brand.facts()
    assert (ROOT / "site" / "anatomy.html").read_text("utf-8") == brand.anatomy_html(f)
    assert (ROOT / "site" / "brand" / "logo.svg").read_text("utf-8") == brand.LOGO
    assert (ROOT / "site" / "brand" / "social-preview.png").stat().st_size > 10_000
    assert 'href="anatomy.html"' in (ROOT / "site" / "index.html").read_text("utf-8")


def test_the_poster_story_is_true():
    f = brand.facts()
    issued = datetime.fromisoformat(f["invoice"]["issued_at"])
    end = datetime.fromisoformat(f["period_end"])
    assert f["issue"]["type"] == "period_cutoff" and not f["inclusive_end"]
    assert issued >= end  # issued after the period end in local time ...
    assert f["invoice"]["issued_at"].endswith("+00:00") and issued.date() < end.date()  # ... but its UTC date is before it
    assert f["ar_row"]["account"] == "1200" and int(f["ar_row"]["debit_minor"]) == f["issue"]["expected_amount_minor"]
    assert f["tp"]["matched"] == f["issue"]["issue_id"]
    assert f["fp"]["matched"] is None and f["fp"]["reason"] == "evidence_incomplete"


def test_cards_page_is_up_to_date_and_honest():
    import json

    cs = cards.cards()
    assert (ROOT / "site" / "cards.html").read_text("utf-8") == cards.page(cs)
    assert 'href="cards.html"' in (ROOT / "site" / "index.html").read_text("utf-8")
    assert [c["error"] for c in cs].count(True) == 4 and [c["error"] for c in cs].count(False) == 4
    for c in cs:
        truth = json.loads((ROOT / "episodes").glob(f"*/{c['ep']}").__next__().joinpath("grader", "truth.json")
                           .read_text("utf-8"))
        affected = {a for i in truth["issues"] for a in i["affected_ids"]}
        first_id = c["shown"].split()[0]
        if c["error"]:
            assert any(i["issue_id"] in c["answer"] and i["type"] in c["answer"] for i in truth["issues"])
        else:
            assert first_id not in affected  # a look-alike is never an error of its episode
