"""Time helpers. Only fixed-offset (no-DST) zones are used, so no tzdata is needed."""

from datetime import date, datetime, timedelta, timezone

# IANA name -> (hours, minutes) UTC offset valid for 2026 (none of these observe DST).
TIMEZONES = {
    "Asia/Almaty": (5, 0),
    "Asia/Tashkent": (5, 0),
    "Asia/Dubai": (4, 0),
    "Asia/Kolkata": (5, 30),
    "Asia/Tokyo": (9, 0),
    "America/Bogota": (-5, 0),
    "America/Lima": (-5, 0),
    # extreme offsets, still without DST: quarter hour, +14 (dateline), -11
    "Asia/Kathmandu": (5, 45),
    "Pacific/Kiritimati": (14, 0),
    "Pacific/Pago_Pago": (-11, 0),
}


def offset_minutes(name: str) -> int:
    h, m = TIMEZONES[name]
    return h * 60 + (m if h >= 0 else -m)


def utc_offset_str(name: str) -> str:
    """'+05:00', '-05:00', '+05:45': the explicit offset that policy.json states next to the zone name."""
    off = offset_minutes(name)
    sign = "+" if off >= 0 else "-"
    return f"{sign}{abs(off) // 60:02d}:{abs(off) % 60:02d}"


def tzinfo_for(name: str) -> timezone:
    return timezone(timedelta(minutes=offset_minutes(name)))


def parse_ts(s: str) -> datetime:
    if not isinstance(s, str):
        raise ValueError("timestamp must be a string")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError("timestamp without offset")
    return dt


def fmt_ts(dt: datetime, utc: bool = False) -> str:
    if utc:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="seconds")


def local_date(dt: datetime, tz) -> date:
    return dt.astimezone(tz).date()


def is_business_day(d: date) -> bool:
    return d.weekday() < 5


def prev_business_day(d: date) -> date:
    d -= timedelta(days=1)
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


def next_business_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_business_day(d):
        d += timedelta(days=1)
    return d


def policy_rate_date(d: date) -> date:
    """fx_missing_rate = previous_business_day: the rate date for a local transaction date."""
    return d if is_business_day(d) else prev_business_day(d)


def add_months(dt: datetime, k: int) -> datetime:
    y, m = divmod(dt.month - 1 + k, 12)
    return dt.replace(year=dt.year + y, month=m + 1, day=1)


def month_str(d) -> str:
    return f"{d.year:04d}-{d.month:02d}"
