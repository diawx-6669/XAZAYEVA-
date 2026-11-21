"""A4: reproducibility certificate - hashes that must be equal on every machine.

    make repro-cert                          -> reports/repro_certificate.{json,md} for THIS machine
    python tools/repro_cert.py --compare F   -> table "this machine vs F" (F = the JSON from another machine,
                                                 e.g. the CI artefact reports/repro_certificate.json or a Mac)
    python tools/repro_cert.py --check       -> recompute and compare with the committed certificate

What is certified (all independent of wall-clock, CPU, OS, Python version):
  * the 20 open episodes (10 train + 10 dev), regenerated IN MEMORY from (seed, config): public and grader
    digests, compared with episodes/*/index.json;
  * the 3 golden episodes (tests/golden_hashes.json);
  * the effective config hashes;
  * the deterministic part of reports/selfcheck.json (everything except the header and "timing") and the
    grader-log chain head - produced by the last `make check` on that machine, so run `make check` first.
Exit code 1 on any mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auditenv.canon import dumps, files_digest  # noqa: E402

OUT_JSON = ROOT / "reports" / "repro_certificate.json"
OUT_MD = ROOT / "reports" / "repro_certificate.md"


def selfcheck_part() -> dict:
    p = ROOT / "reports" / "selfcheck.json"
    rep = json.loads(p.read_text("utf-8"))
    det = {k: v for k, v in rep.items() if k not in ("header", "timing")}
    return {"selfcheck/deterministic": hashlib.sha256(dumps(det).encode()).hexdigest(),
            "selfcheck/total": f"{rep['total']:.1f}/{rep['max_total']}",
            "selfcheck/grader_log_head": rep.get("grader_log_head", "")}


def compute() -> dict:
    from auditenv.config import config_hash, load_config
    from auditenv.generator.episode import generate_episode
    from auditenv.generator.export import grader_files

    items = {}
    for split in ("train", "dev"):
        for e in json.loads((ROOT / "episodes" / split / "index.json").read_text("utf-8")):
            ep = generate_episode(e["seed"], e["config"])
            key = f"episode/{split}/{e['config']}#{e['seed']}"
            items[key + "/public"] = files_digest(ep.files)
            items[key + "/grader"] = files_digest(grader_files(ep))
            items[key + "/committed_index_match"] = str(items[key + "/public"] == e["public_digest"]
                                                       and items[key + "/grader"] == e["grader_digest"]).lower()
    for key in sorted(json.loads((ROOT / "tests" / "golden_hashes.json").read_text("utf-8"))):
        cfg, seed = key.split("#")
        ep = generate_episode(int(seed), cfg)
        items[f"golden/{key}/public"] = files_digest(ep.files)
        items[f"golden/{key}/truth"] = hashlib.sha256(dumps(ep.truth).encode()).hexdigest()
    for p in sorted((ROOT / "configs").glob("*.json")):
        raw = json.loads(p.read_text("utf-8"))
        if isinstance(raw, dict) and "name" in raw and "version" in raw:
            items[f"config/{p.stem}"] = config_hash(load_config(p))
    items.update(selfcheck_part())
    return {"machine": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                        "system": platform.system(), "machine": platform.machine()},
            "items": items}


def render_md(cert: dict, other: dict | None = None, other_name: str = "") -> str:
    m = cert["machine"]
    lines = ["# Сертификат воспроизводимости", "",
             f"Машина: Python {m['python']} ({m['implementation']}), {m['system']} {m['machine']}.",
             "Сгенерировано `make repro-cert` (`tools/repro_cert.py`). Хеши не зависят от времени, процессора, ОС и",
             "версии Python: 20 открытых эпизодов пересобираются в памяти из (seed, config) и сверяются с",
             "`episodes/*/index.json`; плюс 3 golden‑эпизода, хеши конфигов и детерминированная часть",
             "`reports/selfcheck.json` (всё, кроме заголовка и замеров времени) после `make check`.", "",
             "## Как сверить свою машину (Беке, Ералы, CI)", "",
             "```text",
             "make check                     # пересобирает reports/selfcheck.json на вашей машине",
             "make repro-cert-check          # пересчитать и сравнить с закоммиченным сертификатом",
             "```", "",
             "Сравнить два файла (например, артефакт CI `reports/repro_certificate.json` и файл с Мака):", "",
             "```text",
             "python tools/repro_cert.py --out /tmp/mac.json            # на Маке",
             "python tools/repro_cert.py --compare /tmp/mac.json        # здесь: таблица совпадений",
             "```", ""]
    items = cert["items"]
    if other is None:
        n_ok = sum(1 for k, v in items.items() if k.endswith("committed_index_match") and v == "true")
        lines += [f"Эпизодов, совпавших с `index.json`: **{n_ok}/20**. Итог self‑check: **{items['selfcheck/total']}**.", "",
                  "| Что | Хеш (первые 16 знаков) |", "|---|---|"]
        lines += [f"| `{k}` | `{v[:16]}` |" for k, v in items.items() if not k.endswith("committed_index_match")]
    else:
        om = other["machine"]
        rows, bad = [], 0
        for k in sorted(set(items) | set(other["items"])):
            a, b = items.get(k, "—"), other["items"].get(k, "—")
            ok = a == b
            bad += not ok
            rows.append(f"| `{k}` | `{a[:16]}` | `{b[:16]}` | {'да' if ok else '**НЕТ**'} |")
        lines += [f"Сравнение: эта машина (Python {m['python']}, {m['system']} {m['machine']}) против {other_name} "
                  f"(Python {om['python']}, {om['system']} {om['machine']}): **{len(rows) - bad}/{len(rows)} совпало**.", "",
                  "| Что | Здесь | Там | Совпало |", "|---|---|---|---|"] + rows
    return "\n".join(lines) + "\n"


def compare(a: dict, b: dict) -> list:
    return sorted(k for k in set(a["items"]) | set(b["items"]) if a["items"].get(k) != b["items"].get(k))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the certificate JSON here (default reports/repro_certificate.json + .md)")
    ap.add_argument("--compare", help="certificate JSON from another machine")
    ap.add_argument("--check", action="store_true", help="compare with the committed reports/repro_certificate.json")
    a = ap.parse_args(argv)
    cert = compute()
    bad_idx = [k for k, v in cert["items"].items() if k.endswith("committed_index_match") and v != "true"]
    if a.compare or a.check:
        path = Path(a.compare) if a.compare else OUT_JSON
        other = json.loads(path.read_text("utf-8"))
        diff = compare(cert, other)
        print(render_md(cert, other, str(path)).split("\n| Что |")[0].splitlines()[-2])
        for k in diff:
            print(f"  MISMATCH {k}: here {cert['items'].get(k, '—')[:16]} there {other['items'].get(k, '—')[:16]}")
        print(f"repro-cert: {len(cert['items']) - len(diff)}/{len(cert['items'])} items equal, {len(bad_idx)} episodes differ from index.json")
        return 1 if diff or bad_idx else 0
    out = Path(a.out) if a.out else OUT_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cert, indent=1, sort_keys=True) + "\n", "utf-8")
    if not a.out:
        OUT_MD.write_text(render_md(cert), "utf-8")
    print(f"repro-cert: {len(cert['items'])} items, {20 - len(bad_idx)}/20 episodes match index.json -> {out}")
    return 1 if bad_idx else 0


if __name__ == "__main__":
    sys.exit(main())
