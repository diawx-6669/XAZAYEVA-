"""v1.4: the FX calendar has public holidays. policy.json lists them, fx.csv has no rates on them, and a
document dated on a holiday is converted at the previous business day's rate."""

import csv
import io
import json
from datetime import date

from auditenv.generator.episode import generate_episode
from auditenv.timeutil import is_business_day, is_fx_holiday, policy_rate_date


def test_calendar_rules():
    assert is_fx_holiday(date(2026, 12, 16)) and not is_business_day(date(2026, 12, 16))
    assert is_fx_holiday(date(2026, 8, 31))  # 30 August 2026 is a Sunday: the day off moves to Monday
    assert policy_rate_date(date(2026, 8, 31)) == date(2026, 8, 28)  # Monday holiday -> Friday


def test_policy_lists_holidays_and_fx_has_no_rows_on_them():
    seen = 0
    for cfg in ("dev-mixed", "dev-global", "train-global"):
        for seed in range(3):
            ep = generate_episode(seed, cfg)
            pol = json.loads(ep.files["policy.json"])
            hol = set(pol["fx_holidays"])
            days = {r["date"] for r in csv.DictReader(io.StringIO(ep.files["fx.csv"].decode()))}
            assert not hol & days
            assert all(is_fx_holiday(date.fromisoformat(d)) for d in hol)
            seen += bool(hol)
    assert seen
