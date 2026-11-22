"""A17: `python -m auditenv explain <episode_dir> [issue_id]` - a static "before / after" HTML page for
every injected error of an OPEN episode, built from grader/provenance.json.

GRADER-SIDE TOOL: it reads grader/ (truth and provenance). It refuses salted (closed) episodes and must
never be given to an agent. Output is a single offline HTML file (no scripts, no network).

For each issue: the documents and ledger rows before and after the mutation (changed cells highlighted,
added/removed rows marked), every evidence set with the public record behind each ID, and the amount
recomputed from the before/after snapshots and compared with truth.expected_amount_minor.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from .env.data import PublicData
from .paths import ROOT

ROW_COLS = ["row_id", "timestamp", "account", "debit_minor", "credit_minor", "currency", "entity_id", "invoice_id",
            "payment_id"]


def recompute(issue: dict, mutation: dict) -> tuple[int, str]:
    """Distortion in base minor units from the snapshots alone, and the formula used."""
    aff = issue["affected_ids"][0]
    before = [r for s in mutation["before"] for r in s["rows"]]
    after = [r for s in mutation["after"] for r in s["rows"]]
    t = issue["type"]
    if t in ("duplicate_invoice", "period_cutoff"):
        v = sum(r["debit_minor"] for r in after if r["account"] == "1200" and r["invoice_id"] == aff and not r["payment_id"])
        return v, f"Σ Dr 1200 строк счёта {aff} после мутации"
    if t == "payment_allocation":
        f = lambda rows: sum(r["credit_minor"] for r in rows if r["account"] == "2400" and r["payment_id"] == aff)  # noqa: E731
        return f(after) - f(before), f"Cr 2400 платежа {aff}: после − до"
    net = {}
    for sign, rows in ((-1, before), (1, after)):
        for r in rows:
            net[r["account"]] = net.get(r["account"], 0) + sign * (r["debit_minor"] - r["credit_minor"])
    acc = max(net, key=lambda a: abs(net[a])) if net else "?"
    return abs(net.get(acc, 0)), f"max по счетам |Δ сальдо| (счёт {acc})"


def _describe(pid: str, data: PublicData) -> str:
    if pid == "policy":
        p = data.policy
        return f"policy: курс — {p.get('fx_rate_date')}, нет курса — {p.get('fx_missing_rate')}, период {p['period_boundary']['start']} … {p['period_boundary']['end']}"
    if pid in data.ledger_by_id:
        r = data.ledger_by_id[pid]
        return f"ledger {r['timestamp']} счёт {r['account']} Dr {r['debit_minor']} Cr {r['credit_minor']} inv={_fmt(r['invoice_id'])} pay={_fmt(r['payment_id'])}"
    if pid in data.fx_by_id:
        r = data.fx_by_id[pid]
        return f"fx {r['date']} {r['source_currency']}→{r['target_currency']} = {r['rate']}"
    if pid in data.doc_by_id:
        d = data.doc_by_id[pid]
        if "invoice_id" in d:
            return f"счёт {d['invoice_id']} от {d['issued_at']}, {d['currency']} {d['total_minor']}, клиент {d['entity_id']}"
        return f"платёж {d['payment_id']} от {d['timestamp']}, {d['currency']} {d['amount_minor']}, ссылки {d['invoice_refs']}"
    return "— (нет в открытых данных!)"


def _fmt(v) -> str:
    return "null" if v is None else str(v)


def _cell(a, b) -> str:
    if a == b:
        return f"<td>{html.escape(_fmt(a))}</td>"
    return f'<td class="chg"><s>{html.escape(_fmt(a))}</s> → <b>{html.escape(_fmt(b))}</b></td>'


def _rows_table(mut: dict) -> str:
    before = {r["row_id"]: r for s in mut["before"] for r in s["rows"]}
    after = {r["row_id"]: r for s in mut["after"] for r in s["rows"]}
    ids = list(dict.fromkeys(list(before) + list(after)))
    out = ["<table><tr><th>статус</th>" + "".join(f"<th>{c}</th>" for c in ROW_COLS) + "</tr>"]
    for rid in ids:
        b, a = before.get(rid), after.get(rid)
        if b and a:
            st = "изменена" if a != b else "без изменений"
            cells = "".join(_cell(b.get(c), a.get(c)) for c in ROW_COLS)
        elif a:
            st, cells = "добавлена", "".join(f'<td class="add">{html.escape(_fmt(a.get(c)))}</td>' for c in ROW_COLS)
        else:
            st, cells = "удалена", "".join(f'<td class="del">{html.escape(_fmt(b.get(c)))}</td>' for c in ROW_COLS)
        out.append(f'<tr><td class="st">{st}</td>{cells}</tr>')
    return "\n".join(out) + "</table>"


def _docs_table(mut: dict) -> str:
    out = []
    n = max(len(mut["before"]), len(mut["after"]))
    for k in range(n):
        b = (mut["before"][k] if k < len(mut["before"]) else {}).get("document") or {}
        a = (mut["after"][k] if k < len(mut["after"]) else {}).get("document") or {}
        if not a and not b:
            continue
        keys = list(dict.fromkeys(list(b) + list(a)))
        rows = []
        for key in keys:
            bv = json.dumps(b.get(key), ensure_ascii=False) if key in b else "—"
            av = json.dumps(a.get(key), ensure_ascii=False) if key in a else "—"
            cls = ' class="chg"' if bv != av else ""
            rows.append(f"<tr><th>{key}</th><td{cls}>{html.escape(bv)}</td><td{cls}>{html.escape(av)}</td></tr>")
        title = a.get("doc_id") or b.get("doc_id")
        out.append(f"<h4>Документ {html.escape(str(title))}</h4><table class='doc'><tr><th>поле</th><th>до</th><th>после</th></tr>"
                   + "".join(rows) + "</table>")
    return "\n".join(out) or "<p class='muted'>Документы не менялись.</p>"


CSS = """
:root{--paper:#f6f9fc;--sheet:#fff;--rule:#e3e8ee;--ink:#0d253d;--soft:#64748d;--pen:#ea2261;--ok:#4434d4;--mark:#fff3b0;--add:#e3f7e8;--del:#fde4ea}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#0b1430;--sheet:#121c44;--rule:#232f5c;--ink:#e8ecf8;--soft:#9aa6c8;--pen:#ff5c8e;--ok:#9c94ff;--mark:#5a4a12;--add:#123d24;--del:#4a1426;color-scheme:dark}}
:root[data-theme="dark"]{--paper:#0b1430;--sheet:#121c44;--rule:#232f5c;--ink:#e8ecf8;--soft:#9aa6c8;--pen:#ff5c8e;--ok:#9c94ff;--mark:#5a4a12;--add:#123d24;--del:#4a1426;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{margin:36px 0 8px;font-size:20px}
.warn{border-left:4px solid var(--pen);background:var(--sheet);padding:10px 14px;margin:16px 0}.muted{color:var(--soft)}
section{background:var(--sheet);border:1px solid var(--rule);border-radius:12px;padding:16px;margin:18px 0}
table{border-collapse:collapse;width:100%;font:12.5px/1.4 ui-monospace,Menlo,Consolas,monospace;margin:8px 0}
.scroll{overflow-x:auto}th,td{border-bottom:1px solid var(--rule);padding:4px 6px;text-align:left;vertical-align:top;white-space:nowrap}
table.doc td{white-space:normal;word-break:break-word}td.chg{background:var(--mark)}td.add{background:var(--add)}td.del{background:var(--del)}
td.st{color:var(--soft)}.ok{color:var(--ok);font-weight:600}.bad{color:var(--pen);font-weight:600}code{font-family:ui-monospace,Menlo,monospace}
ul.ev li{margin:2px 0}.pill{display:inline-block;border:1px solid var(--rule);border-radius:999px;padding:0 8px;font-size:12px;margin-left:6px}
"""


def render(ep_dir: Path, only: str | None = None) -> str:
    ep_dir = Path(ep_dir)
    truth = json.loads((ep_dir / "grader" / "truth.json").read_text("utf-8"))
    prov = json.loads((ep_dir / "grader" / "provenance.json").read_text("utf-8"))
    if prov.get("seed_salted"):
        raise SystemExit("explain: refusing a salted (closed) episode - this grader tool is for open episodes only")
    data = PublicData.from_dir(ep_dir / "public")
    muts = {m["issue_id"]: m for m in prov["mutations"]}
    issues = [i for i in truth["issues"] if only in (None, i["issue_id"])]
    if only and not issues:
        raise SystemExit(f"explain: no issue {only} in {truth['episode_id']}")
    m = data.manifest
    parts = [f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
             f"<title>Explain {html.escape(truth['episode_id'])}</title><style>{CSS}</style></head><body><main>",
             f"<h1>Разбор эпизода <code>{html.escape(truth['episode_id'])}</code></h1>",
             f"<p class='muted'>База {m['base_currency']}, пояс {m['timezone']}, период {m['period_start']} … {m['period_end']}; "
             f"{m['counts']['ledger']} проводок, {m['counts']['invoices']} счетов, {m['counts']['payments']} платежей; "
             f"ошибок: {len(truth['issues'])}.</p>",
             "<div class='warn'><b>Инструмент оценщика.</b> Страница построена по закрытым <code>grader/truth.json</code> и "
             "<code>grader/provenance.json</code> открытого эпизода. Агенту её показывать нельзя; для закрытых (солёных) "
             "эпизодов команда отказывается работать.</div>"]
    if not issues:
        parts.append("<section><h2>Чистая книга</h2><p>Эталон пуст: ни одной мутации. Правильный ответ — пустой список выводов.</p></section>")
    ok_all = True
    for iss in issues:
        mut = muts[iss["issue_id"]]
        val, formula = recompute(iss, mut)
        ok = val == iss["expected_amount_minor"]
        ok_all &= ok
        parts.append(f"<section id='{iss['issue_id']}'><h2>{iss['issue_id']}: {iss['type']} "
                     f"<span class='pill'>{html.escape(mut.get('variant', '?'))}</span>"
                     f"<span class='pill'>порядок мутации {mut.get('order', '?')}</span></h2>")
        parts.append(f"<p>Затронут: <code>{', '.join(iss['affected_ids'])}</code>. Эталонная сумма: "
                     f"<b>{iss['expected_amount_minor']}</b> {iss['currency']} (мин. ед.). Пересчёт по снимкам до/после "
                     f"({html.escape(formula)}): <b>{val}</b> — "
                     + ("<span class='ok'>совпадает</span>" if ok else "<span class='bad'>НЕ совпадает</span>") + ".</p>")
        if mut.get("detail"):
            parts.append(f"<p class='muted'>Детали мутации: <code>{html.escape(json.dumps(mut['detail'], ensure_ascii=False))}</code></p>")
        parts.append("<h3>Документы: до → после</h3><div class='scroll'>" + _docs_table(mut) + "</div>")
        parts.append("<h3>Проводки: до → после</h3><div class='scroll'>" + _rows_table(mut) + "</div>")
        parts.append("<h3>Наборы доказательств</h3><p class='muted'>TP требует, чтобы один набор целиком входил в evidence_ids. "
                     "Справа — что агент увидит по этому ID через инструменты.</p>")
        for k, s in enumerate(iss["evidence_sets"], 1):
            parts.append(f"<p><b>Набор {k}</b> ({len(s)} ID)</p><ul class='ev'>"
                         + "".join(f"<li><code>{html.escape(x)}</code> — {html.escape(_describe(x, data))}</li>" for x in s)
                         + "</ul>")
        parts.append("</section>")
    try:
        shown = ep_dir.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        shown = ep_dir.name
    parts.append(f"<p class='muted'>Сгенерировано <code>python -m auditenv explain {html.escape(shown)}</code>. "
                 f"Все суммы пересчитаны: {'да' if ok_all else 'НЕТ'}.</p></main></body></html>\n")
    return "\n".join(parts)


EXAMPLES = ["ep-vk7pc3rd7r", "ep-4qcfb8dahb", "ep-xt9h93jnn2"]


def write_examples(root) -> list:
    """site/explain/: the three dev examples + an index page (regenerate: python -m auditenv explain --examples)."""
    out_dir = Path(root) / "site" / "explain"
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for eid in EXAMPLES:
        d = Path(root) / "episodes" / "dev" / eid
        (out_dir / f"{eid}.html").write_text(render(d), "utf-8")
        truth = json.loads((d / "grader" / "truth.json").read_text("utf-8"))
        items.append((eid, truth))
    lis = "".join(f"<li><a href='{eid}.html'><code>{eid}</code></a> — {len(t['issues'])} ошибок: "
                  + ", ".join(html.escape(i['type']) for i in t["issues"]) + "</li>" for eid, t in items)
    idx = (f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
           f"<title>Explain examples</title><style>{CSS}</style></head><body><main><h1>Разбор ошибок «до/после»</h1>"
           "<p>Три открытых dev‑эпизода. Для каждой внесённой ошибки — документы и проводки до и после мутации, "
           "подсвеченные изменения, наборы доказательств и сумма, пересчитанная по снимкам и сверенная с эталоном.</p>"
           "<div class='warn'><b>Инструмент оценщика</b> (читает <code>grader/</code>); только для открытых эпизодов.</div>"
           f"<section><ul>{lis}</ul></section><p class='muted'>Собрать заново: <code>python -m auditenv explain --examples</code>. "
           "Любой эпизод: <code>python -m auditenv explain episodes/dev/&lt;id&gt; [ISS-001] --out page.html</code>. "
           "<a href='../index.html'>← на главную</a></p></main></body></html>\n")
    (out_dir / "index.html").write_text(idx, "utf-8")
    return [out_dir / f"{e}.html" for e in EXAMPLES] + [out_dir / "index.html"]


def main(episode_dir: str, issue_id: str | None, out: str | None) -> int:
    text = render(Path(episode_dir), issue_id)
    eid = json.loads((Path(episode_dir) / "public" / "manifest.json").read_text("utf-8"))["episode_id"]
    path = Path(out or f"{eid}{'_' + issue_id if issue_id else ''}.html")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    bad = "НЕ совпадает" in text
    print(f"explain: {eid} -> {path}" + (" (AMOUNT MISMATCH)" if bad else ""))
    return 1 if bad else 0
