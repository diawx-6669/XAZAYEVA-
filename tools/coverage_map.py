"""A19: pairwise coverage of the generator's factors on 1000 seeds, an SVG heat map and the list of
combinations that never occurred - each with its reason.

Factors of every injected issue:
  variant      error type / variant (provenance)
  tz_sign      sign of the company's UTC offset (+ / -)
  exponent     minor-unit exponent of the affected document's currency (0 / 2 / 3)
  base         base currency of the episode
  interaction  none / duplicate_fx / partial_fx_cutoff (scenario mutations come first, alphabetically)
  weekend      the affected document's LOCAL date is Saturday/Sunday (yes / no)

    make coverage-map  -> reports/coverage_map.md + reports/coverage_map.svg
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_runs import CONFIGS, ROOT, episodes  # noqa: E402

EXP = {"KZT": 2, "USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}
VARIANTS = ["duplicate_invoice/copy", "duplicate_invoice/copy_as_posted", "duplicate_invoice/paid_twice",
            "payment_allocation/unallocated", "payment_allocation/partial", "payment_allocation/wrong_invoice",
            "fx_rate/adjacent_day", "fx_rate/utc_date", "fx_rate/inverted", "fx_rate/historical_rate",
            "fx_rate/wrong_pair", "fx_rate/due_date", "period_cutoff/utc_trap", "period_cutoff/backdated_posting",
            "period_cutoff/prior_period"]
DOMAINS = {"variant": VARIANTS, "tz_sign": ["+", "-"], "exponent": ["0", "2", "3"],
           "base": ["KZT", "USD", "EUR", "JPY", "KWD"], "interaction": ["none", "duplicate_fx", "partial_fx_cutoff"],
           "weekend": ["no", "yes"]}
FACTORS = list(DOMAINS)


def _config_bases():
    from auditenv.config import load_config

    out = set()
    for c in CONFIGS:
        out |= set(load_config(c)["base_currencies"])
    return out


def reason(f1, v1, f2, v2, bases_in_configs) -> str:
    """Why a pair never occurred: structural rule, generator restriction, config choice, or chance."""
    d = {f1: v1, f2: v2}
    var, inter, base, exp = d.get("variant"), d.get("interaction"), d.get("base"), d.get("exponent")
    if base and base not in bases_in_configs:
        return f"конфиги: базовая валюта {base} не включена ни в один открытый конфиг"
    if var and inter == "partial_fx_cutoff" and not var.startswith(("fx_rate", "payment_allocation")):
        return "структура: сценарий partial_fx_cutoff состоит из fx_rate + payment_allocation"
    if var and inter == "duplicate_fx" and not var.startswith(("fx_rate", "duplicate_invoice")):
        return "структура: сценарий duplicate_fx состоит из duplicate_invoice + fx_rate"
    if var and inter == "partial_fx_cutoff" and var not in ("payment_allocation/partial",) and var.startswith("payment_allocation"):
        return "структура: в partial_fx_cutoff платёж распределён частично (вариант partial)"
    if var and inter == "partial_fx_cutoff" and var == "fx_rate/inverted":
        return "генератор: вариант inverted запрещён в partial_fx_cutoff (FAILURES п. 10)"
    if var and inter == "duplicate_fx" and var.startswith("duplicate_invoice") and var != "duplicate_invoice/copy_as_posted":
        return "структура: дубль в duplicate_fx — вариант copy_as_posted (копия, проведённая по неверному курсу)"
    if var and inter and inter != "none" and var.startswith("period_cutoff"):
        return "структура: cutoff не входит ни в один сценарий"
    if var == "duplicate_invoice/copy_as_posted" and inter == "none":
        return "структура: copy_as_posted бывает только внутри сценария duplicate_fx"
    if var in ("payment_allocation/wrong_invoice",) and exp is not None:
        return "генератор: wrong_invoice только в базовой валюте (LIMITATIONS п. 5) — экспонента = экспонента базы"
    if var and var.startswith("fx_rate") and exp is not None and base is None:
        return "данные: fx_rate бывает только у иностранного документа; такой экспоненты нет среди иностранных валют выпавших эпизодов"
    if base and exp is not None and var is None:
        return "редкое сочетание валют базы и документа"
    return "не выпало на этой выборке (редкое сочетание)"


def collect(n: int):
    from auditenv.timeutil import TIMEZONES, parse_ts, tzinfo_for

    rows = []
    for cfg, seed, ep in episodes(n, 750000):
        man = json.loads(ep.files["manifest.json"])
        tz = man["timezone"]
        sign = "+" if TIMEZONES[tz][0] > 0 or (TIMEZONES[tz][0] == 0 and TIMEZONES[tz][1] >= 0) else "-"
        scen = sorted(ep.provenance["plan"].get("scenarios", []))
        order_to_scen = {}
        k = 1
        for s in scen:
            order_to_scen[k], order_to_scen[k + 1] = s, s
            k += 2
        for mu in ep.provenance["mutations"]:
            doc = next((a["document"] for a in mu["after"] if a.get("document")), None) or \
                next((b["document"] for b in mu["before"] if b.get("document")), {})
            ts = doc.get("issued_at") or doc.get("timestamp")
            wk = "?"
            if ts:
                wk = "yes" if parse_ts(ts).astimezone(tzinfo_for(tz)).weekday() >= 5 else "no"
            rows.append({"variant": f"{mu['type']}/{mu.get('variant', '?')}", "tz_sign": sign,
                         "exponent": str(EXP.get(doc.get("currency"), "?")), "base": man["base_currency"],
                         "interaction": order_to_scen.get(mu.get("order"), "none"), "weekend": wk,
                         "config": cfg, "seed": seed})
    return rows


def pair_counts(rows):
    out = {}
    for f1, f2 in itertools.combinations(FACTORS, 2):
        c = {}
        for r in rows:
            c[(r[f1], r[f2])] = c.get((r[f1], r[f2]), 0) + 1
        out[(f1, f2)] = c
    return out


def svg(rows) -> str:
    cols = [(f, v) for f in FACTORS[1:] for v in DOMAINS[f]]
    cw, rh, left, top = 46, 22, 270, 160
    w, h = left + cw * len(cols) + 20, top + rh * len(VARIANTS) + 40
    cnt = {}
    for r in rows:
        for f, v in cols:
            if r[f] == v:
                cnt[(r["variant"], f, v)] = cnt.get((r["variant"], f, v), 0) + 1
    mx = max(cnt.values()) if cnt else 1
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="system-ui,sans-serif" font-size="11">',
           '<style>.t{fill:#0d253d}.z{fill:#ea2261;font-weight:700}@media (prefers-color-scheme:dark){.t{fill:#e8ecf8}}</style>',
           f'<text x="10" y="20" class="t" font-size="14" font-weight="600">Попарное покрытие: вариант ошибки × остальные факторы ({len(rows)} issue)</text>',
           '<text x="10" y="38" class="t">цвет — число issue (лог-шкала); «0» красным — сочетание ни разу не встретилось</text>']
    import math

    for j, (f, v) in enumerate(cols):
        x = left + j * cw + cw / 2
        out.append(f'<text class="t" transform="translate({x},{top - 8}) rotate(-60)">{f}={v}</text>')
    for i, var in enumerate(VARIANTS):
        y = top + i * rh
        out.append(f'<text class="t" x="{left - 6}" y="{y + 15}" text-anchor="end">{var}</text>')
        for j, (f, v) in enumerate(cols):
            n = cnt.get((var, f, v), 0)
            x = left + j * cw
            if n:
                a = 0.15 + 0.85 * math.log1p(n) / math.log1p(mx)
                out.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{rh - 2}" fill="#533afd" fill-opacity="{a:.2f}"/>')
                out.append(f'<text x="{x + cw / 2}" y="{y + 15}" text-anchor="middle" fill="{"#fff" if a > 0.55 else "#0d253d"}">{n}</text>')
            else:
                out.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{rh - 2}" fill="none" stroke="#ea2261" stroke-opacity="0.35"/>')
                out.append(f'<text class="z" x="{x + cw / 2}" y="{y + 15}" text-anchor="middle">0</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def render(rows, n) -> str:
    pc = pair_counts(rows)
    bases = _config_bases()
    total = sum(len(DOMAINS[a]) * len(DOMAINS[b]) for a, b in pc)
    seen = sum(len(c) for c in pc.values())
    out = ["# Карта попарного покрытия генератора", "",
           f"Сгенерировано `make coverage-map` (`tools/coverage_map.py`): {n} seed по 6 открытым конфигам (seed 750000+),",
           f"{len(rows)} внесённых ошибок. Факторы: вариант ошибки, знак смещения пояса, экспонента валюты документа,",
           "базовая валюта, сценарий взаимодействия, выходной день (местная дата документа).", "",
           "![Тепловая карта](coverage_map.svg)", "",
           f"**Покрыто пар значений: {seen} из {total} теоретически возможных** (все пары факторов). Ниже — каждая",
           "непокрытая пара с причиной. Причины проставлены правилами в `tools/coverage_map.py::reason`: «структура» —",
           "сочетание невозможно по определению ошибки или сценария; «генератор» — сознательное ограничение",
           "(`docs/LIMITATIONS.md`, п. 5); «конфиги» — значение не включено в открытые конфиги; иначе — редкость.", "",
           "| Факторы | Покрыто | Из возможных |", "|---|---|---|"]
    for (a, b), c in pc.items():
        out.append(f"| {a} × {b} | {len(c)} | {len(DOMAINS[a]) * len(DOMAINS[b])} |")
    out += ["", "## Ни разу не встретившиеся сочетания", "", "| Факторы | Сочетание | Причина |", "|---|---|---|"]
    from collections import Counter

    why = Counter()
    for (a, b), c in pc.items():
        for va in DOMAINS[a]:
            for vb in DOMAINS[b]:
                if (va, vb) not in c:
                    r = reason(a, va, b, vb, bases)
                    why[r.split(":")[0]] += 1
                    out.append(f"| {a} × {b} | `{va}` × `{vb}` | {r} |")
    out += ["", "## Итог по причинам", "", "| Причина | Пар |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in why.most_common()]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    rows = collect(a.n)
    (ROOT / "reports" / "coverage_map.svg").write_text(svg(rows), "utf-8")
    (ROOT / "reports" / "coverage_map.md").write_text(render(rows, a.n), "utf-8")
    print(f"coverage-map: {len(rows)} issues from {a.n} seeds -> reports/coverage_map.md, reports/coverage_map.svg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
