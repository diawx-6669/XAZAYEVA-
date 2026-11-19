"""Money: integer minor units, currency exponents, Decimal FX conversion. No floats."""

import decimal
import re
from decimal import Decimal, localcontext

EXPONENTS = {"KZT": 2, "USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}
ROUNDING_MODES = {
    "ROUND_HALF_EVEN": decimal.ROUND_HALF_EVEN,
    "ROUND_HALF_UP": decimal.ROUND_HALF_UP,
}
_RATE_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")


def exponent(cur: str, table=None) -> int:
    return (table or EXPONENTS)[cur]


def parse_rate(s) -> Decimal:
    if isinstance(s, Decimal):
        return s
    if not isinstance(s, str) or not _RATE_RE.match(s):
        raise ValueError("rate must be a decimal string")
    d = Decimal(s)
    if d <= 0:
        raise ValueError("rate must be positive")
    return d


def _check_int(x):
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError("money amounts must be int minor units")


def convert_minor(amount_minor: int, src: str, tgt: str, rate, rounding="ROUND_HALF_EVEN", exponents=None) -> int:
    """Convert minor units of `src` into minor units of `tgt`.

    rate = units of tgt per 1 unit of src (decimal string). Result is rounded once
    to an integer number of tgt minor units with the policy rounding mode.
    """
    _check_int(amount_minor)
    if src == tgt:
        return amount_minor
    ex = exponents or EXPONENTS
    r = parse_rate(rate)
    with localcontext() as ctx:
        ctx.prec = 60
        v = (Decimal(amount_minor) * r).scaleb(ex[tgt] - ex[src])
        return int(v.quantize(Decimal(1), rounding=ROUNDING_MODES[rounding]))


def quantize_sig(x: Decimal, sig: int = 6) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 60
        q = Decimal(1).scaleb(x.adjusted() - sig + 1)
        return x.quantize(q, rounding=decimal.ROUND_HALF_EVEN)


def rate_str(x: Decimal) -> str:
    s = format(x, "f")
    return s


def invert_rate(rate: str, sig: int = 8) -> str:
    with localcontext() as ctx:
        ctx.prec = 60
        return rate_str(quantize_sig(Decimal(1) / parse_rate(rate), sig))


def format_minor(amount_minor: int, cur: str) -> str:
    _check_int(amount_minor)
    e = EXPONENTS[cur]
    return rate_str(Decimal(amount_minor).scaleb(-e))
