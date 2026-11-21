"""A23: site/attacks.html - the "hall of attacks": every attack we ran against the reward, the matcher,
the contract and the isolation, with its measured result. Static, offline (no scripts, no network).

Sources (all committed): reports/selfcheck.json (attack policies on 20 episodes), reports/exploit_search.json
(automatic CEM search without the answer key), reports/jury_sim.md (black-box jury simulation, section 5b),
docs/FAILURES.md (vulnerabilities found and closed, each with a guard test), reports/reward_exhaustive.md.

    python tools/build_attacks.py
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "attacks.html"

WHAT = {
    "attack:twins": "один верный вывод 30 раз",
    "attack:type_bruteforce": "знает ID из эталона и шлёт все 4 типа",
    "attack:amount_bruteforce": "сумма X−10 … X+10",
    "attack:guess_ids": "придумывает ID без чтения записей",
    "attack:evidence_spam": "10 случайных доказательств",
    "attack:junk_explanation": "верный ответ + мусорный explanation",
    "attack:persuasive_wrong": "неверный ответ + убедительный explanation",
    "attack:wrong_currency": "верная сумма в валюте документа",
    "attack:all_types_all_docs": "каждый документ под каждым типом",
    "attack:empty": "мгновенный пустой ответ",
    "attack:cem_best": "лучшая стратегия автопоиска (CEM) без эталона",
    "random_explorer": "базовая: случайные действия",
    "simple_reconcile": "базовая: честный скриптовый аудитор",
    "flag_all": "базовая: обвинить всё",
    "oracle": "базовая: знает эталон, 1 шаг",
    "oracle_observing": "знает эталон и открывает все доказательства",
}

CSS = """
:root{--paper:#f6f9fc;--sheet:#fff;--rule:#e3e8ee;--ink:#0d253d;--soft:#64748d;--pen:#ea2261;--ok:#4434d4;--bar:#533afd;--neg:#ea2261}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#0b1430;--sheet:#121c44;--rule:#232f5c;--ink:#e8ecf8;--soft:#9aa6c8;--pen:#ff5c8e;--ok:#9c94ff;--bar:#7a6bff;--neg:#ff5c8e;color-scheme:dark}}
:root[data-theme="dark"]{--paper:#0b1430;--sheet:#121c44;--rule:#232f5c;--ink:#e8ecf8;--soft:#9aa6c8;--pen:#ff5c8e;--ok:#9c94ff;--bar:#7a6bff;--neg:#ff5c8e;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:28px 16px 64px}h1{font-size:30px;margin:0 0 6px}h2{margin:40px 0 6px;font-size:21px}
.lede{color:var(--soft);max-width:760px}section{background:var(--sheet);border:1px solid var(--rule);border-radius:12px;padding:16px;margin:14px 0}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{border-bottom:1px solid var(--rule);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--soft);font-weight:600}td.num{font-family:ui-monospace,Menlo,monospace;text-align:right;white-space:nowrap}
.bar{position:relative;height:14px;min-width:160px;background:linear-gradient(90deg,transparent 49.5%,var(--rule) 49.5%,var(--rule) 50.5%,transparent 50.5%)}
.bar i{position:absolute;top:2px;height:10px;border-radius:3px}.pos{background:var(--bar)}.negb{background:var(--neg)}
.tag{display:inline-block;border:1px solid var(--rule);border-radius:999px;padding:0 8px;font-size:12px;color:var(--soft)}
.win{color:var(--ok);font-weight:600}.lose{color:var(--pen);font-weight:600}code{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.card{background:var(--sheet);border:1px solid var(--rule);border-radius:12px;padding:14px}
.big{font-size:28px;font-weight:700;font-family:ui-monospace,Menlo,monospace}a{color:var(--ok)}
"""


def _bar(v: float) -> str:
    v = max(-1.0, min(1.0, v))
    if v >= 0:
        return f'<div class="bar"><i class="pos" style="left:50%;width:{v * 50:.1f}%"></i></div>'
    return f'<div class="bar"><i class="negb" style="left:{50 + v * 50:.1f}%;width:{-v * 50:.1f}%"></i></div>'


def _md_table(text: str, heading: str) -> list:
    sec = text.split(heading, 1)[1]
    rows = [ln for ln in sec.splitlines() if ln.startswith("|")]
    out = []
    for ln in rows[2:]:
        if not ln.startswith("|"):
            break
        out.append([c.strip() for c in ln.strip("|").split("|")])
    return out


def _md_inline(s: str) -> str:
    s = re.sub(r"<!--fact:[a-z0-9_]+-->(.*?)<!--/fact-->", r"\1", s)
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


def build() -> str:
    sc = json.loads((ROOT / "reports" / "selfcheck.json").read_text("utf-8"))
    ex = json.loads((ROOT / "reports" / "exploit_search.json").read_text("utf-8"))
    jury = (ROOT / "reports" / "jury_sim.md").read_text("utf-8")
    fails = (ROOT / "docs" / "FAILURES.md").read_text("utf-8").split("## 2.", 1)[0]
    exh = (ROOT / "reports" / "reward_exhaustive.md").read_text("utf-8")
    diag = {r["policy"]: r for r in sc["diagnostics"]}
    oracle = diag["oracle"]["return"]
    attacks = [r for r in sc["diagnostics"] if r["policy"].startswith("attack:")]
    # junk_explanation is the CORRECT answer with a junk text: it must equal oracle, it is not a dishonest win
    best_attack = max((r for r in attacks if r["policy"] != "attack:junk_explanation"), key=lambda r: r["return"])
    n_cases = re.search(r"Проверено пар \(эталон, ответ\) \| (\d+)", exh).group(1)
    n_viol = re.search(r"Нарушений \| \*\*(\d+)\*\*", exh).group(1)
    n_fail = len(re.findall(r"^\| \d+ \|", fails, re.M))
    p = [f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
         f"<title>Зал атак AuditEnv</title><style>{CSS}</style></head><body><main>",
         "<p><a href='index.html'>← AuditEnv</a></p><h1>Зал атак</h1>",
         "<p class='lede'>Всё, чем мы пытались обмануть награду, сопоставление, контракт и изоляцию, — с измеренным "
         "результатом. Страница собрана из закоммиченных отчётов скриптом <code>tools/build_attacks.py</code>; работает без сети.</p>",
         "<div class='cards'>",
         f"<div class='card'><div class='big'>{len(attacks)}</div>атак на награду в табло self‑check; лучшая — "
         f"<code>{html.escape(best_attack['policy'])}</code> ({best_attack['return']:+.2f}) &lt; oracle ({oracle:+.2f}); "
         "верный ответ с мусорным explanation = oracle</div>",
         f"<div class='card'><div class='big'>{ex['evaluations']}</div>стратегий перебрал автопоиск без эталона; лучшая на отложенных "
         f"эпизодах {ex['dev_heldout']['best_attack']:+.2f} — хуже молчания ({ex['dev_heldout']['silence']:+.2f})</div>",
         f"<div class='card'><div class='big'>{n_cases}</div>малых случаев перебраны полностью: {n_viol} нарушений "
         "монотонности, порядка и цены шага</div>",
         f"<div class='card'><div class='big'>{n_fail}</div>уязвимостей среды найдено и закрыто, у каждой — тест‑сторож</div>",
         "</div>",
         "<h2>1. Атаки на награду в табло self‑check</h2>",
         "<p class='lede'>Режим eval, 20 эпизодов (5 чистых). Атакам <b>разрешено читать эталон</b> — чтобы они были "
         "сильнейшими из возможных. Источник: <code>reports/selfcheck.json</code>.</p>",
         "<section class='scroll'><table><tr><th>Политика / атака</th><th>Что делает</th><th>Возврат</th><th></th>"
         "<th>На чистых</th><th>На ошибочных</th><th>F1 микро</th><th>Итог</th></tr>"]
    for r in sorted(sc["diagnostics"], key=lambda r: -r["return"]):
        name = r["policy"]
        if name.startswith("attack:"):
            if name == "attack:junk_explanation":
                verdict = "<span class='tag'>= oracle: ответ верный, текст не влияет</span>"
            elif r["return"] >= oracle:
                verdict = "<span class='lose'>НЕ хуже oracle — ошибка!</span>"
            else:
                verdict = "<span class='win'>хуже oracle</span>"
        else:
            verdict = "<span class='tag'>базовая</span>"
        p.append(f"<tr><td><code>{html.escape(name)}</code></td><td>{html.escape(WHAT.get(name, ''))}</td>"
                 f"<td class='num'>{r['return']:+.3f}</td><td>{_bar(r['return'])}</td><td class='num'>{r['return_clean']:+.3f}</td>"
                 f"<td class='num'>{r['return_erroneous']:+.3f}</td><td class='num'>{r['micro_F1']:.3f}</td><td>{verdict}</td></tr>")
    p.append("</table></section>")
    p += ["<h2>2. Автопоиск эксплойтов без эталона (CEM)</h2>",
          f"<p class='lede'>Перекрёстная энтропия по пространству из {len(ex['strategy_space'])} параметров стратегии "
          f"({', '.join(html.escape(k) for k in ex['strategy_space'])}), {ex['evaluations']} оценок. Источник: "
          "<code>reports/exploit_search.json</code>.</p><section class='scroll'><table><tr><th>Отложенные dev‑эпизоды</th><th>Возврат</th><th></th></tr>"]
    for k, v in ex["dev_heldout"].items():
        p.append(f"<tr><td>{html.escape(k)}</td><td class='num'>{v:+.3f}</td><td>{_bar(v)}</td></tr>")
    p.append(f"</table><p>Лучшая найденная стратегия: <code>{html.escape(json.dumps(ex['best_theta'], ensure_ascii=False))}</code></p></section>")
    p += ["<h2>3. Симуляция жюри чёрным ящиком</h2>",
          "<p class='lede'>Бекназар написал свои политики и свой оценщик по тексту кейса, не импортируя <code>auditenv</code>: "
          "35 видов ответов на 6 эпизодах (210 прогонов), 0 расхождений с нашим оценщиком. Источник: <code>reports/jury_sim.md</code>, раздел 5b.</p>",
          "<section class='scroll'><table><tr><th>Атака</th><th>Ошибочные</th><th>Чистые</th><th>Итог</th></tr>"]
    for row in _md_table(jury, "### 5b."):
        if len(row) >= 4:
            p.append("<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in row[:4]) + "</tr>")
    p.append("</table></section>")
    p += ["<h2>4. Атаки на контракт и изоляцию: найдено и закрыто</h2>",
          "<p class='lede'>Каждая строка — уязвимость среды, которую мы (или симуляция жюри) нашли и закрыли, с тестом‑сторожем. "
          "Источник: <code>docs/FAILURES.md</code>, раздел 1.</p><section class='scroll'><table><tr><th>#</th><th>Уязвимость</th>"
          "<th>Как нашли</th><th>Исправление</th><th>Тест‑сторож</th></tr>"]
    for ln in fails.splitlines():
        if re.match(r"^\| \d+ \|", ln):
            c = [x.strip() for x in ln.strip("|").split("|")]
            p.append(f"<tr><td>{c[0]}</td><td>{_md_inline(c[1])}</td><td>{_md_inline(c[3])}</td><td>{_md_inline(c[5])}</td>"
                     f"<td>{_md_inline(c[6])}</td></tr>")
    p.append("</table></section>")
    p.append("<p class='lede'>Повторить: <code>make check</code> (табло и атаки), <code>make exploit-search</code>, "
             "<code>make exhaustive</code>, <code>cd jury_sim &amp;&amp; ./run_all.sh</code>. Каталог атак с объяснениями — "
             "<code>docs/ATTACKS.md</code>.</p></main></body></html>")
    return "\n".join(p) + "\n"


if __name__ == "__main__":
    OUT.write_text(build(), "utf-8")
    print(f"attacks: wrote {OUT.relative_to(ROOT)}")
    sys.exit(0)
