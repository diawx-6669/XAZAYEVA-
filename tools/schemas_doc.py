"""B14 + B15: docs/SCHEMAS.md generated from every schemas/*.json (field, type, required, constraints), and
the check that no schema is dead (each is referenced by the code that validates artefacts or by a test).

    python tools/schemas_doc.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _t(s: dict, root: dict, depth=0) -> str:
    if depth > 4:
        return "…"
    if "$ref" in s:
        ref = s["$ref"]
        if ref.startswith("#/$defs/"):
            return _t(root["$defs"][ref.split("/")[-1]], root, depth + 1)
        return f"→ `{ref}`"
    if "oneOf" in s:
        return " или ".join(_t(x, root, depth + 1) for x in s["oneOf"])
    if "enum" in s:
        return "одно из " + ", ".join(f"`{x}`" for x in s["enum"][:12]) + (" …" if len(s["enum"]) > 12 else "")
    if "const" in s:
        return f"= `{s['const']}`"
    t = s.get("type", "any")
    t = "/".join(t) if isinstance(t, list) else t
    lim = []
    for k, sym in (("minimum", "≥"), ("maximum", "≤"), ("minLength", "длина ≥"), ("maxLength", "длина ≤"),
                   ("minItems", "элементов ≥"), ("maxItems", "элементов ≤")):
        if k in s:
            lim.append(f"{sym} {s[k]}")
    if "pattern" in s:
        lim.append("шаблон `" + s["pattern"].replace("|", "\\|") + "`")
    if t == "array" and "items" in s:
        t = f"array of ({_t(s['items'], root, depth + 1)})"
    if t == "object" and isinstance(s.get("properties"), dict) and depth > 0:
        t = "object {" + ", ".join(s["properties"]) + "}"
    return t + (f" ({', '.join(lim)})" if lim else "")


def render() -> str:
    out = ["# Справочник JSON Schema", "",
           "Сгенерировано `python tools/schemas_doc.py` из `schemas/*.json`; тест `tests/test_round4_schemas_doc.py` сверяет файл",
           "со схемами и проверяет, что каждая схема используется кодом или тестами (нет «мёртвых»). Валидатор —",
           "`auditenv/jsonschema_lite.py`; `python -m auditenv check-schemas` проверяет по ним каждый артефакт репозитория.", ""]
    for p in sorted((ROOT / "schemas").glob("*.json")):
        s = json.loads(p.read_text("utf-8"))
        out += [f"## `{p.name}`", "", s.get("title", "") or s.get("description", ""), ""]
        props = s.get("properties", {})
        if props:
            req = set(s.get("required", []))
            extra = "запрещены" if s.get("additionalProperties") is False else "разрешены"
            out += [f"Лишние поля: {extra}.", "", "| Поле | Тип и ограничения | Обязательное |", "|---|---|---|"]
            for k, v in props.items():
                out.append(f"| `{k}` | {_t(v, s, 1)} | {'да' if k in req else 'нет'} |")
        elif s.get("type"):
            out.append(f"Тип: {_t(s, s)}.")
        if "oneOf" in s and props:
            out.append(f"\nВарианты (`oneOf`): {len(s['oneOf'])}.")
            for br in s["oneOf"]:
                bp = br.get("properties", {})
                tag = next((f"`{k}` = `{v['const']}`" for k, v in bp.items() if isinstance(v, dict) and "const" in v), None)
                args = next((v for k, v in bp.items() if isinstance(v, dict) and v.get("type") == "object"), None)
                if tag and args is not None:
                    req = set(args.get("required", []))
                    cells = ", ".join(f"`{k}`{'*' if k in req else ''}: {_t(v, s, 1)}" for k, v in args.get("properties", {}).items())
                    out.append(f"* {tag}: {cells or '—'}")
            out.append("\n`*` — обязательное поле.")
        out.append("")
    return "\n".join(out)


def unreferenced() -> list:
    code = "".join(p.read_text("utf-8") for d in ("auditenv", "tests", "tools") for p in (ROOT / d).rglob("*.py"))
    out = []
    for p in sorted((ROOT / "schemas").glob("*.json")):
        stem = p.name.replace(".schema.json", "")
        if p.name not in code and f'"{stem}"' not in code:
            out.append(p.name)
    return out


if __name__ == "__main__":
    (ROOT / "docs" / "SCHEMAS.md").write_text(render(), "utf-8")
    print(f"schemas-doc: wrote docs/SCHEMAS.md; unreferenced schemas: {unreferenced() or 'none'}")
