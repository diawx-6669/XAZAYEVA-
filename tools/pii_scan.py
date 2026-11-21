"""A6: "no real data" scanner (stdlib only, does not trust the generator).

Looks for things that would mean real personal or financial data in generated episodes and recorded
trajectories:
  * payment card numbers: 13-19 digits (optionally grouped by spaces/dashes) that pass the Luhn check;
  * IBAN: 2 letters + 2 check digits + 11-30 alphanumerics that pass the ISO 13616 mod-97 check;
  * Kazakhstan BIN/IIN: 12 digits that pass the official two-pass mod-11 checksum;
  * e-mail addresses, phone numbers (+7 ... and other +country numbers of 10-15 digits), URLs.

Scope (narrowed on purpose, docs/SAFETY.md): every STRING value of every record and every CSV cell
except the integer money columns (debit_minor, credit_minor, amount_minor, total_minor,
unit_price_minor, quantity): those are integers by schema and a 16-digit amount is money, not a card.
FX rates and timestamps are strings and ARE scanned.

    make pii-scan                 -> 500 fresh episodes + committed episodes + trajectories
    python tools/pii_scan.py --n 50
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INT_COLUMNS = {"debit_minor", "credit_minor", "amount_minor", "total_minor", "unit_price_minor", "quantity"}

CARD_RE = re.compile(r"(?<![\w.:-])(\d(?:[ -]?\d){12,18})(?![\w.:-])")
IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}[A-Z0-9]{11,30})\b")
TWELVE_RE = re.compile(r"(?<!\d)(\d{12})(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")
PHONE_RE = re.compile(r"(?<![\w])\+\d[\d\s()-]{9,17}\d")
URL_RE = re.compile(r"\b(?:https?://|ftp://|www\.)\S+", re.I)


def luhn_ok(digits: str) -> bool:
    s, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        s += d
        alt = not alt
    return s % 10 == 0


def iban_ok(s: str) -> bool:
    r = s[4:] + s[:4]
    num = "".join(str(int(c, 36)) for c in r)
    return int(num) % 97 == 1


def kz_bin_iin_ok(s: str) -> bool:
    d = [int(c) for c in s]
    w1 = list(range(1, 12))
    c = sum(a * b for a, b in zip(d[:11], w1)) % 11
    if c == 10:
        w2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        c = sum(a * b for a, b in zip(d[:11], w2)) % 11
        if c == 10:
            return False
    return c == d[11]


def scan_text(text: str) -> list:
    hits = []
    for m in CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(1))
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            hits.append(("card", m.group(1)))
    for m in IBAN_RE.finditer(text):
        if iban_ok(m.group(1)):
            hits.append(("iban", m.group(1)))
    for m in TWELVE_RE.finditer(text):
        if kz_bin_iin_ok(m.group(1)):
            hits.append(("kz_bin_iin", m.group(1)))
    hits += [("email", m.group(0)) for m in EMAIL_RE.finditer(text)]
    hits += [("phone", m.group(0)) for m in PHONE_RE.finditer(text)]
    hits += [("url", m.group(0)) for m in URL_RE.finditer(text)]
    return hits


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(k, f"{path}/<key>")
            if k in INT_COLUMNS and isinstance(v, int):
                continue
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def scan_files(files: dict, where: str) -> list:
    out = []
    for name, data in sorted(files.items()):
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        if name.endswith(".csv"):
            for i, row in enumerate(csv.DictReader(io.StringIO(text))):
                for col, val in row.items():
                    if col in INT_COLUMNS and re.fullmatch(r"-?\d*", val or ""):
                        continue
                    out += [(where, f"{name}:{i + 2}:{col}", kind, hit) for kind, hit in scan_text(val or "")]
        else:
            docs = [json.loads(x) for x in text.splitlines() if x.strip()] if name.endswith(".jsonl") else [json.loads(text)]
            for i, d in enumerate(docs):
                for p, s in _walk(d):
                    out += [(where, f"{name}:{i + 1}{p}", kind, hit) for kind, hit in scan_text(s)]
    return out


def run(n: int, include_committed: bool = True) -> dict:
    sys.path.insert(0, str(ROOT))
    from auditenv.generator.episode import generate_episode

    cfgs = ["train-easy", "train-global", "dev-mixed", "dev-global", "interaction-heavy", "clean-only"]
    hits, n_ep, n_bytes = [], 0, 0
    for i in range(n):
        cfg, seed = cfgs[i % len(cfgs)], 600000 + i
        ep = generate_episode(seed, cfg)
        n_ep += 1
        n_bytes += sum(len(v) for v in ep.files.values())
        hits += scan_files(ep.files, f"{cfg}#{seed}")
    n_traj = 0
    if include_committed:
        for d in sorted((ROOT / "episodes").glob("*/*/public")):
            files = {p.name: p.read_bytes() for p in d.iterdir()}
            n_ep += 1
            n_bytes += sum(len(v) for v in files.values())
            hits += scan_files(files, d.parent.name)
        tp = ROOT / "trajectories" / "trajectories.jsonl"
        for i, line in enumerate(tp.read_text("utf-8").splitlines()):
            rec = json.loads(line)
            n_traj += 1
            for p, s in _walk({"action": rec.get("action"), "observation": rec.get("observation")}):
                hits += [("trajectories", f"line {i + 1}{p}", kind, hit) for kind, hit in scan_text(s)]
    return {"episodes": n_ep, "fresh": n, "bytes": n_bytes, "trajectory_lines": n_traj, "hits": hits}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    a = ap.parse_args(argv)
    r = run(a.n)
    for h in r["hits"][:30]:
        print("  HIT", *h)
    print(f"pii-scan: {r['episodes']} episodes ({r['fresh']} fresh + committed), {r['bytes'] / 1e6:.1f} MB, "
          f"{r['trajectory_lines']} trajectory lines, {len(r['hits'])} hits")
    return 1 if r["hits"] else 0


if __name__ == "__main__":
    sys.exit(main())
