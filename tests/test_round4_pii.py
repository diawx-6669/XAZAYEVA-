"""A6: no real personal or financial data. make check scans a small sample; `make pii-scan` scans 500
fresh episodes + the committed ones + all trajectories (set AUDITENV_PII_N to change the sample here)."""

import importlib.util
import json
import os

from auditenv.generator.episode import generate_episode
from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("pii_scan", ROOT / "tools" / "pii_scan.py")
pii = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pii)


def test_checksums_on_known_values():
    assert pii.luhn_ok("4111111111111111") and not pii.luhn_ok("4111111111111112")
    assert pii.iban_ok("KZ86125KZT5004100100") and not pii.iban_ok("KZ87125KZT5004100100")
    assert pii.kz_bin_iin_ok("900101300007") and not pii.kz_bin_iin_ok("900101300008")


def test_scanner_finds_planted_data():
    ep = generate_episode(5, "dev-mixed")
    files = dict(ep.files)
    inv = [json.loads(x) for x in files["invoices.jsonl"].decode().splitlines()]
    inv[0]["line_items"][0]["description"] = "card 4111 1111 1111 1111, IBAN KZ86125KZT5004100100, IIN 900101300007"
    inv[1]["line_items"][0]["description"] = "mail a.b@example.kz, call +7 (701) 123-45-67, see https://bank.kz/x"
    files["invoices.jsonl"] = "".join(json.dumps(x) + "\n" for x in inv).encode()
    kinds = sorted({h[2] for h in pii.scan_files(files, "planted")})
    assert kinds == ["card", "email", "iban", "kz_bin_iin", "phone", "url"]


def test_generated_episodes_contain_no_real_data():
    n = int(os.environ.get("AUDITENV_PII_N", "12"))
    r = pii.run(n, include_committed=False)
    assert r["hits"] == [], r["hits"][:5]


def test_our_ids_rates_and_timestamps_are_not_flagged():
    ep = generate_episode(9008, "interaction-heavy")
    assert pii.scan_files(ep.files, "x") == []
    for s in ["2026-10-30T23:06:00+00:00", "fx:2026-10-30:KWD:KZT", "0.00213456", "ep-yrbb7hd9q6", "JE-P4BSKGR6"]:
        assert pii.scan_text(s) == [], s


def test_opaque_twins_are_not_flagged():
    from auditenv.generator.transforms import transform_episode

    for s in range(3):
        twin = transform_episode(generate_episode(700000 + s, "dev-mixed"), s, opaque=True)[0]
        assert pii.scan_files(twin.files, "twin") == []
