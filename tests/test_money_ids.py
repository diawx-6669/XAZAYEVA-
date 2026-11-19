from decimal import Decimal

import pytest

from auditenv.ids import IdFactory, derive_seed, make_rng
from auditenv.money import convert_minor, format_minor, invert_rate, parse_rate


def test_convert_minor_exponents_and_half_even():
    assert convert_minor(10000, "USD", "KZT", "480.25") == 4802500  # 100.00 USD -> 48025.00 KZT
    assert convert_minor(1000, "JPY", "KZT", "3.2") == 320000  # exp 0 -> exp 2
    assert convert_minor(1000, "KWD", "KZT", "1563.2") == 156320  # 1.000 KWD (exp 3)
    assert convert_minor(1, "USD", "KZT", "0.5") == 0  # 0.5 -> banker's rounding to even
    assert convert_minor(3, "USD", "KZT", "0.5") == 2  # 1.5 -> 2
    assert convert_minor(123, "KZT", "KZT", "999") == 123


def test_money_rejects_floats_and_bad_rates():
    with pytest.raises(TypeError):
        convert_minor(1.5, "USD", "KZT", "1")
    with pytest.raises(TypeError):
        convert_minor(True, "USD", "KZT", "1")
    for bad in ("1e3", "-1", "abc", 1.5, "0"):
        with pytest.raises((ValueError, TypeError)):
            parse_rate(bad)


def test_rate_helpers():
    assert parse_rate("480.1234") == Decimal("480.1234")
    assert invert_rate("400") == "0.0025000000"  # 8 significant digits
    assert format_minor(12345, "KZT") == "123.45"
    assert format_minor(12345, "KWD") == "12.345"


def test_streams_independent_and_deterministic():
    assert derive_seed(1, "story") == derive_seed(1, "story")
    assert derive_seed(1, "story") != derive_seed(1, "naming") != derive_seed(2, "story")
    assert make_rng(5, "x").random() == make_rng(5, "x").random()


def test_ids_unique_unpredictable_and_prefixed():
    f = IdFactory(make_rng(3, "naming"))
    ids = [f.new("invoice") for _ in range(500)]
    assert len(set(ids)) == 500
    assert all(i.startswith(f.prefix["invoice"] + "-") for i in ids)
    tokens = [i.split("-")[1] for i in ids]
    assert tokens != sorted(tokens)  # not sequential
    kinds = {k: IdFactory(make_rng(3, "naming")).prefix[k] for k in ("entity", "invoice", "payment", "doc", "row")}
    assert len(set(kinds.values())) == 5  # namespaces never collide
