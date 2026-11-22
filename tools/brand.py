"""Brand kit built from REAL data: logo, social preview (1280x640), poster "Анатомия ошибки".

The poster traces one real error of an open episode end to end: what happened, how it was injected, what
the agent sees, the UTC trap, the finding, and the grader's verdict (both a TP and the same finding without
the policy -> evidence_incomplete). Every ID, timestamp and amount is read from the episode files and the
verdicts are computed by the real grader, so the poster cannot drift from the code
(tests/test_brand.py).

    python tools/brand.py          # writes site/brand/logo.svg and site/anatomy.html
    python tools/brand.py --png    # also renders site/brand/social-preview.png and anatomy-poster.png
                                   # (needs node + playwright, only for the PNGs)
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auditenv.grader.core import EpisodeGrader  # noqa: E402

EPISODE = ROOT / "episodes" / "train" / "ep-8jyef897pe"
INVOICE = "INV-734N63R"
OUT_SITE = ROOT / "site"
OUT_BRAND = OUT_SITE / "brand"

NAVY, VIOLET, PEN, PAPER, INK, SOFT = "#1c1e54", "#533afd", "#ea2261", "#f6f9fc", "#0d253d", "#64748d"

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
          "ноября", "декабря"]

LOGO = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" role="img" aria-label="AuditEnv">
  <rect width="256" height="256" rx="56" fill="{NAVY}"/>
  <g stroke-linecap="round">
    <line x1="52" y1="74" x2="204" y2="74" stroke="#ffffff" stroke-opacity=".28" stroke-width="12"/>
    <line x1="52" y1="112" x2="176" y2="112" stroke="#ffffff" stroke-opacity=".28" stroke-width="12"/>
    <line x1="52" y1="150" x2="132" y2="150" stroke="{PEN}" stroke-width="12"/>
    <line x1="52" y1="188" x2="150" y2="188" stroke="#ffffff" stroke-opacity=".28" stroke-width="12"/>
  </g>
  <circle cx="150" cy="148" r="44" fill="{VIOLET}" fill-opacity=".22" stroke="#ffffff" stroke-width="12"/>
  <line x1="182" y1="180" x2="214" y2="212" stroke="#ffffff" stroke-width="16" stroke-linecap="round"/>
</svg>
"""


def _money(minor: int, exp: int) -> str:
    whole, frac = divmod(abs(minor), 10 ** exp)
    s = f"{whole:,}".replace(",", " ")
    return ("-" if minor < 0 else "") + (s + "," + str(frac).zfill(exp) if exp else s)


def facts(episode=EPISODE, invoice=INVOICE) -> dict:
    pub, grd = episode / "public", episode / "grader"
    manifest = json.loads((pub / "manifest.json").read_text("utf-8"))
    policy = json.loads((pub / "policy.json").read_text("utf-8"))
    inv = next(json.loads(x) for x in (pub / "invoices.jsonl").read_text("utf-8").splitlines()
               if json.loads(x)["invoice_id"] == invoice)
    rows = [r for r in csv.DictReader((pub / "ledger.csv").open(encoding="utf-8")) if r["invoice_id"] == invoice]
    truth = json.loads((grd / "truth.json").read_text("utf-8"))
    issue = next(i for i in truth["issues"] if i["affected_ids"] == [invoice])
    ev = issue["evidence_sets"][0]
    ar_row = next(r for r in rows if r["row_id"] in ev)
    off = policy["period_boundary"]["utc_offset"]
    sign = 1 if off[0] == "+" else -1
    tz = timezone(sign * timedelta(hours=int(off[1:3]), minutes=int(off[4:6])))
    local = datetime.fromisoformat(inv["issued_at"]).astimezone(tz)
    utc_day = datetime.fromisoformat(inv["issued_at"])
    exp = manifest["currencies"][manifest["base_currency"]]
    finding = {"type": issue["type"], "affected_ids": [invoice], "claimed_amount_minor": issue["expected_amount_minor"],
               "currency": issue["currency"], "evidence_ids": ev,
               "explanation": f"issued {local:%Y-%m-%d %H:%M} {policy['period_boundary']['timezone']}, after the period end"}
    without_policy = dict(finding, evidence_ids=[e for e in ev if e != "policy"])
    g = EpisodeGrader.from_dir(grd)
    verdict = g.grade({"episode_id": truth["episode_id"], "findings": [finding]}, inspection_steps=0)
    verdict2 = g.grade({"episode_id": truth["episode_id"], "findings": [without_policy]}, inspection_steps=0)
    header = (pub / "ledger.csv").read_text("utf-8").splitlines()[0]
    return {
        "episode_id": truth["episode_id"], "tz": policy["period_boundary"]["timezone"], "offset": off,
        "period_start": policy["period_boundary"]["start"], "period_end": policy["period_boundary"]["end"],
        "inclusive_end": policy["period_boundary"]["inclusive_end"], "invoice": inv, "issue": issue,
        "ar_row": ar_row, "rows": rows, "exp": exp, "ledger_header": header, "n_rows": len(rows), "finding": finding,
        "without_policy": without_policy, "amount": _money(issue["expected_amount_minor"], exp),
        "local_human": f"{local.day} {MONTHS[local.month - 1]}, {local:%H:%M:%S}",
        "utc_human": f"{utc_day.day} {MONTHS[utc_day.month - 1]}, {utc_day:%H:%M:%S}",
        "local_iso": local.isoformat(), "tp": verdict["findings"][0], "fp": verdict2["findings"][0],
        "reward_tp": verdict["reward"], "n_issues": len(truth["issues"]),
    }


def anatomy_html(f) -> str:
    e = html.escape
    inv = f["invoice"]
    keys = f["ledger_header"].split(",")
    w = max(len(k) for k in keys)
    ar = "\n".join(f"{k.ljust(w)}  {f['ar_row'][k] or '(пусто)'}" for k in keys)
    finding = json.dumps(f["finding"], ensure_ascii=False, indent=1)
    steps = [
        ("Что произошло на самом деле",
         f"Компания выписала счёт <b>{e(f['local_human'])}</b> по времени {e(f['tz'])}. Период закончился "
         f"в полночь: <code>{e(f['period_end'])}</code>, конец не включается. Значит, это выручка "
         "<b>следующего</b> периода.", None),
        ("Как ошибку внесли",
         "Генератор провёл этот счёт внутри периода и записал время в UTC. Причина записана в закрытом "
         f"<code>provenance.json</code>, эталон — в <code>truth.json</code> ({e(f['issue']['issue_id'])}).", None),
        ("Что видит агент",
         f"Документ <code>{e(inv['doc_id'])}</code> и {f['n_rows']} строк книги. Строка дебиторки:",
         e(ar)),
        ("Ловушка",
         f"Прочитать дату как написано: <b>{e(f['utc_human'])} UTC</b> — внутри периода, всё чисто. "
         f"Пересчитать в {e(f['tz'])} ({e(f['offset'])}): <b>{e(f['local_human'])}</b> — уже после границы.",
         f"{e(inv['issued_at'])}\n= {e(f['local_iso'])}"),
        ("Вывод аудитора",
         f"Тип, затронутый счёт, сумма искажения {e(f['amount'])} ₸ и доказательства: документ, строка "
         "книги и политика, которая задаёт границу периода.", e(finding)),
        ("Вердикт оценщика",
         f"<span class=ok>TP → {e(f['tp']['matched'])}</span> (это 1 из {f['n_issues']} ошибок эпизода). Тот же вывод без "
         f"<code>policy</code>: <span class=bad>FP, {e(f['fp']['reason'])}</span>. Знать ответ — не значит "
         "доказать его.", None),
    ]
    items = []
    for n, (title, body, pre) in enumerate(steps, 1):
        items.append(f"""    <li>
      <h2>{e(title)}</h2>
      <p>{body}</p>{f'''
      <pre>{pre}</pre>''' if pre else ''}
    </li>""")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Анатомия ошибки</title>
<meta name="description" content="Одна настоящая ошибка AuditEnv от события до вердикта оценщика ({e(f['episode_id'])}).">
<style>
:root {{ --paper: {PAPER}; --sheet: #ffffff; --ink: {INK}; --soft: {SOFT}; --navy: {NAVY}; --violet: {VIOLET};
  --pen: {PEN}; --rule: #dfe5ee; --code: #eef1fb; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --paper: #0b1430; --sheet: #121c44;
  --ink: #e8ecf7; --soft: #a3adc8; --rule: #26325f; --code: #1a2552; }} }}
:root[data-theme="dark"] {{ --paper: #0b1430; --sheet: #121c44; --ink: #e8ecf7; --soft: #a3adc8; --rule: #26325f; --code: #1a2552; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 17px/1.55 "Inter", system-ui, -apple-system, sans-serif; }}
main {{ max-width: 760px; margin: 0 auto; padding: 56px 16px 72px; }}
.mast {{ display: flex; gap: 18px; align-items: center; margin-bottom: 36px; }}
.mast img {{ width: 64px; height: 64px; }}
h1 {{ font: 700 clamp(40px, 7vw, 68px)/1.0 "Inter Display", "Inter", system-ui, sans-serif; letter-spacing: -0.03em; margin: 0; }}
.lede {{ color: var(--soft); max-width: 60ch; margin: 0 0 40px; }}
ol {{ list-style: none; counter-reset: s; margin: 0; padding: 0; border-left: 3px solid var(--rule); }}
li {{ counter-increment: s; position: relative; padding: 0 0 34px 34px; }}
li::before {{ content: counter(s); position: absolute; left: -17px; top: 0; width: 31px; height: 31px; border-radius: 50%;
  background: var(--navy); color: #fff; font: 600 15px/31px "Inter", sans-serif; text-align: center; }}
li:nth-child(4)::before {{ background: var(--pen); }}
li:last-child {{ padding-bottom: 0; }}
h2 {{ font: 650 22px/1.25 "Inter Display", "Inter", sans-serif; margin: 2px 0 6px; letter-spacing: -0.01em; }}
p {{ margin: 0; max-width: 64ch; }}
code, pre {{ font-family: "JetBrains Mono", "IBM Plex Mono", ui-monospace, monospace; font-size: 0.86em; }}
code {{ background: var(--code); padding: 1px 5px; border-radius: 4px; }}
pre {{ background: var(--sheet); border: 1px solid var(--rule); border-radius: 10px; padding: 14px 16px; margin: 12px 0 0;
  overflow-x: auto; white-space: pre; line-height: 1.5; }}
.ok {{ color: var(--violet); font-weight: 650; }} .bad {{ color: var(--pen); font-weight: 650; }}
footer {{ margin-top: 48px; color: var(--soft); font-size: 15px; }}
a {{ color: var(--violet); }}
@media print {{ body {{ background: #fff; }} main {{ padding-top: 24px; }} }}
</style>
</head>
<body>
<main>
  <div class="mast"><img src="brand/logo.svg" alt=""><h1>Анатомия ошибки</h1></div>
  <p class="lede">Одна настоящая ошибка из открытого эпизода <code>{e(f['episode_id'])}</code>: от события до вердикта
  оценщика. Все ID, время и суммы взяты из файлов эпизода, вердикты посчитаны настоящим оценщиком.</p>
  <ol>
{chr(10).join(items)}
  </ol>
  <footer>Собрано <code>tools/brand.py</code> из <code>episodes/train/{e(f['episode_id'])}</code>.
  Как устроены остальные типы ошибок — <a href="explain/index.html">примеры «до/после»</a>, как их взламывали —
  <a href="attacks.html">зал атак</a>.</footer>
</main>
</body>
</html>
"""


def social_html(f) -> str:
    # the real ledger rows of the invoice (receivable row first, then revenue lines)
    rev = sorted((r for r in f["rows"] if r["row_id"] != f["ar_row"]["row_id"]), key=lambda r: r["row_id"])[:4]
    rows = rev[:2] + [f["ar_row"]] + rev[2:]  # the receivable row in the middle, under the lens
    trs = "".join(
        f"<tr class='{'hit' if r['row_id'] == f['ar_row']['row_id'] else ''}'><td>{r['row_id']}</td>"
        f"<td>{r['timestamp'][11:]}</td><td>{r['account']}</td>"
        f"<td class=n>{_money(int(r['debit_minor']), f['exp']) if int(r['debit_minor']) else ''}</td>"
        f"<td class=n>{_money(int(r['credit_minor']), f['exp']) if int(r['credit_minor']) else ''}</td></tr>"
        for r in rows)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body {{ margin:0; width:1280px; height:640px; background:{NAVY}; color:#fff; font-family:"Inter",sans-serif; overflow:hidden; position:relative; }}
.l {{ position:absolute; left:72px; top:64px; width:540px; }}
.brand {{ display:flex; align-items:center; gap:14px; font:600 28px "Inter Display","Inter"; letter-spacing:-.01em; }}
.brand img {{ width:52px; height:52px; }}
h1 {{ font:700 56px/1.04 "Inter Display","Inter"; letter-spacing:-.035em; margin:40px 0 20px; text-wrap:balance; }}
.sub {{ font:400 21px/1.45 "Inter"; color:#c9cdf3; margin:0; max-width:470px; }}
.stats {{ position:absolute; left:72px; bottom:56px; display:flex; gap:40px; }}
.stats div {{ font:400 16px/1.3 "Inter"; color:#aab0e6; }} .stats b {{ display:block; font:650 30px "Inter Display"; color:#fff; letter-spacing:-.02em; }}
.sheet {{ position:absolute; left:640px; top:150px; width:600px; background:#fff; color:{INK}; border-radius:18px; padding:20px 26px;
  transform:rotate(-3deg); box-shadow:0 30px 80px rgba(0,0,0,.35); }}
table {{ border-collapse:collapse; width:100%; font:500 16px "JetBrains Mono",monospace; }}
td {{ padding:12px 6px; border-bottom:1px solid #e3e8ee; white-space:nowrap; }} td.n {{ text-align:right; }}
tr:last-child td {{ border-bottom:0; }}
tr.hit td {{ color:{PEN}; font-weight:600; }}
.lens {{ position:absolute; left:745px; top:196px; width:210px; height:210px; border-radius:50%; border:12px solid #fff;
  background:{VIOLET}; color:#fff; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center;
  box-shadow:0 20px 50px rgba(0,0,0,.35); }}
.lens .t {{ font:700 48px/1 "Inter Display"; letter-spacing:-.03em; }} .lens .d {{ font:500 16px/1.3 "Inter"; margin-top:8px; }}
.handle {{ position:absolute; left:938px; top:398px; width:110px; height:22px; background:#fff; border-radius:11px; transform:rotate(45deg); transform-origin:0 50%; }}
.note {{ position:absolute; left:1000px; top:470px; width:230px; font:400 16px/1.4 "Inter"; color:#c9cdf3; }}
.note b {{ color:#fff; font-weight:600; }}
</style></head><body>
<div class="l"><div class="brand"><img src="logo.svg">AuditEnv</div>
<h1>Найти ошибку в книге и доказать её</h1>
<p class="sub">RL‑среда и честный оценщик для ИИ‑аудитора. Офлайн, воспроизводимо, одна команда проверки.</p></div>
<div class="sheet"><table>{trs}</table></div>
<div class="handle"></div>
<div class="lens"><div class="t">00:48</div><div class="d">1 ноября<br>по Алматы</div></div>
<div class="note">В книге <b>31 октября, 19:48 UTC</b>. Период закончился в полночь по Алматы: счёт провели не в тот месяц.</div>
<div class="stats"><div><b>90/90</b>самопроверок</div><div><b>540</b>эпизодов перепроверены</div><div><b>23/23</b>мутаций оценщика пойманы</div></div>
</body></html>"""


def render_png(html_text: str, out: Path, width: int, height: int, scale: int = 1, full_page=False):
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "page.html"
        src.write_text(html_text, "utf-8")
        (Path(tmp) / "logo.svg").write_text(LOGO, "utf-8")
        (Path(tmp) / "brand").mkdir()
        (Path(tmp) / "brand" / "logo.svg").write_text(LOGO, "utf-8")
        js = f"""const {{ chromium }} = require('playwright');
(async () => {{ const b = await chromium.launch(); const p = await b.newPage({{ viewport: {{ width: {width}, height: {height} }},
  deviceScaleFactor: {scale}, colorScheme: 'light' }});
  await p.goto('file://{src}'); await p.waitForTimeout(300);
  await p.screenshot({{ path: '{out}', fullPage: {str(full_page).lower()} }}); await b.close(); }})();"""
        subprocess.run(["node", "-e", js], check=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", action="store_true")
    a = ap.parse_args(argv)
    f = facts()
    OUT_BRAND.mkdir(parents=True, exist_ok=True)
    (OUT_BRAND / "logo.svg").write_text(LOGO, "utf-8")
    (OUT_SITE / "anatomy.html").write_text(anatomy_html(f), "utf-8")
    if a.png:
        render_png(social_html(f), OUT_BRAND / "social-preview.png", 1280, 640)
        render_png(anatomy_html(f), OUT_BRAND / "anatomy-poster.png", 820, 1160, scale=2, full_page=True)
    print("brand: site/brand/logo.svg, site/anatomy.html" + (", social-preview.png, anatomy-poster.png" if a.png else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
