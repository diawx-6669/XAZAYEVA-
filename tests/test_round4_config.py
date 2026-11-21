"""A3: docs/CONFIG_REFERENCE.md is generated from the schema; validate-config explains bad configs."""

import json

import pytest

from auditenv.cli import main
from auditenv.config_doc import REF_PATH, problems, render_reference
from auditenv.paths import CONFIGS_DIR


def test_config_reference_up_to_date():
    assert REF_PATH.read_text("utf-8") == render_reference(), "run: python -m auditenv validate-config --write-reference"


def test_every_named_config_is_valid():
    for p in sorted(CONFIGS_DIR.glob("*.json")):
        raw = json.loads(p.read_text("utf-8"))
        if isinstance(raw, dict) and "name" in raw and "version" in raw:
            assert problems(p) == [], p.name


BAD = [
    ({"n_errors": [3, 1]}, "n_errors: min > max"),
    ({"foreign_share": 1.5, "tolerance": 2}, "foreign_share: 1.5 > 1"),  # two problems at once
    ({"timezones": ["Europe/Moscow"]}, "timezones/0"),
    ({"max_steps": 50}, "max_steps"),
    ({"errors": {"duplicate_invoice": 0, "payment_allocation": 0, "period_cutoff": 0}, "foreign_currencies": []},
     "no foreign currency"),
]


@pytest.mark.parametrize("cfg,needle", BAD, ids=["min_gt_max", "two_errors", "unknown_tz", "max_steps", "fx_without_foreign"])
def test_bad_configs_are_explained(tmp_path, capsys, cfg, needle):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"name": "bad", "version": "1", **cfg}), "utf-8")
    assert main(["validate-config", str(p)]) == 1
    out = capsys.readouterr().out
    assert "НЕВЕРНЫЙ КОНФИГ" in out and needle in out, out
    if "tolerance" in cfg:  # every schema problem is listed, with the expected range and the default
        assert "tolerance: additional property" in out and "ожидается number: 0…1" in out and "2 проблем" in out


def test_not_json_and_missing_file(tmp_path, capsys):
    p = tmp_path / "x.json"
    p.write_text("{oops", "utf-8")
    assert main(["validate-config", str(p), str(tmp_path / "missing.json")]) == 1
    out = capsys.readouterr().out
    assert "не JSON" in out and "файл не найден" in out


def test_good_config_ok(capsys):
    assert main(["validate-config", str(CONFIGS_DIR / "dev-mixed.json")]) == 0
    assert "OK" in capsys.readouterr().out
