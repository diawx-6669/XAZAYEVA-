"""Cards "Ошибка или ловушка?" - real look-alike pairs from the open episodes (site/cards.html).

Each pair is one injected error and the correct look-alike the generator plants against it (case section 05):
duplicate vs monthly rent, UTC cutoff trap vs a late-evening invoice inside the period, wrong FX date vs a
night-time foreign invoice, partially unapplied receipt vs a legitimate partial payment. Every value on a
card is read from the episode files; errors are taken from truth.json, look-alikes from the story tags in
provenance.json, and the arithmetic on the answer side is recomputed with the environment's own helpers.

    python tools/cards.py      # writes site/cards.html (tests/test_brand.py keeps it in sync)
"""

from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auditenv.env.data import PublicData  # noqa: E402

EPISODES = sorted(p for p in (ROOT / "episodes").glob("*/*") if (p / "grader" / "truth.json").exists())
OUT = ROOT / "site" / "cards.html"


def _load(ep):
    data = PublicData.from_dir(ep / "public")
    truth = json.loads((ep / "grader" / "truth.json").read_text("utf-8"))
    prov = json.loads((ep / "grader" / "provenance.json").read_text("utf-8"))
    return data, truth, prov


def _money(minor: int, exp: int) -> str:
    whole, frac = divmod(abs(int(minor)), 10 ** exp)
    s = f"{whole:,}".replace(",", " ")
    return ("-" if int(minor) < 0 else "") + (s + "," + str(frac).zfill(exp) if exp else s)


def _rows_for(data, key, value):
    return [r for r in data.ledger if r.get(key) == value]


def _variant(prov, issue_id):
    return next((m.get("variant") for m in prov["mutations"] if m.get("issue_id") == issue_id), None)


def _tagged(prov, tag):
    return [e for e in prov["story"]["events"] if tag in e.get("tags", [])]


def _first(fn):
    for ep in EPISODES:
        out = fn(ep, *_load(ep))
        if out:
            return out
    raise LookupError(fn.__name__)


def _lines(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} строка"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} строки"
    return f"{n} строк"


def _inv_line(data, inv):
    exp = data.exponents[inv["currency"]]
    sp = inv["line_items"][0]["service_period"]
    return (f"{inv['invoice_id']}  {inv['entity_id']}  {inv['issued_at']}\n"
            f"  {_lines(len(inv['line_items']))}, service_period {sp}, итого {_money(inv['total_minor'], exp)} {inv['currency']}")


# ------------------------------------------------------------------ pairs
def duplicate(ep, data, truth, prov):
    for i in truth["issues"]:
        if i["type"] == "duplicate_invoice" and _variant(prov, i["issue_id"]) in ("copy", "paid_twice"):
            dup = data.invoice_by_id[i["affected_ids"][0]]
            key = sorted((li["description"], li["amount_minor"]) for li in dup["line_items"])
            orig = next(x for x in data.invoices if x is not dup and x["entity_id"] == dup["entity_id"]
                        and sorted((li["description"], li["amount_minor"]) for li in x["line_items"]) == key)
            return {"ep": ep.name, "error": True, "title": "Два одинаковых счёта одному клиенту",
                    "shown": _inv_line(data, orig) + "\n" + _inv_line(data, dup),
                    "answer": f"Ошибка: duplicate_invoice ({i['issue_id']}). Те же клиент, строки и service_period, "
                              f"разница в датах {abs((data.local(dup['issued_at']).date() - data.local(orig['issued_at']).date()).days)} дн. "
                              f"Оба счёта проведены, выручка завышена на {_money(i['expected_amount_minor'], data.exponents[data.base])} {data.base}.",
                    "rule": "Дубль — это та же услуга за тот же период, выставленная дважды."}
    return None


def rent(ep, data, truth, prov):
    ids = [e["invoice_id"] for e in _tagged(prov, "recurring_rent")]
    invs = [data.invoice_by_id[x] for x in ids if x in data.invoice_by_id]
    for a in invs:
        for b in invs:
            if a is not b and a["entity_id"] == b["entity_id"] and a["total_minor"] == b["total_minor"] and \
                    a["line_items"][0]["service_period"] < b["line_items"][0]["service_period"]:
                return {"ep": ep.name, "error": False, "title": "Два одинаковых счёта одному клиенту",
                        "shown": _inv_line(data, a) + "\n" + _inv_line(data, b),
                        "answer": f"Ловушка: ежемесячная аренда. Сумма та же, но service_period разный "
                                  f"({a['line_items'][0]['service_period']} и {b['line_items'][0]['service_period']}): "
                                  "это две разные услуги.",
                        "rule": "Совпадение суммы и клиента — повод проверить период услуги, а не обвинение."}
    return None


def cutoff(ep, data, truth, prov):
    for i in truth["issues"]:
        if i["type"] == "period_cutoff" and _variant(prov, i["issue_id"]) == "utc_trap":
            inv = data.invoice_by_id[i["affected_ids"][0]]
            loc = data.local(inv["issued_at"])
            return {"ep": ep.name, "error": True, "title": "Счёт в последний вечер периода",
                    "shown": f"{_inv_line(data, inv)}\nграница периода: {data.policy['period_boundary']['end']} (не включая)\n"
                             f"проведён в этом периоде",
                    "answer": f"Ошибка: period_cutoff ({i['issue_id']}). По местному времени "
                              f"({data.manifest['timezone']}) счёт выписан {loc:%Y-%m-%d %H:%M}, уже после границы.",
                    "rule": "Дату сравнивают с границей периода в часовом поясе компании, а не в UTC."}
    return None


def boundary(ep, data, truth, prov):
    for e in _tagged(prov, "boundary_end"):
        inv = data.invoice_by_id.get(e.get("invoice_id"))
        if inv and inv["issued_at"].endswith("+00:00"):
            loc = data.local(inv["issued_at"])
            return {"ep": ep.name, "error": False, "title": "Счёт в последний вечер периода",
                    "shown": f"{_inv_line(data, inv)}\nграница периода: {data.policy['period_boundary']['end']} (не включая)\n"
                             f"проведён в этом периоде",
                    "answer": f"Ловушка: по местному времени ({data.manifest['timezone']}) счёт выписан "
                              f"{loc:%Y-%m-%d %H:%M} — до полуночи, внутри периода. Проведён правильно.",
                    "rule": "Поздний час — не ошибка. Ошибка — только если местное время за границей."}
    return None


def fx_error(ep, data, truth, prov):
    for i in truth["issues"]:
        if i["type"] == "fx_rate" and _variant(prov, i["issue_id"]) in ("adjacent_day", "utc_date") and \
                i["affected_ids"][0] in data.invoice_by_id:
            inv = data.invoice_by_id[i["affected_ids"][0]]
            fx_id = next(x for x in i["evidence_sets"][0] if x.startswith("fx:"))
            ar = next(r for r in _rows_for(data, "invoice_id", inv["invoice_id"]) if r["account"] == "1200")
            exp = data.exponents[data.base]
            return {"ep": ep.name, "error": True, "title": "Валютный счёт и его проводка",
                    "shown": f"{_inv_line(data, inv)}\nместная дата: {data.local(inv['issued_at']).date()}\n"
                             f"проведено в {data.base}: {_money(int(ar['debit_minor']), exp)} (строка {ar['row_id']})",
                    "answer": f"Ошибка: fx_rate ({i['issue_id']}). По политике нужен курс {fx_id} = "
                              f"{data.fx_by_id[fx_id]['rate']}; проведено по курсу другого дня, искажение "
                              f"{_money(i['expected_amount_minor'], exp)} {data.base}.",
                    "rule": "Курс — на местную дату операции; нет курса — последний рабочий день до неё."}
    return None


def night_fx(ep, data, truth, prov):
    for e in _tagged(prov, "night_fx"):
        inv = data.invoice_by_id.get(e.get("invoice_id"))
        if not inv:
            continue
        loc = data.local(inv["issued_at"]).date()
        rate, rec = data.correct_rate(inv["issued_at"], inv["currency"])
        ar = next(r for r in _rows_for(data, "invoice_id", inv["invoice_id"]) if r["account"] == "1200")
        if rec and inv["issued_at"][:10] != loc.isoformat() and \
                int(ar["debit_minor"]) == data.to_base(inv["total_minor"], inv["currency"], rate):
            exp = data.exponents[data.base]
            return {"ep": ep.name, "error": False, "title": "Валютный счёт и его проводка",
                    "shown": f"{_inv_line(data, inv)}\nместная дата: {loc}\n"
                             f"проведено в {data.base}: {_money(int(ar['debit_minor']), exp)} (строка {ar['row_id']})",
                    "answer": f"Ловушка: по UTC это {inv['issued_at'][:10]}, но курс берётся на местную дату {loc}: "
                              f"{rec['fx_id']} = {rate}. Пересчёт даёт ровно проведённую сумму.",
                    "rule": "Ночной валютный документ — проверка, что курс взят по местной дате, а не по UTC."}
    return None


def alloc(ep, data, truth, prov):
    for i in truth["issues"]:
        single = sum(1 for j in truth["issues"] if j["affected_ids"] == i["affected_ids"]) == 1
        if i["type"] == "payment_allocation" and _variant(prov, i["issue_id"]) == "partial" and single:
            p = data.payment_by_id[i["affected_ids"][0]]
            rows = _rows_for(data, "payment_id", p["payment_id"])
            exp = data.exponents[data.base]
            lines = "\n".join(f"  {r['row_id']}  {r['account']}  Dr {_money(int(r['debit_minor']), exp)}  "
                              f"Cr {_money(int(r['credit_minor']), exp)}  invoice {r['invoice_id'] or '-'}" for r in rows)
            return {"ep": ep.name, "error": True, "title": "Платёж закрыл счёт не полностью",
                    "shown": f"{p['payment_id']}  {p['timestamp']}  {_money(p['amount_minor'], data.exponents[p['currency']])} "
                             f"{p['currency']}  ссылки: {', '.join(p['invoice_refs'] or [])}\n{lines}",
                    "answer": f"Ошибка: payment_allocation ({i['issue_id']}). Платёж ссылается на счёт, но часть денег "
                              f"осталась на 2400 «Unapplied Cash»: {_money(i['expected_amount_minor'], exp)} {data.base}. "
                              "Дебиторка завышена на эту сумму.",
                    "rule": "Деньги со ссылкой на счёт должны уменьшать 1200, а не висеть на 2400."}
    return None


def partial_open(ep, data, truth, prov):
    for e in _tagged(prov, "partial_open"):
        p = data.payment_by_id.get(e.get("payment_id"))
        if not p or not p["invoice_refs"]:
            continue
        inv = data.invoice_by_id[p["invoice_refs"][0]]
        rows = _rows_for(data, "payment_id", p["payment_id"])
        if inv["currency"] != p["currency"] or any(r["account"] == "2400" for r in rows):
            continue
        exp = data.exponents[data.base]
        lines = "\n".join(f"  {r['row_id']}  {r['account']}  Dr {_money(int(r['debit_minor']), exp)}  "
                          f"Cr {_money(int(r['credit_minor']), exp)}  invoice {r['invoice_id'] or '-'}" for r in rows)
        return {"ep": ep.name, "error": False, "title": "Платёж закрыл счёт не полностью",
                "shown": f"{p['payment_id']}  {p['timestamp']}  {_money(p['amount_minor'], data.exponents[p['currency']])} "
                         f"{p['currency']}  ссылки: {', '.join(p['invoice_refs'])}\n{lines}",
                "answer": f"Ловушка: законная частичная оплата. Счёт {inv['invoice_id']} на "
                          f"{_money(inv['total_minor'], data.exponents[inv['currency']])} {inv['currency']}; всё "
                          "полученное ушло на 1200, остаток честно открыт у клиента. На 2400 ничего нет.",
                "rule": "Открытый остаток — не ошибка. Ошибка — деньги, которые пришли и не разнесены."}
    return None


PAIRS = [(duplicate, rent), (boundary, cutoff), (fx_error, night_fx), (partial_open, alloc)]


def cards():
    return [_first(fn) for pair in PAIRS for fn in pair]


def page(cs) -> str:
    e = html.escape
    items = []
    for n, c in enumerate(cs, 1):
        kind = "error" if c["error"] else "trap"
        verdict = "Ошибка" if c["error"] else "Ловушка"
        items.append(f"""  <article class="card">
    <h2>{e(c['title'])}</h2>
    <pre>{e(c['shown'])}</pre>
    <details>
      <summary>Ошибка или ловушка? Показать ответ</summary>
      <p class="{kind}"><b>{verdict}.</b> {e(c['answer'].split(': ', 1)[1])}</p>
      <p class="rule">{e(c['rule'])}</p>
      <p class="src">Эпизод <code>{e(c['ep'])}</code></p>
    </details>
  </article>""")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ошибка или ловушка</title>
<meta name="description" content="Восемь настоящих записей из открытых эпизодов AuditEnv: четыре ошибки и четыре корректных двойника.">
<style>
:root {{ --paper: #f6f9fc; --sheet: #ffffff; --ink: #0d253d; --soft: #64748d; --rule: #dfe5ee; --violet: #533afd;
  --pen: #ea2261; --navy: #1c1e54; --code: #eef1fb; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --paper: #0b1430; --sheet: #121c44; --ink: #e8ecf7;
  --soft: #a3adc8; --rule: #26325f; --code: #1a2552; --violet: #9d8cff; }} }}
:root[data-theme="dark"] {{ --paper: #0b1430; --sheet: #121c44; --ink: #e8ecf7; --soft: #a3adc8; --rule: #26325f; --code: #1a2552; --violet: #9d8cff; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 17px/1.55 "Inter", system-ui, -apple-system, sans-serif; }}
main {{ max-width: 860px; margin: 0 auto; padding: 56px 16px 72px; }}
.mast {{ display: flex; gap: 16px; align-items: center; }} .mast img {{ width: 56px; height: 56px; }}
h1 {{ font: 700 clamp(36px, 6vw, 58px)/1.02 "Inter Display", "Inter", system-ui, sans-serif; letter-spacing: -0.03em; margin: 0; }}
.lede {{ color: var(--soft); max-width: 62ch; margin: 22px 0 36px; }}
.card {{ background: var(--sheet); border: 1px solid var(--rule); border-radius: 14px; padding: 22px 22px 18px; margin: 0 0 18px; }}
.card:nth-child(2n) {{ margin-bottom: 44px; }}
h2 {{ font: 650 20px/1.3 "Inter Display", "Inter", sans-serif; margin: 0 0 12px; }}
pre {{ font: 14px/1.6 "JetBrains Mono", "IBM Plex Mono", ui-monospace, monospace; background: var(--code); border-radius: 8px;
  padding: 12px 14px; margin: 0 0 14px; overflow-x: auto; white-space: pre; }}
code {{ font-family: "JetBrains Mono", ui-monospace, monospace; font-size: .86em; }}
summary {{ cursor: pointer; color: var(--violet); font-weight: 600; }}
summary:focus-visible {{ outline: 3px solid var(--violet); outline-offset: 3px; border-radius: 4px; }}
details p {{ margin: 10px 0 0; max-width: 70ch; }}
.error b {{ color: var(--pen); }} .trap b {{ color: var(--violet); }}
.rule {{ font-weight: 500; }} .src {{ color: var(--soft); font-size: 14px; }}
a {{ color: var(--violet); }}
</style>
</head>
<body>
<main>
  <div class="mast"><img src="brand/logo.svg" alt=""><h1>Ошибка или ловушка?</h1></div>
  <p class="lede">Восемь настоящих записей из открытых эпизодов. Каждая пара выглядит одинаково: одна — внесённая
  ошибка, другая — корректный «двойник», которого генератор кладёт рядом, чтобы поверхностные признаки не работали.
  Решите сами, потом откройте ответ.</p>
{chr(10).join(items)}
  <p class="src">Собрано <code>tools/cards.py</code>: ошибки — из <code>truth.json</code>, двойники — по тегам истории в
  <code>provenance.json</code>, проверки сумм — функциями самой среды. Одна ошибка целиком — <a href="anatomy.html">анатомия ошибки</a>.</p>
</main>
</body>
</html>
"""


def main() -> int:
    OUT.write_text(page(cards()), "utf-8")
    print("cards: site/cards.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
